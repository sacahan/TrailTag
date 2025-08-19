/**
 * utils.ts - 常用工具函式（TypeScript 輕量轉換版）
 *
 * 此檔案保留較寬鬆的型別以維持與既有程式的相容性。
 * 註解皆為正體中文，說明每個匯出的函式用途與邊界情況。
 */
/**
 * 從 YouTube URL 提取 video_id
 * - 支援一般 watch 連結與短連結（youtu.be）以及 embed/v 路徑
 * - 若未匹配成功回傳 null
 *
 * @param url YouTube 影片 URL
 * @returns video id 或 null
 */
export function extractVideoId(url) {
    if (!url)
        return null;
    // 支援常見的幾種 pattern
    const patterns = [
        /(?:v=|\/)([0-9A-Za-z_-]{11}).*/,
        /(?:embed\/|v\/|youtu\.be\/)([0-9A-Za-z_-]{11})/
    ];
    for (const pattern of patterns) {
        const match = url.match(pattern);
        if (match)
            return match[1];
    }
    return null;
}
/**
 * 檢查網址是否為 YouTube 影片頁
 * @param url 可能的 URL
 * @returns 是否為 YouTube 影片頁
 */
export function isYouTubeVideoPage(url) {
    if (!url)
        return false;
    return url.includes('youtube.com/watch') || url.includes('youtu.be/');
}
/**
 * 取得目前分頁的 YouTube video id（若在 extension 環境可用）
 * - 使用 chrome.tabs.query 取得目前分頁，並在 1s 超時後回傳 null
 * - 會處理 chrome.runtime.lastError 與各種失敗情況
 */
export async function getCurrentVideoId() {
    return new Promise((resolve) => {
        if (typeof chrome === 'undefined' || !chrome.tabs || !chrome.tabs.query) {
            console.warn('chrome.tabs.query is not available in this context');
            resolve(null);
            return;
        }
        let settled = false;
        const timeout = setTimeout(() => {
            if (!settled) {
                settled = true;
                console.warn('getCurrentVideoId timed out');
                resolve(null);
            }
        }, 1000);
        try {
            chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
                if (settled)
                    return;
                if (chrome.runtime && chrome.runtime.lastError) {
                    console.error('chrome.runtime.lastError in getCurrentVideoId:', chrome.runtime.lastError);
                    settled = true;
                    clearTimeout(timeout);
                    resolve(null);
                    return;
                }
                if (!tabs || !tabs[0] || !tabs[0].url) {
                    settled = true;
                    clearTimeout(timeout);
                    resolve(null);
                    return;
                }
                const url = tabs[0].url;
                if (!url.includes('youtube.com/watch') && !url.includes('youtu.be/')) {
                    settled = true;
                    clearTimeout(timeout);
                    resolve(null);
                    return;
                }
                try {
                    const videoId = extractVideoId(url);
                    settled = true;
                    clearTimeout(timeout);
                    resolve(videoId);
                }
                catch (e) {
                    console.error('extractVideoId threw error:', e);
                    settled = true;
                    clearTimeout(timeout);
                    resolve(null);
                }
            });
        }
        catch (err) {
            console.error('Exception calling chrome.tabs.query:', err);
            if (!settled) {
                settled = true;
                clearTimeout(timeout);
                resolve(null);
            }
        }
    });
}
/**
 * 將時間碼格式化為人類可讀形式
 * - 支援 H:MM:SS、MM:SS 與純秒數字串
 */
export function formatTimecode(timecode) {
    if (!timecode)
        return '';
    const cleanTime = timecode.split(',')[0];
    const parts = cleanTime.split(':');
    if (parts.length === 3) {
        const hours = parseInt(parts[0]);
        const minutes = parseInt(parts[1]);
        const seconds = parseInt(parts[2]);
        if (hours > 0) {
            return hours + ':' + minutes.toString().padStart(2, '0') + ':' + seconds.toString().padStart(2, '0');
        }
        else {
            return minutes + ':' + seconds.toString().padStart(2, '0');
        }
    }
    if (parts.length === 2) {
        const minutes = parseInt(parts[0]);
        const seconds = parseInt(parts[1]);
        return minutes + ':' + seconds.toString().padStart(2, '0');
    }
    return timecode;
}
/**
 * 生成 YouTube 時間碼連結（v=VIDEO_ID&t=Ns）
 * - 若輸入無效則回傳空字串
 */
