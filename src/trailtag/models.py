from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

# region: 影片相關資料結構


class VideoMetadata(BaseModel):
    """
    影片 metadata 結構，描述單一影片的基本資訊。
    """

    video_id: str  # 影片唯一識別碼
    title: str  # 影片標題
    description: Optional[str]  # 影片描述
    publish_date: Optional[datetime]  # 發佈日期
    duration: Optional[int]  # 影片長度（秒）
    keywords: Optional[List[str]]  # 關鍵字列表
    subtitle_lang: Optional[str]  # 字幕語言
    subtitles: Optional[str]  # 字幕內容（如有）


# endregion

# region: 主題摘要結構


class SummaryItem(BaseModel):
    """
    主題摘要項目，描述影片中某一主題的摘要資訊。
    """

    name: str  # 主題名稱
    country: Optional[str]  # 所屬國家
    city: Optional[str]  # 所屬城市
    timecode: Optional[str]  # 對應影片時間戳（hh:mm:ss,mmm）
    context: Optional[str]  # 主題相關內容
    related_items: Optional[List[str]]  # 相關主題名稱列表
    confidence_score: Optional[float] = Field(None, ge=0, le=1)  # 信心分數，介於 0~1
    extra_info: Optional[Dict[str, Any]]  # 其他額外資訊


class VideoTopicSummary(BaseModel):
    """
    影片主題摘要，包含主題名稱與對應的摘要項目。
    """

    video_id: str  # 影片唯一識別碼
    topic: str  # 主題名稱
    summary_items: List[SummaryItem]  # 該主題下的摘要項目列表


# endregion

# region: 地圖視覺化結構


class RouteItem(BaseModel):
    """
    路線項目，描述地圖上一個地點與相關資訊。
    """

    location: str  # 地點名稱
    coordinates: Optional[List[float]]  # 地點座標 [經度, 緯度]
    description: Optional[str]  # 地點描述
    timecode: Optional[str]  # 對應影片時間戳（hh:mm:ss,mmm）
    tags: Optional[List[str]]  # 標籤列表
    marker: Optional[str]  # 標記樣式設定


class MapVisualization(BaseModel):
    """
    地圖視覺化資料，包含多個路線項目。
    """

    video_id: str  # 影片唯一識別碼
    routes: List[RouteItem]  # 路線項目列表


# endregion
