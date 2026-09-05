#!/usr/bin/env node
/**
 * Deterministic Expo config validation. Loads app.config.js, invokes it, and
 * asserts the resulting config has the expected shape and required plugins — and
 * that no hardcoded production API endpoint is baked into `extra.apiBaseUrl`.
 *
 * This replaces `expo config` in CI, which pulls in a validation dependency
 * stack (ajv-keywords) that fails to require in this install layout; the app
 * config itself is plain, valid JavaScript.
 */
const path = require("path");

const factory = require(path.resolve(__dirname, "..", "app.config.js"));
const cfg = typeof factory === "function" ? factory() : factory;
const expo = cfg && cfg.expo;

const problems = [];
if (!expo) problems.push("missing `expo` root");
else {
  if (expo.name !== "DilChat") problems.push(`unexpected name: ${expo.name}`);
  if (!expo.slug) problems.push("missing slug");
  if (expo.scheme !== "dilchat") problems.push("missing/incorrect scheme");
  const plugins = expo.plugins || [];
  for (const p of ["expo-router", "expo-secure-store", "expo-notifications"]) {
    if (!plugins.includes(p)) problems.push(`missing plugin: ${p}`);
  }
  const easProjectId = expo.extra && expo.extra.eas && expo.extra.eas.projectId;
  if (easProjectId !== undefined && !process.env.DILCHAT_EAS_PROJECT_ID) {
    problems.push("extra.eas.projectId must come from DILCHAT_EAS_PROJECT_ID, never be baked in");
  }
  const apiBaseUrl = expo.extra && expo.extra.apiBaseUrl;
  if (apiBaseUrl !== undefined && typeof apiBaseUrl === "string") {
    // If set, it must have come from the environment — reject a baked-in non-local host.
    try {
      const host = new URL(apiBaseUrl).host;
      const local = /^(localhost|127\.0\.0\.1|10\.0\.2\.2)(:\d+)?$/.test(host);
      const fromEnv = process.env.DILCHAT_API_BASE_URL === apiBaseUrl;
      if (!local && !fromEnv) problems.push(`extra.apiBaseUrl is a hardcoded non-local endpoint: ${apiBaseUrl}`);
    } catch {
      problems.push(`extra.apiBaseUrl is not a valid URL: ${apiBaseUrl}`);
    }
  }
}

if (problems.length) {
  console.error("Expo config validation failed:");
  problems.forEach((p) => console.error("  - " + p));
  process.exit(1);
}
console.log("expo config validation: OK (shape, plugins, no hardcoded endpoint).");
