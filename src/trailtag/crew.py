import logging
from crewai import Agent, Crew, Process, Task, TaskOutput
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai_tools import (
    ScrapeWebsiteTool,
    SerperDevTool,
    FileReadTool,
    DirectorySearchTool,
)
from .tools.youtube_metadata_tool import YoutubeMetadataTool

from typing import List, Tuple, Any
from .models import (
    VideoMapGenerationOutput,
    MapVisualizationOutput,
)

logging = logging.getLogger(__name__)


# --- Guardrail function for video_map_generation_task ---
def validate_video_map_generation_output(result: TaskOutput) -> Tuple[bool, Any]:
    """驗證 VideoMapGenerationOutput 是否有值且主要欄位不為空。"""
    try:
        # 允許 result.pydantic 或 result.json_dict 取值
        output = getattr(result, "pydantic", None) or getattr(result, "json_dict", None)
        if not output:
            return (False, "無法取得結構化輸出 (pydantic/json_dict) 或輸出為空")
        # 驗證 subtitles 欄位
        required_fields = ["subtitles"]
        for field in required_fields:
            value = (
                getattr(output, field, None)
                if hasattr(output, field)
                else output.get(field)
            )
            if value is None or (isinstance(value, (str, list, dict)) and not value):
                logging.warning(f"欄位 '{field}' 缺失或為空")
                return (False, f"欄位 '{field}' 缺失或為空")

        return (True, output)
    except Exception as e:
        logging.error(f"驗證過程發生例外: {str(e)}")
        return (False, f"驗證過程發生例外: {str(e)}")


@CrewBase
class Trailtag:
    """Trailtag crew
    根據 agents.yaml 與 tasks.yaml 配置所有 Agent 與 Task，並設定執行流程。
    """

    agents: List[BaseAgent]
    tasks: List[Task]

    @agent
    def video_fetch_agent(self) -> Agent:
        """影片資訊提取師：分析影片內容，提取 metadata 與地點、時間軸等資訊。"""
        return Agent(
            llm="gpt-4o-mini",
            config=self.agents_config["video_fetch_agent"],
            max_reasoning_attempts=3,
            max_retry_limit=3,
            verbose=True,
            tools=[
                YoutubeMetadataTool(),
                SerperDevTool(),
                FileReadTool(),
                DirectorySearchTool(),
                ScrapeWebsiteTool(),
            ],
        )

    @agent
    def content_extraction_agent(self) -> Agent:
        """內容重點彙整師：針對主題進行資訊彙整與摘要。"""
        return Agent(
            llm="gpt-4o-mini",
            config=self.agents_config["content_extraction_agent"],
            max_reasoning_attempts=3,
            max_retry_limit=3,
            verbose=True,
            tools=[
                FileReadTool(),
                DirectorySearchTool(),
            ],
        )

    @agent
    def map_visualization_agent(self) -> Agent:
        """地圖可視化設計師：根據地點與時間軸資訊生成地圖路線。"""
        return Agent(
            llm="gpt-4o-mini",
            config=self.agents_config["map_visualization_agent"],
            max_reasoning_attempts=3,
            max_retry_limit=3,
            verbose=True,
            tools=[
                FileReadTool(),
                DirectorySearchTool(),
            ],
        )

    @task
    def video_metadata_extraction_task(self) -> Task:
        """分析 YouTube 影片，提取 metadata 與基本資訊。"""
        return Task(
            config=self.tasks_config["video_metadata_extraction_task"],
            output_file="outputs/video_metadata.json",
            output_json=VideoMapGenerationOutput,
            guardrail=validate_video_map_generation_output,
            max_retries=1,
        )

    @task
    def video_topic_summary_task(self) -> Task:
        """針對主題分析字幕內容，彙整摘要。"""
        return Task(
            config=self.tasks_config["video_topic_summary_task"],
            context=[self.video_metadata_extraction_task()],
            output_file="outputs/video_topic_summary.json",
            # output_json=VideoTopicSummaryOutput,  # 需定義對應模型
        )

    @task
    def map_visualization_task(self) -> Task:
        """分析地點資料產生互動式地圖欄位。"""
        return Task(
            config=self.tasks_config["map_visualization_task"],
            context=[self.video_topic_summary_task()],
            output_file="outputs/map_route.json",
            output_json=MapVisualizationOutput,
        )

    @crew
    def crew(self) -> Crew:
        """建立並返回 Trailtag Crew，依序執行所有任務。"""
        return Crew(
            agents=[
                self.video_fetch_agent(),
                # self.content_extraction_agent(),
                # self.map_visualization_agent(),
            ],
            tasks=[
                self.video_metadata_extraction_task(),
                # self.video_topic_summary_task(),
                # self.map_visualization_task(),
            ],
            process=Process.sequential,
            verbose=True,
            planning=True,
        )
