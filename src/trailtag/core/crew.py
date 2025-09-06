import os
from dotenv import load_dotenv
from src.api.core.logger_config import get_logger
import datetime
from typing import List, Tuple, Any
from crewai import Agent, Crew, Process, Task, TaskOutput
from crewai.project import CrewBase, before_kickoff, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from src.trailtag.tools.data_extraction.youtube_metadata import YoutubeMetadataTool
from src.trailtag.tools.geocoding.place_geocoder import PlaceGeocodeTool
from src.trailtag.tools.processing.subtitle_chunker import SubtitleChunker
from src.trailtag.tools.data_extraction.description_analyzer import DescriptionAnalyzer
from src.trailtag.tools.data_extraction.chapter_extractor import ChapterExtractor
from src.trailtag.tools.data_extraction.comment_miner import CommentMiner

# CacheManager 將在需要時動態匯入以避免循環依賴
from src.trailtag.core.models import VideoMetadata, VideoTopicSummary, MapVisualization
from src.trailtag.core.observers import get_global_observer
from src.api.monitoring.observability import trace
from src.trailtag.memory.manager import get_memory_manager

# 建立 logger 物件，供全域記錄除錯與執行狀態
logger = get_logger(__name__)
# 設定專案根目錄，便於後續路徑組合
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

load_dotenv(override=True)


