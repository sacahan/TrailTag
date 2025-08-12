"""Subtitle Compression Tool

以長字幕為輸入，當長度可能超出 LLM token 上限時，進行分塊壓縮與關鍵地點片段保留，
降低後續主題/地點摘要任務的 token 消耗，同時最大化地點與時間語境的留存。

設計目標 (Simplified version of earlier proposal):
1. 粗估 token (字元/4) 過長才啟用壓縮。
2. 分塊 (chunk) 切割：控制每塊近似 token 大小，避免單塊過大。
3. 地點候選偵測：簡單規則 + 關鍵字；含地點的塊保留更多原文行。
4. 其餘行進行摘要：若可使用 LLM 則用，否則以啟發式 (取前幾行 + 句子截斷)。
5. 產出最終壓縮字幕字串，提供給上層 Agent 使用。

與先前建議差異：為避免在無 API Key/離線測試時失敗，加入 fallback heuristic。

後續可擴充：
- tiktoken 精準 token 估算
- JSON 結構化中繼摘要
- Embedding 過濾無關主題句段
- 地點與原文行對齊 timecode 保留 (現假設原行可能已包含時間資訊)
"""

from __future__ import annotations

import re
import hashlib
import logging
from typing import List, Dict, Optional, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from crewai import LLM

logger = logging.getLogger(__name__)

# -------------------- 參數可調 --------------------
MAX_FINAL_TOKENS = 9000  # 低於此估計 token 直接返回原字幕
CHUNK_TARGET_TOKENS = 800  # 單 chunk 目標 token (估算值)
HIGH_IMPORTANCE_KEEP_RATIO = 0.85  # 含地點 chunk 原文保留比例
NORMAL_KEEP_RATIO = 0.35  # 一般 chunk 原文保留比例
MIN_LOCATION_RECALL = 3  # 若地點過少可考慮後續擴充重跑 (目前僅紀錄)

LOCATION_KEYWORDS = [
    # English common location types
    "road",
    "rd",
    "st",
    "street",
    "ave",
    "avenue",
    "blvd",
    "boulevard",
    "ln",
    "lane",
    "dr",
    "drive",
    "ct",
    "court",
    "pl",
    "place",
    "sq",
    "square",
    "circle",
    "crescent",
    "way",
    "terrace",
    "highway",
    "hwy",
    "expressway",
    "freeway",
    "route",
    "alley",
    "walk",
    "parkway",
    "junction",
    "crossroad",
    "intersection",
    "park",
    "mount",
    "mountain",
    "hill",
    "peak",
    "summit",
    "ridge",
    "valley",
    "canyon",
    "gorge",
    "cliff",
    "lake",
    "pond",
    "reservoir",
    "river",
    "creek",
    "stream",
    "brook",
    "bay",
    "harbor",
    "port",
    "beach",
    "coast",
    "shore",
    "island",
    "peninsula",
    "cape",
    "delta",
    "wetland",
    "marsh",
    "swamp",
    "forest",
    "woods",
    "grove",
    "meadow",
    "field",
    "plain",
    "desert",
    "oasis",
    "plaza",
    "square",
    "market",
    "night market",
    "old street",
    "station",
    "bus station",
    "train station",
    "metro",
    "subway",
    "airport",
    "terminal",
    "pier",
    "dock",
    "wharf",
    "museum",
    "gallery",
    "library",
    "theater",
    "stadium",
    "arena",
    "gym",
    "court",
    "school",
    "university",
    "college",
    "campus",
    "hospital",
    "clinic",
    "temple",
    "church",
    "mosque",
    "cathedral",
    "shrine",
    "monastery",
    "palace",
    "castle",
    "fort",
    "tower",
    "monument",
    "memorial",
    "bridge",
    "tunnel",
    "dam",
    "zoo",
    "aquarium",
    "amusement park",
    "theme park",
    "botanical garden",
    "conservatory",
    "national park",
    "scenic area",
    "viewpoint",
    "lookout",
    "observation deck",
    "visitor center",
    "heritage site",
    "historic site",
    "archaeological site",
    # Chinese common location types
    "國家公園",
    "國家風景區",
    "風景區",
    "山",
    "山脈",
    "峰",
    "嶺",
    "丘",
    "湖",
    "池",
    "潭",
    "水庫",
    "河",
    "溪",
    "谷",
    "峽谷",
    "瀑布",
    "公園",
    "步道",
    "古道",
    "綠道",
    "自行車道",
    "橋",
    "吊橋",
    "車站",
    "火車站",
    "捷運站",
    "地鐵站",
    "機場",
    "碼頭",
    "港口",
    "老街",
    "夜市",
    "廣場",
    "市場",
    "博物館",
    "美術館",
    "圖書館",
    "劇院",
    "體育館",
    "球場",
    "學校",
    "大學",
    "醫院",
    "診所",
    "寺廟",
    "廟",
    "教堂",
    "清真寺",
    "宮",
    "城堡",
    "塔",
    "紀念碑",
    "紀念館",
    "動物園",
    "水族館",
    "遊樂園",
    "主題樂園",
    "植物園",
    "溫室",
    "觀景台",
    "遊客中心",
    "文化遺產",
    "古蹟",
    "遺址",
    "景點",
    "景區",
    "景觀區",
    "觀光區",
    "登山口",
    "登山步道",
    "森林",
    "林場",
    "草原",
    "平原",
    "沙漠",
    "綠地",
    "濕地",
    "沼澤",
    "海灘",
    "海岸",
    "島",
    "半島",
    "岬",
    "三角洲",
    "村",
    "鎮",
    "市",
    "區",
    "里",
]
LOCATION_REGEX = re.compile(r"\b([A-Z][a-zA-Z]{2,}(?:\s+[A-Z][a-zA-Z]{2,})*)\b")


