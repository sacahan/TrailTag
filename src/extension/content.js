/**
 * content.js - TrailTag Extension Content Script
 *
 * Monitors YouTube page changes and communicates with background script
 */

let currentVideoId = null;
let observer = null;

/**
 * Extract video ID from current page URL
 */
function getCurrentVideoId() {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get("v");
}

/**
 * Check if we're on a YouTube video page
 */
function isVideoPage() {
  return window.location.pathname === "/watch" && getCurrentVideoId();
}

/**
 * Notify background script about video changes
 */
function notifyVideoChange() {
  const videoId = getCurrentVideoId();

  if (videoId !== currentVideoId) {
    currentVideoId = videoId;

    // Send message to background script
    chrome.runtime
      .sendMessage({
        type: "VIDEO_CHANGED",
        videoId: videoId,
        url: window.location.href,
      })
      .catch(() => {
        // Ignore errors if background script is not ready
      });

    console.log("Video changed to:", videoId);
  }
}

/**
 * Monitor URL changes (for single-page app navigation)
 */
function setupUrlMonitoring() {
  // Initial check
  notifyVideoChange();

  // Monitor URL changes using history API
  const originalPushState = history.pushState;
  const originalReplaceState = history.replaceState;

  history.pushState = function (...args) {
    originalPushState.apply(history, args);
    setTimeout(notifyVideoChange, 100);
  };

  history.replaceState = function (...args) {
    originalReplaceState.apply(history, args);
    setTimeout(notifyVideoChange, 100);
  };

  // Listen for popstate events
  window.addEventListener("popstate", () => {
    setTimeout(notifyVideoChange, 100);
  });
}

/**
 * Monitor DOM changes for video player updates
 */
function setupDOMMonitoring() {
  // Disconnect existing observer
  if (observer) {
    observer.disconnect();
  }

  // Watch for changes in the video container
  const targetNode = document.querySelector("#primary") || document.body;

  observer = new MutationObserver((mutations) => {
    let shouldCheck = false;

    mutations.forEach((mutation) => {
      // Check if video-related elements changed
      if (mutation.type === "childList") {
        const hasVideoElements = Array.from(mutation.addedNodes).some(
          (node) =>
            node.nodeType === Node.ELEMENT_NODE &&
            node.querySelector &&
            (node.querySelector("video") ||
              node.querySelector("[data-video-id]") ||
              node.classList?.contains("html5-video-player")),
        );

        if (hasVideoElements) {
          shouldCheck = true;
        }
      }
    });

    if (shouldCheck) {
      setTimeout(notifyVideoChange, 500);
    }
  });

  observer.observe(targetNode, {
    childList: true,
    subtree: true,
  });
}

/**
 * Enhanced subtitle detection using DOM
 */
function checkSubtitlesInDOM() {
  // Check for subtitle/caption buttons
  const subtitleButtons = document.querySelectorAll(
    [
      ".ytp-subtitles-button",
      ".ytp-caption-button",
      '[aria-label*="字幕"]',
      '[aria-label*="Subtitles"]',
      '[aria-label*="Captions"]',
    ].join(","),
  );

  let hasSubtitles = false;

  subtitleButtons.forEach((button) => {
    // Check if button is enabled (not disabled)
    if (
      !button.disabled &&
      !button.classList.contains("ytp-subtitles-button-disabled")
    ) {
      hasSubtitles = true;
    }
  });

  // Also check if there are subtitle tracks available
  const video = document.querySelector("video");
  if (video && video.textTracks) {
    for (let i = 0; i < video.textTracks.length; i++) {
      const track = video.textTracks[i];
      if (track.kind === "subtitles" || track.kind === "captions") {
        hasSubtitles = true;
        break;
      }
    }
  }

  return hasSubtitles;
}

/**
 * Monitor subtitle availability changes
 */
function monitorSubtitleChanges() {
  let lastSubtitleState = null;

  const checkSubtitles = () => {
    if (!isVideoPage()) return;

    const hasSubtitles = checkSubtitlesInDOM();

    if (hasSubtitles !== lastSubtitleState) {
      lastSubtitleState = hasSubtitles;

      // Notify background script
      chrome.runtime
        .sendMessage({
          type: "SUBTITLE_STATUS",
          available: hasSubtitles,
          videoId: getCurrentVideoId(),
        })
        .catch(() => {
          // Ignore errors if background script is not ready
        });

      console.log("Subtitle status changed:", hasSubtitles);
    }
  };

  // Check immediately
  setTimeout(checkSubtitles, 1000);

  // Set up periodic checking
  setInterval(checkSubtitles, 5000);

  // Also check when video player changes
  const videoObserver = new MutationObserver(() => {
    setTimeout(checkSubtitles, 1000);
  });

  const playerContainer = document.querySelector("#movie_player");
  if (playerContainer) {
    videoObserver.observe(playerContainer, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["class"],
    });
  }
}

/**
 * Initialize content script
 */
function initialize() {
  console.log("TrailTag content script initialized");

  // Set up monitoring
  setupUrlMonitoring();
  setTimeout(setupDOMMonitoring, 1000);
  setTimeout(monitorSubtitleChanges, 2000);

  // Handle page reload
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      setTimeout(notifyVideoChange, 1000);
    });
  }
}

// Start initialization
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initialize);
} else {
  initialize();
}

// Handle extension updates
chrome.runtime.onConnect.addListener((port) => {
  console.log("Extension reconnected");
});
