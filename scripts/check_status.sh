#!/bin/zsh

# 檢查 TrailTag 系統狀態
echo "檢查 TrailTag 系統狀態..."
cd "$(dirname "$0")"
cd ..

# 檢查 Python 版本
echo "Python 版本:"
python --version

# 檢查已安裝的依賴
echo "\n已安裝的關鍵依賴:"
pip freeze | grep -E 'fastapi|uvicorn|crewai|pydantic|pytest'

# 檢查目錄結構
echo "\n檢查目錄結構:"
ls -la src/
ls -la src/api/ 2>/dev/null || echo "API 目錄不存在或為空"
ls -la src/extension/ 2>/dev/null || echo "擴展目錄不存在或為空"
ls -la src/trailtag/ 2>/dev/null || echo "TrailTag 核心目錄不存在或為空"

# 檢查 API 是否正在運行
echo "\n檢查 API 服務狀態:"
if curl -s http://localhost:8000/health > /dev/null; then
    echo "API 服務正在運行 ✅"
else
    echo "API 服務未運行 ❌"
fi

echo "\n系統狀態檢查完成"
