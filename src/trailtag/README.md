# Trailtag Crew (src/trailtag)

## 簡介

- Trailtag crew 負責組裝並執行影片分析工作流程，包含：
  - 擷取 YouTube metadata
  - 產生主題摘要
  - 地點 geocoding 與地圖視覺化資料輸出

## 主要模組

- `crew.py`：定義 Trailtag Crew、Agents、Tasks 與流程控制，包含進度回調與快取儲存邏輯。
- `models.py`：Pydantic 模型定義，包含 `VideoMetadata`、`VideoTopicSummary`、`MapVisualization` 等。
- `main.py`：命令列執行腳本，可直接跑 crew 流程並將結果輸出到 `outputs/`。
- `tools/`：自訂工具集合（YouTube metadata 擷取、地理編碼等）。

## 執行方式

1. 若要以命令列執行：

   ```bash
   python -m src.trailtag.main <video_id>
   ```

2. 若希望測試快取行為，可先啟動 Redis 並設定環境變數，或使用內部 `MemoryCacheProvider`。

## 注意事項

- 依賴 `crewai` 與其他工具（位於 `src/trailtag/tools`），請確認相依套件已安裝。
- 輸出會儲存在 `outputs/` 目錄，請確保該目錄有寫入權限。

## 示例

- 執行流程並列印結果：

  ```bash
  python -m src.trailtag.main https://www.youtube.com/watch?v=VIDEO_ID
  ```

## 授權

- 請參考專案根目錄 `LICENSE`。
