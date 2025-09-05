/**
 * popup.ts - Popup UI 與狀態管理邏輯（TypeScript）
 *
 * 主要責任：
 * - 維護 popup 的應用狀態並更新 UI
 * - 與後端 API 互動（提交分析、查詢 job 狀態、取得 locations）
 * - 當 SSE/背景不可用時以 polling 取代
 * - 整合字幕檢測系統
 *
 * 本次重排僅調整函式順序與區塊結構，提高可讀性與維護性，不改變行為。
 */
// 導入字幕檢查器
import { SubtitleChecker } from "./subtitle-detector.js";
// 優先使用全域註冊的 Utils（若存在）以便測試或 runtime 相容
const Utils =
  (typeof window !== "undefined" && window.TrailTag && window.TrailTag.Utils) ||
  null;
const getCurrentVideoId = Utils
  ? Utils.getCurrentVideoId
  : typeof window !== "undefined"
    ? window.getCurrentVideoId
    : undefined;
const loadState = Utils
  ? Utils.loadState
  : typeof window !== "undefined"
    ? window.loadState
    : undefined;
const saveState = Utils
  ? Utils.saveState
  : typeof window !== "undefined"
    ? window.saveState
    : undefined;
// 應用的幾個狀態常數
export const AppState = {
  IDLE: "idle",
  CHECKING_CACHE: "checking_cache",
  ANALYZING: "analyzing",
  MAP_READY: "map_ready",
  ERROR: "error",
};
// 全域可變的應用狀態物件（儲存在 popup 的記憶體中）
export let state = {
  currentState: AppState.IDLE,
  videoId: null,
  jobId: null,
  error: null,
  progress: 0,
  phase: null,
  mapVisualization: null,
  activeEventSource: null,
  subtitleChecker: null, // 字幕檢查器實例
  lastUpdated: Date.now(),
};
// cache DOM 元素引用與地圖實例以避免重複查詢
let elements = null;
let map = null;
// ----------------------
// UI helpers / text
// ----------------------
/** Internal helper: safeTextContent - set textContent if element exists */
function safeTextContent(el, text) {
  if (!el) return;
  try {
    el.textContent = text;
  } catch (e) {}
}
export function getStatusText(appState) {
  switch (appState) {
    case AppState.IDLE:
      return "閒置";
    case AppState.CHECKING_CACHE:
      return "檢查中";
    case AppState.ANALYZING:
      return "分析中";
    case AppState.MAP_READY:
      return "已完成";
    case AppState.ERROR:
      return "錯誤";
    default:
      return "未知";
  }
}
export function getPhaseText(phase) {
  switch (phase) {
    case "metadata":
      return "正在抓取影片資料...";
    case "compression":
      return "正在壓縮字幕...";
    case "summary":
      return "正在分析主題與地點...";
    case "geocode":
      return "正在解析地理座標...";
    default:
      return "正在處理...";
  }
}
/**
 * 查詢並快取必要的 DOM 元素引用
 * - 將常用的 DOM 節點保存在 elements，供 updateUI 與事件處理器使用
 * @calledFrom registerApp
 */
export function queryElements() {
  elements = {
    views: {
      idle: document.getElementById("idle-view"),
      checking: document.getElementById("checking-view"),
      analyzing: document.getElementById("analyzing-view"),
      map: document.getElementById("map-view"),
      error: document.getElementById("error-view"),
    },
    statusBadge: document.getElementById("status-badge"),
    analyzeBtn: document.getElementById("analyze-btn"),
    cancelBtn: document.getElementById("cancel-btn"),
    retryBtn: document.getElementById("retry-btn"),
    reportBtn: document.getElementById("report-btn"),
    exportBtn: document.getElementById("export-btn"),
    progressBar: document.getElementById("progress-bar"),
    progressText: document.getElementById("progress-text"),
    phaseText: document.getElementById("phase-text"),
    errorMessage: document.getElementById("error-message"),
    locationsCount: document.getElementById("locations-count"),
  };
}
/**
 * 準備回報錯誤的簡短摘要並嘗試複製到剪貼簿，同時開啟 mailto 以便使用者進一步貼上。
 */
