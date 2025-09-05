/**
 * subtitle-checker.ts - 字幕檢測與用戶提示系統
 *
 * 主要功能：
 * - 檢測 YouTube 影片字幕可用性
 * - 提供友善的用戶提示和錯誤處理
 * - 與後端 API 整合進行字幕狀態檢查
 * - 支援手動字幕和自動字幕的區分
 */
import { API_BASE_URL, fetchWithRetry } from "../services/api.js";
/**
 * 字幕檢查器類別
 * 負責檢測影片字幕狀態並提供用戶介面提示
 */
export class SubtitleChecker {
  /**
   * 初始化字幕檢查器
   * @param statusElementId 顯示狀態的 DOM 元素 ID
   */
  constructor(statusElementId = "subtitle-status") {
    this.statusElement = null;
    this.lastCheckedVideoId = null;
    this.lastCheckResult = null;
    this.statusElement = document.getElementById(statusElementId);
    this.setupStatusDisplay();
  }
  /**
   * 設定狀態顯示區域
   */
  setupStatusDisplay() {
    if (!this.statusElement) {
      // 如果狀態元素不存在，創建一個
      this.statusElement = document.createElement("div");
      this.statusElement.id = "subtitle-status";
      this.statusElement.className = "subtitle-status-container";
      // 嘗試插入到適當位置（在分析按鈕之前）
      const analyzeButton = document.getElementById("analyzeBtn");
      if (analyzeButton && analyzeButton.parentNode) {
        analyzeButton.parentNode.insertBefore(
          this.statusElement,
          analyzeButton,
        );
      } else {
        document.body.appendChild(this.statusElement);
      }
    }
  }
  /**
   * 檢查指定影片的字幕可用性
   * @param videoId YouTube 影片 ID
   * @returns Promise<SubtitleCheckResult>
   */
  async checkSubtitleAvailability(videoId) {
    if (!videoId) {
      return {
        success: false,
        error: "Video ID is required",
        user_message: "請提供有效的影片 ID",
      };
    }
    // 如果是同一個影片且最近檢查過，返回快取結果
    if (this.lastCheckedVideoId === videoId && this.lastCheckResult) {
      console.log("使用快取的字幕檢查結果");
      return this.lastCheckResult;
    }
    try {
      this.showLoadingStatus();
      const url = `${API_BASE_URL}/api/videos/${videoId}/subtitles/check`;
      const response = await fetchWithRetry(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }
      const subtitleStatus = await response.json();
      const result = {
        success: true,
        status: subtitleStatus,
        user_message: this.generateUserMessage(subtitleStatus),
      };
      // 快取結果
      this.lastCheckedVideoId = videoId;
      this.lastCheckResult = result;
      return result;
    } catch (error) {
      console.error("字幕可用性檢查失敗:", error);
      const result = {
        success: false,
        error: error instanceof Error ? error.message : String(error),
        user_message: "無法檢查影片字幕狀態，請稍後再試",
      };
      this.lastCheckedVideoId = videoId;
      this.lastCheckResult = result;
      return result;
    }
  }
  /**
   * 根據字幕狀態生成用戶友善的訊息
   * @param status 字幕狀態
   * @returns 用戶訊息
   */
  generateUserMessage(status) {
    if (!status.available) {
      return "⚠️ 此影片沒有可用的字幕或自動字幕，無法進行分析";
    }
    const messages = ["✅ 字幕檢測通過"];
    if (status.manual_subtitles.length > 0) {
      const langs = status.manual_subtitles.slice(0, 3).join(", ");
      messages.push(`📝 手動字幕: ${langs}`);
      if (status.manual_subtitles.length > 3) {
        messages.push(`等 ${status.manual_subtitles.length} 種語言`);
      }
    }
    if (
      status.auto_captions.length > 0 &&
      status.manual_subtitles.length === 0
    ) {
      const langs = status.auto_captions.slice(0, 3).join(", ");
      messages.push(`🤖 自動字幕: ${langs}`);
      if (status.auto_captions.length > 3) {
        messages.push(`等 ${status.auto_captions.length} 種語言`);
      }
    }
    if (status.confidence_score > 0) {
      const confidence = Math.round(status.confidence_score * 100);
      messages.push(`信心度: ${confidence}%`);
    }
    return messages.join(" | ");
  }
  /**
   * 顯示字幕檢查結果在 UI 上
   * @param result 檢查結果
   * @param autoHide 是否自動隱藏（毫秒，0 表示不自動隱藏）
   */
  displayResult(result, autoHide = 0) {
    if (!this.statusElement) {
      console.warn("字幕狀態顯示元素未找到");
      return;
    }
    // 清除之前的狀態
    this.statusElement.className = "subtitle-status-container";
    if (result.success && result.status) {
      // 成功檢查
      if (result.status.available) {
        this.statusElement.className += " status-success";
        // 字幕可用時隱藏狀態顯示，不需要顯示詳細資訊
        this.hideStatus();
        return;
      } else {
        this.statusElement.className += " status-warning";
      }
    } else {
      // 檢查失敗
      this.statusElement.className += " status-error";
    }
    // 只在字幕不可用或檢查失敗時顯示提示
    const message =
      result.status && !result.status.available
        ? "⚠️ 此影片沒有可用的字幕，無法進行分析"
        : result.user_message || "字幕檢查失敗";
    this.statusElement.innerHTML = `
      <div class="subtitle-status-content">
        <div class="status-message">${message}</div>
        <div class="status-details">建議選擇有字幕的影片</div>
      </div>
    `;
    // 如果設定了自動隱藏
    if (autoHide > 0) {
      setTimeout(() => {
        this.hideStatus();
      }, autoHide);
    }
  }
  /**
   * 顯示載入中狀態
   */
  showLoadingStatus() {
    if (!this.statusElement) return;
    this.statusElement.className = "subtitle-status-container status-loading";
    this.statusElement.innerHTML = `
      <div class="subtitle-status-content">
        <div class="status-message">🔍 檢查字幕可用性中...</div>
        <div class="status-details">請稍候</div>
      </div>
    `;
  }
  /**
   * 隱藏狀態顯示
   */
  hideStatus() {
    if (this.statusElement) {
      this.statusElement.style.display = "none";
    }
  }
  /**
   * 顯示狀態顯示
   */
  showStatus() {
    if (this.statusElement) {
      this.statusElement.style.display = "block";
    }
  }
  /**
   * 檢查當前影片並顯示結果
   * @param videoId 影片 ID
   * @returns Promise<boolean> 是否可以進行分析
   */
  async checkCurrentVideo(videoId) {
    const result = await this.checkSubtitleAvailability(videoId);
    this.displayResult(result);
    // 回傳是否可以進行分析
    return result.success && result.status?.available === true;
  }
  /**
   * 獲取上次檢查的結果
   */
  getLastResult() {
    return this.lastCheckResult;
  }
  /**
   * 清除快取的檢查結果
   */
  clearCache() {
    this.lastCheckedVideoId = null;
    this.lastCheckResult = null;
  }
  /**
   * 靜態方法：快速檢查影片字幕可用性（不創建實例）
   * @param videoId 影片 ID
   * @returns Promise<boolean>
   */
  static async quickCheck(videoId) {
    try {
      const url = `${API_BASE_URL}/api/videos/${videoId}/subtitles/check`;
      const response = await fetchWithRetry(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      });
      if (!response.ok) return false;
      const status = await response.json();
      return status.available;
    } catch {
      return false;
    }
  }
}
// 註冊到全域 TrailTag 物件
if (typeof window !== "undefined") {
  window.TrailTag = window.TrailTag || {};
  window.TrailTag.SubtitleChecker = SubtitleChecker;
}
export default SubtitleChecker;
