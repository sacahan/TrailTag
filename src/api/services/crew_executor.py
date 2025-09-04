"""
CrewAI 執行管理整合模組
提供異步執行、狀態查詢、結果管理等功能，整合 CrewAI Memory 系統。
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import threading

from crewai import Crew
from src.api.core.logger_config import get_logger
from src.api.cache.cache_manager import CacheManager
from src.trailtag.memory.manager import get_memory_manager
from src.trailtag.memory.models import JobStatus, JobPhase
from src.api.monitoring.observability import trace

logger = get_logger(__name__)


class ExecutionStatus(str, Enum):
    """執行狀態枚舉"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionJob:
    """執行任務資料結構"""

    job_id: str
    crew_name: str
    inputs: Dict[str, Any]
    status: ExecutionStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    phase: str = "initializing"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            "job_id": self.job_id,
            "crew_name": self.crew_name,
            "inputs": self.inputs,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "progress": self.progress,
            "phase": self.phase,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata or {},
        }


class CrewExecutor:
    """
    CrewAI 執行管理器

    功能：
    1. 異步執行 Crew 任務
    2. 狀態追蹤和查詢
    3. 結果持久化
    4. 錯誤處理和重試
    5. 進度回調
    """

    def __init__(self, max_concurrent_jobs: int = 5):
        """初始化執行器"""
        self.max_concurrent_jobs = max_concurrent_jobs
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_jobs)
        self.cache = CacheManager()
        self.memory_manager = get_memory_manager()
        self.running_jobs: Dict[str, ExecutionJob] = {}
        self.job_futures: Dict[str, asyncio.Future] = {}
        self._lock = threading.RLock()

        logger.info(
            f"CrewExecutor initialized with {max_concurrent_jobs} max concurrent jobs"
        )

    def generate_job_id(self) -> str:
        """生成唯一的任務ID"""
        return str(uuid.uuid4())

    @trace("crew_executor.submit_job")
    async def submit_job(
        self,
        crew: Crew,
        inputs: Dict[str, Any],
        job_id: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float, str], None]] = None,
    ) -> str:
        """
        提交 Crew 執行任務

        Args:
            crew: CrewAI Crew 實例
            inputs: 執行輸入參數
            job_id: 可選的任務ID，如果不提供會自動生成
            progress_callback: 進度回調函數

        Returns:
            str: 任務ID
        """
        if job_id is None:
            job_id = self.generate_job_id()

        # 檢查是否已存在同樣的任務
        if job_id in self.running_jobs:
            raise ValueError(f"Job {job_id} already exists")

        # 創建執行任務
        job = ExecutionJob(
            job_id=job_id,
            crew_name=crew.__class__.__name__,
            inputs=inputs.copy(),
            status=ExecutionStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            metadata={"progress_callback": progress_callback is not None},
        )

        # 存儲到快取
        await self._store_job(job)

        with self._lock:
            self.running_jobs[job_id] = job

        # 異步執行
        future = asyncio.create_task(self._execute_job(crew, job, progress_callback))
        self.job_futures[job_id] = future

        logger.info(f"Submitted job {job_id} for crew {crew.__class__.__name__}")
        return job_id

    async def _execute_job(
        self,
        crew: Crew,
        job: ExecutionJob,
        progress_callback: Optional[Callable[[str, float, str], None]] = None,
    ) -> None:
        """執行 Crew 任務的內部方法"""
        try:
            # 更新狀態為執行中
            job.status = ExecutionStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            job.phase = "starting"
            await self._update_job_status(job, progress_callback)

            # 在線程池中執行同步的 Crew
            loop = asyncio.get_event_loop()

            def run_crew():
                try:
                    # 設定進度回調（如果 crew 支持）
                    if hasattr(crew, "set_progress_callback"):

                        def internal_callback(progress: float, phase: str):
                            job.progress = progress
                            job.phase = phase
                            asyncio.create_task(
                                self._update_job_status(job, progress_callback)
                            )

                        crew.set_progress_callback(internal_callback)

                    # 執行 Crew
                    result = crew.kickoff(inputs=job.inputs)
                    return result
                except Exception as e:
                    logger.error(f"Crew execution failed for job {job.job_id}: {e}")
                    raise

            # 在線程池中執行
            result = await loop.run_in_executor(self.executor, run_crew)

            # 處理結果
            if hasattr(result, "pydantic") and result.pydantic:
                job.result = result.pydantic.model_dump()
            elif hasattr(result, "json_dict") and result.json_dict:
                job.result = result.json_dict
            elif hasattr(result, "raw") and result.raw:
                job.result = {"raw_output": str(result.raw)}
            else:
                job.result = {"output": str(result)}

            # 更新狀態為完成
            job.status = ExecutionStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.progress = 100.0
            job.phase = "completed"

            logger.info(f"Job {job.job_id} completed successfully")

        except asyncio.CancelledError:
            job.status = ExecutionStatus.CANCELLED
            job.error = "Job was cancelled"
            job.completed_at = datetime.now(timezone.utc)
            logger.info(f"Job {job.job_id} was cancelled")

        except Exception as e:
            job.status = ExecutionStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now(timezone.utc)
            logger.error(f"Job {job.job_id} failed: {e}")

        finally:
            # 最終更新狀態
            await self._update_job_status(job, progress_callback)

            # 清理
            with self._lock:
                if job.job_id in self.running_jobs:
                    del self.running_jobs[job.job_id]
                if job.job_id in self.job_futures:
                    del self.job_futures[job.job_id]

    async def _update_job_status(
        self,
        job: ExecutionJob,
        progress_callback: Optional[Callable[[str, float, str], None]] = None,
    ) -> None:
        """更新任務狀態"""
        # 存儲到快取
        await self._store_job(job)

        # 存儲到記憶系統
        try:
            self.memory_manager.save_job_progress(
                job_id=job.job_id,
                video_id=job.inputs.get("video_id", ""),
                status=JobStatus(job.status.value),
                phase=(
                    JobPhase(job.phase)
                    if job.phase in JobPhase.__members__
                    else JobPhase.PROCESSING
                ),
                progress=job.progress,
            )
        except Exception as e:
            logger.error(f"Failed to store job progress to memory: {e}")

        # 調用進度回調
        if progress_callback:
            try:
                progress_callback(job.job_id, job.progress, job.phase)
            except Exception as e:
                logger.error(f"Progress callback failed for job {job.job_id}: {e}")

    async def _store_job(self, job: ExecutionJob) -> None:
        """存儲任務到快取"""
        try:
            cache_key = f"job:{job.job_id}"
            self.cache.set(cache_key, job.to_dict())
        except Exception as e:
            logger.error(f"Failed to store job {job.job_id} to cache: {e}")

    @trace("crew_executor.get_job_status")
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取任務狀態

        Args:
            job_id: 任務ID

        Returns:
            Dict[str, Any]: 任務狀態信息，如果任務不存在返回 None
        """
        # 先檢查運行中的任務
        with self._lock:
            if job_id in self.running_jobs:
                return self.running_jobs[job_id].to_dict()

        # 從快取中獲取
        try:
            cache_key = f"job:{job_id}"
            cached_job = self.cache.get(cache_key)
            if cached_job:
                return cached_job
        except Exception as e:
            logger.error(f"Failed to get job {job_id} from cache: {e}")

        # 從記憶系統中獲取
        try:
            memory_job = self.memory_manager.get_job_progress(job_id)
            if memory_job:
                return memory_job.model_dump()
        except Exception as e:
            logger.error(f"Failed to get job {job_id} from memory: {e}")

        return None

    @trace("crew_executor.cancel_job")
    async def cancel_job(self, job_id: str) -> bool:
        """
        取消任務

        Args:
            job_id: 任務ID

        Returns:
            bool: 是否成功取消
        """
        with self._lock:
            # 檢查任務是否在運行
            if job_id not in self.job_futures:
                logger.warning(f"Job {job_id} not found or already completed")
                return False

            # 取消 Future
            future = self.job_futures[job_id]
            success = future.cancel()

            if success:
                logger.info(f"Job {job_id} cancelled successfully")
            else:
                logger.warning(
                    f"Failed to cancel job {job_id} (might already be running)"
                )

            return success

    @trace("crew_executor.get_running_jobs")
    async def get_running_jobs(self) -> Dict[str, Dict[str, Any]]:
        """
        獲取所有運行中的任務

        Returns:
            Dict[str, Dict[str, Any]]: 運行中的任務狀態
        """
        with self._lock:
            return {job_id: job.to_dict() for job_id, job in self.running_jobs.items()}

    @trace("crew_executor.cleanup_completed_jobs")
    async def cleanup_completed_jobs(self, older_than_hours: int = 24) -> int:
        """
        清理完成的任務（從快取中移除）

        Args:
            older_than_hours: 清理多少小時前完成的任務

        Returns:
            int: 清理的任務數量
        """
        try:
            # 這裡應該實作清理邏輯，掃描快取中的舊任務
            # 暫時返回 0
            logger.info(f"Cleanup completed jobs older than {older_than_hours} hours")
            return 0
        except Exception as e:
            logger.error(f"Failed to cleanup completed jobs: {e}")
            return 0

    async def shutdown(self) -> None:
        """關閉執行器"""
        logger.info("Shutting down CrewExecutor")

        # 取消所有運行中的任務
        with self._lock:
            for job_id in list(self.job_futures.keys()):
                await self.cancel_job(job_id)

        # 關閉線程池
        self.executor.shutdown(wait=True)

        logger.info("CrewExecutor shutdown completed")


# 全域執行器實例
_global_executor: Optional[CrewExecutor] = None
_executor_lock = threading.Lock()


def get_global_executor(max_concurrent_jobs: int = 5) -> CrewExecutor:
    """
    獲取全域 CrewExecutor 實例

    Args:
        max_concurrent_jobs: 最大並發任務數量

    Returns:
        CrewExecutor: 全域執行器實例
    """
    global _global_executor

    if _global_executor is None:
        with _executor_lock:
            if _global_executor is None:
                _global_executor = CrewExecutor(max_concurrent_jobs)
                logger.info("Global CrewExecutor instance created")

    return _global_executor


async def shutdown_global_executor() -> None:
    """關閉全域執行器"""
    global _global_executor

    if _global_executor is not None:
        await _global_executor.shutdown()
        _global_executor = None
        logger.info("Global CrewExecutor shutdown")
