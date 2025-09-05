import json
import hashlib
import time
from typing import Dict, Any, Optional, Union
from datetime import datetime
from src.api.core.logger_config import get_logger
from src.trailtag.memory.manager import CrewMemoryManager

logger = get_logger(__name__)


class CrewAICacheProvider:
    """
    CrewAI Memory 快取提供者 (最终修复版本)

    完全基於 CrewAI Memory 系統實現的快取功能，修复了搜索逻辑问题，特别是冒号字符的处理。
    """

    def __init__(self, prefix: str = "trailtag:"):
        """
        初始化 CrewAI Memory 快取提供者

        Args:
            prefix: 快取鍵值前綴，用於區分不同應用的快取數據
        """
        self.logger = logger
        self.prefix = prefix
        self.memory = CrewMemoryManager()

        # 記錄初始化狀態
        self.logger.info("CrewAI Memory 快取提供者已初始化")

    def _generate_key(
        self, query: Union[str, Dict], params: Optional[Dict] = None
    ) -> str:
        """
        根據 query 與 params 產生唯一快取鍵值

        使用 MD5 雜湊確保鍵值的唯一性和一致性，同時加上前綴便於管理。

        Args:
            query: 查詢字串或字典
            params: 額外的查詢參數

        Returns:
            str: 唯一的快取鍵值
        """
        if isinstance(query, dict):
            query_str = json.dumps(query, sort_keys=True, ensure_ascii=False)
        else:
            query_str = str(query)

        hash_input = query_str
        if params:
            hash_input += json.dumps(params, sort_keys=True, ensure_ascii=False)

        cache_key = f"{self.prefix}{hashlib.md5(hash_input.encode()).hexdigest()}"
        return cache_key

    def get(
        self, query: Union[str, Dict], params: Optional[Dict] = None
    ) -> Optional[Any]:
        """
        從 CrewAI Memory 獲取快取內容 (最终修复版本)

        Args:
            query: 查詢內容
            params: 額外查詢參數

        Returns:
            快取的內容，若不存在則為 None
        """
        try:
            cache_key = self._generate_key(query, params)
            query_str = str(query)

            # CrewMemoryStorage的搜索对冒号有问题，需要使用不同的搜索策略
            # 1. 直接遍历所有内存记录进行精确匹配（最可靠）
            for memory_id, memory_entry in self.memory.memory_storage.memories.items():
                metadata = memory_entry.metadata

                # 检查是否为cache类型且未被删除
                if metadata.get("type") == "cache" and not metadata.get(
                    "deleted", False
                ):
                    original_query = metadata.get("original_query", "")
                    result_key = metadata.get("key", "")

                    # 精确匹配
                    if original_query == query_str or result_key == cache_key:
                        cached_content = memory_entry.content
                        if cached_content:
                            # 尝试解析 JSON
                            try:
                                return json.loads(cached_content)
                            except json.JSONDecodeError:
                                # 若不是 JSON，直接返回字串
                                return cached_content

            # 2. 如果精确匹配失败，尝试搜索（避免冒号问题）
            # 提取job ID进行搜索
            if query_str.startswith("job:"):
                job_id = query_str[4:]  # 去掉 "job:" 前缀
                search_results = self.memory.search(
                    query=job_id, limit=20, score_threshold=0.0
                )

                # 手动过滤cache类型的记录
                for result in search_results:
                    metadata = result.get("metadata", {})
                    if metadata.get("type") == "cache" and not metadata.get(
                        "deleted", False
                    ):
                        original_query = metadata.get("original_query", "")
                        if original_query == query_str:
                            cached_content = result.get("content")
                            if cached_content:
                                try:
                                    return json.loads(cached_content)
                                except json.JSONDecodeError:
                                    return cached_content

            return None

        except Exception as e:
            self.logger.error(f"CrewAI Memory 獲取快取失敗: {str(e)}")
            return None

    def set(
        self,
        query: Union[str, Dict],
        result: Any,
        params: Optional[Dict] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        將內容存入 CrewAI Memory 快取

        Args:
            query: 查詢內容（用作快取鍵）
            result: 要快取的結果
            params: 額外查詢參數
            ttl: 存活時間（秒），CrewAI Memory 中暫未使用

        Returns:
            bool: 是否成功存入
        """
        try:
            cache_key = self._generate_key(query, params)

            # 序列化結果（處理 datetime 對象）
            if isinstance(result, (dict, list)):
                content = json.dumps(
                    result, ensure_ascii=False, default=self._json_serializer
                )
            else:
                content = str(result)

            # 存入 CrewAI Memory
            memory_id = self.memory.memory_storage.save(
                value=content,
                metadata={
                    "type": "cache",
                    "key": cache_key,
                    "original_query": str(query),
                    "ttl": ttl,
                    "stored_at": time.time(),
                },
            )
            success = memory_id is not None

            if success:
                self.logger.debug(f"成功存入快取，鍵值: {cache_key}")
                return True
            else:
                self.logger.warning(f"存入快取失敗，鍵值: {cache_key}")
                return False

        except Exception as e:
            self.logger.error(f"CrewAI Memory 設置快取失敗: {str(e)}")
            return False

    def exists(self, query: Union[str, Dict], params: Optional[Dict] = None) -> bool:
        """
        檢查快取是否存在於 CrewAI Memory 中

        Args:
            query: 查詢內容
            params: 額外查詢參數

        Returns:
            bool: 快取是否存在
        """
        try:
            return self.get(query, params) is not None
        except Exception as e:
            self.logger.error(f"CrewAI Memory 檢查快取存在失敗: {str(e)}")
            return False

    def delete(self, query: Union[str, Dict], params: Optional[Dict] = None) -> bool:
        """
        從 CrewAI Memory 刪除快取

        Note: CrewAI Memory 目前不直接支援刪除操作，
        這裡實現為標記刪除（透過元數據標記）

        Args:
            query: 查詢內容
            params: 額外查詢參數

        Returns:
            bool: 是否成功標記刪除
        """
        try:
            cache_key = self._generate_key(query, params)

            # CrewAI Memory 不直接支援刪除，使用軟刪除標記
            memory_id = self.memory.memory_storage.save(
                value="DELETED",
                metadata={
                    "type": "cache",
                    "key": cache_key,
                    "deleted": True,
                    "deleted_at": time.time(),
                },
            )
            success = memory_id is not None

            if success:
                self.logger.debug(f"成功標記刪除快取: {cache_key}")

            return success

        except Exception as e:
            self.logger.error(f"CrewAI Memory 刪除快取失敗: {str(e)}")
            return False

    def clear(self):
        """
        清空所有快取（軟刪除）

        由於 CrewAI Memory 不支援批次刪除，此方法記錄警告信息。
        在生產環境中，建議透過 CrewAI Memory 管理介面進行清理。
        """
        self.logger.warning(
            "CrewAI Memory 不支援批次清除快取，請使用 Memory 管理工具進行清理"
        )

    def scan_keys(self, pattern: str) -> list:
        """
        掃描符合模式的快取鍵

        使用 CrewAI Memory 的搜索功能查找符合模式的快取項目。

        Args:
            pattern: 鍵值模式（支援萬用字元）

        Returns:
            list: 符合模式的鍵值列表
        """
        try:
            # 直接遍历所有记录进行模式匹配
            keys = []
            for memory_id, memory_entry in self.memory.memory_storage.memories.items():
                metadata = memory_entry.metadata
                if (
                    metadata.get("type") == "cache"
                    and metadata.get("key")
                    and not metadata.get("deleted")
                ):
                    key = metadata["key"]
                    if pattern in key:  # 简单包含匹配
                        keys.append(key)

            self.logger.debug(f"掃描到 {len(keys)} 個符合模式 '{pattern}' 的快取鍵")
            return keys

        except Exception as e:
            self.logger.error(f"CrewAI Memory 掃描鍵值失敗: {str(e)}")
            return []

    def _json_serializer(self, obj):
        """JSON 序列化處理器，處理 datetime 和其他特殊對象"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, "__dict__"):
            return obj.__dict__
        else:
            return str(obj)
