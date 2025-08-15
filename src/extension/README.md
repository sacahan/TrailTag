# TrailTag Browser Extension (src/extension)

## 簡介

- 這是一個為 TrailTag 專案所設計的 Chrome extension 前端樣板。主要用途為與後端 API 互動、展示影片地點地圖與提供 UI 操作。

## 專案內容概覽

- `popup.html` / `popup.js`：擴充功能彈出視窗介面與行為。
- `map.js`：處理地圖相關的邏輯（整合地圖庫並顯示路線與標記）。
- `api.js`：與後端 API 的互動函式封裝，例如提交分析請求、查詢 job 與取得 locations。
- `service_worker.js`：背景執行邏輯。
- `styles.css`：樣式表。
- `assets/`：圖示與資源。
- `__tests__/`：Jest 測試檔案與測試工具。
- `manifest.json`：擴充功能設定（manifest v3）。

## 開發指引

1. 安裝相依套件（Node.js 與 npm 必須已安裝）：

   ```bash
   npm install
   ```

2. 執行測試：

   ```bash
   npm test
   ```

3. 打包 Chrome 擴充功能：

   ```bash
   npm run package
   ```

## 如何與後端整合

- 預設後端 API 位址：`http://localhost:8010`。請確保 API 正在執行並允許來自 extension 的 CORS。
- `api.js` 包含與 `/api/videos/analyze`、`/api/jobs/{job_id}`、`/api/videos/{video_id}/locations` 的互動範例。

## 注意事項

- 使用 manifest v3，請確認 Chrome 瀏覽器版本支援。
- 部署時可將 `dist/extension` 或 zip 上傳到 Chrome Web Store，或於本機以開發者模式載入。

## 授權

- 請參考專案根目錄 `LICENSE`。
