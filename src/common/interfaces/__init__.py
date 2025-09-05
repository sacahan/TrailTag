"""
快取系統介面定義

定義快取系統的抽象介面，用於解決循環依賴問題。
所有快取實現都應該實現這個介面。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class CacheInterface(ABC):
    """
    快取系統抽象介面

    定義了快取系統的基本操作，包括：
    - 資料存取 (get/set)
    - 存在性檢查 (exists)
    - 資料刪除 (delete)
    - 系統清理 (clear)
    - 狀態檢查 (is_degraded)
    - 統計資訊 (get_stats)
    """

    @abstractmethod
    def get(self, key: str, params: Optional[Dict] = None) -> Any:
        """
        從快取中取得資料

        Args:
            key: 快取鍵值
            params: 進階查詢參數（可選）

        Returns:
            對應的快取內容，若不存在則回傳 None
        """
        pass

    @abstractmethod
    def set(
        self,
        key: str,
        value: Any,
        params: Optional[Dict] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        將資料存入快取

        Args:
            key: 快取鍵值
            value: 欲儲存的內容
            params: 進階查詢參數（可選）
            ttl: 存活時間（秒），可選

        Returns:
            bool: 是否成功存入
        """
        pass

    @abstractmethod
    def exists(self, key: str, params: Optional[Dict] = None) -> bool:
        """
        檢查快取是否存在

        Args:
            key: 快取鍵值
            params: 進階查詢參數（可選）

        Returns:
            bool: 快取是否存在
        """
        pass

    @abstractmethod
    def delete(self, key: str, params: Optional[Dict] = None) -> bool:
        """
        從快取中刪除資料

        Args:
            key: 快取鍵值
            params: 進階查詢參數（可選）

        Returns:
            bool: 是否成功刪除
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """
        清除所有快取內容
        """
        pass

    @abstractmethod
    def is_degraded(self) -> bool:
        """
        檢查快取系統是否處於降級狀態

        Returns:
            bool: 是否處於降級狀態
        """
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        取得快取系統統計資訊

        Returns:
            dict: 快取系統的統計資訊
        """
        pass


class MemoryInterface(ABC):
    """
    記憶體管理介面

    定義了記憶體管理系統的基本操作。
    """

    @abstractmethod
    def save_memory(
        self, agent_role: str, content: str, metadata: Optional[Dict] = None
    ) -> bool:
        """
        儲存記憶體內容

        Args:
            agent_role: Agent 角色
            content: 記憶體內容
            metadata: 元數據（可選）

        Returns:
            bool: 是否成功儲存
        """
        pass

    @abstractmethod
    def search_memory(
        self, query: str, agent_role: Optional[str] = None, limit: int = 10
    ) -> list:
        """
        搜尋記憶體內容

        Args:
            query: 搜尋查詢
            agent_role: Agent 角色過濾（可選）
            limit: 回傳數量限制

        Returns:
            list: 搜尋結果列表
        """
        pass
