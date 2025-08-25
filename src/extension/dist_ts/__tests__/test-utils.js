/* Test utilities for popup.ts (TypeScript) */
let helpers = null;
if (typeof window !== "undefined") {
  window.__registerPopupTestingHelpers = function (h) {
    helpers = h;
  };
}
export function getHelpers() {
  return helpers;
}
export function setState(patch) {
  if (helpers && helpers.setState) return helpers.setState(patch);
}
export function getState() {
  if (helpers && helpers.getState) return helpers.getState();
  return null;
}
export function startPolling(jobId) {
  if (helpers && helpers.startPolling) return helpers.startPolling(jobId);
}
export function stopPolling() {
  if (helpers && helpers.stopPolling) return helpers.stopPolling();
}
