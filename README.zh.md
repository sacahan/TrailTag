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
- **字幕檢測系統**：自動偵測影片字幕可用性，並對無字幕影片提供警告

### 2. 主題抽取與摘要

- 透過 NLP（lightweight agent）抽出影片的主題、重點句與關鍵詞
- 產生時間戳對應的短摘要，便於在地圖 popup 顯示
- **智能 Token 管理**：針對長影片進行智能分割處理，避免 Token 限制問題

### 3. 地點（POI）抽取與地理編碼

- 從文字（字幕、描述、章節）中抓取地名、地址、地標
- 支援多種 geocoding providers（可配置），例如 Nominatim、Google Geocoding API
- 回傳座標、信心度、解析來源
- **多源資料擷取**：整合影片描述、章節資訊與評論區資料提取

### 4. 路線重建（Route reconstruction）

- 將時間序列的 POI 與位置合併成一條或多條路線（LineString），並帶上時間區段
- 產生 GeoJSON 屬性（例如 start_time、end_time、duration、source_video_time）

### 5. 後端 API 與任務管理

- 非同步任務提交（回傳 task_id）
- 任務狀態查詢與結果下載（JSON / GeoJSON）
- Server-Sent Events（SSE）或 WebSocket 支援，用於即時進度更新
- **強化狀態管理**：持久化任務追蹤與恢復機制

### 6. 記憶體與持久化系統

- **CrewAI Memory 系統**：主要儲存解決方案，具備向量搜尋能力
- 可選 Redis 備援，提供向下相容性
- **性能監控**：整合 Langtrace 追蹤與詳細指標收集

### 7. 瀏覽器擴充套件（extension）

- popup/UI：允許使用者在觀看 YouTube 時一鍵發起分析並在側邊或新分頁顯示地圖
- 與後端 API 結合，取得並呈現 GeoJSON layer
- **改善地圖性能**：標記聚類與最佳化渲染

### 8. CLI 與自動化 workflow

- 提供單次執行 CLI：處理單一 video id 並儲存結果
- 可在 CI / cron 中排程執行
- **遷移工具**：從 Redis 遷移到 CrewAI Memory 的完整支援

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

- **單元測試**：`pytest`（Python）或 `cd src/extension && npm test`（Extension）
- **整合測試**：`uv run pytest tests/integration/test_memory_migration.py -v`（Memory 系統驗證）
- **端對端測試**：`uv run python run_e2e_tests.py`（完整工作流程驗證）
- **遷移測試**：`uv run python scripts/migrate_redis_to_memory.py --dry-run`（資料遷移）

## 環境變數（細節）

### 核心配置

- `API_HOST` (default 0.0.0.0)
- `API_PORT` (default 8010)
- `OPENAI_API_KEY` — 用於訪問 OpenAI API 的金鑰
- `GOOGLE_API_KEY` — 用於訪問 Google API 的金鑰

### 記憶體系統（CrewAI）

- `CREW_MEMORY_STORAGE_PATH` — CrewAI Memory 儲存位置（預設：./memory_storage）
- `CREW_MEMORY_EMBEDDER_PROVIDER` — 嵌入向量提供者（預設：openai）

### 可觀測性與監控

- `LANGTRACE_API_KEY` — Langtrace API 金鑰，用於性能追蹤
- `ENABLE_PERFORMANCE_MONITORING` — 啟用/停用監控（預設：true）

### 傳統 Redis 支援（可選）

- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD` — Redis 連線設定
- `REDIS_EXPIRY_DAYS` — 快取過期天數（整數）

## 部署建議

- 小型測試：單一 uvicorn + 可選 Redis（docker-compose 或本機安裝）
- 產線：以容器化（Docker）部署，多執行個體搭配共享 Redis 與負載平衡
- 注意：geocoding API 可能有用量限制，建議加入快取並使用合適的 API keys

## 擴充套件狀態管理系統

### Chrome 擴充套件狀態系統

TrailTag Chrome 擴充套件實現了健全的狀態管理系統來處理影片分析工作流程。該系統協調擴充套件狀態、API 回應與 UI 視圖，提供無縫的使用者體驗。

#### 核心狀態定義

| 擴充套件狀態     | UI 視圖          | 說明                   | 持久化      |
| ---------------- | ---------------- | ---------------------- | ----------- |
| `IDLE`           | `home-view`      | 準備進行新影片分析     | 無          |
| `CHECKING_CACHE` | `loading-view`   | 檢查現有分析結果       | 無          |
| `ANALYZING`      | `analyzing-view` | 分析進行中，顯示進度   | 儲存任務 ID |
| `MAP_READY`      | `map-view`       | 在地圖上顯示分析結果   | 儲存結果    |
| `ERROR`          | `error-view`     | 錯誤狀態，顯示友善訊息 | 無          |

#### API 整合流程

| API 狀態    | API 階段    | 擴充套件回應       | 狀態轉換                |
| ----------- | ----------- | ------------------ | ----------------------- |
| `pending`   | `analyzing` | 顯示進度，開始輪詢 | → `ANALYZING`           |
| `running`   | 各種階段    | 更新進度指示器     | 保持 `ANALYZING`        |
| `completed` | `completed` | 取得位置資料       | → `MAP_READY` 或 `IDLE` |
| `failed`    | `failed`    | 顯示錯誤訊息       | → `ERROR`               |

#### 關鍵錯誤修復

**問題**：擴充套件會直接跳到地圖檢視，而非顯示分析檢視給新影片。

**根本原因**：`handleJobCompleted()` 函式將 404 API 錯誤回應視為有效位置資料。

**解決方案**：在 `popup-controller.ts` 中加入明確的 404 回應錯誤檢測：

```typescript
// popup-controller.ts 第 549-582 行
if (locations && typeof locations === "object" && (locations as any).detail) {
  const detail = String((locations as any).detail || "");
  if (/找不到影片地點資料|not\s*found/i.test(detail)) {
    // 404 回應 - 清理狀態並返回 IDLE
    changeState(AppState.IDLE, {
      videoId: state.videoId,
      mapVisualization: null,
      jobId: null,
      progress: 0,
      phase: null,
    });
    return;
  }
}
```

#### 狀態轉換驗證

| 從狀態                         | 到狀態         | 觸發              | 驗證 |
| ------------------------------ | -------------- | ----------------- | ---- |
| `IDLE` → `CHECKING_CACHE`      | 使用者點擊分析 | 影片 ID 存在      | ✓    |
| `CHECKING_CACHE` → `MAP_READY` | 找到快取資料   | 有效位置資料      | ✓    |
| `CHECKING_CACHE` → `ANALYZING` | 需要新分析     | 回傳有效任務 ID   | ✓    |
| `ANALYZING` → `MAP_READY`      | 任務完成       | 有效 GeoJSON 資料 | ✓    |
| `ANALYZING` → `IDLE`           | 無位置資料     | 404 錯誤處理      | ✓    |
| `ANALYZING` → `ERROR`          | 任務失敗       | 錯誤回應          | ✓    |

#### 階段文字對應

擴充套件將 API 階段對應到使用者友善的中文文字：

```typescript
function getPhaseText(phase: string | null): string {
  const phaseMap: { [key: string]: string } = {
    analyzing: "分析影片內容",
    extracting_places: "提取地點資訊",
    geocoding: "地理編碼處理",
    generating_routes: "生成路線資料",
    completed: "分析完成",
    failed: "分析失敗",
  };
  return phaseMap[phase || "analyzing"] || "處理中...";
}
```

#### 常見狀態管理問題與解決方案

1. **問題**：擴充套件跳過分析檢視直接顯示地圖檢視

   - **根本原因**：404 API 回應被視為有效位置資料
   - **解決方案**：明確的錯誤回應檢測與狀態清理

2. **問題**：過期的任務狀態在會話間持續存在

   - **根本原因**：完成任務但無資料時未清理 Chrome storage
   - **解決方案**：在錯誤情況下進行全面狀態清理

3. **問題**：階段文字與 API 回應不一致
   - **根本原因**：擴充套件預期的階段比 API 提供的更詳細
   - **解決方案**：簡化階段對應以符合實際 API 階段

#### 開發與除錯

啟用狀態轉換除錯：

```javascript
console.log("狀態轉換:", oldState, "->", newState, stateData);
```

監控關鍵事件：

- `changeState()` 呼叫中的狀態變更
- `handleJobCompleted()` 中的 API 回應
- Chrome storage 操作
- 任務輪詢生命週期

## 開發者筆記與程式碼位置（重構後架構）

### 後端組件

- `src/api/` — **模組化 FastAPI 後端**
  - `src/api/core/` — API 核心組件（模型定義、日誌配置）
  - `src/api/routes/` — API 端點與路由處理器
  - `src/api/middleware/` — 中間件（SSE、CORS 處理）
  - `src/api/services/` — 業務邏輯服務（CrewAI 執行、狀態管理、Webhooks）
  - `src/api/cache/` — 快取系統（Redis + 記憶體備案）
  - `src/api/monitoring/` — 性能監控與可觀測性

### CrewAI 系統

- `src/trailtag/` — **增強的 CrewAI 實現**
  - `src/trailtag/core/` — 核心系統（Crew 定義、模型、觀察器）
  - `src/trailtag/memory/` — CrewAI Memory 系統（管理器、進度追蹤）
  - `src/trailtag/tools/` — **分類工具套件**
    - `src/trailtag/tools/data_extraction/` — YouTube 元資料、章節、評論、描述
    - `src/trailtag/tools/processing/` — 字幕處理、壓縮、Token 管理
    - `src/trailtag/tools/geocoding/` — 地理座標解析

### 前端擴充套件

- `src/extension/` — **重構的 Chrome 擴充套件**
  - `src/extension/src/core/` — 核心功能（地圖渲染、彈出視窗控制、字幕檢測）
  - `src/extension/src/services/` — API 通訊服務
  - `src/extension/src/utils/` — 工具函式與最佳化工具
  - `src/extension/ui/` — 使用者介面組件與樣式
  - `src/extension/config/` — 建置與配置檔案
  - `src/extension/tests/` — 測試套件

### 測試與文件

- `tests/` — **完整測試套件**
  - `tests/integration/` — 整合測試（E2E、Memory 遷移驗證）
  - 各模組分散的單元測試
- `scripts/` — 遷移與工具腳本

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
