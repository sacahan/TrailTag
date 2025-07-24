from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai_tools import YoutubeChannelSearchTool, YoutubeVideoSearchTool
from typing import List


@CrewBase
class Trailtag:
    """Trailtag crew
    此類別定義了一個名為 Trailtag 的 Crew，包含多個 Agent 和 Task，並設定其執行流程。
    """

    agents: List[BaseAgent]  # 定義 Crew 中的 Agent 列表
    tasks: List[Task]  # 定義 Crew 中的 Task 列表

    @agent
    def youtube_video_agent(self) -> Agent:
        """定義一個名為 youtube_video_agent 的 Agent，用於擷取影片清單。

        Returns:
            Agent: 配置完成的影片清單擷取 Agent。
        """
        return Agent(
            llm="gpt-4o-mini",  # 使用 gpt-4o-mini 模型
            config=self.agents_config[
                "youtube_video_agent"
            ],  # 使用配置中的影片清單擷取器設定
            tools=[
                YoutubeChannelSearchTool(),
                YoutubeVideoSearchTool(),
            ],  # 使用 YouTube 頻道和影片搜尋工具
            verbose=True,  # 啟用詳細日誌輸出
            expertise_level="Expert",  # 設定專業等級為專家
        )

    @agent
    def travel_video_agent(self) -> Agent:
        """定義一個名為 travel_video_agent 的 Agent，用於過濾旅遊影片。

        Returns:
            Agent: 配置完成的旅遊影片過濾 Agent。
        """
        return Agent(
            llm="gpt-4o-mini",  # 使用 gpt-4o-mini 模型
            config=self.agents_config[
                "travel_video_agent"
            ],  # 使用配置中的旅遊影片過濾器設定
            verbose=True,  # 啟用詳細日誌輸出
            expertise_level="Expert",  # 設定專業等級為專家
        )

    @task
    def youtube_fetch_task(self) -> Task:
        """定義一個名為 youtube_fetch_task 的 Task，用於執行 YouTube 影片擷取任務。

        Returns:
            Task: 配置完成的 YouTube 影片擷取任務。
        """
        return Task(
            config=self.tasks_config[
                "youtube_fetch_task"
            ],  # 使用配置中的 YouTube 影片擷取任務設定
        )

    @task
    def video_check_task(self) -> Task:
        """定義一個名為 video_check_task 的 Task，用於執行影片過濾任務。

        Returns:
            Task: 配置完成的影片過濾任務，並將輸出寫入指定檔案。
        """
        return Task(
            config=self.tasks_config[
                "video_check_task"
            ],  # 使用配置中的影片過濾任務設定
            output_file="outputs/videos.md",  # 指定輸出檔案路徑
        )

    @crew
    def crew(self) -> Crew:
        """建立並返回 Trailtag Crew。

        Returns:
            Crew: 包含所有定義的 Agent 和 Task 的 Crew，並設定執行流程。
        """
        return Crew(
            agents=self.agents,  # 自動由 @agent 裝飾器創建的 Agent 列表
            tasks=self.tasks,  # 自動由 @task 裝飾器創建的 Task 列表
            process=Process.sequential,  # 設定執行流程為順序執行
            verbose=True,  # 啟用詳細日誌輸出
            # process=Process.hierarchical, # 如果需要使用分層執行流程，可啟用此設定
        )
