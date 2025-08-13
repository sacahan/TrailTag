# TrailTag Chrome Extension

TrailTag 的 Chrome 擴充功能，用於在 YouTube 影片頁面上顯示影片中提到的地點地圖。

## 功能

- 自動識別 YouTube 影片頁面
- 呼叫 TrailTag API 分析影片地點
- 顯示分析進度和狀態
- 地圖標記視覺化
- 匯出 GeoJSON

## 開發設置

1. 開啟 Chrome，進入 `chrome://extensions/`
2. 開啟「開發人員模式」
3. 點擊「載入未封裝項目」並選擇此目錄

## 檔案結構

- `manifest.json` - Chrome Extension 設定檔
- `popup.html` - 主要彈出視窗 UI
- `popup.js` - 主控腳本，管理 UI 狀態
- `styles.css` - 樣式表
- `api.js` - API 呼叫模組
- `map.js` - 地圖處理模組
- `utils.js` - 工具函數
- `service_worker.js` - 背景 service worker，處理 SSE 連線
- `assets/` - 圖示和其他資源

## 開發階段

目前處於 E1 (Skeleton) 階段：基本架構、UI 與流程設計。

## 依賴

- [Leaflet.js](https://leafletjs.com/) - 互動式地圖庫
