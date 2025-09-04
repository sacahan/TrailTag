"""
TrailTag Observability 模組 - Langtrace SDK 整合
提供性能監控、追蹤和可觀測性功能
"""

import os
import time
from contextlib import contextmanager
from typing import Dict, Any
from functools import wraps
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ObservabilityManager:
    """可觀測性管理器 - 負責初始化和管理 Langtrace SDK"""

    def __init__(self):
        self.is_enabled = os.getenv("LANGTRACE_ENABLED", "false").lower() == "true"
        self.api_key = os.getenv("LANGTRACE_API_KEY")
        self.project_name = os.getenv("LANGTRACE_PROJECT_NAME", "TrailTag")
        self.langtrace = None
        self._metrics_store = {}
        self._initialize_langtrace()

    def _initialize_langtrace(self):
        """初始化 Langtrace SDK"""
        if not self.is_enabled:
            logger.info("Langtrace 追蹤已停用")
            return

        if not self.api_key:
            logger.warning("LANGTRACE_API_KEY 未設定，將使用本地追蹤模式")

        try:
            from langtrace_python_sdk import langtrace

            # 初始化 Langtrace
            langtrace.init(
                api_key=self.api_key,
                batch=True,
                disable_instrumentations={
                    "openai": False,
                    "requests": True,
                    "redis": False,
                    "fastapi": False,
                },
            )

            self.langtrace = langtrace
            logger.info(f"Langtrace 已成功初始化 - 項目: {self.project_name}")

        except ImportError:
            logger.error("Langtrace SDK 未安裝，請執行: uv add langtrace-python-sdk")
            self.is_enabled = False
        except Exception as e:
            logger.error(f"Langtrace 初始化失敗: {e}")
            self.is_enabled = False

    def trace_function(self, name: str = None, metadata: Dict[str, Any] = None):
        """函數追蹤裝飾器"""

        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                if not self.is_enabled or not self.langtrace:
                    return await func(*args, **kwargs)

                trace_name = name or f"{func.__module__}.{func.__name__}"
                start_time = time.time()

                try:
                    # 使用 Langtrace 追蹤
                    with self.langtrace.trace(name=trace_name, metadata=metadata or {}):
                        result = await func(*args, **kwargs)

                    # 記錄成功指標
                    execution_time = time.time() - start_time
                    self._record_metric(trace_name, "success", execution_time)

                    return result

                except Exception as e:
                    # 記錄錯誤指標
                    execution_time = time.time() - start_time
                    self._record_metric(
                        trace_name, "error", execution_time, error=str(e)
                    )
                    raise

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                if not self.is_enabled or not self.langtrace:
                    return func(*args, **kwargs)

                trace_name = name or f"{func.__module__}.{func.__name__}"
                start_time = time.time()

                try:
                    # 使用 Langtrace 追蹤
                    with self.langtrace.trace(name=trace_name, metadata=metadata or {}):
                        result = func(*args, **kwargs)

                    # 記錄成功指標
                    execution_time = time.time() - start_time
                    self._record_metric(trace_name, "success", execution_time)

                    return result

                except Exception as e:
                    # 記錄錯誤指標
                    execution_time = time.time() - start_time
                    self._record_metric(
                        trace_name, "error", execution_time, error=str(e)
                    )
                    raise

            # 返回適當的包裝器
            import asyncio

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper

        return decorator

    @contextmanager
    def trace_span(self, name: str, metadata: Dict[str, Any] = None):
        """上下文管理器形式的追蹤"""
        if not self.is_enabled or not self.langtrace:
            yield
            return

        start_time = time.time()

        try:
            with self.langtrace.trace(name=name, metadata=metadata or {}):
                yield

            # 記錄成功指標
            execution_time = time.time() - start_time
            self._record_metric(name, "success", execution_time)

        except Exception as e:
            # 記錄錯誤指標
            execution_time = time.time() - start_time
            self._record_metric(name, "error", execution_time, error=str(e))
            raise

    def _record_metric(self, name: str, status: str, execution_time: float, **kwargs):
        """記錄性能指標到內部存儲"""
        timestamp = datetime.now(timezone.utc).isoformat()

        if name not in self._metrics_store:
            self._metrics_store[name] = {
                "total_calls": 0,
                "success_calls": 0,
                "error_calls": 0,
                "total_time": 0.0,
                "avg_time": 0.0,
                "min_time": float("inf"),
                "max_time": 0.0,
                "last_called": timestamp,
                "errors": [],
            }

        metric = self._metrics_store[name]
        metric["total_calls"] += 1
        metric["total_time"] += execution_time
        metric["avg_time"] = metric["total_time"] / metric["total_calls"]
        metric["min_time"] = min(metric["min_time"], execution_time)
        metric["max_time"] = max(metric["max_time"], execution_time)
        metric["last_called"] = timestamp

        if status == "success":
            metric["success_calls"] += 1
        else:
            metric["error_calls"] += 1
            if "error" in kwargs:
                metric["errors"].append(
                    {
                        "timestamp": timestamp,
                        "error": kwargs["error"],
                        "execution_time": execution_time,
                    }
                )
                # 只保留最近 10 個錯誤
                metric["errors"] = metric["errors"][-10:]

    def get_metrics_summary(self) -> Dict[str, Any]:
        """獲取性能指標摘要"""
        return {
            "enabled": self.is_enabled,
            "project_name": self.project_name,
            "metrics": dict(self._metrics_store),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def record_custom_metric(
        self, name: str, value: float, metadata: Dict[str, Any] = None
    ):
        """記錄自定義指標"""
        if not self.is_enabled or not self.langtrace:
            return

        try:
            self.langtrace.log(name=name, value=value, metadata=metadata or {})
        except Exception as e:
            logger.error(f"記錄自定義指標失敗: {e}")


# 全域觀測性管理器實例
observability = ObservabilityManager()


# 便利函數
def trace(name: str = None, metadata: Dict[str, Any] = None):
    """函數追蹤裝飾器 - 便利包裝"""
    return observability.trace_function(name=name, metadata=metadata)


def trace_span(name: str, metadata: Dict[str, Any] = None):
    """追蹤 span 上下文管理器 - 便利包裝"""
    return observability.trace_span(name=name, metadata=metadata)


def record_metric(name: str, value: float, metadata: Dict[str, Any] = None):
    """記錄自定義指標 - 便利包裝"""
    return observability.record_custom_metric(name=name, value=value, metadata=metadata)


def get_metrics():
    """獲取指標摘要 - 便利包裝"""
    return observability.get_metrics_summary()
