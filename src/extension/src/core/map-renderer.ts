/**
 * map-renderer.ts - TypeScript 版本的 TrailTag 地圖渲染工具
 *
 * 此檔案負責 Leaflet 地圖的初始化、標記管理、互動事件、UI 狀態顯示等核心功能。
 * 主要功能：
 *   1. 地圖初始化與配置
 *   2. 標記的建立、清除與管理
 *   3. 地圖視覺化資料的處理
 *   4. 使用者互動事件處理
 *   5. 地圖 UI 狀態管理
 *
 * 全域 API 暴露設計：
 *   - 所有地圖相關 API 會掛載於 window.TrailTag.Map 命名空間，並於 window 上建立對應的全域方法別名。
 *   - 方便其他模組或外部程式直接呼叫地圖功能，例如 window.initMap, window.clearMarkers 等。
 *
 * 所有註解皆以正體中文撰寫，便於維護與理解。
 */

// 宣告外部全域物件
declare const L: any; // Leaflet 地圖 API 全域物件
declare const chrome: any; // Chrome extension API（僅於 extension 環境可用）

// 擴展 Window 介面，定義 TrailTag 相關的全域方法與屬性
declare global {
  interface Window {
    TrailTag?: any; // TrailTag 主命名空間，包含所有相關模組
    initMap?: any; // 初始化地圖的全域方法
    clearMarkers?: any; // 清除所有標記的全域方法
    addMarkersFromMapVisualization?: any; // 從視覺化資料新增標記的全域方法
    getMarkersCount?: any; // 取得標記數量的全域方法
    getMapCurrentVideoId?: any; // 取得當前影片 ID 的全域方法
    getMarkersBounds?: any; // 取得標記邊界的全域方法
    getMarkerLatLngs?: any; // 取得所有標記座標的全域方法
    showMapLoading?: any; // 顯示載入狀態的全域方法
    hideMapLoading?: any; // 隱藏載入狀態的全域方法
    showMapError?: any; // 顯示錯誤訊息的全域方法
    hideMapError?: any; // 隱藏錯誤訊息的全域方法
    updateMapPerformance?: any; // 更新性能資訊的全域方法
    refreshMap?: any; // 重新整理地圖的全域方法
  }
}

// 模組等級的單例變數 - 用於維護地圖狀態
export let leafletMap: any = null; // Leaflet 地圖實例（單例模式），確保全域只有一個地圖實例
export let markersLayer: any = null; // 所有標記匯集的 layer（featureGroup 或 layerGroup），用於統一管理標記
export let currentVideoId: string | null = null; // 當前對應的影片 id，用於關聯地圖標記與影片內容

// 可選的工具集，若 window.TrailTag.Utils 存在則使用，提供輔助功能如時間碼格式化等
const Utils =
  (typeof window !== "undefined" && window.TrailTag && window.TrailTag.Utils) ||
  null;

// 地圖優化工具，若 window.TrailTag.MapOptimization 存在則使用，提供性能優化功能
const MapOptimization =
  (typeof window !== "undefined" &&
    window.TrailTag &&
    window.TrailTag.MapOptimization) ||
  null;

/**
 * 初始化 Leaflet 地圖（單例模式）
 * 如果地圖實例已存在，則直接回傳現有實例，避免重複初始化
 *
 * @param containerId - 地圖要綁定的 DOM 元素 ID
 * @returns 地圖實例物件
 *
 * 被呼叫來源：popup.ts（MAP_READY 事件）與測試程式
 *
 * 功能說明：
 *   1. 檢查是否已存在地圖實例，若存在則直接回傳
 *   2. 建立新的 Leaflet 地圖實例並設定預設視圖
 *   3. 新增 OpenStreetMap 圖層作為底圖
 *   4. 建立標記群組並啟用優化功能
 *   5. 綁定地圖事件處理器
 */
