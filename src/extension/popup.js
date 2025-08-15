/**
 * Popup 主控腳本
 */

// 狀態機狀態定義
const AppState = {
  IDLE: 'idle',
  CHECKING_CACHE: 'checking_cache',
  ANALYZING: 'analyzing',
  MAP_READY: 'map_ready',
  ERROR: 'error'
};

// 應用狀態
let state = {
  currentState: AppState.IDLE,
  videoId: null,
  jobId: null,
  error: null,
  progress: 0,
  phase: null,
  mapVisualization: null,
  activeEventSource: null,
  lastUpdated: Date.now()
};

// Note: For tests, a registration hook is available at window.__registerPopupTestingHelpers
// popup.js will call this at initialization to provide test-only helpers. Production code
// does not attach internal state or functions to global window by default.

// DOM 元素參考
const elements = {
  views: {
    idle: document.getElementById('idle-view'),
    checking: document.getElementById('checking-view'),
    analyzing: document.getElementById('analyzing-view'),
    map: document.getElementById('map-view'),
    error: document.getElementById('error-view')
  },
  statusBadge: document.getElementById('status-badge'),
  analyzeBtn: document.getElementById('analyze-btn'),
  cancelBtn: document.getElementById('cancel-btn'),
  retryBtn: document.getElementById('retry-btn'),
  exportBtn: document.getElementById('export-btn'),
  progressBar: document.getElementById('progress-bar'),
  progressText: document.getElementById('progress-text'),
  phaseText: document.getElementById('phase-text'),
  errorMessage: document.getElementById('error-message'),
  locationsCount: document.getElementById('locations-count')
};

/**
 * 更新 UI 以反映當前狀態
 */
function updateUI() {
  // 隱藏所有視圖
  Object.values(elements.views).forEach(view => view.classList.add('hidden'));

  // 更新狀態徽章
  elements.statusBadge.textContent = getStatusText(state.currentState);
  elements.statusBadge.className = 'status-badge';

  // 根據當前狀態顯示相應視圖
  switch (state.currentState) {
    case AppState.IDLE:
      elements.views.idle.classList.remove('hidden');
      elements.statusBadge.classList.add('idle');
      break;

    case AppState.CHECKING_CACHE:
      elements.views.checking.classList.remove('hidden');
      elements.statusBadge.classList.add('analyzing');
      break;

    case AppState.ANALYZING:
      elements.views.analyzing.classList.remove('hidden');
      elements.statusBadge.classList.add('analyzing');
      elements.progressBar.style.width = `${state.progress}%`;
      elements.progressText.textContent = `${Math.round(state.progress)}%`;
      elements.phaseText.textContent = getPhaseText(state.phase);
      break;

    case AppState.MAP_READY:
      elements.views.map.classList.remove('hidden');
      elements.statusBadge.classList.add('ready');

      // 確保地圖已初始化
      if (!map) {
        initMap('map');
      }

      // 若有新的資料，更新地圖
      if (state.mapVisualization) {
        const markersCount = addMarkersFromMapVisualization(state.mapVisualization, state.videoId);
        elements.locationsCount.textContent = `${markersCount} 個地點`;
      }
      break;

    case AppState.ERROR:
      elements.views.error.classList.remove('hidden');
      elements.statusBadge.classList.add('error');
      elements.errorMessage.textContent = state.error || '未知錯誤';
      break;
  }
}

/**
 * 獲取狀態顯示文字
 * @param {string} appState - 應用狀態
 * @returns {string} 顯示文字
 */
function getStatusText(appState) {
  switch (appState) {
    case AppState.IDLE:
      return '閒置';
    case AppState.CHECKING_CACHE:
      return '檢查中';
    case AppState.ANALYZING:
      return '分析中';
    case AppState.MAP_READY:
      return '已完成';
    case AppState.ERROR:
      return '錯誤';
    default:
      return '未知';
  }
}

/**
 * 獲取階段顯示文字
 * @param {string} phase - API 階段
 * @returns {string} 顯示文字
 */
function getPhaseText(phase) {
  switch (phase) {
    case 'metadata':
      return '正在抓取影片資料...';
    case 'compression':
      return '正在壓縮字幕...';
    case 'summary':
      return '正在分析主題與地點...';
    case 'geocode':
      return '正在解析地理座標...';
    default:
      return '正在處理...';
  }
}

/**
 * 切換應用狀態
 * @param {string} newState - 新狀態
 * @param {Object} data - 狀態相關資料
 */
