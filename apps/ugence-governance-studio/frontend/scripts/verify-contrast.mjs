// Evidence-based WCAG 2.2 contrast verifier (§C4).
//
// Loads the canonical design tokens from tailwind.config.js, computes relative
// luminance and contrast ratios for the critical foreground/background pairs
// (compositing the app's /10 tinted surfaces), compares each to its WCAG
// threshold, prints a table, writes a deterministic machine-readable report and
// FAILS on any violation or missing required pair.
//
//   node scripts/verify-contrast.mjs
//
// Pure helpers are exported for unit testing.
import { writeFileSync, existsSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import tailwind from "../tailwind.config.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.dirname(HERE);
const REPORT_PATH = path.join(FRONTEND, "artifacts", "contrast-report.json");

const THRESHOLDS = { normal: 4.5, large: 3.0, nontext: 3.0 };

// -- color math ------------------------------------------------------------
export function parseHex(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex).trim());
  if (!m) throw new Error(`unsupported color format: ${hex}`);
  const int = parseInt(m[1], 16);
  return { r: (int >> 16) & 255, g: (int >> 8) & 255, b: int & 255 };
}

function channelLuminance(c) {
  const s = c / 255;
  return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
}

export function relativeLuminance(hex) {
  const { r, g, b } = parseHex(hex);
  return 0.2126 * channelLuminance(r) + 0.7152 * channelLuminance(g) + 0.0722 * channelLuminance(b);
}

export function contrastRatio(fg, bg) {
  const l1 = relativeLuminance(fg);
  const l2 = relativeLuminance(bg);
  const [hi, lo] = l1 >= l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}

// Composite a foreground color at `alpha` over an opaque background (sRGB).
export function composite(fgHex, alpha, bgHex) {
  const fg = parseHex(fgHex);
  const bg = parseHex(bgHex);
  const mix = (f, b) => Math.round(f * alpha + b * (1 - alpha));
  const toHex = (n) => n.toString(16).padStart(2, "0");
  return `#${toHex(mix(fg.r, bg.r))}${toHex(mix(fg.g, bg.g))}${toHex(mix(fg.b, bg.b))}`;
}

// -- token resolution ------------------------------------------------------
const COLORS = tailwind.theme.extend.colors;
const T = (group, key) => {
  const v = COLORS?.[group]?.[key];
  if (!v) throw new Error(`missing token ${group}.${key}`);
  return v;
};
const ACCENT = "#6aa9ff"; // focus ring / accent (index.css :focus-visible)

// Effective background for a `bg-state-X/10` tint over a surface.
const tint = (group, key, surface) => composite(T(group, key), 0.1, surface);

// -- required pairs --------------------------------------------------------
export function buildPairs() {
  const s0 = T("surface", "0");
  const s1 = T("surface", "1");
  const s2 = T("surface", "2");
  const stateBg = tint("state", "eligible", s0); // representative tinted surface
  const p = [];
  const add = (name, fg, bg, kind) => p.push({ name, fg, bg, kind, threshold: THRESHOLDS[kind] });

  add("primary body text on primary background", T("ink", "1"), s0, "normal");
  add("secondary text on primary background", T("ink", "2"), s0, "normal");
  add("muted text on card background", T("ink", "3"), s1, "large");
  add("link/accent on primary background", ACCENT, s0, "nontext");
  add("focus indicator on primary background", ACCENT, s0, "nontext");
  add("button text (normal) on surface-2", T("ink", "0"), s2, "normal");
  add("button text (disabled) on surface-2", T("ink", "3"), s2, "large");
  add("table body text on card", T("ink", "1"), s1, "normal");
  add("table header text on surface-2", T("ink", "2"), s2, "normal");
  add("drawer/dialog text on card", T("ink", "1"), s1, "normal");

  // status pills: full state color on the /10 tinted surface it renders over
  const states = [
    ["eligible", "eligible state"],
    ["ineligible", "ineligible state"],
    ["indeterminate", "indeterminate state"],
    ["invalid", "invalid state"],
    ["authority", "human-authority state"],
    ["review", "human-review state"],
    ["governance", "governance-owned state"],
    ["deterministic", "deterministic-service state"],
  ];
  for (const [key, label] of states) {
    const bg = tint("state", key === "deterministic" ? "eligible" : key, s2);
    const fg = key === "deterministic" ? T("ink", "2") : T("state", key);
    add(`${label} foreground/background`, fg, bg, "normal");
  }

  // error + success/readiness text on their tinted surfaces
  add("error text on error background", T("ink", "1"), tint("state", "ineligible", s0), "normal");
  add("error title on error background", T("state", "ineligible"), tint("state", "ineligible", s0), "normal");
  add("success/readiness text on background", T("state", "eligible"), stateBg, "normal");

  // P3D semantic states (§35). Each reuses a contrast-verified state token on the
  // /10 tinted surface it renders over; measured explicitly here so the report
  // documents ranking / selection / permission / fallback / replay / diff / what-if
  // color pairs individually.
  const p3d = [
    ["selected primary state", "eligible"],
    ["selected fallback state", "governance"],
    ["eligible-not-selected state", "indeterminate"],
    ["permission proposed state", "governance"],
    ["permission excluded/prohibited state", "ineligible"],
    ["fallback available state", "eligible"],
    ["no fallback state", "ineligible"],
    ["replay match state", "eligible"],
    ["replay mismatch state", "ineligible"],
    ["plan added state", "eligible"],
    ["plan removed state", "ineligible"],
    ["plan changed state", "indeterminate"],
    ["what-if active state", "authority"],
  ];
  for (const [label, tone] of p3d) add(label, T("state", tone), tint("state", tone, s2), "normal");
  return p;
}

