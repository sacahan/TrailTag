import config from './config.mjs';

/**
 * Service Worker 背景腳本
 */

// 偵聽來自 popup 的訊息
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'startListeningEvents') {
    // 初始化 SSE 連線
    const { jobId } = message;
    listenToJobEvents(jobId);
    sendResponse({ success: true });
    return true; // 表示將非同步回應
  }

  if (message.type === 'stopListeningEvents') {
    // 停止 SSE 連線
    const { jobId } = message;
    stopListeningToJobEvents(jobId);
    sendResponse({ success: true });
    return true;
  }
});

// 活躍的 EventSource 連線
const activeEventSources = {};
// 重連計數
const reconnectAttempts = {};
const MAX_RECONNECT = (typeof TRAILTAG_CONFIG !== 'undefined' && TRAILTAG_CONFIG.MAX_RECONNECT != null) ? TRAILTAG_CONFIG.MAX_RECONNECT : 1;

/**
 * 開始監聽任務事件
 * @param {string} jobId - 任務 ID
 */
async function listenToJobEvents(jobId) {
  // 若已有連線，先關閉
  stopListeningToJobEvents(jobId);
  // 先嘗試從 storage 讀取設定（若有），再回退到 self.TRAILTAG_CONFIG 或 config.mjs
  let resolvedConfig = {};
  try {
    // read chrome.storage.local for 'trailtag_config' or 'api_base_url'
    const storageVal = await new Promise((resolve) => {
      try {
        chrome.storage.local.get(['trailtag_config', 'api_base_url'], (res) => resolve(res || {}));
      } catch (e) {
        resolve({});
      }
    });

    resolvedConfig = Object.assign({}, config || {});
    if (typeof self !== 'undefined' && self.TRAILTAG_CONFIG) {
      Object.assign(resolvedConfig, self.TRAILTAG_CONFIG);
    }

    if (storageVal) {
      if (storageVal.trailtag_config && typeof storageVal.trailtag_config === 'object') {
        Object.assign(resolvedConfig, storageVal.trailtag_config);
      }
      if (storageVal.api_base_url) {
        resolvedConfig.API_BASE_URL = storageVal.api_base_url;
      }
    }
  } catch (e) {
    resolvedConfig = config || {};
  }

  const API_BASE_URL = resolvedConfig.API_BASE_URL || 'http://localhost:8000';

  // 建立 EventSource
  const eventSource = new EventSource(`${API_BASE_URL}/api/jobs/${jobId}/stream`);

  // 儲存連線
  activeEventSources[jobId] = eventSource;

  // 處理階段更新事件
  eventSource.addEventListener('phase_update', (event) => {
    try {
      const data = JSON.parse(event.data);
  // reset reconnect attempts on successful data flow
  if (reconnectAttempts[jobId]) reconnectAttempts[jobId] = 0;
      // 轉發給 popup
      chrome.runtime.sendMessage({
        type: 'phase_update',
        jobId,
        data
      });
    } catch (error) {
      console.error('Parse phase_update error:', error);
    }
  });

  // 處理完成事件
  eventSource.addEventListener('completed', (event) => {
    try {
      const data = JSON.parse(event.data);
  if (reconnectAttempts[jobId]) delete reconnectAttempts[jobId];
      // 轉發給 popup
      chrome.runtime.sendMessage({
        type: 'completed',
        jobId,
        data
      });

      // 關閉連線
      stopListeningToJobEvents(jobId);
    } catch (error) {
      console.error('Parse completed error:', error);
    }
  });

  // 處理錯誤事件
  eventSource.addEventListener('error', (event) => {
    console.error('EventSource error for job', jobId, event);

    // 關閉目前連線並清理
    try { eventSource.close(); } catch (e) { /* ignore */ }
    delete activeEventSources[jobId];

    // 嘗試重連（有限次數）
    const attempts = reconnectAttempts[jobId] || 0;
    if (attempts < MAX_RECONNECT) {
      reconnectAttempts[jobId] = attempts + 1;
  const baseDelay = (typeof TRAILTAG_CONFIG !== 'undefined' && TRAILTAG_CONFIG.FETCH_BACKOFF_MS) ? TRAILTAG_CONFIG.FETCH_BACKOFF_MS : 800;
      const jitter = Math.floor(Math.random() * 400);
      const wait = baseDelay * Math.pow(2, attempts) + jitter;
      console.log(`Attempting reconnect #${reconnectAttempts[jobId]} for job: ${jobId} (waiting ${wait}ms)`);
      setTimeout(() => {
        listenToJobEvents(jobId);
      }, wait);
      return;
    }

    // 若重試仍失敗，通知 popup 使用輪詢做為 fallback
    chrome.runtime.sendMessage({
      type: 'sse_fallback',
      jobId,
      data: { message: 'SSE connection failed, fallback to polling' }
    });

    // 清理重試計數
    delete reconnectAttempts[jobId];
  });

  // 處理心跳事件 (保持連線)
  eventSource.addEventListener('heartbeat', (event) => {
    console.debug('Heartbeat received for job:', jobId);
  });
}

/**
 * 停止監聽任務事件
 * @param {string} jobId - 任務 ID
 */
function stopListeningToJobEvents(jobId) {
  const eventSource = activeEventSources[jobId];
  if (eventSource) {
    eventSource.close();
    delete activeEventSources[jobId];
    console.log(`Stopped listening to events for job: ${jobId}`);
  }
}

// 監聽 service worker 啟動事件
self.addEventListener('activate', (event) => {
  console.log('Service worker activated');
});

// 確保 service worker 保持活躍
self.addEventListener('message', (event) => {
  // 處理保活訊息
  if (event.data && event.data.type === 'keepAlive') {
    console.log('Keeping service worker alive');
  }
});
