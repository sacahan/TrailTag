from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

# region: 影片相關資料結構


class SubtitleAvailability(BaseModel):
    """
    字幕可用性資訊模型

    此類別描述 YouTube 影片的字幕支援狀態，包含手動字幕與自動字幕的詳細資訊。
    主要用於判斷影片是否具備足夠的字幕資料進行內容分析。

    Attributes:
        available (bool): 是否存在任何形式的可用字幕
        manual_subtitles (List[str]): 手動上傳字幕的語言代碼列表 (如 ['en', 'zh-TW'])
        auto_captions (List[str]): 自動生成字幕的語言代碼列表
        selected_lang (Optional[str]): 系統實際選擇使用的字幕語言代碼
        confidence_score (float): 字幕品質評估分數 (0.0-1.0，越高代表品質越好)

    使用範例:
        subtitle_info = SubtitleAvailability(
            available=True,
            manual_subtitles=['en'],
            auto_captions=['zh-TW'],
            selected_lang='en',
            confidence_score=0.85
        )
    """

    available: bool  # 是否有可用字幕
    manual_subtitles: List[str] = Field(default_factory=list)  # 手動字幕語言列表
    auto_captions: List[str] = Field(default_factory=list)  # 自動字幕語言列表
    selected_lang: Optional[str] = None  # 實際選擇的字幕語言
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)  # 字幕品質信心分數


class VideoMetadata(BaseModel):
    """
    YouTube 影片元數據模型

    包含從 YouTube API 和影片頁面提取的所有基本資訊，是整個分析流程的基礎資料結構。
    此模型整合了影片基本資訊、字幕內容和可用性狀態。

    Attributes:
        video_id (str): YouTube 影片唯一識別碼 (11 字元，如 'dQw4w9WgXcQ')
        title (str): 影片標題，用於上下文理解和摘要生成
        description (Optional[str]): 影片描述文本，包含頻道提供的詳細資訊
        publish_date (Optional[datetime]): 影片發佈時間，用於時間上下文分析
        duration (Optional[int]): 影片總長度（以秒為單位）
        keywords (Optional[List[str]]): 影片標籤關鍵字列表，協助主題分類
        subtitle_lang (Optional[str]): 已廢棄欄位，保留向下相容性
        subtitles (Optional[str]): 完整字幕文本內容，是地點擷取的主要資料來源
        subtitle_availability (Optional[SubtitleAvailability]): 字幕詳細可用性資訊

    注意事項:
        - video_id 必須為有效的 YouTube 影片 ID 格式
        - subtitles 欄位包含完整的時間軸與內容對應
        - subtitle_availability 提供比 subtitle_lang 更詳細的字幕狀態資訊
    """

    video_id: str  # 影片唯一識別碼
    title: str  # 影片標題
    description: Optional[str]  # 影片描述
    publish_date: Optional[datetime]  # 發佈日期
    duration: Optional[int]  # 影片長度（秒）
    keywords: Optional[List[str]]  # 關鍵字列表
    subtitle_lang: Optional[str]  # 字幕語言（向下相容）
    subtitles: Optional[str]  # 字幕內容（如有）
    subtitle_availability: Optional[SubtitleAvailability] = None  # 字幕可用性詳細資訊


# endregion

# region: 主題摘要結構


