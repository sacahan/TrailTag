/**
 * API 呼叫模組
 *
 * 此檔案包含與後端 API 溝通的 helper 函式（包含 retry 邏輯）、
 * SSE 連線建構，以及將取得的地點資料產生與下載為 GeoJSON 的工具函式。
 */

// 嘗試在各種執行環境中同步取得設定（模組、window 或 service worker）
function getConfigSync() {
  // 全域常數優先（在一些測試或打包環境會直接注入 TRAILTAG_CONFIG）
  if (typeof TRAILTAG_CONFIG !== 'undefined') return TRAILTAG_CONFIG;
  // 瀏覽器環境下從 window 取得
  if (typeof window !== 'undefined' && window.TRAILTAG_CONFIG) return window.TRAILTAG_CONFIG;
  // service worker / worker 環境下從 self 取得
  if (typeof self !== 'undefined' && self.TRAILTAG_CONFIG) return self.TRAILTAG_CONFIG;
  // 在某些測試環境中無法動態 import，回傳 null 表示使用預設值
  return null;
}

const _cfg = getConfigSync();
// API 基礎路徑 (可由外部 config 覆寫)，預設為本地開發伺服器
const API_BASE_URL = (_cfg && _cfg.API_BASE_URL) ? _cfg.API_BASE_URL : 'http://localhost:8010';

/**
 * 簡單的 fetch + retry wrapper
 *
 * 行為說明：
 * - 使用 fetch 執行請求
 * - 當遇到可重試的錯誤（HTTP 5xx 或 429）時，會根據指定位數進行指數回退並重試
 * - 非重試性錯誤（例如 4xx）會直接回傳 response，呼叫端可依需要處理
 *
 * @param {string} url
 * @param {Object} options
 * @param {number} retries - 最大重試次數
 * @param {number} backoffMs - 初始回退毫秒數（指數倍增）
 * @returns {Promise<Response>} fetch 回傳的 Response 物件
 */
async function fetchWithRetry(url, options = {}, retries = (typeof TRAILTAG_CONFIG !== 'undefined' ? TRAILTAG_CONFIG.FETCH_RETRIES : 2), backoffMs = (typeof TRAILTAG_CONFIG !== 'undefined' ? TRAILTAG_CONFIG.FETCH_BACKOFF_MS : 500)) {
  let attempt = 0;
  while (true) {
    try {
      const res = await fetch(url, options);
      // Treat 5xx as retryable, 429 as retryable, 4xx as non-retryable
      if (!res.ok) {
        // 5xx 與 429 被視為可重試
        if ((res.status >= 500 && res.status < 600) || res.status === 429) {
          throw new Error(`Retryable API error: ${res.status} ${res.statusText}`);
        }
      }
      // 正常或非重試性錯誤都回傳 Response，由呼叫端決定如何處理 body
      return res;
    } catch (err) {
      attempt += 1;
      // 超過重試次數時拋出錯誤
      if (attempt > retries) throw err;
      // 增加一些隨機 jitter，避免多個客戶端同時重試造成洪峰
      const jitter = Math.floor(Math.random() * 200);
      const wait = backoffMs * Math.pow(2, attempt - 1) + jitter;
      console.warn(`Fetch attempt ${attempt} failed for ${url}, retrying in ${wait}ms`);
      await new Promise(r => setTimeout(r, wait));
    }
  }
}

/**
 * 發送影片分析請求
 *
 * @param {string} videoUrl - YouTube 影片 URL
 * @returns {Promise<Object>} - 解析後的 JSON 物件（通常包含 job_id 與初步狀態）
 * @throws 當 fetch 或 API 回傳錯誤時會拋出
 */
