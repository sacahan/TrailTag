"""
TrailTag 核心系統模組 (Core System)

此模組包含 TrailTag 的核心系統元件：
- crew.py: CrewAI 核心配置與代理程式定義
- models.py: 基礎資料模型與 Pydantic 結構
- observers.py: CrewAI 事件監聽器與性能監控

這些是系統運行的基礎組件，負責 CrewAI 的初始化、
代理程式協調以及系統監控。
"""

from .crew import Trailtag
from . import models
from .observers import AgentObserver

__all__ = [
    "Trailtag",
    "AgentObserver",
    "models",
]
