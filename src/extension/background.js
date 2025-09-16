/**
 * background.js - TrailTag Extension Background Script
 *
 * Handles badge notifications and tab monitoring for TrailTag availability
 */

// Badge states
const BADGE_STATES = {
  AVAILABLE: {
    text: "✌︎",
    color: "#4CAF50",
    title: "TrailTag 可用 - 可以分析此影片",
  },
  UNAVAILABLE: {
    text: "!",
    color: "#FF9800",
    title: "TrailTag 不可用 - 此影片沒有字幕",
  },
  CHECKING: {
    text: "...",
    color: "#2196F3",
    title: "TrailTag 檢查中...",
  },
  NOT_YOUTUBE: {
    text: "",
    color: "",
    title: "TrailTag - 旅遊影片地圖化",
  },
};

// Current state tracking
let currentState = {};

/**
 * Update badge for a specific tab
 */
function updateBadge(tabId, state) {
  if (!BADGE_STATES[state]) {
    console.warn("Unknown badge state:", state);
    return;
  }

  const badgeState = BADGE_STATES[state];

  // Update badge text
  chrome.action.setBadgeText({
    tabId: tabId,
    text: badgeState.text,
  });

  // Update badge color
  if (badgeState.color) {
    chrome.action.setBadgeBackgroundColor({
      tabId: tabId,
      color: badgeState.color,
    });
  }

  // Update title
  chrome.action.setTitle({
    tabId: tabId,
    title: badgeState.title,
  });

  // Store current state
  currentState[tabId] = state;

  console.log(`Badge updated for tab ${tabId}: ${state}`);
}

/**
 * Check if URL is a YouTube video page
 */
function isYouTubeVideo(url) {
  if (!url) return false;

  try {
    const urlObj = new URL(url);
    return (
      urlObj.hostname === "www.youtube.com" &&
      urlObj.pathname === "/watch" &&
      urlObj.searchParams.has("v")
    );
  } catch {
    return false;
  }
}

/**
 * Extract video ID from YouTube URL
 */
function extractVideoId(url) {
  try {
    const urlObj = new URL(url);
    return urlObj.searchParams.get("v");
  } catch {
    return null;
  }
}

/**
 * Check subtitle availability for a video
 */
async function checkSubtitleAvailability(videoId) {
  try {
    // Use the same API endpoint as the subtitle detector
    const API_BASE_URL = "http://localhost:8010"; // Default API URL
    const response = await fetch(
      `${API_BASE_URL}/api/videos/${videoId}/subtitles/check`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      },
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    return data.available === true;
  } catch (error) {
    console.error("Failed to check subtitle availability:", error);
    return false;
  }
}

/**
 * Handle tab updates
 */
async function handleTabUpdate(tabId, changeInfo, tab) {
  // Only process when URL changes or tab is loaded
  if (!changeInfo.url && changeInfo.status !== "complete") {
    return;
  }

  const url = tab.url || changeInfo.url;

  if (!isYouTubeVideo(url)) {
    // Not a YouTube video page
    updateBadge(tabId, "NOT_YOUTUBE");
    return;
  }

  const videoId = extractVideoId(url);
  if (!videoId) {
    updateBadge(tabId, "NOT_YOUTUBE");
    return;
  }

  // Show checking state
  updateBadge(tabId, "CHECKING");

  // Check subtitle availability
  const isAvailable = await checkSubtitleAvailability(videoId);

  // Update badge based on result
  updateBadge(tabId, isAvailable ? "AVAILABLE" : "UNAVAILABLE");
}

/**
 * Handle tab activation
 */
function handleTabActivated(activeInfo) {
  const tabId = activeInfo.tabId;

  // Get current tab info and update badge
  chrome.tabs.get(tabId, (tab) => {
    if (chrome.runtime.lastError) {
      console.error("Error getting tab info:", chrome.runtime.lastError);
      return;
    }

    handleTabUpdate(tabId, { status: "complete" }, tab);
  });
}

/**
 * Handle tab removal
 */
function handleTabRemoved(tabId) {
  // Clean up stored state
  delete currentState[tabId];
}

/**
 * Handle messages from content script
 */
function handleMessage(message, sender, sendResponse) {
  if (!sender.tab) return;

  const tabId = sender.tab.id;

  switch (message.type) {
    case "VIDEO_CHANGED":
      // Video changed on the page, recheck
      if (message.videoId) {
        handleTabUpdate(tabId, { url: sender.tab.url }, sender.tab);
      } else {
        updateBadge(tabId, "NOT_YOUTUBE");
      }
      break;

    case "SUBTITLE_STATUS":
      // Direct subtitle status from content script
      const state = message.available ? "AVAILABLE" : "UNAVAILABLE";
      updateBadge(tabId, state);
      break;

    case "GET_BADGE_STATE":
      // Return current badge state
      sendResponse({ state: currentState[tabId] || "NOT_YOUTUBE" });
      break;
  }
}

// Register event listeners
chrome.tabs.onUpdated.addListener(handleTabUpdate);
chrome.tabs.onActivated.addListener(handleTabActivated);
chrome.tabs.onRemoved.addListener(handleTabRemoved);
chrome.runtime.onMessage.addListener(handleMessage);

// Initialize badge for all existing tabs when extension starts
chrome.tabs.query({}, (tabs) => {
  tabs.forEach((tab) => {
    if (tab.id && tab.url) {
      handleTabUpdate(tab.id, { status: "complete" }, tab);
    }
  });
});

console.log("TrailTag background script initialized");
