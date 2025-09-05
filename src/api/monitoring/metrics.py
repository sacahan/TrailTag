"""
TrailTag Metrics API 模組
提供效能指標監控和儀表板功能
"""

import time
import psutil
from datetime import datetime, timezone
from typing import Dict, List
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from src.api.core.logger_config import get_logger
from src.api.monitoring.observability import get_metrics as get_observability_metrics

# CacheManager 將在需要時動態匯入以避免循環依賴

logger = get_logger(__name__)

# 創建路由器
router = APIRouter()


class SystemMetrics(BaseModel):
    """系統指標模型"""

    timestamp: str
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_usage_percent: float
    network_connections: int


class APIMetrics(BaseModel):
    """API 指標模型"""

    endpoint: str
    method: str
    total_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    error_rate: float
    last_request: str


class MetricsCollector:
    """指標收集器 - 收集系統和應用指標"""

    def __init__(self):
        self.api_metrics: Dict[str, Dict] = {}
        self.system_metrics_history: List[SystemMetrics] = []
        self.max_history_size = 100  # 保留最近100個系統指標記錄

    def record_api_request(
        self, endpoint: str, method: str, response_time: float, status_code: int
    ):
        """記錄 API 請求指標"""
        key = f"{method}:{endpoint}"
        timestamp = datetime.now(timezone.utc).isoformat()

        if key not in self.api_metrics:
            self.api_metrics[key] = {
                "endpoint": endpoint,
                "method": method,
                "total_requests": 0,
                "total_response_time": 0.0,
                "min_response_time": float("inf"),
                "max_response_time": 0.0,
                "error_count": 0,
                "last_request": timestamp,
                "response_times": [],
            }

        metrics = self.api_metrics[key]
        metrics["total_requests"] += 1
        metrics["total_response_time"] += response_time
        metrics["min_response_time"] = min(metrics["min_response_time"], response_time)
        metrics["max_response_time"] = max(metrics["max_response_time"], response_time)
        metrics["last_request"] = timestamp

        # 記錄錯誤
        if status_code >= 400:
            metrics["error_count"] += 1

        # 保留最近的響應時間用於計算
        metrics["response_times"].append(response_time)
        if len(metrics["response_times"]) > 1000:  # 只保留最近1000個
            metrics["response_times"] = metrics["response_times"][-1000:]

    def get_system_metrics(self) -> SystemMetrics:
        """獲取當前系統指標"""
        timestamp = datetime.now(timezone.utc).isoformat()

        # CPU 使用率
        cpu_percent = psutil.cpu_percent(interval=1)

        # 記憶體使用情況
        memory = psutil.virtual_memory()

        # 磁碟使用情況
        disk = psutil.disk_usage("/")

        # 網路連接數
        try:
            network_connections = len(psutil.net_connections())
        except (psutil.AccessDenied, OSError):
            network_connections = -1  # 權限不足時返回-1

        metrics = SystemMetrics(
            timestamp=timestamp,
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_mb=memory.used / 1024 / 1024,
            memory_total_mb=memory.total / 1024 / 1024,
            disk_usage_percent=disk.percent,
            network_connections=network_connections,
        )

        # 添加到歷史記錄
        self.system_metrics_history.append(metrics)
        if len(self.system_metrics_history) > self.max_history_size:
            self.system_metrics_history.pop(0)

        return metrics

    def get_api_metrics_summary(self) -> List[APIMetrics]:
        """獲取 API 指標摘要"""
        result = []

        for key, metrics in self.api_metrics.items():
            if metrics["total_requests"] > 0:
                avg_response_time = (
                    metrics["total_response_time"] / metrics["total_requests"]
                )
                error_rate = (metrics["error_count"] / metrics["total_requests"]) * 100
            else:
                avg_response_time = 0.0
                error_rate = 0.0

            api_metric = APIMetrics(
                endpoint=metrics["endpoint"],
                method=metrics["method"],
                total_requests=metrics["total_requests"],
                avg_response_time=avg_response_time,
                min_response_time=(
                    metrics["min_response_time"]
                    if metrics["min_response_time"] != float("inf")
                    else 0.0
                ),
                max_response_time=metrics["max_response_time"],
                error_rate=error_rate,
                last_request=metrics["last_request"],
            )
            result.append(api_metric)

        return sorted(result, key=lambda x: x.total_requests, reverse=True)


# 全域指標收集器
metrics_collector = MetricsCollector()


