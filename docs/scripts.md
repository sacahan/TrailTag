# TrailTag 管理腳本

本文檔說明了 TrailTag 項目中所有管理腳本的用途和使用方法。

## 可用腳本

以下是 `scripts/` 目錄中提供的管理腳本：

### 設置與安裝

- `setup_dev.sh` - 設置完整的開發環境
  - 安裝所有 Python 依賴
  - 確保必要的目錄結構存在
  - 為其他腳本添加執行權限

### 運行服務

- `start_api.sh` - 啟動 TrailTag API 服務
  - 啟動位於 `src/api/main.py` 的 FastAPI 應用
  - 在 [http://localhost:8000](http://localhost:8000) 上運行
  - 使用 uvicorn 並啟用熱重載功能

### 測試與檢查

- `run_tests.sh` - 運行所有測試
  - 使用 pytest 運行 `tests/` 目錄中的測試
  - 驗證系統功能是否正常

- `check_status.sh` - 檢查系統狀態
  - 顯示 Python 版本
  - 列出已安裝的關鍵依賴
  - 驗證目錄結構
  - 檢查 API 服務是否正在運行

### 示範與範例

- `demo_config.sh` - 演示配置文件的加載與使用
  - 加載並顯示 `agents.yaml` 和 `tasks.yaml` 的內容
  - 展示如何在 Python 代碼中使用這些配置

## 使用方法

所有腳本都需要執行權限。首次使用前，請運行：

```bash
chmod +x scripts/*.sh
```

然後可以直接執行任何腳本：

```bash
./scripts/setup_dev.sh
./scripts/start_api.sh
# 等等
```

## 開發工作流程

典型的開發工作流程如下：

1. 運行 `./scripts/setup_dev.sh` 設置開發環境
2. 運行 `./scripts/start_api.sh` 啟動 API 服務
3. 安裝瀏覽器擴展（參見 `docs/startup_guide.md`）
4. 進行開發和測試
5. 運行 `./scripts/run_tests.sh` 確保所有測試通過
6. 使用 `./scripts/check_status.sh` 驗證系統狀態

有關更多詳細信息，請參閱 `docs/` 目錄中的文檔。
