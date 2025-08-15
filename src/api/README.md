# TrailTag API (src/api)

## 簡介

- 提供後端 HTTP API，負責：
  - 接收 YouTube 影片分析請求（非同步任務）
  - 查詢任務狀態（job）
  - 回傳影片地圖視覺化分析結果
- 使用 FastAPI 開發，內含簡易快取管理（Redis 作為第一選擇，Memory fallback）。

## 主要端點

### GET /health

- 基本健康檢查，回傳服務狀態、時間戳與快取是否降級（degraded）。

### POST /api/videos/analyze

- 提交影片分析請求。
- 參數：JSON body，例如：

```json
{"url": "https://..."}
```

- 回傳 job_id 與初始任務狀態。

### GET /api/jobs/{job_id}

- 查詢單一任務的狀態、進度與錯誤資訊。

### GET /api/videos/{video_id}/locations

- 取得影片分析後的地圖視覺化資料（MapVisualization）。

## 啟動指引（本地開發）

1. 建議建立虛擬環境並安裝相依套件（參考 `pyproject.toml`）。
1. 常用啟動（假設使用 uvicorn）：

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8010 --reload
```

1. 如使用 Redis，請設定以下環境變數（範例）：

- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_DB`
- `REDIS_PASSWORD`
- `REDIS_EXPIRY_DAYS`（預設 7）

## 重要環境變數

- `API_PORT` / `API_HOST`：用於應用內部列印與部署（uvicorn 可另外指定）。
- `REDIS_*`：Redis 連線資訊。

## 快取與工作流程

- 使用 `CacheManager` 自動選擇 Redis 或 `MemoryCacheProvider`（若 Redis 不可用則降級）。
- 分析任務會以背景工作執行，並將進度寫入快取（key: `job:{job_id}`），最終結果會存入 `analysis:{video_id}`。

## 開發與偵錯

- 日誌：使用 `src/api/logger_config.py`，若安裝 `colorlog` 可得到彩色輸出。
- 若需要測試，請查看專案根目錄的 `tests/` 或在本模組新增對應的單元測試。

## 授權與來源

- 請參考專案根目錄 `LICENSE`。

## 簡短範例（curl）

- 提交分析任務：

```bash
curl -X POST http://localhost:8010/api/videos/analyze \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=VIDEO_ID"}'
```

- 查詢 job：

```bash
curl http://localhost:8010/api/jobs/<job_id>
```

- 取得地點資料：

```bash
curl http://localhost:8010/api/videos/<video_id>/locations
```
