"""
SSE (Server-Sent Events) 事件流路由器模組
本模組負責即時推送任務進度、狀態、錯誤等事件給前端，
支援多種事件型別，並自動處理心跳與例外。
"""

# FastAPI 路由與型別
from fastapi import APIRouter, Path

# SSE 回應工具
from sse_starlette.sse import EventSourceResponse

# 非同步與系統工具
import asyncio
from src.api.logger_config import get_logger

import time
import json
from enum import Enum

# 快取存取（查詢 job 狀態）
from .cache_manager import CacheManager

# 任務狀態列舉
from src.api.models import JobStatus


# 設定 logger
logger = get_logger(__name__)
# 註冊 API 路由前綴
router = APIRouter(prefix="/api")


class EventType(str, Enum):
    """
    SSE 事件型別列舉：
    - PHASE_UPDATE：任務階段/進度更新
    - COMPLETED：任務完成
    - ERROR：任務失敗或異常
    - HEARTBEAT：心跳訊號，保持連線活性
    """

    PHASE_UPDATE = "phase_update"
    COMPLETED = "completed"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


async def event_generator(job_id: str):
    """
    SSE 事件流生成器：
    1. 持續輪詢快取中的 job 狀態，並根據狀態推送對應事件。
    2. 若 phase/progress 有變化則推送 phase_update。
    3. 任務完成（DONE）推送 completed，失敗/取消推送 error，並結束事件流。
    4. 定期推送 heartbeat 保持連線活性。
    5. 若查無任務則立即推送 error 並結束。
    6. 例外狀況會推送 error 事件。
    """
    cache = CacheManager()  # 每次請求獨立快取實例
    last_phase = None  # 記錄上次推送的階段
    last_progress = None  # 記錄上次推送的進度
    try:
        while True:
            job = cache.get(f"job:{job_id}")
            if not job:
                # 任務不存在，推送 error 並結束
                yield {
                    "event": EventType.ERROR,
                    "data": json.dumps({"message": "Job not found"}),
                    "id": job_id,
                }
                break
            # 若 phase/progress 有變化則推送 phase_update 事件
            phase = job.get("phase")
            progress = job.get("progress")
            status = job.get("status")
            # 若狀態有變化則推送 status_update 事件
            if phase != last_phase or progress != last_progress:
                yield {
                    "event": EventType.PHASE_UPDATE,
                    "data": json.dumps({"phase": phase, "progress": progress}),
                    "id": job_id,
                }
                last_phase = phase
                last_progress = progress

            # 狀態為 done/failed/canceled 時推送完成或錯誤事件並結束
            if status == JobStatus.DONE:
                yield {
                    "event": EventType.COMPLETED,
                    "data": json.dumps({"job_id": job_id, "progress": 100}),
                    "id": job_id,
                }
                break
            elif status in [JobStatus.FAILED, JobStatus.CANCELED]:
                yield {
                    "event": EventType.ERROR,
                    "data": json.dumps({"job_id": job_id, "status": status}),
                    "id": job_id,
                }
                break
            # 定期推送心跳事件，避免前端斷線
            yield {
                "event": EventType.HEARTBEAT,
                "data": json.dumps({"timestamp": time.time(), "status": status}),
                "id": job_id,
            }
            await asyncio.sleep(2)
    except Exception as e:
        # 例外狀況推送 error 事件
        logger.error({"event": "sse_error", "job_id": job_id, "error": str(e)})
        yield {
            "event": EventType.ERROR,
            "data": json.dumps({"message": str(e)}),
            "id": job_id,
        }


# SSE 事件流 API 端點
@router.get("/jobs/{job_id}/stream")
async def stream_job_events(job_id: str = Path(..., description="任務 ID")):
    """
    以 SSE 格式推送指定任務的即時進度、狀態與錯誤事件。
    前端可透過此端點即時監控任務進度。
    """
    return EventSourceResponse(event_generator(job_id))
