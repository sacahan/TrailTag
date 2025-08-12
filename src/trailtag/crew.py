import logging
import os
from crewai import LLM, Agent, Crew, Process, Task, TaskOutput
from crewai.project import CrewBase, before_kickoff, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from .tools.youtube_metadata_tool import YoutubeMetadataTool
from .tools.place_geocode_tool import PlaceGeocodeTool
from .tools.subtitle_compression_tool import SubtitleCompressionTool
from .tools.redis_cache_tool import RedisCacheTool

from typing import List, Tuple, Any
from .models import (
    VideoMetadata,
    VideoTopicSummary,
    MapVisualization,
)

# 設定 logging 物件，方便後續記錄執行過程與除錯
logging = logging.getLogger(__name__)

# 執行檔案目錄
base_dir = os.path.dirname(os.path.dirname(__file__))


# --- 任務輸出結構驗證（Guardrail）函式 ---
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
            return (False, "無法取得結構化輸出 (pydantic/json_dict) 或輸出為空")

        # 驗證 subtitles 欄位是否存在且不為空
        value = getattr(output, "subtitles", None)
        print(f"subtitles 欄位值: {value}")  # 除錯輸出

        if value is None:
            print("欄位 'subtitles' 缺失或為空")
            return (False, "欄位 'subtitles' 缺失或為空")

        return (True, output)
    except Exception as e:
        print(f"驗證過程發生例外: {str(e)}")
        return (False, f"驗證過程發生例外: {str(e)}")


# === 主流程 Crew 定義 ===
@CrewBase
class Trailtag:
    """
    Trailtag crew
    根據 agents.yaml 與 tasks.yaml 配置所有 Agent 與 Task，並設定執行流程。
    此類別負責組裝所有 Agent、Task，並處理啟動前初始化、快取、資料儲存等邏輯。
    """

    agents: List[BaseAgent]
    tasks: List[Task]

    # 指定 LLM 模型，可切換本地或雲端模型
    # 可依需求切換本地 ollama 或雲端 OpenAI
    # llm = LLM(model="ollama/llama3.2:1b", base_url="http://localhost:11434")
    # llm = LLM(model="ollama/gemma3:1b", base_url="http://localhost:11434")
    # llm = LLM(model="ollama/deepseek-r1:1.5b", base_url="http://localhost:11434")
    # 預設使用線上 OpenAI GPT-4o-mini
    llm = LLM(
        model="openai/gpt-4o-mini", max_tokens=12000, temperature=0.7, timeout=300
    )
    outputs_dir = os.path.join(base_dir, "outputs")

    @agent
    def video_fetch_agent(self) -> Agent:
        """
        影片資訊提取師 Agent
        負責分析影片內容，提取 metadata、地點、時間軸等資訊。
        主要工具：YoutubeMetadataTool。
        """
        return Agent(
            llm=self.llm,
            config=self.agents_config["video_fetch_agent"],
            reasoning=True,
            max_reasoning_attempts=3,
            max_retry_limit=1,
            verbose=True,
            respect_context_window=False,
            tools=[
                YoutubeMetadataTool(),
            ],
        )

    @agent
    def content_extraction_agent(self) -> Agent:
        """
        內容重點彙整師 Agent
        針對主題進行資訊彙整與摘要。
        主要工具：字幕壓縮工具、向量資料庫。
        """
        return Agent(
            llm=self.llm,
            config=self.agents_config["content_extraction_agent"],
            reasoning=True,
            max_reasoning_attempts=3,
            max_retry_limit=3,
            verbose=True,
            respect_context_window=False,
            tools=[
                SubtitleCompressionTool(),  # 長字幕壓縮工具
            ],
        )

    @agent
    def map_visualization_agent(self) -> Agent:
        """
        地圖可視化設計師 Agent
        根據地點與時間軸資訊生成地圖路線。
        主要工具：地理編碼工具、向量資料庫。
        """
        return Agent(
            llm=self.llm,
            config=self.agents_config["map_visualization_agent"],
            reasoning=True,
            max_reasoning_attempts=3,
            max_retry_limit=3,
            verbose=True,
            respect_context_window=False,
            tools=[
                PlaceGeocodeTool(),
            ],
        )

    @task
    def video_metadata_extraction_task(self) -> Task:
        """
        影片 metadata 擷取任務
        分析 YouTube 影片，提取 metadata 與基本資訊。
        任務完成後會將結果存入向量資料庫。
        """
        return Task(
            config=self.tasks_config["video_metadata_extraction_task"],
            output_file="outputs/video_metadata.json",
            output_pydantic=VideoMetadata,
            guardrail=validate_video_map_generation_output,
            max_retries=3,
        )

    @task
    def video_topic_summary_task(self) -> Task:
        """
        主題摘要任務
        針對主題分析字幕內容，彙整摘要。
        依賴 video_metadata_extraction_task 的結果作為 context。
        """
        return Task(
            config=self.tasks_config["video_topic_summary_task"],
            context=[self.video_metadata_extraction_task()],
            output_file="outputs/topic_summary.json",
            output_pydantic=VideoTopicSummary,
        )

    @task
    def map_visualization_task(self) -> Task:
        """
        地圖可視化任務
        分析地點資料產生互動式地圖欄位。
        依賴 video_topic_summary_task 的結果作為 context。
        """
        return Task(
            config=self.tasks_config["map_visualization_task"],
            context=[self.video_topic_summary_task()],
            output_file="outputs/map_routes.json",
            output_pydantic=MapVisualization,
            callback=self._store_map_routes_result,
        )

    def _store_map_routes_result(self, output: TaskOutput):
        """
        將地圖路線結果存入 Redis 快取
        kickoff inputs 可由 self.kickoff_inputs 取得。
        """
        if output.pydantic is None:
            print("Output is empty or not structured, skipping storage.")
            return output

        try:
            kickoff_inputs = getattr(self, "kickoff_inputs", {})
            youtube_url = kickoff_inputs.get("youtube_video_url")

            # 存入 Redis 快取，加速下次查詢
            redis_tool = RedisCacheTool(prefix="trailtag:map_routes:")
            redis_tool.set(youtube_url, output.pydantic.model_dump())
            print(f">>> 已將地圖路線結果存入 Redis 快取: {youtube_url}")
        except Exception as e:
            print(f"存儲地圖路線結果失敗: {str(e)}")
        return output

    @before_kickoff
    def before_kickoff_function(self, inputs):
        """
        任務啟動前的初始化函式

        若指定 clear_cache，則清除 Redis 快取。
        並將 kickoff inputs 儲存於 self.kickoff_inputs 供 callback 使用。
        """
        print(f"--- Before kickoff function with inputs: {inputs} ---")
        self.kickoff_inputs = inputs.copy() if isinstance(inputs, dict) else inputs

        # 如果指定了要清除快取，則清除 Redis 中所有 trailtag:* 相關快取
        if inputs.get("clear_cache", False):
            try:
                redis_tool = RedisCacheTool()
                cleared = redis_tool.clear_all("trailtag:*")
                if cleared:
                    print(f"已清除 {cleared} 個 Redis 快取")
            except Exception as e:
                print(f"清除 Redis 快取失敗: {str(e)}")

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
