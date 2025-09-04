"""
API 路由模組 (API Routes)

此模組包含 FastAPI 應用程式的所有路由定義：
- main_routes.py: 主要 API 端點與路由處理器
  * POST /api/analyze - 提交影片分析任務
  * GET /api/status/{task_id} - 查詢任務狀態與進度
  * GET /api/results/{task_id} - 下載 GeoJSON 分析結果
  * GET /api/map/{task_id}.geojson - 直接存取地圖資料
  * GET /health - 服務健康檢查
  * GET /metrics - 系統性能指標

路由處理器負責請求驗證、業務邏輯呼叫、
回應格式化等 HTTP 層面的處理工作。
"""

from .main_routes import main_routes

__all__ = [
    "main_routes",
]
