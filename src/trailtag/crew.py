import os
from src.api.logger_config import get_logger
import datetime
from typing import List, Tuple, Any
from crewai import Agent, Crew, Process, Task, TaskOutput
from crewai.project import CrewBase, before_kickoff, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from src.trailtag.tools.youtube_metadata_tool import YoutubeMetadataTool
from src.trailtag.tools.place_geocode_tool import PlaceGeocodeTool
from src.api.cache_provider import RedisCacheProvider
from src.api.cache_manager import CacheManager
from src.trailtag.models import VideoMetadata, VideoTopicSummary, MapVisualization

# 建立 logger 物件，供全域記錄除錯與執行狀態
logger = get_logger(__name__)
# 設定專案根目錄，便於後續路徑組合
BASE_DIR = os.path.dirname(os.path.dirname(__file__))


def validate_video_map_generation_output(result: TaskOutput) -> Tuple[bool, Any]:
    """
    驗證 VideoMetadata 是否有值且主要欄位不為空。
    此函式作為任務的 guardrail，確保輸出結構正確且必要欄位存在。
    若欄位缺失或格式錯誤，將回傳 False 及錯誤訊息。
    """
    try:
        # 允許 result.pydantic 或 result.json_dict 取值
        output = getattr(result, "pydantic", None) or getattr(result, "json_dict", None)
        if not output:
            return False, "無法取得結構化輸出 (pydantic/json_dict) 或輸出為空"
        # 驗證 subtitles 欄位是否存在且不為空
        if getattr(output, "subtitles", None) is None:
            return False, "欄位 'subtitles' 缺失或為空"
        return True, output
    except Exception as e:
        logger.error(f"Guardrail 驗證例外: {e}")
        return False, f"驗證過程發生例外: {e}"


