"""
API 快取系統模組 (API Cache System)

此模組包含 API 應用程式的快取系統組件：
- cache_manager.py: 快取管理器
  * 提供統一的快取操作介面
  * 支援 Redis 與記憶體快取的無縫切換
  * 處理快取失效與更新策略

- cache_provider.py: 快取提供者實現
  * Redis 快取提供者 (主要選擇)
  * 記憶體快取提供者 (降級備案)
  * 自動故障轉移與健康檢查機制

快取系統用於加速重複的影片分析請求，
減少 CrewAI 處理時間並提升使用者體驗。
"""

from .cache_manager import cache_manager
from .cache_provider import cache_provider

__all__ = [
    "cache_manager",
    "cache_provider",
]
