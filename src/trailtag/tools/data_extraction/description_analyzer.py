"""
影片描述分析工具
用於從 YouTube 影片描述中提取地點資訊、時間戳記等有用信息。
整合 spaCy NLP 和 Transformers 模型進行深度分析。
"""

import re
import json
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass, asdict
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

try:
    import spacy
    from transformers import pipeline

    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    DEPENDENCIES_AVAILABLE = False
    logging.warning(f"Description analyzer dependencies not available: {e}")

from src.api.core.logger_config import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractedLocation:
    """提取的地點資訊"""

    name: str
    confidence: float
    context: str  # 包含該地點的原始文本
    category: str  # 地點類型 (city, landmark, region, etc.)
    timestamp: Optional[str] = None  # 如果有相關時間戳記
    coordinates: Optional[Tuple[float, float]] = None  # 如果能解析出座標


@dataclass
class ExtractedTimestamp:
    """提取的時間戳記資訊"""

    original_text: str
    seconds: int
    context: str  # 周圍的文本上下文
    confidence: float


@dataclass
class DescriptionAnalysisResult:
    """描述分析結果"""

    locations: List[ExtractedLocation]
    timestamps: List[ExtractedTimestamp]
    keywords: List[str]
    summary: str
    language: str
    sentiment: str  # positive, negative, neutral


class DescriptionAnalyzerInput(BaseModel):
    """描述分析器輸入模型"""

    description: str = Field(..., description="YouTube 影片描述文本")
    video_id: str = Field(..., description="影片ID，用於上下文關聯")
    language: str = Field(default="auto", description="文本語言，auto為自動檢測")


