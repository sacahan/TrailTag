"""
視頻分析相關路由器模組
本模組負責 API 端點、任務分派、快取查詢與狀態管理，
並將分析任務分派給 crewai 執行，支援即時進度查詢。
"""

from fastapi import APIRouter, HTTPException, Path, BackgroundTasks
import logging
import uuid
from datetime import datetime
import re


from src.api.models import (
    AnalyzeRequest,
    JobResponse,
    JobStatus,
    Phase,
    MapVisualization,
)

from .cache_manager import CacheManager

from trailtag.crew import Trailtag

logger = logging.getLogger("trailtag-api")
router = APIRouter(prefix="/api")


# 快取提供者（Redis/Memory fallback），統一管理 job 狀態與分析結果
cache = CacheManager()


def extract_video_id(url: str) -> str:
    """
    從 YouTube URL 中提取 video_id。
    支援多種常見網址格式，若無法解析則拋出例外。
    """
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",  # youtu.be/XXX or youtube.com/watch?v=XXX
        r"(?:embed\/|v\/|youtu\.be\/)([0-9A-Za-z_-]{11})",  # youtube.com/embed/XXX
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"無法從 URL 提取有效的 YouTube video_id: {url}")


# --- 背景任務：執行 crewai 分析並即時更新 job 狀態 ---
def run_trailtag_job(job_id, video_id):
    """
    執行 crewai 分析流程，並根據階段即時更新 job 狀態與進度。
    1. 依照分析階段（metadata→geocode）即時寫入 job 狀態，供 SSE 查詢。
    2. 若分析成功，將結果寫入 analysis 快取。
    3. 若失敗則記錄錯誤並更新 job 狀態。
    """
    try:

        def update_job(phase, progress, status=JobStatus.RUNNING, extra=None):
            """
            寫入/更新 job 狀態到快取，供進度查詢與 SSE 推播。
            """
            now = datetime.now(datetime.timezone.utc)
            job = cache.get(f"job:{job_id}") or {}
            job.update(
                {
                    "job_id": job_id,
                    "video_id": video_id,
                    "status": status,
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

        # 1. metadata 階段（可擴充更多細緻進度）
        update_job("metadata", 0.0)
        try:
            # 準備 crewai kickoff 輸入，補充 job_id, video_id 以利 callback 進度更新
            inputs = {
                "job_id": job_id,
                "video_id": video_id,
                "search_subject": "找出景點與美食的地理位置",
            }
            # 進度: metadata
            update_job("metadata", 5)
            # 執行 crewai 主流程（同步呼叫，實際可依需求細分進度）
            output = Trailtag().crew().kickoff(inputs=inputs)
            # 進度: geocode 完成
            update_job("geocode", 100, status=JobStatus.DONE)
            # 結果寫入 analysis 快取，供地圖查詢
            cache.set(
                f"analysis:{video_id}",
                output.model_dump() if hasattr(output, "model_dump") else output,
            )
        except Exception as e:
            # crewai 執行失敗，記錄錯誤並更新 job 狀態
            logger.error({"event": "job_failed", "job_id": job_id, "error": str(e)})
            update_job(
                "geocode",
                0,
                status=JobStatus.FAILED,
                extra={"error": {"type": "exception", "message": str(e)}},
            )
    except Exception as e:
        # 背景任務本身致命錯誤
        logger.error({"event": "job_fatal", "job_id": job_id, "error": str(e)})


@router.post("/videos/analyze", response_model=JobResponse)
async def analyze_video(
    request: AnalyzeRequest, background_tasks: BackgroundTasks
) -> JobResponse:
    """
    提交新的影片分析請求：
    1. 先檢查快取，若命中則直接回傳已完成 job。
    2. 若未命中，建立 job 狀態並分派 crewai 任務到背景執行。
    3. 回傳 job_id 供前端查詢進度。
    """
    try:
        video_id = extract_video_id(str(request.url))
    except ValueError as e:
        logger.error({"event": "invalid_url", "url": str(request.url), "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))

    # 檢查是否已有此影片的分析結果（查快取）
    cache_key = f"analysis:{video_id}"
    cached_result = cache.get(cache_key)
    if cached_result:
        logger.info({"event": "cache_hit", "video_id": video_id})
        job_id = str(uuid.uuid4())
        now = datetime.now(datetime.timezone.utc)
        job = {
            "job_id": job_id,
            "video_id": video_id,
            "status": JobStatus.DONE,
            "phase": Phase.GEOCODE,
            "progress": 100.0,
            "cached": True,
            "created_at": now,
            "updated_at": now,
        }
        cache.set(f"job:{job_id}", job)
        return JobResponse(**job)

    # 創建新任務
    job_id = str(uuid.uuid4())
    now = datetime.now(datetime.timezone.utc)
    job = {
        "job_id": job_id,
        "video_id": video_id,
        "status": JobStatus.QUEUED,
        "phase": None,
        "progress": 0.0,
        "cached": False,
        "created_at": now,
        "updated_at": now,
    }
    cache.set(f"job:{job_id}", job)
    logger.info({"event": "job_created", "job_id": job_id, "video_id": video_id})

    # 分派 crewai 任務到背景，執行分析與進度更新
    background_tasks.add_task(run_trailtag_job, job_id, video_id)
    return JobResponse(**job)


# 查詢任務狀態 API
@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str = Path(..., description="任務 ID")) -> JobResponse:
    """
    根據 job_id 查詢任務狀態，回傳進度、階段、錯誤等資訊。
    若 job 不存在則回傳 404。
    """
    job = cache.get(f"job:{job_id}")
    if not job:
        logger.warning({"event": "job_not_found", "job_id": job_id})
        raise HTTPException(status_code=404, detail=f"任務不存在: {job_id}")
    return JobResponse(**job)


# 查詢影片地點視覺化資料 API
@router.get("/videos/{video_id}/locations", response_model=MapVisualization)
async def get_video_locations(
    video_id: str = Path(..., description="YouTube 影片 ID"),
) -> MapVisualization:
    """
    根據 video_id 查詢分析後的地點視覺化資料（地圖路線等）。
    若查無資料則回傳 404。
    """
    cache_key = f"analysis:{video_id}"
    result = cache.get(cache_key)
    if not result:
        logger.warning({"event": "locations_not_found", "video_id": video_id})
        raise HTTPException(status_code=404, detail=f"找不到影片地點資料: {video_id}")
    return MapVisualization(**result)
