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

/**
 * 開始監聽任務事件
 * @param {string} jobId - 任務 ID
 */
function listenToJobEvents(jobId) {
  // 若已有連線，先關閉
  stopListeningToJobEvents(jobId);

  // API 基礎路徑 (實際整合時可能需要從 storage 或環境變數取得)
  const API_BASE_URL = 'http://localhost:8000';

  // 建立 EventSource
  const eventSource = new EventSource(`${API_BASE_URL}/api/jobs/${jobId}/stream`);

  // 儲存連線
  activeEventSources[jobId] = eventSource;

  // 處理階段更新事件
  eventSource.addEventListener('phase_update', (event) => {
    try {
      const data = JSON.parse(event.data);
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
    console.error('EventSource error:', event);

    // 轉發給 popup
    chrome.runtime.sendMessage({
      type: 'error',
      jobId,
      data: {
        message: 'Connection error'
      }
    });

    // 關閉連線
    stopListeningToJobEvents(jobId);
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
