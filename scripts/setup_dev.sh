#!/bin/zsh

# TrailTag 開發環境設置腳本
echo "設置 TrailTag 開發環境..."
cd "$(dirname "$0")"
cd ..

# 確保目錄結構存在
mkdir -p src/outputs

# 安裝 Python 依賴
echo "安裝 Python 依賴..."
pip install -e .
pip install -r src/api/requirements.txt

# 安裝開發依賴
echo "安裝開發依賴..."
pip install pytest pytest-cov

# 為腳本添加執行權限
chmod +x scripts/start_api.sh
chmod +x scripts/run_tests.sh

echo "開發環境設置完成!"
echo "使用 './scripts/start_api.sh' 啟動 API 服務"
echo "使用 './scripts/run_tests.sh' 運行測試"
