module.exports = {
  preset: "ts-jest",
  testEnvironment: "jsdom",
  roots: ["<rootDir>"],
  rootDir: "..",
  setupFilesAfterEnv: ["<rootDir>/config/jest.setup.js"],
  // Only run compiled JS tests under dist_ts to avoid ts-jest compiling source tests
  testMatch: ["**/dist_ts/**/__tests__/**/*.test.(js)"],
  transform: {
    "^.+\\.[tj]s$": ["ts-jest", { tsconfig: "config/tsconfig.json" }],
  },
  moduleFileExtensions: ["ts", "js", "json", "node"],
};
