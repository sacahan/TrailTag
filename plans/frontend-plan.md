# TrailTag 前端 Chrome Extension 規格書

本規格書為[主要提案](project-proposal.md)的前端實作規範。

## 概述

本文件聚焦 TrailTag 的 Chrome Extension。Extension 讀取目前 YouTube 影片頁 URL，向後端查詢是否已有地點分析結果，若無則觸發分析並以 SSE/輪詢顯示進度與部分地點，完成後顯示互動地圖。

## 使用者旅程 (User Flow)

1. 使用者於 YouTube 影片頁開啟 Extension popup。
2. 系統解析 video_id，呼叫 `GET /api/videos/{id}/locations`。
3. 若已有資料 → 直接顯示地圖。
4. 若 404 → 呼叫 `POST /api/videos/analyze` 取得 job_id。
5. 建立 SSE 連線或啟動輪詢更新進度。
6. 在進度完成時，呼叫。
7. 完成後顯示統計與匯出功能。

## 前端流程循序圖

以下循序圖詳細說明 Chrome Extension 前端組件之間的互動流程，以及與後端 API 的完整通訊過程：

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant P as Popup
  participant SW as Service Worker
  participant API as Backend API
  participant Cache as Chrome Storage

  Note over U,Cache: 使用者開啟 Extension Popup
  U->>P: 開啟 Extension Popup
  P->>P: 解析當前頁面 video_id
  P->>Cache: 檢查本地快取狀態

  alt 本地有快取且未過期
    Cache-->>P: 返回快取的 locations
    P->>P: 渲染地圖 (map_ready 狀態)
    P->>U: 顯示完整地圖
  else 無快取或已過期
    P->>API: GET /videos/{id}/locations
    alt 後端已有分析結果
      API-->>P: 200 locations
      P->>Cache: 儲存 locations 到快取
      P->>P: 渲染地圖 (map_ready 狀態)
      P->>U: 顯示完整地圖
    else 後端無分析結果
      API-->>P: 404 Not Found
      P->>P: 切換到 analyzing 狀態
      P->>U: 顯示「準備分析」訊息
      P->>API: POST /videos/analyze {url}
      API-->>P: {job_id, status: queued}
      P->>Cache: 儲存 job_id 與時間戳記

      par SSE 連線監聽
        P->>SW: 請求建立 SSE 連線
        SW->>API: GET /jobs/{job_id}/stream
        loop 即時更新
          API-->>SW: event: phase_update
          SW->>P: 轉發進度事件
          P->>P: 更新進度條與階段文字
          P->>U: 顯示分析進度
        end
        API-->>SW: event: completed
        SW->>P: 通知分析完成
        P->>P: 切換到 completed 狀態
      and 錯誤處理與重試
        alt SSE 連線失敗
          SW->>SW: 嘗試重新連線
          alt 重連失敗
            SW->>P: 通知切換到輪詢模式
            loop 輪詢狀態
              P->>API: GET /jobs/{job_id}
              API-->>P: job status & progress
              P->>P: 更新 UI
              P->>U: 顯示進度
            end
          end
        else 網路錯誤
          P->>P: 顯示錯誤狀態
          P->>U: 顯示重試按鈕
          U->>P: 點擊重試
          P->>P: 重新開始分析流程
        end
      end

      Note over P,API: 分析完成後取得結果
      P->>API: GET /videos/{id}/locations
      API-->>P: 200 locations
      P->>Cache: 儲存 locations 到快取
      P->>P: 渲染地圖 (map_ready 狀態)
      P->>U: 顯示完整地圖與統計
    end
  end

  Note over U,Cache: 使用者互動功能
  opt 匯出功能
    U->>P: 點擊匯出按鈕
    P->>P: 生成 GeoJSON
    P->>U: 下載 GeoJSON 檔案
  end

  opt 地圖互動
    U->>P: 點擊地圖 Marker
    P->>P: 顯示地點資訊 Popup
    opt 時間碼跳轉
      U->>P: 點擊跳轉連結
      P->>U: 開啟 YouTube 影片特定時間點
    end
  end

  opt Popup 關閉與重開
    U->>P: 關閉 Popup
    P->>Cache: 保存當前狀態
    U->>P: 重新開啟 Popup
    P->>Cache: 讀取保存的狀態
    P->>P: 恢復之前的 UI 狀態
  end