class MetricsMiddleware:
    """FastAPI 中間件 - 自動收集 API 指標"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 開始計時
        start_time = time.time()

        # 提取請求信息
        method = scope["method"]
        path = scope["path"]

        # 排除不需要監控的端點
        if (
            path.startswith("/docs")
            or path.startswith("/openapi.json")
            or path.startswith("/redoc")
        ):
            await self.app(scope, receive, send)
            return

        status_code = 200

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            status_code = 500
            raise
        finally:
            # 記錄指標
            response_time = time.time() - start_time
            metrics_collector.record_api_request(
                path, method, response_time, status_code
            )


@router.get("/metrics", response_class=JSONResponse)
async def get_metrics_endpoint():
    """獲取完整的系統指標 JSON 數據"""
    try:
        # 收集各種指標
        system_metrics = metrics_collector.get_system_metrics()
        api_metrics = metrics_collector.get_api_metrics_summary()
        observability_metrics = get_observability_metrics()

        # 獲取 CrewAI 觀察者指標
        from src.trailtag.core.observers import get_global_observer

        observer = get_global_observer()
        crew_metrics = observer.get_performance_summary()

        # 獲取快取狀態
        from src.api.cache.cache_manager import CacheManager

        cache = CacheManager()
        cache_status = {
            "is_degraded": cache.is_degraded(),
            "cache_type": "Redis" if not cache.is_degraded() else "Memory",
        }

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system": system_metrics.model_dump(),
            "api_endpoints": [metric.model_dump() for metric in api_metrics],
            "observability": observability_metrics,
            "crew_ai": crew_metrics,
            "cache": cache_status,
            "system_history": [
                m.model_dump() for m in metrics_collector.system_metrics_history[-10:]
            ],  # 最近10個記錄
        }

    except Exception as e:
        logger.error(f"獲取指標數據失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取指標數據失敗: {str(e)}")


@router.get("/metrics/dashboard", response_class=HTMLResponse)
async def get_metrics_dashboard():
    """獲取效能指標儀表板 HTML 頁面"""
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-TW">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TrailTag 效能監控儀表板</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            .header {
                background: white;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .metrics-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-bottom: 20px;
            }
            .metric-card {
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .metric-title {
                font-size: 18px;
                font-weight: 600;
                margin-bottom: 15px;
                color: #333;
            }
            .metric-value {
                font-size: 24px;
                font-weight: 700;
                color: #007bff;
            }
            .metric-unit {
                font-size: 14px;
                color: #666;
                margin-left: 5px;
            }
            .chart-container {
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }
            .api-table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }
            .api-table th,
            .api-table td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #eee;
            }
            .api-table th {
                background-color: #f8f9fa;
                font-weight: 600;
            }
            .status-indicator {
                display: inline-block;
                width: 12px;
                height: 12px;
                border-radius: 50%;
                margin-right: 8px;
            }
            .status-good { background-color: #28a745; }
            .status-warning { background-color: #ffc107; }
            .status-error { background-color: #dc3545; }
            .refresh-btn {
                background: #007bff;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
            }
            .refresh-btn:hover {
                background: #0056b3;
            }
            .loading {
                opacity: 0.6;
                pointer-events: none;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>TrailTag 效能監控儀表板</h1>
                <button class="refresh-btn" onclick="refreshMetrics()">重新整理</button>
                <span id="lastUpdate" style="margin-left: 20px; color: #666;"></span>
            </div>

            <div class="metrics-grid" id="systemMetrics">
                <!-- 系統指標將在這裡動態載入 -->
            </div>

            <div class="chart-container">
                <h2>系統資源使用趨勢</h2>
                <canvas id="systemChart" width="400" height="100"></canvas>
            </div>

            <div class="chart-container">
                <h2>API 端點效能</h2>
                <table class="api-table" id="apiTable">
                    <thead>
                        <tr>
                            <th>端點</th>
                            <th>方法</th>
                            <th>總請求數</th>
                            <th>平均響應時間</th>
                            <th>錯誤率</th>
                            <th>狀態</th>
                        </tr>
                    </thead>
                    <tbody>
                        <!-- API 指標將在這裡動態載入 -->
                    </tbody>
                </table>
            </div>

            <div class="chart-container">
                <h2>CrewAI Agent 執行統計</h2>
                <div id="crewMetrics">
                    <!-- CrewAI 指標將在這裡動態載入 -->
                </div>
            </div>
        </div>

        <script>
            let systemChart;
            let refreshInterval;

            async function fetchMetrics() {
                try {
                    const response = await fetch('/metrics');
                    return await response.json();
                } catch (error) {
                    console.error('獲取指標失敗:', error);
                    return null;
                }
            }

            function updateSystemMetrics(data) {
                const container = document.getElementById('systemMetrics');
                const system = data.system;

                container.innerHTML = `
                    <div class="metric-card">
                        <div class="metric-title">CPU 使用率</div>
                        <div class="metric-value">${system.cpu_percent.toFixed(1)}<span class="metric-unit">%</span></div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-title">記憶體使用率</div>
                        <div class="metric-value">${system.memory_percent.toFixed(1)}<span class="metric-unit">%</span></div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-title">記憶體使用量</div>
                        <div class="metric-value">${(system.memory_used_mb).toFixed(0)}<span class="metric-unit">MB</span></div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-title">磁碟使用率</div>
                        <div class="metric-value">${system.disk_usage_percent.toFixed(1)}<span class="metric-unit">%</span></div>
                    </div>
                `;
            }

            function updateChart(data) {
                const ctx = document.getElementById('systemChart').getContext('2d');
                const history = data.system_history || [];

                if (systemChart) {
                    systemChart.destroy();
                }

                systemChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: history.map((_, index) => `-${history.length - index - 1}m`),
                        datasets: [
                            {
                                label: 'CPU (%)',
                                data: history.map(h => h.cpu_percent),
                                borderColor: '#007bff',
                                backgroundColor: 'rgba(0, 123, 255, 0.1)',
                                tension: 0.4
                            },
                            {
                                label: 'Memory (%)',
                                data: history.map(h => h.memory_percent),
                                borderColor: '#28a745',
                                backgroundColor: 'rgba(40, 167, 69, 0.1)',
                                tension: 0.4
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 100
                            }
                        }
                    }
                });
            }

            function updateApiTable(data) {
                const tbody = document.querySelector('#apiTable tbody');
                const apis = data.api_endpoints || [];

                tbody.innerHTML = apis.map(api => {
                    const statusClass = api.error_rate > 10 ? 'status-error' :
                                       api.avg_response_time > 2000 ? 'status-warning' : 'status-good';

                    return `
                        <tr>
                            <td>${api.endpoint}</td>
                            <td>${api.method}</td>
                            <td>${api.total_requests}</td>
                            <td>${api.avg_response_time.toFixed(0)}ms</td>
                            <td>${api.error_rate.toFixed(1)}%</td>
                            <td><span class="status-indicator ${statusClass}"></span></td>
                        </tr>
                    `;
                }).join('');
            }

            function updateCrewMetrics(data) {
                const container = document.getElementById('crewMetrics');
                const crew = data.crew_ai || {};

                if (crew.message) {
                    container.innerHTML = `<p>${crew.message}</p>`;
                    return;
                }

                const agents = Object.entries(crew.agent_statistics || {});

                container.innerHTML = `
                    <div class="metrics-grid">
                        <div class="metric-card">
                            <div class="metric-title">總執行次數</div>
                            <div class="metric-value">${crew.total_executions || 0}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-title">總執行時間</div>
                            <div class="metric-value">${(crew.total_duration || 0).toFixed(1)}<span class="metric-unit">秒</span></div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-title">總 Token 使用量</div>
                            <div class="metric-value">${crew.total_tokens?.total || 0}</div>
                        </div>
                    </div>
                    ${agents.length > 0 ? `
                        <h3>Agent 執行統計</h3>
                        <table class="api-table">
                            <thead>
                                <tr>
                                    <th>Agent</th>
                                    <th>執行次數</th>
                                    <th>成功率</th>
                                    <th>平均耗時</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${agents.map(([name, stats]) => `
                                    <tr>
                                        <td>${name}</td>
                                        <td>${stats.total_executions}</td>
                                        <td>${((stats.successful_executions / stats.total_executions) * 100).toFixed(1)}%</td>
                                        <td>${stats.avg_duration.toFixed(1)}s</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    ` : ''}
                `;
            }

            async function refreshMetrics() {
                const container = document.querySelector('.container');
                container.classList.add('loading');

                try {
                    const data = await fetchMetrics();
                    if (data) {
                        updateSystemMetrics(data);
                        updateChart(data);
                        updateApiTable(data);
                        updateCrewMetrics(data);

                        document.getElementById('lastUpdate').textContent =
                            `最後更新: ${new Date().toLocaleString('zh-TW')}`;
                    }
                } finally {
                    container.classList.remove('loading');
                }
            }

            // 初始載入
            refreshMetrics();

            // 設定自動重新整理（每30秒）
            refreshInterval = setInterval(refreshMetrics, 30000);

            // 頁面隱藏時停止重新整理，顯示時重新開始
            document.addEventListener('visibilitychange', function() {
                if (document.hidden) {
                    clearInterval(refreshInterval);
                } else {
                    refreshInterval = setInterval(refreshMetrics, 30000);
                    refreshMetrics();
                }
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.get("/metrics/system")
async def get_system_metrics():
    """獲取系統指標"""
    try:
        metrics = metrics_collector.get_system_metrics()
        return metrics
    except Exception as e:
        logger.error(f"獲取系統指標失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取系統指標失敗: {str(e)}")


@router.get("/metrics/api")
async def get_api_metrics():
    """獲取 API 指標"""
    try:
        metrics = metrics_collector.get_api_metrics_summary()
        return [metric.model_dump() for metric in metrics]
    except Exception as e:
        logger.error(f"獲取 API 指標失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取 API 指標失敗: {str(e)}")


@router.get("/metrics/crew")
async def get_crew_metrics():
    """獲取 CrewAI 指標"""
    try:
        # Import here to avoid circular dependency
        from src.trailtag.core.observers import get_global_observer

        observer = get_global_observer()
        return observer.get_performance_summary()
    except Exception as e:
        logger.error(f"獲取 CrewAI 指標失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取 CrewAI 指標失敗: {str(e)}")


# 導出中間件類別供 main.py 使用
__all__ = ["router", "MetricsMiddleware", "metrics_collector"]
