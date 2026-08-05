/**
 * Live-backend integration test config (separate from the jest-expo unit suite).
 *
 * Runs in a plain Node environment with Node's real `fetch` — NOT jsdom and NOT
 * the RN fetch polyfill — so the PRODUCTION HttpClient/endpoints make real HTTP
 * calls to a running FastAPI backend + PostgreSQL. Orchestration (fresh DB,
 * migrate, start uvicorn) is done by scripts/run-integration.sh, which sets
 * DILCHAT_INTEGRATION_BASE_URL. The test FAILS loudly if that is unset/unreachable.
 */
module.exports = {
  testEnvironment: "node",
  roots: ["<rootDir>/integration"],
  testMatch: ["**/integration/**/*.test.ts"],
  setupFiles: ["<rootDir>/integration/setup.integration.ts"],
  moduleNameMapper: {
    "^expo-constants$": "<rootDir>/integration/expo-constants.stub.ts",
    "^@/(.*)$": "<rootDir>/src/$1",
  },
  transform: {
    "^.+\\.ts$": ["babel-jest", { configFile: "./integration/babel.config.integration.js" }],
  },
  testTimeout: 30000,
};
