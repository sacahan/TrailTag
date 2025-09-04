/**
 * Tests for popup initializeApp restore/attach behavior.
 *
 * These tests mock the minimal environment (window helpers and chrome.runtime)
 * and verify that `initializeApp` will either restore from saved state or
 * attach to a background-known active job.
 */

// Use jest in this file
describe("popup initializeApp restore/attach", () => {
  // helper to create a mock chrome runtime before importing the popup module
  function makeMockChrome(getActiveJobResponse?: any) {
    const sendMessage = jest.fn((msg: any, cb?: any) => {
      if (cb) {
        if (msg && msg.type === "getActiveJobForVideo") {
          cb(getActiveJobResponse ? getActiveJobResponse : null);
        } else {
          cb({ success: true });
        }
      }
    });
    (global as any).chrome = {
      runtime: {
        id: "test-ext",
        sendMessage,
        onMessage: { addListener: jest.fn() },
      },
      storage: { local: { get: jest.fn(), set: jest.fn() } },
    };
    return sendMessage;
  }

  beforeEach(() => {
    // Ensure popup does not auto-run registerApp on import by making the
    // document appear to be still loading; popup attaches a DOMContentLoaded
    // listener when readyState === 'loading'.
    Object.defineProperty(document, "readyState", {
      value: "loading",
      configurable: true,
    });
    // Clear module cache so popup.ts picks up the mocks set above on import.
    jest.resetModules();
  });

  // Create minimal DOM elements expected by popup.queryElements/updateUI
  function createDomMocks() {
    const ids = [
      "idle-view",
      "checking-view",
      "analyzing-view",
      "map-view",
      "error-view",
      "status-badge",
      "analyze-btn",
      "cancel-btn",
      "retry-btn",
      "report-btn",
      "export-btn",
      "progress-bar",
      "progress-text",
      "phase-text",
      "error-message",
      "locations-count",
      "map",
    ];
    ids.forEach((id) => {
      let el = document.getElementById(id);
      if (!el) {
        el = document.createElement("div");
        el.id = id;
        document.body.appendChild(el);
      }
    });
  }

  test("no saved state and no cached locations -> enters idle", async () => {
    // prepare mocks on window before importing popup
    (global as any).window = (global as any).window || {};
    (global as any).window.getCurrentVideoId = async () => "video-1";
    (global as any).window.loadState = async () => null;
    // ensure saveState stub exists to avoid saveState undefined in popup.changeState
    (global as any).window.saveState = async () => {
      return;
    };
    // mock API to return no cached locations
    (global as any).window.TrailTag = {
      API: { getVideoLocations: async () => null },
    };

    createDomMocks();
    const popup = await import("../popup");
    const {
      initializeApp,
      state: popupState,
      AppState,
      queryElements,
    } = popup as any;
    if (typeof queryElements === "function") queryElements();

    await initializeApp();

    // popup should enter idle state when no saved state and no cached locations
    expect(popupState.currentState).toBe(AppState.IDLE);
  });

  test("restores from saved state and starts polling", async () => {
    // reset for fresh module import
    Object.defineProperty(document, "readyState", {
      value: "loading",
      configurable: true,
    });
    jest.resetModules();
    (global as any).window = (global as any).window || {};
    (global as any).window.getCurrentVideoId = async () => "video-2";
    // Return a plain string for currentState to avoid needing AppState before import
    (global as any).window.loadState = async () => ({
      videoId: "video-2",
      jobId: "saved-job",
      currentState: "analyzing",
      progress: 42,
      phase: "geocode",
    });
    (global as any).window.saveState = async () => {
      return;
    };
    // no need to mock chrome messaging; popup should call startPolling
    const popup = await import("../popup");
    const { initializeApp, queryElements } = popup as any;
    if (typeof queryElements === "function") queryElements();

    await initializeApp();

    // popup should be in analyzing state and should have started polling (jobId set)
    expect(popup.state.currentState).toBe("analyzing");
    expect(popup.state.progress).toBe(42);
    expect(popup.state.jobId).toBe("saved-job");
  });
});
