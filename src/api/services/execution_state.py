"""
執行狀態持久化管理模組
提供任務執行狀態的持久化存儲、查詢和恢復功能，支持系統重啟後的狀態恢復。
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import threading

from src.api.logger_config import get_logger
from src.api.observability import trace

logger = get_logger(__name__)


class ExecutionStateType(str, Enum):
    """執行狀態類型"""

    JOB = "job"
    CREW = "crew"
    AGENT = "agent"
    TASK = "task"
    SYSTEM = "system"


@dataclass
class ExecutionState:
    """執行狀態資料結構"""

    state_id: str
    state_type: ExecutionStateType
    entity_id: str  # job_id, crew_id, agent_id 等
    status: str
    phase: str
    progress: float
    data: Dict[str, Any]
    error: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        now = datetime.now(timezone.utc)
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            "state_id": self.state_id,
            "state_type": self.state_type.value,
            "entity_id": self.entity_id,
            "status": self.status,
            "phase": self.phase,
            "progress": self.progress,
            "data": self.data,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class ExecutionStateManager:
    """
    執行狀態持久化管理器

    功能：
    1. SQLite 數據庫存儲執行狀態
    2. 狀態查詢和更新
    3. 系統重啟後的狀態恢復
    4. 狀態歷史記錄管理
    5. 自動清理過期狀態
    """

    def __init__(self, db_path: str = "trailtag_execution_state.db"):
        """初始化執行狀態管理器"""
        self.db_path = Path(db_path)
        self._lock = threading.RLock()
        self._init_database()

        logger.info(f"ExecutionStateManager initialized with database: {self.db_path}")

    def _init_database(self) -> None:
        """初始化數據庫表結構"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS execution_states (
                        state_id TEXT PRIMARY KEY,
                        state_type TEXT NOT NULL,
                        entity_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        phase TEXT NOT NULL,
                        progress REAL NOT NULL DEFAULT 0.0,
                        data TEXT NOT NULL DEFAULT '{}',
                        error TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """
                )

                # 創建索引以提升查詢性能
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_entity_id
                    ON execution_states(entity_id)
                """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_state_type
                    ON execution_states(state_type)
                """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_status
                    ON execution_states(status)
                """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_updated_at
                    ON execution_states(updated_at)
                """
                )

                # 創建歷史記錄表
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS execution_state_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        state_id TEXT NOT NULL,
                        state_type TEXT NOT NULL,
                        entity_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        phase TEXT NOT NULL,
                        progress REAL NOT NULL,
                        data TEXT NOT NULL,
                        error TEXT,
                        created_at TEXT NOT NULL,
                        snapshot_at TEXT NOT NULL
                    )
                """
                )

                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_history_entity_id
                    ON execution_state_history(entity_id)
                """
                )

                conn.commit()
                logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    @trace("execution_state.store")
    async def store_state(self, state: ExecutionState) -> bool:
        """
        存儲執行狀態

        Args:
            state: 執行狀態對象

        Returns:
            bool: 是否存儲成功
        """
        try:
            with self._lock:
                # 先檢查是否存在，如果存在則記錄歷史
                existing = await self.get_state(state.state_id)
                if existing:
                    await self._store_history(existing)

                # 更新時間戳
                state.updated_at = datetime.now(timezone.utc)

                # 存儲到數據庫
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO execution_states
                        (state_id, state_type, entity_id, status, phase, progress,
                         data, error, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            state.state_id,
                            state.state_type.value,
                            state.entity_id,
                            state.status,
                            state.phase,
                            state.progress,
                            json.dumps(state.data),
                            state.error,
                            state.created_at.isoformat(),
                            state.updated_at.isoformat(),
                        ),
                    )
                    conn.commit()

                logger.debug(f"Stored execution state {state.state_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to store execution state {state.state_id}: {e}")
            return False

    async def _store_history(self, state: ExecutionState) -> None:
        """存儲狀態歷史記錄"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO execution_state_history
                    (state_id, state_type, entity_id, status, phase, progress,
                     data, error, created_at, snapshot_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        state.state_id,
                        state.state_type.value,
                        state.entity_id,
                        state.status,
                        state.phase,
                        state.progress,
                        json.dumps(state.data),
                        state.error,
                        state.created_at.isoformat(),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.error(
                f"Failed to store execution state history {state.state_id}: {e}"
            )

    @trace("execution_state.get")
    async def get_state(self, state_id: str) -> Optional[ExecutionState]:
        """
        獲取執行狀態

        Args:
            state_id: 狀態ID

        Returns:
            Optional[ExecutionState]: 執行狀態，如果不存在返回 None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT state_id, state_type, entity_id, status, phase, progress,
                           data, error, created_at, updated_at
                    FROM execution_states
                    WHERE state_id = ?
                """,
                    (state_id,),
                )

                row = cursor.fetchone()
                if not row:
                    return None

                return ExecutionState(
                    state_id=row[0],
                    state_type=ExecutionStateType(row[1]),
                    entity_id=row[2],
                    status=row[3],
                    phase=row[4],
                    progress=row[5],
                    data=json.loads(row[6]),
                    error=row[7],
                    created_at=datetime.fromisoformat(row[8]),
                    updated_at=datetime.fromisoformat(row[9]),
                )

        except Exception as e:
            logger.error(f"Failed to get execution state {state_id}: {e}")
            return None

    @trace("execution_state.get_by_entity")
    async def get_states_by_entity(
        self, entity_id: str, state_type: Optional[ExecutionStateType] = None
    ) -> List[ExecutionState]:
        """
        根據實體ID獲取執行狀態列表

        Args:
            entity_id: 實體ID
            state_type: 狀態類型（可選）

        Returns:
            List[ExecutionState]: 執行狀態列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                if state_type:
                    cursor = conn.execute(
                        """
                        SELECT state_id, state_type, entity_id, status, phase, progress,
                               data, error, created_at, updated_at
                        FROM execution_states
                        WHERE entity_id = ? AND state_type = ?
                        ORDER BY updated_at DESC
                    """,
                        (entity_id, state_type.value),
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT state_id, state_type, entity_id, status, phase, progress,
                               data, error, created_at, updated_at
                        FROM execution_states
                        WHERE entity_id = ?
                        ORDER BY updated_at DESC
                    """,
                        (entity_id,),
                    )

                states = []
                for row in cursor.fetchall():
                    states.append(
                        ExecutionState(
                            state_id=row[0],
                            state_type=ExecutionStateType(row[1]),
                            entity_id=row[2],
                            status=row[3],
                            phase=row[4],
                            progress=row[5],
                            data=json.loads(row[6]),
                            error=row[7],
                            created_at=datetime.fromisoformat(row[8]),
                            updated_at=datetime.fromisoformat(row[9]),
                        )
                    )

                return states

        except Exception as e:
            logger.error(f"Failed to get execution states for entity {entity_id}: {e}")
            return []

    @trace("execution_state.get_active_jobs")
    async def get_active_jobs(self) -> List[ExecutionState]:
        """
        獲取所有活躍的任務狀態

        Returns:
            List[ExecutionState]: 活躍任務列表
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT state_id, state_type, entity_id, status, phase, progress,
                           data, error, created_at, updated_at
                    FROM execution_states
                    WHERE state_type = ? AND status IN ('pending', 'running')
                    ORDER BY created_at ASC
                """,
                    (ExecutionStateType.JOB.value,),
                )

                jobs = []
                for row in cursor.fetchall():
                    jobs.append(
                        ExecutionState(
                            state_id=row[0],
                            state_type=ExecutionStateType(row[1]),
                            entity_id=row[2],
                            status=row[3],
                            phase=row[4],
                            progress=row[5],
                            data=json.loads(row[6]),
                            error=row[7],
                            created_at=datetime.fromisoformat(row[8]),
                            updated_at=datetime.fromisoformat(row[9]),
                        )
                    )

                return jobs

        except Exception as e:
            logger.error(f"Failed to get active jobs: {e}")
            return []

    @trace("execution_state.update_status")
    async def update_status(
        self,
        state_id: str,
        status: str,
        phase: Optional[str] = None,
        progress: Optional[float] = None,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> bool:
        """
        更新執行狀態

        Args:
            state_id: 狀態ID
            status: 新狀態
            phase: 新階段（可選）
            progress: 進度（可選）
            data: 額外資料（可選）
            error: 錯誤信息（可選）

        Returns:
            bool: 是否更新成功
        """
        try:
            # 先獲取現有狀態
            existing_state = await self.get_state(state_id)
            if not existing_state:
                logger.warning(f"State {state_id} not found for update")
                return False

            # 更新字段
            existing_state.status = status
            if phase is not None:
                existing_state.phase = phase
            if progress is not None:
                existing_state.progress = progress
            if data is not None:
                existing_state.data.update(data)
            if error is not None:
                existing_state.error = error

            # 存儲更新後的狀態
            return await self.store_state(existing_state)

        except Exception as e:
            logger.error(f"Failed to update execution state {state_id}: {e}")
            return False

    @trace("execution_state.delete")
    async def delete_state(self, state_id: str) -> bool:
        """
        刪除執行狀態

        Args:
            state_id: 狀態ID

        Returns:
            bool: 是否刪除成功
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM execution_states
                    WHERE state_id = ?
                """,
                    (state_id,),
                )

                deleted_count = cursor.rowcount
                conn.commit()

                if deleted_count > 0:
                    logger.debug(f"Deleted execution state {state_id}")
                    return True
                else:
                    logger.warning(f"State {state_id} not found for deletion")
                    return False

        except Exception as e:
            logger.error(f"Failed to delete execution state {state_id}: {e}")
            return False

    @trace("execution_state.cleanup")
    async def cleanup_old_states(self, older_than_days: int = 7) -> int:
        """
        清理舊的執行狀態

        Args:
            older_than_days: 清理多少天前的狀態

        Returns:
            int: 清理的狀態數量
        """
        try:
            cutoff_time = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - datetime.timedelta(days=older_than_days)

            with sqlite3.connect(self.db_path) as conn:
                # 清理主表中已完成的舊狀態
                cursor = conn.execute(
                    """
                    DELETE FROM execution_states
                    WHERE updated_at < ? AND status IN ('completed', 'failed', 'cancelled')
                """,
                    (cutoff_time.isoformat(),),
                )

                deleted_count = cursor.rowcount

                # 清理歷史記錄
                conn.execute(
                    """
                    DELETE FROM execution_state_history
                    WHERE snapshot_at < ?
                """,
                    (cutoff_time.isoformat(),),
                )

                conn.commit()

                logger.info(f"Cleaned up {deleted_count} old execution states")
                return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup old states: {e}")
            return 0

    @trace("execution_state.get_statistics")
    async def get_statistics(self) -> Dict[str, Any]:
        """
        獲取執行狀態統計信息

        Returns:
            Dict[str, Any]: 統計信息
        """
        try:
            stats = {}

            with sqlite3.connect(self.db_path) as conn:
                # 總狀態數量
                cursor = conn.execute("SELECT COUNT(*) FROM execution_states")
                stats["total_states"] = cursor.fetchone()[0]

                # 按類型統計
                cursor = conn.execute(
                    """
                    SELECT state_type, COUNT(*)
                    FROM execution_states
                    GROUP BY state_type
                """
                )
                stats["by_type"] = dict(cursor.fetchall())

                # 按狀態統計
                cursor = conn.execute(
                    """
                    SELECT status, COUNT(*)
                    FROM execution_states
                    GROUP BY status
                """
                )
                stats["by_status"] = dict(cursor.fetchall())

                # 活躍任務數量
                cursor = conn.execute(
                    """
                    SELECT COUNT(*) FROM execution_states
                    WHERE state_type = ? AND status IN ('pending', 'running')
                """,
                    (ExecutionStateType.JOB.value,),
                )
                stats["active_jobs"] = cursor.fetchone()[0]

                # 歷史記錄數量
                cursor = conn.execute("SELECT COUNT(*) FROM execution_state_history")
                stats["history_records"] = cursor.fetchone()[0]

            return stats

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    async def recover_incomplete_jobs(self) -> List[ExecutionState]:
        """
        恢復未完成的任務狀態（系統重啟時使用）

        Returns:
            List[ExecutionState]: 需要恢復的任務列表
        """
        try:
            incomplete_jobs = await self.get_active_jobs()

            # 將運行中的任務標記為失敗（因為系統重啟了）
            for job in incomplete_jobs:
                if job.status == "running":
                    await self.update_status(
                        job.state_id,
                        "failed",
                        error="System restarted while job was running",
                    )

            logger.info(f"Found {len(incomplete_jobs)} incomplete jobs for recovery")
            return incomplete_jobs

        except Exception as e:
            logger.error(f"Failed to recover incomplete jobs: {e}")
            return []


