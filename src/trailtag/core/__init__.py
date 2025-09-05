"""
TrailTag 核心系統模組 (Core System)

此模組包含 TrailTag 的核心系統元件：
- crew.py: CrewAI 核心配置與代理程式定義
- models.py: 基礎資料模型與 Pydantic 結構
- observers.py: CrewAI 事件監聽器與性能監控

這些是系統運行的基礎組件，負責 CrewAI 的初始化、
代理程式協調以及系統監控。
"""

# 使用延遲匯入避免循環依賴
from . import models
from .observers import AgentObserver


def get_trailtag():
    """
    延遲匯入 Trailtag 類別以避免循環依賴
    """
    from .crew import Trailtag

    return Trailtag


# 提供向下相容性
Trailtag = None


def __getattr__(name):
    if name == "Trailtag":
        global Trailtag
        if Trailtag is None:
            from .crew import Trailtag as _Trailtag

            Trailtag = _Trailtag
        return Trailtag
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "get_trailtag",
    "AgentObserver",
    "models",
]
