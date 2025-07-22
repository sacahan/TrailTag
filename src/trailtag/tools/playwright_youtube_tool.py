# Playwright Web Site Tool
# 設計一個 Playwright 工具，用於互動操作Youtube網站，擷取資料．
# Params: `keyword`，用於結合搜尋字串：`https://www.youtube.com/results?search_query={keyword}`
# 將搜尋結果中的頻道名稱（使用 `@` 開頭）擷取出來並輸出

from crewai.tools import tool
from playwright.sync_api import sync_playwright


@tool("search_youtuber_async")
async def search_youtuber(keyword: str) -> str:
    """
    使用 Playwright 瀏覽 YouTube，搜尋關鍵字並擷取頻道名稱。
    """
    with sync_playwright() as p:  # 啟動 Playwright 同步模式
        browser = p.chromium.launch(
            headless=True
        )  # 啟動 Chromium 瀏覽器，並設定為無頭模式
        context = browser.new_context()  # 建立新的瀏覽器上下文
        page = context.new_page()  # 開啟新的分頁

        try:
            # 建立搜尋 URL，將關鍵字嵌入到 YouTube 搜尋網址中
            search_url = f"https://www.youtube.com/results?search_query={keyword}"
            page.goto(search_url)  # 導航到搜尋頁面

            # 等待頁面載入完成，確保搜尋結果已顯示
            page.wait_for_selector("#channel-thumbnail")

            # 擷取頻道名稱，選取所有頻道連結元素
            channels = page.query_selector_all("#channel-thumbnail")

            for channel in channels:
                href = channel.get_attribute("href")
                if href:
                    return href.replace("/@", "")  # 去除 @ 符號
        finally:
            # 關閉瀏覽器，釋放資源
            browser.close()


# 測試範例
if __name__ == "__main__":
    results = search_youtuber("阿滴")  # 執行搜尋並擷取結果
    print(results)  # 輸出結果到終端