async function submitAnalysis(videoUrl) {
  try {
    const response = await fetchWithRetry(`${API_BASE_URL}/api/videos/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url: videoUrl }),
    }, 2, 500);

    if (!response.ok) {
      // 非 2xx 回傳視為錯誤並拋出，呼叫端可以捕捉並顯示錯誤訊息
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Submit analysis error:', error);
    throw error;
  }
}

/**
 * 取得任務狀態
 *
 * @param {string} jobId - 任務 ID
 * @returns {Promise<Object>} - 任務狀態的 JSON 物件
 */
async function getJobStatus(jobId) {
  try {
    const response = await fetchWithRetry(`${API_BASE_URL}/api/jobs/${jobId}`, {}, 2, 500);
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Get job status error:', error);
    throw error;
  }
}

/**
 * 取得影片對應的地點資料
 *
 * @param {string} videoId - YouTube video_id
 * @returns {Promise<Object|null>} - 若尚未分析會回傳 null，否則回傳地點陣列的 JSON
 */
async function getVideoLocations(videoId) {
  try {
    const response = await fetchWithRetry(`${API_BASE_URL}/api/videos/${videoId}/locations`, {}, 2, 500);

    if (response.status === 404) {
      // 404 表示伺服器尚未有分析結果，回傳 null 由 UI 決定下一步行為
      return null;
    }

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Get video locations error:', error);
    throw error;
  }
}

/**
 * 建立 SSE (Server-Sent Events) 連線來監聽後端任務事件
 *
 * 提供一個簡單的事件監聽器註冊介面，會將後端送來的事件解析為 JSON
 * 並呼叫對應的回呼函式。若接收到完成或錯誤事件，會自動關閉連線。
 *
 * @param {string} jobId - 任務 ID
 * @param {Object} callbacks - 回呼物件，包含 onPhaseUpdate, onCompleted, onError
 * @returns {{close: Function}} - 回傳一個可關閉連線的物件
 */
function connectToEventStream(jobId, callbacks) {
  const eventSource = new EventSource(`${API_BASE_URL}/api/jobs/${jobId}/stream`);

  // 階段更新事件
  eventSource.addEventListener('phase_update', (event) => {
    try {
      const data = JSON.parse(event.data);
      callbacks.onPhaseUpdate?.(data);
    } catch (error) {
      console.error('Parse phase_update error:', error);
    }
  });

  // 完成事件，收到後關閉連線
  eventSource.addEventListener('completed', (event) => {
    try {
      const data = JSON.parse(event.data);
      callbacks.onCompleted?.(data);
      eventSource.close();
    } catch (error) {
      console.error('Parse completed error:', error);
    }
  });

  // 錯誤事件，嘗試解析錯誤內容再關閉連線
  eventSource.addEventListener('error', (event) => {
    try {
      const data = event.data ? JSON.parse(event.data) : { message: 'Unknown error' };
      callbacks.onError?.(data);
      eventSource.close();
    } catch (error) {
      console.error('Parse error event error:', error);
      callbacks.onError?.({ message: 'Error parsing error event' });
    }
  });

  // 心跳事件用於保持連線活性（伺服器端可選發）
  eventSource.addEventListener('heartbeat', (event) => {
    console.debug('>>> Heartbeat received');
  });

  // 當 EventSource 本身發生錯誤時的處理
  eventSource.onerror = (error) => {
    console.error('EventSource error:', error);
    callbacks.onError?.({ message: 'Connection error' });
    eventSource.close();
  };

  return {
    close: () => eventSource.close(),
  };
}

/**
 * 將視覺化地點資料轉為 GeoJSON
 *
 * 假設輸入的 mapVisualization.routes 為陣列，每個 route 至少包含 coordinates
 *（[lon, lat]）與 location 字段；只會將有有效座標的項目轉為 Point feature。
 *
 * @param {Object} mapVisualization - 包含 routes 與 video_id
 * @returns {Object} GeoJSON FeatureCollection
 */
function generateGeoJSON(mapVisualization) {
  const features = mapVisualization.routes
    .filter(route => Array.isArray(route.coordinates) && route.coordinates.length === 2)
    .map(route => ({
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [route.coordinates[0], route.coordinates[1]], // [lon, lat]
      },
      properties: {
        name: route.location,
        description: route.description || '',
        timecode: route.timecode || '',
        tags: route.tags || [],
        marker: route.marker || 'default',
      },
    }));

  return {
    type: 'FeatureCollection',
    features,
    properties: {
      video_id: mapVisualization.video_id,
      generated_at: new Date().toISOString(),
    },
  };
}

/**
 * 下載 GeoJSON 檔案供使用者保存
 *
 * @param {Object} geoJSON - GeoJSON 物件
 * @param {string} videoId - 用於檔名的 video id
 */
function downloadGeoJSON(geoJSON, videoId) {
  // 使用 Blob 與 createObjectURL 生成可下載連結，並自動觸發下載
  const blob = new Blob([JSON.stringify(geoJSON, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = `trailtag-${videoId}.geojson`;
  a.click();

  // 釋放物件 URL
  URL.revokeObjectURL(url);
}
