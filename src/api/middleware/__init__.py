"""
API 中間件模組 (API Middleware)

此模組包含 FastAPI 應用程式的中間件與處理器：
- sse_handler.py: Server-Sent Events (SSE) 處理器
  * 提供即時進度更新與事件推送功能
  * 支援長連線與自動重連機制
  * 用於向前端即時傳遞任務處理進度

中間件負責處理 HTTP 請求與回應之間的中間邏輯，
包括身份驗證、CORS 處理、即時通訊等功能。
"""

from .sse_handler import sse_handler

__all__ = [
    "sse_handler",
]
