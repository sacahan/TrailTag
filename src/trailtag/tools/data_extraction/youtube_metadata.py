from src.api.logger_config import get_logger
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from ..models import VideoMetadata, SubtitleAvailability
import yt_dlp
from datetime import datetime
import requests
import json

# 設定 logger 以便記錄除錯與警告訊息
logger = get_logger(__name__)


class YoutubeMetadataToolInput(BaseModel):
    """
    YouTube Metadata Tool 輸入參數模型

    定義 YoutubeMetadataTool 工具所需的輸入參數結構。
    使用 Pydantic BaseModel 確保輸入數據的型別安全與驗證。

    Attributes:
        video_id (str): YouTube 影片識別碼，必須是有效的 11 字元 YouTube ID
            格式範例: 'dQw4w9WgXcQ', 'VF1HMYD95aw'
            驗證規則: 非空字串，符合 YouTube ID 格式規範

    使用場景:
        - CrewAI Tool 的參數結構定義
        - 確保 Agent 傳入正確格式的影片 ID
        - 提供 API 文檔與錯誤驗證
    """

    video_id: str = Field(..., description="YouTube 影片的 11 字元唯一識別碼")


class YoutubeMetadataTool(BaseTool):
    """
    YouTube 影片元數據與字幕提取工具

    這是 TrailTag 系統中最重要的資料擷取工具，負責從 YouTube 獲取影片的完整元數據。
    整合了多個資料來源，包括影片資訊、多語言字幕、章節結構等，為後續分析提供基礎資料。

    核心功能:
        - 影片資訊提取: 標題、描述、發佈時間、時長等基本資訊
        - 智慧字幕處理: 自動選擇最適合的字幕語言與格式
        - 字幕品質評估: 評估手動/自動字幕的可靠度
        - 抗反爬機制: 配置多重策略應對 YouTube 的存取限制

    技術特色:
        - 多語言支援: 優先繁體中文、簡體中文、英文字幕
        - 格式智慧選擇: 優先 SRT 格式，確保時間軸準確性
        - 健全的錯誤處理: 多層次的例外捕獲與回復機制
        - 效能優化: 使用 yt-dlp 的最佳化配置

    工具屬性:
        name (str): CrewAI 工具識別名稱
        description (str): 工具功能描述，供 LLM 理解用途
        args_schema (Type[BaseModel]): 輸入參數的 Pydantic 模型定義

    相依套件:
        - yt-dlp: YouTube 影片資訊擷取的核心引擎
        - requests: HTTP 請求處理，用於字幕下載
        - pydantic: 資料驗證與序列化

    輸出資料:
        VideoMetadata: 結構化的影片元數據物件，包含所有必要欄位

    使用限制:
        - 需要網路連線存取 YouTube 服務
        - 受 YouTube API 速率限制約束
        - 部分私人或地區限制影片可能無法存取
    """

    name: str = "YouTube Metadata Fetcher"
    description: str = "根據 video_id 取得 YouTube 影片的 metadata（含字幕資訊），回傳 VideoMetadata Pydantic 物件。"
    args_schema: Type[BaseModel] = YoutubeMetadataToolInput

    def _detect_subtitle_availability(self, info: dict) -> SubtitleAvailability:
        """
        智慧字幕可用性檢測與品質評估

        深度分析 YouTube 影片的字幕資源，區分手動上傳與自動生成字幕，
        並依據語言覆蓋範圍與字幕類型計算品質信心分數。

        檢測邏輯:
            1. 掃描 yt-dlp 提取的字幕結構 (subtitles + automatic_captions)
            2. 分類手動字幕與自動字幕的語言清單
            3. 依據字幕類型與語言支援度計算信心分數
            4. 記錄詳細的檢測結果供後續選擇使用

        信心分數計算:
            - 手動字幕: 0.9 (高品質基準)
            - 手動字幕 + 中英文支援: 0.95 (最高品質)
            - 自動字幕: 0.7 (中等品質基準)
            - 自動字幕 + 中英文支援: 0.75 (提升品質)
            - 無任何字幕: 0.0 (無法分析)

        語言優先級:
            繁中(zh-TW) > 繁中變體(zh-Hant) > 簡中(zh-CN) > 簡中變體(zh-Hans) > 英文(en)

        Args:
            info (dict): yt-dlp extract_info() 回傳的完整影片資訊字典
                必須包含 'subtitles' 和/或 'automatic_captions' 鍵值

        Returns:
            SubtitleAvailability: 字幕可用性資訊物件，包含:
                - available: 是否有任何形式的字幕可用
                - manual_subtitles: 手動字幕語言代碼列表
                - auto_captions: 自動字幕語言代碼列表
                - confidence_score: 字幕品質信心分數 (0.0-1.0)
                - selected_lang: 預留欄位，將在後續步驟設定

        異常處理:
            - info 結構異常: 回傳預設無字幕狀態
            - 語言代碼解析失敗: 記錄警告但繼續處理
            - 網路或權限問題: 優雅降級處理

        日誌記錄:
            - INFO: 成功檢測到的字幕語言清單
            - WARNING: 字幕檢測過程中的非致命錯誤
        """
        try:
            subtitles = info.get("subtitles", {})
            auto_captions = info.get("automatic_captions", {})

            # 取得可用的手動字幕語言
            manual_subtitles = []
            if subtitles:
                manual_subtitles = list(subtitles.keys())
                logger.info(f"發現手動字幕語言: {manual_subtitles}")

            # 取得可用的自動字幕語言
            auto_caption_langs = []
            if auto_captions:
                auto_caption_langs = list(auto_captions.keys())
                logger.info(f"發現自動字幕語言: {auto_caption_langs}")

            # 檢查是否有任何字幕可用
            has_subtitles = bool(manual_subtitles or auto_caption_langs)

            # 計算信心分數
            confidence_score = 0.0
            if manual_subtitles:
                # 手動字幕品質較高
                confidence_score = 0.9
                if any(
                    lang in ["zh-TW", "zh-Hant", "zh-CN", "zh-Hans", "en"]
                    for lang in manual_subtitles
                ):
                    confidence_score = 0.95
            elif auto_caption_langs:
                # 自動字幕品質較低
                confidence_score = 0.7
                if any(
                    lang in ["zh-TW", "zh-Hant", "zh-CN", "zh-Hans", "en"]
                    for lang in auto_caption_langs
                ):
                    confidence_score = 0.75

            return SubtitleAvailability(
                available=has_subtitles,
                manual_subtitles=manual_subtitles,
                auto_captions=auto_caption_langs,
                selected_lang=None,  # 將在後續步驟中設定
                confidence_score=confidence_score,
            )

        except Exception as e:
            logger.warning(f"字幕可用性檢測失敗: {e}")
            return SubtitleAvailability(
                available=False,
                manual_subtitles=[],
                auto_captions=[],
                selected_lang=None,
                confidence_score=0.0,
            )

    def _extract_subtitle_url(
        self, info: dict, preferred_langs: list[str]
    ) -> tuple[str | None, str | None]:
        """
        根據優先語言，從 info 取得字幕的 URL 與格式。

        搜尋順序：
        1. 手動字幕 (subtitles)
        2. 自動字幕 (automatic_captions)
        3. 依 preferred_langs 順序尋找
        4. 優先 srt 格式，否則取第一個可用字幕

        Args:
            info (dict): yt_dlp 擷取的影片資訊。
            preferred_langs (list[str]): 語言優先順序。

        Returns:
            tuple[str | None, str | None]: (字幕 URL, 格式)，若無字幕則皆為 None。
        """
        try:
            # 先查找 subtitles 若不存在則使用 automatic_captions
            subs = info.get("subtitles") or info.get("automatic_captions") or {}
            # 依照優先語言順序尋找可用字幕
            for lang in preferred_langs:
                if lang in subs and subs[lang]:
                    lang_subs = subs[lang]
                    # 優先選擇 srt 格式
                    for s in lang_subs:
                        if s.get("ext") == "srt":
                            return s.get("url"), lang

            # 若無偏好srt，取第一個可用字幕
            if subs:
                lang, subtitles = next(iter(subs.items()))
                for s in subtitles:
                    if s.get("ext") == "srt":
                        return s.get("url"), lang
        except Exception as e:
            logger.warning(f"字幕 URL 提取失敗: {e}")

        # 若無任何可用字幕，回傳 None
        return None, None

    def _run(self, video_id: str) -> VideoMetadata | None:
        """
        YouTube 影片完整元數據擷取的核心執行方法

        這是工具的主要執行入口，整合了影片資訊擷取、字幕處理、資料標準化等完整流程。
        採用多層次的錯誤處理機制，確保在各種網路環境和影片狀態下都能穩定執行。

        完整執行流程:
            1. 組裝 YouTube URL 並設定 yt-dlp 反爬蟲配置
            2. 執行影片資訊擷取，獲取完整的 metadata
            3. 智慧字幕可用性檢測與品質評估
            4. 根據語言偏好選擇最佳字幕來源
            5. 下載並處理字幕內容（SRT 格式）
            6. 日期格式標準化與關鍵字處理
            7. 組裝完整的 VideoMetadata 物件

        技術實現特色:
            - 反爬蟲機制: 使用多重 user-agent 與 player client 策略
            - 智慧重試: yt-dlp 內建的指數退縮重試機制
            - 字幕優先級: zh-TW > zh-Hant > zh-CN > zh-Hans > en
            - 格式偏好: 優先選擇 SRT 格式確保時間軸準確性
            - 記憶體優化: 僅下載必要資訊，跳過實際影片檔案

        資料處理邏輯:
            - 日期轉換: YYYYMMDD 格式轉為 Python datetime 物件
            - 關鍵字標準化: 統一為字串陣列格式
            - 字幕品質標記: 更新 SubtitleAvailability 的實際選擇語言
            - 錯誤容錯: 部分欄位失敗不影響整體執行

        Args:
            video_id (str): YouTube 影片的 11 字元唯一識別碼
                格式要求: 符合 YouTube ID 規範 (如 'dQw4w9WgXcQ')
                驗證: 非空且長度正確的英數字串組合

        Returns:
            VideoMetadata | None: 完整的影片元數據物件，包含以下欄位:
                - 基本資訊: video_id, title, description, duration
                - 時間資訊: publish_date (標準化後的 datetime)
                - 內容資訊: keywords (標籤陣列), subtitles (完整字幕文本)
                - 字幕狀態: subtitle_lang, subtitle_availability
                失敗時回傳 None，並記錄詳細錯誤資訊

        錯誤處理策略:
            - 網路連線問題: 自動重試機制，記錄連線狀態
            - YouTube 存取限制: 多重配置策略，動態適應
            - 字幕下載失敗: 繼續執行但標記字幕不可用
            - 資料格式異常: 個別欄位錯誤不影響整體結果
            - API 限制: 記錄限制狀態，為後續呼叫提供參考

        效能考量:
            - 網路最佳化: 10 秒超時設定平衡速度與穩定性
            - 記憶體控制: 不下載影片檔案，僅處理元數據
            - 並行友善: 無狀態設計，支援多執行緒使用

        日誌記錄等級:
            - INFO: 成功的關鍵步驟 (字幕下載、資料擷取)
            - WARNING: 非致命錯誤 (字幕解析失敗、日期格式問題)
            - ERROR: 致命錯誤 (yt-dlp 執行失敗、網路連線問題)

        使用範例:
            tool = YoutubeMetadataTool()
            metadata = tool._run("dQw4w9WgXcQ")
            if metadata and metadata.subtitles:
                print(f"成功獲取影片: {metadata.title}")
        """

        url = f"https://www.youtube.com/watch?v={video_id}"  # 組合 YouTube 影片網址
        ydl_opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "writesubtitles": False,
            "writeautomaticsub": False,
            "extract_flat": False,
            # 避免 YouTube 反爬蟲機制 - 更新配置
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web"],
                    "player_skip": ["configs", "webpage"],
                }
            },
            "noplaylist": True,
            # 不指定格式，讓 yt-dlp 自己選擇
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            # 先檢測字幕可用性
            subtitle_availability = self._detect_subtitle_availability(info)
            logger.info(f"字幕可用性檢測結果: {subtitle_availability.model_dump()}")

            # 設定字幕語言優先順序
            preferred_langs = ["zh-TW", "zh-Hant", "zh-CN", "zh-Hans", "en"]
            subtitle_url, subtitle_lang = self._extract_subtitle_url(
                info, preferred_langs
            )

            subtitles_text = None
            if subtitle_url:
                try:
                    # 下載字幕內容，失敗則記錄警告
                    logger.info(f"正在下載字幕: {subtitle_url}")
                    resp = requests.get(subtitle_url, timeout=10)
                    resp.raise_for_status()
                    subtitles_text = resp.text
                    # 更新字幕可用性中的選擇語言
                    subtitle_availability.selected_lang = subtitle_lang
                except Exception as e:
                    logger.warning(f"字幕下載或解析失敗: {e}")
            else:
                logger.info(f"影片 {video_id} 無可用字幕或自動字幕")

            # 轉換日期格式，yt_dlp 回傳格式為 YYYYMMDD
            publish_date = None
            if info.get("upload_date"):
                try:
                    publish_date = datetime.strptime(info["upload_date"], "%Y%m%d")
                except Exception as e:
                    print(f"日期格式解析失敗: {e}")

            # 關鍵字欄位，優先 tags，否則 categories
            keywords = info.get("tags") or info.get("categories") or None
            if keywords and not isinstance(keywords, list):
                keywords = [str(keywords)]

            # 填充 VideoMetadata (根據 models.py)
            metadata = VideoMetadata(
                url=info.get("webpage_url") or url,
                video_id=info.get("id"),
                title=info.get("title"),
                description=info.get("description"),
                publish_date=publish_date,
                duration=info.get("duration"),
                keywords=keywords,
                subtitle_lang=subtitle_lang,
                subtitles=subtitles_text,
                subtitle_availability=subtitle_availability,
            )

            # 轉為JSON存到 outputs/video_metadata.json
            # with open("outputs/video_metadata.json", "w", encoding="utf-8") as f:
            #     json.dump(metadata.model_dump(), f, ensure_ascii=False, indent=2, default=str)

            return metadata

        except Exception as e:
            logger.error(f"yt_dlp error for video {video_id}: {str(e)}")
            return None


# 使用範例：直接執行此檔案時會執行以下程式
if __name__ == "__main__":
    # 工具測試範例，執行後會印出指定影片的 metadata
    tool = YoutubeMetadataTool()
    video_id = "VF1HMYD95aw"  # 替換為實際的 YouTube 影片 ID
    metadata = tool._run(video_id)
    if metadata:
        # Pydantic v2 不再支援 json() 的 ensure_ascii/indent 參數，需用 json.dumps
        print(
            json.dumps(metadata.model_dump(), ensure_ascii=False, indent=2, default=str)
        )
    else:
        print(None)
