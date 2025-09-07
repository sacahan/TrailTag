"""
視頻分析相關路由器模組
本模組負責 API 端點、任務分派、快取查詢與狀態管理，
並將分析任務分派給 crewai 執行，支援即時進度查詢。
"""

from fastapi import APIRouter, HTTPException, Path, BackgroundTasks
from fastapi.openapi.utils import get_openapi
from src.api.core.logger_config import get_logger
import uuid
from datetime import datetime, timezone
import re
from src.api.core.models import (
    AnalyzeRequest,
    JobResponse,
    JobStatusResponse,
    JobStatus,
    Phase,
    MapVisualization,
    SubtitleStatus,
)

# CacheManager 和 Trailtag 將在需要時動態匯入以避免循環依賴
from src.trailtag.tools.data_extraction.youtube_metadata import YoutubeMetadataTool


logger = get_logger(__name__)
router = APIRouter(prefix="/api")


def custom_openapi():
    if router.openapi_schema:
        return router.openapi_schema
    openapi_schema = get_openapi(
        title="TrailTag API",
        version="1.0.0",
        description="TrailTag 後端 API，提供 YouTube 影片分析、任務進度查詢與地點視覺化資料。支援快取、非同步任務、SSE 進度推播。",
        routes=router.routes,
    )
    router.openapi_schema = openapi_schema
    return router.openapi_schema


router.openapi = custom_openapi


def get_cache():
    """獲取快取管理器實例（延遲匯入）"""
    from src.api.cache.cache_manager import CacheManager

    return CacheManager()


def get_trailtag():
    """獲取 Trailtag 實例（延遲匯入）"""
    from src.trailtag.core.crew import Trailtag

    return Trailtag


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


def check_subtitle_availability(video_id: str) -> SubtitleStatus:
    """
    快速檢測影片字幕可用性，用於在分析開始前提供用戶提示。
    優先檢查緩存，避免重複下載字幕導致 Too Many Requests 錯誤。

    Args:
        video_id (str): YouTube 影片 ID

    Returns:
        SubtitleStatus: 字幕狀態資訊
    """
    try:
        # 延遲匯入避免循環依賴
        from src.api.cache.cache_provider import get_cache

        cache = get_cache()

        # 先檢查是否有快取的分析結果
        cached_result = cache.get(f"analysis:{video_id}")
        if cached_result:
            logger.info(f"從快取獲取影片 {video_id} 的字幕狀態")
            # 如果有分析結果，說明字幕是可用的（否則分析不會成功）
            return SubtitleStatus(
                available=True,
                manual_subtitles=[],  # 快取結果沒有詳細字幕類型資訊
                auto_captions=[],
                selected_lang="cached",  # 標記來源為快取
                confidence_score=0.9,  # 已分析過的影片信心度較高
            )

        # 如果沒有快取，才進行實際檢測
        logger.info(f"快取未命中，檢測影片 {video_id} 字幕可用性")
        metadata_tool = YoutubeMetadataTool()
        metadata = metadata_tool._run(video_id)

        if metadata and metadata.subtitle_availability:
            availability = metadata.subtitle_availability
            return SubtitleStatus(
                available=availability.available,
                manual_subtitles=availability.manual_subtitles,
                auto_captions=availability.auto_captions,
                selected_lang=availability.selected_lang,
                confidence_score=availability.confidence_score,
            )
        else:
            logger.warning(f"無法檢測影片 {video_id} 的字幕可用性")
            return SubtitleStatus(
                available=False,
                manual_subtitles=[],
                auto_captions=[],
                selected_lang=None,
                confidence_score=0.0,
            )

    except Exception as e:
        logger.error(f"字幕可用性檢測失敗 {video_id}: {str(e)}")
        return SubtitleStatus(
            available=False,
            manual_subtitles=[],
            auto_captions=[],
            selected_lang=None,
            confidence_score=0.0,
        )