# 全域執行狀態管理器實例
_global_state_manager: Optional[ExecutionStateManager] = None
_manager_lock = threading.Lock()


def get_execution_state_manager(
    db_path: str = "trailtag_execution_state.db",
) -> ExecutionStateManager:
    """
    獲取全域執行狀態管理器實例

    Args:
        db_path: 數據庫文件路徑

    Returns:
        ExecutionStateManager: 全域管理器實例
    """
    global _global_state_manager

    if _global_state_manager is None:
        with _manager_lock:
            if _global_state_manager is None:
                _global_state_manager = ExecutionStateManager(db_path)
                logger.info("Global ExecutionStateManager instance created")

    return _global_state_manager


# 便利函數
async def store_job_state(
    job_id: str,
    status: str,
    phase: str = "unknown",
    progress: float = 0.0,
    data: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> bool:
    """
    存儲任務狀態的便利函數

    Args:
        job_id: 任務ID
        status: 狀態
        phase: 階段
        progress: 進度
        data: 額外資料
        error: 錯誤信息

    Returns:
        bool: 是否存儲成功
    """
    manager = get_execution_state_manager()

    state = ExecutionState(
        state_id=f"job_{job_id}",
        state_type=ExecutionStateType.JOB,
        entity_id=job_id,
        status=status,
        phase=phase,
        progress=progress,
        data=data or {},
        error=error,
    )

    return await manager.store_state(state)


async def get_job_state(job_id: str) -> Optional[ExecutionState]:
    """
    獲取任務狀態的便利函數

    Args:
        job_id: 任務ID

    Returns:
        Optional[ExecutionState]: 任務狀態
    """
    manager = get_execution_state_manager()
    return await manager.get_state(f"job_{job_id}")
