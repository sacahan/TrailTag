/**
 * 工具函數模組
 */

/**
 * 從 YouTube URL 提取 video_id
 * @param {string} url - YouTube 影片 URL
 * @returns {string|null} 提取到的 video_id 或 null
 */
function extractVideoId(url) {
  if (!url) return null;

  // 支援多種 YouTube URL 格式
  const patterns = [
    /(?:v=|\/)([0-9A-Za-z_-]{11}).*/, // youtube.com/watch?v=XXX 或 youtu.be/XXX
    /(?:embed\/|v\/|youtu\.be\/)([0-9A-Za-z_-]{11})/, // youtube.com/embed/XXX
  ];

  for (const pattern of patterns) {
    const match = url.match(pattern);
    if (match) return match[1];
  }

  return null;
}

/**
 * 從目前瀏覽的頁面 URL 取得 YouTube video_id（如果是 YouTube 影片頁）
 * @returns {Promise<string|null>} 提取到的 video_id 或 null
 */
async function getCurrentVideoId() {
  return new Promise((resolve) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs || !tabs[0] || !tabs[0].url) {
        resolve(null);
        return;
      }

      const url = tabs[0].url;
      if (!url.includes('youtube.com/watch') && !url.includes('youtu.be/')) {
        resolve(null);
        return;
      }

      const videoId = extractVideoId(url);
      resolve(videoId);
    });
  });
}

/**
 * 檢查當前頁面是否為 YouTube 影片頁
 * @returns {Promise<boolean>}
 */
async function isYouTubeVideoPage() {
  const videoId = await getCurrentVideoId();
  return !!videoId;
}

/**
 * 將時間碼格式化為人類易讀的形式
 * @param {string} timecode - 時間碼 (hh:mm:ss 或 hh:mm:ss,mmm 格式)
 * @returns {string} 格式化後的時間碼
 */
function formatTimecode(timecode) {
  if (!timecode) return '';

  // 移除毫秒部分
  const cleanTime = timecode.split(',')[0];
  const parts = cleanTime.split(':');

  // 僅顯示分與秒
  if (parts.length === 3) {
    const hours = parseInt(parts[0]);
    const minutes = parseInt(parts[1]);
    const seconds = parseInt(parts[2]);

    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    } else {
      return `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }
  }

  return timecode;
}

/**
 * 生成 YouTube 時間碼 URL
 * @param {string} videoId - YouTube video_id
 * @param {string} timecode - 時間碼 (hh:mm:ss 或 hh:mm:ss,mmm 格式)
 * @returns {string} 包含時間碼的 YouTube URL
 */
function createTimecodeUrl(videoId, timecode) {
  if (!videoId || !timecode) return '';

  // 轉換為秒數
  const parts = timecode.split(':');
  let seconds = 0;

  if (parts.length === 3) {
    // hh:mm:ss 格式
    seconds = parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseInt(parts[2]);
  } else if (parts.length === 2) {
    // mm:ss 格式
    seconds = parseInt(parts[0]) * 60 + parseInt(parts[1]);
  } else if (parts.length === 1) {
    // 純秒數
    seconds = parseInt(parts[0]);
  }

  return `https://www.youtube.com/watch?v=${videoId}&t=${seconds}s`;
}

/**
 * 檢查字串是否為有效的 YouTube video_id
 * @param {string} videoId - 要檢查的 video_id
 * @returns {boolean} 是否有效
 */
function isValidVideoId(videoId) {
  return /^[0-9A-Za-z_-]{11}$/.test(videoId);
}

/**
 * 將 state 保存到 Chrome 儲存空間
 * @param {Object} state - 要保存的狀態
 * @returns {Promise<void>}
 */
function saveState(state) {
  return new Promise((resolve) => {
    chrome.storage.local.set({ trailtag_state: state }, resolve);
  });
}

/**
 * 從 Chrome 儲存空間讀取 state
 * @returns {Promise<Object|null>} 讀取到的狀態或 null
 */
function loadState() {
  return new Promise((resolve) => {
    chrome.storage.local.get('trailtag_state', (result) => {
      resolve(result.trailtag_state || null);
    });
  });
}
