# 匯入共享介面
from src.common.interfaces import CacheInterface

# 匯入 CrewAI Memory 快取提供者
from .cache_provider import CrewAICacheProvider


class CacheManager(CacheInterface):
    """
    CrewAI Memory 快取管理器

    完全基於 CrewAI Memory 系統的快取管理器，取代原有的 Redis 快取系統。
    提供統一的快取操作介面，確保與現有系統的相容性。

    主要特色：
        - 純 CrewAI Memory：完全移除對 Redis 的依賴
        - 語義搜索：支援基於內容相似性的快取檢索
        - 統一介面：保持與原有快取系統的 API 相容性
        - 高效能：利用 CrewAI Memory 的向量化存儲優勢
        - 零配置：無需額外的外部服務配置

    遷移優勢：
        - 簡化架構：移除 Redis 服務依賴
        - 智能快取：基於語義相似性的快取匹配
        - 原生整合：與 CrewAI 工作流程深度整合
        - 持久化：CrewAI Memory 內建數據持久性
    """

    def __init__(self):
        """
        初始化 CrewAI Memory 快取管理器

        直接使用 CrewAI Memory 作為唯一的快取後端，
        無需考慮降級模式或外部服務連線問題。
        """
        # 使用 CrewAI Memory 作為快取後端
        self.backend = CrewAICacheProvider()

        # CrewAI Memory 系統永遠可用，無降級模式
        self.degraded = False

    def get(self, key, params=None):
        """
        從 CrewAI Memory 取得快取內容

        Args:
            key: 快取鍵值
            params: 進階查詢參數（可選）

        Returns:
            對應的快取內容，若不存在則回傳 None
        """
        return self.backend.get(key, params)

    def set(self, key, value, params=None, ttl: int = None):
        """
        將內容存入 CrewAI Memory 快取

        Args:
            key: 快取鍵值
            value: 欲儲存的內容
            params: 進階查詢參數（可選）
            ttl: 存活時間（秒），CrewAI Memory 中目前未實作

        Returns:
            bool: 是否成功存入
        """
        return self.backend.set(key, value, params, ttl=ttl)

    def exists(self, key, params=None):
        """
        檢查快取是否存在於 CrewAI Memory 中

        Args:
            key: 快取鍵值
            params: 進階查詢參數（可選）

        Returns:
            bool: 快取是否存在
        """
        return self.backend.exists(key, params)

    def delete(self, key, params=None):
        """
        從 CrewAI Memory 刪除快取

        Args:
            key: 快取鍵值
            params: 進階查詢參數（可選）

        Returns:
            bool: 是否成功刪除
        """
        return self.backend.delete(key, params)

    def clear(self):
        """
        清除所有 CrewAI Memory 快取內容

        Note: 由於 CrewAI Memory 的設計特性，此操作會記錄警告信息。
        實際的批次清理建議透過 CrewAI Memory 管理工具執行。
        """
        self.backend.clear()

    def is_degraded(self):
        """
        檢查快取系統是否處於降級狀態

        Returns:
            bool: CrewAI Memory 系統永遠返回 False（無降級模式）

        Note:
            由於 CrewAI Memory 是內建系統，不依賴外部服務，
            因此不會出現降級情況。此方法保留是為了向下相容性。
        """
        return self.degraded

    def get_stats(self):
        """
        取得 CrewAI Memory 快取系統統計資訊

        Returns:
            dict: 快取系統的統計資訊
        """
        return {
            "backend": "CrewAI Memory",
            "degraded": False,
            "type": "semantic_cache",
            "features": [
                "semantic_search",
                "vector_storage",
                "metadata_filtering",
                "content_similarity",
            ],
        }
