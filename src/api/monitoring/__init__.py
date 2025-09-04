"""
API 監控與可觀測性模組 (API Monitoring & Observability)

此模組包含 API 應用程式的監控與可觀測性組件：
- metrics.py: 性能指標收集器
  * 收集系統運行指標 (CPU、記憶體、響應時間等)
  * 追蹤 API 請求統計與錯誤率
  * 提供 Prometheus 格式的指標匯出

- observability.py: 可觀測性整合
  * Langtrace 分散式追蹤整合
  * 請求鏈路追蹤與性能分析
  * CrewAI 代理程式執行可視化

監控系統提供完整的運行狀態洞察，
幫助識別性能瓶頸和系統問題。
"""

from .metrics import metrics
from .observability import observability

__all__ = [
    "metrics",
    "observability",
]
