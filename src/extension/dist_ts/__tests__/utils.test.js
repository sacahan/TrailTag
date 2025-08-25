const fs = require("fs");
const path = require("path");
function findCompiled(...parts) {
  const candidates = [
    path.resolve(__dirname, "..", "dist_ts", ...parts),
    path.resolve(__dirname, "..", "..", "dist_ts", ...parts),
    path.resolve(__dirname, "..", ...parts),
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  throw new Error("compiled file not found: " + parts.join("/"));
}
const srcUtils = findCompiled("utils.js");
const utilsMod = require(srcUtils);
global.saveState =
  utilsMod.saveState || (utilsMod.default && utilsMod.default.saveState);
global.loadState =
  utilsMod.loadState || (utilsMod.default && utilsMod.default.loadState);
global.getCurrentVideoId =
  utilsMod.getCurrentVideoId ||
  (utilsMod.default && utilsMod.default.getCurrentVideoId);
describe("utils (ts build) fallback behaviors", () => {
  test("saveState/loadState fallback when chrome.storage missing", async () => {
    // ensure chrome.storage not defined
    global.chrome = undefined;
    await expect(saveState({ a: 1 })).resolves.toBeUndefined();
    const loaded = await loadState();
    // loaded may be null or an object depending on test environment (localStorage presence)
    expect(loaded === null || typeof loaded === "object").toBeTruthy();
  });
  test("getCurrentVideoId returns null when chrome.tabs.query missing", async () => {
    global.chrome = undefined;
    const id = await getCurrentVideoId();
    expect(id).toBeNull();
  });
});
export {};
