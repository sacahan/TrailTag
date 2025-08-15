#!/bin/zsh
# 測試 trailtag.main.py 模組，支援 video_id 參數

if [[ $# -lt 1 ]]; then
  echo "用法: ./test_trailtag_main.sh <video_id>"
  echo "範例: ./test_trailtag_main.sh 3VWiIFqy65M"
  exit 1
fi

VIDEO_ID="$1"

# 切換到專案根目錄
cd "$(dirname "$0")/.."

# 執行 main.py 並傳入 video_id
python -m src.trailtag.main "$VIDEO_ID"