export function reportError() {
  const errText = state.error || "未知錯誤";
  const debugId =
    state && (state.debugId || state.errorDebugId)
      ? state.debugId || state.errorDebugId
      : "";
  const jobId = state.jobId || "";
  const videoId = state.videoId || "";
  const body = `TrailTag 錯誤回報%0AvideoId: ${videoId}%0AjobId: ${jobId}%0AdebugId: ${debugId}%0Amessage: ${errText}`;
  const subject = encodeURIComponent("TrailTag 錯誤回報");
  const mailto = `mailto:sacahan@gmail.com?subject=${subject}&body=${body}`;
  // 複製摘要到剪貼簿（若可用）
  try {
    const clipboardText = `videoId:${videoId}\njobId:${jobId}\ndebugId:${debugId}\nmessage:${errText}`;
    if (navigator && navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(clipboardText).catch(() => {});
    }
  } catch (e) {}
  // 開啟 mailto 以便使用者寄出或貼上內容
  try {
    window.open(mailto, "_blank");
  } catch (e) {
    /* ignore */
  }
}
/**
 * 根據目前 state 更新 popup 的 UI
 * - 隱藏/顯示不同視圖、更新進度條與文字說明
 * @calledFrom changeState, initializeApp
 */
export function updateUI() {
  if (!elements) return;
  Object.values(elements.views).forEach((view) => view.classList.add("hidden"));
  elements.statusBadge.textContent = getStatusText(state.currentState);
  elements.statusBadge.className = "status-badge";
  /**
   * 根據目前的應用狀態切換 UI 顯示區塊與狀態徽章樣式
   * - IDLE: 顯示閒置視圖
   * - CHECKING_CACHE: 顯示檢查快取視圖
   * - ANALYZING: 顯示分析進度與階段
   * - MAP_READY: 顯示地圖與地點數
   * - ERROR: 顯示錯誤訊息
   */
  switch (state.currentState) {
    case AppState.IDLE:
      // 閒置狀態：顯示 idle 視圖，狀態徽章加上 idle 樣式
      elements.views.idle.classList.remove("hidden");
      elements.statusBadge.classList.add("idle");
      break;
    case AppState.CHECKING_CACHE:
      // 檢查快取狀態：顯示 checking 視圖，狀態徽章加上 analyzing 樣式
      elements.views.checking.classList.remove("hidden");
      elements.statusBadge.classList.add("analyzing");
      break;
    case AppState.ANALYZING:
      // 分析中：顯示 analyzing 視圖，更新進度條、進度文字與階段說明
      elements.views.analyzing.classList.remove("hidden");
      elements.statusBadge.classList.add("analyzing");
      elements.progressBar.style.width = `${state.progress}%`;
      elements.progressText.textContent = `${Math.round(state.progress)}%`;
      elements.phaseText.textContent = getPhaseText(state.phase);
      break;
    case AppState.MAP_READY:
      // 地圖已完成：顯示 map 視圖，初始化地圖並顯示地點數
      elements.views.map.classList.remove("hidden");
      elements.statusBadge.classList.add("ready");
      if (!map) {
        try {
          if (
            typeof window !== "undefined" &&
            window.TrailTag &&
            window.TrailTag.Map &&
            typeof window.TrailTag.Map.initMap === "function"
          ) {
            map = window.TrailTag.Map.initMap("map");
          } else if (typeof initMap === "function") {
            map = initMap("map");
          }
        } catch (e) {
          console.warn("Map init failed", e);
          map = null;
        }
      }
      if (state.mapVisualization) {
        // 嘗試將地點資料加到地圖上，並顯示地點數
        let addFn = null;
        if (
          typeof window !== "undefined" &&
          window.TrailTag &&
          window.TrailTag.Map &&
          typeof window.TrailTag.Map.addMarkersFromMapVisualization ===
            "function"
        ) {
          addFn = window.TrailTag.Map.addMarkersFromMapVisualization;
        } else if (typeof addMarkersFromMapVisualization === "function") {
          addFn = addMarkersFromMapVisualization;
        }
        if (addFn) {
          try {
            const markersCount = addFn(state.mapVisualization, state.videoId);
            elements.locationsCount.textContent = `${markersCount} 個地點`;
          } catch (e) {
            console.error("Error adding markers to map:", e);
            elements.locationsCount.textContent = `0 個地點`;
          }
        }
      }
      break;
    case AppState.ERROR:
      // 錯誤狀態：顯示 error 視圖，狀態徽章加上 error 樣式，顯示錯誤訊息
      elements.views.error.classList.remove("hidden");
      elements.statusBadge.classList.add("error");
      elements.errorMessage.textContent = state.error || "未知錯誤";
      break;
  }
}
/**
 * 切換應用狀態並保存至 chrome.storage（若可用），之後更新 UI
 * - newState: 目標狀態
 * - data: 可選的狀態補充欄位，例如 videoId / jobId / progress
 */