# --- 背景任務：執行 crewai 分析並即時更新 job 狀態 ---
def run_trailtag_job(job_id, video_id):
    """
    執行 crewai 分析流程，並根據階段即時更新 job 狀態與進度。
    1. 依照分析階段（metadata→geocode）即時寫入 job 狀態，供 SSE 查詢。
    2. 若分析成功，將結果寫入 analysis 快取。
    3. 若失敗則記錄錯誤並更新 job 狀態。
    """
    try:
        # 延遲匯入避免循環依賴
        cache = get_cache()

        def update_job(
            phase, progress, status=JobStatus.RUNNING, extra=None, ttl: int = None
        ):
            """
            寫入/更新 job 狀態到快取，供進度查詢與 SSE 推播。
            支援可選的 ttl（秒）參數以便設定短暫生命週期的完成狀態。
            """
            logger.info(
                f"🔄 更新任務狀態 - job_id: {job_id}, status: {status}, phase: {phase}, progress: {progress}"
            )

            try:
                now = datetime.now(timezone.utc).isoformat()  # 直接轉為 ISO 字串
                # 先檢查現有的 job 狀態
                existing_job = cache.get(f"job:{job_id}")
                logger.info(f"📋 現有任務狀態: {existing_job}")

                job = existing_job or {}
                job.update(
                    {
                        "job_id": job_id,
                        "video_id": video_id,
                        "status": (
                            status.value if hasattr(status, "value") else status
                        ),  # 確保枚舉轉為字串
                        "phase": phase,
                        "progress": progress,
                        "cached": False,
                        "created_at": job.get("created_at", now),
                        "updated_at": now,
                    }
                )
                if extra:
                    job.update(extra)

                # 執行快取更新
                logger.info(f"💾 準備寫入快取 - key: job:{job_id}, ttl: {ttl}")
                success = cache.set(f"job:{job_id}", job, ttl=ttl)
                logger.info(f"📝 快取寫入結果: {success}")

                # 短暫延遲後驗證寫入是否成功
                import time

                time.sleep(0.1)
                updated_job = cache.get(f"job:{job_id}")
                logger.info(f"✅ 快取更新後驗證: {updated_job}")

                # 檢查狀態是否正確更新
                if updated_job and updated_job.get("status") == job.get("status"):
                    logger.info(f"🎉 狀態更新確認成功: {updated_job.get('status')}")
                else:
                    logger.error(
                        f"❌ 狀態更新失敗 - 期望: {job.get('status')}, 實際: {updated_job.get('status') if updated_job else 'None'}"
                    )

            except Exception as e:
                logger.error(f"❌ 更新任務狀態失敗: {e}", exc_info=True)

        # 1. 更新任務狀態為 RUNNING
        update_job("metadata", 0.0, status=JobStatus.RUNNING)
        try:
            # 準備 crewai kickoff 輸入，補充 job_id, video_id 以利 callback 進度更新
            inputs = {
                "job_id": job_id,
                "video_id": video_id,
                "search_subject": "找出景點、餐廳、交通方式與住宿的地理位置",
            }
            # 進度: metadata 階段
            update_job("metadata", 25, status=JobStatus.RUNNING)

            # 執行 crewai 主流程（同步呼叫，實際可依需求細分進度）
            Trailtag = get_trailtag()
            logger.info(
                f"開始執行 CrewAI 任務 - job_id: {job_id}, video_id: {video_id}"
            )

            # 進度: 開始執行
            update_job("processing", 50, status=JobStatus.RUNNING)
            output = Trailtag().crew().kickoff(inputs=inputs)

            logger.info(
                f"CrewAI 任務完成 - job_id: {job_id}, output type: {type(output)}"
            )

            # 進度: geocode 完成 — 將完成的 job TTL 設為 60 秒
            update_job("geocode", 100, status=JobStatus.DONE, ttl=60)

            # 結果寫入 analysis 快取，供地圖查詢
            # 根據 CrewAI 文檔，crew().kickoff() 返回 CrewOutput 物件
            if output and hasattr(output, "pydantic") and output.pydantic:
                logger.info("使用 output.pydantic 儲存結果")
                cache.set(
                    f"analysis:{video_id}",
                    (
                        output.pydantic.model_dump()
                        if hasattr(output.pydantic, "model_dump")
                        else (
                            output.pydantic.dict()
                            if hasattr(output.pydantic, "dict")
                            else output.pydantic
                        )
                    ),
                )
            elif output and hasattr(output, "json_dict") and output.json_dict:
                logger.info("使用 output.json_dict 儲存結果")
                cache.set(f"analysis:{video_id}", output.json_dict)
            elif output and hasattr(output, "raw"):
                logger.info("使用 output.raw 儲存結果")
                # 嘗試解析 raw 輸出為 JSON
                try:
                    import json

                    raw_data = (
                        json.loads(output.raw)
                        if isinstance(output.raw, str)
                        else output.raw
                    )
                    cache.set(f"analysis:{video_id}", raw_data)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"無法解析 raw 輸出為 JSON: {output.raw}")
                    # 使用原始字串作為備用
                    cache.set(
                        f"analysis:{video_id}",
                        {"raw_output": str(output.raw), "video_id": video_id},
                    )
            else:
                logger.warning(
                    f"CrewAI 輸出格式不符預期: {type(output)}, 屬性: {dir(output) if hasattr(output, '__dict__') else 'N/A'}"
                )
                # 嘗試將整個輸出物件轉換為字典
                try:
                    if hasattr(output, "__dict__"):
                        cache.set(f"analysis:{video_id}", output.__dict__)
                    else:
                        cache.set(
                            f"analysis:{video_id}",
                            {"raw_output": str(output), "video_id": video_id},
                        )
                except Exception as e:
                    logger.error(f"儲存輸出失敗: {e}")

            # 任務完成，移除 video->job 映射以避免 stale state
            try:
                cache.delete(f"video_job:{video_id}")
            except Exception:
                logger.debug({"event": "video_job_delete_failed", "video_id": video_id})
        except Exception as e:
            # crewai 執行失敗，記錄錯誤並更新 job 狀態
            logger.error({"event": "job_failed", "job_id": job_id, "error": str(e)})
            update_job(
                "geocode",
                0,
                status=JobStatus.FAILED,
                extra={"error": {"type": "exception", "message": str(e)}},
            )
            # 任務失敗時也清除 video->job 映射
            try:
                cache.delete(f"video_job:{video_id}")
            except Exception:
                logger.debug({"event": "video_job_delete_failed", "video_id": video_id})
    except Exception as e:
        # 背景任務本身致命錯誤
        logger.error({"event": "job_fatal", "job_id": job_id, "error": str(e)})
        try:
            cache.delete(f"video_job:{video_id}")
        except Exception:
            logger.debug({"event": "video_job_delete_failed", "video_id": video_id})


