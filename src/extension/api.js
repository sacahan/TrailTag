/**
 * API 呼叫模組
 */

// API 基礎路徑
const API_BASE_URL = 'http://localhost:8000';

/**
 * 發送分析請求
 * @param {string} videoUrl - YouTube 影片 URL
 * @returns {Promise<Object>} - 回應物件，包含 job_id 與狀態
 */
async function submitAnalysis(videoUrl) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/videos/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url: videoUrl }),
    });

    if (!response.ok) {
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
 * @param {string} jobId - 任務 ID
 * @returns {Promise<Object>} - 回應物件，包含任務狀態
 */
async function getJobStatus(jobId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`);

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
 * 取得影片地點
 * @param {string} videoId - YouTube video_id
 * @returns {Promise<Object>} - 回應物件，包含地點列表
 */
async function getVideoLocations(videoId) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/videos/${videoId}/locations`);

    if (response.status === 404) {
      // 特殊處理 404 - 代表尚未有分析結果
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
 * 建立 SSE 連線，取得事件
 * @param {string} jobId - 任務 ID
 * @param {Object} callbacks - 回呼函數物件：
 *   @param {Function} callbacks.onPhaseUpdate - 階段更新回呼
 *   @param {Function} callbacks.onCompleted - 完成回呼
 *   @param {Function} callbacks.onError - 錯誤回呼
 */
function connectToEventStream(jobId, callbacks) {
  const eventSource = new EventSource(`${API_BASE_URL}/api/jobs/${jobId}/stream`);

  eventSource.addEventListener('phase_update', (event) => {
    try {
      const data = JSON.parse(event.data);
      callbacks.onPhaseUpdate?.(data);
    } catch (error) {
      console.error('Parse phase_update error:', error);
    }
  });

  eventSource.addEventListener('completed', (event) => {
    try {
      const data = JSON.parse(event.data);
      callbacks.onCompleted?.(data);
      eventSource.close();
    } catch (error) {
      console.error('Parse completed error:', error);
    }
  });

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

  eventSource.addEventListener('heartbeat', (event) => {
    // 心跳事件，保持連線
    console.debug('Heartbeat received');
  });

  // 處理連線錯誤
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
 * 從地點資料生成 GeoJSON
 * @param {Object} mapVisualization - MapVisualization 物件
 * @returns {Object} GeoJSON 物件
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
 * 下載 GeoJSON 檔案
 * @param {Object} geoJSON - GeoJSON 物件
 * @param {string} videoId - YouTube video_id 用於檔名
 */
function downloadGeoJSON(geoJSON, videoId) {
  const blob = new Blob([JSON.stringify(geoJSON, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = `trailtag-${videoId}.geojson`;
  a.click();

  URL.revokeObjectURL(url);
}