export function evaluatePairs(pairs) {
  const rows = pairs.map((pair) => {
    const ratio = contrastRatio(pair.fg, pair.bg);
    return { ...pair, ratio: Math.round(ratio * 100) / 100, pass: ratio >= pair.threshold };
  });
  const failures = rows.filter((r) => !r.pass);
  const lowest = rows.reduce((m, r) => Math.min(m, r.ratio), Infinity);
  return { rows, failures, lowest, ok: failures.length === 0 };
}

function main() {
  const REQUIRED = [
    "primary body text",
    "secondary text",
    "muted text",
    "link/accent",
    "focus indicator",
    "button text (normal)",
    "button text (disabled)",
    "table body text",
    "table header text",
    "drawer/dialog text",
    "eligible state",
    "ineligible state",
    "indeterminate state",
    "invalid state",
    "human-authority state",
    "human-review state",
    "governance-owned state",
    "deterministic-service state",
    "error text",
    "success/readiness text",
  ];
  const pairs = buildPairs();
  const missing = REQUIRED.filter((req) => !pairs.some((pp) => pp.name.includes(req)));
  const { rows, failures, lowest, ok } = evaluatePairs(pairs);

  console.log("WCAG 2.2 token contrast (thresholds: normal 4.5, large 3.0, non-text 3.0)");
  for (const r of rows) {
    console.log(`  ${r.pass ? "PASS" : "FAIL"}  ${r.ratio.toFixed(2)}:1  [${r.kind}]  ${r.name}`);
  }
  const report = {
    schema: "governance_studio.contrast_report.v1",
    thresholds: THRESHOLDS,
    pair_count: rows.length,
    lowest_passing_ratio: Number.isFinite(lowest) ? lowest : null,
    failed_pairs: failures.map((f) => ({ name: f.name, ratio: f.ratio, threshold: f.threshold })),
    missing_required_pairs: missing,
    pairs: rows.map((r) => ({ name: r.name, fg: r.fg, bg: r.bg, kind: r.kind, ratio: r.ratio, pass: r.pass })),
    result: ok && missing.length === 0 ? "PASS" : "FAIL",
  };
  if (!existsSync(path.dirname(REPORT_PATH))) mkdirSync(path.dirname(REPORT_PATH), { recursive: true });
  writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2) + "\n");

  if (missing.length) console.error(`  MISSING required pairs: ${missing.join(", ")}`);
  console.log(`  pairs: ${rows.length} · lowest ${lowest.toFixed(2)}:1 · result: ${report.result}`);
  process.exit(report.result === "PASS" ? 0 : 1);
}

if (import.meta.url === `file://${process.argv[1]}`) main();