```

### 狀態轉換說明

Extension Popup 主要狀態轉換：

1. **idle** → **checking_cache**：Popup 開啟時自動檢查快取
2. **checking_cache** → **map_ready**：快取命中，直接顯示地圖
3. **checking_cache** → **analyzing**：快取未命中，開始分析流程
4. **analyzing** → **map_ready**：分析完成，顯示結果
5. **analyzing** → **error**：分析失敗，顯示錯誤
6. **error** → **analyzing**：使用者點擊重試

### SSE 與輪詢策略

- **主要方式**：SSE 即時連線，低延遲更新進度
- **備援方式**：SSE 失敗時自動切換到輪詢模式
- **重連機制**：SSE 中斷時自動嘗試重新連線一次
- **輪詢頻率**：每 2-3 秒查詢一次 job 狀態

## 功能列表 (MVP)

| 功能              | 描述                                  | 優先級 |
| ----------------- | ------------------------------------- | ------ |
| 影片辨識          | 解析當前 tab YouTube video_id         | P0     |
| 查詢既有分析      | 快速判斷快取是否存在                  | P0     |
| 觸發分析          | 呼叫 /analyze 取得 job_id             | P0     |
| 進度顯示          | 百分比 + 階段文字                     | P0     |
| SSE 連線          | 接收 phase_update / completed / error | P0     |
| 地點地圖渲染      | Leaflet 基本地圖 + Marker             | P0     |
| 結果呈現          | 任務完成後一次性載入全量地點          | P0     |
| 錯誤處理與重試    | 基本重試 + 提示訊息                   | P0     |
| 匯出 GeoJSON      | 從現有 locations 生成                 | P1     |
| Marker clustering | >20 地點時分群                        | P1     |
| 時間碼跳轉        | Marker popup 提供跳轉影片功能         | P1     |
| 狀態快取          | chrome.storage 保存最近 job           | P1     |
| 主題顯示          | 顯示摘要主題或標籤                    | P2     |

## 架構與檔案

| 檔案              | 角色                                       |
| ----------------- | ------------------------------------------ |
| manifest.json     | MV3 設定、權限、service_worker 指定        |
| service_worker.js | 背景：SSE 管理、重試、訊息轉發             |
| popup.html        | UI 容器                                    |
| popup.js          | 狀態管理（有限 state machine）+ DOM 更新   |
| api.js            | 抽象後端 API 呼叫（fetch wrapper + retry） |
| map.js            | 地圖初始化與 Marker 管理模組               |
| styles.css        | 基礎樣式                                   |
| utils.js          | 解析 video_id、格式化時間                  |

## State Machine (概念)

States: idle → checking_cache → analyzing → map_ready → error

```text
Transition:
 idle -> checking_cache (open popup)
 checking_cache -> map_ready (cache hit)
 checking_cache -> analyzing (cache miss + analyze start)
 analyzing -> map_ready (completed)
 analyzing -> error (fail)
 error -> analyzing (retry)
