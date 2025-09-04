"""
YouTube 評論區資料挖掘工具
用於從 YouTube 影片評論中挖掘地點資訊和用戶反饋。
整合 NLTK 進行文本分析和情感分析。
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import Counter
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

try:
    from youtube_comment_downloader import YoutubeCommentDownloader
    import nltk
    from nltk.sentiment import SentimentIntensityAnalyzer
    # 已移除未使用的匯入

    NLTK_AVAILABLE = True

    # 嘗試下載必要的 NLTK 資料
    try:
        nltk.data.find("tokenizers/punkt")
        nltk.data.find("corpora/stopwords")
        nltk.data.find("taggers/averaged_perceptron_tagger")
        nltk.data.find("vader_lexicon")
    except LookupError:
        # 靜默下載，避免在生產環境中出現錯誤
        pass

except ImportError as e:
    NLTK_AVAILABLE = False
    logging.warning(f"Comment mining dependencies not available: {e}")

from src.api.core.logger_config import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractedComment:
    """提取的評論資訊"""

    comment_id: str
    author: str
    text: str
    likes: int
    published: str  # 發布時間
    reply_count: int = 0
    is_reply: bool = False
    parent_comment_id: Optional[str] = None


@dataclass
class LocationMention:
    """評論中的地點提及"""

    location_name: str
    mention_context: str  # 提及地點的上下文
    confidence: float
    comment_id: str
    sentiment: str  # positive, negative, neutral
    comment_likes: int  # 該評論的按讚數


@dataclass
class CommentAnalysis:
    """單個評論的分析結果"""

    comment_id: str
    locations_mentioned: List[str]
    sentiment_score: float  # -1 到 1
    sentiment_label: str  # positive, negative, neutral
    keywords: List[str]
    is_travel_related: bool
    confidence: float


@dataclass
class CommentMiningResult:
    """評論挖掘結果"""

    video_id: str
    total_comments: int
    processed_comments: int
    location_mentions: List[LocationMention]
    popular_locations: List[Tuple[str, int]]  # (地點名稱, 提及次數)
    sentiment_distribution: Dict[str, int]  # positive/negative/neutral 分布
    travel_keywords: List[Tuple[str, int]]  # (關鍵詞, 出現次數)
    top_comments: List[CommentAnalysis]  # 熱門評論分析
    extraction_stats: Dict[str, Any]


class CommentMinerInput(BaseModel):
    """評論挖掘器輸入模型"""

    video_id: str = Field(..., description="YouTube 影片ID")
    limit: int = Field(default=100, description="要分析的評論數量上限")
    include_replies: bool = Field(default=False, description="是否包含回覆評論")
    min_likes: int = Field(default=0, description="最少按讚數篩選")


class CommentMiner(BaseTool):
    """
    YouTube 評論區資料挖掘工具

    功能：
    1. 下載和分析 YouTube 評論
    2. 提取地點相關資訊
    3. 計算信心分數
    4. 情感分析
    5. 關鍵詞提取
    """

    name: str = "comment_miner"
    description: str = """
    挖掘 YouTube 影片評論區中的地點資訊和用戶反饋。
    輸入: 影片ID和分析參數
    輸出: 結構化的評論分析結果，包含地點提及、情感分析等
    """
    args_schema: type[BaseModel] = CommentMinerInput

    def __init__(self):
        """初始化評論挖掘器"""
        super().__init__()
        self._downloader = None
        self._sentiment_analyzer = None

        if not NLTK_AVAILABLE:
            logger.warning("NLTK dependencies not available, using basic analysis only")

    @property
    def downloader(self):
        """延遲載入評論下載器"""
        if self._downloader is None and NLTK_AVAILABLE:
            try:
                self._downloader = YoutubeCommentDownloader()
                logger.info("Initialized YouTube comment downloader")
            except Exception as e:
                logger.error(f"Failed to initialize comment downloader: {e}")
        return self._downloader

    @property
    def sentiment_analyzer(self):
        """延遲載入情感分析器"""
        if self._sentiment_analyzer is None and NLTK_AVAILABLE:
            try:
                self._sentiment_analyzer = SentimentIntensityAnalyzer()
                logger.info("Initialized NLTK sentiment analyzer")
            except Exception as e:
                logger.error(f"Failed to initialize sentiment analyzer: {e}")
        return self._sentiment_analyzer

    def _download_comments(
        self, video_id: str, limit: int, include_replies: bool
    ) -> List[ExtractedComment]:
        """下載 YouTube 評論"""
        comments = []

        if not self.downloader:
            logger.error("Comment downloader not available")
            return comments

        try:
            logger.info(f"Downloading comments for video {video_id} (limit: {limit})")

            # 下載評論
            raw_comments = self.downloader.get_comments_from_url(
                f"https://www.youtube.com/watch?v={video_id}",
                sort_by=1,  # 按熱門程度排序
            )

            processed_count = 0
            for comment_data in raw_comments:
                if processed_count >= limit:
                    break

                try:
                    # 主評論
                    main_comment = ExtractedComment(
                        comment_id=comment_data.get("cid", ""),
                        author=comment_data.get("author", "Unknown"),
                        text=comment_data.get("text", ""),
                        likes=int(comment_data.get("votes", 0)),
                        published=comment_data.get("time", ""),
                        reply_count=len(comment_data.get("replies", [])),
                        is_reply=False,
                    )

                    if main_comment.text.strip():  # 確保評論內容不為空
                        comments.append(main_comment)
                        processed_count += 1

                    # 處理回覆（如果啟用）
                    if (
                        include_replies
                        and comment_data.get("replies")
                        and processed_count < limit
                    ):
                        for reply_data in comment_data["replies"]:
                            if processed_count >= limit:
                                break

                            reply_comment = ExtractedComment(
                                comment_id=reply_data.get("cid", ""),
                                author=reply_data.get("author", "Unknown"),
                                text=reply_data.get("text", ""),
                                likes=int(reply_data.get("votes", 0)),
                                published=reply_data.get("time", ""),
                                is_reply=True,
                                parent_comment_id=main_comment.comment_id,
                            )

                            if reply_comment.text.strip():
                                comments.append(reply_comment)
                                processed_count += 1

                except Exception as e:
                    logger.debug(f"Error processing comment: {e}")
                    continue

            logger.info(f"Downloaded {len(comments)} comments")

        except Exception as e:
            logger.error(f"Failed to download comments: {e}")

        return comments

    def _extract_locations_from_comment(
        self, text: str
    ) -> List[Tuple[str, str, float]]:
        """從評論文本中提取地點資訊"""
        locations = []

        # 地點提取模式
        location_patterns = [
            # 城市/國家（英文）
            (r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+City|City)?)\b", "city", 0.7),
            # 中文地點
            (
                r"([一-龯]+(?:市|縣|區|鎮|村|街|路|道|山|河|湖|海|島|港|灣|機場))",
                "location",
                0.8,
            ),
            # 地標關鍵詞
            (
                r"([A-Z][a-zA-Z\s]+(?:Tower|Building|Park|Museum|Temple|Station|Airport|Hotel|Restaurant|Mall|Market|Beach))",
                "landmark",
                0.6,
            ),
            # 國家名稱
            (
                r"\b(Japan|Korea|Taiwan|China|Thailand|Vietnam|Singapore|Malaysia|Indonesia|Philippines|Cambodia|Laos|Myanmar|India|Nepal|Australia|New Zealand|France|Germany|Italy|Spain|UK|USA|Canada|Mexico|Brazil|Argentina|Chile)\b",
                "country",
                0.9,
            ),
        ]

        text_lower = text.lower()

        # 檢查是否有地點相關的上下文
        location_contexts = [
            "been to",
            "visited",
            "went to",
            "going to",
            "travel to",
            "trip to",
            "in",
            "at",
            "from",
            "live in",
            "stay in",
            "去過",
            "到過",
            "住在",
            "來自",
            "在",
            "旅行",
            "旅遊",
            "參觀",
            "拜訪",
        ]

        has_location_context = any(
            context in text_lower for context in location_contexts
        )

        for pattern, location_type, base_confidence in location_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                location_name = match.group(1).strip()

                # 過濾不太可能是地點的詞彙
                excluded_words = {
                    "Good",
                    "Bad",
                    "Great",
                    "Best",
                    "Nice",
                    "Beautiful",
                    "Amazing",
                    "Awesome",
                    "First",
                    "Last",
                    "Next",
                    "Previous",
                    "New",
                    "Old",
                    "Big",
                    "Small",
                    "Day",
                    "Night",
                    "Time",
                    "Year",
                    "Month",
                    "Week",
                    "Today",
                    "Yesterday",
                    "Video",
                    "Channel",
                    "Subscribe",
                    "Like",
                    "Comment",
                    "Share",
                }

                if (
                    location_name not in excluded_words
                    and len(location_name) >= 2
                    and not location_name.isdigit()
                ):
                    # 調整信心度
                    confidence = base_confidence
                    if has_location_context:
                        confidence = min(confidence + 0.15, 1.0)
                    if len(location_name) >= 4:
                        confidence = min(confidence + 0.1, 1.0)

                    # 獲取上下文
                    start_pos = max(0, match.start() - 30)
                    end_pos = min(len(text), match.end() + 30)
                    context = text[start_pos:end_pos].strip()

                    locations.append((location_name, context, confidence))

        # 去重（保留信心度最高的）
        unique_locations = {}
        for location, context, confidence in locations:
            location_key = location.lower()
            if (
                location_key not in unique_locations
                or unique_locations[location_key][2] < confidence
            ):
                unique_locations[location_key] = (location, context, confidence)

        return list(unique_locations.values())

    def _analyze_comment_sentiment(self, text: str) -> Tuple[float, str]:
        """分析評論情感"""
        try:
            if self.sentiment_analyzer:
                scores = self.sentiment_analyzer.polarity_scores(text)
                compound_score = scores["compound"]

                if compound_score >= 0.05:
                    label = "positive"
                elif compound_score <= -0.05:
                    label = "negative"
                else:
                    label = "neutral"

                return compound_score, label
            else:
                # 簡單的情感分析
                positive_words = [
                    "good",
                    "great",
                    "amazing",
                    "awesome",
                    "beautiful",
                    "love",
                    "like",
                    "best",
                    "wonderful",
                    "fantastic",
                    "好",
                    "棒",
                    "美",
                    "讚",
                    "愛",
                    "喜歡",
                    "最好",
                    "太棒了",
                    "很棒",
                    "不錯",
                ]
                negative_words = [
                    "bad",
                    "terrible",
                    "awful",
                    "hate",
                    "dislike",
                    "worst",
                    "boring",
                    "disappointing",
                    "壞",
                    "糟",
                    "差",
                    "爛",
                    "討厭",
                    "不喜歡",
                    "最糟",
                    "無聊",
                    "失望",
                ]

                text_lower = text.lower()
                pos_count = sum(1 for word in positive_words if word in text_lower)
                neg_count = sum(1 for word in negative_words if word in text_lower)

                if pos_count > neg_count:
                    return 0.5, "positive"
                elif neg_count > pos_count:
                    return -0.5, "negative"
                else:
                    return 0.0, "neutral"

        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return 0.0, "neutral"

    def _extract_travel_keywords(self, text: str) -> List[str]:
        """提取旅遊相關關鍵詞"""
        travel_keywords = []

        # 旅遊相關詞彙
        travel_terms = [
            # 英文
            "travel",
            "trip",
            "visit",
            "tour",
            "vacation",
            "holiday",
            "journey",
            "explore",
            "adventure",
            "hotel",
            "restaurant",
            "food",
            "culture",
            "history",
            "temple",
            "museum",
            "park",
            "beach",
            "mountain",
            "lake",
            "river",
            "city",
            "town",
            "village",
            "local",
            "guide",
            "tourist",
            "sightseeing",
            "backpack",
            "flight",
            "train",
            "bus",
            "taxi",
            "walking",
            "hiking",
            # 中文
            "旅行",
            "旅遊",
            "旅程",
            "度假",
            "假期",
            "參觀",
            "拜訪",
            "探索",
            "冒險",
            "酒店",
            "飯店",
            "餐廳",
            "美食",
            "文化",
            "歷史",
            "寺廟",
            "博物館",
            "公園",
            "海灘",
            "山",
            "湖",
            "河",
            "城市",
            "小鎮",
            "村莊",
            "當地",
            "導遊",
            "遊客",
            "觀光",
            "背包",
            "飛機",
            "火車",
            "巴士",
            "計程車",
            "步行",
            "健行",
        ]

        text_lower = text.lower()
        for term in travel_terms:
            if term in text_lower:
                travel_keywords.append(term)

        return travel_keywords

    def _is_travel_related(self, text: str, keywords: List[str]) -> bool:
        """判斷評論是否與旅遊相關"""
        if not keywords:
            return False

        # 如果包含多個旅遊關鍵詞，認為是旅遊相關
        return len(keywords) >= 1

    def _calculate_location_confidence(
        self, location_mention: LocationMention, all_mentions: List[LocationMention]
    ) -> float:
        """計算地點提及的信心分數"""
        base_confidence = location_mention.confidence

        # 根據評論按讚數調整信心度
        likes_factor = min(location_mention.comment_likes / 100.0, 0.2)  # 最多增加 0.2

        # 根據該地點在所有評論中的提及頻率調整
        mention_count = sum(
            1
            for mention in all_mentions
            if mention.location_name.lower() == location_mention.location_name.lower()
        )
        frequency_factor = min(mention_count / 10.0, 0.3)  # 最多增加 0.3

        # 根據情感調整（正面情感增加信心度）
        sentiment_factor = 0.1 if location_mention.sentiment == "positive" else 0.0

        final_confidence = min(
            base_confidence + likes_factor + frequency_factor + sentiment_factor, 1.0
        )
        return final_confidence

    def _run(
        self,
        video_id: str,
        limit: int = 100,
        include_replies: bool = False,
        min_likes: int = 0,
    ) -> str:
        """執行評論挖掘"""
        try:
            logger.info(f"Mining comments for video {video_id}")

            if not video_id:
                return json.dumps(
                    {"error": "Video ID is required", "video_id": video_id}
                )

            # 1. 下載評論
            comments = self._download_comments(video_id, limit, include_replies)

            if not comments:
                return json.dumps(
                    {
                        "error": "No comments found or download failed",
                        "video_id": video_id,
                        "total_comments": 0,
                        "processed_comments": 0,
                        "location_mentions": [],
                        "popular_locations": [],
                        "sentiment_distribution": {
                            "positive": 0,
                            "negative": 0,
                            "neutral": 0,
                        },
                        "travel_keywords": [],
                        "top_comments": [],
                        "extraction_stats": {},
                    }
                )

            # 2. 過濾評論（按讚數）
            filtered_comments = [c for c in comments if c.likes >= min_likes]

            # 3. 分析評論
            location_mentions = []
            comment_analyses = []
            all_travel_keywords = []
            sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}

            for comment in filtered_comments[:limit]:  # 確保不超過限制
                try:
                    # 提取地點
                    locations_in_comment = self._extract_locations_from_comment(
                        comment.text
                    )

                    # 分析情感
                    sentiment_score, sentiment_label = self._analyze_comment_sentiment(
                        comment.text
                    )
                    sentiment_counts[sentiment_label] += 1

                    # 提取旅遊關鍵詞
                    travel_keywords = self._extract_travel_keywords(comment.text)
                    all_travel_keywords.extend(travel_keywords)

                    # 判斷是否旅遊相關
                    is_travel_related = self._is_travel_related(
                        comment.text, travel_keywords
                    )

                    # 為每個地點創建 LocationMention
                    extracted_locations = []
                    for location_name, context, confidence in locations_in_comment:
                        location_mention = LocationMention(
                            location_name=location_name,
                            mention_context=context,
                            confidence=confidence,
                            comment_id=comment.comment_id,
                            sentiment=sentiment_label,
                            comment_likes=comment.likes,
                        )
                        location_mentions.append(location_mention)
                        extracted_locations.append(location_name)

                    # 創建評論分析
                    comment_analysis = CommentAnalysis(
                        comment_id=comment.comment_id,
                        locations_mentioned=extracted_locations,
                        sentiment_score=sentiment_score,
                        sentiment_label=sentiment_label,
                        keywords=travel_keywords,
                        is_travel_related=is_travel_related,
                        confidence=0.8 if is_travel_related else 0.5,
                    )
                    comment_analyses.append(comment_analysis)

                except Exception as e:
                    logger.debug(f"Error analyzing comment {comment.comment_id}: {e}")
                    continue

            # 4. 重新計算地點信心分數
            for mention in location_mentions:
                mention.confidence = self._calculate_location_confidence(
                    mention, location_mentions
                )

            # 5. 統計熱門地點
            location_counter = Counter(
                [mention.location_name for mention in location_mentions]
            )
            popular_locations = location_counter.most_common(10)

            # 6. 統計旅遊關鍵詞
            keyword_counter = Counter(all_travel_keywords)
            travel_keywords_ranked = keyword_counter.most_common(15)

            # 7. 選取熱門評論（高按讚數且包含地點資訊）
            top_comments = sorted(
                [ca for ca in comment_analyses if ca.locations_mentioned],
                key=lambda x: len(x.locations_mentioned) * 10
                + (1 if x.is_travel_related else 0),
                reverse=True,
            )[:10]

            # 8. 組裝結果
            result = CommentMiningResult(
                video_id=video_id,
                total_comments=len(comments),
                processed_comments=len(filtered_comments),
                location_mentions=location_mentions,
                popular_locations=popular_locations,
                sentiment_distribution=sentiment_counts,
                travel_keywords=travel_keywords_ranked,
                top_comments=top_comments,
                extraction_stats={
                    "total_location_mentions": len(location_mentions),
                    "unique_locations": len(location_counter),
                    "travel_related_comments": sum(
                        1 for ca in comment_analyses if ca.is_travel_related
                    ),
                    "average_sentiment": (
                        sum(ca.sentiment_score for ca in comment_analyses)
                        / len(comment_analyses)
                        if comment_analyses
                        else 0
                    ),
                },
            )

            # 轉換為 JSON
            result_dict = asdict(result)

            logger.info(
                f"Comment mining completed: {len(location_mentions)} location mentions, {len(popular_locations)} unique locations"
            )

            return json.dumps(result_dict, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Comment mining failed: {e}")
            return json.dumps(
                {
                    "error": f"Comment mining failed: {str(e)}",
                    "video_id": video_id,
                    "total_comments": 0,
                    "processed_comments": 0,
                    "location_mentions": [],
                    "popular_locations": [],
                    "sentiment_distribution": {
                        "positive": 0,
                        "negative": 0,
                        "neutral": 0,
                    },
                    "travel_keywords": [],
                    "top_comments": [],
                    "extraction_stats": {},
                }
            )
