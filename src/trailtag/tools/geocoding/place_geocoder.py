import threading
import time
from src.api.logger_config import get_logger
import os
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
import requests

# 設定 logger 以便記錄錯誤與警告訊息
logger = get_logger(__name__)


class TokenBucket:
    """
    Token Bucket 演算法速率限制器

    實作 Google Geocoding API 的速率限制機制，防止超出 API 配額限制。
    使用經典的 Token Bucket 演算法，允許適度突發請求但保持長期穩定的速率。

    算法特性:
        - 穩定速率: 保證每秒不超過指定請求數
        - 突發支援: 允許短時間內的高速請求
        - 線程安全: 使用鎖機制保證並發安全
        - 自動補充: 隨時間推移自動補充 token

    參數說明:
        rate (float): 每秒 token 補充率，決定穩定狀態下的最大速率
        burst (int): token 桶容量，決定可承受的最大突發數量

    使用情境:
        - API 速率限制: 防止超出供應商的請求限制
        - 資源保護: 避免集中請求導致系統過載
        - 成本控制: 管理付費 API 的使用量
    """

    def __init__(self, rate: float, burst: int):
        """
        初始化 Token Bucket 速率限制器

        設定基本參數和初始狀態，包含線程安全的鎖機制和時間追蹤。

        Args:
            rate (float): Token 補充速率 (每秒)
                設定穩定狀態下的最大請求頻率
                例: 5.0 表示每秒最多 5 個請求
            burst (int): Token 桶最大容量
                允許的最大突發請求數量
                例: 10 表示允許短時間內 10 個請求

        初始化狀態:
            - tokens: 起始全滿 (burst 數量)
            - timestamp: 現在的單調時間
            - lock: 線程安全鎖
        """
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.lock = threading.Lock()
        self.timestamp = time.monotonic()

    def consume(self, tokens: int = 1) -> bool:
        """
        嘗試消耗指定數量的 Token

        實現 Token Bucket 演算法的核心邏輯，包含 Token 補充和消耗檢查。
        使用線程鎖確保在並發環境中的正確性。

        Token 補充邏輯:
            1. 計算距離上次操作的時間間隔
            2. 按照設定速率補充 Token
            3. 確保 Token 數量不超過最大容量 (burst)
            4. 更新時間戳為目前時間

        消耗檢查:
            - 若當前 Token 足夠：扣除並回傳 True
            - 若 Token 不足：不扣除且回傳 False

        Args:
            tokens (int): 需要消耗的 Token 數量
                預設為 1，一般一個 API 請求消耗一個 Token

        Returns:
            bool: Token 消耗結果
                True: 成功消耗，可以執行請求
                False: Token 不足，需要等待補充

        線程安全:
            使用 threading.Lock() 保證原子性操作

        時間精度:
            使用 time.monotonic() 避免系統時間調整影響
        """
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.timestamp
            # 補充 token，確保不超過 burst 上限
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.timestamp = now
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False


# 模組層級的 Token Bucket 實例
# 配置: 5 次/秒的穩定速率，10 次的突發容量
# 這個設定符合 Google Geocoding API 的免費額度限制
_token_bucket = TokenBucket(rate=5, burst=10)


class PlaceGeocodeToolInput(BaseModel):
    """
    地理編碼工具輸入參數模型

    定義 Google Geocoding API 查詢所需的地理資訊結構。
    使用階層式的地址結構提高地理編碼的精度和成功率。

    地址組成策略:
        最終地址 = "{place}, {city}, {country}"
        例: "故宮博物院, 台北市, 台灣"

    Attributes:
        country (str): 國家名稱，提供地理上下文 (如 '台灣', '日本')
        city (str): 城市名稱，縮小搜尋範圍 (如 '台北市', '東京')
        place (str): 具體地點名稱，主要查詢目標 (如 '故宮博物院', '東京鐵塔')

    資料品質要求:
        - 使用正確的繁體/簡體中文名稱
        - 提供完整的地名而非簡稱
        - 避免特殊字元或縮寫
        - 保持一致的命名風格

    使用範例:
        PlaceGeocodeToolInput(
            country="日本",
            city="東京",
            place="東京鐵塔"
        )
    """

    country: str = Field(..., description="國家名稱")
    city: str = Field(..., description="城市名稱")
    place: str = Field(..., description="地點名稱")