@router.post(
    "/videos/analyze",
    response_model=JobResponse,
    summary="提交影片分析任務",
    description="提交新的 YouTube 影片分析請求，支援快取查詢與非同步任務分派。回傳 job_id 供進度查詢。",
)
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
        raise HTTPException(
            status_code=400,
            detail=f"無效的 YouTube URL：{str(e)}。請確認 URL 格式正確，支援的格式包括 youtube.com/watch?v=ID 或 youtu.be/ID",
        )

    # 快速檢測字幕可用性
    subtitle_status = check_subtitle_availability(video_id)
    logger.info(
        f"影片 {video_id} 字幕檢測結果: available={subtitle_status.available}, confidence={subtitle_status.confidence_score}"
    )

    # 如果沒有字幕可用，提供友善的錯誤訊息
    if not subtitle_status.available:
        logger.warning(f"影片 {video_id} 無可用字幕")
        raise HTTPException(
            status_code=422,
            detail={
                "message": "此影片沒有可用的字幕或自動字幕，無法進行分析",
                "suggestion": "請選擇有字幕的影片，或者等待 YouTube 生成自動字幕後再試",
                "video_id": video_id,
                "subtitle_status": subtitle_status.model_dump(),
            },
        )

    # 檢查是否已有此影片的分析結果（查快取）
    cache = get_cache()
    cache_key = f"analysis:{video_id}"
    cached_result = cache.get(cache_key)
    if cached_result:
        logger.info({"event": "cache_hit", "video_id": video_id})
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        job = {
            "job_id": job_id,
            "video_id": video_id,
            "status": JobStatus.DONE,
            "phase": Phase.GEOCODE,
            "progress": 100.0,
            "cached": True,
            "created_at": now,
            "updated_at": now,
            "subtitle_availability": subtitle_status.model_dump(),
        }
        cache.set(f"job:{job_id}", job, ttl=60)
        # 建立 video_id -> job_id 映射，方便以 video_id 查詢目前對應的 job
        try:
            cache.set(f"video_job:{video_id}", job_id, ttl=60)
        except Exception:
            # 不應該阻斷主流程，僅記錄即可
            logger.debug(
                {
                    "event": "video_job_map_failed",
                    "video_id": video_id,
                    "job_id": job_id,
                }
            )
        return JobResponse(**job)

    # 創建新任務
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    job = {
        "job_id": job_id,
        "video_id": video_id,
        "status": JobStatus.QUEUED,
        "phase": None,
        "progress": 0.0,
        "cached": False,
        "created_at": now,
        "updated_at": now,
        "subtitle_availability": subtitle_status.model_dump(),
    }
    cache.set(f"job:{job_id}", job)
    # 設定 video_id -> job_id 映射，方便以 video_id 查詢目前對應的 job
    try:
        cache.set(f"video_job:{video_id}", job_id)
    except Exception:
        logger.debug(
            {"event": "video_job_map_failed", "video_id": video_id, "job_id": job_id}
        )
    logger.info({"event": "job_created", "job_id": job_id, "video_id": video_id})

    # 分派 crewai 任務到背景，執行分析與進度更新
    background_tasks.add_task(run_trailtag_job, job_id, video_id)
    return JobResponse(**job)


