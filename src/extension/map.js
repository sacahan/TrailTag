/**
 * 地圖處理模組
 */

// 地圖實例
let map = null;
// 所有標記的圖層
let markersLayer = null;
// 目前影片的 video_id
let currentVideoId = null;

/**
 * 初始化地圖
 * @param {string} containerId - 地圖容器元素 ID
 * @returns {Object} 地圖實例
 */
function initMap(containerId) {
  // 檢查是否已經初始化
  if (map) return map;

  // 建立地圖
  map = L.map(containerId).setView([25.0, 121.5], 10); // 預設台灣中心點

  // 加入 OpenStreetMap 圖層
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(map);

  // 建立標記圖層
  markersLayer = L.layerGroup().addTo(map);

  // 稍後自適應地圖邊界，確保所有標記都在視圖內
  map.on('resize', function() {
    if (markersLayer.getLayers().length > 0) {
      map.fitBounds(markersLayer.getBounds(), { padding: [20, 20] });
    }
  });

  return map;
}

/**
 * 清除所有標記
 */
function clearMarkers() {
  if (markersLayer) {
    markersLayer.clearLayers();
  }
}

/**
 * 從 MapVisualization 中的路線添加標記
 * @param {Object} mapVisualization - MapVisualization 物件
 * @param {string} videoId - YouTube video_id
 */
function addMarkersFromMapVisualization(mapVisualization, videoId) {
  // 先清除之前的標記
  clearMarkers();

  // 記錄目前影片 ID
  currentVideoId = videoId;

  // 遍歷路線點，新增標記
  const routes = mapVisualization.routes || [];
  routes.forEach(route => {
    if (!route.coordinates || route.coordinates.length !== 2) return;

    const [lon, lat] = route.coordinates;
    const marker = L.marker([lat, lon]).addTo(markersLayer);

    // 建立彈出視窗內容
    let popupContent = `<div class="marker-popup">
      <h3>${route.location}</h3>`;

    if (route.description) {
      popupContent += `<p>${route.description}</p>`;
    }

    if (route.timecode) {
      const timecodeUrl = createTimecodeUrl(videoId, route.timecode);
      const formattedTime = formatTimecode(route.timecode);
      popupContent += `<a href="${timecodeUrl}" target="_blank" class="timecode-link">
        觀看片段 ${formattedTime}
      </a>`;
    }

    popupContent += '</div>';

    // 設置彈出視窗
    marker.bindPopup(popupContent);
  });

  // 自適應地圖邊界
  if (markersLayer.getLayers().length > 0) {
    map.fitBounds(markersLayer.getBounds(), { padding: [20, 20] });
  }

  return markersLayer.getLayers().length;
}

/**
 * 獲取目前標記數量
 * @returns {number} 標記數量
 */
function getMarkersCount() {
  return markersLayer ? markersLayer.getLayers().length : 0;
}

/**
 * 獲取目前影片 ID
 * @returns {string|null} 影片 ID
 */
function getCurrentVideoId() {
  return currentVideoId;
}
