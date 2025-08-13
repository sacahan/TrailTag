"""
TrailTag API 主應用模組
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import logging
import time
import sys
import os

# 禁用 OpenTelemetry SDK
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"

# 確保模組可以被找到
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 從專案內部模組引入

from .routes import router as videos_router
from .sse import router as sse_router
from .cache_manager import CacheProvider


# 設定 logger
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}',
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)
logger = logging.getLogger("trailtag-api")

# 全域快取狀態
cache = CacheProvider()

# 創建 FastAPI 應用
app = FastAPI(
    title="TrailTag API",
    description="YouTube 旅遊影片地圖化 API 服務",
    version="0.1.0",
)

# 設定 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["chrome-extension://*", "http://localhost:*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊路由器
app.include_router(videos_router)
app.include_router(sse_router)

# 基本健康檢查


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """基本健康檢查端點"""
    return {
        "status": "ok",
        "timestamp": time.time(),
        "version": app.version,
        "degraded": cache.is_degraded(),
    }