export function createTimecodeUrl(videoId, timecode) {
    if (!videoId || !timecode)
        return '';
    const parts = timecode.split(',')[0].split(':');
    let seconds = 0;
    if (parts.length === 3) {
        seconds = parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseInt(parts[2]);
    }
    else if (parts.length === 2) {
        seconds = parseInt(parts[0]) * 60 + parseInt(parts[1]);
    }
    else if (parts.length === 1) {
        seconds = parseInt(parts[0]);
    }
    return 'https://www.youtube.com/watch?v=' + videoId + '&t=' + seconds + 's';
}
/**
 * 驗證 video id 格式（長度 11，允許字母、數字、_ 和 -）
 */
export function isValidVideoId(videoId) {
    return /^[0-9A-Za-z_-]{11}$/.test(videoId);
}
/**
 * 將狀態儲存到 chrome.storage.local（若無 chrome 則為 noop）
 */
export function saveState(state) {
    try {
        const payload = {
            videoId: state?.videoId || null,
            jobId: state?.jobId || null,
            currentState: state?.currentState || null,
            progress: state?.progress || 0,
            phase: state?.phase || null,
            timestamp: Date.now(),
        };
        // Prefer chrome.storage.local when available
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
            return new Promise((resolve) => {
                try {
                    chrome.storage.local.set({ trailtag_state_v1: payload }, () => resolve());
                }
                catch (e) {
                    // ignore failures when chrome.storage is not usable
                    resolve();
                }
            });
        }
        // if chrome.storage.local is not available, noop (no persistent fallback)
    }
    catch (e) { }
    return Promise.resolve();
}
/**
 * 從 chrome.storage.local 讀取先前儲存的狀態，若不可用回傳 null
 */
export function loadState() {
    return new Promise((resolve) => {
        try {
            if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                try {
                    chrome.storage.local.get(['trailtag_state_v1'], (res) => {
                        const val = res && res.trailtag_state_v1 ? res.trailtag_state_v1 : null;
                        if (!val)
                            return resolve(null);
                        const ttl = (typeof TRAILTAG_CONFIG !== 'undefined' && TRAILTAG_CONFIG.STATE_TTL_MS != null) ? TRAILTAG_CONFIG.STATE_TTL_MS : 30 * 60 * 1000;
                        if (val.timestamp && Date.now() - val.timestamp > ttl)
                            return resolve(null);
                        return resolve(val);
                    });
                    return;
                }
                catch (e) {
                    // if chrome.storage get throws, treat as unavailable
                }
            }
        }
        catch (e) { }
        // chrome.storage.local not available or failed => no persisted state
        return resolve(null);
    });
}
// attach to global for legacy usage
try {
    if (typeof window !== 'undefined') {
        window.TrailTag = window.TrailTag || {};
        window.TrailTag.Utils = Object.assign(window.TrailTag.Utils || {}, {
            extractVideoId,
            getCurrentVideoId,
            isYouTubeVideoPage,
            formatTimecode,
            createTimecodeUrl,
            isValidVideoId,
            saveState,
            loadState
        });
        if (!window.getCurrentVideoId)
            window.getCurrentVideoId = window.TrailTag.Utils.getCurrentVideoId;
        if (!window.formatTimecode)
            window.formatTimecode = window.TrailTag.Utils.formatTimecode;
        if (!window.loadState)
            window.loadState = window.TrailTag.Utils.loadState;
        if (!window.saveState)
            window.saveState = window.TrailTag.Utils.saveState;
        if (!window.extractVideoId)
            window.extractVideoId = window.TrailTag.Utils.extractVideoId;
    }
}
catch (e) { }
export default null;
