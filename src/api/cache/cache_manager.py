# 匯入記憶體快取（當 Redis 不可用時自動降級）
from .cache_provider import MemoryCacheProvider, RedisCacheProvider


class CacheManager:
    """
    快取提供者：自動選擇 Redis 或記憶體快取作為後端。
    - 預設優先使用 Redis，若連線失敗則自動降級為記憶體快取（degraded 模式）。
    - 封裝 get/set/exists/delete/clear 介面，統一快取操作。
    - 提供 degraded 狀態查詢，利於健康檢查與監控。
    """

    def __init__(self):
        """
        初始化快取提供者。
        嘗試建立 Redis 連線，若失敗則自動切換為記憶體快取。
        """
        try:
            # 嘗試建立 Redis 快取後端
            self.backend = RedisCacheProvider()
            self.degraded = False  # Redis 可用，非 degraded
        except Exception:
            # Redis 失敗時自動切換為記憶體快取
            self.backend = MemoryCacheProvider()
            self.degraded = True  # 進入 degraded 模式

    def get(self, key, params=None):
        """
        取得快取內容。
        :param key: 快取鍵值
        :param params: 進階查詢參數（可選）
        :return: 對應快取內容，若不存在則回傳 None
        """
        return self.backend.get(key, params)

    def set(self, key, value, params=None, ttl: int = None):
        """
        設定快取內容。
        :param key: 快取鍵值
        :param value: 欲儲存內容
        :param params: 進階查詢參數（可選）
        :return: 是否成功
        """
        # Forward optional ttl to backend if supported
        try:
            return self.backend.set(key, value, params, ttl=ttl)
        except TypeError:
            # backend may not accept ttl param (backwards compatibility)
            return self.backend.set(key, value, params)

    def exists(self, key, params=None):
        """
        檢查快取鍵是否存在。
        :param key: 快取鍵值
        :param params: 進階查詢參數（可選）
        :return: 存在則回傳 True，否則 False
        """
        return self.backend.exists(key, params)

    def delete(self, key, params=None):
        """
        刪除指定快取鍵。
        :param key: 快取鍵值
        :param params: 進階查詢參數（可選）
        :return: 是否成功
        """
        return self.backend.delete(key, params)

    def clear(self):
        """
        清除所有快取內容（僅限支援 clear 的 backend）。
        """
        if hasattr(self.backend, "clear"):
            self.backend.clear()

    def is_degraded(self):
        """
        回傳目前快取是否處於 degraded（降級）狀態。
        :return: True 表示 Redis 不可用，使用記憶體快取
        """
        return self.degraded