export function changeState(newState, data = {}) {
  console.log(`State change: ${state.currentState} -> ${newState}`, data);
  state = {
    ...state,
    currentState: newState,
    ...data,
    lastUpdated: Date.now(),
  };
  saveState(state);
  updateUI();
}
/**
 * 啟動分析流程：
 * 1. 嘗試從目前分頁取得 videoId
 * 2. 檢查快取（getVideoLocations）是否已有結果，若有直接顯示地圖
 * 3. 若無則呼叫 submitAnalysis 開始分析並註冊事件監聽
 *
 * @calledFrom UI (analyze button), tests
 */
export async function startAnalysis() {
  /**
   * 啟動分析流程主邏輯
   * 1. 取得目前分頁的 videoId，若無則顯示錯誤
   * 2. 切換至檢查快取狀態
   * 3. 檢查是否已有地點資料（快取），若有直接顯示地圖
   * 4. 若無快取則呼叫 submitAnalysis 開始分析
   *    - 若 API 回傳 cached，則再取一次地點資料並顯示地圖
   *    - 否則切換至分析中狀態，並啟動事件監聽
   * 5. 任一環節失敗則顯示錯誤
   */
  try {
    // 1. 取得目前分頁的 videoId
    const videoId = await getCurrentVideoId();
    if (!videoId) {
      changeState(AppState.ERROR, {
        error: "無法識別 YouTube 影片 ID，請確認您正在瀏覽 YouTube 影片頁面。",
      });
      return;
    }
    // 2. 切換至檢查快取狀態
    changeState(AppState.CHECKING_CACHE, { videoId });
    // 3. 檢查是否已有地點資料（快取）
    try {
      const locations = await (typeof window !== "undefined" &&
      window.TrailTag &&
      window.TrailTag.API &&
      typeof window.TrailTag.API.getVideoLocations === "function"
        ? window.TrailTag.API.getVideoLocations(videoId)
        : Promise.resolve(null));
      if (locations) {
        // 有快取則直接顯示地圖
        changeState(AppState.MAP_READY, { mapVisualization: locations });
        return;
      }
    } catch (error) {
      // 快取查詢失敗僅記錄錯誤，不中斷流程
      console.error("Check cache error:", error);
    }
    // 4. 呼叫 submitAnalysis 開始分析
    const videoUrl = `https://www.youtube.com/watch?v=${videoId}`;
    const response = await (typeof window !== "undefined" &&
    window.TrailTag &&
    window.TrailTag.API &&
    typeof window.TrailTag.API.submitAnalysis === "function"
      ? window.TrailTag.API.submitAnalysis(videoUrl)
      : Promise.resolve({ cached: false, job_id: null, phase: null }));
    if (response.cached) {
      // 若 API 回傳 cached，則再取一次地點資料並顯示地圖
      try {
        const locations = await (typeof window !== "undefined" &&
        window.TrailTag &&
        window.TrailTag.API &&
        typeof window.TrailTag.API.getVideoLocations === "function"
          ? window.TrailTag.API.getVideoLocations(videoId)
          : Promise.resolve(null));
        if (locations) {
          changeState(AppState.MAP_READY, { mapVisualization: locations });
          return;
        }
      } catch (error) {
        // 快取命中但資料取得失敗，僅記錄錯誤
        console.error("Get locations after cache hit error:", error);
      }
    }
    // 5. 切換至分析中狀態，並啟動事件監聽
    changeState(AppState.ANALYZING, {
      jobId: response.job_id,
      progress: 0,
      phase: response.phase || null,
    });
    startEventListener(response.job_id);
  } catch (error) {
    // 任一環節失敗則顯示錯誤
    console.error("Start analysis error:", error);
    changeState(AppState.ERROR, { error: `分析請求失敗: ${error.message}` });
  }
}
/**
 * 通知 background/service worker 開始監聽指定 jobId 的事件串流（SSE）
 * @param jobId 要監聽的 job id
 */
