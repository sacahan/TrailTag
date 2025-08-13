#!/bin/zsh

# 運行測試
echo "運行 TrailTag 測試..."
cd "$(dirname "$0")"
cd ..

# 運行所有測試
pytest tests/
