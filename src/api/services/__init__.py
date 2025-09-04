"""
API 業務邏輯服務模組 (API Business Logic Services)

此模組包含 API 應用程式的核心業務邏輯服務：
- crew_executor.py: CrewAI 代理程式執行管理器
  * 負責非同步執行 CrewAI 任務流程
  * 管理代理程式生命週期與資源分配
  * 處理任務排隊、執行、完成等狀態轉換

- execution_state.py: 任務執行狀態管理器
  * 持久化任務執行狀態與進度追蹤
  * 提供任務恢復與錯誤處理機制
  * 支援分散式任務狀態同步

- webhooks.py: Webhook 回調處理器
  * 處理外部系統的回調通知
  * 支援任務完成、錯誤等事件的通知
  * 提供可擴展的事件處理框架

這些服務封裝了複雜的業務邏輯，為 API 路由
提供高階的功能介面。
"""

from .crew_executor import crew_executor
from .execution_state import execution_state
from .webhooks import webhooks

__all__ = [
    "crew_executor",
    "execution_state",
    "webhooks",
]
