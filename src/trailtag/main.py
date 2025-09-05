#!/usr/bin/env python
import sys
import os
import uuid
import warnings
import json
from dotenv import load_dotenv

# 將專案根目錄添加到 Python 路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

# ruff: noqa: E402
from src.api.core.logger_config import get_logger
from src.trailtag.core.crew import Trailtag
from src.trailtag.memory.manager import CrewMemoryManager

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

# 初始化 CrewAI Memory 管理器，用於儲存分析結果與狀態
memory_manager = CrewMemoryManager()


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
        print("⚠️ No YouTube video ID provided. Please provide a video ID or URL. ❌")
        return

    try:
        # CrewAI Memory 查詢邏輯 - 檢查是否已有分析結果
        # 使用語義搜索查找相關的影片分析結果
        search_results = memory_manager.search(
            query=f"video_analysis:{video_id}",
            filter_metadata={"type": "video_analysis", "video_id": video_id},
            limit=1,
        )

        if search_results:
            cached_result = search_results[0].get("content")
            if cached_result:
                print(f"<<< 在 CrewAI Memory 中找到 {video_id} 的分析結果，直接回傳。")
                try:
                    # 嘗試解析為 JSON
                    result_data = json.loads(cached_result)
                    print(json.dumps(result_data, indent=2, ensure_ascii=False))
                except json.JSONDecodeError:
                    # 若不是 JSON 格式，直接輸出
                    print(cached_result)
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

        # 將分析結果存入 CrewAI Memory 供後續使用
        result_content = json.dumps(output.json_dict, ensure_ascii=False)
        memory_manager.store(
            content=result_content,
            metadata={
                "type": "video_analysis",
                "video_id": video_id,
                "job_id": inputs["job_id"],
                "timestamp": str(uuid.uuid4()),  # 使用 UUID 作為時間戳記
                "search_subject": inputs["search_subject"],
            },
        )
        logger.info(f"分析結果已存入 CrewAI Memory，影片 ID: {video_id}")

        # 輸出分析結果
        print(json.dumps(output.json_dict, indent=2, ensure_ascii=False))

        # 任務成功結束，結束追蹤
        # agentops.end_trace(trace_context=trace_context, end_state="SUCCESS")
    except Exception as e:
        # 若發生例外，記錄失敗狀態並拋出詳細錯誤
        # agentops.end_trace(trace_context=trace_context, end_state="FAILED")
        raise Exception(f"❌ An error occurred while running the crew: {e} 🚨")


if __name__ == "__main__":
    # 若以 --help 參數執行，顯示使用說明並結束
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("📖 Usage: python main.py")
        print("🚀 Run the Trailtag crew with the default inputs. 🏞️")
        sys.exit(0)

    # 預設以指定的 YouTube 影片網址執行主流程: https://www.youtube.com/watch?v=3VWiIFqy65M
    run()

    # 執行結束後提示使用者檢查輸出檔案
    print("✅ Trailtag crew has been successfully executed. 🎉")
    print("📄 Check the output file 'report.md' for the results. 📝")
