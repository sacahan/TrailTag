module.exports = {
  preset: "ts-jest",
  testEnvironment: "jsdom",
  roots: ["<rootDir>"],
  // Only run compiled JS tests under dist_ts to avoid ts-jest compiling source tests
  testMatch: ["**/dist_ts/**/__tests__/**/*.test.(js)"],
  transform: {
    "^.+\\.[tj]s$": ["ts-jest"],
  },
  moduleFileExtensions: ["ts", "js", "json", "node"],
  globals: {
    "ts-jest": {
      tsconfig: "tsconfig.json",
    },
  },
};
