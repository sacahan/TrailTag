import logging
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from ..models import VideoMetadata
import yt_dlp
from datetime import datetime
import requests
import json

# 設定 logger 以便記錄除錯與警告訊息
logger = logging.getLogger(__name__)


class YoutubeMetadataToolInput(BaseModel):
    """
    YoutubeMetadataTool 的輸入資料結構。

    Attributes:
        video_id (str): YouTube 影片的 ID。
    """

    video_id: str = Field(..., description="YouTube 影片的 ID")


class YoutubeMetadataTool(BaseTool):
    """
    取得 YouTube 影片 metadata 及字幕的工具。

    Attributes:
        name (str): 工具名稱。
        description (str): 工具用途說明。
        args_schema (Type[BaseModel]): 輸入參數的 schema。
    """

    name: str = "YouTube Metadata Fetcher"
    description: str = "根據 video_id 取得 YouTube 影片的 metadata（含字幕資訊），回傳 VideoMetadata Pydantic 物件。"
    args_schema: Type[BaseModel] = YoutubeMetadataToolInput

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

        # 先查找 subtitles 若不存在則使用 automatic_captions
        subs = info.get("subtitles") or info.get("automatic_captions") or None
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

        # 若無任何可用字幕，回傳 None
        return None, None

    def _run(self, video_id: str) -> VideoMetadata | None:
        """
        取得 YouTube 影片 metadata，並自動擷取字幕（優先 zh-TW, zh-CN, en）。

        包含步驟：
        1. 以 yt_dlp 擷取影片資訊。
        2. 依語言優先順序取得字幕 URL 並下載字幕內容。
        3. 處理日期格式與關鍵字欄位。
        4. 組成 VideoMetadata 物件。

        Args:
            video_id (str): YouTube 影片的 ID。

        Returns:
            VideoMetadata | None: 影片 metadata，若失敗則回傳 None。
        """

        url = f"https://www.youtube.com/watch?v={video_id}"  # 組合 YouTube 影片網址
        ydl_opts = {"skip_download": True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            # 設定字幕語言優先順序
            preferred_langs = ["zh-TW", "zh-Hant", "zh-CN", "zh-Hans", "en"]
            subtitle_url, subtitle_lang = self._extract_subtitle_url(
                info, preferred_langs
            )

            subtitles_text = None
            if subtitle_url:
                try:
                    # 下載字幕內容，失敗則記錄警告
                    print(f"Downloading subtitles from {subtitle_url}...")
                    resp = requests.get(subtitle_url, timeout=10)
                    resp.raise_for_status()
                    subtitles_text = resp.text
                except Exception as e:
                    print(f"字幕下載或解析失敗: {e}")
            else:
                print(f"No subtitles or automatic captions found for video {video_id}")

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
    video_id = "xV-oTx8RHZw"  # 替換為實際的 YouTube 影片 ID
    metadata = tool._run(video_id)
    if metadata:
        # Pydantic v2 不再支援 json() 的 ensure_ascii/indent 參數，需用 json.dumps
        print(
            json.dumps(metadata.model_dump(), ensure_ascii=False, indent=2, default=str)
        )
    else:
        print(None)
