"""
Redis 快取工具 - 用於快取 CrewAI 輸出結果
"""

import json
import hashlib
import logging
import os
from typing import Dict, Any, Optional, Union

import redis

logger = logging.getLogger(__name__)


class RedisCacheTool:
    """Redis 快取工具，用於儲存和檢索 CrewAI 輸出結果"""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        db: int = None,
        password: Optional[str] = None,
        expiry_days: int = None,
        prefix: str = "crewai:",
    ):
        """初始化 Redis 快取工具

        Args:
            host: Redis 伺服器主機
            port: Redis 埠號
            db: Redis 資料庫編號
            password: Redis 密碼
            expiry_days: 快取過期天數
            prefix: 快取鍵前綴
        """
        super().__init__()
        # 從環境變數讀取快取過期天數，預設 7 天
        self.expiry_days = (
            expiry_days
            if expiry_days is not None
            else int(os.getenv("REDIS_EXPIRY_DAYS", 7))
        )
        self.expiry_seconds = self.expiry_days * 24 * 60 * 60
        self.prefix = prefix

        # 從環境變數讀取 Redis 連線參數，若未指定則使用預設值
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT", 6379))
        self.db = db if db is not None else int(os.getenv("REDIS_DB", 0))
        self.password = (
            password if password is not None else os.getenv("REDIS_PASSWORD", None)
        )

        # 記錄 Redis 連線參數（不記錄密碼內容）
        print(
            f"Redis 連線參數: host={self.host}, port={self.port}, db={self.db}, password={'***' if self.password else None}, expiry_days={self.expiry_days}"
        )

        # 連接 Redis
        try:
            self.redis = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,  # 自動解碼回應
            )
            self.redis.ping()  # 測試連接
            print("已成功連接到 Redis 伺服器")
        except Exception as e:
            print(f"Redis 連接失敗: {str(e)}")
            self.redis = None

    def _generate_key(
        self, query: Union[str, Dict], params: Optional[Dict] = None
    ) -> str:
        """根據查詢和參數生成唯一快取鍵值

        Args:
            query: 查詢字串或字典
            params: 額外參數字典

        Returns:
            str: 快取鍵值
        """
        if isinstance(query, dict):
            query_str = json.dumps(query, sort_keys=True)
        else:
            query_str = str(query)

        hash_input = query_str
        if params:
            hash_input += json.dumps(params, sort_keys=True)

        return f"{self.prefix}{hashlib.md5(hash_input.encode()).hexdigest()}"

    def get(
        self, query: Union[str, Dict], params: Optional[Dict] = None
    ) -> Optional[Any]:
        """從快取中檢索數據

        Args:
            query: 查詢字串或字典
            params: 額外參數字典

        Returns:
            Optional[Any]: 快取數據，若不存在則為 None
        """
        if not self.redis:
            logger.warning("Redis 未連接，無法獲取快取")
            return None

        try:
            key = self._generate_key(query, params)
            data = self.redis.get(key)

            if not data:
                return None

            return json.loads(data)
        except Exception as e:
            logger.error(f"Redis 獲取快取失敗: {str(e)}")
            return None

    def set(
        self, query: Union[str, Dict], result: Any, params: Optional[Dict] = None
    ) -> bool:
        """向快取中存入數據

        Args:
            query: 查詢字串或字典
            result: 要快取的結果
            params: 額外參數字典

        Returns:
            bool: 是否成功
        """
        if not self.redis:
            logger.warning("Redis 未連接，無法設置快取")
            return False

        try:
            key = self._generate_key(query, params)

            # 將結果轉為 JSON 字串
            result_json = json.dumps(result, ensure_ascii=False)

            # 設置快取並設定過期時間
            self.redis.setex(key, self.expiry_seconds, result_json)

            logger.info(f"已成功設置快取，鍵值: {key}")
            return True
        except Exception as e:
            logger.error(f"Redis 設置快取失敗: {str(e)}")
            return False

    def exists(self, query: Union[str, Dict], params: Optional[Dict] = None) -> bool:
        """檢查快取鍵是否存在

        Args:
            query: 查詢字串或字典
            params: 額外參數字典

        Returns:
            bool: 是否存在
        """
        if not self.redis:
            return False

        try:
            key = self._generate_key(query, params)
            return bool(self.redis.exists(key))
        except Exception as e:
            logger.error(f"Redis 檢查鍵存在失敗: {str(e)}")
            return False

    def delete(self, query: Union[str, Dict], params: Optional[Dict] = None) -> bool:
        """刪除快取鍵

        Args:
            query: 查詢字串或字典
            params: 額外參數字典

        Returns:
            bool: 是否成功
        """
        if not self.redis:
            return False

        try:
            key = self._generate_key(query, params)
            return bool(self.redis.delete(key))
        except Exception as e:
            logger.error(f"Redis 刪除鍵失敗: {str(e)}")
            return False

    def clear_all(self, pattern: str = None) -> int:
        """清除所有或符合模式的快取

        Args:
            pattern: 鍵模式，例如 "crewai:*"

        Returns:
            int: 刪除的鍵數量
        """
        if not self.redis:
            return 0

        try:
            if not pattern:
                pattern = f"{self.prefix}*"

            keys = self.redis.keys(pattern)
            if not keys:
                return 0

            return self.redis.delete(*keys)
        except Exception as e:
            logger.error(f"Redis 清除快取失敗: {str(e)}")
            return 0
