// @ts-nocheck
import * as TestUtils from "./test-utils";
const fs = require("fs");
const path = require("path");

function findCompiled(...parts) {
  const candidates = [
    path.resolve(__dirname, "..", "..", "src", ...parts),
    path.resolve(__dirname, "..", "dist_ts", ...parts),
    path.resolve(__dirname, "..", "..", "dist_ts", ...parts),
    path.resolve(__dirname, "..", ...parts),
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  throw new Error("compiled file not found: " + parts.join("/"));
}
const srcUtils = findCompiled("utils", "helpers.js");
const utilsMod = require(srcUtils);
global.getCurrentVideoId =
  utilsMod.getCurrentVideoId ||
  (utilsMod.default && utilsMod.default.getCurrentVideoId);

describe("getCurrentVideoId with chrome.tabs mock", () => {
  test("returns extracted video id from active tab url", async () => {
    global.chrome = {
      tabs: {
        query: (opts, cb) =>
          cb([{ id: 1, url: "https://www.youtube.com/watch?v=abcdEFGhijk" }]),
      },
      runtime: { lastError: null },
    };
    const id = await getCurrentVideoId();
    expect(id).toBe("abcdEFGhijk");
  });
});
