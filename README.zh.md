
# TrailTag

TrailTag 將 YouTube 旅遊 Vlog 轉換成可互動的地圖與路線資料，讓使用者能在地圖上重現創作者的旅程、檢視重要地點與主題摘要。這份 README 會說明主要功能、輸入/輸出合約、API 與 CLI 使用範例、資料格式、部署與開發注意事項。

![TrailTag Screenshot](https://github.com/user-attachments/assets/77dae24a-d77e-48e7-a376-db48e372a55c)

[TrailTag Demo](https://youtu.be/DzmGJXYH4-g)

## 目標讀者

- 想把旅遊影片自動化轉成地理資訊（開發者／資料工程師）
- 想把影片路線可視化（產品或前端工程師）
- 想在 GitHub 上評估或貢獻此專案的人

## 一句話功能總覽

- 從 YouTube 影片或影片 ID 擷取 metadata、字幕與時間軸
- 自動辨識影片中提到的地點（POI）與時間戳（timestamp）
- 進行地理編碼（geocoding）取得座標，重構路線（LineString）與 POI（Point）
- 建立可直接丟到地圖上的 GeoJSON（含屬性：時間、標題、信心度等）
- 提供後端 API、CLI 與瀏覽器擴充套件（extension）整合前端地圖顯示
- 支援快取（記憶體或 Redis）與任務狀態查詢（task/status streaming）

## 合約（簡短）

- 輸入：YouTube video ID 或影片 URL（亦可接收已下載的字幕/metadata）
- 輸出：
  - 任務識別：task_id（非同步處理）
  - 地圖資料：GeoJSON（route: LineString、points: FeatureCollection of Points）
  - 任務狀態：pending / running / done / failed

## 主要功能（詳細）

### 1. 影片擷取與預處理

- 下載或解析 YouTube metadata（title、description、upload date）
- 取得字幕（自動生成的字幕或上傳字幕），並解析時間戳與章節（chapters）

### 2. 主題抽取與摘要

- 透過 NLP（lightweight agent）抽出影片的主題、重點句與關鍵詞
- 產生時間戳對應的短摘要，便於在地圖 popup 顯示

### 3. 地點（POI）抽取與地理編碼

- 從文字（字幕、描述、章節）中抓取地名、地址、地標
- 支援多種 geocoding providers（可配置），例如 Nominatim、Google Geocoding API
- 回傳座標、信心度、解析來源

### 4. 路線重建（Route reconstruction）

- 將時間序列的 POI 與位置合併成一條或多條路線（LineString），並帶上時間區段
- 產生 GeoJSON 屬性（例如 start_time、end_time、duration、source_video_time）

### 5. 後端 API 與任務管理

- 非同步任務提交（回傳 task_id）
- 任務狀態查詢與結果下載（JSON / GeoJSON）
- Server-Sent Events（SSE）或 WebSocket 支援，用於即時進度更新

### 6. 快取與儲存

- 支援記憶體快取與 Redis（如安裝與設定），避免重複分析
- 可設定快取過期天數

### 7. 瀏覽器擴充套件（extension）

- popup/UI：允許使用者在觀看 YouTube 時一鍵發起分析並在側邊或新分頁顯示地圖
- 與後端 API 結合，取得並呈現 GeoJSON layer

### 8. CLI 與自動化 workflow

- 提供單次執行 CLI：處理單一 video id 並儲存結果
- 可在 CI / cron 中排程執行

## API 快覽（常見端點範例）

- POST /analyze
  - 說明：提交影片分析請求
  - 範例請求體：

  ```json
  {
   "video_id": "YOUTUBE_VIDEO_ID",
   "callback_url": "https://example.com/webhook",
   "options": {}
  }
  ```

  - 回應：

  ```json
  {
   "task_id": "...",
   "status": "pending"
  }
  ```

- GET /status/{task_id}
  - 說明：查詢任務狀態
  - 回應：{ "task_id": "...", "status": "done", "progress": 100 }

- GET /results/{task_id}
  - 說明：下載處理結果（JSON/GeoJSON）
  - 回應：GeoJSON FeatureCollection，包含 route 與 points

- GET /map/{task_id}.geojson
  - 說明：直接取得可放入地圖的 GeoJSON

（實際路由以 `src/api/routes.py` 為準）

## 資料格式範例（GeoJSON 摘要）

- route (LineString) feature properties 範例：

```json
{"type":"Feature","geometry":{"type":"LineString","coordinates":[...]},
 "properties": {"video_id":"abc","start_time":"00:01:30","end_time":"00:12:45","source":"detected"}}
```

- poi (Point) feature properties 範例：

```json
{"type":"Feature","geometry":{"type":"Point","coordinates":[lng,lat]},
 "properties":{"title":"Eiffel Tower","time":"00:05:22","confidence":0.89,"source":"subtitle"}}
```

## 快速啟動（開發）

先決條件

- Python 3.11+（見 `pyproject.toml`）
- Node.js + npm（用於 extension）
- 可選：Redis（若要快取或在多執行個體部署）

啟動後端（開發模式，使用 uvicorn）：

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8010 --reload
```

以命令列執行 Trailtag crew（單次執行）：

```bash
python -m src.trailtag.main <VIDEO_ID>
```

開發與打包 extension：

```bash
cd src/extension
npm install
npm test
npm run package
```

測試

- Python tests：在專案根目錄執行 `pytest`。
- Extension tests：在 `src/extension` 執行 `npm test`。

## 環境變數（細節）

- `API_HOST` (default 0.0.0.0)
- `API_PORT` (default 8010)
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD` — Redis 連線設定
- `REDIS_EXPIRY_DAYS` — 快取過期天數（整數）
- `OPENAI_API_KEY` — 用於訪問 OpenAI API 的金鑰
- `GOOGLE_API_KEY` — 用於訪問 Google API 的金鑰

## 部署建議

- 小型測試：單一 uvicorn + 可選 Redis（docker-compose 或本機安裝）
- 產線：以容器化（Docker）部署，多執行個體搭配共享 Redis 與負載平衡
- 注意：geocoding API 可能有用量限制，建議加入快取並使用合適的 API keys

## 開發者筆記與程式碼位置

- `src/api/` — FastAPI 應用、路由、模型、logger
- `src/trailtag/` — crew、agent 工具與 CLI
- `src/extension/` — 前端 extension 源碼與測試
- `tests/` — 單元測試

## 邊界注意

- 輸入不包含有效字幕或語言辨識失敗時，系統會嘗試用 video description 或章節備援；若都失敗，會回傳部分結果或標記為 "needs_human_review"。
- 大型影片（長時間）：處理可被切片並平行化；快取能減少重複負載。
- 地理編碼無法解析的地名會標記為未解析並回傳原始字串供人工處理。

## Inputs/Outputs

- Inputs: { video_id: string } 或已解析 subtitle/timestamps JSON
- Outputs: { task_id, status } + 最終 results: GeoJSON

## 測試與品質門檻

- 寫入單元測試（tests/）覆蓋核心轉換與 geocoding 邏輯
- 在修改公共 API 時請更新對應測試

## 貢獻

- 歡迎提交 PR、Issue 或改善測試
- 請遵循 repo 的 coding style 與在 PR 中描述修改原因

## 授權

- 授權請參考專案根目錄 `LICENSE`。