def validate_video_map_generation_output(result: TaskOutput) -> Tuple[bool, Any]:
    """
    影片地圖生成輸出驗證函式

    作為 CrewAI Task 的 guardrail 機制，驗證 VideoMetadata 任務輸出的完整性和正確性。
    確保後續任務能夠獲得有效的字幕資料進行分析。

    Args:
        result (TaskOutput): CrewAI 任務執行結果物件
            - 必須包含 pydantic 或 json_dict 屬性
            - 應為 VideoMetadata 模型的實例

    Returns:
        Tuple[bool, Any]: 驗證結果元組
            - bool: 驗證是否通過 (True=成功, False=失敗)
            - Any: 成功時返回驗證後的輸出物件，失敗時返回錯誤訊息字串

    驗證規則:
        1. result 物件必須包含結構化輸出 (pydantic 或 json_dict)
        2. 輸出必須包含非空的 'subtitles' 欄位
        3. subtitles 內容應包含可分析的文本資料

    異常處理:
        - 捕獲所有驗證過程中的例外並記錄到日誌
        - 返回具體的錯誤描述以便除錯

    使用場景:
        - video_metadata_extraction_task 的 guardrail 參數
        - 確保字幕擷取成功後才進入內容分析階段
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
# TrailTag CrewAI 主要執行類別
# 整合所有 Agent、Task 與執行流程控制邏輯
######################################################################
@CrewBase
class Trailtag:
    """
    TrailTag CrewAI 主要執行類別

    這是整個 TrailTag 系統的核心控制器，負責協調三個主要 Agent 的執行流程：
    1. Video Fetch Agent - 影片資訊提取
    2. Content Extraction Agent - 內容重點彙整
    3. Map Visualization Agent - 地圖視覺化生成

    主要職責:
        - Agent 與 Task 的定義和配置管理
        - 執行流程控制與任務依賴關係管理
        - 快取機制與資料持久化處理
        - 執行狀態監控與進度回報
        - 記憶系統整合與上下文管理

    設計模式:
        - 使用 CrewAI 的 @CrewBase 裝飾器實現配置驅動
        - 採用 Sequential Process 確保任務依序執行
        - 整合 Observer 模式進行執行監控
        - 支援非同步執行與狀態追蹤

    配置文件依賴:
        - agents.yaml: Agent 角色與行為定義
        - tasks.yaml: Task 目標與輸出格式定義
        - 環境變數: API 密鑰與執行參數

    執行流程:
        video_id → VideoMetadata → VideoTopicSummary → MapVisualization → GeoJSON

    記憶與快取:
        - CrewAI Memory 系統: 長期記憶與向量搜尋
        - CrewAI Memory: 任務狀態與中間結果
        - 檔案輸出: JSON 格式的執行結果
    """

    # Agent 與 Task 清單，供流程組裝
    agents: List[BaseAgent] = []
    tasks: List[Task] = []
    # 指定 LLM 模型，可切換本地或雲端模型
    # llm = LLM(model="openai/gpt-4o-mini", max_tokens=12000, timeout=300)
    llm = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    # 啟動時的輸入參數
    kickoff_inputs: dict = {}
    # 輸出資料目錄
    outputs_dir = os.path.join(BASE_DIR, "outputs")
    # 外部進度回調函式
    _progress_callback: callable = None

    # Token 限制與分段配置
    MAX_TOKENS_PER_TASK = 3000  # 每個任務的最大 Token 數
    CHUNK_OVERLAP_RATIO = 0.1  # 分段重疊比例

    def __init__(self):
        """
        初始化 TrailTag Crew 執行環境

        設定所有必要的組件和配置，包括字幕處理器、記憶管理器等核心服務。
        此方法在 Crew 實例化時自動調用，確保所有依賴組件正確初始化。

        初始化組件:
            - SubtitleChunker: 處理長字幕的智慧分段器
            - MemoryManager: CrewAI 記憶系統管理器
            - 日誌系統: 執行狀態記錄與監控

        配置參數:
            - MAX_TOKENS_PER_TASK: 單一任務最大 Token 限制
            - CHUNK_OVERLAP_RATIO: 分段重疊比例，確保上下文連續性
            - llm: 指定使用的語言模型 (預設 gpt-4o-mini)

        異常處理:
            - 記憶管理器初始化失敗時使用預設配置
            - 字幕分割器配置錯誤時回退到基本設定
        """
        super().__init__()
        # 初始化字幕分割器，處理長影片字幕的 Token 限制問題
        self.subtitle_chunker = SubtitleChunker(
            max_tokens=self.MAX_TOKENS_PER_TASK,
            model=self.llm,
            overlap_ratio=self.CHUNK_OVERLAP_RATIO,
        )
        # 初始化 CrewAI 記憶管理器，提供向量搜尋與上下文記憶
        self.memory_manager = get_memory_manager()
        logger.info(
            f"Trailtag Crew 初始化完成 - 字幕分割器與記憶管理器已就緒 ({self.llm})"
        )

    @agent
    def video_fetch_agent(self) -> Agent:
        """
        YouTube 影片資訊提取 Agent

        負責從 YouTube 平台獲取影片的完整元數據資訊，包含字幕、描述、章節等所有可用資料。
        這是整個分析流程的第一個階段，為後續分析提供基礎資料。

        主要功能:
            - YouTube API 資料獲取: 影片標題、描述、時間等
            - 字幕系統整合: 手動/自動字幕的智慧選擇
            - 章節結構分析: 提取影片的章節資訊
            - 留言挖掘: 獲取觀眾的地點推薦資訊

        配置特色:
            - 高重試次數: 處理網路不穩定與 API 限制
            - 記憶功能: 避免重複處理相同影片
            - 上下文視窗限制: 智慧管理長內容
            - 多工具整合: 結合多個資料來源

        輸出格式:
            VideoMetadata - 包含完整的影片資訊與字幕內容

        錯誤處理:
            - 字幕不可用: 嘗試多種字幕來源
            - API 限制: 自動重試與指數退縮
            - 長內容處理: 配合字幕分割器使用
        """
        return Agent(
            llm=self.llm,
            config=self.agents_config["video_fetch_agent"],
            # 推理與重試配置
            max_reasoning_attempts=3,
            max_retry_limit=2,  # 增加重試次數以處理 Token 限制
            max_iter=15,  # 限制最大迭代次數避免無限循環
            # 記憶與上下文管理
            memory=True,  # 啟用 Agent 記憶功能
            respect_context_window=True,  # 遵守上下文視窗限制
            verbose=True,
            tools=[
                YoutubeMetadataTool(),
                DescriptionAnalyzer(),
                ChapterExtractor(),
                CommentMiner(),
            ],
        )

    @agent
    def content_extraction_agent(self) -> Agent:
        """
        內容分析與主題提取 Agent

        專門從影片字幕內容中識別與提取旅遊相關的地點、時間和主題資訊。
        這是分析流程的核心階段，將原始字幕轉換為結構化的主題摘要。

        主要能力:
            - 地點識別: 從字幕中精確識別旅遊地點
            - 時間對應: 將地點與影片時間軸建立關聯
            - 主題分類: 根據內容性質進行主題歸納
            - 上下文理解: 提取每個地點的相關資訊

        進階特性:
            - 長文本處理: 自動分段與上下文保持
            - 信心分數評估: 為每個識別結果提供可靠度評分
            - 關聯性分析: 建立地點間的關連關係
            - 多層次推理: 支援複雜的內容理解任務

        模型優化:
            - 更多推理步驟: 處理複雜的內容分析
            - 更長迭代限制: 適應長內容處理需求
            - 記憶功能啟用: 保持上下文連貫性

        輸出格式:
            VideoTopicSummary - 結構化的主題摘要與地點列表
        """
        return Agent(
            llm=self.llm,
            config=self.agents_config["content_extraction_agent"],
            # 推理與重試配置 - 針對內容分析任務優化
            max_reasoning_attempts=5,  # 內容分析需要更多推理步驟
            max_retry_limit=3,
            max_iter=20,  # 處理長內容可能需要更多迭代
            # 記憶與上下文管理
            memory=True,
            respect_context_window=True,
            verbose=True,
            # 暫時不添加工具，將使用內建的分段處理邏輯
            tools=[],
        )

    @agent
    def map_visualization_agent(self) -> Agent:
        """
        地圖視覺化與地理編碼 Agent

        負責將主題摘要中的地點資訊轉換為精確的地理座標，並生成可視化的路線資料。
        這是整個流程的最後階段，產生可以在地圖上顯示的 GeoJSON 資料。

        核心功能:
            - 地理編碼: 使用 Google Geocoding API 獲取精確座標
            - 路線規劃: 按時間順序組織地點成為連貫路線
            - 地點驗證: 確保地理編碼結果的正確性
            - 元数據富化: 為每個地點添加顯示資訊

        地理資料處理:
            - 座標精度優化: 優先選擇高精度結果
            - 地址標準化: 統一地址格式與命名
            - 錯誤容限: 處理地理編碼失敗的情況
            - 效能優化: 批量處理減少 API 呼叫

        輸出品質保證:
            - 座標驗證: WGS84 標準座標系統
            - 路線連貫性: 確保時間順序正確
            - 地圖相容性: 符合主流地圖平台標準

        輸出格式:
            MapVisualization - 包含完整座標資訊的路線資料
        """
        return Agent(
            llm=self.llm,
            config=self.agents_config["map_visualization_agent"],
            # 推理與重試配置 - 地圖生成任務優化
            max_reasoning_attempts=4,  # 地理資料處理需要適度推理
            max_retry_limit=3,
            max_iter=15,
            # 記憶與上下文管理
            memory=True,
            respect_context_window=True,
            verbose=True,
            tools=[PlaceGeocodeTool()],
        )

    def set_progress_callback(self, callback: callable):
        """
        設置外部進度回調函式，用於與 CrewExecutor 整合

        Args:
            callback: 進度回調函式，接收 (progress: float, phase: str) 參數
        """
        self._progress_callback = callback
        logger.info("進度回調函式已設置")

    def _update_job_progress(self, phase, progress, status=None, extra=None):
        """
        於分析流程各階段即時更新 job 狀態與進度到 CrewAI Memory 快取，供 SSE 查詢。
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

        # 調用外部進度回調（如果有設置）
        if self._progress_callback:
            try:
                self._progress_callback(progress, phase)
            except Exception as e:
                logger.error(f"進度回調執行失敗: {e}")

        # 使用延遲匯入避免循環依賴
        from src.api.cache.cache_manager import CacheManager

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

    def _task_callback(self, output: TaskOutput):
        """
        統一的任務回調函式，根據任務名稱更新進度。
        """
        task_name = output.task.config["description"]
        if "metadata" in task_name:
            self._update_job_progress("metadata_completed", 30, status="running")
        elif "summary" in task_name:
            self._update_job_progress("summary_completed", 70, status="running")
        elif "visualization" in task_name:
            self._update_job_progress("geocode_completed", 100, status="done")
            self._store_map_routes_result(output)
        return output

    @task
    def video_metadata_extraction_task(self) -> Task:
        """
        影片 metadata 擷取任務：分析 YouTube 影片，提取 metadata 與基本資訊。
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
        主題摘要任務：針對主題分析字幕內容，彙整摘要。
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
        地圖可視化任務：分析地點資料產生互動式地圖欄位。
        """
        return Task(
            config=self.tasks_config["map_visualization_task"],
            context=[self.video_topic_summary_task()],
            output_file="outputs/map_routes.json",
            output_pydantic=MapVisualization,
        )

    def _store_map_routes_result(self, output: TaskOutput):
        """
        將地圖路線結果存入 CrewAI Memory 快取。
        若 output.pydantic 為空則跳過。
        """
        if output.pydantic is None:
            logger.warning("Output is empty or not structured, skipping storage.")
            return output
        try:
            video_id = self.kickoff_inputs.get("video_id")
            # 同步存入分析結果快取（分析結果 key 統一）
            # 使用延遲匯入避免循環依賴
            from src.api.cache.cache_manager import CacheManager

            cache = CacheManager()
            cache.set(f"analysis:{video_id}", output.pydantic.model_dump())
            logger.info(f"已將地圖路線結果存入 CrewAI Memory 快取: {video_id}")
        except Exception as e:
            logger.error(f"存儲地圖路線結果失敗: {e}")
        return output

    @before_kickoff
    def before_kickoff_function(self, inputs):
        """
        任務啟動前的初始化函式。
        若指定 clear_cache，則清除 CrewAI Memory 快取。
        並將 kickoff inputs 儲存於 self.kickoff_inputs 供 callback 使用。
        """
        logger.info(f"Before kickoff with inputs: {inputs}")
        self.kickoff_inputs = inputs.copy() if isinstance(inputs, dict) else inputs
        # 如果指定了要清除快取，則清除 CrewAI Memory 快取
        if inputs.get("clear_cache", False):
            try:
                # 使用延遲匯入避免循環依賴
                from src.api.cache.cache_manager import CacheManager

                cache = CacheManager()
                # CrewAI Memory 系統使用軟清除方式
                cache.clear()
                logger.info("已發送 CrewAI Memory 快取清除請求")
            except Exception as e:
                logger.error(f"清除 CrewAI Memory 快取失敗: {e}")
        return inputs

    @crew
    def crew(self) -> Crew:
        """
        建立並返回 Trailtag Crew，依序執行所有任務。
        """
        trailtag_instance = self
        observer = get_global_observer()

        crew_instance = Crew(
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
            memory=True,
            task_callback=self._task_callback,
        )

        class ObserverWrappedCrew:
            def __init__(self, crew, observer, trailtag_instance):
                self._crew = crew
                self._observer = observer
                self._trailtag = trailtag_instance

            def __getattr__(self, name):
                return getattr(self._crew, name)

            @trace("crew.kickoff_with_observer")
            def kickoff(self, inputs=None):
                self._trailtag.kickoff_inputs = inputs or {}
                self._trailtag._update_job_progress("starting", 5, status="running")
                self._observer.on_crew_start(self._crew, inputs)
                try:
                    self._trailtag._update_job_progress(
                        "metadata_started", 10, status="running"
                    )
                    result = self._crew.kickoff(inputs)
                    self._observer.on_crew_complete(self._crew, result)
                    return result
                except Exception as e:
                    self._observer.on_crew_complete(self._crew, error=str(e))
                    raise

            @trace("crew.kickoff_async_with_observer")
            async def kickoff_async(self, inputs=None):
                if not hasattr(self._crew, "kickoff_async"):
                    raise AttributeError("Crew 不支援 kickoff_async")
                self._observer.on_crew_start(self._crew, inputs)
                try:
                    result = await self._crew.kickoff_async(inputs)
                    self._observer.on_crew_complete(self._crew, result)
                    return result
                except Exception as e:
                    self._observer.on_crew_complete(self._crew, error=str(e))
                    raise

        return ObserverWrappedCrew(crew_instance, observer, trailtag_instance)
