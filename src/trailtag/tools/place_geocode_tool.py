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
    Token Bucket 實作，限制速率與突發流量。
    rate: 每秒補充 token 數量
    burst: 最大 token 數量
    """

    def __init__(self, rate: float, burst: int):
        """
        初始化 TokenBucket。

        Args:
            rate (float): 每秒補充 token 的數量。
            burst (int): token 的最大容量（突發上限）。
        """
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.lock = threading.Lock()
        self.timestamp = time.monotonic()

    def consume(self, tokens: int = 1) -> bool:
        """
        嘗試消耗指定數量的 token，若足夠則扣除並回傳 True，否則回傳 False。

        Args:
            tokens (int): 需要消耗的 token 數量，預設為 1。

        Returns:
            bool: 是否成功消耗 token。
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


# 將 TokenBucket 實例移至模組層級，避免被 pickle
_token_bucket = TokenBucket(rate=5, burst=10)


class PlaceGeocodeToolInput(BaseModel):
    """
    景點查詢工具輸入資料結構。

    Attributes:
        country (str): 國家名稱。
        city (str): 城市名稱。
        place (str): 地點名稱。
    """

    country: str = Field(..., description="國家名稱")
    city: str = Field(..., description="城市名稱")
    place: str = Field(..., description="地點名稱")


class PlaceGeocodeTool(BaseTool):
    """
    根據國家、城市、地點名稱查詢經緯度，回傳 {'lat': float, 'lng': float}。
    """

    name: str = "Place Geocode Tool"
    description: str = (
        "根據國家、城市、地點名稱查詢經緯度，回傳 {'lat': float, 'lng': float}。"
    )
    args_schema: Type[BaseModel] = PlaceGeocodeToolInput

    def _run(self, country: str, city: str, place: str) -> dict | None:
        """
        查詢地點經緯度。

        Args:
            country (str): 國家名稱
            city (str): 城市名稱
            place (str): 地點名稱

        Returns:
            dict | None: {'lat': float, 'lng': float} 或 None
        """
        # 速率限制：每秒最多 5 次、突發 10 次
        if not _token_bucket.consume():
            logger.warning("Geocoding API 已達速率上限，請稍後再試")
            return None
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.error("GOOGLE_API_KEY 環境變數未設定")
            return None
        # 組合完整地址字串
        address = f"{place}, {city}, {country}"
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {"address": address, "key": api_key}
        try:
            # 發送 GET 請求至 Google Geocoding API
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            # print(f">>> Geocoding API 回應: {json.dumps(data, ensure_ascii=False, indent=2)}")

            # 檢查回應狀態與結果
            if data.get("status") == "OK" and data["results"]:
                loc = data["results"][0]["geometry"]["location"]
                return {"lat": loc["lat"], "lng": loc["lng"]}
            else:
                logger.warning(f"查無經緯度: {data.get('status')}, {address}")
                return None
        except Exception as e:
            # 捕捉並記錄所有例外狀況
            logger.error(f"Geocoding API 錯誤: {e}")
            return None


# 增加 main 呼叫
if __name__ == "__main__":
    tool = PlaceGeocodeTool()
    result = tool._run("台灣", "台北市", "故宮博物院")
    print(result)