export function initMap(containerId: string) {
  if (leafletMap) return leafletMap; // 若已建立實例就直接回傳，確保單例模式
  // 建立地圖實例並設定預設中心點（台灣中心）與縮放等級
  leafletMap = L.map(containerId).setView([25.0, 121.5], 10);
  // 使用 OpenStreetMap 的圖磚服務作為底圖
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19, // 設定最大縮放等級
  }).addTo(leafletMap);
  // 暫時禁用聚類群組以避免 popup 重複開啟問題
  // TODO: 未來可以實作動態聚類切換功能
  console.log(
    "🎯 Using FeatureGroup to avoid MarkerClusterGroup popup conflicts",
  );
  markersLayer =
    typeof L.featureGroup === "function" ? L.featureGroup() : L.layerGroup();
  markersLayer.addTo(leafletMap);

  // 啟用地圖優化功能
  if (
    MapOptimization &&
    typeof MapOptimization.optimizeTileLoading === "function"
  ) {
    MapOptimization.optimizeTileLoading(leafletMap);
  }
  // 當視窗大小改變時，若有標記則嘗試調整地圖範圍（使用優化的智能調整）
  leafletMap.on("resize", function () {
    if (markersLayer && markersLayer.getLayers().length > 0) {
      const bounds =
        typeof markersLayer.getBounds === "function"
          ? markersLayer.getBounds()
          : null;
      if (bounds) {
        if (
          MapOptimization &&
          typeof MapOptimization.smartFitBounds === "function"
        ) {
          console.warn("🔍 CALLING smartFitBounds from RESIZE event");
          MapOptimization.smartFitBounds(leafletMap, bounds);
        } else {
          console.warn("🔍 CALLING leafletMap.fitBounds from RESIZE event");
          leafletMap.fitBounds(bounds, { padding: [20, 20] });
        }
      }
    }
  });

  // 添加 zoom 事件處理器，確保標記在縮放時位置正確
  leafletMap.on("zoom", function () {
    // 強制重繪標記，確保位置正確
    if (markersLayer && typeof markersLayer.getLayers === "function") {
      const layers = markersLayer.getLayers();
      layers.forEach((marker: any) => {
        if (
          marker &&
          typeof marker.getLatLng === "function" &&
          typeof marker.setLatLng === "function"
        ) {
          // 重新設置標記位置以確保正確顯示
          const latLng = marker.getLatLng();
          marker.setLatLng(latLng);

          // 如果標記有自定義 icon，確保 icon 正確更新
          if (
            marker.options &&
            marker.options.icon &&
            typeof marker.setIcon === "function"
          ) {
            marker.setIcon(marker.options.icon);
          }
        }
      });
    }
  });

  // 添加 zoomend 事件處理器，在縮放結束後進行最終調整
  leafletMap.on("zoomend", function () {
    // 縮放結束後，確保地圖視圖正確更新
    setTimeout(() => {
      if (leafletMap && typeof leafletMap.invalidateSize === "function") {
        leafletMap.invalidateSize();
      }

      // 如果有標記且需要重新調整視圖範圍
      if (
        markersLayer &&
        typeof markersLayer.getLayers === "function" &&
        markersLayer.getLayers().length > 0
      ) {
        const bounds =
          typeof markersLayer.getBounds === "function"
            ? markersLayer.getBounds()
            : null;
        if (bounds && bounds.isValid && bounds.isValid()) {
          // 檢查當前 zoom 是否合適，避免無限調整
          const currentZoom = leafletMap.getZoom();
          console.warn("🔍 ZOOMEND HANDLER - Current zoom:", currentZoom);
          if (currentZoom < 3) {
            // 只在 zoom 過小時才重新調整，允許用戶縮放到最大級別 19
            console.warn(
              "🔍 ZOOMEND HANDLER - Executing fitBounds due to zoom too small",
            );
            leafletMap.fitBounds(bounds, { padding: [20, 20], maxZoom: 16 });
          } else {
            console.warn(
              "🔍 ZOOMEND HANDLER - Zoom acceptable, no adjustment needed",
            );
          }
        }
      }
    }, 100);
  });
  return leafletMap;
}