class SubtitleCompressionInput(BaseModel):
    """字幕壓縮工具輸入資料模型

    subtitle_text: 完整字幕文字
    search_subject: 主題焦點 (可選)
    """

    subtitle_text: str = Field(..., description="完整字幕文字。")
    search_subject: Optional[str] = Field(None, description="主題焦點 (可選)。")


class ChunkSummary(BaseModel):
    """單一分塊摘要資訊

    chunk_index: 分塊索引
    detected_locations: 偵測到的地點關鍵字
    kept_lines: 保留的原文行
    summarized_points: 摘要重點句
    """

    chunk_index: int
    detected_locations: List[str]
    kept_lines: List[str]
    summarized_points: List[str]


class SubtitleCompressionTool(BaseTool):
    """當字幕過長時執行壓縮，否則回傳原字幕。

    主要功能：
    - 根據 token 長度判斷是否需要壓縮
    - 分塊切割字幕
    - 地點偵測與保留
    - 其餘行摘要（優先 LLM，失敗則啟發式）
    - 組合壓縮後字幕
    """

    name: str = "SubtitleCompressionTool"
    description: str = "當字幕估計 token 過長時，自動進行分塊壓縮並保留地點相關行，輸出壓縮後字幕文字。"
    args_schema: Type[BaseModel] = SubtitleCompressionInput
    llm: Optional[LLM] = None  # LLM 實例，若無則使用啟發式摘要

    def __init__(self, model_name: str = "openai/gpt-4o-mini"):
        """
        初始化字幕壓縮工具，嘗試建立 LLM 實例，失敗則 fallback 為啟發式摘要。
        """
        super().__init__()
        # 透過 crewai.LLM 以便與現有架構一致；失敗則 None -> 走 heuristic
        try:
            self.llm = LLM(model=model_name, temperature=0, max_tokens=1200)
        except Exception as e:  # pragma: no cover - 初始化失敗 fallback
            logger.warning(f"LLM 初始化失敗, 將使用啟發式摘要: {e}")
            self.llm = None
        self._cache: Dict[str, ChunkSummary] = {}

    # --------------- 主流程 ---------------
    def _run(self, subtitle_text: str, search_subject: Optional[str] = None) -> str:
        """
        主執行流程：
        1. 若字幕長度未超過 token 閾值，直接回傳原字幕。
        2. 否則進行分塊、地點偵測、摘要與組合。
        """
        if not subtitle_text:
            return ""
        est_tokens = self._estimate_tokens(subtitle_text)
        if est_tokens <= MAX_FINAL_TOKENS:
            return subtitle_text  # 不壓縮

        lines = self._split_lines(subtitle_text)
        chunks = self._group_into_chunks(lines)
        summaries: List[ChunkSummary] = []
        for idx, chunk_lines in enumerate(chunks):
            chunk_text = "\n".join(chunk_lines)
            detected = self._detect_locations(chunk_text)
            importance_ratio = (
                HIGH_IMPORTANCE_KEEP_RATIO if detected else NORMAL_KEEP_RATIO
            )
            summaries.append(
                self._summarize_chunk(
                    idx=idx,
                    lines=chunk_lines,
                    detected_locations=detected,
                    keep_ratio=importance_ratio,
                    search_subject=search_subject or "",
                )
            )

        # 地點召回資訊 (暫記錄日志, 後續可擴充第二輪)
        all_locations = {l for s in summaries for l in s.detected_locations}  # noqa: E741
        if len(all_locations) < MIN_LOCATION_RECALL:
            logger.info(
                "地點數量低於閾值，可考慮後續加入再處理/降低壓縮 (目前僅提示, 不重跑)"
            )

        return self._compose_final_text(summaries)

    # --------------- 工具函式 ---------------
    def _estimate_tokens(self, text: str) -> int:
        """
        粗略估算 token 數量（1 token ≈ 4 字元，適用於中英文混合）
        """
        return max(1, len(text) // 4)

    def _split_lines(self, text: str) -> List[str]:
        """
        將字幕文字依行切割並去除空白行
        """
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _group_into_chunks(self, lines: List[str]) -> List[List[str]]:
        """
        將字幕行依據目標 token 數分組，避免單一分塊過大
        """
        chunks: List[List[str]] = []
        current: List[str] = []
        token_sum = 0
        for line in lines:
            t = self._estimate_tokens(line)
            if token_sum + t > CHUNK_TARGET_TOKENS and current:
                chunks.append(current)
                current = [line]
                token_sum = t
            else:
                current.append(line)
                token_sum += t
        if current:
            chunks.append(current)
        return chunks

    def _detect_locations(self, text: str) -> List[str]:
        """
        偵測字幕片段中出現的地點關鍵字或專有名詞
        """
        found = set()
        lower = text.lower()
        for kw in LOCATION_KEYWORDS:
            if kw.lower() in lower:
                found.add(kw)
        for m in LOCATION_REGEX.findall(text):
            if len(m) >= 3:
                found.add(m.strip())
        return list(found)

    def _summarize_chunk(
        self,
        idx: int,
        lines: List[str],
        detected_locations: List[str],
        keep_ratio: float,
        search_subject: str,
    ) -> ChunkSummary:
        """
        對單一分塊進行摘要：
        - 優先保留含地點的原文行
        - 其餘行摘要（優先 LLM，失敗則啟發式）
        - 結果快取避免重複運算
        """
        # cache key
        raw_text = "\n".join(lines)
        h = hashlib.sha256(
            (
                raw_text
                + "|"
                + ",".join(sorted(detected_locations))
                + f"|{keep_ratio}|{search_subject}"
            ).encode("utf-8")
        ).hexdigest()
        if h in self._cache:
            return self._cache[h]

        # 計算要保留的原文行數
        keep_count = max(1, int(len(lines) * keep_ratio))
        kept: List[str] = []
        if detected_locations:
            # 先收集含地點的行
            for line in lines:
                if any(loc in line for loc in detected_locations):
                    kept.append(line)
            # 若仍不足 keep_count，補前幾行
        if len(kept) < keep_count:
            for line in lines:
                if line not in kept:
                    kept.append(line)
                if len(kept) >= keep_count:
                    break

        # 其餘摘要：
        summarized_points: List[str] = []
        remaining_text = "\n".join([line for line in lines if line not in kept])
        if remaining_text and self.llm is not None:
            prompt = (
                "你是字幕壓縮助手，僅用原文重述重點，不新增不存在資訊。\n"
                f"主題焦點: {search_subject or 'N/A'}\n"
                "以下是需濃縮的字幕片段:\n" + remaining_text + "\n"
                "請輸出 3~6 條精簡要點 (不帶編號，只是一行一點)。"
            )
            try:
                resp = self.llm.invoke(prompt=prompt)
                raw = (
                    getattr(resp, "raw", None)
                    or getattr(resp, "output", None)
                    or str(resp)
                )
                # 切行過濾空白
                summarized_points = [
                    r.strip("- ") for r in raw.splitlines() if r.strip()
                ][:6]
            except Exception as e:  # pragma: no cover - LLM 失敗 fallback
                logger.warning(f"LLM 摘要失敗, 使用啟發式: {e}")
                summarized_points = self._heuristic_points(remaining_text)
        else:
            summarized_points = self._heuristic_points(remaining_text)

        cs = ChunkSummary(
            chunk_index=idx,
            detected_locations=detected_locations,
            kept_lines=kept,
            summarized_points=summarized_points,
        )
        self._cache[h] = cs
        return cs

    def _heuristic_points(self, text: str) -> List[str]:
        """
        啟發式摘要：將剩餘文字依句號等標點切割，取前幾句作為重點
        """
        if not text:
            return []
        sentences = re.split(r"[。.!?！？]", text)
        pts = [s.strip() for s in sentences if s.strip()]
        return pts[:5]

    def _compose_final_text(self, summaries: List[ChunkSummary]) -> str:
        """
        將所有分塊摘要組合為最終壓縮字幕字串
        """
        out_lines: List[str] = []
        for s in summaries:
            if s.detected_locations:
                out_lines.append(
                    f"[Chunk {s.chunk_index} 地點]: {', '.join(s.detected_locations)}"
                )
            for line in s.kept_lines:
                out_lines.append(f"*原文* {line}")
            for p in s.summarized_points:
                out_lines.append(f"- {p}")
        return "\n".join(out_lines)


if __name__ == "__main__":  # 簡易手動測試
    # 建立工具實例，產生大量測試字幕並執行壓縮，僅顯示部分結果
    tool = SubtitleCompressionTool()
    demo = "\n".join([f"00:00:{i:02d} Taipei 101 is amazing view" for i in range(1200)])
    compressed = tool._run(demo, search_subject="景點")
    print(compressed[:800], "...\n--- length:", len(compressed))
