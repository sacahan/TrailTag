/* Test utilities for popup.ts (TypeScript) */

declare global {
  interface Window {
    __registerPopupTestingHelpers?: ((arg: any) => void) | any;
  }
}

let helpers: any = null;

if (typeof window !== "undefined") {
  window.__registerPopupTestingHelpers = function (h: any) {
    helpers = h;
  };
}

export function getHelpers() {
  return helpers;
}
export function setState(patch: any) {
  if (helpers && helpers.setState) return helpers.setState(patch);
}
export function getState() {
  if (helpers && helpers.getState) return helpers.getState();
  return null;
}
export function startPolling(jobId?: any) {
  if (helpers && helpers.startPolling) return helpers.startPolling(jobId);
}
export function stopPolling() {
  if (helpers && helpers.stopPolling) return helpers.stopPolling();
}
