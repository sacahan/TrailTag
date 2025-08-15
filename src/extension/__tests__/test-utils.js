// Test-only helpers for popup tests. This file lives in __tests__ and is not shipped in the extension.
let helpers = null;

module.exports = {
  register: (h) => { helpers = h; },
  setState: (patch) => { if (helpers && helpers.setState) return helpers.setState(patch); },
  getState: () => { if (helpers && helpers.getState) return helpers.getState(); return null; },
  startPolling: (jobId) => { if (helpers && helpers.startPolling) return helpers.startPolling(jobId); },
  stopPolling: () => { if (helpers && helpers.stopPolling) return helpers.stopPolling(); }
};