```

## SSE 事件處理

| 事件         | 動作                                    |
| ------------ | --------------------------------------- |
| phase_update | 更新階段標籤 + 百分比                   |
| completed    | 切換 map_ready 狀態並觸發一次性抓取地點 |
| error        | 顯示錯誤並提供重試                      |

## UI 規劃

| 區塊   | 元件              | 說明                             |
| ------ | ----------------- | -------------------------------- |
| Header | 標題 + 狀態徽章   | 顯示目前階段                     |
| Body   | 狀態訊息 / 進度條 | analyzing 時顯示                 |
| Map    | Leaflet 容器      | map_ready 顯示                   |
| Footer | 動作按鈕          | retry / export / open in new tab |

## 畫面狀態與對應功能（實作範圍與優先）

下列為 extension popup 在各種狀態下的畫面顯示、主要功能、資料契約與對應要實作的位置。依你的指示，我將優先實作下列項目：

- 必須實作：1) 狀態持久化（save/load state）、3) popup ↔ background 重新 attach 機制、4) 錯誤分類與回報按鈕。
- 可以實作但不在 UI 提供按鈕：2) 權限/配額處理（不顯示「授權並重試」或「手動上傳」按鈕）。
- 不實作（本次迭代略過）：5) Partial incremental UI、6) Accessibility 深度優化、7) 進階 UX 改善。

每個狀態說明：

- Idle（未分析 / 初始）

  - 顯示：`idle-view`，標題、簡短說明、主要按鈕「分析此影片」。
  - 主要動作：使用者點擊 `analyze-btn` → 呼 `startAnalysis()` → 切換到 `checking_cache` 或 `analyzing`。
  - 資料契約：無輸入；按下後呼 `POST /api/videos/analyze { url }`，得到 `{ job_id, cached? }`。
  - 要修改的檔案：`src/extension/popup.html`（view）、`src/extension/popup.ts`（行為）。

- Checking_cache（檢查快取）

  - 顯示：`checking-view`，spinner 與說明文字。
  - 主要動作：呼 `GET /api/videos/{id}/locations`；若命中直接切 MAP_READY，否則觸發分析流程。
  - 要修改的檔案：`src/extension/popup.ts`、`src/extension/api.ts`（已存在）。

- Analyzing（分析中 / 進度）

  - 顯示：`analyzing-view`，進度條（`progress-bar`）、階段文字（`phase-text`）、取消按鈕。
  - 主要動作：建立 SSE（由 service worker 建立並轉發），或在 SSE 失敗後以 polling 更新；可取消（停止 event listener 並回到 IDLE）。
  - 資料契約：phase_update events { progress, phase, optional partial payload }；completed / error events。
  - 要修改的檔案（必做）：`src/extension/popup.ts`（在 initialize 階段加入 restore/attach 邏輯）、`src/extension/service_worker.ts`（background attach 已具部分實作，可強化回應 attach 要求）。

- Map_ready（已完成）

  - 顯示：`map-view`，Leaflet 地圖、地點數、匯出按鈕。
  - 主要動作：顯示 markers、提供 `exportGeoJSON()` 下載功能。
  - 要修改的檔案：`src/extension/popup.ts`（map 初始化）與 `src/extension/api.ts` / `src/extension/utils.ts`（GeoJSON 生成與下載已實作）。

- Error（錯誤）

  - 顯示：`error-view`，錯誤友善訊息、主要按鈕「重試」、以及「回報錯誤」按鈕（本次將加上）。
  - 主要動作：錯誤會包含可分類資訊（HTTP code / message / debugId），UI 顯示分類後的建議文案；按「回報錯誤」會將錯誤摘要與 debugId 準備好以便用戶複製或觸發 mailto/issue（不自動上傳任何敏感資訊）。
  - 要修改的檔案（必做）：`src/extension/popup.html`（在 error view 加回報按鈕）、`src/extension/popup.ts`（錯誤顯示與回報邏輯）、`src/extension/api.ts`（在出錯時包含 code/debugId）。

- Empty / Not supported（無可分析內容）

  - 顯示：目前會回到 IDLE 或顯示 ERROR（「請在 YouTube 影片頁使用」）；計畫中可新增 `empty-view` 以說明原因，但本次不為必做。若要處理 CSP 或 iframe 問題，會在 error 分類中標示為 "unsupported"。
  - 決策：此狀態不新增手動上傳按鈕（依指示不在 UI 顯示）。

- Auth / Rate-limit（權限或配額）

  - 顯示：分類後的錯誤提示（如 401/403/429），說明性文案與下一步建議（例如稍後再試或聯絡維運）。
  - 決策：會在錯誤分類時顯示建議，但不提供「授權並重試」或「手動上傳」按鈕（按你要求）。

- Cancelled / Paused（已取消/暫停）
  - 顯示：取消後 UI 會回到 IDLE（目前設計），若需專屬 cancelled view 可於後續加入；本次維持現狀（回 IDLE）。

檔案變更總覽（本次迭代）

- 必做（會在此迭代修改）
  1. `src/extension/utils.ts` — 實作 `saveState()` / `loadState()` 使用 `chrome.storage.local`（含 TTL / 最低欄位：videoId, jobId, timestamp, progress）。
  2. `src/extension/popup.ts` — 在 `initializeApp()` 加入從 storage restore 的流程；若發現尚未完成的 jobId，發訊息給 background 請求 attach 或呼 `startEventListener(jobId)`；在 `registerApp()` 確保重新 attach 與 polling 控制。
  3. `src/extension/popup.html` — 在 `error-view` 加上「回報錯誤」按鈕（並在 `popup.ts` 中實作回報 handler），不新增授權/上傳按鈕。
  4. `src/extension/api.ts` / `src/extension/service_worker.ts` — 在 error/fail/path 中包含可辨識的 code 或 debugId，並在 service worker 對 attach 請求做更明確的回應（若 background 端已有 job，回傳 jobId）。

驗收準則（短期）

- 開啟 popup 且有未完成 job 時，popup 能自動恢復 "分析中" 的 UI 並繼續接收進度（SSE 或 polling）。
- 於分析中關閉再開啟 popup，不會造成多重 listener；state 能被正確還原或 background attach。
- 發生錯誤時，Error view 顯示分類後的友善文案並提供「回報錯誤」的動作；API 回傳包含 code/debugId 以便回報。

如要我開始實作上述變更，回覆「請實作」，我會依序在 repo 上做小幅 patch（先完成 save/load state 與 popup restore），每個步驟完成後執行快速檢查並回報結果。

## 進度條策略

- 後端提供 progress（0~100）→ 直接映射。
- 沒有新事件 >10s 時：顯示 spinner 與「等待伺服器回應」。
- 前端不維護任何地點增量暫存，僅在完成時一次性接收。

## 錯誤與重試策略

| 類型               | 行為                                  |
| ------------------ | ------------------------------------- |
| Network / 5xx      | 指數退避 (1s,2s,4s) 最多 3 次         |
| 4xx (client error) | 顯示錯誤訊息，不自動重試              |
| SSE 中斷           | 立即嘗試重新連線 1 次 → fallback 輪詢 |

## 安全與權限最小化

- permissions: ["tabs", "storage"]
- host_permissions: ["https://www.youtube.com/*"] (可簡化為使用 activeTab)
- 不讀取頁面 DOM（初期）；僅解析 URL query 取得 `v` 參數。

## 高風險點與緩解

| 風險         | 說明                 | 緩解                         |
| ------------ | -------------------- | ---------------------------- |
| SSE 被阻擋   | 公司網路或瀏覽器策略 | fallback 輪詢 GET /jobs/{id} |
| 地圖渲染延遲 | 大量 marker          | clustering + lazy popup      |
| 記憶體累積   | 多次進出 popup       | service_worker 清理 listener |
| 重複任務     | 使用者反覆點擊       | disable 按鈕 + 後端冪等快取  |

## Milestones

| 里程碑      | 內容                       | 完成判準               |
| ----------- | -------------------------- | ---------------------- |
| E1 Skeleton | manifest + popup 初始      | popup 顯示 idle        |
| E2 API 整合 | /locations + /analyze 串接 | 快取命中與觸發分析可行 |
| E3 SSE      | 即時進度（無地點增量）     | 進度條更新             |
| E4 地圖強化 | clustering + popup         | >20 地點仍順暢         |
| E5 匯出     | 產出 GeoJSON               | 下載檔案成功           |
| E6 穩健化   | 錯誤/重試/儲存             | 關閉再開仍接續         |

## 任務分解 (Backlog)

E1:

- 建立 manifest.json (MV3)
- 建立 popup.html / popup.js 基礎 DOM
- 加入 styles.css + reset

E2:

- utils: 解析 video_id
- api.js: fetch 包裝（含 JSON 錯誤）
- 呼叫 /locations 與 /analyze 分支流程

E3:

- service_worker: SSE channel 管理
- popup: 訂閱 background message (chrome.runtime.onMessage)
- progress bar component

E4:

- map.js: Leaflet 初始化 + marker add/update
- clustering 套件 (Leaflet.markercluster 或內建簡化)
- marker popup 模板（名稱 + 字幕節錄 + 跳轉連結）

E5:

- 匯出 GeoJSON 生成工具函式
- 下載按鈕 + Blob 觸發

E6:

- chrome.storage 狀態持久化（job_id, video_id, ts, progress）
- SSE 斷線重連 / fallback 輪詢
- error banner + retry 按鈕

## 後續延伸 (Future)

- 多影片聚合與跨影片搜尋
- 前端紀錄使用頻率指標 (匿名)
- 深色模式與無障礙優化

## 追蹤指標 (Extension)

- cache_hit_ratio
- avg_first_location_render_seconds
- analyze_to_done_seconds (p50/p90)
- sse_phase_events_per_job

## 品質保證

- ESLint + Prettier（若引入 build pipeline）
- 每個模組最小單元測試（可用 Vitest 若改為模組化建置）
- 手動測試腳本：列舉主要錯誤情境（無網路 / SSE 中斷 / 404）

## 最近變更（2025-08-16）

### 概要

- 在 `src/extension/popup.js` 的 `initializeApp()` 新增：當 popup 開啟且目前狀態不是 `ANALYZING` 時，自動向後端呼叫 `getVideoLocations(videoId)` 以嘗試取得後端已存在的地點資料，若有資料則直接切換到 `MAP_READY` 並顯示地圖。

- 新增兩個 Jest 測試（`src/extension/__tests__/popup.test.js`）來模擬 `getVideoLocations()` 的回傳行為：

  - 測試在非 `ANALYZING` 狀態時，`initializeApp()` 會呼叫 `getVideoLocations()` 並在取得資料時切換到 `MAP_READY`。

  - 測試在已為 `ANALYZING` 狀態時，`initializeApp()` 不會呼叫 `getVideoLocations()`（guard 生效，避免中斷進行中的 job）。

### 目的與風險

- 目的：確保使用者每次打開 popup 時能取得後端快取結果，立即顯示地圖（改善使用者體驗），同時避免在正在分析中的情況下干擾現行任務。

- 風險：增加一次額外的後端請求；設計為保守行為（僅在非 ANALYZING 時發送），並在請求失敗時只記錄 warning，不會中斷初始化流程。

### 驗證

- 已在 `src/extension` 執行 Jest 測試（本地測試環境）：4 個測試檔、18 個測試皆通過。

### 後續建議

- 顯示「資料來源：快取」與最後更新時間，讓使用者知道顯示的是後端快取結果。

- 若要更節省頻寬，可改為條件請求（ETag / If-Modified-Since）或短期失效的快取策略。
