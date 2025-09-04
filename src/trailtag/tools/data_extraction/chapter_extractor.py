"""
YouTube 章節資訊提取工具
用於從 YouTube 影片中提取章節資訊並與地點時間進行映射。
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

try:
    import yt_dlp

    YT_DLP_AVAILABLE = True
except ImportError as e:
    YT_DLP_AVAILABLE = False
    logging.warning(f"yt-dlp not available for chapter extraction: {e}")

from src.api.core.logger_config import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractedChapter:
    """提取的章節資訊"""

    title: str
    start_time: int  # 開始時間（秒）
    end_time: Optional[int]  # 結束時間（秒）
    duration: Optional[int]  # 持續時間（秒）
    description: Optional[str] = None  # 章節描述
    thumbnail_url: Optional[str] = None  # 章節縮圖
    locations: List[str] = None  # 從標題推斷的地點
    confidence: float = 0.8  # 提取信心度


@dataclass
class ChapterLocationMapping:
    """章節與地點的映射關係"""

    chapter_title: str
    start_time: int
    end_time: Optional[int]
    extracted_locations: List[str]
    potential_locations: List[str]  # 可能的地點（較低信心度）
    confidence_score: float


@dataclass
class ChapterExtractionResult:
    """章節提取結果"""

    video_id: str
    total_chapters: int
    chapters: List[ExtractedChapter]
    location_mappings: List[ChapterLocationMapping]
    extraction_method: str  # api, description_parsing, manual
    metadata: Dict[str, Any]  # 額外的元資料


class ChapterExtractorInput(BaseModel):
    """章節提取器輸入模型"""

    video_id: str = Field(..., description="YouTube 影片ID")
    video_url: str = Field(None, description="YouTube 影片URL（可選）")
    fallback_to_description: bool = Field(
        default=True, description="如果 API 失敗，是否回退到描述解析"
    )


class ChapterExtractor(BaseTool):
    """
    YouTube 章節資訊提取工具

    功能：
    1. 從 YouTube API 提取官方章節資訊
    2. 從影片描述中解析手動標記的章節
    3. 地點與時間映射分析
    4. 章節標題的地點實體識別
    """

    name: str = "chapter_extractor"
    description: str = """
    提取 YouTube 影片的章節資訊，並分析章節與地點的映射關係。
    輸入: 影片ID或URL
    輸出: 結構化的章節資訊，包含時間點和地點映射
    """
    args_schema: type[BaseModel] = ChapterExtractorInput

    def __init__(self):
        """初始化章節提取器"""
        super().__init__()
        if not YT_DLP_AVAILABLE:
            logger.warning(
                "yt-dlp not available, falling back to basic extraction only"
            )

    def _extract_chapters_from_yt_dlp(
        self, video_id: str
    ) -> Tuple[List[ExtractedChapter], Dict[str, Any]]:
        """使用 yt-dlp 提取官方章節資訊"""
        chapters = []
        metadata = {}

        if not YT_DLP_AVAILABLE:
            logger.warning("yt-dlp not available, skipping official chapter extraction")
            return chapters, metadata

        try:
            video_url = f"https://www.youtube.com/watch?v={video_id}"

            # 配置 yt-dlp 選項
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "writesubtitles": False,
                "writeautomaticsub": False,
                "skip_download": True,
                # 設定 User-Agent 以避免 403 錯誤
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                },
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(video_url, download=False)

                    # 提取基本元資料
                    metadata = {
                        "title": info.get("title", ""),
                        "duration": info.get("duration", 0),
                        "view_count": info.get("view_count", 0),
                        "upload_date": info.get("upload_date", ""),
                        "uploader": info.get("uploader", ""),
                    }

                    # 提取章節資訊
                    if "chapters" in info and info["chapters"]:
                        for i, chapter in enumerate(info["chapters"]):
                            start_time = int(chapter.get("start_time", 0))
                            end_time = (
                                int(chapter.get("end_time", 0))
                                if chapter.get("end_time")
                                else None
                            )
                            duration = (end_time - start_time) if end_time else None

                            extracted_chapter = ExtractedChapter(
                                title=chapter.get("title", f"Chapter {i+1}"),
                                start_time=start_time,
                                end_time=end_time,
                                duration=duration,
                                confidence=0.95,  # 官方章節信心度高
                            )

                            # 從章節標題提取可能的地點
                            extracted_chapter.locations = (
                                self._extract_locations_from_title(
                                    extracted_chapter.title
                                )
                            )

                            chapters.append(extracted_chapter)

                        logger.info(
                            f"Extracted {len(chapters)} official chapters from video {video_id}"
                        )
                    else:
                        logger.info(f"No official chapters found in video {video_id}")

                except Exception as e:
                    logger.error(f"yt-dlp extraction failed for video {video_id}: {e}")

        except Exception as e:
            logger.error(f"Failed to initialize yt-dlp for video {video_id}: {e}")

        return chapters, metadata

    def _extract_chapters_from_description(
        self, description: str, video_duration: int = None
    ) -> List[ExtractedChapter]:
        """從影片描述中解析章節資訊"""
        chapters = []

        if not description:
            return chapters

        # 常見章節時間戳記格式
        chapter_patterns = [
            # 標準格式: 00:00 - 章節標題
            r"(\d{1,2}:\d{2}(?::\d{2})?)\s*[-–—]\s*(.+?)(?:\n|$)",
            # 格式: 00:00 章節標題
            r"(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+?)(?:\n|$)",
            # 格式: [00:00] 章節標題
            r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.+?)(?:\n|$)",
            # 格式: (00:00) 章節標題
            r"\((\d{1,2}:\d{2}(?::\d{2})?)\)\s*(.+?)(?:\n|$)",
        ]

        for pattern in chapter_patterns:
            matches = re.finditer(pattern, description, re.MULTILINE | re.IGNORECASE)
            temp_chapters = []

            for match in matches:
                timestamp_str = match.group(1)
                title = match.group(2).strip()

                # 解析時間戳記為秒數
                start_time = self._parse_timestamp_to_seconds(timestamp_str)
                if start_time is not None and title:
                    temp_chapters.append(
                        {
                            "start_time": start_time,
                            "title": title,
                            "timestamp_str": timestamp_str,
                        }
                    )

            # 如果這個模式找到了章節，處理並返回
            if temp_chapters:
                # 按時間排序
                temp_chapters.sort(key=lambda x: x["start_time"])

                for i, chapter_data in enumerate(temp_chapters):
                    # 計算結束時間
                    if i + 1 < len(temp_chapters):
                        end_time = temp_chapters[i + 1]["start_time"]
                    else:
                        end_time = video_duration if video_duration else None

                    duration = (
                        (end_time - chapter_data["start_time"]) if end_time else None
                    )

                    extracted_chapter = ExtractedChapter(
                        title=chapter_data["title"],
                        start_time=chapter_data["start_time"],
                        end_time=end_time,
                        duration=duration,
                        confidence=0.75,  # 描述解析的信心度中等
                    )

                    # 從章節標題提取地點
                    extracted_chapter.locations = self._extract_locations_from_title(
                        extracted_chapter.title
                    )

                    chapters.append(extracted_chapter)

                if chapters:
                    logger.info(
                        f"Extracted {len(chapters)} chapters from description using pattern"
                    )
                    break  # 找到章節後就停止嘗試其他模式

        return chapters

    def _parse_timestamp_to_seconds(self, timestamp: str) -> Optional[int]:
        """將時間戳記轉換為秒數"""
        try:
            # 清理時間戳記字符串
            timestamp = timestamp.strip()
            parts = timestamp.split(":")

            if len(parts) == 2:  # MM:SS
                minutes, seconds = map(int, parts)
                return minutes * 60 + seconds
            elif len(parts) == 3:  # HH:MM:SS
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds
            else:
                logger.warning(f"Invalid timestamp format: {timestamp}")
                return None

        except Exception as e:
            logger.error(f"Failed to parse timestamp {timestamp}: {e}")
            return None

    def _extract_locations_from_title(self, title: str) -> List[str]:
        """從章節標題中提取地點資訊"""
        locations = []

        # 地點關鍵詞模式
        location_patterns = [
            # 城市名稱（大寫開頭）
            r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b",
            # 中文地點
            r"([一-龯]+(?:市|縣|區|鎮|村|街|路|道|橋|山|河|湖|海|島|港|灣|廟|寺|塔|樓|園|館|站|場|機場))",
            # 常見地標詞彙
            r"([A-Z][a-zA-Z\s]*(?:Tower|Building|Park|Museum|Temple|Station|Airport|Hotel|Restaurant|Cafe|Shop|Mall|Market|Beach|Mountain|Lake|River))",
        ]

        title_lower = title.lower()

        # 檢查是否包含地點指示詞
        location_indicators = [
            "in",
            "at",
            "to",
            "from",
            "visit",
            "explore",
            "在",
            "到",
            "去",
            "來自",
            "參觀",
            "探索",
        ]
        has_location_context = any(
            indicator in title_lower for indicator in location_indicators
        )

        for pattern in location_patterns:
            matches = re.findall(pattern, title)
            for match in matches:
                potential_location = match.strip()

                # 過濾明顯不是地點的詞彙
                excluded_words = {
                    "Day",
                    "Night",
                    "Morning",
                    "Evening",
                    "First",
                    "Last",
                    "Best",
                    "Good",
                    "Bad",
                    "New",
                    "Old",
                    "Big",
                    "Small",
                    "Beautiful",
                    "Amazing",
                    "Awesome",
                    "Great",
                    "Part",
                    "Episode",
                    "Chapter",
                    "Video",
                    "Travel",
                    "Trip",
                    "Journey",
                    "第一",
                    "第二",
                    "第三",
                    "最後",
                    "最好",
                    "最美",
                    "最棒",
                    "旅行",
                    "旅程",
                    "影片",
                    "部分",
                }

                if (
                    potential_location not in excluded_words
                    and len(potential_location) >= 2
                    and not potential_location.isdigit()
                ):
                    # 如果有地點上下文或長度較長，增加信心度
                    if has_location_context or len(potential_location) >= 4:
                        locations.append(potential_location)

        # 去重並限制數量
        unique_locations = list(dict.fromkeys(locations))[:5]  # 保持順序並去重

        return unique_locations

    def _create_location_mappings(
        self, chapters: List[ExtractedChapter]
    ) -> List[ChapterLocationMapping]:
        """創建章節與地點的映射關係"""
        mappings = []

        for chapter in chapters:
            # 提取高信心度地點
            extracted_locations = chapter.locations or []

            # 從標題中提取額外的潛在地點
            potential_locations = self._extract_potential_locations(chapter.title)

            # 計算整體信心度
            confidence_score = chapter.confidence
            if extracted_locations:
                confidence_score *= 0.9  # 有地點資訊時略微降低，因為地點識別可能有誤

            mapping = ChapterLocationMapping(
                chapter_title=chapter.title,
                start_time=chapter.start_time,
                end_time=chapter.end_time,
                extracted_locations=extracted_locations,
                potential_locations=potential_locations,
                confidence_score=confidence_score,
            )

            mappings.append(mapping)

        return mappings

    def _extract_potential_locations(self, title: str) -> List[str]:
        """提取潛在的地點（較低信心度）"""
        potential_locations = []

        # 更寬鬆的地點模式
        loose_patterns = [
            # 任何大寫詞彙（可能是地名）
            r"\b([A-Z][a-zA-Z]{2,})\b",
            # 數字+地點後綴的組合
            r"(\d+[a-zA-Z]*(?:街|路|號|巷|弄|樓))",
        ]

        for pattern in loose_patterns:
            matches = re.findall(pattern, title)
            for match in matches:
                if len(match) >= 3 and match.isalpha():  # 至少3個字符且全為字母
                    potential_locations.append(match)

        # 去重並限制數量
        return list(dict.fromkeys(potential_locations))[:3]

    def _run(
        self, video_id: str, video_url: str = None, fallback_to_description: bool = True
    ) -> str:
        """執行章節提取"""
        try:
            logger.info(f"Extracting chapters for video {video_id}")

            if not video_id:
                return json.dumps(
                    {"error": "Video ID is required", "video_id": video_id}
                )

            chapters = []
            metadata = {}
            extraction_method = "none"

            # 1. 首先嘗試使用 yt-dlp 提取官方章節
            if YT_DLP_AVAILABLE:
                try:
                    chapters, metadata = self._extract_chapters_from_yt_dlp(video_id)
                    if chapters:
                        extraction_method = "api"
                        logger.info(
                            f"Successfully extracted {len(chapters)} chapters via yt-dlp"
                        )
                except Exception as e:
                    logger.error(f"yt-dlp chapter extraction failed: {e}")

            # 2. 如果沒有找到官方章節且允許回退，嘗試從描述解析
            if not chapters and fallback_to_description:
                try:
                    # 這裡需要獲取影片描述，可以通過已有的 YouTube metadata tool
                    # 暫時使用空描述作為示例
                    description = metadata.get("description", "")
                    video_duration = metadata.get("duration")

                    if description:
                        chapters = self._extract_chapters_from_description(
                            description, video_duration
                        )
                        if chapters:
                            extraction_method = "description_parsing"
                            logger.info(
                                f"Successfully extracted {len(chapters)} chapters from description"
                            )
                except Exception as e:
                    logger.error(f"Description parsing failed: {e}")

            # 3. 創建地點映射
            location_mappings = (
                self._create_location_mappings(chapters) if chapters else []
            )

            # 組裝結果
            result = ChapterExtractionResult(
                video_id=video_id,
                total_chapters=len(chapters),
                chapters=chapters,
                location_mappings=location_mappings,
                extraction_method=extraction_method,
                metadata=metadata,
            )

            # 轉換為 JSON
            result_dict = asdict(result)

            logger.info(
                f"Chapter extraction completed: {len(chapters)} chapters, {len(location_mappings)} location mappings"
            )

            return json.dumps(result_dict, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Chapter extraction failed: {e}")
            return json.dumps(
                {
                    "error": f"Chapter extraction failed: {str(e)}",
                    "video_id": video_id,
                    "total_chapters": 0,
                    "chapters": [],
                    "location_mappings": [],
                    "extraction_method": "error",
                    "metadata": {},
                }
            )
