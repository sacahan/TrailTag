---
post_title: "TrailTag Browser Extension (src/extension)"
author1: "sacahan"
post_slug: "trailtag-extension"
microsoft_alias: "sacahan"
featured_image: "assets/icon_128x128.png"
categories:
   - Extensions
tags:
   - chrome-extension
   - typescript
   - build
ai_note: "Updated with AI assistance"
summary: "說明如何開發、測試與打包 TrailTag Chrome extension，包含範例指令與注意事項。"
post_date: "2025-08-16"
---

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

1. 安裝相依套件（需要 Node.js 與 npm）：

    ```bash
    npm install
    ```

2. 執行測試：

    ```bash
    npm test
    ```

3. 本地打包（clean、TypeScript 編譯、複製必要檔案並壓縮）：

    ```bash
    cd src/extension
    npm run package
    ```

4. 若只要編譯並複製檔案：

    ```bash
    npm run build
    ```

## 與後端整合

- 預設後端 API 位址：`http://localhost:8010`。請確保 API 正在執行並允許來自 extension 的 CORS。
- `api.js` 包含與 `/api/videos/analyze`、`/api/jobs/{job_id}`、`/api/videos/{video_id}/locations` 的互動範例。

## 打包輸出

- 打包後產生的資料夾：`dist/extension`
- 壓縮檔：`dist/extension.zip`

範例：`dist/extension` 會包含 `manifest.json`、`popup.html`、編譯後的 `.js` 檔案、`service_worker.js`、`styles.css`、`assets/` 與 `vendor/`。

## 注意事項

- 使用 manifest v3，請確認 Chrome 瀏覽器版本支援。
- 若要在不同作業系統上保持相容，建議改用 Node.js 腳本或安裝跨平台套件來處理複製與壓縮流程。
- 上傳至 Chrome Web Store 或以開發者模式載入時，請使用 `dist/extension` 或 `dist/extension.zip`。

## 授權

- 請參考專案根目錄的 `LICENSE`。
