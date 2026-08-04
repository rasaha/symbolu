#!/usr/bin/env node
/**
 * Guard: no hardcoded production API endpoint may be committed in the mobile
 * source. The base URL must come from configuration (DILCHAT_API_BASE_URL via
 * app.config.js -> extra.apiBaseUrl). A LOCAL dev fallback (localhost / 127.0.0.1
 * / 10.0.2.2) is allowed. Any other absolute http(s) URL in src/ or app/ fails.
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const SCAN_DIRS = ["src", "app"];
const URL_RE = /https?:\/\/[^\s"'`)]+/g;
const ALLOWED_HOST_RE = /^(localhost|127\.0\.0\.1|10\.0\.2\.2)(:\d+)?$/;
// Documentation/spec hosts that are never used as an endpoint.
const ALLOWED_URL_PREFIXES = ["https://schemas.", "http://www.w3.org", "https://reactnative.dev", "https://docs.expo.dev"];

function walk(dir, acc) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(p, acc);
    else if (/\.(ts|tsx|js|jsx)$/.test(entry.name)) acc.push(p);
  }
  return acc;
}

const offenders = [];
for (const d of SCAN_DIRS) {
  const abs = path.join(ROOT, d);
  if (!fs.existsSync(abs)) continue;
  for (const file of walk(abs, [])) {
    const text = fs.readFileSync(file, "utf8");
    const matches = text.match(URL_RE) || [];
    for (const url of matches) {
      if (ALLOWED_URL_PREFIXES.some((p) => url.startsWith(p))) continue;
      let host;
      try {
        host = new URL(url).host;
      } catch {
        continue;
      }
      if (!ALLOWED_HOST_RE.test(host)) {
        offenders.push(`${path.relative(ROOT, file)}: ${url}`);
      }
    }
  }
}

if (offenders.length > 0) {
  console.error("Hardcoded non-local endpoint(s) found (must come from DILCHAT_API_BASE_URL):");
  for (const o of offenders) console.error("  - " + o);
  process.exit(1);
}
console.log("no-prod-endpoint guard: OK (base URL is configuration-driven; only local dev fallback present)");
