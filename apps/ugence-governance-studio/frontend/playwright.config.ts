import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";

// Prefer an explicit override, then the environment's pre-installed Chromium if
// present; otherwise let Playwright resolve its own installed browser (CI runs
// `npx playwright install chromium`).
const PREINSTALLED = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const chromiumExecutable =
  process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ||
  (existsSync(PREINSTALLED) ? PREINSTALLED : undefined);

// End-to-end against the REAL P3B backend (§29). Two managed servers:
//  1. the FastAPI backend (uvicorn) with CORS opened to the preview origin;
//  2. the built frontend served by `vite preview`.
// The frontend's default API base URL (127.0.0.1:8000) matches the backend.
const REPO = "../../..";
const PYTHONPATH = [
  `${REPO}/packages/capabilities/agent-workforce-composer/src`,
  `${REPO}/packages/tooling/policy-workflow-compiler/src`,
  `${REPO}/apps/ugence-governance-studio/backend/src`,
].join(":");

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "off",
    screenshot: "off",
  },
  // Use the environment's pre-installed Chromium (avoids a version-pinned
  // download). Override via PLAYWRIGHT_CHROMIUM_EXECUTABLE when running elsewhere.
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        launchOptions: chromiumExecutable ? { executablePath: chromiumExecutable } : {},
      },
    },
  ],
  webServer: [
    {
      command: `bash -c "PYTHONPATH=${PYTHONPATH} UGS_API_CORS_ALLOWED_ORIGINS=http://127.0.0.1:4173 python -m ugence_governance_studio_api.cli serve --host 127.0.0.1 --port 8000"`,
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "npm run preview",
      url: "http://127.0.0.1:4173",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});
