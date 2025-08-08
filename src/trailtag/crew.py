import logging
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai_tools import (
    ScrapeWebsiteTool,
    SerperDevTool,
    FileReadTool,
    DirectorySearchTool,
)
from .tools.youtube_metadata_tool import YoutubeSubtitleTool

from typing import List
from .models import (
    VideoMapGenerationOutput,
    MapVisualizationOutput,
)

logging.basicConfig(level=logging.INFO)


@CrewBase
class Trailtag:
    """Trailtag crew
    此類別定義了一個名為 Trailtag 的 Crew，包含多個 Agent 和 Task，並設定其執行流程。
    """

    agents: List[BaseAgent]  # 定義 Crew 中的 Agent 列表
    tasks: List[Task]  # 定義 Crew 中的 Task 列表

    @agent
    def video_analysis_agent(self) -> Agent:
        """定義一個名為 video_analysis_agent 的 Agent，分析影片內容，提取地點資訊和時間軸，並結構化存儲。

        Returns:
            Agent: 配置完成的影片內容分析 Agent。
        """
        return Agent(
            llm="gpt-4o-mini",
            config=self.agents_config["video_analysis_agent"],
            # reasoning=True,  # 設定 Agent 進行推理
            max_reasoning_attempts=3,  # 設定最大推理嘗試次數
            max_retry_limit=3,  # 設定最大重試次數
            verbose=True,
            tools=[
                YoutubeSubtitleTool(),  # 獲取 YouTube 影片字幕
                SerperDevTool(),  # 獲取地理資訊參考資料
                FileReadTool(),  # 讀取影片文字稿/字幕檔
                DirectorySearchTool(),  # 搜尋本地檔案
                ScrapeWebsiteTool(),  # 獲取地理資訊參考資料
            ],
        )

    @agent
    def map_visualization_agent(self) -> Agent:
        """定義一個名為 map_visualization_agent 的 Agent，根據提取的地點與時間軸資訊，生成可視化的地圖路線。

        Returns:
            Agent: 配置完成的地圖路線生成 Agent。
        """
        return Agent(
            llm="gpt-4o-mini",
            config=self.agents_config["map_visualization_agent"],
            # reasoning=True,  # 設定 Agent 進行推理
            max_reasoning_attempts=3,  # 設定最大推理嘗試次數
            max_retry_limit=3,  # 設定最大重試次數
            verbose=True,
            tools=[
                FileReadTool(),  # 讀取結構化地點資料
                DirectorySearchTool(),  # 搜尋模板或設定檔
            ],
        )

    @task
    def video_map_generation_task(self) -> Task:
        """定義一個名為 video_map_generation_task 的 Task，用於擷取 YouTube 影片內容並進行基本屬性分析。

        Returns:
            Task: 配置完成的影片擷取與分析任務。
        """
        return Task(
            config=self.tasks_config["video_map_generation_task"],
            output_file="outputs/video_map_info.json",
            output_json=VideoMapGenerationOutput,  # 指定 Pydantic 模型
        )

    @task
    def map_visualization_task(self) -> Task:
        """定義一個名為 map_visualization_task 的 Task，用於生成地圖路線。

        Returns:
            Task: 配置完成的地圖路線生成任務。
        """
        return Task(
            config=self.tasks_config["map_visualization_task"],
            context=[self.video_map_generation_task()],
            output_file="outputs/map_route.json",
            output_json=MapVisualizationOutput,  # 指定 Pydantic 模型
        )

    @crew
    def crew(self) -> Crew:
        """建立並返回 Trailtag Crew。

        Returns:
            Crew: 包含所有定義的 Agent 和 Task 的 Crew，並設定執行流程。
        """
        return Crew(
            # agents=self.agents,
            # tasks=self.tasks,
            agents=[self.video_analysis_agent()],
            tasks=[self.video_map_generation_task()],
            process=Process.sequential,
            verbose=True,
            planning=True,
        )