export function startEventListener(jobId) {
  // Start local polling as the popup-managed fallback (no service worker usage)
  try {
    startPolling(jobId);
  } catch (e) {
    console.error("Failed to start local polling for events:", e);
  }
}
/**
 * 停止事件監聽（通知 background）並停止任何備援輪詢
 */
export function stopEventListener() {
  if (state.jobId) {
    // Stop local polling and clear persisted active job state
    stopPolling();
    try {
      if (
        chrome &&
        chrome.storage &&
        chrome.storage.local &&
        typeof chrome.storage.local.remove === "function"
      ) {
        chrome.storage.local.remove(["trailtag_state_v1"], () => {
          /* noop */
        });
      }
    } catch (e) {
      /* ignore */
    }
    state.jobId = null;
  }
}
let pollingIntervalId = null;
const POLLING_INTERVAL_MS =
  typeof TRAILTAG_CONFIG !== "undefined" && TRAILTAG_CONFIG.POLLING_INTERVAL_MS
    ? TRAILTAG_CONFIG.POLLING_INTERVAL_MS
    : 2500;
/**
 * 透過 API 輪詢 job 狀態，用於 SSE 無法使用時作為備援
 * - 會更新進度並在完成或失敗時做相對應處理
 */
export async function pollJobStatus(jobId) {
  /**
   * 輪詢指定 jobId 的狀態：
   * 1. 取得任務狀態（API）
   * 2. 若有進度則更新 UI
   * 3. 若已完成則停止輪詢並處理完成流程
   * 4. 若失敗則停止輪詢並顯示錯誤
   */
  try {
    // 1. 取得任務狀態
    const status = await (typeof window !== "undefined" &&
    window.TrailTag &&
    window.TrailTag.API &&
    typeof window.TrailTag.API.getJobStatus === "function"
      ? window.TrailTag.API.getJobStatus(jobId)
      : Promise.resolve(null));
    if (!status) return;
    // 2. 若有進度則更新 UI
    if (status.progress != null) {
      changeState(AppState.ANALYZING, {
        progress: status.progress,
        phase: status.phase || state.phase,
      });
    }
    // 3. 若已完成則停止輪詢並處理完成流程
    if (status.status === "completed" || status.status === "done") {
      stopPolling();
      handleJobCompleted();
    }
    // 4. 若失敗則停止輪詢並顯示錯誤
    else if (status.status === "failed" || status.status === "error") {
      stopPolling();
      changeState(AppState.ERROR, { error: status.message || "Job failed" });
    }
  } catch (error) {
    // 輪詢過程發生錯誤，僅記錄不中斷主流程
    console.error("Polling job status error:", error);
  }
}
/** 啟動備援輪詢（會先停止現有輪詢） */
export function startPolling(jobId) {
  stopPolling();
  pollingIntervalId = setInterval(
    () => pollJobStatus(jobId),
    POLLING_INTERVAL_MS,
  );
  console.log("Started polling for job:", jobId);
}
/** 停止輪詢 */
export function stopPolling() {
  if (pollingIntervalId) {
    clearInterval(pollingIntervalId);
    pollingIntervalId = null;
    console.log("Stopped polling");
  }
}
/**
 * 任務完成後的處理流程：
 * - 取得地點資料
 * - 嘗試預先初始化地圖並切換至 MAP_READY 顯示結果
 */
