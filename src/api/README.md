# TrailTag API 服務

TrailTag 的後端 API 服務，處理 YouTube 影片分析、任務排程和地點視覺化資料。

## 安裝

```bash
pip install -r requirements.txt
```

## 啟動開發伺服器

```bash
uvicorn src.api.main:app --reload --port 8000
```

## API 端點

- `POST /api/videos/analyze` - 提交分析請求
- `GET /api/jobs/{job_id}` - 查詢任務狀態
- `GET /api/jobs/{job_id}/stream` - SSE 進度事件流
- `GET /api/videos/{video_id}/locations` - 取得地點視覺化資料

## 開發階段

目前處於 M1 (Skeleton) 階段：基本 FastAPI 架構與健康檢查。

## 未來功能

1. 非同步任務隊列 (Redis + Celery)
2. 快取 (Redis)
3. 指標 (Prometheus)
4. 失敗地點重試
