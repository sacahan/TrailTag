from src.trailtag.tools.token_count_tool import count_tokens


def test_count_tokens_basic():
    text = "Hello, world!"
    assert count_tokens(text) > 0


def test_count_tokens_chinese():
    text = "你好，世界！"
    assert count_tokens(text) > 0


def test_count_tokens_empty():
    text = ""
    assert count_tokens(text) == 0


def test_count_tokens_model_change():
    text = "This is a test."
    count1 = count_tokens(text, model="gpt-3.5-turbo")
    count2 = count_tokens(text, model="gpt-4")
    assert count1 > 0 and count2 > 0
    assert abs(count1 - count2) <= 2  # 不同模型可能略有差異
