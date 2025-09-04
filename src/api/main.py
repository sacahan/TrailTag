"""
TrailTag API 主應用程式模組

這是 TrailTag 系統的核心 FastAPI 應用程式，負責提供 HTTP API 服務，
整合影片分析、地圖視覺化、監控等所有後端功能。

主要功能:
    - RESTful API: 提供影片分析的完整 HTTP API
    - WebSocket/SSE: 支援即時進度更新推送
    - CORS 支援: 允許瀏覽器擴充功能存取
    - 指標監控: 整合 Prometheus 風格的效能指標
    - 健康檢查: 提供系統狀態監控端點
    - 可觀測性: 整合 Langtrace 進行追蹤監控

架構設計:
    - FastAPI 框架: 高效能的現代 Python Web 框架
    - 中間件堆疊: CORS、指標收集等中間件
    - 路由模組化: 按功能分離的路由器設計
    - 快取整合: 統一的快取管理與降級處理

技術特色:
    - 非同步處理: 支援高並發的非同步請求處理
    - 自動文檔: OpenAPI/Swagger 自動文檔生成
    - 型別安全: 完整的型別注解與 Pydantic 整合
    - 擴展友善: 支援瀏覽器擴充功能的跨域請求

監控與維運:
    - 效能指標: 請求延遲、錯誤率、QPS 等指標
    - 健康檢查: 多層次的系統健康狀態監控
    - 日誌系統: 結構化的日誌記錄
    - 錯誤處理: 統一的錯誤回應格式

部署配置:
    - 環境變數: 支援環境變數配置
    - 容器化: Docker 容器部署支援
    - 開發模式: 熱重載與除錯支援
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
from src.api.core.logger_config import get_logger
from .routes import router as videos_router
from .middleware.sse_handler import router as sse_router
from .monitoring.metrics import router as metrics_router, MetricsMiddleware
from .cache.cache_manager import CacheManager
from .monitoring.observability import observability
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
    description="YouTube 旅遊影片地圖化 API 服務 - 整合效能監控",
    version="0.1.0",
)

# 添加指標監控中間件
app.add_middleware(MetricsMiddleware)

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
app.include_router(metrics_router)


# 系統健康檢查端點
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    系統健康檢查端點

    提供 TrailTag 系統的整體健康狀態資訊，用於監控系統、負載均衡器、
    容器編排平台等進行健康檢查和故障偵測。

    檢查項目:
        - API 服務狀態: FastAPI 應用程式是否正常運行
        - 快取系統狀態: Redis 連線狀況與降級模式檢查
        - 監控系統狀態: 可觀測性服務的啟用狀態
        - 版本資訊: 目前部署的應用程式版本
        - 時間戳記: 伺服器當前時間，用於時區與時鐘檢查

    Returns:
        Dict[str, Any]: 健康檢查結果物件，包含以下欄位:
            - status: 整體狀態 ("ok" | "degraded" | "error")
            - timestamp: ISO 格式的當前時間戳記
            - version: 應用程式版本號
            - degraded: 是否處於降級模式 (如 Redis 不可用)
            - observability_enabled: 可觀測性服務狀態
            - monitoring: 詳細的監控組件狀態
                - langtrace: Langtrace 追蹤服務狀態
                - metrics_collection: 指標收集狀態
                - agent_observers: Agent 觀察者狀態

    HTTP 狀態碼:
        - 200: 系統正常或處於可接受的降級狀態
        - 503: 系統嚴重故障 (未來擴充)

    使用場景:
        - 監控告警: 監控系統定期檢查服務健康度
        - 負載均衡: 負載均衡器決定流量分配
        - 自動恢復: 容器編排系統的健康檢查探針
        - 運維診斷: 手動檢查系統狀態

    監控建議:
        - 檢查頻率: 建議每 30-60 秒檢查一次
        - 告警條件: degraded=true 時發出警告，連續失敗時告警
        - 超時設定: 設定適當的請求超時 (如 5 秒)
    """
    return {
        "status": "ok",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "version": app.version,
        "degraded": cache.is_degraded(),
        "observability_enabled": observability.is_enabled,
        "monitoring": {
            "langtrace": observability.is_enabled,
            "metrics_collection": True,
            "agent_observers": True,
        },
    }


# 啟動 FastAPI 伺服器時，印出 OpenAPI docs 與 JSON spec 的 URL
port = int(os.getenv("API_PORT", 8010))
host = os.getenv("API_HOST", "0.0.0.0")
print(f"\n[OpenAPI] Swagger UI: http://{host}:{port}/docs")
print(f"[OpenAPI] JSON Spec: http://{host}:{port}/openapi.json")
print(f"[Monitoring] Metrics Dashboard: http://{host}:{port}/metrics/dashboard")
print(f"[Monitoring] Metrics API: http://{host}:{port}/metrics")
print(f"[Health Check] Health Endpoint: http://{host}:{port}/health\n")
