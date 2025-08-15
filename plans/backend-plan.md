# TrailTag 後端 API 規格書

本規格書為[主要提案](project-proposal.md)的後端實作規範。

## 目標

- 提供 REST API 與 SSE 進度查詢，支援非同步任務、快取，易於維護。

## 架構簡述

- FastAPI 為主，API 路由集中於 `src/api/routes.py`。
- 主要流程：
  1. analyze 請求先查快取，命中直接回傳。
  2. 未命中則建立 job，非同步執行分析。
  3. 進度/錯誤即時回報，結果寫入快取。
- Redis 為快取與狀態儲存主體，memory fallback。
- crew.py 負責分析邏輯，工具層如 subtitle_compression_tool、place_geocode_tool。

## 主要端點

| Method | Path | 說明 |
| ------ | ---- | ---- |
| POST | /api/videos/analyze | 提交分析任務，快取命中直接回傳 |
| GET | /api/jobs/{job_id} | 查詢任務進度與狀態 |
| GET | /api/jobs/{job_id}/stream | SSE 事件推播進度 |
| GET | /api/videos/{video_id}/locations | 取得地點視覺化結果 |

## Job 狀態與階段

- 狀態：queued / running / partial / failed / done
- 階段：metadata / compression / summary / geocode

## 資料結構（簡化）

```json
{
  "job_id": "...",
  "video_id": "...",
  "status": "running",
  "phase": "compression",
  "progress": 35.0,
  "created_at": 1734031000,
  "updated_at": 1734031020,
  "error": null
}
```

## 快取策略

- 先查 `analysis:{video_id}:{strategy_version}`，命中直接回傳。
- strategy_version 由分析參數 hash 得出。
- Redis 不可用時 fallback memory cache。

## 進度計算

- 依各階段完成比例加總。
- metadata：下載/解析步驟完成比例。
- compression：已壓縮段數 / 總段數。
- summary：已摘要 chunk / 總 chunk。
- geocode：成功 geocode 地點 / 總地點。

## SSE 事件

- phase_update：job_id, phase, progress, ts
- heartbeat：job_id, status, ts
- completed：job_id, status=done, progress=100
- error：job_id, status=failed, error

## 錯誤分類

- transient：如 LLM timeout/429，重試 3 次失敗則 fail
- deterministic：如無效 video id，直接 fail
- partial：部分 geocode 失敗，status=partial

## 後端 AI Agent 流程

### 主要序列圖

```mermaid
sequenceDiagram
  autonumber
  participant C as Client
  participant API as FastAPI
  participant R as Redis Cache
  participant Q as Queue
  participant W as Worker
  participant T as Tools

  C->>API: POST /api/videos/analyze
  API->>R: 查快取 analysis:{video_id}:{hash}
  alt Cache Hit
    R-->>API: cached result
    API-->>C: {status: done, cached: true}
  else Cache Miss
    R-->>API: not found
    API->>Q: enqueue job
    API->>R: 存 job 狀態 (queued)
    API-->>C: {job_id, status: queued}

    W->>Q: 取得 job
    W->>R: 更新狀態 (running)
    W->>T: metadata 階段
    W->>R: 更新進度 (phase: metadata, progress: 25)
    W->>T: compression 階段
    W->>R: 更新進度 (phase: compression, progress: 50)
    W->>T: summary 階段
    W->>R: 更新進度 (phase: summary, progress: 75)
    W->>T: geocode 階段
    W->>R: 更新進度 (phase: geocode, progress: 100)
    W->>R: 存結果快取 & 狀態 (done)
  end
```

### SSE 進度推播

```mermaid
sequenceDiagram
  autonumber
  participant C as Client
  participant API as FastAPI
  participant R as Redis Cache
  participant SSE as SSE Handler

  C->>API: GET /jobs/{job_id}/stream
  API->>SSE: 建立 SSE 連線

  loop 每 2 秒查詢
    SSE->>R: 查詢 job 狀態
    alt Job 有更新
      R-->>SSE: job data
      SSE-->>C: event: phase_update
    else 無變化
      SSE-->>C: event: heartbeat
    end
  end

  alt Job 完成
    SSE-->>C: event: completed
    SSE->>SSE: 關閉連線
  else Job 失敗
    SSE-->>C: event: error
    SSE->>SSE: 關閉連線
  end
```

### 錯誤處理與重試

```mermaid
sequenceDiagram
  autonumber
  participant W as Worker
  participant T as Tools
  participant R as Redis Cache

  W->>T: 執行工具 (如 LLM 呼叫)
  alt 成功
    T-->>W: 結果
    W->>R: 更新進度
  else Transient 錯誤 (429, timeout)
    T-->>W: error
    W->>W: 指數退避 (1s, 2s, 4s)
    W->>T: 重試 (最多 3 次)
    alt 重試成功
      T-->>W: 結果
      W->>R: 更新進度
    else 重試失敗
      W->>R: 標記 failed
    end
  else Deterministic 錯誤 (無效 video_id)
    T-->>W: error
    W->>R: 直接標記 failed
  end
```

## 測試策略

- Unit：hash、快取、分析流程
- Integration：cache miss/hit、進度計算
- Contract：API schema 完整性
- Load：佇列堆疊
- Retry：transient 錯誤重試
