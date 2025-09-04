"""
進度追蹤機制

此模組實現了分段處理的進度追蹤功能，用於監控長文本處理的進度
並提供結果合併邏輯。

主要功能：
- 分段處理狀態追蹤
- 進度百分比計算
- 結果合併與驗證
- 錯誤處理與重試
- 時間統計與性能分析
"""

import uuid
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.api.core.logger_config import get_logger
from src.trailtag.tools.processing.subtitle_chunker import (
    SubtitleChunk,
    SubtitleChunker,
)

logger = get_logger(__name__)


class ProcessingStatus(str, Enum):
    """處理狀態枚舉"""

    PENDING = "pending"  # 等待處理
    PROCESSING = "processing"  # 處理中
    COMPLETED = "completed"  # 處理完成
    FAILED = "failed"  # 處理失敗
    RETRYING = "retrying"  # 重試中
    CANCELLED = "cancelled"  # 已取消


@dataclass
class ChunkProgress:
    """分段處理進度"""

    chunk_id: str
    chunk_index: int
    status: ProcessingStatus = ProcessingStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    processing_time: float = 0.0
    token_count: int = 0
    result: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        """計算處理時長"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    @property
    def is_finished(self) -> bool:
        """是否處理完成（成功或失敗）"""
        return self.status in [
            ProcessingStatus.COMPLETED,
            ProcessingStatus.FAILED,
            ProcessingStatus.CANCELLED,
        ]

    @property
    def can_retry(self) -> bool:
        """是否可以重試"""
        return (
            self.status == ProcessingStatus.FAILED
            and self.retry_count < self.max_retries
        )


@dataclass
class TaskProgress:
    """任務整體進度"""

    task_id: str
    task_name: str
    total_chunks: int
    chunk_progresses: List[ChunkProgress] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    merged_result: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def completed_chunks(self) -> int:
        """已完成的分段數"""
        return len(
            [
                cp
                for cp in self.chunk_progresses
                if cp.status == ProcessingStatus.COMPLETED
            ]
        )

    @property
    def failed_chunks(self) -> int:
        """失敗的分段數"""
        return len(
            [cp for cp in self.chunk_progresses if cp.status == ProcessingStatus.FAILED]
        )

    @property
    def processing_chunks(self) -> int:
        """處理中的分段數"""
        return len(
            [
                cp
                for cp in self.chunk_progresses
                if cp.status == ProcessingStatus.PROCESSING
            ]
        )

    @property
    def progress_percentage(self) -> float:
        """進度百分比"""
        if self.total_chunks == 0:
            return 100.0
        return (self.completed_chunks / self.total_chunks) * 100.0

    @property
    def is_completed(self) -> bool:
        """是否全部完成"""
        return self.completed_chunks == self.total_chunks

    @property
    def total_processing_time(self) -> float:
        """總處理時間"""
        return sum(
            cp.processing_time for cp in self.chunk_progresses if cp.processing_time > 0
        )

    @property
    def average_chunk_time(self) -> float:
        """平均每個分段處理時間"""
        completed = self.completed_chunks
        if completed == 0:
            return 0.0
        return self.total_processing_time / completed

    @property
    def estimated_remaining_time(self) -> float:
        """預估剩餘時間"""
        remaining_chunks = self.total_chunks - self.completed_chunks
        if remaining_chunks <= 0 or self.average_chunk_time <= 0:
            return 0.0
        return remaining_chunks * self.average_chunk_time


class ProgressTracker:
    """
    進度追蹤器

    負責追蹤分段處理任務的進度，提供實時狀態更新、
    結果合併和錯誤處理功能。
    """

    def __init__(self, max_concurrent_tasks: int = 3):
        """
        初始化進度追蹤器

        Args:
            max_concurrent_tasks: 最大並行任務數
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self.active_tasks: Dict[str, TaskProgress] = {}
        self.progress_callbacks: List[Callable[[TaskProgress], None]] = []

        logger.info(
            f"ProgressTracker 初始化完成: max_concurrent={max_concurrent_tasks}"
        )

    def add_progress_callback(self, callback: Callable[[TaskProgress], None]) -> None:
        """添加進度回調函數"""
        self.progress_callbacks.append(callback)

    def create_task(
        self, task_name: str, chunks: List[SubtitleChunk], task_id: Optional[str] = None
    ) -> str:
        """
        創建新的追蹤任務

        Args:
            task_name: 任務名稱
            chunks: 字幕分段列表
            task_id: 任務 ID（可選，自動生成）

        Returns:
            任務 ID
        """
        if task_id is None:
            task_id = str(uuid.uuid4())

        # 創建分段進度
        chunk_progresses = []
        for i, chunk in enumerate(chunks):
            chunk_progress = ChunkProgress(
                chunk_id=chunk.id,
                chunk_index=i,
                token_count=chunk.token_count,
                metadata={
                    "start_time": chunk.start_time,
                    "end_time": chunk.end_time,
                    "word_count": chunk.word_count,
                    "sentence_count": chunk.sentence_count,
                },
            )
            chunk_progresses.append(chunk_progress)

        # 創建任務進度
        task_progress = TaskProgress(
            task_id=task_id,
            task_name=task_name,
            total_chunks=len(chunks),
            chunk_progresses=chunk_progresses,
            start_time=datetime.now(timezone.utc),
            metadata={
                "total_tokens": sum(chunk.token_count for chunk in chunks),
                "total_duration": sum(
                    chunk.end_time - chunk.start_time for chunk in chunks
                ),
                "chunk_strategy": (
                    chunks[0].metadata.get("chunk_strategy", "unknown")
                    if chunks
                    else "unknown"
                ),
            },
        )

        self.active_tasks[task_id] = task_progress

        logger.info(f"創建追蹤任務: {task_id} ({task_name}), {len(chunks)} 個分段")
        return task_id

    def update_chunk_status(
        self,
        task_id: str,
        chunk_index: int,
        status: ProcessingStatus,
        result: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        更新分段處理狀態

        Args:
            task_id: 任務 ID
            chunk_index: 分段索引
            status: 新狀態
            result: 處理結果
            error_message: 錯誤訊息
        """
        if task_id not in self.active_tasks:
            logger.warning(f"任務不存在: {task_id}")
            return

        task_progress = self.active_tasks[task_id]

        if chunk_index >= len(task_progress.chunk_progresses):
            logger.warning(f"分段索引超出範圍: {chunk_index}")
            return

        chunk_progress = task_progress.chunk_progresses[chunk_index]
        now = datetime.now(timezone.utc)

        # 更新狀態和時間
        old_status = chunk_progress.status
        chunk_progress.status = status

        if (
            status == ProcessingStatus.PROCESSING
            and old_status == ProcessingStatus.PENDING
        ):
            chunk_progress.start_time = now
        elif status in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED]:
            chunk_progress.end_time = now
            if chunk_progress.start_time:
                chunk_progress.processing_time = (
                    now - chunk_progress.start_time
                ).total_seconds()

        # 更新結果或錯誤訊息
        if result is not None:
            chunk_progress.result = result
        if error_message is not None:
            chunk_progress.error_message = error_message

        # 如果是失敗狀態，增加重試計數
        if status == ProcessingStatus.FAILED:
            chunk_progress.retry_count += 1

        # 檢查任務整體狀態
        self._update_task_status(task_id)

        # 觸發回調
        self._trigger_callbacks(task_progress)

        logger.debug(f"更新分段狀態: {task_id}[{chunk_index}] {old_status} -> {status}")

    def get_task_progress(self, task_id: str) -> Optional[TaskProgress]:
        """取得任務進度"""
        return self.active_tasks.get(task_id)

    def get_progress_summary(self, task_id: str) -> Dict[str, Any]:
        """
        取得進度摘要

        Returns:
            進度摘要字典
        """
        task_progress = self.active_tasks.get(task_id)
        if not task_progress:
            return {"error": "Task not found"}

        return {
            "task_id": task_progress.task_id,
            "task_name": task_progress.task_name,
            "status": task_progress.status.value,
            "progress_percentage": round(task_progress.progress_percentage, 2),
            "completed_chunks": task_progress.completed_chunks,
            "total_chunks": task_progress.total_chunks,
            "failed_chunks": task_progress.failed_chunks,
            "processing_chunks": task_progress.processing_chunks,
            "total_processing_time": round(task_progress.total_processing_time, 2),
            "average_chunk_time": round(task_progress.average_chunk_time, 2),
            "estimated_remaining_time": round(
                task_progress.estimated_remaining_time, 2
            ),
            "start_time": (
                task_progress.start_time.isoformat()
                if task_progress.start_time
                else None
            ),
            "end_time": (
                task_progress.end_time.isoformat() if task_progress.end_time else None
            ),
        }

    def process_chunks_with_function(
        self,
        task_id: str,
        processing_function: Callable[[str], str],
        chunks: List[SubtitleChunk],
        max_workers: Optional[int] = None,
    ) -> List[str]:
        """
        使用指定函數處理分段並追蹤進度

        Args:
            task_id: 任務 ID
            processing_function: 處理函數
            chunks: 分段列表
            max_workers: 最大工作執行緒數

        Returns:
            處理結果列表
        """
        if task_id not in self.active_tasks:
            raise ValueError(f"任務不存在: {task_id}")

        if max_workers is None:
            max_workers = min(self.max_concurrent_tasks, len(chunks))

        task_progress = self.active_tasks[task_id]
        task_progress.status = ProcessingStatus.PROCESSING

        results = [None] * len(chunks)

        logger.info(
            f"開始處理任務: {task_id}, {len(chunks)} 個分段, {max_workers} 個工作執行緒"
        )

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任務
                future_to_index = {}
                for i, chunk in enumerate(chunks):
                    future = executor.submit(
                        self._process_single_chunk,
                        task_id,
                        i,
                        chunk,
                        processing_function,
                    )
                    future_to_index[future] = i

                # 收集結果
                for future in as_completed(future_to_index):
                    index = future_to_index[future]
                    try:
                        result = future.result()
                        results[index] = result
                        self.update_chunk_status(
                            task_id, index, ProcessingStatus.COMPLETED, result
                        )
                    except Exception as e:
                        error_msg = str(e)
                        logger.error(f"分段處理失敗: {task_id}[{index}] - {error_msg}")
                        self.update_chunk_status(
                            task_id,
                            index,
                            ProcessingStatus.FAILED,
                            error_message=error_msg,
                        )
                        results[index] = ""  # 失敗時使用空字串

            # 處理重試
            self._handle_retries(task_id, processing_function, chunks, results)

        except Exception as e:
            logger.error(f"任務處理失敗: {task_id} - {e}")
            task_progress.status = ProcessingStatus.FAILED
            task_progress.error_message = str(e)
            raise

        return results

    def merge_results(
        self,
        task_id: str,
        results: List[str],
        chunker: Optional[SubtitleChunker] = None,
    ) -> str:
        """
        合併處理結果

        Args:
            task_id: 任務 ID
            results: 結果列表
            chunker: 字幕分割器（用於合併）

        Returns:
            合併後的結果
        """
        task_progress = self.active_tasks.get(task_id)
        if not task_progress:
            raise ValueError(f"任務不存在: {task_id}")

        try:
            if chunker and hasattr(chunker, "merge_chunks"):
                # 重建分段物件用於合併
                chunks = []
                for i, cp in enumerate(task_progress.chunk_progresses):
                    # 簡化版本的 SubtitleChunk
                    chunk_data = {
                        "id": cp.chunk_id,
                        "start_time": cp.metadata.get("start_time", 0),
                        "end_time": cp.metadata.get("end_time", 0),
                        "token_count": cp.token_count,
                    }
                    chunks.append(chunk_data)

                merged_result = chunker.merge_chunks(chunks, results)
            else:
                # 簡單合併
                merged_result = "\n\n---\n\n".join(filter(None, results))

            task_progress.merged_result = merged_result
            task_progress.end_time = datetime.now(timezone.utc)
            task_progress.status = ProcessingStatus.COMPLETED

            logger.info(f"結果合併完成: {task_id}, 長度: {len(merged_result)} 字元")
            return merged_result

        except Exception as e:
            error_msg = f"結果合併失敗: {e}"
            logger.error(error_msg)
            task_progress.error_message = error_msg
            task_progress.status = ProcessingStatus.FAILED
            raise

    def cleanup_task(self, task_id: str) -> None:
        """清理完成的任務"""
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]
            logger.info(f"清理任務: {task_id}")

    def get_active_tasks(self) -> Dict[str, Dict[str, Any]]:
        """取得所有活動任務的摘要"""
        return {
            task_id: self.get_progress_summary(task_id) for task_id in self.active_tasks
        }

    def _process_single_chunk(
        self,
        task_id: str,
        chunk_index: int,
        chunk: SubtitleChunk,
        processing_function: Callable[[str], str],
    ) -> str:
        """處理單一分段"""
        self.update_chunk_status(task_id, chunk_index, ProcessingStatus.PROCESSING)

        try:
            result = processing_function(chunk.content)
            return result
        except Exception as e:
            logger.error(f"分段處理失敗: {task_id}[{chunk_index}] - {e}")
            raise

    def _handle_retries(
        self,
        task_id: str,
        processing_function: Callable[[str], str],
        chunks: List[SubtitleChunk],
        results: List[str],
    ) -> None:
        """處理重試邏輯"""
        task_progress = self.active_tasks[task_id]
        retry_chunks = []
        retry_indices = []

        # 找出需要重試的分段
        for i, cp in enumerate(task_progress.chunk_progresses):
            if cp.can_retry:
                retry_chunks.append(chunks[i])
                retry_indices.append(i)

        if not retry_chunks:
            return

        logger.info(f"重試失敗分段: {task_id}, {len(retry_chunks)} 個分段")

        # 重試處理
        for retry_chunk, retry_index in zip(retry_chunks, retry_indices):
            try:
                self.update_chunk_status(
                    task_id, retry_index, ProcessingStatus.RETRYING
                )
                result = processing_function(retry_chunk.content)
                results[retry_index] = result
                self.update_chunk_status(
                    task_id, retry_index, ProcessingStatus.COMPLETED, result
                )
            except Exception as e:
                error_msg = f"重試失敗: {e}"
                self.update_chunk_status(
                    task_id,
                    retry_index,
                    ProcessingStatus.FAILED,
                    error_message=error_msg,
                )
                results[retry_index] = ""

    def _update_task_status(self, task_id: str) -> None:
        """更新任務整體狀態"""
        task_progress = self.active_tasks[task_id]

        if task_progress.is_completed:
            task_progress.status = ProcessingStatus.COMPLETED
            task_progress.end_time = datetime.now(timezone.utc)
        elif task_progress.failed_chunks > 0 and task_progress.processing_chunks == 0:
            # 如果有失敗且沒有正在處理的，檢查是否還能重試
            can_retry = any(cp.can_retry for cp in task_progress.chunk_progresses)
            if not can_retry:
                task_progress.status = ProcessingStatus.FAILED
                task_progress.end_time = datetime.now(timezone.utc)

    def _trigger_callbacks(self, task_progress: TaskProgress) -> None:
        """觸發進度回調"""
        for callback in self.progress_callbacks:
            try:
                callback(task_progress)
            except Exception as e:
                logger.error(f"進度回調失敗: {e}")


# 全域進度追蹤器實例
_global_progress_tracker: Optional[ProgressTracker] = None


def get_progress_tracker() -> ProgressTracker:
    """取得全域進度追蹤器實例"""
    global _global_progress_tracker

    if _global_progress_tracker is None:
        _global_progress_tracker = ProgressTracker()

    return _global_progress_tracker


def reset_progress_tracker() -> None:
    """重置全域進度追蹤器"""
    global _global_progress_tracker
    _global_progress_tracker = None
