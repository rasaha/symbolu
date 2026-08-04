#!/usr/bin/env node
/**
 * API contract-drift guard. Confirms that every backend route the mobile client
 * depends on still exists in the committed OpenAPI document, and that NO Guna /
 * compatibility route has appeared. The OpenAPI path is provided via
 * DILCHAT_OPENAPI_JSON (generated from the backend in CI); when absent the check
 * is skipped with a clear notice (so local runs without the backend don't fail),
 * but CI always supplies it.
 */
const fs = require("fs");

// Routes the mobile client calls (paths as templated in OpenAPI).
const REQUIRED = [
  ["POST", "/v1/auth/register"],
  ["POST", "/v1/auth/login"],
  ["POST", "/v1/auth/refresh"],
  ["POST", "/v1/auth/logout"],
  ["POST", "/v1/auth/logout-all"],
  ["GET", "/v1/users/me"],
  ["POST", "/v1/birth-profiles"],
  ["GET", "/v1/birth-profiles/me"],
  ["PATCH", "/v1/birth-profiles/me"],
  ["POST", "/v1/couples/invitations"],
  ["POST", "/v1/couples/invitations/{token}/accept"],
  ["GET", "/v1/couples/current"],
  ["POST", "/v1/couples/{couple_id}/unpair"],
];
const BANNED_SUBSTRINGS = ["guna", "compatibility", "koota", "ashtakoot", "milan", "dosha"];

const specPath = process.env.DILCHAT_OPENAPI_JSON;
if (!specPath) {
  console.log("contract-drift: SKIPPED (DILCHAT_OPENAPI_JSON not set; CI supplies it).");
  process.exit(0);
}
const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));
const paths = spec.paths || {};

const missing = [];
for (const [method, route] of REQUIRED) {
  const ops = paths[route];
  if (!ops || !ops[method.toLowerCase()]) missing.push(`${method} ${route}`);
}

const banned = Object.keys(paths).filter((p) => BANNED_SUBSTRINGS.some((b) => p.toLowerCase().includes(b)));

let failed = false;
if (missing.length) {
  console.error("Contract drift — required backend routes missing:");
  missing.forEach((m) => console.error("  - " + m));
  failed = true;
}
if (banned.length) {
  console.error("Forbidden Guna/compatibility route(s) present in OpenAPI:");
  banned.forEach((b) => console.error("  - " + b));
  failed = true;
}
if (failed) process.exit(1);
console.log(`contract-drift: OK (${REQUIRED.length} required routes present; no Guna/compatibility route).`);
