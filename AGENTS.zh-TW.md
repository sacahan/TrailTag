# Repository Guidelines

## 專案結構與模組

- `src/api/` — FastAPI 後端（routes、services、middleware、monitoring、cache）。
- `src/trailtag/` — CrewAI 工作流程、記憶體系統、工具、CLI 入口（`main.py`）。
- `src/extension/` — Chrome 擴充功能（TS/JS、測試、建置設定、資產）。
- `tests/` — Python 測試（單元／整合、E2E 工具）。
- `scripts/` — 建置與部署工具（如 `build_backend.sh`、`build_frontend.sh`）。
- `outputs/`, `dist/` — 產出物；避免納入版控。

## 開發、建置與測試指令

- 啟動 API（dev）：`uvicorn src.api.main:app --host 0.0.0.0 --port 8010 --reload`。
- 執行 Crew CLI：`python -m src.trailtag.main YT_VIDEO_ID`。
- Python 測試：`pytest -q`（或 `uv run pytest -q`）。
- 擴充功能測試：`npm test --prefix src/extension`。
- 擴充功能打包：`npm run package --prefix src/extension`。
- 預提交檢查：`pre-commit run -a`。
- 容器（選用）：`docker-compose up --build`。

## 程式風格與命名

- 格式化：Python 以 Ruff formatter；JS/TS 以 Prettier（皆由 pre-commit 強制）。
- 縮排：2 空白（見 `.editorconfig`）。
- Python：函式／變數 snake_case；類別 PascalCase；模組小寫含底線。
- 型別：公開函式需型別註記；API I/O 優先使用 Pydantic model。
- Extension TS：檔名 kebab-case；匯出類別 PascalCase。

## 測試規範

- 框架：`pytest`、`pytest-asyncio`、`pytest-mock`；Extension 以 Jest。
- 位置：單元測試靠近模組；整合測試置於 `tests/integration/`。
- 命名：`test_*.py`、`*_test.py`；非同步以 `@pytest.mark.asyncio` 標記。
- 覆蓋率：`tests/run_e2e_tests.py --coverage` 或 `pytest --cov`（若已設定）。

## Commit 與 PR 準則

- 建議採 Conventional Commits：`feat(api): ...`、`fix(memory): ...`、`docs: ...`、`refactor: ...`、`style: ...`。
- PR 需包含：變更摘要、連結議題、測試範圍，Extension 變更請附截圖／GIF。
- 變更 API 合約時請同步更新 README／相關文件與測試。

## 安全與設定

- 勿提交密鑰；使用 `.env`（可參考 `.env.simple`）。常用鍵：`OPENAI_API_KEY`、`GOOGLE_API_KEY`、`LANGTRACE_API_KEY`。
- 注意外部服務額度限制；善用 `src/api/cache/` 與 CrewAI Memory 快取。

## 代理（Agent）貢獻建議

- 僅修改相關模組並遵循目錄慣例。
- 新增 API 時請於 `src/api/routes/` 註冊 router，並補上測試。
- 以小且聚焦的變更為主；提交前執行 `pre-commit run -a`。
