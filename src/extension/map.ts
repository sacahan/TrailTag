/**
 * map.ts - TypeScript 版本的輕量地圖工具（加入中文註解以利維護）
 */

/* Ambient globals */
declare const L: any; // Leaflet 全域物件
declare const chrome: any; // Chrome extension API（若在 extension 環境可用）
declare global {
  interface Window {
    TrailTag?: any;
    initMap?: any;
    clearMarkers?: any;
    addMarkersFromMapVisualization?: any;
    getMarkersCount?: any;
    getMapCurrentVideoId?: any;
    getMarkersBounds?: any;
    getMarkerLatLngs?: any;
  }
}

// 模組等級的單例變數
export let leafletMap: any = null; // Leaflet 地圖實例（單例）
export let markersLayer: any = null; // 所有標記匯集的 layer（featureGroup 或 layerGroup）
export let currentVideoId: string | null = null; // 當前對應的影片 id
// 可選的工具集，若 window.TrailTag.Utils 存在則使用
const Utils =
  (typeof window !== "undefined" && window.TrailTag && window.TrailTag.Utils) ||
  null;

/**
 * 初始化 Leaflet 地圖（單例）
 * 若已初始化則回傳現有實例。
 * - containerId: 地圖要綁定的 DOM id
 *
 * 被呼叫來源：popup.ts（MAP_READY）與測試
 */
export function initMap(containerId: string) {
  if (leafletMap) return leafletMap; // 若已建立就直接回傳
  // 建立地圖並設定預設中心與縮放
  leafletMap = L.map(containerId).setView([25.0, 121.5], 10);
  // 使用 OpenStreetMap 的 tiles
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(leafletMap);
  // 建立一個 marker 的群組（featureGroup 支援 getBounds）並加入地圖
  markersLayer = (
    typeof L.featureGroup === "function" ? L.featureGroup() : L.layerGroup()
  ).addTo(leafletMap);
  // 當視窗大小改變時，若有標記則嘗試調整地圖範圍
  leafletMap.on("resize", function () {
    if (markersLayer && markersLayer.getLayers().length > 0)
      leafletMap.fitBounds(markersLayer.getBounds(), { padding: [20, 20] });
  });
  return leafletMap;
}

/**
 * 清除目前所有標記（如果 markersLayer 支援 clearLayers）
 */
export function clearMarkers() {
  if (markersLayer && typeof markersLayer.clearLayers === "function")
    markersLayer.clearLayers();
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
  clearMarkers();
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
    const bgColorWithAlpha = `${color}99`;
    return L.divIcon({
      className: "tt-div-icon",
      html: `<div style="display:flex;align-items:center;justify-content:center;width:16px;height:16px;background:${bgColorWithAlpha};color:#fff;font-size:18px;border-radius:50%;box-shadow:0 1px 3px rgba(0,0,0,0.8);">${emoji}</div>`,
      iconSize: [56, 56],
      iconAnchor: [28, 56],
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
    const markerOptions = icon ? { icon } : {};
    const marker =
      typeof L === "undefined" || !L.marker
        ? null
        : L.marker([lat, lon], markerOptions);

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

    // 綁定 popup（若 marker 支援）
    try {
      if (marker && typeof marker.bindPopup === "function")
        marker.bindPopup(popupContent);
    } catch (e) {}

    // 當 popup 開啟時，為 timecode 連結加入 click handler（支援 chrome extension 與一般 window.open）
    try {
      if (marker && typeof marker.on === "function")
        marker.on("popupopen", function (e: any) {
          try {
            const popupEl =
              e && e.popup && typeof e.popup.getElement === "function"
                ? e.popup.getElement()
                : null;
            if (!popupEl) return;
            // 支援多個連結：timecode-link 與 open-map-link
            const timeLink =
              popupEl.querySelector && popupEl.querySelector(".timecode-link");
            const mapLink =
              popupEl.querySelector && popupEl.querySelector(".open-map-link");

            function bindOpenLink(el: any, dataAttr: string) {
              if (!el) return;
              if (el.__tt_bound) return;
              el.__tt_bound = true;
              el.addEventListener("click", function (ev: any) {
                try {
                  ev.preventDefault();
                  const url = el.getAttribute(dataAttr);
                  if (!url || url === "#") return;
                  if (typeof chrome !== "undefined" && chrome.tabs) {
                    try {
                      // For timecode links prefer updating the current active tab so the user stays in the video context.
                      // For other links (e.g. google maps) prefer creating a new tab.
                      const prefersUpdate =
                        dataAttr === "data-timecode-url" ||
                        (el.classList &&
                          el.classList.contains("timecode-link"));
                      if (
                        prefersUpdate &&
                        chrome.tabs.query &&
                        chrome.tabs.update
                      ) {
                        // Try to update the current active tab first, fallback to creating a new tab or window.open
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
                        // Default behaviour for non-timecode links: open a new tab
                        chrome.tabs.create({ url: url });
                      } else if (chrome.tabs.query && chrome.tabs.update) {
                        // Fallback: update current tab if create is not available
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
          } catch (err) {}
        });
    } catch (e) {}

    try {
      console.debug("Added marker", {
        location: route.location,
        coords: [lat, lon],
        markerType: route.marker,
        tags: route.tags,
      });
    } catch (e) {}
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
  console.debug("Total markers on map:", count);
  return count;
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
  }
} catch (e) {}

export default null;