class PlaceGeocodeTool(BaseTool):
    """
    Google Geocoding API 地理編碼工具

    這是 TrailTag 系統中負責地理座標轉換的核心工具，將文字形式的地點資訊
    轉換為精確的 WGS84 座標系統座標。整合了速率限制、錯誤處理和結果驗證。

    技術特色:
        - Google Maps 整合: 使用官方 Geocoding API 確保結果品質
        - 智慧速率限制: Token Bucket 演算法防止 API 濫用
        - 健全錯誤處理: 多層次的例外捕獲與日誌記錄
        - 空安全設計: API 密鑰自動驗證與環境變數管理

    API 效能配置:
        - 速率限制: 5 次/秒，突發 10 次
        - 連線超時: 10 秒，平衡速度與穩定性
        - 重試機制: 可擴展的指數退縮策略

    地理資料品質:
        - 座標精度: 一般為 5-10 公尺精度
        - 座標系統: WGS84 (世界大地測量系統 1984)
        - 格式標準: 經緯度十進制度數格式
        - 資料來源: Google Maps 官方資料庫

    使用限制:
        - 需要有效的 GOOGLE_API_KEY 環境變數
        - 受 Google Cloud API 配額限制約束
        - 需要網路連線存取 Google 服務
        - 地理名稱識別依賴 Google Maps 數據庫覆蓋範圍

    輸出格式:
        {'lat': float, 'lng': float} - 標準 JSON 結構的座標資訊
    """

    name: str = "Place Geocode Tool"
    description: str = (
        "根據國家、城市、地點名稱查詢經緯度，回傳 {'lat': float, 'lng': float}。"
    )
    args_schema: Type[BaseModel] = PlaceGeocodeToolInput

    def _run(self, country: str, city: str, place: str) -> dict | None:
        """
        地理編碼查詢的核心執行方法

        整合 Google Geocoding API 查詢流程，包含速率限制、API 認證、
        資料組裝和結果處理等完整步驟。

        執行流程:
            1. Token Bucket 速率限制檢查
            2. Google API Key 驗證和環境變數讀取
            3. 地址字串組裝 ("{place}, {city}, {country}")
            4. Google Geocoding API HTTP 請求
            5. 回應狀態驗證和結果提取
            6. 座標資料結構化輸出

        API 狀態處理:
            - "OK": 成功找到匹配結果
            - "ZERO_RESULTS": 無法找到匹配的地址
            - "OVER_QUERY_LIMIT": 超過 API 配額限制
            - "REQUEST_DENIED": API 密鑰無效或權限不足
            - "INVALID_REQUEST": 請求參數格式錯誤

        Args:
            country (str): 國家名稱，提供地理上下文 (如 '台灣')
            city (str): 城市名稱，縮小搜尋範圍 (如 '台北市')
            place (str): 具體地點名稱 (如 '故宮博物院')

        Returns:
            dict | None: 地理座標資訊或錯誤時的 None
                成功格式: {'lat': 25.1024, 'lng': 121.5483}
                失敗情況: None (並記錄具體錯誤資訊)

        錯誤處理:
            - 速率限制: 記錄警告並直接回傳 None
            - API 密鑰缺失: 記錄錯誤並終止執行
            - 網路連線問題: 記錄錯誤和例外詳情
            - API 回應異常: 記錄狀態碼和地址資訊

        日誌等級:
            - WARNING: 非致命問題 (速率限制、查無結果)
            - ERROR: 致命錯誤 (API 密鑰、網路失敗)

        效能注意:
            - 連線超時: 10 秒防止長時間等待
            - 速率控制: 自動限制請求頻率避免 API 濫用
        """
        # Token Bucket 速率限制檢查 - 防止 API 濫用
        if not _token_bucket.consume():
            logger.warning("Geocoding API 速率限制觸發 - 當前請求被拒絕，請稍後再試")
            return None
        # Google API Key 驗證 - 確保必要的認證資訊存在
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.error("GOOGLE_API_KEY 環境變數未設定 - 無法執行地理編碼查詢")
            return None
        # 地址字串組裝 - 使用階層結構提高編碼精度
        address = f"{place}, {city}, {country}"
        logger.info(f"進行地理編碼查詢: {address}")

        # Google Geocoding API 請求參數
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": address,
            "key": api_key,
            "language": "zh-TW",  # 優先使用繁體中文回應
        }
        try:
            # 發送 HTTP GET 請求至 Google Geocoding API
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()  # 檢查 HTTP 狀態碼
            data = resp.json()

            # 詳細的 API 回應日誌 (只在需要時啟用)
            # logger.debug(f"Google Geocoding API 回應: {json.dumps(data, ensure_ascii=False, indent=2)}")

            # 結果狀態驗證與座標提取
            status = data.get("status")
            if status == "OK" and data.get("results"):
                # 提取第一個 (最佳) 匹配結果的座標
                location = data["results"][0]["geometry"]["location"]
                coordinates = {"lat": location["lat"], "lng": location["lng"]}
                logger.info(f"地理編碼成功: {address} -> {coordinates}")
                return coordinates
            else:
                # 無法找到匹配結果或其他 API 錯誤
                logger.warning(
                    f"地理編碼失敗: {status} - {address}"
                    + (
                        f" ({data.get('error_message', '')})"
                        if data.get("error_message")
                        else ""
                    )
                )
                return None
        except requests.exceptions.Timeout:
            logger.error(f"地理編碼請求超時 (10秒) - {address}")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("網路連線錯誤 - 無法連接 Google Geocoding API")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP 錯誤狀態碼: {e.response.status_code} - {address}")
            return None
        except Exception as e:
            # 捕捉所有其他未預期的例外
            logger.error(f"地理編碼未知錯誤: {type(e).__name__}: {e} - {address}")
            return None


# 測試和示範程式碼
if __name__ == "__main__":
    """
    地理編碼工具的測試和示範程式

    執行需求:
        1. 設定 GOOGLE_API_KEY 環境變數
        2. 確保網路連線正常
        3. Google Cloud API 配額足夠

    範例輸出:
        {'lat': 25.1024, 'lng': 121.5483}
    """
    tool = PlaceGeocodeTool()
    result = tool._run("台灣", "台北市", "故宮博物院")
    print(f"地理編碼結果: {result}")
