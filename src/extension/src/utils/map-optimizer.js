/**
 * map-optimization.js - 地圖性能優化模組
 * 包含標記聚類功能和延遲載入優化
 */

/* Global declarations */
var L = typeof L !== "undefined" ? L : null;
var MarkerClusterGroup =
  typeof L !== "undefined" && L.markerClusterGroup
    ? L.markerClusterGroup
    : null;

// 性能優化配置
var OPTIMIZATION_CONFIG = {
  // 標記聚類配置
  cluster: {
    enabled: true,
    maxClusterRadius: 80,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
    zoomToBoundsOnClick: true,
    // 自定義聚類圖標
    iconCreateFunction: function (cluster) {
      var childCount = cluster.getChildCount();
      var className = "marker-cluster-small";

      if (childCount > 50) {
        className = "marker-cluster-large";
      } else if (childCount > 10) {
        className = "marker-cluster-medium";
      }

      return new L.DivIcon({
        html: "<div><span>" + childCount + "</span></div>",
        className: "marker-cluster " + className,
        iconSize: new L.Point(40, 40),
      });
    },
  },

  // 延遲載入配置
  lazyLoad: {
    enabled: true,
    debounceDelay: 300,
    maxMarkersBeforeCluster: 50,
    tileLoadDelay: 100,
  },

  // 視圖管理配置
  viewport: {
    minZoom: 3,
    maxZoom: 18,
    defaultZoom: 10,
    fitBoundsPadding: [20, 20],
    maxBoundsZoom: 16,
  },
};

// 性能監控變數
var performanceMetrics = {
  markerCount: 0,
  clusterCount: 0,
  renderTime: 0,
  lastUpdate: null,
};