function changeState(newState, data = {}) {
  console.log(`State change: ${state.currentState} -> ${newState}`, data);

  state = {
    ...state,
    currentState: newState,
    ...data,
    lastUpdated: Date.now()
  };

  // 保存狀態
  saveState(state);

  // 更新 UI
  updateUI();
}

/**
 * 啟動分析流程
 */
async function startAnalysis() {
  try {
    const videoId = await getCurrentVideoId();

    if (!videoId) {
      changeState(AppState.ERROR, { error: '無法識別 YouTube 影片 ID，請確認您正在瀏覽 YouTube 影片頁面。' });
      return;
    }

    changeState(AppState.CHECKING_CACHE, { videoId });

    // 首先嘗試獲取既有地點
    try {
      const locations = await getVideoLocations(videoId);

      if (locations) {
        // 有快取結果，直接顯示
        changeState(AppState.MAP_READY, { mapVisualization: locations });
        return;
      }
    } catch (error) {
      console.error('Check cache error:', error);
      // 快取檢查失敗，繼續嘗試分析
    }

    // 沒有快取，提交分析請求
    const videoUrl = `https://www.youtube.com/watch?v=${videoId}`;
    const response = await submitAnalysis(videoUrl);

    if (response.cached) {
      // 快取命中，但前一步未能獲取到地點資料
      // 嘗試再次獲取
      try {
        const locations = await getVideoLocations(videoId);

        if (locations) {
          changeState(AppState.MAP_READY, { mapVisualization: locations });
          return;
        }
      } catch (error) {
        console.error('Get locations after cache hit error:', error);
      }
    }

    // 設置分析中狀態
    changeState(AppState.ANALYZING, {
      jobId: response.job_id,
      progress: 0,
      phase: response.phase || null
    });

    // 啟動 SSE 監聽
    startEventListener(response.job_id);

  } catch (error) {
    console.error('Start analysis error:', error);
    changeState(AppState.ERROR, { error: `分析請求失敗: ${error.message}` });
  }
}

/**
 * 啟動事件監聽
 * @param {string} jobId - 任務 ID
 */
function startEventListener(jobId) {
  // 通知 service worker 開始監聽
  chrome.runtime.sendMessage({
    type: 'startListeningEvents',
    jobId
  }, (response) => {
    if (!response || !response.success) {
      console.error('Failed to start event listener');
    }
  });
}

/**
 * 停止事件監聽
 */
function stopEventListener() {
  if (state.jobId) {
    chrome.runtime.sendMessage({
      type: 'stopListeningEvents',
      jobId: state.jobId
    });
    // 停止任何可能的輪詢備援
    stopPolling();
    state.jobId = null;
  }
}

// Polling fallback
let pollingIntervalId = null;
const POLLING_INTERVAL_MS = (typeof TRAILTAG_CONFIG !== 'undefined' && TRAILTAG_CONFIG.POLLING_INTERVAL_MS) ? TRAILTAG_CONFIG.POLLING_INTERVAL_MS : 2500; // 2.5s

async function pollJobStatus(jobId) {
  try {
    const status = await getJobStatus(jobId);

    if (!status) return;

    if (status.progress != null) {
      changeState(AppState.ANALYZING, { progress: status.progress, phase: status.phase || state.phase });
    }

    if (status.status === 'completed' || status.status === 'done') {
      // 任務完成
      stopPolling();
      handleJobCompleted();
    } else if (status.status === 'failed' || status.status === 'error') {
      stopPolling();
      changeState(AppState.ERROR, { error: status.message || 'Job failed' });
    }
  } catch (error) {
    console.error('Polling job status error:', error);
  }
}

function startPolling(jobId) {
  stopPolling();
  pollingIntervalId = setInterval(() => pollJobStatus(jobId), POLLING_INTERVAL_MS);
  console.log('Started polling for job:', jobId);
}

function stopPolling() {
  if (pollingIntervalId) {
    clearInterval(pollingIntervalId);
    pollingIntervalId = null;
    console.log('Stopped polling');
  }
}

/**
 * 處理任務完成事件
 */
async function handleJobCompleted() {
  try {
    // 獲取最終地點資料
    const locations = await getVideoLocations(state.videoId);

    if (locations) {
      changeState(AppState.MAP_READY, { mapVisualization: locations });
    } else {
      throw new Error('無法獲取地點資料');
    }
  } catch (error) {
    console.error('Handle job completed error:', error);
    changeState(AppState.ERROR, { error: `獲取地點資料失敗: ${error.message}` });
  }
}

/**
 * 導出 GeoJSON
 */
