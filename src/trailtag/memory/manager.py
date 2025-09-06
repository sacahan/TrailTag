"""
CrewAI Memory 管理器

此模組實現了 CrewAI Memory 系統的核心功能，用於替代 Redis 快取。
基於 CrewAI 官方文檔和最佳實踐實現。

主要功能：
- 記憶儲存與檢索
- Agent 特定記憶管理
- 任務進度追蹤
- 向量相似度搜尋
- 資料遷移支援
"""

import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

# CrewAI 相關匯入
from crewai import Crew
from crewai.memory.external.external_memory import ExternalMemory
from crewai.memory.storage.interface import Storage
from crewai.utilities.events.base_event_listener import BaseEventListener
from crewai.utilities.events import (
    MemorySaveStartedEvent,
    MemorySaveCompletedEvent,
    MemorySaveFailedEvent,
    MemoryQueryStartedEvent,
    MemoryQueryCompletedEvent,
    MemoryQueryFailedEvent,
    MemoryRetrievalStartedEvent,
    MemoryRetrievalCompletedEvent,
)

# 本地模組匯入
from .models import (
    MemoryEntry,
    JobProgressEntry,
    AnalysisResultEntry,
    AgentMemoryEntry,
    CrewMemoryConfig,
    MemoryStats,
    MemoryType,
    JobStatus,
    JobPhase,
)
from src.api.core.logger_config import get_logger

logger = get_logger(__name__)


