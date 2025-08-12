from trailtag.tools.subtitle_compression_tool import (
    SubtitleCompressionTool,
    ChunkSummary,
)


def test_subtitle_compression_short_pass_through():
    tool = SubtitleCompressionTool()
    short = "這是一個很短的字幕。\n只包含兩行。"
    out = tool._run(short)
    assert out == short


def test_subtitle_compression_long_monkeypatch():
    tool = SubtitleCompressionTool()
    long_lines = [f"00:00:{i:02d} Taipei 101 nice view" for i in range(0, 600)]
    long_text = "\n".join(long_lines)

    def fake_sum(idx, lines, detected_locations, keep_ratio, search_subject):  # type: ignore
        return ChunkSummary(
            chunk_index=idx,
            detected_locations=detected_locations
            or (["Taipei 101"] if idx == 0 else []),
            kept_lines=lines[:2],
            summarized_points=["示例要點1", "示例要點2"],
        )

    tool._summarize_chunk = fake_sum  # type: ignore
    output = tool._run(long_text, search_subject="景點")
    assert "示例要點1" in output
    assert "Taipei 101" in output
    assert output.count("\n") < 200