export async function handleJobCompleted() {
  /**
   * 任務完成後：
   * 1. 取得地點資料（API）
   * 2. 嘗試預先初始化地圖（避免 UI 卡住）
   * 3. 切換狀態至 MAP_READY 並顯示地圖
   * 4. 若失敗則顯示錯誤
   */
  try {
    // 1. 取得地點資料
    const locations = await (typeof window !== "undefined" &&
    window.TrailTag &&
    window.TrailTag.API &&
    typeof window.TrailTag.API.getVideoLocations === "function"
      ? window.TrailTag.API.getVideoLocations(state.videoId)
      : Promise.resolve(null));
    if (locations) {
      // 2. 嘗試預先初始化地圖（非必要，僅提升體驗）
      try {
        if (
          typeof window !== "undefined" &&
          window.TrailTag &&
          window.TrailTag.Map &&
          typeof window.TrailTag.Map.initMap === "function"
        ) {
          window.TrailTag.Map.initMap("map");
        } else if (typeof initMap === "function") {
          initMap("map");
        }
      } catch (e) {
        // 地圖初始化失敗不影響主流程，僅記錄警告
        console.warn("pre-init map failed:", e);
      }
      // 3. 切換狀態至 MAP_READY 並顯示地圖
      try {
        changeState(AppState.MAP_READY, { mapVisualization: locations });
      } catch (e) {
        // 狀態切換失敗則顯示錯誤
        console.error("Error while changing to MAP_READY:", e);
        changeState(AppState.ERROR, { error: `顯示地圖失敗: ${e.message}` });
      }
    } else {
      // 4. 若無地點資料則顯示錯誤
      throw new Error("無法獲取地點資料");
    }
  } catch (error) {
    // 取得地點資料失敗則顯示錯誤
    console.error("Handle job completed error:", error);
    changeState(AppState.ERROR, {
      error: `獲取地點資料失敗: ${error.message}`,
    });
  }
}
/**
 * 將目前的 mapVisualization 轉為 GeoJSON 並觸發下載
 * - 需有 state.mapVisualization 與 state.videoId
 */
export function exportGeoJSON() {
  if (!state.mapVisualization || !state.videoId) {
    console.error("No map visualization or video ID available");
    return;
  }
  const geoJSON =
    typeof window !== "undefined" &&
    window.TrailTag &&
    typeof window.TrailTag.Utils !== "undefined" &&
    typeof window.TrailTag.Utils.generateGeoJSON === "function"
      ? window.TrailTag.Utils.generateGeoJSON(state.mapVisualization)
      : null;
  if (
    geoJSON &&
    typeof window !== "undefined" &&
    typeof window.downloadGeoJSON === "function"
  ) {
    downloadGeoJSON(geoJSON, state.videoId);
  }
}
/**
 * initializeApp - 初始化 popup 應用邏輯
 *
 * 主要流程：
 * - 檢查是否在 YouTube 影片頁，若不是則切到 ERROR
 * - 嘗試從後端取得已存在的 locations；若有直接顯示地圖並移除已保存的任務資料
 * - 若無快取，重置本地 state 為 CHECKING_CACHE
 * - 嘗試從 persisted state 恢復先前未完成的 job，並與後端同步最新狀態
 *   - 若 job 已完成/失敗/進行中，根據後端回傳更新 UI 並啟動 polling（如需要）
 * - 若無可恢復任務或同步失敗，切到 IDLE
 *
 * 實作注意事項：
 * - 不直接使用儲存的 saved.currentState，全部以後端狀態為準
 * - 所有外部 API 呼叫以 window.TrailTag.API 的存在檢查包裹
 * - 會在必要時清除 chrome.storage.local 的 persisted state（trailtag_state_v1）
 *
 * @async
 * @returns {Promise<void>}
 * @calledFrom registerApp
 */
