// Test utilities for popup.js
// This module installs a global registration function that popup.js can call to expose
// internal helpers to tests without polluting production globals.

let helpers = null;

// popup.js will call window.__registerPopupTestingHelpers({ setState, getState, startPolling, stopPolling })
if (typeof window !== 'undefined') {
  window.__registerPopupTestingHelpers = function(h) {
    helpers = h;
  };
}

module.exports = {
  // Returns the helpers object (may be null until popup is loaded)
  getHelpers: () => helpers,
  setState: (patch) => { if (helpers && helpers.setState) return helpers.setState(patch); },
  getState: () => { if (helpers && helpers.getState) return helpers.getState(); return null; },
  startPolling: (jobId) => { if (helpers && helpers.startPolling) return helpers.startPolling(jobId); },
  stopPolling: () => { if (helpers && helpers.stopPolling) return helpers.stopPolling(); }
};