function exportGeoJSON() {
  if (!state.mapVisualization || !state.videoId) {
    console.error('No map visualization or video ID available');
    return;
  }

  const geoJSON = generateGeoJSON(state.mapVisualization);
  downloadGeoJSON(geoJSON, state.videoId);
}

/**
 * 初始化應用
 */
async function initializeApp() {
  // 載入先前的狀態
  const savedState = await loadState();

  if (savedState) {
    state = { ...state, ...savedState };
  }

  // 獲取當前影片 ID
  const currentVideoId = await getCurrentVideoId();

  // 檢查是否是 YouTube 影片頁
  const isVideoPage = !!currentVideoId;

  if (!isVideoPage) {
    changeState(AppState.ERROR, { error: '請在 YouTube 影片頁面使用此擴充功能。' });
    return;
  }

  // 如果狀態很舊或影片 ID 不同，重置狀態
  const isStateStale = (Date.now() - state.lastUpdated) > 1000 * 60 * 60; // 1 小時
  const isVideoChanged = currentVideoId !== state.videoId;

  if (isStateStale || isVideoChanged || !state.videoId) {
    changeState(AppState.IDLE, { videoId: currentVideoId });
  } else {
    // 如果有進行中的分析，恢復 SSE 監聽
    if (state.currentState === AppState.ANALYZING && state.jobId) {
      startEventListener(state.jobId);
    }

    // 如果已經有地圖數據，確保狀態正確
    if (state.mapVisualization && state.currentState !== AppState.MAP_READY) {
      changeState(AppState.MAP_READY);
    }

    updateUI();
  }
}

// 處理來自 service worker 的事件訊息
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // 確認訊息來自 service worker
  if (sender.id !== chrome.runtime.id) return;

  switch (message.type) {
    case 'phase_update':
      if (state.currentState === AppState.ANALYZING && state.jobId === message.jobId) {
        changeState(AppState.ANALYZING, {
          progress: message.data.progress || state.progress,
          phase: message.data.phase || state.phase
        });
      }
      break;

    case 'completed':
      if (state.currentState === AppState.ANALYZING && state.jobId === message.jobId) {
        handleJobCompleted();
      }
      break;

    case 'error':
      if (state.currentState === AppState.ANALYZING && state.jobId === message.jobId) {
        changeState(AppState.ERROR, { error: message.data.message || '未知錯誤' });
      }
      break;
    case 'sse_fallback':
      // Service worker 通知 SSE 已失敗，啟動輪詢作為備援
      if (state.currentState === AppState.ANALYZING && state.jobId === message.jobId) {
        console.warn('SSE fallback received, starting polling for job:', message.jobId);
        // prefer test-overridable window.startPolling when available
        if (typeof window !== 'undefined' && typeof window.startPolling === 'function') {
          window.startPolling(message.jobId);
        } else {
          startPolling(message.jobId);
        }
      }
      break;
  }

  sendResponse({ received: true });
});

// 註冊按鈕事件處理器
document.addEventListener('DOMContentLoaded', () => {
  // 分析按鈕
  elements.analyzeBtn.addEventListener('click', startAnalysis);

  // 取消按鈕
  elements.cancelBtn.addEventListener('click', () => {
    stopEventListener();
    changeState(AppState.IDLE);
  });

  // 重試按鈕
  elements.retryBtn.addEventListener('click', startAnalysis);

  // 匯出按鈕
  elements.exportBtn.addEventListener('click', exportGeoJSON);

  // 初始化
  initializeApp();

  // 每 N 秒保活 service worker (可由 config 覆寫)
  setInterval(() => {
    chrome.runtime.sendMessage({ type: 'keepAlive' });
  }, (typeof TRAILTAG_CONFIG !== 'undefined' && TRAILTAG_CONFIG.KEEPALIVE_MS) ? TRAILTAG_CONFIG.KEEPALIVE_MS : 30000);
});

// If test harness is present, register small helpers without polluting production globals
try {
  if (typeof window !== 'undefined' && typeof window.__registerPopupTestingHelpers === 'function') {
    window.__registerPopupTestingHelpers({
      setState: (patch) => Object.assign(state, patch),
      getState: () => state,
      startPolling,
      stopPolling
    });
    // also expose some functions on window for easier spying in tests
    try {
      window.startPolling = startPolling;
      window.stopPolling = stopPolling;
      window.startAnalysis = startAnalysis;
      window.stopEventListener = stopEventListener;
      window.changeState = changeState;
      window.exportGeoJSON = exportGeoJSON;
    } catch (e) {
      // ignore
    }
  }
} catch (e) {
  // noop
}
