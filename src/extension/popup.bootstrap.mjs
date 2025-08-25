import defaults from "./config.mjs";

/*
 * popup.bootstrap.mjs
 *
 * Purpose: bootstrap popup environment using bundled defaults. chrome.storage is
 * intentionally not used so popup always relies on the packaged configuration
 * and the backend for fresh data.
 */

// bootstrap module for popup: resolve config and load legacy scripts in order
(async function bootstrap() {
  // always use packaged defaults; do not read from chrome.storage
  const resolved = Object.assign({}, defaults);

  // expose config globally
  window.TRAILTAG_CONFIG = resolved;

  // dynamic import old modules in order and attach to window.TrailTag
  const scripts = [
    { file: "utils.js", ns: "Utils" },
    { file: "api.js", ns: "API" },
    { file: "map.js", ns: "Map" },
    { file: "popup.js", ns: "Popup" },
  ];

  window.TrailTag = window.TrailTag || {};

  for (const s of scripts) {
    try {
      const mod = await import(`./${s.file}`);
      window.TrailTag[s.ns] = mod;
    } catch (err) {
      console.error("Failed to import module", s.file, err);
      throw err;
    }
  }
})();
// 將解析後的設定放到全域，可被舊式腳本或測試讀取（命名為 TRAILTAG_CONFIG）
