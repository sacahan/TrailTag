import defaults from "./config.mjs";
import * as Utils from "./utils/helpers.js";
import * as API from "./services/api.js";
import * as Map from "./core/map-renderer.js";
import * as Popup from "./core/popup-controller.js";

/*
 * popup.bootstrap.mjs
 *
 * Purpose: bootstrap popup environment using bundled defaults. chrome.storage is
 * intentionally not used so popup always relies on the packaged configuration
 * and the backend for fresh data.
 */

// bootstrap module for popup: resolve config and load legacy scripts in order
(function bootstrap() {
  // always use packaged defaults; do not read from chrome.storage
  const resolved = Object.assign({}, defaults);

  // expose config globally
  window.TRAILTAG_CONFIG = resolved;

  // attach modules to window.TrailTag
  window.TrailTag = window.TrailTag || {};
  window.TrailTag.Utils = Utils;
  window.TrailTag.API = API;
  window.TrailTag.Map = Map;
  window.TrailTag.Popup = Popup;

  console.log("TrailTag bootstrap completed", window.TrailTag);
})();
// 將解析後的設定放到全域，可被舊式腳本或測試讀取（命名為 TRAILTAG_CONFIG）