export async function initializeApp() {
  const currentVideoId = await getCurrentVideoId();
  const isVideoPage = !!currentVideoId;
  // 若非影片頁則顯示錯誤
  if (!isVideoPage) {
    changeState(AppState.ERROR, {
      error: "請在 YouTube 影片頁面使用此擴充功能。",
    });
    return;
  }
  // 初始化字幕檢查器
  if (!state.subtitleChecker) {
    state.subtitleChecker = new SubtitleChecker("subtitle-status");
  }
  // 檢查當前影片的字幕可用性
  try {
    const canAnalyze =
      await state.subtitleChecker.checkCurrentVideo(currentVideoId);
    // 如果沒有字幕，暫停初始化流程，讓用戶看到提示
    if (!canAnalyze) {
      // 更新按鈕狀態為不可用
      const analyzeBtn = document.getElementById("analyze-btn");
      if (analyzeBtn) {
        analyzeBtn.disabled = true;
        analyzeBtn.textContent = "此影片無字幕，無法分析";
        analyzeBtn.style.opacity = "0.6";
      }
      return; // 停止進一步的初始化
    }
  } catch (error) {
    console.warn("字幕檢查失敗，繼續初始化流程:", error);
  }
  // 1) 先嘗試取得地點資料，若有則直接顯示地圖並嘗試移除先前儲存的任務狀態
  try {
    const latestLocations = await (typeof window !== "undefined" &&
    window.TrailTag &&
    window.TrailTag.API &&
    typeof window.TrailTag.API.getVideoLocations === "function"
      ? window.TrailTag.API.getVideoLocations(currentVideoId)
      : Promise.resolve(null));
    if (latestLocations) {
      changeState(AppState.MAP_READY, {
        videoId: currentVideoId,
        mapVisualization: latestLocations,
        jobId: null,
        progress: 100,
        phase: null,
      });
      // 若有舊的 persisted 任務狀態，移除它，避免 popup 之後誤判
      try {
        if (
          chrome &&
          chrome.storage &&
          chrome.storage.local &&
          typeof chrome.storage.local.remove === "function"
        ) {
          chrome.storage.local.remove(["trailtag_state_v1"], () => {
            /* noop */
          });
        }
      } catch (e) {
        /* ignore */
      }
      return;
    }
  } catch (e) {
    console.warn("Failed to fetch locations on init:", e);
  }
  // 2) 無快取地點資料 -> 重設本地 state 並進入 CHECKING_CACHE
  state = {
    ...state,
    videoId: currentVideoId,
    jobId: null,
    mapVisualization: null,
    currentState: AppState.CHECKING_CACHE,
    progress: 0,
    phase: null,
  };
  updateUI();
  // 3) 嘗試恢復先前儲存的分析任務；若 chrome.storage.local 有保存任務則忽略儲存的狀態值
  //    直接呼叫後端 API 取得最新 job 狀態並以該狀態更新與保存 local state
  try {
    const saved = await loadState();
    if (saved) {
      try {
        // 先透過 videoId 嘗試取得後端目前對應的 job（避免使用已儲存的 jobId 為 stale）
        const mapped = await (typeof window !== "undefined" &&
        window.TrailTag &&
        window.TrailTag.API &&
        typeof window.TrailTag.API.getJobByVideo === "function"
          ? window.TrailTag.API.getJobByVideo(currentVideoId)
          : Promise.resolve(null));
        // 如果後端回傳了對應的 job_id，再向後端查詢該 job 的詳細狀態；否則視為沒有可恢復的任務
        let latestStatus = null;
        if (mapped && mapped.job_id) {
          latestStatus = await (typeof window !== "undefined" &&
          window.TrailTag &&
          window.TrailTag.API &&
          typeof window.TrailTag.API.getJobStatus === "function"
            ? window.TrailTag.API.getJobStatus(mapped.job_id)
            : Promise.resolve(null));
        }
        /**
                 * {
                    "job_id": "55309d4c-ce65-457e-be4f-2ed08374bc6d",
                    "video_id": "sROac3CHrI4",
                    "status": "running",
                    "phase": "metadata",
                    "progress": 5,
                    "cached": false,
                    "created_at": "2025-08-19T10:41:59.207297Z",
                    "updated_at": "2025-08-19T10:41:59.233663Z"
                    }
                 */
        if (latestStatus) {
          // 根據後端回傳的最新狀態決定本地狀態（ignore saved.currentState）
          const isCompleted =
            latestStatus.status === "completed" ||
            latestStatus.status === "done";
          const isFailed =
            latestStatus.status === "failed" || latestStatus.status === "error";
          if (isCompleted) {
            // 直接標示為 ANALYZING 的完成，之後 handleJobCompleted 會切換至 MAP_READY
            state = {
              ...state,
              jobId: saved.jobId,
              currentState: AppState.ANALYZING,
              progress:
                latestStatus.progress != null ? latestStatus.progress : 100,
              phase: latestStatus.phase || null,
            };
            saveState(state);
            updateUI();
            // 停止/啟動 polling 以取得最終結果
            try {
              startPolling(latestStatus.job_id);
            } catch (e) {
              /* ignore */
            }
            return;
          } else if (isFailed) {
            state = {
              ...state,
              jobId: latestStatus.job_id,
              currentState: AppState.ERROR,
              progress:
                latestStatus.progress != null
                  ? latestStatus.progress
                  : state.progress,
              phase: latestStatus.phase || state.phase,
              error: latestStatus.message || "Job failed",
            };
            saveState(state);
            updateUI();
            stopPolling();
            return;
          } else {
            // 任務仍在進行中，將 local state 設為 ANALYZING 並開始輪詢
            state = {
              ...state,
              jobId: latestStatus.job_id,
              currentState: AppState.ANALYZING,
              progress:
                latestStatus.progress != null
                  ? latestStatus.progress
                  : saved.progress || 0,
              phase: latestStatus.phase || saved.phase || null,
            };
            saveState(state);
            updateUI();
            try {
              startPolling(latestStatus.job_id);
            } catch (e) {
              /* ignore */
            }
            return;
          }
        } else {
          // 若無法取得最新任務狀態，清除先前儲存的狀態
          console.warn(
            "Failed to fetch job status for saved job:",
            saved.jobId,
          );
          try {
            if (
              chrome &&
              chrome.storage &&
              chrome.storage.local &&
              typeof chrome.storage.local.remove === "function"
            ) {
              chrome.storage.local.remove(["trailtag_state_v1"], () => {
                /* noop */
              });
            }
            stopPolling();
          } catch (e) {
            /* ignore */
          }
        }
      } catch (e) {
        console.warn(
          "Failed to sync job status from backend for saved job:",
          e,
        );
        // 若同步失敗，清除先前儲存的狀態，避免後續誤判
        try {
          if (
            chrome &&
            chrome.storage &&
            chrome.storage.local &&
            typeof chrome.storage.local.remove === "function"
          ) {
            chrome.storage.local.remove(["trailtag_state_v1"], () => {
              /* noop */
            });
          }
          stopPolling();
        } catch (e) {
          /* ignore */
        }
      }
    }
  } catch (e) {
    console.warn("loadState error:", e);
  }
  // 4) 若無可恢復的任務或同步失敗，進入閒置狀態
  changeState(AppState.IDLE, { videoId: currentVideoId });
  stopPolling();
}
// popup 不再監聽 background/service worker 的 runtime messages；
// popup 改以直接向後端輪詢 (polling) 取得 job 狀態。
/**
 * 註冊 popup 應用的事件處理器與初始化邏輯
 * - 綁定 UI 按鈕事件（分析、取消、重試、匯出、回報錯誤）
 * - 初始化應用狀態
 * - 定期發送 keepAlive 訊息給 background/service worker
 * - 註冊測試輔助函式於 window（方便測試與除錯）
 */
