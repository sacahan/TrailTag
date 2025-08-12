---
post_title: "TrailTag 後端 API 與任務處理計劃"
author1: "TEAM"
post_slug: "backend-plan"
microsoft_alias: "na"
featured_image: ""
categories: [architecture]
tags: [backend, fastapi, crewai, redis, celery, architecture]
ai_note: "此文件由 AI 協助生成，已由人員審閱。"
summary: "將既有 CrewAI 同步流程重構為可快取、可觀測、非同步的 API 服務，涵蓋 FastAPI、任務排程、快取、觀測性與階段 Roadmap。"
post_date: 2025-08-12
---

TrailTag 後端 API 與任務處理計劃
=============================

概述
----

本文件聚焦 TrailTag 後端重構：把目前單一 `main.py` 串行執行的影片→字幕→壓縮→主題/地點→地理編碼流程 API 化，支援非同步、快取、進度推送與觀測性（不再提供 artifacts 下載端點，對外只暴露地點視覺化資料）。

目標與成功指標
---------------

- 提供標準化 REST 端點：提交分析、查詢進度、取得地點視覺化資料。
- 單一影片重複請求 <100ms 回應（快取命中）。
- 90% 影片分析全流程在 60 秒內完成（示範資料集）。
- Geocode 成功率 ≥ 85%，失敗地點可重試。
- 具備結構化日誌與基本指標匯出。

範疇 (In Scope)
---------------

- FastAPI 應用骨架
- 任務隊列與執行（初期 ThreadPool → 後續 Celery+Redis）
- Redis 快取與任務狀態儲存
- SSE 進度回報（phase_update / completed / error / heartbeat）。不再推送 partial locations 或 artifacts。
- 基本重試與錯誤分類
- 指標 / 日誌 / 簡易健康檢查

非範疇 (Out of Scope)
---------------------

- 多租戶 / SaaS 帳務
- OAuth / 使用者管理
- Whisper ASR (Roadmap P2)
- GeoJSON 路線優化 (Roadmap P4)

架構概要
--------

- FastAPI (REST + /health + /metrics)
- 任務執行層：`AnalysisOrchestrator` 封裝現有工具
- 任務排程：`JobDispatcher` (抽象) → `InMemoryDispatcher` → `CeleryDispatcher`
- Redis：
  - Key: `analysis:{video_id}:{strategy_version}` (結果)
  - Key: `job:{job_id}` (狀態 JSON)
  - TTL: 7d (可調)
- Artifacts：內部仍生成（供除錯與後續功能），不提供公開端點；對外僅提供聚合後的 `MapVisualization`（來源於 `models.py`）。

端點設計
--------

| Method | Path | 說明 | 回傳 (核心欄位) |
| ------ | ---- | ---- | --------------- |
| POST | /api/videos/analyze | 提交新分析或命中快取 | job_id, status, cached |
| GET | /api/jobs/{job_id} | 查詢進度 | job_id, status, phase, progress, stats |
| GET | /api/jobs/{job_id}/stream | SSE 事件 | event: phase_update/completed/error/heartbeat |
| GET | /api/videos/{video_id}/locations | 取得地點視覺化資料 (一次性) | MapVisualization (video_id, routes[]) |
| POST | /api/videos/{video_id}/geocode/retry | 局部地點重試 (P1.5) | retried_count |

`MapVisualization` 回傳示例：

```json
{
  "video_id": "abc123",
  "routes": [
    {
      "location": "Taipei 101",
      "coordinates": [121.5645, 25.0339],
      "description": "觀景台夜景",
      "timecode": "00:05:12,000",
      "tags": ["landmark"],
      "marker": "poi"
    }
  ]
}
```

狀態與階段定義
--------------

| Phase | 權重 | 描述 |
| ----- | ---- | ---- |
| metadata | 10 | 下載 metadata + 字幕 |
| compression | 25 | 字幕分段 + 壓縮 |
| summary | 35 | 主題/地點抽取 |
| geocode | 30 | 地點地理編碼與組合 |

Progress = Σ 已完成階段權重 + 當前階段內細分進度。

Job 狀態列舉
-----------

queued / running / partial / failed / done / canceled

資料結構 (概念 JSON)
-------------------

