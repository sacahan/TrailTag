/**
 * badge-manager.ts - Badge Management Utilities
 *
 * Handles communication with background script for badge updates
 */

export interface BadgeState {
  state: "AVAILABLE" | "UNAVAILABLE" | "CHECKING" | "NOT_YOUTUBE";
}

/**
 * Badge Manager Class
 * Coordinates badge updates between popup and background script
 */
export class BadgeManager {
  /**
   * Get current badge state from background script
   */
  static async getBadgeState(): Promise<BadgeState | null> {
    try {
      return new Promise((resolve) => {
        chrome.runtime.sendMessage(
          { type: "GET_BADGE_STATE" },
          (response: BadgeState) => {
            if (chrome.runtime.lastError) {
              console.error("Badge state error:", chrome.runtime.lastError);
              resolve(null);
            } else {
              resolve(response);
            }
          },
        );
      });
    } catch (error) {
      console.error("Failed to get badge state:", error);
      return null;
    }
  }

  /**
   * Notify background script of subtitle status
   */
  static async updateSubtitleStatus(
    videoId: string,
    available: boolean,
  ): Promise<void> {
    try {
      chrome.runtime.sendMessage({
        type: "SUBTITLE_STATUS",
        available: available,
        videoId: videoId,
      });
    } catch (error) {
      console.error("Failed to update subtitle status:", error);
    }
  }

  /**
   * Force refresh of badge state for current video
   */
  static async refreshBadge(videoId: string): Promise<void> {
    try {
      chrome.runtime.sendMessage({
        type: "VIDEO_CHANGED",
        videoId: videoId,
        url: window.location?.href,
      });
    } catch (error) {
      console.error("Failed to refresh badge:", error);
    }
  }

  /**
   * Check if current badge state indicates TrailTag is available
   */
  static async isTrailTagAvailable(): Promise<boolean> {
    const badgeState = await this.getBadgeState();
    return badgeState?.state === "AVAILABLE";
  }

  /**
   * Get user-friendly message based on badge state
   */
  static getBadgeMessage(state: string): string {
    switch (state) {
      case "AVAILABLE":
        return "✅ TrailTag 可用 - 可以分析此影片";
      case "UNAVAILABLE":
        return "⚠️ TrailTag 不可用 - 此影片沒有字幕";
      case "CHECKING":
        return "🔍 TrailTag 檢查中...";
      case "NOT_YOUTUBE":
        return "ℹ️ 請在 YouTube 影片頁面使用 TrailTag";
      default:
        return "❓ TrailTag 狀態未知";
    }
  }
}

// Global export for backward compatibility
declare global {
  interface Window {
    TrailTag?: any;
  }
}

if (typeof window !== "undefined") {
  window.TrailTag = window.TrailTag || {};
  window.TrailTag.BadgeManager = BadgeManager;
}

export default BadgeManager;