class DescriptionAnalyzer(BaseTool):
    """
    YouTube 影片描述分析工具

    功能：
    1. 地點實體識別和分類
    2. 時間戳記提取和解析
    3. 關鍵詞提取
    4. 文本摘要生成
    5. 情感分析
    """

    name: str = "description_analyzer"
    description: str = """
    分析 YouTube 影片描述，提取地點、時間戳記等關鍵資訊。
    輸入: 影片描述文本和影片ID
    輸出: 結構化的分析結果，包含地點、時間戳記、關鍵詞等
    """
    args_schema: type[BaseModel] = DescriptionAnalyzerInput

    def __init__(self):
        """初始化分析器"""
        super().__init__()
        self._nlp_model = None
        self._ner_pipeline = None
        self._sentiment_pipeline = None
        self._summarizer = None

        if not DEPENDENCIES_AVAILABLE:
            logger.warning(
                "Dependencies not available, analyzer will use basic extraction only"
            )

    @property
    def nlp_model(self):
        """延遲載入 spaCy 模型"""
        if self._nlp_model is None and DEPENDENCIES_AVAILABLE:
            try:
                # 嘗試載入中文模型，回退到英文模型
                try:
                    self._nlp_model = spacy.load("zh_core_web_sm")
                    logger.info("Loaded Chinese spaCy model")
                except OSError:
                    self._nlp_model = spacy.load("en_core_web_sm")
                    logger.info(
                        "Loaded English spaCy model (Chinese model not available)"
                    )
            except Exception as e:
                logger.error(f"Failed to load spaCy model: {e}")
        return self._nlp_model

    @property
    def ner_pipeline(self):
        """延遲載入 NER pipeline"""
        if self._ner_pipeline is None and DEPENDENCIES_AVAILABLE:
            try:
                self._ner_pipeline = pipeline(
                    "ner",
                    model="dbmdz/bert-large-cased-finetuned-conll03-english",
                    aggregation_strategy="simple",
                )
                logger.info("Loaded NER pipeline")
            except Exception as e:
                logger.error(f"Failed to load NER pipeline: {e}")
        return self._ner_pipeline

    @property
    def sentiment_pipeline(self):
        """延遲載入情感分析 pipeline"""
        if self._sentiment_pipeline is None and DEPENDENCIES_AVAILABLE:
            try:
                self._sentiment_pipeline = pipeline("sentiment-analysis")
                logger.info("Loaded sentiment analysis pipeline")
            except Exception as e:
                logger.error(f"Failed to load sentiment pipeline: {e}")
        return self._sentiment_pipeline

    def _extract_timestamps(self, text: str) -> List[ExtractedTimestamp]:
        """從文本中提取時間戳記"""
        timestamps = []

        # 常見的時間戳記格式
        patterns = [
            # MM:SS 或 HH:MM:SS 格式
            (r"(\d{1,2}:\d{2}(?::\d{2})?)", "time"),
            # 文字描述的時間點
            (r"(?:at|在)\s*(\d{1,2}:\d{2}(?::\d{2})?)", "contextual_time"),
            # 分鐘標記
            (r"(\d+)\s*(?:分鐘|分|minutes?|mins?)", "minute_mark"),
            # 秒數標記
            (r"(\d+)\s*(?:秒|seconds?|secs?)", "second_mark"),
        ]

        for pattern, pattern_type in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                timestamp_text = match.group(1)
                context = text[max(0, match.start() - 50) : match.end() + 50]

                try:
                    seconds = self._parse_timestamp_to_seconds(
                        timestamp_text, pattern_type
                    )
                    if seconds is not None:
                        timestamps.append(
                            ExtractedTimestamp(
                                original_text=timestamp_text,
                                seconds=seconds,
                                context=context.strip(),
                                confidence=0.9 if pattern_type == "time" else 0.7,
                            )
                        )
                except Exception as e:
                    logger.debug(f"Failed to parse timestamp {timestamp_text}: {e}")

        return timestamps

    def _parse_timestamp_to_seconds(
        self, timestamp: str, pattern_type: str
    ) -> Optional[int]:
        """將時間戳記轉換為秒數"""
        try:
            if pattern_type == "time" or pattern_type == "contextual_time":
                # 解析 MM:SS 或 HH:MM:SS 格式
                parts = timestamp.split(":")
                if len(parts) == 2:  # MM:SS
                    minutes, seconds = map(int, parts)
                    return minutes * 60 + seconds
                elif len(parts) == 3:  # HH:MM:SS
                    hours, minutes, seconds = map(int, parts)
                    return hours * 3600 + minutes * 60 + seconds
            elif pattern_type == "minute_mark":
                # 直接是分鐘數
                minutes = int(re.search(r"\d+", timestamp).group())
                return minutes * 60
            elif pattern_type == "second_mark":
                # 直接是秒數
                return int(re.search(r"\d+", timestamp).group())
        except Exception:
            pass
        return None

    def _extract_locations_basic(self, text: str) -> List[ExtractedLocation]:
        """基礎地點提取（不依賴 ML 模型）"""
        locations = []

        # 常見地點關鍵詞
        location_patterns = [
            # 城市/國家
            (r"(?:in|at|到|在)\s+([A-Z][a-zA-Z\s]+(?:City|市|縣|區))", "city"),
            (r"([A-Z][a-zA-Z]+(?:国|國|country))", "country"),
            # 地標
            (
                r"([A-Z][a-zA-Z\s]+(?:Tower|Building|Park|Museum|Temple|Station|Airport|山|塔|樓|公園|博物館|寺|站|機場))",
                "landmark",
            ),
            # 餐廳/商店
            (
                r"([A-Z][a-zA-Z\s]+(?:Restaurant|Cafe|Shop|Store|Hotel|餐廳|咖啡廳|店|酒店))",
                "business",
            ),
        ]

        for pattern, category in location_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                location_name = match.group(1).strip()
                context = text[max(0, match.start() - 30) : match.end() + 30]

                locations.append(
                    ExtractedLocation(
                        name=location_name,
                        confidence=0.6,  # 基礎提取信心度較低
                        context=context.strip(),
                        category=category,
                    )
                )

        return locations

    def _extract_locations_advanced(self, text: str) -> List[ExtractedLocation]:
        """進階地點提取（使用 ML 模型）"""
        locations = []

        try:
            # 使用 spaCy 進行 NER
            if self.nlp_model:
                doc = self.nlp_model(text)
                for ent in doc.ents:
                    if ent.label_ in [
                        "GPE",
                        "LOC",
                        "ORG",
                    ]:  # Geopolitical entity, Location, Organization
                        category = self._classify_location_type(ent.text, ent.label_)
                        locations.append(
                            ExtractedLocation(
                                name=ent.text,
                                confidence=0.8,
                                context=text[
                                    max(0, ent.start_char - 30) : ent.end_char + 30
                                ],
                                category=category,
                            )
                        )

            # 使用 Transformers NER pipeline 作為補充
            if self.ner_pipeline:
                ner_results = self.ner_pipeline(text)
                for result in ner_results:
                    if (
                        result["entity_group"] in ["LOC", "MISC"]
                        and result["score"] > 0.7
                    ):
                        category = self._classify_location_type(
                            result["word"], result["entity_group"]
                        )
                        locations.append(
                            ExtractedLocation(
                                name=result["word"],
                                confidence=result["score"],
                                context=text[
                                    max(0, result["start"] - 30) : result["end"] + 30
                                ],
                                category=category,
                            )
                        )

        except Exception as e:
            logger.error(f"Advanced location extraction failed: {e}")
            # 回退到基礎提取
            return self._extract_locations_basic(text)

        return locations

    def _classify_location_type(self, location_name: str, entity_label: str) -> str:
        """分類地點類型"""
        location_lower = location_name.lower()

        # 地標關鍵詞
        if any(
            keyword in location_lower
            for keyword in [
                "tower",
                "building",
                "museum",
                "temple",
                "park",
                "塔",
                "樓",
                "博物館",
                "寺",
                "公園",
            ]
        ):
            return "landmark"
        # 城市關鍵詞
        elif any(keyword in location_lower for keyword in ["city", "市", "縣", "區"]):
            return "city"
        # 國家關鍵詞
        elif any(keyword in location_lower for keyword in ["country", "國", "国"]):
            return "country"
        # 商業場所
        elif any(
            keyword in location_lower
            for keyword in [
                "restaurant",
                "cafe",
                "hotel",
                "shop",
                "餐廳",
                "咖啡",
                "酒店",
                "店",
            ]
        ):
            return "business"
        else:
            # 根據 NER 標籤推斷
            if entity_label == "GPE":
                return "city"
            elif entity_label == "LOC":
                return "landmark"
            else:
                return "unknown"

    def _extract_keywords(self, text: str) -> List[str]:
        """提取關鍵詞"""
        keywords = []

        try:
            if self.nlp_model:
                doc = self.nlp_model(text)
                # 提取名詞和形容詞作為關鍵詞
                keywords = [
                    token.lemma_.lower()
                    for token in doc
                    if token.pos_ in ["NOUN", "ADJ"]
                    and not token.is_stop
                    and len(token.text) > 2
                    and token.is_alpha
                ]
                # 去重並限制數量
                keywords = list(set(keywords))[:20]
            else:
                # 簡單的關鍵詞提取
                import re

                words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
                # 基本停用詞過濾
                stop_words = {
                    "the",
                    "and",
                    "but",
                    "are",
                    "was",
                    "were",
                    "been",
                    "have",
                    "has",
                    "had",
                    "will",
                    "would",
                    "could",
                    "should",
                }
                keywords = [word for word in set(words) if word not in stop_words][:15]

        except Exception as e:
            logger.error(f"Keyword extraction failed: {e}")

        return keywords

    def _generate_summary(self, text: str) -> str:
        """生成文本摘要"""
        if len(text) < 100:
            return text

        try:
            # 簡單的摘要邏輯：取前3句話或前200字符
            sentences = text.split("。")
            if len(sentences) >= 3:
                summary = "。".join(sentences[:3]) + "。"
            else:
                summary = text[:200] + ("..." if len(text) > 200 else "")

            return summary.strip()

        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return text[:150] + ("..." if len(text) > 150 else "")

    def _analyze_sentiment(self, text: str) -> str:
        """分析文本情感"""
        try:
            if self.sentiment_pipeline:
                result = self.sentiment_pipeline(text[:512])  # 限制長度
                label = result[0]["label"].lower()
                return (
                    "positive"
                    if label == "positive"
                    else "negative"
                    if label == "negative"
                    else "neutral"
                )
            else:
                # 簡單的情感分析
                positive_words = [
                    "好",
                    "棒",
                    "美",
                    "讚",
                    "愛",
                    "good",
                    "great",
                    "awesome",
                    "beautiful",
                    "love",
                    "amazing",
                ]
                negative_words = [
                    "壞",
                    "糟",
                    "差",
                    "爛",
                    "bad",
                    "terrible",
                    "awful",
                    "horrible",
                    "hate",
                ]

                text_lower = text.lower()
                pos_count = sum(1 for word in positive_words if word in text_lower)
                neg_count = sum(1 for word in negative_words if word in text_lower)

                if pos_count > neg_count:
                    return "positive"
                elif neg_count > pos_count:
                    return "negative"
                else:
                    return "neutral"

        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return "neutral"

    def _detect_language(self, text: str) -> str:
        """檢測文本語言"""
        try:
            # 簡單的語言檢測
            chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
            total_chars = len(text)

            if chinese_chars / max(total_chars, 1) > 0.3:
                return "zh"
            else:
                return "en"

        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            return "auto"

    def _run(self, description: str, video_id: str, language: str = "auto") -> str:
        """執行描述分析"""
        try:
            logger.info(f"Analyzing description for video {video_id}")

            if not description or not description.strip():
                return json.dumps(
                    {"error": "Empty description provided", "video_id": video_id}
                )

            # 檢測語言
            detected_language = (
                self._detect_language(description) if language == "auto" else language
            )

            # 提取時間戳記
            timestamps = self._extract_timestamps(description)

            # 提取地點資訊
            if DEPENDENCIES_AVAILABLE and self.nlp_model:
                locations = self._extract_locations_advanced(description)
            else:
                locations = self._extract_locations_basic(description)

            # 去重地點
            unique_locations = []
            seen_names = set()
            for loc in locations:
                if loc.name.lower() not in seen_names:
                    unique_locations.append(loc)
                    seen_names.add(loc.name.lower())

            # 提取關鍵詞
            keywords = self._extract_keywords(description)

            # 生成摘要
            summary = self._generate_summary(description)

            # 分析情感
            sentiment = self._analyze_sentiment(description)

            # 組裝結果
            result = DescriptionAnalysisResult(
                locations=unique_locations,
                timestamps=timestamps,
                keywords=keywords,
                summary=summary,
                language=detected_language,
                sentiment=sentiment,
            )

            # 轉換為 JSON
            result_dict = asdict(result)

            logger.info(
                f"Description analysis completed: {len(unique_locations)} locations, {len(timestamps)} timestamps, {len(keywords)} keywords"
            )

            return json.dumps(result_dict, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Description analysis failed: {e}")
            return json.dumps(
                {
                    "error": f"Analysis failed: {str(e)}",
                    "video_id": video_id,
                    "locations": [],
                    "timestamps": [],
                    "keywords": [],
                    "summary": "",
                    "language": "unknown",
                    "sentiment": "neutral",
                }
            )
