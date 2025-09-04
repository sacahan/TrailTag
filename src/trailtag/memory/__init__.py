"""
TrailTag 記憶系統模組 (Memory System)

此模組包含 CrewAI Memory 系統的實現：
- manager.py: CrewAI Memory 管理器，替代 Redis 快取
- models.py: 記憶系統資料模型與類型定義
- progress_tracker.py: 任務進度追蹤與狀態管理

這個記憶系統提供向量搜尋、任務狀態持久化、
以及比傳統 Redis 快取更智能的記憶管理功能。
"""

from .manager import CrewMemoryManager, get_memory_manager, reset_global_memory_manager
from . import models
from .progress_tracker import ProgressTracker

__all__ = [
    "CrewMemoryManager",
    "get_memory_manager",
    "reset_global_memory_manager",
    "models",
    "ProgressTracker",
    # models 中的類別會通過 * 匯入自動包含
]
