import json
import hashlib
import os
import time
import datetime
from typing import Dict, Any, Optional, Union
import redis
from src.api.logger_config import get_logger

logger = get_logger(__name__)


def json_default(obj):
    # 處理 datetime 物件序列化
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


# 記憶體快取（斷線/測試用）
class MemoryCacheProvider:
    """
    提供本地記憶體快取功能，適用於測試或 Redis 斷線時。
    支援快取存取、過期檢查、刪除與清空。
    """

    def __init__(self, expiry_seconds=3600):
        # 初始化快取儲存結構與預設過期秒數
        # _store maps key -> (value, ts, ttl_seconds_or_None)
        self._store = {}
        self.expiry_seconds = expiry_seconds

    def _now(self):
        # 取得目前時間（秒）
        return int(time.time())

    def get(self, key):
        # 取得快取內容，若已過期則自動移除
        v = self._store.get(key)
        if not v:
            return None
        value, ts, ttl = v
        ttl = ttl if ttl is not None else self.expiry_seconds
        if self._now() - ts > ttl:
            del self._store[key]
            return None
        return value

    def set(self, key, value, ttl: int = None):
        # 設定快取內容，並記錄存入時間與可選的 TTL（秒）
        # 若 ttl 為 None，會使用預設 self.expiry_seconds
        self._store[key] = (value, self._now(), ttl)

    def exists(self, key):
        # 檢查快取是否存在且未過期
        v = self._store.get(key)
        if not v:
            return False
        value, ts, ttl = v
        ttl = ttl if ttl is not None else self.expiry_seconds
        if self._now() - ts > ttl:
            del self._store[key]
            return False
        return True

    def delete(self, key):
        # 刪除指定快取
        if key in self._store:
            del self._store[key]

    def clear(self):
        # 清空所有快取
        self._store.clear()


class RedisCacheProvider:
    """
    Redis 快取工具，支援 get/set/exists/delete/clear_all，並自動序列化 JSON。
    用於儲存和檢索分析結果、狀態等。
    """

    def __init__(
        self,
        host: str = None,
        port: int = None,
        db: int = None,
        password: Optional[str] = None,
        expiry_days: int = None,
        prefix: str = "trailtag:",
    ):
        """
        初始化 RedisCacheProvider，設定連線參數、快取前綴與過期時間。
        連線失敗時 logger 會記錄警告。
        """
        self.logger = logger
        self.expiry_days = (
            expiry_days
            if expiry_days is not None
            else int(os.getenv("REDIS_EXPIRY_DAYS", 7))
        )
        self.expiry_seconds = self.expiry_days * 24 * 60 * 60
        self.prefix = prefix

        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT", 6379))
        self.db = db if db is not None else int(os.getenv("REDIS_DB", 0))
        self.password = (
            password if password is not None else os.getenv("REDIS_PASSWORD", None)
        )

        self.redis = None
        try:
            # 建立 Redis 連線
            self.redis = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
            )
            self.redis.ping()
            self.logger.debug("*** Redis Connected ***")
        except Exception as e:
            self.logger.warning(f"Redis 連接失敗: {str(e)}")
            self.redis = None

    def _generate_key(
        self, query: Union[str, Dict], params: Optional[Dict] = None
    ) -> str:
        """
        根據 query 與 params 產生唯一快取鍵值，並加上前綴。
        以 MD5 雜湊確保鍵值唯一且不易重複。
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
        """
        取得指定 query 與 params 的快取內容。
        若 Redis 未連接或快取不存在則回傳 None。
        內容自動反序列化為 Python 物件。
        """
        if not self.redis:
            self.logger.warning("Redis 未連接，無法獲取快取")
            return None
        try:
            key = self._generate_key(query, params)
            data = self.redis.get(key)
            if not data:
                return None
            return json.loads(data)
        except Exception as e:
            self.logger.error(f"Redis 獲取快取失敗: {str(e)}")
            return None

    def set(
        self,
        query: Union[str, Dict],
        result: Any,
        params: Optional[Dict] = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        設定快取內容，將 result 以 JSON 序列化後存入 Redis。
        若 Redis 未連接則回傳 False。
        """
        if not self.redis:
            self.logger.warning("Redis 未連接，無法設置快取")
            return False
        try:
            key = self._generate_key(query, params)
            result_json = json.dumps(result, ensure_ascii=False, default=json_default)
            expire = ttl if ttl is not None else self.expiry_seconds
            self.redis.setex(key, expire, result_json)
            self.logger.debug(f"已成功設置快取，鍵值: {key}")
            return True
        except Exception as e:
            self.logger.error(f"Redis 設置快取失敗: {str(e)}")
            return False

    def exists(self, query: Union[str, Dict], params: Optional[Dict] = None) -> bool:
        """
        檢查指定 query 與 params 的快取是否存在。
        若 Redis 未連接則回傳 False。
        """
        if not self.redis:
            return False
        try:
            key = self._generate_key(query, params)
            return bool(self.redis.exists(key))
        except Exception as e:
            self.logger.error(f"Redis 檢查鍵存在失敗: {str(e)}")
            return False

    def delete(self, query: Union[str, Dict], params: Optional[Dict] = None) -> bool:
        """
        刪除指定 query 與 params 的快取。
        若 Redis 未連接則回傳 False。
        """
        if not self.redis:
            return False
        try:
            key = self._generate_key(query, params)
            return bool(self.redis.delete(key))
        except Exception as e:
            self.logger.error(f"Redis 刪除鍵失敗: {str(e)}")
            return False

    def clear_all(self, pattern: str = None) -> int:
        """
        清除所有符合 pattern 的快取鍵。
        預設清除所有 trailtag 前綴的快取。
        回傳刪除鍵數量。
        若 Redis 未連接則回傳 0。
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
            self.logger.error(f"Redis 清除快取失敗: {str(e)}")
            return 0