class SummaryItem(BaseModel):
    """
    主題摘要項目模型

    表示從影片內容中擷取的單一主題要點，通常對應到影片中提及的地點、事件或重要資訊。
    此類別是內容分析 Agent 的主要輸出格式，包含地理資訊和時間定位。

    Attributes:
        name (str): 主題或地點的名稱 (如 '東京晴空塔', '淺草寺')
        country (Optional[str]): 地點所屬國家名稱，用於地理分類
        city (Optional[str]): 地點所屬城市名稱，提供更精確的地理定位
        timecode (Optional[str]): 對應的影片時間戳記 (格式: 'hh:mm:ss,mmm')
        context (Optional[str]): 該主題在影片中的相關描述或上下文內容
        related_items (Optional[List[str]]): 相關聯的其他主題名稱列表
        confidence_score (Optional[float]): AI 對此摘要項目的信心分數 (0.0-1.0)
        extra_info (Optional[Dict[str, Any]]): 額外的結構化資訊 (如評分、標籤等)

    使用場景:
        - 從字幕內容中識別旅行地點
        - 提取影片中的重要時間點
        - 建立地點間的關聯性分析
        - 為地圖視覺化提供資料來源
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
    影片主題摘要模型

    將特定影片的內容分析結果組織成主題化的摘要結構。
    此模型是 Content Extraction Agent 的最終輸出，包含所有識別出的主題項目。

    Attributes:
        video_id (str): YouTube 影片唯一識別碼，與 VideoMetadata 關聯
        topic (str): 主要主題分類 (如 '日本旅遊', '美食探索')
        summary_items (List[SummaryItem]): 該主題下所有擷取的摘要項目列表

    資料流程:
        VideoMetadata → ContentExtractionAgent → VideoTopicSummary → MapVisualizationAgent

    使用注意:
        - summary_items 按時間順序排列，方便路線規劃
        - 每個 SummaryItem 應包含足夠資訊供地理編碼使用
    """

    video_id: str  # 影片唯一識別碼
    topic: str  # 主題名稱
    summary_items: List[SummaryItem]  # 該主題下的摘要項目列表


# endregion

# region: 地圖視覺化結構


class RouteItem(BaseModel):
    """
    路線地點項目模型

    代表地圖上的單一地點節點，包含完整的地理資訊和顯示設定。
    此模型是 Map Visualization Agent 的核心輸出，經過地理編碼處理。

    Attributes:
        location (str): 標準化的地點名稱 (經過地理編碼驗證)
        coordinates (Optional[List[float]]): WGS84 座標 [經度, 緯度] (範圍: [-180,180], [-90,90])
        description (Optional[str]): 地點的詳細描述，包含影片中的相關內容
        timecode (Optional[str]): 對應影片時間戳，用於與影片內容同步
        tags (Optional[List[str]]): 地點分類標籤 (如 '餐廳', '景點', '交通')
        marker (Optional[str]): 地圖標記樣式識別碼 (用於前端顯示)

    地理編碼過程:
        SummaryItem.name → Google Geocoding API → RouteItem.coordinates

    注意事項:
        - coordinates 為 None 表示地理編碼失敗
        - timecode 格式必須符合 WebVTT 時間標準
    """

    location: str  # 地點名稱
    coordinates: Optional[List[float]]  # 地點座標 [經度, 緯度]
    description: Optional[str]  # 地點描述
    timecode: Optional[str]  # 對應影片時間戳（hh:mm:ss,mmm）
    tags: Optional[List[str]]  # 標籤列表
    marker: Optional[str]  # 標記樣式設定


class MapVisualization(BaseModel):
    """
    地圖視覺化資料模型

    包含完整的地圖呈現所需資料，是整個分析流程的最終輸出。
    此模型將轉換為 GeoJSON 格式供前端地圖元件使用。

    Attributes:
        video_id (str): YouTube 影片唯一識別碼，用於結果快取和查詢
        routes (List[RouteItem]): 已完成地理編碼的路線地點項目列表

    輸出格式:
        MapVisualization → GeoJSON FeatureCollection
        - RouteItem → Point Feature (coordinates 存在時)
        - 多個 RouteItem → LineString Feature (路線連接)

    快取策略:
        - 存儲於 Redis: key="analysis:{video_id}"
        - 提供 REST API: GET /api/results/{task_id}
        - 轉換為 GeoJSON: GET /api/map/{task_id}.geojson

    品質檢查:
        - routes 不應為空列表
        - 至少 50% 的 RouteItem 應有有效 coordinates
        - timecode 應按時間順序排列
    """

    video_id: str  # 影片唯一識別碼
    routes: List[RouteItem]  # 路線項目列表


# endregion
