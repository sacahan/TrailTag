/**
 * TrailTag 運行時配置
 *
 * 此檔案由 inject-config.mjs 在建制時自動生成
 * 請勿手動修改此檔案
 *
 * 生成時間: 2025-09-05T10:38:46.576Z
 */

// ES module 格式的配置匯出
const TRAILTAG_CONFIG = {
  API_BASE_URL: "http://localhost:8010",
  FETCH_RETRIES: 2,
  FETCH_BACKOFF_MS: 500,
  MAX_RECONNECT: 1,
  POLLING_INTERVAL_MS: 5000,
  KEEPALIVE_MS: 30000,
  STATE_TTL_MS: 1800000,
};

// 全域配置物件，供 api.ts 和其他模組使用
if (typeof window !== "undefined") {
  window.TRAILTAG_CONFIG = TRAILTAG_CONFIG;
}

// 同時將配置掛載到 globalThis，支援 Worker 環境
if (typeof globalThis !== "undefined") {
  globalThis.TRAILTAG_CONFIG = TRAILTAG_CONFIG;
}

// 如果在 ServiceWorker 環境中，將配置掛載到 self
if (typeof self !== "undefined" && typeof window === "undefined") {
  self.TRAILTAG_CONFIG = TRAILTAG_CONFIG;
}

export default TRAILTAG_CONFIG;
