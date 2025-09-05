# TrailTag 前端環境變數配置指南

## 概述

TrailTag 前端擴充功能支援透過環境變數進行配置，可在建制時設定 API 端點、重試參數等選項。此功能讓您可以針對不同環境（開發、測試、正式）輕鬆調整配置。

## 支援的環境變數

| 環境變數名稱                   | 配置鍵名              | 預設值                  | 說明                             |
| ------------------------------ | --------------------- | ----------------------- | -------------------------------- |
| `TRAILTAG_API_BASE_URL`        | `API_BASE_URL`        | `http://localhost:8010` | 後端 API 服務的基礎 URL          |
| `TRAILTAG_FETCH_RETRIES`       | `FETCH_RETRIES`       | `2`                     | HTTP 請求失敗時的重試次數        |
| `TRAILTAG_FETCH_BACKOFF_MS`    | `FETCH_BACKOFF_MS`    | `500`                   | 重試的初始退避時間（毫秒）       |
| `TRAILTAG_MAX_RECONNECT`       | `MAX_RECONNECT`       | `1`                     | SSE 連線的最大重連次數           |
| `TRAILTAG_POLLING_INTERVAL_MS` | `POLLING_INTERVAL_MS` | `5000`                  | 輪詢狀態的間隔時間（毫秒）       |
| `TRAILTAG_KEEPALIVE_MS`        | `KEEPALIVE_MS`        | `30000`                 | Keep-alive 的時間窗（毫秒）      |
| `TRAILTAG_STATE_TTL_MS`        | `STATE_TTL_MS`        | `1800000`               | 持久化狀態的 TTL（毫秒，30分鐘） |

## 使用方式

### 1. 透過建制腳本設定

使用 `scripts/build_frontend.sh` 時，可以在執行前設定環境變數：

```bash
# 設定正式環境配置
export TRAILTAG_API_BASE_URL="https://api.trailtag.com"
export TRAILTAG_FETCH_RETRIES="3"
export TRAILTAG_FETCH_BACKOFF_MS="1000"

# 執行建制
./scripts/build_frontend.sh
```

### 2. 單次建制設定

您也可以在同一行中設定環境變數並執行建制：

```bash
TRAILTAG_API_BASE_URL="https://staging.trailtag.com" \
TRAILTAG_FETCH_RETRIES="3" \
./scripts/build_frontend.sh
```

### 3. 透過 npm 腳本設定

直接在前端目錄中使用 npm 建制時：

```bash
cd src/extension

# 設定環境變數
export TRAILTAG_API_BASE_URL="https://api.trailtag.com"

# 執行建制
npm run build
```

### 4. 使用 .env 檔案（可選）

您可以創建一個 `.env` 檔案並使用工具（如 `dotenv`）載入：

```env
# .env 檔案
TRAILTAG_API_BASE_URL=https://api.trailtag.com
TRAILTAG_FETCH_RETRIES=3
TRAILTAG_FETCH_BACKOFF_MS=1000
```

然後使用：

```bash
# 需要安裝 dotenv-cli: npm install -g dotenv-cli
dotenv ./scripts/build_frontend.sh
```

## 配置驗證

建制過程中，腳本會顯示當前使用的配置值：

```text
[INFO] 當前 TrailTag 配置:
[INFO]   API_BASE_URL: https://api.trailtag.com
[INFO]   FETCH_RETRIES: 3
[INFO]   FETCH_BACKOFF_MS: 1000
[INFO]   MAX_RECONNECT: 1
[INFO]   POLLING_INTERVAL_MS: 5000
[INFO]   KEEPALIVE_MS: 30000
[INFO]   STATE_TTL_MS: 1800000
```

## 不同環境的建議配置

### 開發環境

```bash
export TRAILTAG_API_BASE_URL="http://localhost:8010"
export TRAILTAG_FETCH_RETRIES="2"
export TRAILTAG_FETCH_BACKOFF_MS="500"
```

### 測試環境

```bash
export TRAILTAG_API_BASE_URL="https://staging.trailtag.com"
export TRAILTAG_FETCH_RETRIES="3"
export TRAILTAG_FETCH_BACKOFF_MS="1000"
```

### 正式環境

```bash
export TRAILTAG_API_BASE_URL="https://api.trailtag.com"
export TRAILTAG_FETCH_RETRIES="3"
export TRAILTAG_FETCH_BACKOFF_MS="1000"
export TRAILTAG_MAX_RECONNECT="2"
```

## 技術細節

### 配置注入機制

1. **建制時注入**: `config/inject-config.mjs` 腳本會讀取環境變數並生成 `dist_ts/config.js` 檔案
2. **運行時載入**: 擴充功能在載入時會自動載入這個配置檔案
3. **回退機制**: 如果找不到配置檔案，會使用程式碼中的預設值

### 配置優先順序

配置的載入優先順序為：

1. 全域 `TRAILTAG_CONFIG` 物件（建制時注入）
2. `window.TRAILTAG_CONFIG`（瀏覽器環境）
3. `self.TRAILTAG_CONFIG`（Worker 環境）
4. 程式碼中的預設值

### 檔案位置

- 配置注入腳本: `src/extension/config/inject-config.mjs`
- 生成的配置檔案: `src/extension/dist_ts/config.js`
- 最終部署位置: `dist/extension/config.js`

## 故障排除

### 常見問題

**Q: 環境變數設定後沒有生效？**
A: 確保在執行建制腳本前設定環境變數，並檢查是否正確匯出（使用 `export`）。

**Q: 建制失敗，提示找不到 config.js？**
A: 確保 `npm run inject:config` 步驟成功執行，檢查 `dist_ts/` 目錄是否存在。

**Q: 擴充功能仍使用舊配置？**
A: 確保瀏覽器中的擴充功能已重新載入，清除快取後重試。

### 除錯方法

1. 檢查建制輸出中的配置資訊
2. 查看生成的 `dist_ts/config.js` 檔案內容
3. 在瀏覽器開發者工具中檢查 `window.TRAILTAG_CONFIG`

## 範例腳本

以下是一個完整的部署腳本範例：

```bash
#!/usr/bin/env zsh

# 設定正式環境配置
export TRAILTAG_API_BASE_URL="https://api.trailtag.com"
export TRAILTAG_FETCH_RETRIES="3"
export TRAILTAG_FETCH_BACKOFF_MS="1000"
export TRAILTAG_MAX_RECONNECT="2"

# 執行建制
echo "🚀 開始建制 TrailTag 正式版本..."
./scripts/build_frontend.sh

if [ $? -eq 0 ]; then
    echo "✅ 建制成功！"
    echo "📦 擴充功能檔案位於: dist/extension/"
else
    echo "❌ 建制失敗！"
    exit 1
fi
```
