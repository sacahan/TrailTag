import config from './config.mjs';

/* Ambient globals used by extension runtime */
declare const chrome: any;
declare const TRAILTAG_CONFIG: any;
declare const self: any;

/**
 * 事件負載型別，phase_update 可能包含任意欄位
 */
type PhaseUpdatePayload = { [key: string]: any };

// 追蹤目前打開的 EventSource 與重試次數
const activeEventSources: Record<string, EventSource> = {};
const reconnectAttempts: Record<string, number> = {};

// 最大重連次數，可由全域 TRAILTAG_CONFIG 覆寫
const MAX_RECONNECT: number = (typeof (globalThis as any).TRAILTAG_CONFIG !== 'undefined' && (globalThis as any).TRAILTAG_CONFIG?.MAX_RECONNECT != null)
  ? (globalThis as any).TRAILTAG_CONFIG.MAX_RECONNECT
  : 1;

/**
 * 對指定 jobId 建立 SSE (EventSource) 連線並轉發事件到 background/runtime
 * - 會先讀取 config（包含從 chrome.storage 或 globalThis 覆寫的值）
 * - 處理 phase_update、completed、error 與 heartbeat 事件
 */
async function listenToJobEvents(jobId: string): Promise<void> {
  // 停止先前的 SSE 監聽（確保同 jobId 不重複監聽）
  stopListeningToJobEvents(jobId);

  // 解析設定來源，優先順序：內建 config <- globalThis.TRAILTAG_CONFIG <- chrome.storage
  // 1. 先讀取 chrome.storage 內 trailtag_config 與 api_base_url
  // 2. 合併 config、globalThis.TRAILTAG_CONFIG、storage 取得最終設定
  let resolvedConfig: Record<string, any> = {};
  try {
    const storageVal = await new Promise<Record<string, any>>((resolve) => {
      try {
        chrome.storage.local.get(['trailtag_config', 'api_base_url'], (res: any) => resolve(res || {}));
      } catch (e) {
        resolve({});
      }
    });

    resolvedConfig = Object.assign({}, (config as any) || {});

    if (typeof (globalThis as any) !== 'undefined' && (globalThis as any).TRAILTAG_CONFIG) {
      Object.assign(resolvedConfig, (globalThis as any).TRAILTAG_CONFIG);
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
    // 若解析失敗則回退使用預設 config
    resolvedConfig = (config as any) || {};
  }

  // 取得 API_BASE_URL，預設為 localhost:8010
  const API_BASE_URL = (resolvedConfig && (resolvedConfig as any).API_BASE_URL) || 'http://localhost:8010';

  // 建立 EventSource 連線並記錄於 activeEventSources
  const eventSource = new EventSource(`${API_BASE_URL}/api/jobs/${jobId}/stream`);
  activeEventSources[jobId] = eventSource;

  // phase_update 事件：解析並轉發給 runtime，並重置重試計數
  eventSource.addEventListener('phase_update', (event: MessageEvent) => {
    try {
      const data: PhaseUpdatePayload = JSON.parse((event as any).data);
      // 成功收到 phase_update 時重置重連計數
      if (reconnectAttempts[jobId]) reconnectAttempts[jobId] = 0;
      chrome.runtime.sendMessage({ type: 'phase_update', jobId, data });
    } catch (error) {
      console.error('Parse phase_update error:', error);
    }
  });

  // completed 事件：解析後通知 runtime 並關閉連線
  eventSource.addEventListener('completed', (event: MessageEvent) => {
    try {
      const data = JSON.parse((event as any).data);
      // 完成後移除重連計數並關閉 SSE
      if (reconnectAttempts[jobId]) delete reconnectAttempts[jobId];
      chrome.runtime.sendMessage({ type: 'completed', jobId, data });
      // clear persisted active job state to avoid stale restoration
      try {
        chrome.storage.local.get(['trailtag_state_v1'], (res: any) => {
          const val = res && res.trailtag_state_v1 ? res.trailtag_state_v1 : null;
          if (val && val.jobId === jobId) {
            chrome.storage.local.remove(['trailtag_state_v1'], () => { /* noop */ });
          }
        });
      } catch (e) { /* ignore */ }
      stopListeningToJobEvents(jobId);
    } catch (error) {
      console.error('Parse completed error:', error);
    }
  });

  // error 事件：嘗試關閉並根據重連策略重試，若超出則回報需要改用輪詢（fallback）
  eventSource.addEventListener('error', (event: Event) => {
    console.error('EventSource error for job', jobId, event);
    try { eventSource.close(); } catch (e) { /* ignore */ }
    delete activeEventSources[jobId];

    // 檢查重連次數，未達上限則延遲重試
    const attempts = reconnectAttempts[jobId] || 0;
    if (attempts < MAX_RECONNECT) {
      reconnectAttempts[jobId] = attempts + 1;
      // 計算重試延遲（指數退避 + 隨機抖動）
      const baseDelay = (typeof (globalThis as any).TRAILTAG_CONFIG !== 'undefined' && (globalThis as any).TRAILTAG_CONFIG?.FETCH_BACKOFF_MS)
        ? (globalThis as any).TRAILTAG_CONFIG.FETCH_BACKOFF_MS
        : 800;
      const jitter = Math.floor(Math.random() * 400);
      const wait = baseDelay * Math.pow(2, attempts) + jitter;
      console.log(`Attempting reconnect #${reconnectAttempts[jobId]} for job: ${jobId} (waiting ${wait}ms)`);
      setTimeout(() => { void listenToJobEvents(jobId); }, wait);
      return;
    }

    // 超出重試次數：通知前端改用輪詢
    chrome.runtime.sendMessage({ type: 'sse_fallback', jobId, data: { message: 'SSE connection failed, fallback to polling' } });
    delete reconnectAttempts[jobId];
  });

  // 心跳事件：可用於 debug 或確認連線存活
  eventSource.addEventListener('heartbeat', (event: Event) => {
    console.debug('Heartbeat received for job:', jobId);
  });
}

/**
 * 停止監聽指定 job 的 SSE 並清理狀態
 */
function stopListeningToJobEvents(jobId: string): void {
  const eventSource = activeEventSources[jobId];
  if (eventSource) {
    try { eventSource.close(); } catch (e) { /* ignore */ }
    delete activeEventSources[jobId];
    console.log(`Stopped listening to events for job: ${jobId}`);
  }
}

// 處理來自前端的開/關監聽請求
chrome.runtime.onMessage.addListener((message: any, sender: any, sendResponse: (resp: any) => void) => {
  if (message.type === 'startListeningEvents') {
    const { jobId, videoId } = message;
    // persist active job in storage so popup can query background for active job when opened
    try {
      const payload = { videoId: videoId || null, jobId: jobId || null, currentState: 'analyzing', timestamp: Date.now() };
      chrome.storage.local.set({ trailtag_state_v1: payload }, () => {
        void listenToJobEvents(jobId);
        sendResponse({ success: true });
      });
      return true; // indicate async response
    } catch (e) {
      // fallback: still start listening
      void listenToJobEvents(jobId);
      sendResponse({ success: false, error: e && e.message ? e.message : String(e) });
      return false;
    }
  }

  if (message.type === 'stopListeningEvents') {
    const { jobId } = message;
    stopListeningToJobEvents(jobId);
    // clear persisted active job if it matches
    try {
      chrome.storage.local.get(['trailtag_state_v1'], (res: any) => {
        const val = res && res.trailtag_state_v1 ? res.trailtag_state_v1 : null;
        if (val && val.jobId === jobId) {
          chrome.storage.local.remove(['trailtag_state_v1'], () => { sendResponse({ success: true }); });
        } else {
          sendResponse({ success: true });
        }
      });
      return true;
    } catch (e) {
      sendResponse({ success: false, error: e && e.message ? e.message : String(e) });
      return false;
    }
  }

  // 查詢目前是否有針對特定 videoId 的活動 job（由 popup 在 open 時詢問）
  if (message.type === 'getActiveJobForVideo') {
    const { videoId } = message;
    // 讀取已儲存的 state（若有）以找出正在分析的 job
    try {
      chrome.storage.local.get(['trailtag_state_v1'], (res: any) => {
        const val = res && res.trailtag_state_v1 ? res.trailtag_state_v1 : null;
        // If there's a stored entry for this video and it has a jobId, return it.
        // Be permissive about currentState: the popup may have saved a slightly
        // different state or background persisted it earlier. Returning the jobId
        // allows the popup to re-attach and recover UI state.
        if (val && val.videoId === videoId && val.jobId) {
              sendResponse({ jobId: val.jobId, currentState: val.currentState || 'analyzing' });
            } else {
              sendResponse({ jobId: null });
            }
      });
      return true; // indicate async response
    } catch (e) {
      sendResponse({ jobId: null });
      return false;
    }
  }
  return false;
});

// service worker life-cycle 事件（簡單紀錄）
self.addEventListener('activate', (event: Event) => {
  console.log('Service worker activated');
});

// 接收 keepAlive 訊息以維持 worker 活性（由 popup registerApp 發送）
self.addEventListener('message', (event: any) => {
  if (event.data && event.data.type === 'keepAlive') {
    console.log('Keeping service worker alive');
  }
});
