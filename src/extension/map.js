/**
 * 地圖處理模組
 *
 * 本檔案使用 Leaflet (L) 建立地圖與標記圖層，並提供簡單的 API
 * 供擴充功能其他模組呼叫：
 * - initMap(containerId)
 * - clearMarkers()
 * - addMarkersFromMapVisualization(mapVisualization, videoId)
 * - getMarkersCount()
 * - getCurrentVideoId()
 */

// 地圖實例；若未初始化為 null
let map = null;
// 存放所有標記的 LayerGroup，方便一次清除或取得邊界
let markersLayer = null;
// 記住目前顯示路線所屬的 YouTube video id，供外部查詢
let currentVideoId = null;

/**
 * 初始化地圖（單例）
 *
 * 如果已呼叫過，會直接回傳既有的地圖實例，避免重複建立。
 *
 * @param {string} containerId - DOM 容器的 id（例如 'map'）
 * @returns {L.Map} 已建立或既有的 Leaflet 地圖實例
 */
function initMap(containerId) {
  // 若已初始化，直接回傳，保證單例行為
  if (map) return map;

  // 建立 Leaflet 地圖，預設聚焦台灣中心點與適當縮放等級
  map = L.map(containerId).setView([25.0, 121.5], 10); // 預設台灣中心點

  // 加入 OpenStreetMap 的圖磚服務（Tile Layer）
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    // 圖磚來源聲明（必須保留授權資訊）
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(map);

  // 建立一個 LayerGroup 來管理後續產生的標記（marker）
  markersLayer = L.layerGroup().addTo(map);

  // 當地圖尺寸改變時，若已有標記則自動調整視窗以包住所有標記
  map.on('resize', function() {
    if (markersLayer && markersLayer.getLayers().length > 0) {
      map.fitBounds(markersLayer.getBounds(), { padding: [20, 20] });
    }
  });

  return map;
}

/**
 * 清除目前所有標記
 *
 * 會清空 `markersLayer` 中的所有 child layers（markers / popups），
 * 但不會移除圖層本身，方便之後繼續向同一個圖層新增。
 */
function clearMarkers() {
  if (markersLayer) {
    markersLayer.clearLayers();
  }
}

/**
 * 從 MapVisualization 物件新增標記
 *
 * 此函式負責：
 * - 清除舊的標記
 * - 以 mapVisualization.routes（陣列）逐一建立 marker
 * - 將每個 marker 綁定彈跳視窗，顯示地點、描述與可連回影片時間點的連結
 * - 最後自動調整地圖視窗以包住所有標記
 *
 * @param {Object} mapVisualization - 包含 routes 陣列的物件，每個 route 應含有 coordinates、location 等欄位
 * @param {string} videoId - 對應的 YouTube 影片 ID（用於建立跳轉到特定時間碼的連結）
 * @returns {number} 新增後的標記數量
 */
function addMarkersFromMapVisualization(mapVisualization, videoId) {
  // 先清除之前的標記，確保地圖只顯示當前影片的路線
  clearMarkers();

  // 記錄目前影片 ID，讓外部可以查詢或建立時間碼連結
  currentVideoId = videoId;

  // 安全取值：若 mapVisualization.routes 不存在則視為空陣列
  const routes = (mapVisualization && mapVisualization.routes) || [];

  routes.forEach(route => {
    // 檢查座標格式是否合理，預期為 [lon, lat]
    if (!route || !route.coordinates || route.coordinates.length !== 2) return;

    const [lon, lat] = route.coordinates;
    // Leaflet 使用 [lat, lon] 的順序
    const marker = L.marker([lat, lon]).addTo(markersLayer);

    // 建立彈出視窗內容（安全性：假設外部已淨化輸入或信任來源）
    let popupContent = `<div class="marker-popup">
      <h3>${route.location}</h3>`;

    // 若有描述文字則加入段落
    if (route.description) {
      popupContent += `<p>${route.description}</p>`;
    }

    // 若有時間碼（timecode）則顯示可點擊連結，連回 YouTube 的對應時間
    if (route.timecode) {
      // 依賴外部函式 createTimecodeUrl 與 formatTimecode（若不存在則會拋錯）
      const timecodeUrl = createTimecodeUrl(videoId, route.timecode);
      const formattedTime = formatTimecode(route.timecode);
      popupContent += `<a href="${timecodeUrl}" target="_blank" class="timecode-link">
        觀看片段 ${formattedTime}
      </a>`;
    }

    popupContent += '</div>';

    // 將組好的 HTML 綁定到 marker 的 popup
    marker.bindPopup(popupContent);
  });

  // 若圖層內有標記，調整地圖視窗以包覆所有標記（加上 padding）
  if (markersLayer && markersLayer.getLayers().length > 0) {
    map.fitBounds(markersLayer.getBounds(), { padding: [20, 20] });
  }

  return markersLayer ? markersLayer.getLayers().length : 0;
}

/**
 * 取得目前圖層中標記的數量
 * @returns {number} 標記數量（若未建立圖層則回傳 0）
 */
function getMarkersCount() {
  return markersLayer ? markersLayer.getLayers().length : 0;
}

/**
 * 取得目前關聯的 YouTube 影片 ID
 * @returns {string|null} 若尚未設定則回傳 null
 */
function getCurrentVideoId() {
  return currentVideoId;
}
