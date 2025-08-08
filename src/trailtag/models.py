# src/trailtag/models.py
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl, field_validator


class VideoMetadata(BaseModel):
    """
    YouTube 影片 metadata（對應 video_metadata_extraction_task）

    屬性:
        url (HttpUrl): 影片 URL
        video_id (str): YouTube 影片 ID
        title (str): 影片標題
        description (Optional[str]): 影片描述
        publish_date (Optional[str]): 發佈日期 (YYYY-MM-DD)
        duration (Optional[int]): 持續時間（秒）
        keywords (List[str]): 關鍵字
        subtitles (Optional[str]): 字幕內容
    """

    url: HttpUrl = Field(..., description="影片 URL")
    video_id: str = Field(..., description="YouTube 影片 ID")
    title: str = Field(..., description="影片標題")
    description: Optional[str] = Field(None, description="影片描述")
    publish_date: Optional[str] = Field(None, description="發佈日期 (YYYY-MM-DD)")
    duration: Optional[int] = Field(None, description="持續時間（秒）")
    keywords: List[str] = Field(default_factory=list, description="關鍵字")
    subtitles: Optional[str] = Field(None, description="字幕內容")


# 主題摘要任務輸出模型
class SummaryItem(BaseModel):
    """
    主題摘要項目模型

    屬性:
        name (str): 項目名稱（如地點名稱、人物名稱等）
        video_timestamp (Optional[int]): 字幕中提及該項目的時間軸（秒）
        context (Optional[str]): 字幕中提及該項目的上下文內容
        related_items (Optional[List[str]]): 相關項目列表
        confidence_score (Optional[float]): 項目識別置信度 (0-1)
        extra_info (Optional[Dict[str, Any]]): 其他補充資訊（如地點類型、熱門程度等，依主題彈性擴充）
    """

    name: str = Field(..., description="項目名稱（如地點名稱、人物名稱等）")
    video_timestamp: Optional[int] = Field(
        None, description="字幕中提及該項目的時間軸（秒）"
    )
    context: Optional[str] = Field(None, description="字幕中提及該項目的上下文內容")
    related_items: Optional[List[str]] = Field(default=None, description="相關項目列表")
    confidence_score: Optional[float] = Field(None, description="項目識別置信度 (0-1)")
    extra_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="其他補充資訊（如地點類型、熱門程度等，依主題彈性擴充）",
    )


class VideoTopicSummaryOutput(BaseModel):
    """
    主題摘要任務輸出模型

    屬性:
        topic (str): 主題名稱（如地點/人物/事件/主題）
        summary_items (List[SummaryItem]): 主題摘要項目
    """

    topic: str = Field(..., description="主題名稱（如地點/人物/事件/主題）")
    summary_items: List[SummaryItem] = Field(
        default_factory=list, description="主題摘要項目"
    )


class LocationInfo(BaseModel):
    """
    地點資訊模型

    屬性:
        name (str): 地點名稱
        latitude (Optional[float]): 緯度
        longitude (Optional[float]): 經度
        address (Optional[str]): 詳細地址
        country (Optional[str]): 國家
        city (Optional[str]): 城市
        region (Optional[str]): 地區/州
        place_type (Optional[str]): 地點類型 (景點/餐廳/住宿等)
        confidence_score (Optional[float]): 識別信心分數
    """

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
    """
    時間軸條目模型

    屬性:
        timestamp (str): 時間戳記 (格式: MM:SS 或 HH:MM:SS)
        location (Optional[LocationInfo]): 對應地點資訊
        description (str): 該時間點的活動描述
        activity_type (Optional[str]): 活動類型 (觀光/用餐/交通等)
    """

    timestamp: str = Field(..., description="時間戳記 (格式: MM:SS 或 HH:MM:SS)")
    location: Optional[LocationInfo] = Field(None, description="對應地點資訊")
    description: str = Field(..., description="該時間點的活動描述")
    activity_type: Optional[str] = Field(
        None, description="活動類型 (觀光/用餐/交通等)"
    )

    @field_validator("timestamp")
    def validate_timestamp(cls, v):
        """
        驗證時間戳記格式

        參數:
            v (str): 欲驗證的時間戳記字串

        回傳:
            str: 驗證通過的時間戳記

        拋出:
            ValueError: 若格式不符 MM:SS 或 HH:MM:SS
        """
        import re

        if not re.match(r"^\d{1,2}:\d{2}(:\d{2})?$", v):
            raise ValueError("時間戳記格式必須為 MM:SS 或 HH:MM:SS")
        return v


