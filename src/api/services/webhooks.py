"""
WebHook 回調系統
提供異步通知機制，支持任務狀態變更、結果完成等事件的回調通知。
"""

import json
import asyncio
import aiohttp
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from urllib.parse import urlparse
import hashlib
import hmac
import uuid

from src.api.core.logger_config import get_logger
from src.api.cache.cache_manager import CacheManager
from src.api.monitoring.observability import trace

logger = get_logger(__name__)


class WebhookEvent(str, Enum):
    """Webhook 事件類型"""

    JOB_STARTED = "job.started"
    JOB_PROGRESS = "job.progress"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_CANCELLED = "job.cancelled"
    SYSTEM_ERROR = "system.error"
    ANALYSIS_READY = "analysis.ready"


class WebhookStatus(str, Enum):
    """Webhook 發送狀態"""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class WebhookConfig:
    """Webhook 配置"""

    url: str
    secret: Optional[str] = None
    events: List[WebhookEvent] = None
    headers: Dict[str, str] = None
    timeout: int = 30  # 秒
    retry_count: int = 3
    retry_delay: int = 5  # 秒
    active: bool = True

    def __post_init__(self):
        if self.events is None:
            self.events = list(WebhookEvent)
        if self.headers is None:
            self.headers = {}


@dataclass
class WebhookPayload:
    """Webhook 負載資料"""

    event: WebhookEvent
    timestamp: datetime
    data: Dict[str, Any]
    job_id: Optional[str] = None
    video_id: Optional[str] = None
    webhook_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            "event": self.event.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "job_id": self.job_id,
            "video_id": self.video_id,
            "webhook_id": self.webhook_id,
        }


@dataclass
class WebhookDelivery:
    """Webhook 發送記錄"""

    delivery_id: str
    webhook_config: WebhookConfig
    payload: WebhookPayload
    status: WebhookStatus
    attempts: int = 0
    last_attempt: Optional[datetime] = None
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)


