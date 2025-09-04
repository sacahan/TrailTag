/**
 * TrailTag Chrome Extension - 主要模組索引
 *
 * TrailTag Chrome 擴充功能的主要入口點，用於將 YouTube 旅遊 Vlog
 * 轉換為互動式地圖資料與路線可視化。
 *
 * 架構組織：
 * - core/: 核心功能 (地圖渲染、彈出視窗控制、字幕偵測)
 * - services/: 外部服務整合 (API 客戶端、後端通訊)
 * - utils/: 工具函式 (輔助函式、最佳化工具)
 *
 * 主要功能：
 * - YouTube 影片頁面整合
 * - 即時地圖資料可視化
 * - 字幕可用性自動偵測
 * - 與 FastAPI 後端的無縫通訊
 * - Server-Sent Events 即時進度更新
 */

export * from "./core";
export * from "./services";
export * from "./utils";
