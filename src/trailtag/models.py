# src/trailtag/models.py
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl, field_validator


class VideoMetadata(BaseModel):
    """YouTube 影片完整 metadata 模型 (對應 yt_dlp extract_info 欄位)"""

    video_id: str = Field(..., description="YouTube 影片 ID")
    title: str = Field(..., description="影片標題")
    description: Optional[str] = Field(None, description="影片描述")
    channel: Optional[str] = Field(None, description="頻道名稱")
    channel_id: Optional[str] = Field(None, description="頻道 ID")
    channel_url: Optional[HttpUrl] = Field(None, description="頻道網址")
    uploader: Optional[str] = Field(None, description="上傳者名稱")
    uploader_id: Optional[str] = Field(None, description="上傳者 ID")
    uploader_url: Optional[HttpUrl] = Field(None, description="上傳者網址")
    duration: Optional[int] = Field(None, description="影片時長（秒）")
    view_count: Optional[int] = Field(None, description="觀看次數")
    like_count: Optional[int] = Field(None, description="按讚數")
    dislike_count: Optional[int] = Field(None, description="倒讚數")
    average_rating: Optional[float] = Field(None, description="平均評分")
    age_limit: Optional[int] = Field(None, description="年齡限制")
    webpage_url: Optional[HttpUrl] = Field(None, description="影片網址")
    original_url: Optional[HttpUrl] = Field(None, description="原始網址（如有）")
    upload_date: Optional[str] = Field(None, description="上傳日期 (YYYYMMDD)")
    release_date: Optional[str] = Field(None, description="發佈日期 (YYYYMMDD)")
    timestamp: Optional[int] = Field(None, description="上傳時間戳 (秒)")
    tags: List[str] = Field(default_factory=list, description="影片標籤")
    categories: List[str] = Field(default_factory=list, description="影片分類")
    automatic_captions: Optional[Dict[str, Any]] = Field(
        None, description="自動產生字幕資訊"
    )
    comment_count: Optional[int] = Field(None, description="留言數")
    license: Optional[str] = Field(None, description="授權資訊")
    availability: Optional[str] = Field(None, description="可用性")
    subtitles_format: Optional[str] = Field(None, description="字幕格式")
    subtitles_text: Optional[str] = Field(None, description="影片字幕內容")


class LocationInfo(BaseModel):
    """地點資訊模型"""

    name: str = Field(..., description="地點名稱")
    latitude: Optional[float] = Field(None, description="緯度", ge=-90, le=90)
    longitude: Optional[float] = Field(None, description="經度", ge=-180, le=180)
    address: Optional[str] = Field(None, description="詳細地址")
    country: Optional[str] = Field(None, description="國家")
    city: Optional[str] = Field(None, description="城市")
    region: Optional[str] = Field(None, description="地區/州")
    place_type: Optional[str] = Field(None, description="地點類型 (景點/餐廳/住宿等)")
    confidence_score: Optional[float] = Field(
        None, description="識別信心分數", ge=0, le=1
    )


class TimelineEntry(BaseModel):
    """時間軸條目模型"""

    timestamp: str = Field(..., description="時間戳記 (格式: MM:SS 或 HH:MM:SS)")
    location: Optional[LocationInfo] = Field(None, description="對應地點資訊")
    description: str = Field(..., description="該時間點的活動描述")
    activity_type: Optional[str] = Field(
        None, description="活動類型 (觀光/用餐/交通等)"
    )

    @field_validator("timestamp")
    def validate_timestamp(cls, v):
        """驗證時間戳記格式"""
        import re

        if not re.match(r"^\d{1,2}:\d{2}(:\d{2})?$", v):
            raise ValueError("時間戳記格式必須為 MM:SS 或 HH:MM:SS")
        return v


class VideoFetchAndAnalysisOutput(BaseModel):
    """影片擷取與分析任務輸出模型"""

    video_metadata: VideoMetadata = Field(..., description="影片基本資訊")
    transcript: Optional[str] = Field(None, description="影片文字稿")
    detected_languages: List[str] = Field(default=[], description="檢測到的語言")
    analysis_timestamp: datetime = Field(
        default_factory=datetime.now, description="分析時間戳記"
    )
    processing_status: str = Field(default="completed", description="處理狀態")
    error_messages: List[str] = Field(default=[], description="錯誤訊息")


