#!/bin/zsh

# 啟動 TrailTag API 服務
echo "啟動 TrailTag API 服務..."
cd "$(dirname "$0")"
cd ..

# 啟動虛擬環境
source .venv/bin/activate

# 確保依賴已安裝
echo "檢查依賴..."
uv sync

# 啟動 API 服務
echo "啟動 API 伺服器..."
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8010
