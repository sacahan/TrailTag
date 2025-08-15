/*
  TrailTag 擴充功能的集中設定檔 (centralized configuration)

  說明：
  - 在此定義預設值（DEFAULTS）。在測試或執行期間，可以透過在評估此檔案之前
    設定 `window.__TRAILTAG_CONFIG__`（popup / 測試）或 `self.__TRAILTAG_CONFIG__`（service worker）
    來覆寫預設值，或之後呼叫 `updateTrailTagConfig()` 進行動態更新。
  - 此檔採即時快照（snapshot）方式暴露 `TRAILTAG_CONFIG`，並提供 `updateTrailTagConfig`
    用以合併補丁（patch）並重建快照。

  注意：此檔以立即函式 (IIFE) 包裝以避免污染全域命名空間，且在不同執行環境
  (window / service worker) 中皆能運作。
*/
(function(){
  // 預設設定項目
  const DEFAULTS = {
    // API 基礎 URL（開發預設指向本機）
    API_BASE_URL: 'http://localhost:8010',
    // fetch 重試策略
    FETCH_RETRIES: 2,
    FETCH_BACKOFF_MS: 500,
    // service worker 的 SSE 最大重連次數（應由後端與前端協調）
    MAX_RECONNECT: 1,
    // popup 端的輪詢與 keepalive 設定
    POLLING_INTERVAL_MS: 2500,
    KEEPALIVE_MS: 30000
  };

  /**
   * 從可能的全域覆寫來源合併設定
   * - 優先順序：DEFAULTS <- window.__TRAILTAG_CONFIG__ <- self.__TRAILTAG_CONFIG__
   * - 目的是在不同執行環境（popup、測試、service worker）都能簡單覆寫設定
   *
   * @returns {Object} 合併後的設定物件
   */
  function resolveOverrides() {
    const fromWindow = (typeof window !== 'undefined' && window.__TRAILTAG_CONFIG__) ? window.__TRAILTAG_CONFIG__ : {};
    const fromSelf = (typeof self !== 'undefined' && self.__TRAILTAG_CONFIG__) ? self.__TRAILTAG_CONFIG__ : {};
    // 使用 Object.assign 以維持簡單的淺層合併行為
    return Object.assign({}, DEFAULTS, fromWindow, fromSelf);
  }

  // 建立一個快照，後續會將此快照暴露在對應的執行上下文中
  const cfg = resolveOverrides();

  // 暴露於 window（popup / 測試環境）
  if (typeof window !== 'undefined') {
    // TRAILTAG_CONFIG 作為不可直接修改的快照，方便其他模組直接讀取
    window.TRAILTAG_CONFIG = cfg;
    // updateTrailTagConfig 可用於動態 patch 設定，會寫入 __TRAILTAG_CONFIG__ 並重新解析快照
    window.updateTrailTagConfig = (patch) => {
      window.__TRAILTAG_CONFIG__ = Object.assign({}, window.__TRAILTAG_CONFIG__ || {}, patch);
      window.TRAILTAG_CONFIG = resolveOverrides();
      return window.TRAILTAG_CONFIG;
    };
  }

  // 暴露於 service worker 或其他 worker 環境
  if (typeof self !== 'undefined') {
    self.TRAILTAG_CONFIG = cfg;
    self.updateTrailTagConfig = (patch) => {
      self.__TRAILTAG_CONFIG__ = Object.assign({}, self.__TRAILTAG_CONFIG__ || {}, patch);
      self.TRAILTAG_CONFIG = resolveOverrides();
      return self.TRAILTAG_CONFIG;
    };
  }
})();
