"""
字幕分割工具

此工具負責將長字幕內容分割成適當大小的段落，避免 Token 限制問題。
使用智能分段策略，保持內容語意完整性。

主要功能：
- Token 計算與限制檢查
- 語意感知的分段策略
- 時間軸保留與重建
- 內容上下文保持
"""

import re
from typing import List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import tiktoken
from src.api.logger_config import get_logger

logger = get_logger(__name__)


class ChunkStrategy(str, Enum):
    """分段策略枚舉"""

    TIME_BASED = "time_based"  # 基於時間軸分段
    SEMANTIC = "semantic"  # 語意感知分段
    HYBRID = "hybrid"  # 混合策略（推薦）
    SIMPLE = "simple"  # 簡單字數分段


@dataclass
class SubtitleChunk:
    """字幕分段資料結構"""

    id: str
    content: str
    start_time: float
    end_time: float
    token_count: int
    word_count: int
    sentence_count: int
    original_indices: List[int]  # 原始字幕條目索引
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SubtitleEntry:
    """單一字幕條目"""

    index: int
    start_time: float
    end_time: float
    text: str
    duration: float = None

    def __post_init__(self):
        if self.duration is None:
            self.duration = self.end_time - self.start_time


class SubtitleChunker:
    """
    字幕分割器

    負責將長字幕內容智能分割成適當大小的段落，
    避免超過模型的 Token 限制，同時保持內容完整性。
    """

    def __init__(
        self,
        max_tokens: int = 3000,
        min_tokens: int = 500,
        model: str = "gpt-4o-mini",
        overlap_ratio: float = 0.1,
    ):
        """
        初始化字幕分割器

        Args:
            max_tokens: 每個分段的最大 Token 數
            min_tokens: 每個分段的最小 Token 數
            model: 用於 Token 計算的模型名稱
            overlap_ratio: 分段重疊比例 (0.0-0.3)
        """
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens
        self.overlap_ratio = max(0.0, min(0.3, overlap_ratio))

        # 初始化 tiktoken 編碼器
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            logger.warning(f"模型 {model} 不支援，使用 cl100k_base 編碼")
            self.encoding = tiktoken.get_encoding("cl100k_base")

        # 語句分隔符號和標點符號
        self.sentence_endings = r"[.!?。！？]\s*"
        self.strong_breaks = r"[.!?。！？]\s*(?=[A-Z\u4e00-\u9fff])"
        self.weak_breaks = r"[,;，；]\s*"

        logger.info(
            f"SubtitleChunker 初始化完成: max_tokens={max_tokens}, model={model}"
        )

    def count_tokens(self, text: str) -> int:
        """計算文字的 Token 數量"""
        try:
            return len(self.encoding.encode(text))
        except Exception as e:
            logger.error(f"Token 計算失敗: {e}")
            # 備用估算：平均每個字母約 0.25 tokens
            return int(len(text) * 0.25)

    def parse_subtitles(self, subtitle_text: str) -> List[SubtitleEntry]:
        """
        解析字幕文字為結構化格式
        支援 SRT, VTT 等常見格式

        Args:
            subtitle_text: 原始字幕文字

        Returns:
            解析後的字幕條目列表
        """
        entries = []

        try:
            # 預處理：移除多餘的空白行
            lines = [line.strip() for line in subtitle_text.split("\n") if line.strip()]

            i = 0
            index = 0

            while i < len(lines):
                # 跳過序號行（純數字）
                if lines[i].isdigit():
                    i += 1
                    if i >= len(lines):
                        break

                # 解析時間戳
                time_line = lines[i]
                time_match = re.search(
                    r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[.,](\d{3})",
                    time_line,
                )

                if time_match:
                    # 計算開始和結束時間（秒）
                    start_h, start_m, start_s, start_ms = map(
                        int, time_match.groups()[:4]
                    )
                    end_h, end_m, end_s, end_ms = map(int, time_match.groups()[4:])

                    start_time = (
                        start_h * 3600 + start_m * 60 + start_s + start_ms / 1000
                    )
                    end_time = end_h * 3600 + end_m * 60 + end_s + end_ms / 1000

                    i += 1

                    # 收集文字內容
                    text_lines = []
                    while (
                        i < len(lines)
                        and not lines[i].isdigit()
                        and "-->" not in lines[i]
                    ):
                        # 清理 HTML 標籤和格式
                        clean_text = re.sub(r"<[^>]+>", "", lines[i])
                        clean_text = re.sub(
                            r"\{[^}]+\}", "", clean_text
                        )  # 移除樣式標籤
                        if clean_text:
                            text_lines.append(clean_text)
                        i += 1

                    if text_lines:
                        text_content = " ".join(text_lines).strip()
                        if text_content:
                            entries.append(
                                SubtitleEntry(
                                    index=index,
                                    start_time=start_time,
                                    end_time=end_time,
                                    text=text_content,
                                )
                            )
                            index += 1
                else:
                    i += 1

            logger.info(f"解析字幕完成: {len(entries)} 個條目")
            return entries

        except Exception as e:
            logger.error(f"字幕解析失敗: {e}")
            return []

    def chunk_by_time(
        self, entries: List[SubtitleEntry], target_duration: float = 300.0
    ) -> List[List[SubtitleEntry]]:
        """
        基於時間的分段策略

        Args:
            entries: 字幕條目列表
            target_duration: 目標分段時長（秒）

        Returns:
            時間分段列表
        """
        if not entries:
            return []

        chunks = []
        current_chunk = []
        chunk_start_time = entries[0].start_time

        for entry in entries:
            # 檢查是否需要開始新分段
            chunk_duration = entry.end_time - chunk_start_time

            if (chunk_duration > target_duration and current_chunk) or (
                current_chunk
                and self._get_chunk_tokens(current_chunk) > self.max_tokens
            ):
                chunks.append(current_chunk)
                current_chunk = [entry]
                chunk_start_time = entry.start_time
            else:
                current_chunk.append(entry)

        # 添加最後一個分段
        if current_chunk:
            chunks.append(current_chunk)

        logger.debug(f"時間分段完成: {len(chunks)} 個分段")
        return chunks

    def chunk_by_semantic(
        self, entries: List[SubtitleEntry]
    ) -> List[List[SubtitleEntry]]:
        """
        語意感知分段策略

        基於句子完整性和語意邊界進行分段
        """
        if not entries:
            return []

        chunks = []
        current_chunk = []
        current_tokens = 0

        for i, entry in enumerate(entries):
            entry_tokens = self.count_tokens(entry.text)

            # 檢查是否需要開始新分段
            if current_tokens + entry_tokens > self.max_tokens and current_chunk:
                # 尋找最佳分割點
                split_point = self._find_semantic_split_point(current_chunk)

                if split_point > 0:
                    # 在語意邊界分割
                    chunks.append(current_chunk[:split_point])
                    current_chunk = current_chunk[split_point:] + [entry]
                    current_tokens = self._get_chunk_tokens(current_chunk)
                else:
                    # 無法找到語意邊界，強制分割
                    chunks.append(current_chunk)
                    current_chunk = [entry]
                    current_tokens = entry_tokens
            else:
                current_chunk.append(entry)
                current_tokens += entry_tokens

        # 添加最後一個分段
        if current_chunk:
            chunks.append(current_chunk)

        logger.debug(f"語意分段完成: {len(chunks)} 個分段")
        return chunks

    def chunk_by_hybrid(
        self, entries: List[SubtitleEntry]
    ) -> List[List[SubtitleEntry]]:
        """
        混合分段策略（推薦）

        結合時間和語意邊界的智能分段
        """
        if not entries:
            return []

        # 第一步：基於時間的粗分段
        time_chunks = self.chunk_by_time(entries, target_duration=600.0)  # 10分鐘

        # 第二步：對每個時間分段進行語意細分
        final_chunks = []
        for time_chunk in time_chunks:
            semantic_chunks = self.chunk_by_semantic(time_chunk)
            final_chunks.extend(semantic_chunks)

        logger.debug(f"混合分段完成: {len(final_chunks)} 個分段")
        return final_chunks

    def _find_semantic_split_point(self, entries: List[SubtitleEntry]) -> int:
        """
        尋找語意分割點

        Returns:
            分割點索引，0 表示無法分割
        """
        if len(entries) <= 1:
            return 0

        # 計算每個位置的分割分數
        scores = []
        for i in range(1, len(entries)):
            score = self._calculate_split_score(entries, i)
            scores.append((score, i))

        # 選擇分數最高的分割點
        if scores:
            scores.sort(reverse=True)
            best_score, best_index = scores[0]

            # 確保分割後的兩部分都有最小 Token 數
            if (
                self._get_chunk_tokens(entries[:best_index]) >= self.min_tokens
                and self._get_chunk_tokens(entries[best_index:]) >= self.min_tokens
            ):
                return best_index

        return 0

    def _calculate_split_score(
        self, entries: List[SubtitleEntry], split_index: int
    ) -> float:
        """計算分割點的分數"""
        if split_index <= 0 or split_index >= len(entries):
            return 0.0

        score = 0.0
        prev_entry = entries[split_index - 1]
        curr_entry = entries[split_index]

        # 時間間隔分數：較長的間隔得分更高
        time_gap = curr_entry.start_time - prev_entry.end_time
        if time_gap > 2.0:  # 大於2秒
            score += 30.0
        elif time_gap > 1.0:  # 大於1秒
            score += 20.0
        elif time_gap > 0.5:  # 大於0.5秒
            score += 10.0

        # 句子結尾分數
        if re.search(self.strong_breaks, prev_entry.text):
            score += 25.0
        elif re.search(self.sentence_endings, prev_entry.text):
            score += 15.0

        # Token 平衡分數
        left_tokens = self._get_chunk_tokens(entries[:split_index])
        right_tokens = self._get_chunk_tokens(entries[split_index:])
        total_tokens = left_tokens + right_tokens

        if total_tokens > 0:
            balance = 1.0 - abs(left_tokens - right_tokens) / total_tokens
            score += balance * 20.0

        return score

    def _get_chunk_tokens(self, entries: List[SubtitleEntry]) -> int:
        """計算分段的總 Token 數"""
        return sum(self.count_tokens(entry.text) for entry in entries)

    def create_chunk_object(
        self, chunk_id: str, entries: List[SubtitleEntry], chunk_index: int
    ) -> SubtitleChunk:
        """創建字幕分段物件"""
        if not entries:
            raise ValueError("空的字幕條目列表")

        # 合併文字內容
        content_parts = []
        for entry in entries:
            timestamp = f"[{self._format_time(entry.start_time)} --> {self._format_time(entry.end_time)}]"
            content_parts.append(f"{timestamp} {entry.text}")

        content = "\n".join(content_parts)

        # 計算統計資訊
        token_count = self.count_tokens(content)
        word_count = len(re.findall(r"\b\w+\b", content))
        sentence_count = len(re.findall(self.sentence_endings, content))

        return SubtitleChunk(
            id=f"{chunk_id}_{chunk_index:03d}",
            content=content,
            start_time=entries[0].start_time,
            end_time=entries[-1].end_time,
            token_count=token_count,
            word_count=word_count,
            sentence_count=sentence_count,
            original_indices=[entry.index for entry in entries],
            metadata={
                "chunk_index": chunk_index,
                "entry_count": len(entries),
                "duration": entries[-1].end_time - entries[0].start_time,
                "avg_tokens_per_entry": token_count / len(entries) if entries else 0,
            },
        )

    def _format_time(self, seconds: float) -> str:
        """格式化時間為 HH:MM:SS.mmm"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

    def chunk_subtitles(
        self,
        subtitle_text: str,
        video_id: str = "unknown",
        strategy: ChunkStrategy = ChunkStrategy.HYBRID,
    ) -> List[SubtitleChunk]:
        """
        主要分割方法

        Args:
            subtitle_text: 原始字幕文字
            video_id: 影片 ID（用於生成分段 ID）
            strategy: 分割策略

        Returns:
            字幕分段列表
        """
        try:
            logger.info(f"開始分割字幕: video_id={video_id}, strategy={strategy.value}")

            # 檢查輸入
            if not subtitle_text or not subtitle_text.strip():
                logger.warning("空的字幕內容")
                return []

            # 解析字幕
            entries = self.parse_subtitles(subtitle_text)
            if not entries:
                logger.warning("無法解析字幕內容")
                return []

            # 檢查是否需要分割
            total_tokens = self._get_chunk_tokens(entries)
            if total_tokens <= self.max_tokens:
                logger.info(f"字幕內容較短 ({total_tokens} tokens)，不需要分割")
                chunk = self.create_chunk_object(video_id, entries, 0)
                return [chunk]

            # 執行分割策略
            if strategy == ChunkStrategy.TIME_BASED:
                entry_chunks = self.chunk_by_time(entries)
            elif strategy == ChunkStrategy.SEMANTIC:
                entry_chunks = self.chunk_by_semantic(entries)
            elif strategy == ChunkStrategy.HYBRID:
                entry_chunks = self.chunk_by_hybrid(entries)
            else:  # SIMPLE
                entry_chunks = self._chunk_simple(entries)

            # 創建分段物件
            chunks = []
            for i, entry_chunk in enumerate(entry_chunks):
                if entry_chunk:  # 確保分段不為空
                    chunk = self.create_chunk_object(video_id, entry_chunk, i)
                    chunks.append(chunk)

            # 添加重疊內容（如果啟用）
            if self.overlap_ratio > 0:
                chunks = self._add_overlap(chunks, entry_chunks)

            logger.info(
                f"字幕分割完成: {len(chunks)} 個分段, 總計 {total_tokens} tokens"
            )

            # 打印分割統計
            self._log_chunk_statistics(chunks)

            return chunks

        except Exception as e:
            logger.error(f"字幕分割失敗: {e}")
            return []

    def _chunk_simple(self, entries: List[SubtitleEntry]) -> List[List[SubtitleEntry]]:
        """簡單分段策略：基於 Token 數量"""
        chunks = []
        current_chunk = []
        current_tokens = 0

        for entry in entries:
            entry_tokens = self.count_tokens(entry.text)

            if current_tokens + entry_tokens > self.max_tokens and current_chunk:
                chunks.append(current_chunk)
                current_chunk = [entry]
                current_tokens = entry_tokens
            else:
                current_chunk.append(entry)
                current_tokens += entry_tokens

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _add_overlap(
        self, chunks: List[SubtitleChunk], entry_chunks: List[List[SubtitleEntry]]
    ) -> List[SubtitleChunk]:
        """為分段添加重疊內容以保持上下文"""
        if len(chunks) <= 1:
            return chunks

        overlapped_chunks = [chunks[0]]  # 第一個分段保持不變

        for i in range(1, len(chunks)):
            prev_chunk = entry_chunks[i - 1]
            curr_chunk = entry_chunks[i]

            # 計算重疊大小
            overlap_size = max(1, int(len(prev_chunk) * self.overlap_ratio))
            overlap_entries = prev_chunk[-overlap_size:]

            # 創建包含重疊的新分段
            combined_entries = overlap_entries + curr_chunk

            # 確保不超過 Token 限制
            if self._get_chunk_tokens(combined_entries) <= self.max_tokens:
                overlapped_chunk = self.create_chunk_object(
                    chunks[i].id.rsplit("_", 1)[0], combined_entries, i
                )
                overlapped_chunk.metadata["has_overlap"] = True
                overlapped_chunk.metadata["overlap_entries"] = len(overlap_entries)
                overlapped_chunks.append(overlapped_chunk)
            else:
                overlapped_chunks.append(chunks[i])

        return overlapped_chunks

    def _log_chunk_statistics(self, chunks: List[SubtitleChunk]) -> None:
        """記錄分割統計資訊"""
        if not chunks:
            return

        total_tokens = sum(chunk.token_count for chunk in chunks)
        total_duration = sum(chunk.end_time - chunk.start_time for chunk in chunks)
        avg_tokens = total_tokens / len(chunks)

        logger.info("分割統計:")
        logger.info(f"  - 總分段數: {len(chunks)}")
        logger.info(f"  - 總 Tokens: {total_tokens}")
        logger.info(f"  - 平均 Tokens/分段: {avg_tokens:.1f}")
        logger.info(f"  - 總時長: {total_duration:.1f} 秒")
        logger.info(
            f"  - Token 範圍: {min(c.token_count for c in chunks)} - {max(c.token_count for c in chunks)}"
        )

    def merge_chunks(self, chunks: List[SubtitleChunk], results: List[str]) -> str:
        """
        合併處理後的分段結果

        Args:
            chunks: 原始分段列表
            results: 對應的處理結果列表

        Returns:
            合併後的完整結果
        """
        if len(chunks) != len(results):
            logger.error(f"分段數量不匹配: {len(chunks)} vs {len(results)}")
            return "\n".join(results)

        try:
            merged_parts = []

            for chunk, result in zip(chunks, results):
                # 添加時間戳資訊
                time_info = f"[時間: {self._format_time(chunk.start_time)} - {self._format_time(chunk.end_time)}]"
                merged_parts.append(f"{time_info}\n{result}")

            merged_result = "\n\n---\n\n".join(merged_parts)

            logger.info(f"分段結果合併完成: {len(chunks)} 個分段")
            return merged_result

        except Exception as e:
            logger.error(f"合併分段結果失敗: {e}")
            return "\n".join(results)


# 工廠函數
def create_subtitle_chunker(
    max_tokens: int = 3000, model: str = "gpt-4o-mini"
) -> SubtitleChunker:
    """創建字幕分割器實例"""
    return SubtitleChunker(max_tokens=max_tokens, model=model)


# 便捷函數
def chunk_subtitle_text(
    subtitle_text: str,
    max_tokens: int = 3000,
    strategy: ChunkStrategy = ChunkStrategy.HYBRID,
    video_id: str = "unknown",
) -> List[SubtitleChunk]:
    """
    快速分割字幕文字

    Args:
        subtitle_text: 原始字幕文字
        max_tokens: 最大 Token 數
        strategy: 分割策略
        video_id: 影片 ID

    Returns:
        字幕分段列表
    """
    chunker = create_subtitle_chunker(max_tokens=max_tokens)
    return chunker.chunk_subtitles(subtitle_text, video_id=video_id, strategy=strategy)
