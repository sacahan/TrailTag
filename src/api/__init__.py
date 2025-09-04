"""
TrailTag API 模組 (FastAPI Backend)

TrailTag 的 FastAPI 後端服務，提供 YouTube 影片分析與地圖化的 API 介面。
使用模組化架構設計，支援非同步任務處理、即時進度更新、快取機制等功能。

模組結構：
- core/: 核心 API 組件 (模型定義、日誌配置)
- routes/: API 路由與端點處理器
- middleware/: 中間件與處理器 (SSE、CORS 等)
- services/: 業務邏輯服務 (CrewAI 執行、狀態管理、Webhooks)
- cache/: 快取系統 (Redis + 記憶體快取備案)
- monitoring/: 監控與可觀測性 (指標收集、分散式追蹤)

主要功能：
- YouTube 影片分析任務提交與追蹤
- CrewAI 代理程式非同步執行管理
- GeoJSON 格式的路線資料輸出
- Server-Sent Events 即時進度推送
- 多層級快取系統提升性能
- 完整的監控與可觀測性支援
"""

# 核心組件
from . import core

# API 路由
from . import routes

# 中間件處理
from . import middleware

# 業務邏輯服務
from . import services

# 快取系統
from . import cache

# 監控系統
from . import monitoring

__all__ = [
    "core",
    "routes",
    "middleware",
    "services",
    "cache",
    "monitoring",
]
