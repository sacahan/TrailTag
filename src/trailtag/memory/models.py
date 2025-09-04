"""
CrewAI Memory 系統資料模型

此模組定義了 CrewAI Memory 系統的資料結構，用於替代 Redis 快取。
基於 CrewAI 官方文檔中的 Memory 最佳實踐設計。
"""

import os
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from enum import Enum


class MemoryType(str, Enum):
    """記憶類型枚舉"""

    SHORT_TERM = "short_term"  # 短期記憶：當前對話/任務上下文
    LONG_TERM = "long_term"  # 長期記憶：跨會話持久化資料
    ENTITY = "entity"  # 實體記憶：實體關係與知識
    KNOWLEDGE = "knowledge"  # 知識庫：結構化知識儲存


class JobStatus(str, Enum):
    """任務狀態枚舉"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPhase(str, Enum):
    """任務執行階段"""

    METADATA = "metadata"  # 影片 metadata 提取
    SUMMARY = "summary"  # 主題摘要分析
    GEOCODE = "geocode"  # 地理編碼與地圖生成
    PROCESSING = "processing"  # 通用處理階段


class MemoryEntry(BaseModel):
    """基礎記憶條目模型"""

    id: str = Field(..., description="記憶條目唯一識別碼")
    memory_type: MemoryType = Field(..., description="記憶類型")
    content: Union[str, Dict[str, Any]] = Field(..., description="記憶內容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="額外元資料")
    agent_role: Optional[str] = Field(None, description="相關 Agent 角色")
    task_id: Optional[str] = Field(None, description="相關任務 ID")
    video_id: Optional[str] = Field(None, description="相關影片 ID")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = Field(None, description="過期時間（可選）")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class JobProgressEntry(BaseModel):
    """任務進度記憶條目"""

    job_id: str = Field(..., description="任務 ID")
    video_id: str = Field(..., description="影片 ID")
    status: JobStatus = Field(default=JobStatus.PENDING, description="任務狀態")
    phase: JobPhase = Field(..., description="當前執行階段")
    progress: int = Field(default=0, ge=0, le=100, description="進度百分比")
    cached: bool = Field(default=False, description="是否使用快取結果")
    result: Optional[Dict[str, Any]] = Field(None, description="任務結果資料")
    error_message: Optional[str] = Field(None, description="錯誤訊息")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class AnalysisResultEntry(BaseModel):
    """影片分析結果記憶條目"""

    video_id: str = Field(..., description="影片 ID")
    metadata: Dict[str, Any] = Field(..., description="影片 metadata")
    topic_summary: Dict[str, Any] = Field(..., description="主題摘要")
    map_visualization: Dict[str, Any] = Field(..., description="地圖可視化資料")
    processing_time: float = Field(..., description="處理時間（秒）")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    cached: bool = Field(default=False, description="結果是否來自快取")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class AgentMemoryEntry(BaseModel):
    """Agent 特定記憶條目"""

    agent_role: str = Field(..., description="Agent 角色")
    memory_type: MemoryType = Field(..., description="記憶類型")
    context: str = Field(..., description="記憶上下文")
    entities: List[Dict[str, Any]] = Field(
        default_factory=list, description="提取的實體"
    )
    relationships: List[Dict[str, Any]] = Field(
        default_factory=list, description="實體關係"
    )
    insights: List[str] = Field(default_factory=list, description="學到的洞察")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="信心分數")
    source_task_id: Optional[str] = Field(None, description="來源任務 ID")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class CrewMemoryConfig(BaseModel):
    """CrewAI Memory 配置模型"""

    enabled: bool = Field(default=True, description="是否啟用記憶功能")
    storage_path: str = Field(
        default_factory=lambda: os.getenv("CREWAI_STORAGE_DIR", "./crewai_storage"),
        description="記憶儲存路徑",
    )
    embedder_config: Dict[str, Any] = Field(
        default_factory=lambda: {
            "provider": "openai",
            "config": {"model": "text-embedding-3-small"},
        },
        description="嵌入模型配置",
    )
    max_short_term_entries: int = Field(default=1000, description="短期記憶最大條目數")
    max_long_term_entries: int = Field(default=10000, description="長期記憶最大條目數")
    cleanup_interval_hours: int = Field(default=24, description="清理間隔（小時）")

    # Redis 遷移相關設定
    redis_migration_batch_size: int = Field(
        default=100, description="Redis 遷移批次大小"
    )
    redis_backup_enabled: bool = Field(default=True, description="是否備份 Redis 資料")

    class Config:
        env_prefix = "CREWAI_MEMORY_"


class MemoryQuery(BaseModel):
    """記憶查詢模型"""

    query_text: str = Field(..., description="查詢文字")
    memory_types: List[MemoryType] = Field(
        default_factory=list, description="查詢的記憶類型"
    )
    agent_role: Optional[str] = Field(None, description="特定 Agent 角色")
    video_id: Optional[str] = Field(None, description="特定影片 ID")
    limit: int = Field(default=10, ge=1, le=100, description="返回結果數量限制")
    score_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="相似度分數閾值"
    )
    time_range_start: Optional[datetime] = Field(None, description="時間範圍開始")
    time_range_end: Optional[datetime] = Field(None, description="時間範圍結束")


class MemoryQueryResult(BaseModel):
    """記憶查詢結果"""

    entries: List[MemoryEntry] = Field(default_factory=list, description="查詢結果")
    total_count: int = Field(default=0, description="總結果數")
    query_time_ms: float = Field(..., description="查詢耗時（毫秒）")
    max_score: float = Field(default=0.0, description="最高相似度分數")
    avg_score: float = Field(default=0.0, description="平均相似度分數")


class MemoryStats(BaseModel):
    """記憶系統統計資訊"""

    total_entries: int = Field(default=0, description="總記憶條目數")
    short_term_count: int = Field(default=0, description="短期記憶數量")
    long_term_count: int = Field(default=0, description="長期記憶數量")
    entity_count: int = Field(default=0, description="實體記憶數量")
    knowledge_count: int = Field(default=0, description="知識庫條目數")
    storage_size_mb: float = Field(default=0.0, description="儲存空間使用（MB）")
    last_cleanup: Optional[datetime] = Field(None, description="上次清理時間")
    avg_query_time_ms: float = Field(default=0.0, description="平均查詢時間（毫秒）")


# 向後相容的類型別名
VideoMetadataCache = AnalysisResultEntry  # 保持與現有程式碼相容
JobCache = JobProgressEntry  # 保持與現有程式碼相容
