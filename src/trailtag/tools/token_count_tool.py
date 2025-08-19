"""
token_count_tool.py

此工具用於計算輸入字串經 LLM tokenizer 處理後的 token 數量。
預設使用 OpenAI 的 tiktoken，支援多種模型。
"""

import tiktoken


def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """
    計算輸入字串經指定 LLM 模型 tokenizer 處理後的 token 數量。
    :param text: 輸入字串
    :param model: LLM 模型名稱，預設為 gpt-4o-mini
    :return: token 數量
    """
    encoding = tiktoken.encoding_for_model(model)
    tokens = encoding.encode(text)
    return len(tokens)


if __name__ == "__main__":
    sample = "你好，這是一個測試訊息。"
    print(f"Token 數量: {count_tokens(sample)}")
