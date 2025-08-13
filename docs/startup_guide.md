# TrailTag 啟動指南

本文檔提供了啟動和使用 TrailTag 系統的步驟說明。

## 前置需求

確保您已安裝以下依賴項：

- Python 3.12 或更高版本
- pip (Python 包管理器)
- 瀏覽器 (Chrome 或 Edge，用於擴展)

## 後端 API 服務啟動

使用以下命令啟動 TrailTag API 服務：

```bash
# 給予腳本執行權限（首次運行時需要）
chmod +x scripts/start_api.sh

# 啟動 API 服務
./scripts/start_api.sh
```

服務將在 [http://localhost:8000](http://localhost:8000) 上運行。您可以訪問 [http://localhost:8000/docs](http://localhost:8000/docs) 查看 API 文檔。

## 擴展安裝

1. 打開 Chrome 或 Edge 瀏覽器
2. 訪問 `chrome://extensions` 或 `edge://extensions`
3. 啟用「開發者模式」
4. 點擊「載入未封裝項目」
5. 選擇 `src/extension` 目錄
6. 擴展將顯示在您的瀏覽器工具欄中

## 運行測試

使用以下命令運行測試：

```bash
# 給予腳本執行權限（首次運行時需要）
chmod +x scripts/run_tests.sh

# 運行測試
./scripts/run_tests.sh
```

## 功能概述

TrailTag 系統使用以下步驟分析 YouTube 影片：

1. 通過擴展提交 YouTube 影片 URL
2. 後端分析影片，提取路線數據
3. 創建可視化地圖，在擴展中顯示
4. 提供路線摘要和關鍵位置點

如需更多詳細信息，請參閱系統文檔。
