"""
API 模型定義模組
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    """任務狀態列舉"""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELED = "canceled"


class SubtitleStatus(BaseModel):
    """字幕狀態資訊"""

    available: bool = Field(..., description="是否有可用字幕")
    manual_subtitles: List[str] = Field(
        default_factory=list, description="手動字幕語言列表"
    )
    auto_captions: List[str] = Field(
        default_factory=list, description="自動字幕語言列表"
    )
    selected_lang: Optional[str] = Field(None, description="實際選擇的字幕語言")
    confidence_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="字幕品質信心分數"
    )


class Phase(str, Enum):
    """處理階段列舉"""

    METADATA = "metadata"
    COMPRESSION = "compression"
    SUMMARY = "summary"
    GEOCODE = "geocode"


class RouteItem(BaseModel):
    """
    路線項目，描述地圖上一個地點與相關資訊。
    """

    location: str
    coordinates: Optional[List[float]] = None
    description: Optional[str] = None
    timecode: Optional[str] = None
    tags: Optional[List[str]] = None
    marker: Optional[str] = None


class MapVisualization(BaseModel):
    """
    地圖視覺化資料，包含影片ID與多個路線項目。
    """

    video_id: str
    routes: List[RouteItem]


class AnalyzeRequest(BaseModel):
    """分析請求模型"""

    url: HttpUrl = Field(..., description="YouTube 影片 URL")


class JobResponse(BaseModel):
    """任務回應模型"""

    job_id: str
    video_id: str
    status: JobStatus
    phase: Optional[Phase] = None
    progress: float = 0
    cached: bool = False
    created_at: datetime
    updated_at: datetime
    subtitle_availability: Optional[SubtitleStatus] = Field(
        None, description="字幕可用性資訊"
    )


class JobStatusResponse(BaseModel):
    """任務狀態回應模型"""

    job_id: str
    status: JobStatus
    phase: Optional[Phase] = None
    progress: float = 0
    stats: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[Dict[str, str]] = None
    subtitle_availability: Optional[SubtitleStatus] = Field(
        None, description="字幕可用性資訊"
    )
