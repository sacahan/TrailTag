/*
  TrailTag (ES module) 的設定預設值

  說明：
  - 此檔提供一組預設配置 (DEFAULTS)，以及一個輔助函式 `resolveConfig`
    用於合併使用者提供的覆寫 (overrides) 與預設值。
  - `DEFAULTS` 僅為淺層設定（shallow）且適用於在 popup、service worker、或測試中
    當作起始配置。
*/
const DEFAULTS = {
    // API 基礎 URL（開發預設指向本地服務）
    API_BASE_URL: 'https://tailtag.brianhan.cc',
    // fetch 重試次數
    FETCH_RETRIES: 2,
    // fetch 起始回退時間（毫秒），實作可基於此做指數回退
    FETCH_BACKOFF_MS: 500,
    // service worker 使用的最大重連次數（SSE 等機制）
    MAX_RECONNECT: 1,
    // popup 端輪詢間隔（毫秒）
    POLLING_INTERVAL_MS: 2500,
    // keepalive 的時間窗（毫秒）
    KEEPALIVE_MS: 30000
};
/**
 * 解析最終配置
 *
 * 將 DEFAULTS 與使用者提供的 overrides 淺層合併，回傳一個新的物件。
 * 這是一個純函式 (pure function)，不會修改傳入的參數。
 *
 * @param {Object} [overrides={}] - 要覆寫的設定鍵值對（淺層合併）
 * @returns {Object} 合併後的新設定物件
 */
export function resolveConfig(overrides = {}) {
    return Object.assign({}, DEFAULTS, overrides);
}
// 預設匯出 DEFAULTS，方便不需覆寫時直接引用
export default DEFAULTS;
