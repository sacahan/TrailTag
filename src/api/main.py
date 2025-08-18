"""
TrailTag API 主應用模組
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
from src.api.logger_config import get_logger
from .routes import router as videos_router
from .sse import router as sse_router
from .cache_manager import CacheManager
import time
import sys
import os

logger = get_logger(__name__)

# 禁用 OpenTelemetry SDK
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"

# 確保模組可以被找到
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 全域快取狀態
cache = CacheManager()

# 創建 FastAPI 應用
app = FastAPI(
    title="TrailTag API",
    description="YouTube 旅遊影片地圖化 API 服務",
    version="0.1.0",
)

# 設定 CORS
app.add_middleware(
    CORSMiddleware,
    # 明確列出開發時常用的本機來源
    allow_origins=["*"],
    # 允許 chrome-extension://<extension-id> 的 origin（例如 chrome-extension://apkdjmojbemmceiaalnlfocjlkcbphnn）
    # 使用正規表達式以覆蓋各種 extension id。若需限制單一 id，可改為完整字串清單。
    allow_origin_regex=r"^chrome-extension://[a-p0-9]+$",
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
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "version": app.version,
        "degraded": cache.is_degraded(),
    }


# 啟動 FastAPI 伺服器時，印出 OpenAPI docs 與 JSON spec 的 URL
port = int(os.getenv("API_PORT", 8010))
host = os.getenv("API_HOST", "0.0.0.0")
print(f"\n[OpenAPI] Swagger UI: http://{host}:{port}/docs")
print(f"[OpenAPI] JSON Spec: http://{host}:{port}/openapi.json\n")
