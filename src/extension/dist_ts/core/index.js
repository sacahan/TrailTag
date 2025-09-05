/**
 * Extension 核心模組 (Core Extension Components)
 *
 * 此模組包含 Chrome 擴充功能的核心組件：
 * - map-renderer.ts: Leaflet 地圖渲染引擎
 *   * YouTube 影片頁面地圖顯示
 *   * GeoJSON 路線與 POI 可視化
 *   * 互動式地圖控制與動畫
 *
 * - popup-controller.ts: 擴充功能彈出視窗控制器
 *   * 使用者介面邏輯與事件處理
 *   * API 狀態管理與進度顯示
 *   * 錯誤處理與使用者回饋
 *
 * - subtitle-detector.ts: 字幕偵測與警告系統
 *   * 自動偵測 YouTube 影片字幕可用性
 *   * 提供字幕缺失警告與建議
 *   * 支援多語言字幕檢測
 *
 * 這些核心組件負責擴充功能的主要業務邏輯，
 * 與 YouTube DOM 互動並提供地圖化功能。
 */
export * from "./map-renderer";
export * from "./popup-controller";
export * from "./subtitle-detector";