/**
 * 清除目前所有標記（如果 markersLayer 支援 clearLayers）
 */
export function clearMarkers() {
  console.warn("🧹 === clearMarkers START ===");
  if (markersLayer && typeof markersLayer.clearLayers === "function") {
    // 在清除前，移除所有 popup 的處理標記以防止記憶體洩漏
    try {
      if (typeof markersLayer.getLayers === "function") {
        const layers = markersLayer.getLayers();
        console.warn(`🗑️ Found ${layers.length} markers to clear`);

        layers.forEach((marker: any, index: number) => {
          try {
            console.warn(`🧹 Clearing marker ${index}:`, {
              bound: marker.__popup_handler_bound,
              hasOff: typeof marker.off === "function",
            });

            if (marker && marker._popup && marker._popup._container) {
              delete marker._popup._container.__tt_popup_processed;
            }
            // 清理自定義屬性（按 Leaflet 官方文檔，事件清理在綁定時處理）
            if (marker) {
              console.warn(`🧹 Clearing marker ${index}`);
            }
          } catch (e) {
            console.warn(`❌ Error clearing marker ${index}:`, e);
          }
        });
      }
    } catch (e) {
      console.warn("❌ Error in clearMarkers:", e);
    }
    markersLayer.clearLayers();
    console.warn("✅ markersLayer.clearLayers() completed");
  }
  console.warn("🧹 === clearMarkers END ===");
}

/**
 * 將 mapVisualization 轉為地圖上的 markers 並加入到 markersLayer
 * - 會嘗試建立 markersLayer（若尚未建立）
 * - 會清除舊有標記、設定 currentVideoId，並回傳加入後的標記數量
 *
 * 參數：
 * - mapVisualization: 期待具有 routes 陣列的物件
 * - videoId: 與標記關聯的影片 id（可為 null）
 */
