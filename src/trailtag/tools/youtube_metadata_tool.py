import logging
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from ..models import VideoMetadata
import yt_dlp

# 設定 logger 以便記錄除錯與警告訊息
logger = logging.getLogger(__name__)


class YoutubeMetadataToolInput(BaseModel):
    """YoutubeMetadataTool 的輸入資料結構，定義 video_id 欄位。"""

    video_id: str = Field(..., description="YouTube 影片的 ID")


class YoutubeMetadataTool(BaseTool):
    # 工具名稱
    name: str = "YouTube Metadata Fetcher"
    # 工具描述，說明用途
    description: str = "根據 video_id 取得 YouTube 影片的 metadata（含字幕資訊），回傳 VideoMetadata Pydantic 物件。"
    # 指定輸入參數的 schema
    args_schema: Type[BaseModel] = YoutubeMetadataToolInput

    def _extract_subtitle_url(
        self, info: dict, preferred_langs: list[str]
    ) -> tuple[str | None, str | None]:
        """
        根據優先語言，從 info 取得字幕的 URL 與格式。
        先找手動字幕，若無則找自動字幕。
        回傳 (subtitle_url, format)，若無字幕則皆為 None。
        """
        # 依序搜尋 subtitles 與 automatic_captions
        for key in ("subtitles", "automatic_captions"):
            subs = info.get(key) or {}
            # 依照優先語言順序尋找可用字幕
            for lang in preferred_langs:
                if lang in subs and subs[lang]:
                    lang_subs = subs[lang]
                    # 優先選擇 srt 格式
                    for s in lang_subs:
                        if s.get("ext") == "srt":
                            return s.get("url"), "srt"
                    # 若無 srt，取第一個可用字幕
                    if lang_subs:
                        return lang_subs[0].get("url"), lang_subs[0].get("ext")
        # 若無任何可用字幕，回傳 None
        return None, None

    def _run(self, video_id: str) -> VideoMetadata | None:
        """
        取得 YouTube 影片 metadata，並自動擷取字幕（優先 zh-TW, zh-CN, en）。
        回傳 VideoMetadata，若失敗則回傳 None。
        """
        import requests

        url = f"https://www.youtube.com/watch?v={video_id}"  # 組合 YouTube 影片網址
        ydl_opts = {"skip_download": True}  # 設定 yt_dlp 選項，不下載影片僅抓取資訊
        try:
            # 使用 yt_dlp 擷取影片資訊
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            # 將擷取到的資訊填入 VideoMetadata Pydantic 物件
            metadata = VideoMetadata(
                video_id=info.get("id"),
                title=info.get("title"),
                description=info.get("description"),
                channel=info.get("channel"),
                channel_id=info.get("channel_id"),
                channel_url=info.get("channel_url"),
                uploader=info.get("uploader"),
                uploader_id=info.get("uploader_id"),
                uploader_url=info.get("uploader_url"),
                duration=info.get("duration"),
                view_count=info.get("view_count"),
                like_count=info.get("like_count"),
                dislike_count=info.get("dislike_count"),
                average_rating=info.get("average_rating"),
                age_limit=info.get("age_limit"),
                webpage_url=info.get("webpage_url"),
                original_url=info.get("original_url"),
                upload_date=info.get("upload_date"),
                release_date=info.get("release_date"),
                timestamp=info.get("timestamp"),
                tags=info.get("tags") or [],
                categories=info.get("categories") or [],
                automatic_captions=info.get("automatic_captions"),
                comment_count=info.get("comment_count"),
                license=info.get("license"),
                availability=info.get("availability"),
            )

            # 設定字幕語言優先順序
            preferred_langs = ["zh-TW", "zh-CN", "en"]
            # 取得字幕下載連結與格式
            subtitle_url, subtitle_format = self._extract_subtitle_url(
                info, preferred_langs
            )

            subtitles_text = None
            if subtitle_url:
                try:
                    # 下載字幕內容
                    resp = requests.get(subtitle_url, timeout=10)
                    resp.raise_for_status()
                    subtitles_text = resp.text.strip()
                except Exception as e:
                    # 若字幕下載或解析失敗，記錄警告
                    logger.warning(f"字幕下載或解析失敗: {e}")

            # 將字幕格式與內容存入 metadata
            metadata.subtitles_format = subtitle_format
            metadata.subtitles_text = subtitles_text

            # 若無字幕，記錄警告
            if not subtitle_url:
                logger.warning(
                    f"No subtitles or automatic captions found for video {video_id}"
                )

            return metadata

        except Exception as e:
            # 若 yt_dlp 擷取失敗，記錄錯誤並回傳 None
            logger.error(f"yt_dlp error for video {video_id}: {str(e)}")
            return None


# 使用範例：直接執行此檔案時會執行以下程式
if __name__ == "__main__":
    tool = YoutubeMetadataTool()
    # video_id = "SlRSbihlytQ"  # 替換為實際的 YouTube 影片 ID
    video_id = "1LPTp7CMQCs"
    metadata = tool._run(video_id)
    print(metadata)