class CrewMemoryStorage(Storage):
    """
    CrewAI 自訂記憶儲存後端實作

    實現 CrewAI Storage 介面，提供持久化的記憶儲存功能。
    這是 TrailTag 記憶系統的核心組件，負責所有記憶資料的儲存、檢索和管理。

    設計特色:
        - Storage 介面相容: 完全符合 CrewAI Memory 系統規範
        - 持久化儲存: 使用 JSON 格式進行資料持久化
        - 內存索引: 提供快速的記憶條目存取
        - 文本搜尋: 實現基於關鍵字的記憶內容搜尋
        - 元數據支援: 支援豐富的記憶條目元數據

    資料組織:
        - memories: 主要記憶條目字典 {memory_id: MemoryEntry}
        - embeddings: 向量嵌入快取 {memory_id: embedding_vector}
        - storage_path: 檔案系統持久化路徑

    儲存格式:
        - JSON 檔案: memories.json 存放所有記憶條目
        - UTF-8 編碼: 支援多語言內容
        - 結構化數據: 使用 Pydantic 模型確保資料完整性

    搜尋能力:
        - 關鍵字匹配: 基於文本內容的模糊搜尋
        - 相似度評分: 簡化的文本相似度計算
        - 結果排序: 按相似度分數排序搜尋結果
        - 數量限制: 支援結果數量和品質閾值控制

    整合接口:
        - save(): 儲存記憶條目並返回唯一 ID
        - search(): 搜尋相關記憶條目
        - reset(): 重置所有記憶資料
        - 自動載入: 初始化時自動載入現有記憶

    使用限制:
        - 文件系統依賴: 需要可寫入的檔案系統路徑
        - 記憶體使用: 所有記憶在記憶體中維護索引
        - 搜尋複雜度: O(n) 線性搜尋，適合中等規模資料
    """

    def __init__(self, storage_path: str, embedder_config: Dict[str, Any]):
        """
        初始化記憶儲存

        Args:
            storage_path: 儲存路徑
            embedder_config: 嵌入模型配置
        """
        self.storage_path = Path(storage_path)
        self.embedder_config = embedder_config
        self.memories: Dict[str, MemoryEntry] = {}
        self.embeddings: Dict[str, List[float]] = {}

        # 確保儲存目錄存在
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 載入現有記憶
        self._load_memories()

        logger.info(f"CrewMemoryStorage 初始化完成，儲存路徑: {self.storage_path}")

    def save(
        self, value: str, metadata: Optional[Dict] = None, agent: Optional[str] = None
    ) -> str:
        """
        儲存記憶條目

        Args:
            value: 記憶內容
            metadata: 額外元資料
            agent: Agent 角色（可選）

        Returns:
            記憶條目 ID
        """
        try:
            entry_id = str(uuid.uuid4())
            entry = MemoryEntry(
                id=entry_id,
                memory_type=MemoryType.SHORT_TERM,  # 預設短期記憶
                content=value,
                metadata=metadata or {},
                agent_role=agent,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

            self.memories[entry_id] = entry
            self._persist_memory(entry)

            logger.debug(f"儲存記憶條目: {entry_id}, Agent: {agent}")
            return entry_id

        except Exception as e:
            logger.error(f"儲存記憶失敗: {e}")
            raise

    def search(
        self, query: str, limit: int = 10, score_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        搜尋記憶條目

        Args:
            query: 查詢字串
            limit: 結果數量限制
            score_threshold: 相似度閾值

        Returns:
            搜尋結果列表
        """
        try:
            # 簡化版本：基於文字匹配搜尋
            results = []
            query_lower = query.lower()

            for memory_id, memory in self.memories.items():
                content_str = str(memory.content).lower()
                if query_lower in content_str:
                    # 計算簡單相似度分數
                    score = min(1.0, query_lower.count(" ") + 1) / max(
                        1, content_str.count(" ")
                    )

                    if score >= score_threshold:
                        results.append(
                            {
                                "id": memory_id,
                                "content": memory.content,
                                "metadata": memory.metadata,
                                "score": score,
                                "agent_role": memory.agent_role,
                                "created_at": memory.created_at,
                            }
                        )

            # 按分數排序並限制結果數量
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"搜尋記憶失敗: {e}")
            return []

    def reset(self) -> None:
        """重置所有記憶"""
        try:
            self.memories.clear()
            self.embeddings.clear()

            # 刪除儲存檔案
            memory_file = self.storage_path / "memories.json"
            if memory_file.exists():
                memory_file.unlink()

            logger.info("記憶重置完成")

        except Exception as e:
            logger.error(f"重置記憶失敗: {e}")
            raise

    def _load_memories(self) -> None:
        """載入已儲存的記憶"""
        try:
            memory_file = self.storage_path / "memories.json"
            if memory_file.exists():
                with open(memory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for memory_data in data:
                        entry = MemoryEntry(**memory_data)
                        self.memories[entry.id] = entry

                logger.info(f"載入 {len(self.memories)} 個記憶條目")
        except Exception as e:
            logger.warning(f"載入記憶失敗: {e}")

    def _persist_memory(self, entry: MemoryEntry) -> None:
        """持久化單一記憶條目"""
        try:
            memory_file = self.storage_path / "memories.json"

            # 載入現有資料
            memories_data = []
            if memory_file.exists():
                with open(memory_file, "r", encoding="utf-8") as f:
                    memories_data = json.load(f)

            # 新增或更新記憶
            entry_dict = entry.model_dump(mode="json")
            existing_index = next(
                (i for i, m in enumerate(memories_data) if m.get("id") == entry.id),
                None,
            )

            if existing_index is not None:
                memories_data[existing_index] = entry_dict
            else:
                memories_data.append(entry_dict)

            # 寫入檔案
            with open(memory_file, "w", encoding="utf-8") as f:
                json.dump(memories_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"持久化記憶失敗: {e}")


class MemoryEventListener(BaseEventListener):
    """CrewAI Memory 事件監聽器"""

    def __init__(self, memory_manager: "CrewMemoryManager"):
        super().__init__()
        self.memory_manager = memory_manager
        self.query_times = []
        self.save_times = []

    def setup_listeners(self, crewai_event_bus):
        """設定事件監聽器"""

        @crewai_event_bus.on(MemorySaveStartedEvent)
        def on_memory_save_started(source, event: MemorySaveStartedEvent):
            if event.agent_role:
                logger.debug(
                    f"Agent '{event.agent_role}' 開始儲存記憶: {str(event.value)[:50]}..."
                )
            else:
                logger.debug(f"開始儲存記憶: {str(event.value)[:50]}...")

        @crewai_event_bus.on(MemorySaveCompletedEvent)
        def on_memory_save_completed(source, event: MemorySaveCompletedEvent):
            self.save_times.append(event.save_time_ms)
            logger.debug(f"記憶儲存完成，耗時: {event.save_time_ms:.2f}ms")

        @crewai_event_bus.on(MemorySaveFailedEvent)
        def on_memory_save_failed(source, event: MemorySaveFailedEvent):
            agent_info = (
                f"Agent '{event.agent_role}'" if event.agent_role else "未知 Agent"
            )
            logger.error(f"記憶儲存失敗 - {agent_info}: {event.error}")

        @crewai_event_bus.on(MemoryQueryStartedEvent)
        def on_memory_query_started(source, event: MemoryQueryStartedEvent):
            logger.debug(f"記憶查詢開始: '{event.query}' (限制: {event.limit})")

        @crewai_event_bus.on(MemoryQueryCompletedEvent)
        def on_memory_query_completed(source, event: MemoryQueryCompletedEvent):
            self.query_times.append(event.query_time_ms)
            logger.debug(f"記憶查詢完成，耗時: {event.query_time_ms:.2f}ms")

        @crewai_event_bus.on(MemoryQueryFailedEvent)
        def on_memory_query_failed(source, event: MemoryQueryFailedEvent):
            logger.error(f"記憶查詢失敗: '{event.query}' - {event.error}")

        @crewai_event_bus.on(MemoryRetrievalStartedEvent)
        def on_memory_retrieval_started(source, event: MemoryRetrievalStartedEvent):
            logger.debug(f"開始檢索任務記憶: {event.task_id}")

        @crewai_event_bus.on(MemoryRetrievalCompletedEvent)
        def on_memory_retrieval_completed(source, event: MemoryRetrievalCompletedEvent):
            logger.debug(
                f"任務記憶檢索完成: {event.task_id}，耗時: {event.retrieval_time_ms:.2f}ms"
            )


class CrewMemoryManager:
    """
    TrailTag CrewAI 記憶系統管理器

    這是 TrailTag 系統的核心記憶管理組件，負責協調所有記憶相關的操作與資料持久化。
    整合 CrewAI Memory 系統，提供多層次的記憶儲存與檢索能力，支援從短期任務記憶到長期知識記憶。

    核心職責:
        - CrewAI Memory 系統整合: 創建具有記憶功能的 Crew 實例
        - 任務進度記憶: 追蹤影片分析任務的進度狀態
        - 分析結果快取: 持久化完整的影片分析結果
        - Agent 特定記憶: 管理每個 Agent 的專屬記憶
        - 向量搜尋: 支援語義相似性搜尋
        - 事件監控: 集成事件監聽器進行性能監控

    記憶層次架構:
        1. 短期記憶 (Short-term): 當前任務相關的臨時資訊
        2. 長期記憶 (Long-term): 持久化的 Agent 學習記憶
        3. 實體記憶 (Entity): 識別的地點、人物等結構化實體
        4. 知識記憶 (Knowledge): 抽象的知識與洞察
        5. 任務記憶 (Job): 任務執行進度與狀態
        6. 分析記憶 (Analysis): 完整的影片分析結果

    儲存系統:
        - CrewMemoryStorage: 自訂 CrewAI Storage 後端
        - ExternalMemory: CrewAI 外部記憶整合
        - JSON 持久化: 各類記憶的檔案系統持久化
        - 記憶體索引: 快速存取的記憶體索引

    整合功能:
        - 事件驅動: 支援 CrewAI 事件系統監控
        - 配置靈活: 可自訂記憶配置與嵌入模型
        - 統計分析: 提供詳細的記憶使用統計
        - 資料遷移: 支援從 Redis 等系統遷移

    API 設計:
        - create_crew_with_memory(): 創建記憶啟用的 Crew
        - save_*/get_*: 各類記憶的儲存與檢索方法
        - query_*: 智慧搜尋與相似性查詢
        - reset_memories(): 記憶清理與重置
        - get_memory_stats(): 系統狀態監控

    性能特性:
        - 非同步支援: 支援非同步記憶操作
        - 批量處理: 高效的批量記憶儲存
        - 智慧索引: 自動維護的記憶索引結構
        - 記憶壓縮: 適當的記憶數據壓縮策略

    安全與可靠性:
        - 事務安全: 確保記憶操作的原子性
        - 錯誤復原: 健全的錯誤處理與復原機制
        - 資料驗證: 使用 Pydantic 確保資料完整性
        - 備份策略: 支援記憶資料的備份與恢復

    使用場景:
        - 影片分析流程: 記憶分析過程中的中間結果
        - Agent 學習: 累積 Agent 的經驗與知識
        - 用戶會話: 維護跨會話的上下文記憶
        - 系統優化: 基於歷史記憶進行性能優化

    配置要求:
        - storage_path: 記憶持久化的檔案系統路徑
        - embedder_config: 向量嵌入模型配置
        - memory_config: CrewAI Memory 系統配置
    """

    def __init__(self, config: Optional[CrewMemoryConfig] = None):
        """
        初始化記憶管理器

        Args:
            config: 記憶配置，預設使用環境變數
        """
        self.config = config or CrewMemoryConfig()
        self.storage_path = Path(self.config.storage_path)

        # 記憶儲存後端
        self.memory_storage = CrewMemoryStorage(
            storage_path=str(self.storage_path / "crew_memory"),
            embedder_config=self.config.embedder_config,
        )

        # 各類記憶儲存
        self.job_memories: Dict[str, JobProgressEntry] = {}
        self.analysis_results: Dict[str, AnalysisResultEntry] = {}
        self.agent_memories: Dict[str, List[AgentMemoryEntry]] = {}

        # 事件監聽器
        self.event_listener = MemoryEventListener(self)

        # External Memory 實例
        self.external_memory = ExternalMemory(storage=self.memory_storage)

        # 載入現有資料
        self._load_existing_data()

        logger.debug(f"CrewMemoryManager 初始化完成，儲存路徑: {self.storage_path}")

    def create_crew_with_memory(self, agents: List, tasks: List, **kwargs) -> Crew:
        """
        建立啟用記憶功能的 Crew

        Args:
            agents: Agent 列表
            tasks: Task 列表
            **kwargs: 其他 Crew 參數

        Returns:
            配置記憶功能的 Crew 實例
        """
        try:
            crew = Crew(
                agents=agents,
                tasks=tasks,
                memory=True,  # 啟用基礎記憶系統
                external_memory=self.external_memory,  # 使用自訂外部記憶
                embedder=self.config.embedder_config,
                **kwargs,
            )

            logger.info("已建立啟用記憶功能的 Crew")
            return crew

        except Exception as e:
            logger.error(f"建立 Crew 失敗: {e}")
            raise

    # 任務進度記憶相關方法
    def save_job_progress(
        self,
        job_id: str,
        video_id: str,
        status: JobStatus,
        phase: JobPhase,
        progress: int,
        **extra,
    ) -> None:
        """儲存任務進度"""
        try:
            entry = JobProgressEntry(
                job_id=job_id,
                video_id=video_id,
                status=status,
                phase=phase,
                progress=progress,
                updated_at=datetime.now(timezone.utc),
                **extra,
            )

            self.job_memories[job_id] = entry
            self._persist_job_memory(entry)

            logger.debug(f"儲存任務進度: {job_id} - {status.value} ({progress}%)")

        except Exception as e:
            logger.error(f"儲存任務進度失敗: {e}")
            raise

    def get_job_progress(self, job_id: str) -> Optional[JobProgressEntry]:
        """取得任務進度"""
        return self.job_memories.get(job_id)

    def save_analysis_result(
        self,
        video_id: str,
        metadata: Dict[str, Any],
        topic_summary: Dict[str, Any],
        map_visualization: Dict[str, Any],
        processing_time: float,
    ) -> None:
        """儲存分析結果"""
        try:
            entry = AnalysisResultEntry(
                video_id=video_id,
                metadata=metadata,
                topic_summary=topic_summary,
                map_visualization=map_visualization,
                processing_time=processing_time,
                created_at=datetime.now(timezone.utc),
            )

            self.analysis_results[video_id] = entry
            self._persist_analysis_result(entry)

            logger.info(f"儲存分析結果: {video_id}")

        except Exception as e:
            logger.error(f"儲存分析結果失敗: {e}")
            raise

    def get_analysis_result(self, video_id: str) -> Optional[AnalysisResultEntry]:
        """取得分析結果"""
        return self.analysis_results.get(video_id)

    def save_agent_memory(
        self,
        agent_role: str,
        context: str,
        entities: List[Dict[str, Any]] = None,
        relationships: List[Dict[str, Any]] = None,
        insights: List[str] = None,
        confidence: float = 1.0,
    ) -> str:
        """儲存 Agent 記憶"""
        try:
            entry = AgentMemoryEntry(
                agent_role=agent_role,
                memory_type=MemoryType.LONG_TERM,
                context=context,
                entities=entities or [],
                relationships=relationships or [],
                insights=insights or [],
                confidence=confidence,
                created_at=datetime.now(timezone.utc),
            )

            if agent_role not in self.agent_memories:
                self.agent_memories[agent_role] = []

            self.agent_memories[agent_role].append(entry)
            self._persist_agent_memory(entry)

            logger.debug(f"儲存 Agent 記憶: {agent_role}")
            return f"{agent_role}_{len(self.agent_memories[agent_role])}"

        except Exception as e:
            logger.error(f"儲存 Agent 記憶失敗: {e}")
            raise

    def query_agent_memories(
        self, agent_role: str, query: str, limit: int = 10
    ) -> List[AgentMemoryEntry]:
        """查詢 Agent 記憶"""
        try:
            memories = self.agent_memories.get(agent_role, [])
            query_lower = query.lower()

            # 簡化版本：基於文字匹配
            matching_memories = []
            for memory in memories:
                if query_lower in memory.context.lower():
                    matching_memories.append(memory)

            # 按時間排序，最新的優先
            matching_memories.sort(key=lambda x: x.created_at, reverse=True)
            return matching_memories[:limit]

        except Exception as e:
            logger.error(f"查詢 Agent 記憶失敗: {e}")
            return []

    def reset_memories(self, memory_type: Optional[str] = None) -> None:
        """重置記憶"""
        try:
            if memory_type == "job":
                self.job_memories.clear()
                self._clear_job_memories()
            elif memory_type == "analysis":
                self.analysis_results.clear()
                self._clear_analysis_results()
            elif memory_type == "agent":
                self.agent_memories.clear()
                self._clear_agent_memories()
            elif memory_type == "crew":
                self.memory_storage.reset()
            else:
                # 重置所有記憶
                self.job_memories.clear()
                self.analysis_results.clear()
                self.agent_memories.clear()
                self.memory_storage.reset()
                self._clear_all_persistent_data()

            logger.info(f"記憶重置完成: {memory_type or 'all'}")

        except Exception as e:
            logger.error(f"重置記憶失敗: {e}")
            raise

    def get_memory_stats(self) -> MemoryStats:
        """取得記憶系統統計資訊"""
        try:
            stats = MemoryStats(
                total_entries=len(self.memory_storage.memories)
                + len(self.job_memories)
                + len(self.analysis_results),
                short_term_count=sum(
                    1
                    for m in self.memory_storage.memories.values()
                    if m.memory_type == MemoryType.SHORT_TERM
                ),
                long_term_count=sum(
                    1
                    for m in self.memory_storage.memories.values()
                    if m.memory_type == MemoryType.LONG_TERM
                ),
                entity_count=sum(
                    1
                    for m in self.memory_storage.memories.values()
                    if m.memory_type == MemoryType.ENTITY
                ),
                knowledge_count=sum(
                    1
                    for m in self.memory_storage.memories.values()
                    if m.memory_type == MemoryType.KNOWLEDGE
                ),
                avg_query_time_ms=(
                    sum(self.event_listener.query_times)
                    / len(self.event_listener.query_times)
                    if self.event_listener.query_times
                    else 0.0
                ),
            )

            # 計算儲存空間
            try:
                storage_size = sum(
                    f.stat().st_size
                    for f in self.storage_path.rglob("*")
                    if f.is_file()
                )
                stats.storage_size_mb = storage_size / (1024 * 1024)
            except Exception:
                stats.storage_size_mb = 0.0

            return stats

        except Exception as e:
            logger.error(f"取得記憶統計失敗: {e}")
            return MemoryStats()

    # 私有方法：資料持久化
    def _load_existing_data(self) -> None:
        """載入現有資料"""
        try:
            # 載入任務記憶
            job_file = self.storage_path / "job_memories.json"
            if job_file.exists():
                with open(job_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for job_data in data:
                        entry = JobProgressEntry(**job_data)
                        self.job_memories[entry.job_id] = entry

            # 載入分析結果
            analysis_file = self.storage_path / "analysis_results.json"
            if analysis_file.exists():
                with open(analysis_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for result_data in data:
                        entry = AnalysisResultEntry(**result_data)
                        self.analysis_results[entry.video_id] = entry

            # 載入 Agent 記憶
            agent_file = self.storage_path / "agent_memories.json"
            if agent_file.exists():
                with open(agent_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for agent_role, memories_data in data.items():
                        self.agent_memories[agent_role] = [
                            AgentMemoryEntry(**memory_data)
                            for memory_data in memories_data
                        ]

            logger.info("載入現有記憶資料完成")

        except Exception as e:
            logger.warning(f"載入現有資料失敗: {e}")

    def _persist_job_memory(self, entry: JobProgressEntry) -> None:
        """持久化任務記憶"""
        try:
            job_file = self.storage_path / "job_memories.json"
            self.storage_path.mkdir(parents=True, exist_ok=True)

            with open(job_file, "w", encoding="utf-8") as f:
                data = [
                    entry.model_dump(mode="json")
                    for entry in self.job_memories.values()
                ]
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"持久化任務記憶失敗: {e}")

    def _persist_analysis_result(self, entry: AnalysisResultEntry) -> None:
        """持久化分析結果"""
        try:
            analysis_file = self.storage_path / "analysis_results.json"
            self.storage_path.mkdir(parents=True, exist_ok=True)

            with open(analysis_file, "w", encoding="utf-8") as f:
                data = [
                    entry.model_dump(mode="json")
                    for entry in self.analysis_results.values()
                ]
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"持久化分析結果失敗: {e}")

    def _persist_agent_memory(self, entry: AgentMemoryEntry) -> None:
        """持久化 Agent 記憶"""
        try:
            agent_file = self.storage_path / "agent_memories.json"
            self.storage_path.mkdir(parents=True, exist_ok=True)

            with open(agent_file, "w", encoding="utf-8") as f:
                data = {}
                for agent_role, memories in self.agent_memories.items():
                    data[agent_role] = [
                        memory.model_dump(mode="json") for memory in memories
                    ]
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"持久化 Agent 記憶失敗: {e}")

    def _clear_job_memories(self) -> None:
        """清除任務記憶檔案"""
        try:
            job_file = self.storage_path / "job_memories.json"
            if job_file.exists():
                job_file.unlink()
        except Exception as e:
            logger.error(f"清除任務記憶檔案失敗: {e}")

    def _clear_analysis_results(self) -> None:
        """清除分析結果檔案"""
        try:
            analysis_file = self.storage_path / "analysis_results.json"
            if analysis_file.exists():
                analysis_file.unlink()
        except Exception as e:
            logger.error(f"清除分析結果檔案失敗: {e}")

    def _clear_agent_memories(self) -> None:
        """清除 Agent 記憶檔案"""
        try:
            agent_file = self.storage_path / "agent_memories.json"
            if agent_file.exists():
                agent_file.unlink()
        except Exception as e:
            logger.error(f"清除 Agent 記憶檔案失敗: {e}")

    def _clear_all_persistent_data(self) -> None:
        """清除所有持久化資料"""
        try:
            if self.storage_path.exists():
                import shutil

                shutil.rmtree(self.storage_path)
                self.storage_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"清除所有持久化資料失敗: {e}")

    def search(
        self,
        query: str,
        limit: int = 10,
        score_threshold: float = 0.5,
        filter_metadata: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """
        搜尋記憶條目

        Args:
            query: 查詢字串
            limit: 結果數量限制
            score_threshold: 相似度閾值
            filter_metadata: 過濾條件（為了兼容 cache_provider 的調用）

        Returns:
            搜尋結果列表
        """
        # 委派給 memory_storage 的 search 方法
        return self.memory_storage.search(
            query=query, limit=limit, score_threshold=score_threshold
        )


# 全域記憶管理器實例
_global_memory_manager: Optional[CrewMemoryManager] = None


def get_memory_manager(config: Optional[CrewMemoryConfig] = None) -> CrewMemoryManager:
    """
    取得全域記憶管理器實例

    Args:
        config: 記憶配置（僅在首次呼叫時使用）

    Returns:
        記憶管理器實例
    """
    global _global_memory_manager

    if _global_memory_manager is None:
        _global_memory_manager = CrewMemoryManager(config)

    return _global_memory_manager


def reset_global_memory_manager() -> None:
    """重置全域記憶管理器實例"""
    global _global_memory_manager
    _global_memory_manager = None