export function registerApp() {
  // 查詢並快取 DOM 元素
  queryElements();
  // 綁定分析按鈕事件：啟動分析流程
  if (elements && elements.analyzeBtn) {
    elements.analyzeBtn.addEventListener("click", () => {
      const fn =
        typeof window !== "undefined" && window.startAnalysis
          ? window.startAnalysis
          : startAnalysis;
      return fn();
    });
  }
  // 綁定取消按鈕事件：停止事件監聽並切換至閒置狀態
  if (elements && elements.cancelBtn) {
    elements.cancelBtn.addEventListener("click", () => {
      const stopFn =
        typeof window !== "undefined" && window.stopEventListener
          ? window.stopEventListener
          : stopEventListener;
      stopFn();
      const changeFn =
        typeof window !== "undefined" && window.changeState
          ? window.changeState
          : changeState;
      changeFn(AppState.IDLE);
    });
  }
  // 綁定重試按鈕事件：重新啟動分析流程
  if (elements && elements.retryBtn) {
    elements.retryBtn.addEventListener("click", () => {
      const fn =
        typeof window !== "undefined" && window.startAnalysis
          ? window.startAnalysis
          : startAnalysis;
      return fn();
    });
  }
  // 綁定匯出按鈕事件：匯出 GeoJSON
  if (elements && elements.exportBtn) {
    elements.exportBtn.addEventListener("click", () => {
      const fn =
        typeof window !== "undefined" && window.exportGeoJSON
          ? window.exportGeoJSON
          : exportGeoJSON;
      return fn();
    });
  }
  // 綁定回報錯誤按鈕事件：回報錯誤摘要
  if (elements && elements.reportBtn) {
    elements.reportBtn.addEventListener("click", () => {
      reportError();
    });
  }
  // 初始化應用狀態與 UI
  initializeApp();
  // (已移除) 先前此處會定期向 background/service worker 發送 keepAlive。
  // 當 popup 被關閉或切換（visibilitychange / beforeunload）時，確保當前 state 被儲存到 storage
  // 以便重新打開 popup 時能夠恢復到分析中的狀態。
  const saveNow = () => {
    try {
      saveState(state);
    } catch (e) {
      /* ignore */
    }
  };
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      saveNow();
    }
  });
  // storage onChanged handler: 當 background 或 service worker 更新 persisted state 時，
  // popup 可即時反映並嘗試 re-attach
  const storageChangeHandler = (changes, areaName) => {
    if (areaName !== "local") return;
    if (!changes || !changes.trailtag_state_v1) return;
    const newVal = changes.trailtag_state_v1.newValue;
    if (!newVal) return;
    // 只對目前 videoId 的變更做反應
    if (newVal.videoId && newVal.videoId === state.videoId) {
      try {
        // 當 background 有 jobId 時更新 local state
        if (newVal.jobId) {
          state = {
            ...state,
            jobId: newVal.jobId,
            currentState: newVal.currentState || state.currentState,
            progress: newVal.progress || state.progress,
            phase: newVal.phase || state.phase,
          };
          try {
            saveState(state);
          } catch (e) {}
          updateUI();
          // start local polling for the new active job announced via storage changes
          try {
            startPolling(newVal.jobId);
          } catch (e) {}
        }
      } catch (e) {
        /* ignore */
      }
    }
  };
  try {
    if (
      chrome &&
      chrome.storage &&
      chrome.storage.onChanged &&
      typeof chrome.storage.onChanged.addListener === "function"
    ) {
      chrome.storage.onChanged.addListener(storageChangeHandler);
    }
  } catch (e) {
    /* ignore */
  }
  window.addEventListener("beforeunload", () => {
    saveNow();
    try {
      if (
        chrome &&
        chrome.storage &&
        chrome.storage.onChanged &&
        typeof chrome.storage.onChanged.removeListener === "function"
      ) {
        chrome.storage.onChanged.removeListener(storageChangeHandler);
      }
    } catch (e) {
      /* ignore */
    }
  });
  // 註冊測試輔助函式於 window，方便測試與除錯
  try {
    if (
      typeof window !== "undefined" &&
      typeof window.__registerPopupTestingHelpers === "function"
    ) {
      window.__registerPopupTestingHelpers({
        setState: (patch) => Object.assign(state, patch),
        getState: () => state,
        startPolling,
        stopPolling,
      });
      // 將主要流程函式掛到 window，方便測試或外部呼叫
      try {
        window.startPolling = startPolling;
        window.stopPolling = stopPolling;
        window.startAnalysis = startAnalysis;
        window.stopEventListener = stopEventListener;
        window.changeState = changeState;
        window.exportGeoJSON = exportGeoJSON;
      } catch (e) {}
    }
  } catch (e) {}
}
// 當 DOM 尚未載入完成時，監聽 DOMContentLoaded 事件以延後初始化；
// 若已載入則直接執行 registerApp 初始化 popup 應用邏輯。
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", registerApp);
} else {
  registerApp();
}
export default null;