class WebhookManager:
    """
    Webhook 管理器

    功能：
    1. 註冊和管理 Webhook 配置
    2. 異步發送 Webhook 通知
    3. 重試機制和錯誤處理
    4. 簽名驗證和安全性
    5. 發送記錄和監控
    """

    def __init__(self):
        """初始化 Webhook 管理器"""
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.cache = CacheManager()
        self.pending_deliveries: Dict[str, WebhookDelivery] = {}
        self._session: Optional[aiohttp.ClientSession] = None

        logger.info("WebhookManager initialized")

    async def _get_session(self) -> aiohttp.ClientSession:
        """獲取 HTTP 客戶端 session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60),
                headers={
                    "User-Agent": "TrailTag-Webhooks/1.0",
                    "Content-Type": "application/json",
                },
            )
        return self._session

    def register_webhook(self, webhook_id: str, config: WebhookConfig) -> None:
        """
        註冊 Webhook

        Args:
            webhook_id: Webhook 唯一標識符
            config: Webhook 配置
        """
        # 驗證 URL
        parsed_url = urlparse(config.url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError(f"Invalid webhook URL: {config.url}")

        self.webhooks[webhook_id] = config
        logger.info(f"Registered webhook {webhook_id} for URL {config.url}")

        # 存儲到快取
        try:
            cache_key = f"webhook:{webhook_id}"
            self.cache.set(cache_key, asdict(config))
        except Exception as e:
            logger.error(f"Failed to cache webhook config {webhook_id}: {e}")

    def unregister_webhook(self, webhook_id: str) -> bool:
        """
        取消註冊 Webhook

        Args:
            webhook_id: Webhook 標識符

        Returns:
            bool: 是否成功取消註冊
        """
        if webhook_id in self.webhooks:
            del self.webhooks[webhook_id]

            # 從快取中移除
            try:
                cache_key = f"webhook:{webhook_id}"
                self.cache.delete(cache_key)
            except Exception as e:
                logger.error(f"Failed to remove webhook from cache {webhook_id}: {e}")

            logger.info(f"Unregistered webhook {webhook_id}")
            return True
        return False

    def get_webhook(self, webhook_id: str) -> Optional[WebhookConfig]:
        """
        獲取 Webhook 配置

        Args:
            webhook_id: Webhook 標識符

        Returns:
            WebhookConfig: Webhook 配置，如果不存在返回 None
        """
        return self.webhooks.get(webhook_id)

    def list_webhooks(self) -> Dict[str, WebhookConfig]:
        """
        列出所有 Webhook 配置

        Returns:
            Dict[str, WebhookConfig]: 所有 Webhook 配置
        """
        return self.webhooks.copy()

    def _generate_signature(self, payload: str, secret: str) -> str:
        """
        生成 Webhook 簽名

        Args:
            payload: 負載字符串
            secret: 密鑰

        Returns:
            str: HMAC-SHA256 簽名
        """
        signature = hmac.new(
            secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"

    @trace("webhook.trigger_event")
    async def trigger_event(
        self,
        event: WebhookEvent,
        data: Dict[str, Any],
        job_id: Optional[str] = None,
        video_id: Optional[str] = None,
    ) -> List[str]:
        """
        觸發 Webhook 事件

        Args:
            event: 事件類型
            data: 事件資料
            job_id: 任務ID（可選）
            video_id: 影片ID（可選）

        Returns:
            List[str]: 發送的 delivery ID 列表
        """
        if not self.webhooks:
            logger.debug(f"No webhooks registered, skipping event {event.value}")
            return []

        payload = WebhookPayload(
            event=event,
            timestamp=datetime.now(timezone.utc),
            data=data,
            job_id=job_id,
            video_id=video_id,
        )

        delivery_ids = []

        # 發送到所有符合條件的 Webhook
        for webhook_id, config in self.webhooks.items():
            if not config.active or event not in config.events:
                continue

            payload.webhook_id = webhook_id
            delivery_id = await self._send_webhook(webhook_id, config, payload)
            if delivery_id:
                delivery_ids.append(delivery_id)

        logger.info(f"Triggered event {event.value} to {len(delivery_ids)} webhooks")
        return delivery_ids

    async def _send_webhook(
        self, webhook_id: str, config: WebhookConfig, payload: WebhookPayload
    ) -> Optional[str]:
        """
        發送單個 Webhook

        Args:
            webhook_id: Webhook ID
            config: Webhook 配置
            payload: 負載資料

        Returns:
            Optional[str]: delivery ID，如果發送失敗返回 None
        """
        delivery_id = str(uuid.uuid4())
        delivery = WebhookDelivery(
            delivery_id=delivery_id,
            webhook_config=config,
            payload=payload,
            status=WebhookStatus.PENDING,
        )

        self.pending_deliveries[delivery_id] = delivery

        # 異步發送
        asyncio.create_task(self._deliver_webhook(delivery))

        return delivery_id

    async def _deliver_webhook(self, delivery: WebhookDelivery) -> None:
        """
        實際發送 Webhook 的方法

        Args:
            delivery: 發送記錄
        """
        config = delivery.webhook_config
        payload = delivery.payload

        for attempt in range(1, config.retry_count + 2):  # +1 for initial attempt
            delivery.attempts = attempt
            delivery.last_attempt = datetime.now(timezone.utc)

            try:
                # 準備請求資料
                payload_json = json.dumps(payload.to_dict())
                headers = config.headers.copy()

                # 添加簽名（如果有密鑰）
                if config.secret:
                    signature = self._generate_signature(payload_json, config.secret)
                    headers["X-Webhook-Signature"] = signature

                # 添加標準標頭
                headers.update(
                    {
                        "X-Webhook-Event": payload.event.value,
                        "X-Webhook-Delivery": delivery.delivery_id,
                        "X-Webhook-Timestamp": str(int(payload.timestamp.timestamp())),
                    }
                )

                # 發送請求
                session = await self._get_session()
                async with session.post(
                    config.url,
                    data=payload_json,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=config.timeout),
                ) as response:
                    delivery.response_status = response.status
                    delivery.response_body = await response.text()

                    if 200 <= response.status < 300:
                        delivery.status = WebhookStatus.SENT
                        logger.info(
                            f"Webhook {delivery.delivery_id} sent successfully (attempt {attempt})"
                        )
                        break
                    else:
                        logger.warning(
                            f"Webhook {delivery.delivery_id} failed with status {response.status} (attempt {attempt})"
                        )

            except asyncio.TimeoutError:
                error_msg = f"Timeout after {config.timeout} seconds"
                delivery.error_message = error_msg
                logger.warning(
                    f"Webhook {delivery.delivery_id} timeout (attempt {attempt}): {error_msg}"
                )

            except Exception as e:
                error_msg = str(e)
                delivery.error_message = error_msg
                logger.warning(
                    f"Webhook {delivery.delivery_id} error (attempt {attempt}): {error_msg}"
                )

            # 如果還有重試機會，等待後重試
            if attempt <= config.retry_count:
                delivery.status = WebhookStatus.RETRYING
                await asyncio.sleep(config.retry_delay)
            else:
                delivery.status = WebhookStatus.FAILED
                logger.error(
                    f"Webhook {delivery.delivery_id} failed after {attempt} attempts"
                )

        # 存儲發送記錄
        await self._store_delivery_record(delivery)

        # 清理記憶體
        if delivery.delivery_id in self.pending_deliveries:
            del self.pending_deliveries[delivery.delivery_id]

    async def _store_delivery_record(self, delivery: WebhookDelivery) -> None:
        """存儲發送記錄到快取"""
        try:
            cache_key = f"webhook_delivery:{delivery.delivery_id}"
            record = {
                "delivery_id": delivery.delivery_id,
                "webhook_url": delivery.webhook_config.url,
                "event": delivery.payload.event.value,
                "status": delivery.status.value,
                "attempts": delivery.attempts,
                "last_attempt": (
                    delivery.last_attempt.isoformat() if delivery.last_attempt else None
                ),
                "response_status": delivery.response_status,
                "error_message": delivery.error_message,
                "created_at": delivery.created_at.isoformat(),
                "job_id": delivery.payload.job_id,
                "video_id": delivery.payload.video_id,
            }
            self.cache.set(cache_key, record, expire=86400 * 7)  # 保存 7 天
        except Exception as e:
            logger.error(
                f"Failed to store webhook delivery record {delivery.delivery_id}: {e}"
            )

    @trace("webhook.get_delivery_status")
    async def get_delivery_status(self, delivery_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取發送狀態

        Args:
            delivery_id: 發送ID

        Returns:
            Dict[str, Any]: 發送狀態信息
        """
        # 先檢查記憶體中的記錄
        if delivery_id in self.pending_deliveries:
            delivery = self.pending_deliveries[delivery_id]
            return {
                "delivery_id": delivery.delivery_id,
                "status": delivery.status.value,
                "attempts": delivery.attempts,
                "last_attempt": (
                    delivery.last_attempt.isoformat() if delivery.last_attempt else None
                ),
                "response_status": delivery.response_status,
                "error_message": delivery.error_message,
            }

        # 從快取中獲取
        try:
            cache_key = f"webhook_delivery:{delivery_id}"
            record = self.cache.get(cache_key)
            return record
        except Exception as e:
            logger.error(f"Failed to get delivery status {delivery_id}: {e}")
            return None

    @trace("webhook.get_delivery_history")
    async def get_delivery_history(
        self,
        webhook_id: Optional[str] = None,
        event: Optional[WebhookEvent] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        獲取發送歷史記錄

        Args:
            webhook_id: Webhook ID（可選）
            event: 事件類型（可選）
            limit: 返回數量限制

        Returns:
            List[Dict[str, Any]]: 發送歷史記錄
        """
        # 這裡應該實現從快取中查詢歷史記錄的邏輯
        # 暫時返回空列表
        return []

    async def shutdown(self) -> None:
        """關閉 Webhook 管理器"""
        logger.info("Shutting down WebhookManager")

        if self._session and not self._session.closed:
            await self._session.close()

        logger.info("WebhookManager shutdown completed")


# 全域 Webhook 管理器實例
_global_webhook_manager: Optional[WebhookManager] = None


def get_webhook_manager() -> WebhookManager:
    """
    獲取全域 Webhook 管理器實例

    Returns:
        WebhookManager: 全域管理器實例
    """
    global _global_webhook_manager

    if _global_webhook_manager is None:
        _global_webhook_manager = WebhookManager()
        logger.info("Global WebhookManager instance created")

    return _global_webhook_manager


async def shutdown_webhook_manager() -> None:
    """關閉全域 Webhook 管理器"""
    global _global_webhook_manager

    if _global_webhook_manager is not None:
        await _global_webhook_manager.shutdown()
        _global_webhook_manager = None
        logger.info("Global WebhookManager shutdown")


# 便利函數
async def trigger_webhook_event(
    event: WebhookEvent,
    data: Dict[str, Any],
    job_id: Optional[str] = None,
    video_id: Optional[str] = None,
) -> List[str]:
    """
    觸發 Webhook 事件的便利函數

    Args:
        event: 事件類型
        data: 事件資料
        job_id: 任務ID（可選）
        video_id: 影片ID（可選）

    Returns:
        List[str]: 發送的 delivery ID 列表
    """
    manager = get_webhook_manager()
    return await manager.trigger_event(event, data, job_id, video_id)