```text
Job {
  job_id: str,
  video_id: str,
  status: str,
  phase: str,
  progress: float,
  created_at: ts,
  updated_at: ts,
  strategy_version: str,
  metrics: {
    tokens_in: int,
    tokens_out: int,
    locations_found: int
  },
  error: { type: str, message: str } | null
}
```

快取與冪等策略
--------------

- 先檢查 `analysis:{video_id}:{strategy_version}` 是否存在 → 直接返回 done 與可用 MapVisualization。
- strategy_version = 壓縮參數 / 模型版本 / 抽取規則 hash。
- 當策略版本升級：不重用舊 key，透過新 hash 強制重跑。

失敗分類與重試
--------------

| 類型 | 範例 | 處理 |
| ---- | ---- | ---- |
| transient | 429, timeout | 指數退避 3 次 → fail |
| deterministic | invalid video id | 直接 fail |
| partial | subset geocode fail | 記錄缺失 + status=done + retriable flag |

可觀測性
--------

- 日誌：JSON 行 (job_id, phase, elapsed_ms, event_type)
- 指標（/metrics Prometheus）：jobs_total、jobs_running、phase_duration_seconds_bucket、geocode_success_ratio
- Tracing（P2 之後）：OpenTelemetry exporter (可選)

安全與限速
--------

- Rate limit：IP + 路徑 token bucket (fastapi-limiter / 自製 Redis script)
- API Key header（P1.5 覆蓋）
- CORS：白名單 extension origin + localhost

交付分階段 (Milestones)
-----------------------

| Milestone | 內容 | 完成判準 |
| --------- | ---- | -------- |
| M1 Skeleton | FastAPI 啟動 + /health | 200 OK |
| M2 Analyze Sync | POST /analyze 同步執行（阻塞） | 回傳 job_id, status=done |
| M3 Async Queue | 引入 dispatcher + 狀態查詢 | 任務可排隊並查進度 |
| M4 SSE | /jobs/{id}/stream 推送 | 前端可即時顯示階段 |
| M5 Cache | Redis 命中 <100ms | 重複請求顯示 cached=true |
| M6 Partial Push | geocode 時 partial_locations | 地圖能增量更新 |
| M7 Metrics | /metrics + 主要指標 | Prometheus 可抓取 |
| M8 Retry Geocode | 局部重試端點 | 失敗地點可補全 |

詳細任務分解 (Backlog 切片)
---------------------------

M1~M2:

- 建立 FastAPI 專案結構 (`src/api/`)
- 匯入現有工具模組抽象成 service 層
- 同步版 POST /api/videos/analyze

M3:

- 建 Dispatcher 介面 + InMemory 實作 (queue, worker thread)
- Job 狀態存 Redis Hash
- GET /api/jobs/{id}

M4:

- SSE router (yield event-stream)
- 事件模型 + heartbeat

M5:

- Hash 策略實作
- cache 命中短路返回

M6:

- （若未來需要增量呈現）可再引入 partial locations；目前維持一次性輸出 MapVisualization，減少前端狀態複雜度。

M7:

- 指標中介層 + phase 計時 decorator
- /metrics endpoint

M8:

- 失敗地點紀錄 + retry 邏輯
- POST /api/videos/{id}/geocode/retry

風險與緩解
--------

| 風險 | 描述 | 緩解 |
| ---- | ---- | ---- |
| 長任務阻塞 | 初期未佇列化 | 優先完成 M3 非同步化 |
| Redis 不可用 | 快取/狀態失效 | fallback memory + 降級警示 |
| LLM 成本上升 | 重複分析 | 積極快取 + version 控制 |
| Geocode 失敗率高 | 模糊地名 | 加語境 + 多輪重試 + retry 端點 |

後續延伸 (Beyond P1.5)
----------------------

- WebSocket 雙向互動 (取消任務 / 動態調整策略)
- 任務優先級排程
- 多影片批次分析 API
- OpenTelemetry Tracing

實作備註
--------

- 先不引入大型 ORM；直接讀寫 JSON + 輕量索引。
- 避免阻塞 I/O：yt_dlp、LLM 呼叫包裝在 thread / async executor。
- 嚴格區分工具層（純函式）與 orchestrator（狀態）。
