import pytest
from trailtag.tools.youtube_metadata_tool import YoutubeSubtitleTool


@pytest.mark.parametrize(
    "video_id",
    [
        "SlRSbihlytQ",  # Rick Astley - Never Gonna Give You Up（有英文字幕）
        # 可再加入其他已知有字幕的 video_id
    ],
)
def test_youtube_subtitle_tool_returns_subtitles(video_id):
    tool = YoutubeSubtitleTool()
    result = tool._run(video_id)
    print(f"Subtitle for video {video_id}: {str(result)}")
    assert isinstance(result, object)
    assert len(result) > 0


def test_youtube_subtitle_tool_no_subtitles():
    video_id = (
        "ObNdveOYlWM"  # Daft Punk - Get Lucky（假設沒有字幕，可替換為實際無字幕影片）
    )
    tool = YoutubeSubtitleTool()
    result = tool._run(video_id)
    print(f"Subtitle for video {video_id}: {result}")
    assert result == "找不到此影片的字幕" or result == "此影片字幕功能已關閉"


def test_youtube_subtitle_tool_video_unavailable():
    video_id = "xxxxxxxxxxx"  # 不存在的 video_id
    tool = YoutubeSubtitleTool()
    result = tool._run(video_id)
    print(f"Subtitle for video {video_id}: {result}")
    assert result == "影片不存在或無法存取"
