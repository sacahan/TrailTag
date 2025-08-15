# TrailTag

TrailTag 是一個將 YouTube 旅遊 Vlog 內容轉換為互動地圖的專案，能從影片中擷取路線、地點與重點，讓使用者可視覺化追蹤創作者的旅程。

## 主要功能

- 後端 API：接收影片分析請求、回傳任務狀態與地點視覺化資料。

- Crew：以 `crewai` 組裝多個 Agent 與 Task，執行影片 metadata 擷取、主題摘要與地點 geocoding，並將結果存入快取。

- 瀏覽器外掛：提供前端 popup/UI 與地圖顯示，能與後端 API 整合顯示分析結果。

## 倉庫結構（重點）

- `src/api/` — FastAPI 後端與快取、路由、模型。

- `src/trailtag/` — Trailtag crew、models、tools 與 CLI 腳本。

- `src/extension/` — Chrome extension 前端資源與測試。

- `tests/` — Python unit tests。

## 快速啟動

先決條件

- Python 3.11+（請參考 `pyproject.toml`）
- Node.js + npm（用於 extension）
- 可選：Redis（若要使用 Redis 快取）

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

## 環境變數（常用）

- `API_PORT`, `API_HOST` — 應用列印或部署用途。

```bash
cd src/extension
npm install
npm test
npm run package
```

## 環境變數（常用）

- `API_PORT`, `API_HOST` — 應用列印或部署用途。

- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD`, `REDIS_EXPIRY_DAYS` — Redis 連線與過期設定。

- `AGENTOPS_API_KEY` —（可選）AgentOps 追蹤 API 金鑰。

## 測試

- Python tests：在專案根目錄執行 `pytest`。

- Extension tests：進入 `src/extension` 並執行 `npm test`。

## 日誌與偵錯

- 後端使用 `src/api/logger_config.py` 管理日誌，若已安裝 `colorlog`，會顯示彩色日誌。

## 貢獻與授權

- 歡迎 pull requests 與 issues，請參考專案風格並撰寫測試。

- 授權請參考專案根目錄的 `LICENSE`。