export function addMarkersFromMapVisualization(
  mapVisualization: any,
  videoId: string | null,
): number {
  console.warn("🚀 === addMarkersFromMapVisualization START ===", {
    videoId,
    timestamp: Date.now(),
    stack: new Error().stack?.split("\n")[1]?.trim(),
  });
  // 確保 markersLayer 已建立，盡可能在 leafletMap 或 DOM 已就緒時建立
  if (!markersLayer) {
    if (leafletMap) {
      markersLayer = (
        typeof L.featureGroup === "function" ? L.featureGroup() : L.layerGroup()
      ).addTo(leafletMap);
    } else if (
      typeof document !== "undefined" &&
      document.getElementById &&
      document.getElementById("map")
    ) {
      try {
        initMap("map");
      } catch (e) {}
    }
    if (!markersLayer) {
      markersLayer =
        typeof L.featureGroup === "function"
          ? L.featureGroup()
          : L.layerGroup();
    }
  }

  // 清除現有標記並設定目前影片 id
  console.warn("🧹 About to clearMarkers...");
  clearMarkers();
  console.warn("✅ clearMarkers completed");
  currentVideoId = videoId;

  const routes = (mapVisualization && mapVisualization.routes) || [];

  // 根據 route 的類型或 tag 建立一個簡單的 divIcon，用顏色與 emoji 表示類別
  function createIconForRoute(route: any) {
    const type =
      (route && route.marker) ||
      (route && route.tags && route.tags[0]) ||
      "default";
    const COLOR_MAP: any = {
      Restaurant: "#e74c3c",
      default: "#2c3e50",
      Park: "#27ae60",
      Museum: "#8e44ad",
      Shop: "#f39c12",
    };
    const color = COLOR_MAP[type] || COLOR_MAP.default;
    const EMOJI_MAP: any = {
      Restaurant: "🍔",
      Park: "🌳",
      Museum: "🏛️",
      Shop: "🛍️",
    };
    const emoji = EMOJI_MAP[type] || "❇️";
    // 使用透明背景（不顯示圓形背景色），保留尺寸與對齊
    // 將 icon 放大為 56x56，加入半透明圓形背景以提高可見性，保留置中底部 anchor
    // 使用 8 位 hex alpha（modern browsers 支援），alpha 0x99 約為 60% 不透明度
    return L.divIcon({
      className: "tt-div-icon",
      html: `<div style="display:flex;align-items:center;justify-content:center;width:24px;height:24px;color:#fff;font-size:24px;border-radius:50%;">${emoji}</div>`,
      iconSize: [36, 36],
      iconAnchor: [28, 36],
      popupAnchor: [0, -36],
    });
  }

  // 逐一處理 route，建立 marker、popup 與事件綁定
  routes.forEach((route: any) => {
    if (!route || !route.coordinates || route.coordinates.length !== 2) return; // 無效資料略過
    let lat = Number(route.coordinates[0]);
    let lon = Number(route.coordinates[1]);
    // 有時候 coordinates 可能被放反（lon, lat），嘗試偵測並交換
    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      if (Math.abs(lat) > 90 && Math.abs(lon) <= 90) {
        const tmp = lat;
        lat = lon;
        lon = tmp;
      }
    } else {
      return;
    }

    // 嘗試建立自訂 icon，若失敗則使用預設 marker
    let icon: any = null;
    try {
      icon = createIconForRoute(route);
    } catch (e) {
      icon = null;
    }
    const markerOptions = icon
      ? {
          icon,
          // 添加額外選項以提高標記穩定性
          riseOnHover: true,
          riseOffset: 250,
        }
      : {
          riseOnHover: true,
          riseOffset: 250,
        };

    const marker =
      typeof L === "undefined" || !L.marker
        ? null
        : L.marker([lat, lon], markerOptions);

    // 為標記添加防止位置偏移的處理
    if (marker && typeof marker.on === "function") {
      marker.on("add", function () {
        // 確保標記添加到地圖時位置正確
        setTimeout(() => {
          if (
            marker &&
            typeof marker.getLatLng === "function" &&
            typeof marker.setLatLng === "function"
          ) {
            const currentLatLng = marker.getLatLng();
            marker.setLatLng([currentLatLng.lat, currentLatLng.lng]);
          }
        }, 50);
      });
    }

    // 將 marker 加入 markersLayer（不同 Leaflet 版本有不同方法，故做多重嘗試）
    if (markersLayer) {
      if (typeof markersLayer.addLayer === "function")
        markersLayer.addLayer(marker);
      else if (marker && typeof marker.addTo === "function") {
        try {
          marker.addTo(markersLayer);
        } catch (e) {}
      } else if (leafletMap && marker) marker.addTo(leafletMap);
    } else if (leafletMap && marker) marker.addTo(leafletMap);

    // 建立 popup 內容（包含位置與描述），並加入兩個並排連結：左為「在地圖開啟」，右為「觀看片段」(若有 timecode)
    let popupContent = `<div class="marker-popup"><h3>${route.location}</h3>`;
    if (route.description) popupContent += `<p>${route.description}</p>`;

    // 使用 route 的經緯度建立 Google Maps link
    const googleMapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
      lat + "," + lon,
    )}`;

    popupContent += `<div class="popup-links">`;

    // 先加入觀看片段（若有），再加入在地圖開啟，讓「在地圖開啟」顯示於右側
    if (route.timecode) {
      const vid = videoId || null;
      let timecodeUrl = "#";
      // 若有 Utils.createTimecodeUrl，使用它產生連結
      if (vid) {
        if (Utils && typeof Utils.createTimecodeUrl === "function")
          timecodeUrl = Utils.createTimecodeUrl(vid, route.timecode);
      }
      const formattedTime =
        Utils && typeof Utils.formatTimecode === "function"
          ? Utils.formatTimecode(route.timecode)
          : route.timecode;
      popupContent += `<a href="${timecodeUrl}" data-timecode-url="${timecodeUrl}" class="timecode-link popup-link">觀看片段 ${formattedTime}</a>`;
    }

    // 在地圖開啟連結（會由 popupopen handler 處理以支援 chrome.tabs），放在後面以顯示於右側
    popupContent += `<a href="${googleMapsUrl}" target="_blank" data-google-url="${googleMapsUrl}" class="open-map-link popup-link">在地圖開啟</a>`;

    popupContent += "</div></div>";

    // 綁定 popup（若 marker 支援） - 使用完整內容
    try {
      if (marker && typeof marker.bindPopup === "function") {
        marker.bindPopup(popupContent);
        console.log("🔗 Bound popup to:", route.location);
      }
    } catch (e) {}

    // 當 popup 開啟時，為 timecode 連結加入 click handler（支援 chrome extension 與一般 window.open）
    // 使用 once 來避免重複綁定事件
    try {
      if (marker && typeof marker.once === "function") {
        marker.once("popupopen", function (e: any) {
          try {
            const popupEl =
              e && e.popup && typeof e.popup.getElement === "function"
                ? e.popup.getElement()
                : null;
            if (!popupEl) return;

            const timeLink =
              popupEl.querySelector && popupEl.querySelector(".timecode-link");
            const mapLink =
              popupEl.querySelector && popupEl.querySelector(".open-map-link");

            function bindOpenLink(el: any, dataAttr: string) {
              if (!el || el.__tt_bound) return;
              el.__tt_bound = true;
              el.addEventListener("click", function (ev: any) {
                try {
                  ev.preventDefault();
                  const url = el.getAttribute(dataAttr);
                  if (!url || url === "#") return;
                  if (typeof chrome !== "undefined" && chrome.tabs) {
                    try {
                      const prefersUpdate =
                        dataAttr === "data-timecode-url" ||
                        (el.classList &&
                          el.classList.contains("timecode-link"));
                      if (
                        prefersUpdate &&
                        chrome.tabs.query &&
                        chrome.tabs.update
                      ) {
                        chrome.tabs.query(
                          { active: true, currentWindow: true },
                          function (tabs: any) {
                            try {
                              if (tabs && tabs[0] && tabs[0].id) {
                                chrome.tabs.update(tabs[0].id, { url: url });
                              } else if (
                                typeof chrome.tabs.create === "function"
                              ) {
                                chrome.tabs.create({ url: url });
                              } else {
                                window.open(url, "_blank");
                              }
                            } catch (err) {
                              window.open(url, "_blank");
                            }
                          },
                        );
                      } else if (typeof chrome.tabs.create === "function") {
                        chrome.tabs.create({ url: url });
                      } else if (chrome.tabs.query && chrome.tabs.update) {
                        chrome.tabs.query(
                          { active: true, currentWindow: true },
                          function (tabs: any) {
                            try {
                              if (tabs && tabs[0] && tabs[0].id)
                                chrome.tabs.update(tabs[0].id, { url: url });
                              else window.open(url, "_blank");
                            } catch (err) {
                              window.open(url, "_blank");
                            }
                          },
                        );
                      } else {
                        window.open(url, "_blank");
                      }
                    } catch (err) {
                      window.open(url, "_blank");
                    }
                  } else {
                    window.open(url, "_blank");
                  }
                } catch (err) {
                  console.error("Link click handler error", err);
                }
              });
            }

            bindOpenLink(timeLink, "data-timecode-url");
            bindOpenLink(mapLink, "data-google-url");
          } catch (err) {
            console.error("Popup event handler error", err);
          }
        });
      }
    } catch (e) {
      console.error("Failed to bind popup event handler", e);
    }

    try {
      // 在非生產環境中顯示調試資訊
      // 注意：這裡使用 window.TrailTag?.debug 代替對 process.env 的引用
      if (
        typeof window !== "undefined" &&
        window.TrailTag &&
        window.TrailTag.debug
      ) {
        console.debug("Added marker", {
          location: route.location,
          coords: [lat, lon],
          markerType: route.marker,
          tags: route.tags,
        });
      }
    } catch (e) {
      // 忽略調試資訊輸出過程中的錯誤
    }
  });

  // 確保 markersLayer 已加入地圖（某些情況下 markersLayer 尚未被 addTo）
  try {
    if (
      markersLayer &&
      leafletMap &&
      (!markersLayer._map || markersLayer._map !== leafletMap)
    ) {
      try {
        markersLayer.addTo(leafletMap);
      } catch (e) {}
    }
  } catch (e) {}

  // 如果有標記，嘗試調整地圖範圍以包含所有標記，並以重試機制處理 layout timing 問題
  if (
    markersLayer &&
    leafletMap &&
    typeof markersLayer.getLayers === "function" &&
    markersLayer.getLayers().length > 0
  ) {
    const bounds =
      typeof markersLayer.getBounds === "function"
        ? markersLayer.getBounds()
        : null;
    if (bounds) {
      const tryFit = (attemptsLeft = 3, delay = 120) => {
        try {
          try {
            leafletMap.invalidateSize();
          } catch (e) {}
          leafletMap.fitBounds(bounds, { padding: [20, 20] });
        } catch (err) {
          if (attemptsLeft > 0)
            setTimeout(
              () => tryFit(attemptsLeft - 1, Math.min(600, delay * 2)),
              delay,
            );
          else console.warn("fitBounds failed after retries", err);
        }
      };
      tryFit();
    }
  }

  const count =
    markersLayer && typeof markersLayer.getLayers === "function"
      ? markersLayer.getLayers().length
      : 0;
  console.warn("🏁 === addMarkersFromMapVisualization END ===", {
    totalMarkers: count,
    timestamp: Date.now(),
  });

  // 更新 UI 和性能指標
  setTimeout(() => {
    hideMapLoading(); // 隱藏載入中狀態
    updateMapPerformance(); // 更新性能指標

    // 更新地點計數顯示
    try {
      const locationsCountEl = document.getElementById("locations-count");
      if (locationsCountEl) {
        locationsCountEl.textContent = `${count} 個地點`;
      }
    } catch (e) {
      console.warn("Failed to update locations count", e);
    }
  }, 100);

  return count; // 回傳標記數量
}

/**
 * 取得目前 markers 的數量
 */
export function getMarkersCount() {
  return markersLayer && typeof markersLayer.getLayers === "function"
    ? markersLayer.getLayers().length
    : 0;
}

/**
 * 取得目前關聯的影片 ID
 */
export function getMapCurrentVideoId() {
  return currentVideoId;
}

/**
 * 取得 markers layer 的邊界（若有標記則回傳 LatLngBounds，否則回傳 null）
 */
export function getMarkersBounds() {
  try {
    if (
      markersLayer &&
      typeof markersLayer.getBounds === "function" &&
      typeof markersLayer.getLayers === "function" &&
      markersLayer.getLayers().length > 0
    )
      return markersLayer.getBounds();
  } catch (e) {
    console.warn("getMarkersBounds error", e);
  }
  return null;
}

/**
 * 回傳 markers 的 LatLng 陣列，若發生錯誤或無 markers 則回傳空陣列
 */
export function getMarkerLatLngs() {
  try {
    if (!markersLayer || typeof markersLayer.getLayers !== "function")
      return [];
    return markersLayer.getLayers().map((l: any) => {
      try {
        return l && typeof l.getLatLng === "function" ? l.getLatLng() : null;
      } catch (e) {
        return null;
      }
    });
  } catch (e) {
    console.warn("getMarkerLatLngs error", e);
    return [];
  }
}

/**
 * 顯示地圖載入狀態
 * @param {string} message - 載入訊息
 */
export function showMapLoading(message = "正在載入地圖...") {
  try {
    const loadingOverlay = document.getElementById("map-loading-overlay");
    const loadingText = loadingOverlay?.querySelector(
      ".map-loading-text",
    ) as HTMLElement;

    if (loadingOverlay) {
      loadingOverlay.classList.remove("hidden");
      if (loadingText) {
        loadingText.textContent = message;
      }
    }
  } catch (e) {
    console.warn("showMapLoading error", e);
  }
}

/**
 * 隱藏地圖載入狀態
 */
export function hideMapLoading() {
  try {
    const loadingOverlay = document.getElementById("map-loading-overlay");
    if (loadingOverlay) {
      loadingOverlay.classList.add("hidden");
    }
  } catch (e) {
    console.warn("hideMapLoading error", e);
  }
}

/**
 * 顯示地圖錯誤提示
 * @param {string} message - 錯誤訊息
 * @param {number} duration - 顯示時長(毫秒)，0 表示不自動隱藏
 */
export function showMapError(message: string, duration = 5000) {
  try {
    const errorBanner = document.getElementById("map-error-banner");
    const errorMessage = document.getElementById("map-error-message");

    if (errorBanner && errorMessage) {
      errorMessage.textContent = message;
      errorBanner.classList.remove("hidden");

      // 自動隱藏
      if (duration > 0) {
        setTimeout(() => hideMapError(), duration);
      }
    }
  } catch (e) {
    console.warn("showMapError error", e);
  }
}

/**
 * 隱藏地圖錯誤提示
 */
export function hideMapError() {
  try {
    const errorBanner = document.getElementById("map-error-banner");
    if (errorBanner) {
      errorBanner.classList.add("hidden");
    }
  } catch (e) {
    console.warn("hideMapError error", e);
  }
}

/**
 * 更新地圖性能信息顯示
 */
export function updateMapPerformance() {
  try {
    const performanceEl = document.getElementById("map-performance");
    if (!performanceEl) return;

    // 從優化模組獲取性能指標
    if (
      MapOptimization &&
      typeof MapOptimization.getPerformanceMetrics === "function"
    ) {
      const metrics = MapOptimization.getPerformanceMetrics();
      const renderTime = metrics.renderTime
        ? Math.round(metrics.renderTime)
        : 0;

      if (renderTime > 0) {
        performanceEl.textContent = `渲染時間: ${renderTime}ms`;
        performanceEl.style.display = "block";
      } else {
        performanceEl.style.display = "none";
      }
    } else {
      performanceEl.style.display = "none";
    }
  } catch (e) {
    console.warn("updateMapPerformance error", e);
  }
}

/**
 * 重新整理地圖
 */
export function refreshMap() {
  try {
    showMapLoading("正在重新整理地圖...");

    setTimeout(() => {
      try {
        if (leafletMap && typeof leafletMap.invalidateSize === "function") {
          leafletMap.invalidateSize();
        }

        // 如果有標記，重新調整視圖
        if (
          markersLayer &&
          typeof markersLayer.getLayers === "function" &&
          markersLayer.getLayers().length > 0
        ) {
          const bounds =
            typeof markersLayer.getBounds === "function"
              ? markersLayer.getBounds()
              : null;
          if (bounds) {
            if (
              MapOptimization &&
              typeof MapOptimization.smartFitBounds === "function"
            ) {
              console.warn(
                "🔍 CALLING smartFitBounds from addMarkersFromMapVisualization",
              );
              MapOptimization.smartFitBounds(leafletMap, bounds);
            } else {
              console.warn(
                "🔍 CALLING leafletMap.fitBounds from addMarkersFromMapVisualization",
              );
              leafletMap.fitBounds(bounds, { padding: [20, 20] });
            }
          }
        }

        hideMapLoading();
        updateMapPerformance();
      } catch (error) {
        hideMapLoading();
        showMapError("地圖重新整理失敗: " + (error as Error).message);
      }
    }, 500);
  } catch (e) {
    console.warn("refreshMap error", e);
    hideMapLoading();
    showMapError("無法重新整理地圖");
  }
}

// 添加全局調試監控
if (typeof window !== "undefined") {
  (window as any).__DEBUG_MARKER_EVENTS = true;
  console.warn("🐞 Marker event debugging enabled");
}

// 若在瀏覽器環境，將 API 暴露到 window.TrailTag.Map，並在 window 上建立方便存取的別名
try {
  if (typeof window !== "undefined") {
    window.TrailTag = window.TrailTag || {};
    window.TrailTag.Map = Object.assign(window.TrailTag.Map || {}, {
      initMap,
      clearMarkers,
      addMarkersFromMapVisualization,
      getMarkersCount,
      getMapCurrentVideoId,
      getMarkersBounds,
      getMarkerLatLngs,
      showMapLoading,
      hideMapLoading,
      showMapError,
      hideMapError,
      updateMapPerformance,
      refreshMap,
    });
    if (!window.initMap) window.initMap = window.TrailTag.Map.initMap;
    if (!window.clearMarkers)
      window.clearMarkers = window.TrailTag.Map.clearMarkers;
    if (!window.addMarkersFromMapVisualization)
      window.addMarkersFromMapVisualization =
        window.TrailTag.Map.addMarkersFromMapVisualization;
    if (!window.getMarkersCount)
      window.getMarkersCount = window.TrailTag.Map.getMarkersCount;
    if (!window.getMapCurrentVideoId)
      window.getMapCurrentVideoId = window.TrailTag.Map.getMapCurrentVideoId;
    if (!window.getMarkersBounds)
      window.getMarkersBounds = window.TrailTag.Map.getMarkersBounds;
    if (!window.getMarkerLatLngs)
      window.getMarkerLatLngs = window.TrailTag.Map.getMarkerLatLngs;
    if (!window.showMapLoading)
      window.showMapLoading = window.TrailTag.Map.showMapLoading;
    if (!window.hideMapLoading)
      window.hideMapLoading = window.TrailTag.Map.hideMapLoading;
    if (!window.showMapError)
      window.showMapError = window.TrailTag.Map.showMapError;
    if (!window.hideMapError)
      window.hideMapError = window.TrailTag.Map.hideMapError;
    if (!window.updateMapPerformance)
      window.updateMapPerformance = window.TrailTag.Map.updateMapPerformance;
    if (!window.refreshMap) window.refreshMap = window.TrailTag.Map.refreshMap;
  }
} catch (e) {
  console.warn("Failed to expose Map API to window", e);
}

/**
 * 初始化地圖 UI 事件監聽器
 * 綁定地圖相關 UI 元素的事件處理器
 */
export function initMapUI(): void {
  try {
    // 地圖錯誤提示關閉按鈕
    const errorCloseBtn = document.getElementById("map-error-close");
    if (errorCloseBtn && !errorCloseBtn.hasAttribute("data-listener-added")) {
      errorCloseBtn.addEventListener("click", hideMapError);
      errorCloseBtn.setAttribute("data-listener-added", "true");
    }

    // 重新整理地圖按鈕
    const refreshBtn = document.getElementById("refresh-map-btn");
    if (refreshBtn && !refreshBtn.hasAttribute("data-listener-added")) {
      refreshBtn.addEventListener("click", refreshMap);
      refreshBtn.setAttribute("data-listener-added", "true");
    }

    console.debug("Map UI event listeners initialized");
  } catch (e) {
    console.warn("Failed to initialize map UI event listeners", e);
  }
}

/**
 * 工具函式：在 DOMContentLoaded 或 DOM 已載入時執行 callback
 * @param callback 要執行的函式
 */
function runOnDomReady(callback: () => void): void {
  if (typeof document === "undefined") return;
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", callback);
  } else {
    callback();
  }
}

// 如果在 DOM 就緒時自動初始化 UI
runOnDomReady(initMapUI);

// 用於 ESModule 語法支援，避免使用預設匯出時出現警告
export default null;
