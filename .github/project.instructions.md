# TrailTag 開發指南

## 專案概覽

TrailTag 是一個基於 CrewAI 框架的專案，用於將 YouTube 影響者的旅程轉換成互動式旅遊地圖。此專案使用 AI 代理人協同工作來處理影片內容，並產生結構化的旅遊資訊。

## 專案結構

```
src/trailtag/
├── config/          # 代理人和任務的設定檔
│   ├── agents.yaml  # AI 代理人的角色定義
│   └── tasks.yaml   # 工作流程任務定義
├── tools/           # 自訂工具
└── crew.py         # CrewAI 代理人和任務的實作
```

## 關鍵模式

### CrewAI 整合

- 使用 `@CrewBase` 裝飾器來定義主要的 Crew 類別
- 使用 `@agent`、`@task` 和 `@crew` 裝飾器來定義元件
- 代理人和任務設定使用 YAML 格式進行設定，支援變數插值 (例如 `{topic}`)

### 開發工作流程

1. 在 `config/agents.yaml` 定義新的代理人角色和目標
2. 在 `config/tasks.yaml` 定義相關任務
3. 在 `crew.py` 中實作對應的代理人和任務方法
4. 使用 `pyproject.toml` 管理相依套件和專案資訊

### 命令列工具

專案提供以下命令：
- `trailtag` 或 `run_crew` - 執行主要工作流程
- `train` - 訓練代理人（需要指定迭代次數和輸出檔案）
- `replay` - 重播特定任務的執行
- `test` - 測試工作流程（需要指定迭代次數和評估模型）

## 代碼規範

- 使用 Python 3.10+ 
- 使用 Black 進行程式碼格式化
- 使用 Ruff 進行程式碼品質檢查
- 使用 pre-commit hooks 自動執行以上檢查

## 提示和技巧

1. 擴充功能：
   - 新增工具時使用 `tools/custom_tool.py` 作為範本
   - 工具需要實作 `_run` 方法和定義輸入架構

2. 除錯技巧：
   - 設定 `verbose=True` 來查看詳細的執行日誌
   - 使用 `replay` 命令重播特定任務以進行除錯

3. 最佳實踐：
   - 將共用邏輯放在 tools 目錄下
   - 在 YAML 檔案中使用變數來提高重用性
   - 保持任務獨立且職責單一