// 延遲執行工具函數
function debounce(func, wait) {
  var timeout;
  return function executedFunction() {
    var context = this;
    var args = arguments;
    var later = function () {
      timeout = null;
      func.apply(context, args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

/**
 * 創建優化的標記聚類群組
 * @param {Object} options - 覆蓋預設配置的選項
 * @returns {Object} Leaflet MarkerClusterGroup 實例
 */
function createOptimizedClusterGroup(options) {
  if (!L || !L.markerClusterGroup) {
    console.warn(
      "Leaflet MarkerCluster not available, falling back to regular LayerGroup",
    );
    return L.layerGroup();
  }

  var config = Object.assign({}, OPTIMIZATION_CONFIG.cluster, options || {});

  var clusterGroup = L.markerClusterGroup(config);

  // 添加聚類事件監聽器
  clusterGroup.on("clustermouseover", function (event) {
    // 滑鼠懸停時的優化處理
    if (event.layer && event.layer.getChildCount) {
      var childCount = event.layer.getChildCount();
      if (childCount > 100) {
        // 對大型聚類進行特殊處理
        event.layer.setOpacity(0.8);
      }
    }
  });

  clusterGroup.on("clustermouseout", function (event) {
    if (event.layer && event.layer.setOpacity) {
      event.layer.setOpacity(1);
    }
  });

  return clusterGroup;
}

/**
 * 批次添加標記到聚類群組
 * @param {Object} clusterGroup - 聚類群組
 * @param {Array} markers - 標記陣列
 * @param {Function} onProgress - 進度回調函數
 */
function addMarkersInBatches(clusterGroup, markers, onProgress) {
  if (!markers || markers.length === 0) return;

  var startTime = performance.now();
  var batchSize = Math.min(50, Math.max(10, Math.floor(markers.length / 10)));
  var currentIndex = 0;

  function processBatch() {
    var endIndex = Math.min(currentIndex + batchSize, markers.length);
    var batch = markers.slice(currentIndex, endIndex);

    // 添加這批標記
    batch.forEach(function (marker) {
      if (marker && typeof clusterGroup.addLayer === "function") {
        clusterGroup.addLayer(marker);
      }
    });

    currentIndex = endIndex;

    // 更新進度
    if (typeof onProgress === "function") {
      onProgress({
        processed: currentIndex,
        total: markers.length,
        percentage: Math.round((currentIndex / markers.length) * 100),
      });
    }

    // 繼續處理下一批或完成
    if (currentIndex < markers.length) {
      // 使用 requestAnimationFrame 來避免阻塞 UI
      if (typeof requestAnimationFrame !== "undefined") {
        requestAnimationFrame(processBatch);
      } else {
        setTimeout(processBatch, 1);
      }
    } else {
      // 完成時更新性能指標
      performanceMetrics.renderTime = performance.now() - startTime;
      performanceMetrics.markerCount = markers.length;
      performanceMetrics.lastUpdate = new Date();

      console.debug("Markers added in batches:", {
        total: markers.length,
        renderTime: performanceMetrics.renderTime.toFixed(2) + "ms",
        batches: Math.ceil(markers.length / batchSize),
      });
    }
  }

  // 開始處理第一批
  processBatch();
}

/**
 * 智能視圖調整函數
 * @param {Object} map - Leaflet 地圖實例
 * @param {Object} bounds - 邊界對象
 * @param {Object} options - 調整選項
 */
var smartFitBounds = debounce(function (map, bounds, options) {
  if (!map || !bounds || !bounds.isValid || !bounds.isValid()) return;

  try {
    var currentZoom = map.getZoom();
    var defaultOptions = {
      padding: OPTIMIZATION_CONFIG.viewport.fitBoundsPadding,
      maxZoom: OPTIMIZATION_CONFIG.viewport.maxBoundsZoom,
    };
    var fitOptions = Object.assign(defaultOptions, options || {});

    // 檢查是否需要調整
    var mapBounds = map.getBounds();
    if (mapBounds.contains(bounds)) {
      // 如果當前視圖已經包含所有標記，且 zoom 合理，則不調整
      if (
        currentZoom >= OPTIMIZATION_CONFIG.viewport.minZoom &&
        currentZoom <= OPTIMIZATION_CONFIG.viewport.maxZoom
      ) {
        return;
      }
    }

    // 先使地圖大小無效化，然後調整邊界
    if (typeof map.invalidateSize === "function") {
      map.invalidateSize();
    }

    map.fitBounds(bounds, fitOptions);
  } catch (error) {
    console.warn("Smart fit bounds failed:", error);
  }
}, OPTIMIZATION_CONFIG.lazyLoad.debounceDelay);

/**
 * 延遲載入地圖切片
 * @param {Object} map - Leaflet 地圖實例
 */
function optimizeTileLoading(map) {
  if (!map) return;

  // 添加切片載入優化
  map.on("movestart", function () {
    // 移動開始時暫停不必要的操作
    map._tilesToLoad = map._tilesToLoad || [];
  });

  var debouncedMoveEnd = debounce(function () {
    // 移動結束後，延遲載入切片
    setTimeout(function () {
      if (typeof map.invalidateSize === "function") {
        map.invalidateSize();
      }
    }, OPTIMIZATION_CONFIG.lazyLoad.tileLoadDelay);
  }, OPTIMIZATION_CONFIG.lazyLoad.debounceDelay);

  map.on("moveend", debouncedMoveEnd);

  // 優化縮放操作
  map.on("zoomstart", function () {
    // 縮放開始時準備優化
    performanceMetrics.zoomStartTime = performance.now();
  });

  map.on("zoomend", function () {
    // 縮放結束後的優化
    if (performanceMetrics.zoomStartTime) {
      var zoomTime = performance.now() - performanceMetrics.zoomStartTime;
      if (zoomTime > 1000) {
        // 如果縮放操作超過 1 秒，可能需要優化
        console.debug(
          "Slow zoom operation detected:",
          zoomTime.toFixed(2) + "ms",
        );
      }
      delete performanceMetrics.zoomStartTime;
    }
  });
}

/**
 * 獲取性能指標
 * @returns {Object} 性能指標對象
 */
function getPerformanceMetrics() {
  return Object.assign({}, performanceMetrics, {
    timestamp: new Date().toISOString(),
    config: OPTIMIZATION_CONFIG,
  });
}

/**
 * 重置性能指標
 */
function resetPerformanceMetrics() {
  performanceMetrics = {
    markerCount: 0,
    clusterCount: 0,
    renderTime: 0,
    lastUpdate: null,
  };
}

/**
 * 檢查是否應該使用聚類
 * @param {number} markerCount - 標記數量
 * @returns {boolean} 是否應該使用聚類
 */
function shouldUseCluster(markerCount) {
  return (
    OPTIMIZATION_CONFIG.cluster.enabled &&
    markerCount > OPTIMIZATION_CONFIG.lazyLoad.maxMarkersBeforeCluster
  );
}

// 將函數暴露到全域範圍
if (typeof window !== "undefined") {
  window.TrailTag = window.TrailTag || {};
  window.TrailTag.MapOptimization = {
    createOptimizedClusterGroup: createOptimizedClusterGroup,
    addMarkersInBatches: addMarkersInBatches,
    smartFitBounds: smartFitBounds,
    optimizeTileLoading: optimizeTileLoading,
    getPerformanceMetrics: getPerformanceMetrics,
    resetPerformanceMetrics: resetPerformanceMetrics,
    shouldUseCluster: shouldUseCluster,
    config: OPTIMIZATION_CONFIG,
  };

  // 建立便利的全域函數
  window.createOptimizedClusterGroup = createOptimizedClusterGroup;
  window.addMarkersInBatches = addMarkersInBatches;
  window.smartFitBounds = smartFitBounds;
}

// CSS 樣式，如果需要的話會自動注入
if (typeof document !== "undefined" && document.head) {
  var existingStyle = document.getElementById("trailtag-cluster-styles");
  if (!existingStyle) {
    var style = document.createElement("style");
    style.id = "trailtag-cluster-styles";
    style.textContent = `
      .marker-cluster-small {
        background-color: rgba(181, 226, 140, 0.8);
      }
      .marker-cluster-small div {
        background-color: rgba(110, 204, 57, 0.8);
      }

      .marker-cluster-medium {
        background-color: rgba(241, 211, 87, 0.8);
      }
      .marker-cluster-medium div {
        background-color: rgba(240, 194, 12, 0.8);
      }

      .marker-cluster-large {
        background-color: rgba(253, 156, 115, 0.8);
      }
      .marker-cluster-large div {
        background-color: rgba(241, 128, 23, 0.8);
      }

      .marker-cluster {
        background-clip: padding-box;
        border-radius: 20px;
      }
      .marker-cluster div {
        width: 30px;
        height: 30px;
        margin-left: 5px;
        margin-top: 5px;
        text-align: center;
        border-radius: 15px;
        font: 12px "Helvetica Neue", Arial, Helvetica, sans-serif;
      }
      .marker-cluster span {
        line-height: 30px;
      }
    `;
    document.head.appendChild(style);
  }
}
