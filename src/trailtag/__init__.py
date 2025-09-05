"""
TrailTag - YouTube 旅遊影片地圖化系統

TrailTag 是一個將 YouTube 旅遊 Vlog 轉換為互動地圖資料和路線可視化的系統。
使用 CrewAI 代理程式來提取影片中的地點資訊，並生成 GeoJSON 格式的地圖資料。

主要模組結構：
- core/: 核心系統 (CrewAI 配置、基礎模型、事件監聽)
- memory/: 記憶系統 (CrewAI Memory、進度追蹤、狀態管理)
- tools/: CrewAI 工具套件 (資料提取、處理、地理編碼)

功能特色：
- YouTube 影片元資料與字幕分析
- 智能地點識別與地理編碼
- 路線重建與 GeoJSON 輸出
- CrewAI Memory 系統取代 Redis
- 完整的性能監控與狀態追蹤
"""

__version__ = "0.2.0"

# 核心系統匯入 (使用延遲匯入避免循環依賴)
from .core import AgentObserver, get_trailtag
from .memory import CrewMemoryManager, get_memory_manager, ProgressTracker

# 工具模組匯入 (需要時才匯入，避免循環依賴)
from . import tools


# 延遲匯入核心類別
def __getattr__(name):
    if name == "Trailtag":
        return get_trailtag()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    # 版本資訊
    "__version__",
    # 核心系統
    "Trailtag",
    "AgentObserver",
    # 記憶系統
    "CrewMemoryManager",
    "get_memory_manager",
    "ProgressTracker",
    # 工具模組
    "tools",
    # 向下相容性支援 (舊版 API)
    "Trailtag",
    "VideoMetadata",
    "SummaryItem",
    "VideoTopicSummary",
    "RouteItem",
    "MapVisualization",
]
