/**
 * Extension 工具模組 (Extension Utilities)
 *
 * 此模組包含 Chrome 擴充功能的工具函式與最佳化組件：
 * - helpers.ts: 通用工具函式
 *   * YouTube URL 解析與驗證
 *   * DOM 操作與事件處理輔助函式
 *   * 資料格式轉換與驗證工具
 *   * 錯誤處理與日誌記錄輔助
 *
 * - map-optimizer.js: 地圖渲染最佳化工具
 *   * Leaflet 地圖性能最佳化
 *   * 大量標記點的聚類處理
 *   * 動態載入與記憶體管理
 *
 * 工具模組提供可重用的輔助功能，
 * 支援擴充功能的各個核心組件。
 */

export * from "./helpers";
export * from "./badge-manager";
// map-optimizer.js 是 JavaScript 檔案，需要個別載入
