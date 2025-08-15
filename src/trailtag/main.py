#!/usr/bin/env python
import sys
import os
import uuid
import warnings
from dotenv import load_dotenv
from src.api.logger_config import get_logger
from trailtag.crew import Trailtag
from src.api.cache_provider import RedisCacheProvider
import json

logger = get_logger(__name__)

# 禁用 OpenTelemetry SDK
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"

# 忽略 pysbd 套件產生的語法警告，避免影響執行時的輸出
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# 確保 outputs 目錄存在，若不存在則自動建立，用於儲存輸出結果
os.makedirs("outputs", exist_ok=True)

# 載入 .env 檔案中的環境變數，若已存在則覆蓋
load_dotenv(override=True)

# 取得 AgentOps API 金鑰，供後續追蹤與監控使用
AGENTOPS_API_KEY = os.getenv("AGENTOPS_API_KEY")

# 初始化快取提供者，用於儲存分析結果與狀態
redisCache = RedisCacheProvider()


def run(video_id: str = None):
    """
    執行 Trailtag crew 主流程。

    """

    # 若沒有傳入 YouTube 影片網址，則從命令列參數中取得
    video_id = None
    if len(sys.argv) > 1:
        video_id = sys.argv[1]

    # 若未提供 YouTube 影片網址，則記錄錯誤並結束流程
    if not video_id:
        print("No YouTube video ID provided.")
        return

    try:
        # 快取查詢邏輯（僅針對 map_routes）
        # 以 YouTube 影片網址為 key，查詢是否已有地圖路線快取結果
        cached_result = redisCache.get(f"analysis:{video_id}")
        if cached_result:
            print(f"<<< 已找到 {video_id} 的地圖路線快取，直接回傳，不執行 crew。")
            # 格式化快取結果為 JSON 字串並印出
            print(json.dumps(cached_result, indent=2, ensure_ascii=False))
            return

        # 初始化 AgentOps 追蹤功能，便於後續監控與除錯
        # agentops.init(api_key=AGENTOPS_API_KEY, auto_start_session=False)
        # trace_context = agentops.start_trace(trace_name="TrailTag Workflow")

        # 準備輸入參數，包含影片網址、搜尋主題與快取設定
        inputs = {
            "job_id": str(uuid.uuid4()),  # 產生唯一的 job_id
            "video_id": video_id,
            "search_subject": "找出景點與美食的地理位置",
            "clear_cache": False,  # 設置為 True 可清除所有快取
        }
        # 執行 Trailtag crew 主流程，kickoff 方法會啟動整個任務
        output = Trailtag().crew().kickoff(inputs=inputs)
        print(json.dumps(output.json_dict, indent=2, ensure_ascii=False))

        # 任務成功結束，結束追蹤
        # agentops.end_trace(trace_context=trace_context, end_state="SUCCESS")
    except Exception as e:
        # 若發生例外，記錄失敗狀態並拋出詳細錯誤
        # agentops.end_trace(trace_context=trace_context, end_state="FAILED")
        raise Exception(f"An error occurred while running the crew: {e}")


if __name__ == "__main__":
    # 若以 --help 參數執行，顯示使用說明並結束
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage: python main.py")
        print("Run the Trailtag crew with the default inputs.")
        sys.exit(0)

    # 預設以指定的 YouTube 影片網址執行主流程: https://www.youtube.com/watch?v=3VWiIFqy65M
    run()

    # 執行結束後提示使用者檢查輸出檔案
    print("Trailtag crew has been successfully executed.")
    print("Check the output file 'report.md' for the results.")