######################################################################
# 主流程 Crew 定義
# 此類別負責組裝所有 Agent、Task，並處理啟動前初始化、快取、資料儲存等邏輯
######################################################################
@CrewBase
class Trailtag:
    """
    Trailtag crew
    根據 agents.yaml 與 tasks.yaml 配置所有 Agent 與 Task，並設定執行流程。
    主要負責：
    - Agent/Task 組裝
    - 任務啟動前初始化
    - 快取與資料儲存
    """

    # Agent 與 Task 清單，供流程組裝
    agents: List[BaseAgent] = []
    tasks: List[Task] = []
    # 指定 LLM 模型，可切換本地或雲端模型
    # llm = LLM(model="openai/gpt-4o-mini", max_tokens=12000, timeout=300)
    llm = "gpt-4o-mini"
    # 啟動時的輸入參數
    kickoff_inputs: dict = {}
    # 輸出資料目錄
    outputs_dir = os.path.join(BASE_DIR, "outputs")

    @agent
    def video_fetch_agent(self) -> Agent:
        """
        影片資訊提取師 Agent：分析影片內容，提取 metadata、地點、時間軸等資訊。
        主要工具：YoutubeMetadataTool。
        """
        return Agent(
            llm=self.llm,
            config=self.agents_config["video_fetch_agent"],
            # reasoning=True,
            max_reasoning_attempts=3,
            max_retry_limit=1,
            verbose=True,
            respect_context_window=False,
            tools=[YoutubeMetadataTool()],
        )

    @agent
    def content_extraction_agent(self) -> Agent:
        """
        內容重點彙整師 Agent：主題資訊彙整與摘要。
        主要工具：SubtitleCompressionTool。
        """
        return Agent(
            llm=self.llm,
            config=self.agents_config["content_extraction_agent"],
            # reasoning=True,
            max_reasoning_attempts=3,
            max_retry_limit=3,
            verbose=True,
            respect_context_window=False,
            tools=[
                # SubtitleCompressionTool()
            ],
        )

    @agent
    def map_visualization_agent(self) -> Agent:
        """
        地圖可視化設計師 Agent：根據地點與時間軸資訊生成地圖路線。
        主要工具：PlaceGeocodeTool。
        """
        return Agent(
            llm=self.llm,
            config=self.agents_config["map_visualization_agent"],
            # reasoning=True,
            max_reasoning_attempts=3,
            max_retry_limit=3,
            verbose=True,
            respect_context_window=False,
            tools=[PlaceGeocodeTool()],
        )

    def _update_job_progress(self, phase, progress, status=None, extra=None):
        """
        於分析流程各階段即時更新 job 狀態與進度到 Redis 快取，供 SSE 查詢。
        需由 kickoff_inputs 取得 job_id。
        phase: 當前階段名稱
        progress: 進度百分比
        status: 狀態字串（如 running/done）
        extra: 額外欄位
        """
        job_id = self.kickoff_inputs.get("job_id")
        video_id = self.kickoff_inputs.get("video_id")
        if not job_id:
            return

        cache = CacheManager()
        now = datetime.datetime.now(datetime.timezone.utc)
        job = cache.get(f"job:{job_id}") or {}
        job.update(
            {
                "job_id": job_id,
                "video_id": video_id,
                "status": status or job.get("status", "running"),
                "phase": phase,
                "progress": progress,
                "cached": False,
                "created_at": job.get("created_at", now),
                "updated_at": now,
            }
        )
        if extra:
            job.update(extra)
        cache.set(f"job:{job_id}", job)

    def _video_metadata_callback(self, output: TaskOutput):
        """
        影片 metadata 任務 callback，更新進度至 20%，狀態為 running。
        """
        self._update_job_progress("metadata", 20, status="running")
        return output

    def _video_topic_summary_callback(self, output: TaskOutput):
        """
        主題摘要任務 callback，更新進度至 60%，狀態為 running。
        """
        self._update_job_progress("summary", 60, status="running")
        return output

    def _map_visualization_callback(self, output: TaskOutput):
        """
        地圖可視化任務 callback，更新進度至 100%，狀態為 done，並存儲地圖路線結果。
        """
        self._update_job_progress("geocode", 100, status="done")
        return self._store_map_routes_result(output)

    @task
    def video_metadata_extraction_task(self) -> Task:
        """
        影片 metadata 擷取任務：分析 YouTube 影片，提取 metadata 與基本資訊。
        任務完成後會將結果存入向量資料庫。
        執行結束時 callback 會即時更新 job 狀態。
        """
        return Task(
            config=self.tasks_config["video_metadata_extraction_task"],
            output_file="outputs/video_metadata.json",
            output_pydantic=VideoMetadata,
            guardrail=validate_video_map_generation_output,
            max_retries=3,
            callback=self._video_metadata_callback,
        )

    @task
    def video_topic_summary_task(self) -> Task:
        """
        主題摘要任務：針對主題分析字幕內容，彙整摘要。
        依賴 video_metadata_extraction_task 的結果作為 context。
        執行結束時 callback 會即時更新 job 狀態。
        """
        return Task(
            config=self.tasks_config["video_topic_summary_task"],
            context=[self.video_metadata_extraction_task()],
            output_file="outputs/topic_summary.json",
            output_pydantic=VideoTopicSummary,
            callback=self._video_topic_summary_callback,
        )

    @task
    def map_visualization_task(self) -> Task:
        """
        地圖可視化任務：分析地點資料產生互動式地圖欄位。
        依賴 video_topic_summary_task 的結果作為 context。
        執行結束時 callback 會即時更新 job 狀態。
        """
        return Task(
            config=self.tasks_config["map_visualization_task"],
            context=[self.video_topic_summary_task()],
            output_file="outputs/map_routes.json",
            output_pydantic=MapVisualization,
            callback=self._map_visualization_callback,
        )

    def _store_map_routes_result(self, output: TaskOutput):
        """
        將地圖路線結果存入 Redis 快取。
        若 output.pydantic 為空則跳過。
        """
        if output.pydantic is None:
            logger.warning("Output is empty or not structured, skipping storage.")
            return output
        try:
            video_id = self.kickoff_inputs.get("video_id")
            # 同步存入分析結果快取（分析結果 key 統一）
            cache = CacheManager()
            cache.set(f"analysis:{video_id}", output.pydantic.model_dump())
            logger.info(f"已將地圖路線結果存入 Redis 快取: {video_id}")
        except Exception as e:
            logger.error(f"存儲地圖路線結果失敗: {e}")
        return output

    @before_kickoff
    def before_kickoff_function(self, inputs):
        """
        任務啟動前的初始化函式。
        若指定 clear_cache，則清除 Redis 快取。
        並將 kickoff inputs 儲存於 self.kickoff_inputs 供 callback 使用。
        """
        logger.info(f"Before kickoff with inputs: {inputs}")
        self.kickoff_inputs = inputs.copy() if isinstance(inputs, dict) else inputs
        # 如果指定了要清除快取，則清除 Redis 中所有 trailtag:* 相關快取
        if inputs.get("clear_cache", False):
            try:
                redis_tool = RedisCacheProvider()
                cleared = redis_tool.clear_all("trailtag:*")
                if cleared:
                    logger.info(f"已清除 {cleared} 個 Redis 快取")
            except Exception as e:
                logger.error(f"清除 Redis 快取失敗: {e}")
        return inputs

    @crew
    def crew(self) -> Crew:
        """
        建立並返回 Trailtag Crew，依序執行所有任務。
        agents 與 tasks 依照順序組成流程，並啟用規劃與快取功能。
        """
        return Crew(
            agents=[
                self.video_fetch_agent(),
                self.content_extraction_agent(),
                self.map_visualization_agent(),
            ],
            tasks=[
                self.video_metadata_extraction_task(),
                self.video_topic_summary_task(),
                self.map_visualization_task(),
            ],
            process=Process.sequential,
            verbose=True,
        )
