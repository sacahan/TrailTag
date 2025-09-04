/**
 * Extension 服務模組 (Extension Services)
 *
 * 此模組包含 Chrome 擴充功能的外部服務整合：
 * - api.ts: TrailTag API 客戶端
 *   * 與 FastAPI 後端通訊的封裝層
 *   * 處理 YouTube 影片分析請求
 *   * 管理 SSE 連線與即時狀態更新
 *   * 提供 GeoJSON 結果擷取功能
 *
 * 服務層負責與外部 API 的所有通訊，
 * 為核心組件提供資料存取介面。
 */

export * from "./api";