class VideoFetchAndAnalysisOutput(BaseModel):
    """
    影片擷取與分析任務輸出模型

    屬性:
        video_metadata (VideoMetadata): 影片基本資訊
        transcript (Optional[str]): 影片文字稿
        detected_languages (List[str]): 檢測到的語言
        analysis_timestamp (datetime): 分析時間戳記
        processing_status (str): 處理狀態
        error_messages (List[str]): 錯誤訊息
    """

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
    """
    影片分析中地點資訊條目

    屬性:
        location_name (str): 片中每個地點的名稱
        coordinates (Dict[str, float]): 地點座標（經度和緯度）
        timestamp (str): 時間軸（HH:MM:SS）
        location_type (Optional[str]): 地點類型 (景點/餐廳/住宿等)
        confidence_score (Optional[float]): 識別信心分數
        context (Optional[str]): 影片中提及該地點的上下文內容
        related_locations (Optional[List[str]]): 相關鄰近地點列表
        popularity_score (Optional[float]): 地點熱門程度評分
        accessibility_info (Optional[str]): 無障礙設施資訊
        opening_hours (Optional[str]): 營業時間資訊
        contact_info (Optional[str]): 聯絡方式
    """

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
    """
    地圖視覺化地點資訊（map_visualization_task）

    屬性:
        location (str): 地點名稱
        coordinates (Dict[str, float]): 地點座標（經度和緯度）
        description (Optional[str]): 地點描述
        video_timestamp (Optional[int]): 字幕中提及該項目的時間軸（秒）
        tags (Optional[List[str]]): 地點標籤
    """

    location: str = Field(..., description="地點名稱")
    coordinates: Dict[str, float] = Field(..., description="地點座標（經度和緯度）")
    description: Optional[str] = Field(None, description="地點描述")
    video_timestamp: Optional[int] = Field(
        None, description="字幕中提及該項目的時間軸（秒）"
    )
    tags: Optional[List[str]] = Field(None, description="地點標籤")


# 地圖設定模型
class MapSettings(BaseModel):
    """
    地圖設定模型

    屬性:
        zoom_level (int): 預設縮放等級
        center_coordinates (Dict[str, float]): 地圖中心座標
        map_style (Optional[str]): 地圖樣式
        markers_style (Optional[str]): 標記樣式設定 (依特性給予不同標記，如餐廳、景點、商場等)
    """

    zoom_level: int = Field(..., description="預設縮放等級", ge=1, le=20)
    center_coordinates: Dict[str, float] = Field(..., description="地圖中心座標")
    map_style: Optional[str] = Field(None, description="地圖樣式")
    markers_style: Optional[str] = Field(
        None, description="標記樣式設定 (依特性給予不同標記，如餐廳、景點、商場等)"
    )


# 視覺化元資料模型
class Metadata(BaseModel):
    """
    視覺化元資料模型

    屬性:
        video_title (str): 影片標題
        video_url (HttpUrl): 影片URL
        author (Optional[str]): 作者資訊
    """

    video_title: str = Field(..., description="影片標題")
    video_url: HttpUrl = Field(..., description="影片URL")
    author: Optional[str] = Field(None, description="作者資訊")


class MapVisualizationData(BaseModel):
    """
    地圖視覺化資料模型

    屬性:
        center_coordinates (Dict[str, float]): 地圖中心座標
        zoom_level (int): 縮放級別
        markers (List[Dict[str, Any]]): 地圖標記資料
        polylines (List[Dict[str, Any]]): 路線線條資料
    """

    center_coordinates: Dict[str, float] = Field(..., description="地圖中心座標")
    zoom_level: int = Field(default=10, description="縮放級別", ge=1, le=20)
    markers: List[Dict[str, Any]] = Field(..., description="地圖標記資料")
    polylines: List[Dict[str, Any]] = Field(default=[], description="路線線條資料")


class VideoMapGenerationOutput(BaseModel):
    """
    影片地圖生成任務輸出模型

    屬性:
        video_id (str): 影片 ID
        url (HttpUrl): 影片 URL
        title (str): 影片標題
        description (Optional[str]): 影片描述
        publish_date (Optional[datetime]): 發布日期
        duration (str): 影片時長
        keywords (List[str]): 關鍵字
        subtitles (Optional[str]): 字幕內容
        analysis (List[AnalysisEntry]): 影片中地點分析
        timeline (List[TimelineEntry]): 時間軸資訊
        unique_locations (List[LocationInfo]): 去重後的地點列表
        suggested_routes (List[RouteInfo]): 建議路線
        travel_summary (Dict[str, Any]): 旅程摘要資訊
        generation_timestamp (datetime): 生成時間戳記
    """

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
    """
    地圖視覺化任務輸出模型（map_visualization_task）

    屬性:
        routes (List[RouteInfo]): 地點列表
        map_settings (MapSettings): 地圖設定
        metadata (Metadata): 影片元資料
    """

    routes: List[RouteInfo] = Field(default=[], description="地點列表")
    map_settings: MapSettings = Field(..., description="地圖設定")
    metadata: Metadata = Field(..., description="影片元資料")