# 新增分析條目模型
class AnalysisEntry(BaseModel):
    """影片分析中地點資訊條目"""

    location_name: str = Field(..., description="片中每個地點的名稱")
    coordinates: Dict[str, float] = Field(..., description="地點座標（經度和緯度）")
    timestamp: str = Field(..., description="時間軸（HH:MM:SS）")
    location_type: Optional[str] = Field(
        None, description="地點類型 (景點/餐廳/住宿等)"
    )
    confidence_score: Optional[float] = Field(
        None, description="識別信心分數", ge=0, le=1
    )
    context: Optional[str] = Field(None, description="影片中提及該地點的上下文內容")
    related_locations: Optional[List[str]] = Field(None, description="相關鄰近地點列表")
    popularity_score: Optional[float] = Field(None, description="地點熱門程度評分")
    accessibility_info: Optional[str] = Field(None, description="無障礙設施資訊")
    opening_hours: Optional[str] = Field(None, description="營業時間資訊")
    contact_info: Optional[str] = Field(None, description="聯絡方式")


# 新增路線資訊模型（符合 map_visualization_task）
class RouteInfo(BaseModel):
    """路線資訊模型（地圖視覺化）"""

    location: str = Field(..., description="地點名稱")
    coordinates: Dict[str, float] = Field(..., description="地點座標（經度和緯度）")
    timestamp: str = Field(..., description="時間軸（HH:MM:SS）")
    description: Optional[str] = Field(None, description="地點描述")
    thumbnail: Optional[HttpUrl] = Field(None, description="地點縮圖URL")
    video_timestamp: Optional[int] = Field(None, description="影片時間戳記（秒）")
    tags: Optional[List[str]] = Field(None, description="地點標籤")


# 地圖設定模型
class MapSettings(BaseModel):
    zoom_level: int = Field(..., description="預設縮放等級", ge=1, le=20)
    center_coordinates: Dict[str, float] = Field(..., description="地圖中心座標")
    map_style: Optional[str] = Field(None, description="地圖樣式")
    markers_style: Optional[str] = Field(None, description="標記樣式設定")


# 視覺化元資料模型
class Metadata(BaseModel):
    video_title: str = Field(..., description="影片標題")
    video_url: HttpUrl = Field(..., description="影片URL")
    author: Optional[str] = Field(None, description="作者資訊")


class MapVisualizationData(BaseModel):
    """地圖視覺化資料模型"""

    center_coordinates: Dict[str, float] = Field(..., description="地圖中心座標")
    zoom_level: int = Field(default=10, description="縮放級別", ge=1, le=20)
    markers: List[Dict[str, Any]] = Field(..., description="地圖標記資料")
    polylines: List[Dict[str, Any]] = Field(default=[], description="路線線條資料")


class VideoMapGenerationOutput(BaseModel):
    """影片地圖生成任務輸出模型"""

    video_id: str = Field(..., description="影片 ID")
    url: HttpUrl = Field(..., description="影片 URL")
    title: str = Field(..., description="影片標題")
    description: Optional[str] = Field(None, description="影片描述")
    publish_date: Optional[datetime] = Field(None, description="發布日期")
    duration: str = Field(..., description="影片時長")
    keywords: List[str] = Field(default=[], description="關鍵字")
    subtitles: Optional[str] = Field(None, description="字幕內容")
    analysis: List[AnalysisEntry] = Field(default=[], description="影片中地點分析")
    timeline: List[TimelineEntry] = Field(..., description="時間軸資訊")
    unique_locations: List[LocationInfo] = Field(..., description="去重後的地點列表")
    suggested_routes: List[RouteInfo] = Field(default=[], description="建議路線")
    travel_summary: Dict[str, Any] = Field(default={}, description="旅程摘要資訊")
    generation_timestamp: datetime = Field(
        default_factory=datetime.now, description="生成時間戳記"
    )


class MapVisualizationOutput(BaseModel):
    """地圖視覺化任務輸出模型"""

    video_id: str = Field(..., description="影片 ID")
    routes: List[RouteInfo] = Field(default=[], description="地點列表")
    map_settings: MapSettings = Field(..., description="地圖設定")
    metadata: Metadata = Field(..., description="影片元資料")
    map_data: MapVisualizationData = Field(..., description="地圖視覺化資料")
    route_file_path: Optional[str] = Field(None, description="路線檔案路徑")
    map_html_content: Optional[str] = Field(None, description="地圖 HTML 內容")
    visualization_config: Dict[str, Any] = Field(default={}, description="視覺化配置")
    creation_timestamp: datetime = Field(
        default_factory=datetime.now, description="創建時間戳記"
    )