# 查詢任務狀態 API
@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    summary="查詢任務狀態",
    description="根據 job_id 查詢分析任務的進度、階段與錯誤資訊。",
)
async def get_job_status(job_id: str = Path(..., description="任務 ID")) -> JobResponse:
    """
    根據 job_id 查詢任務狀態，回傳進度、階段、錯誤等資訊。
    若 job 不存在則回傳 404。
    """
    cache = get_cache()
    job = cache.get(f"job:{job_id}")
    if not job:
        logger.warning({"event": "job_not_found", "job_id": job_id})
        raise HTTPException(status_code=404, detail=f"任務不存在: {job_id}")
    return JobResponse(**job)


# 查詢影片地點視覺化資料 API
@router.get(
    "/videos/{video_id}/locations",
    response_model=MapVisualization,
    summary="查詢影片地點視覺化資料",
    description="根據 YouTube video_id 查詢分析後的地點視覺化資料（地圖路線等）。",
)
async def get_video_locations(
    video_id: str = Path(..., description="YouTube 影片 ID"),
) -> MapVisualization:
    """
    根據 video_id 查詢分析後的地點視覺化資料（地圖路線等）。
    若查無資料則回傳 404。
    """
    cache = get_cache()
    cache_key = f"analysis:{video_id}"
    result = cache.get(cache_key)
    if not result:
        logger.warning({"event": "locations_not_found", "video_id": video_id})
        raise HTTPException(status_code=404, detail=f"找不到影片地點資料: {video_id}")
    return MapVisualization(**result)


@router.get(
    "/videos/{video_id}/subtitles/check",
    response_model=SubtitleStatus,
    summary="檢查影片字幕可用性",
    description="快速檢測 YouTube 影片的字幕可用性，包括手動字幕和自動字幕資訊。",
)
async def check_video_subtitles(
    video_id: str = Path(..., description="YouTube 影片 ID"),
) -> SubtitleStatus:
    """
    檢查指定影片的字幕可用性，回傳詳細的字幕狀態資訊。
    用於在分析前快速判斷影片是否適合處理。
    """
    try:
        subtitle_status = check_subtitle_availability(video_id)
        logger.info(
            f"字幕檢查請求 - 影片: {video_id}, 結果: {subtitle_status.available}"
        )
        return subtitle_status
    except Exception as e:
        logger.error(f"字幕檢查失敗 {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"無法檢查影片字幕狀態: {str(e)}")


@router.get(
    "/videos/{video_id}/job",
    response_model=JobStatusResponse,
    summary="以 video_id 查詢對應的 job 狀態",
    description="根據 YouTube video_id 查詢目前對應的 job（若有）。若未找到則回傳 404。",
)
async def get_job_by_video(
    video_id: str = Path(..., description="YouTube 影片 ID"),
) -> JobStatusResponse:
    """
    先嘗試使用 video_job:{video_id} 映射取得對應 job_id，若未命中則回傳 404。
    若命中則回傳該 job 的簡要狀態（job_id, status, phase, progress, stats, error）。
    """
    cache = get_cache()
    # 嘗試直接查找映射
    try:
        mapped = cache.get(f"video_job:{video_id}")
    except Exception:
        mapped = None

    if not mapped:
        # 若映射不存在，嘗試回傳 404（避免遍歷全部快取）
        logger.info({"event": "video_job_not_found", "video_id": video_id})
        raise HTTPException(
            status_code=404, detail=f"找不到針對影片的進行中任務: {video_id}"
        )

    job = cache.get(f"job:{mapped}")
    if not job:
        logger.info(
            {"event": "job_not_found_for_video", "video_id": video_id, "job_id": mapped}
        )
        raise HTTPException(status_code=404, detail=f"找不到 job: {mapped}")

    # 構建回傳格式
    resp = {
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "phase": job.get("phase"),
        "progress": job.get("progress", 0),
        "stats": {},
        "error": (
            job.get("error")
            if job.get("status") in [JobStatus.FAILED, JobStatus.CANCELED]
            else None
        ),
    }
    return JobStatusResponse(**resp)
