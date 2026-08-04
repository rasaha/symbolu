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
import { writeFileSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import tailwind from "../tailwind.config.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.dirname(HERE);
const REPORT_PATH = path.join(FRONTEND, "artifacts", "contrast-report.json");

const THRESHOLDS = { normal: 4.5, large: 3.0, nontext: 3.0 };

// WCAG 2.2 content-type classification (C3). Each pair declares WHAT it is; the
// required ratio is derived from that classification plus the rendered typography,
// so a pair can never quietly borrow the wrong (lower) threshold.
export const CONTENT_TYPES = ["normal_text", "large_text", "non_text_ui", "focus_indicator", "inactive_component_exception"];

// WCAG "large text" = ≥ 24px, or ≥ 18.66px when bold (≥700).
export function isLargeText(px, weight) {
  return px >= 24 || (px >= 18.66 && weight >= 700);
}

// Required ratio for a classified pair. inactive_component_exception has no minimum
// (WCAG 1.4.3 exempts inactive components) but MUST carry a rationale.
export function requiredRatio(contentType, px, weight) {
  switch (contentType) {
    case "normal_text": return 4.5;
    case "large_text": return 3.0;
    case "non_text_ui": return 3.0;
    case "focus_indicator": return 3.0;
    case "inactive_component_exception": return 0;
    default: return NaN;
  }
}

// Enforce honest classification. Returns an array of error strings (empty = OK).
export function validateClassifications(pairs) {
  const errors = [];
  for (const p of pairs) {
    const where = p.name;
    if (!p.fg || !p.bg) errors.push(`${where}: missing foreground/background`);
    if (!p.content_type) { errors.push(`${where}: missing content_type`); continue; }
    if (!CONTENT_TYPES.includes(p.content_type)) { errors.push(`${where}: unknown content_type ${p.content_type}`); continue; }
    if (typeof p.font_size_px !== "number" || typeof p.font_weight !== "number") {
      errors.push(`${where}: missing font metadata (font_size_px/font_weight)`);
    }
    if (p.content_type === "large_text" && !isLargeText(p.font_size_px, p.font_weight)) {
      errors.push(`${where}: large_text classification without qualifying size/weight (${p.font_size_px}px/${p.font_weight})`);
    }
    if (p.content_type === "inactive_component_exception" && !(p.rationale && p.rationale.trim())) {
      errors.push(`${where}: inactive_component_exception without documented rationale`);
    }
    // normal text must use 4.5 (never the 3:1 large/non-text threshold)
    const req = requiredRatio(p.content_type, p.font_size_px, p.font_weight);
    if (p.content_type === "normal_text" && req !== 4.5) errors.push(`${where}: normal_text must require 4.5`);
    if (p.fg && p.bg) {
      const ratio = contrastRatio(p.fg, p.bg);
      if (p.content_type !== "inactive_component_exception" && ratio < req) {
        errors.push(`${where}: ratio ${ratio.toFixed(2)} below required ${req} for ${p.content_type}`);
      }
    }
  }
  return errors;
}

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
  // content_type drives the threshold; kind is retained for backward compatibility.
  const KIND = { normal_text: "normal", large_text: "large", non_text_ui: "nontext", focus_indicator: "nontext", inactive_component_exception: "nontext" };
  const add = (name, fg, bg, content_type, px, weight, rationale) =>
    p.push({
      name, fg, bg, content_type, font_size_px: px, font_weight: weight, rationale,
      kind: KIND[content_type], threshold: requiredRatio(content_type, px, weight),
    });

  add("primary body text on primary background", T("ink", "1"), s0, "normal_text", 16, 400, "Primary body copy at 16px/400 meets normal-text 4.5.");
  add("secondary text on primary background", T("ink", "2"), s0, "normal_text", 14, 400, "Secondary copy at 14px/400 meets normal-text 4.5.");
  add("muted text on card background", T("ink", "3"), s1, "normal_text", 14, 400, "Muted 14px/400 body-adjacent copy; ink-3 brightened so it meets normal-text 4.5 (not treated as large text).");
  add("link/accent on primary background", ACCENT, s0, "non_text_ui", 0, 0, "Accent/link affordance and border; non-text UI (3.0). Ratio also exceeds normal-text 4.5.");
  add("focus indicator on primary background", ACCENT, s0, "focus_indicator", 0, 0, "Focus ring is a non-text UI component (SC 1.4.11, 3.0).");
  add("button text (normal) on surface-2", T("ink", "0"), s2, "normal_text", 14, 600, "Enabled button label 14px/600 meets normal-text 4.5.");
  add("button text (disabled) on surface-2", T("ink", "3"), s2, "normal_text", 14, 600, "Disabled control label; brightened ink-3 meets normal-text 4.5 — no inactive-component exception relied upon.");
  add("table body text on card", T("ink", "1"), s1, "normal_text", 14, 400, "Table cell copy 14px/400 meets normal-text 4.5.");
  add("table header text on surface-2", T("ink", "2"), s2, "normal_text", 12, 600, "Table header 12px/600 meets normal-text 4.5.");
  add("drawer/dialog text on card", T("ink", "1"), s1, "normal_text", 14, 400, "Drawer/dialog copy 14px/400 meets normal-text 4.5.");

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
    add(`${label} foreground/background`, fg, bg, "normal_text", 12, 600, "Status pill label 12px/600 meets normal-text 4.5.");
  }

  // error + success/readiness text on their tinted surfaces
  add("error text on error background", T("ink", "1"), tint("state", "ineligible", s0), "normal_text", 14, 400, "Error body 14px/400 meets normal-text 4.5.");
  add("error title on error background", T("state", "ineligible"), tint("state", "ineligible", s0), "normal_text", 14, 600, "Error title 14px/600 meets normal-text 4.5.");
  add("success/readiness text on background", T("state", "eligible"), stateBg, "normal_text", 14, 500, "Readiness text 14px/500 meets normal-text 4.5.");

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
  for (const [label, tone] of p3d) add(label, T("state", tone), tint("state", tone, s2), "normal_text", 12, 600, "P3D status pill 12px/600 meets normal-text 4.5.");
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
  const write = process.argv.includes("--write");
  const pairs = buildPairs();
  const missing = REQUIRED.filter((req) => !pairs.some((pp) => pp.name.includes(req)));
  const classErrors = validateClassifications(pairs);
  const { rows, failures, lowest, ok } = evaluatePairs(pairs);
  const lowestNormal = rows.filter((r) => r.content_type === "normal_text").reduce((m, r) => Math.min(m, r.ratio), Infinity);

  console.log("WCAG 2.2 token contrast (content-type classified)");
  for (const r of rows) {
    console.log(`  ${r.pass ? "PASS" : "FAIL"}  ${r.ratio.toFixed(2)}:1  [${r.content_type} ≥${r.threshold}]  ${r.name}`);
  }

  const report = {
    schema: "governance_studio.contrast_report.v2",
    content_types: CONTENT_TYPES,
    pair_count: rows.length,
    lowest_passing_ratio: Number.isFinite(lowest) ? lowest : null,
    lowest_normal_text_ratio: Number.isFinite(lowestNormal) ? lowestNormal : null,
    failed_pairs: failures.map((f) => ({ name: f.name, ratio: f.ratio, threshold: f.threshold })),
    classification_errors: classErrors,
    missing_required_pairs: missing,
    pairs: rows.map((r) => ({
      name: r.name, foreground: r.fg, background: r.bg,
      content_type: r.content_type, font_size_px: r.font_size_px, font_weight: r.font_weight,
      ratio: r.ratio, required_ratio: r.threshold, pass: r.pass, rationale: r.rationale,
    })),
    result: ok && missing.length === 0 && classErrors.length === 0 ? "PASS" : "FAIL",
  };
  const serialized = JSON.stringify(report, null, 2) + "\n";

  // Stale-report detection: the committed artifact must match the freshly computed
  // report. `--write` regenerates it; CI runs without it and fails on drift.
  let stale = false;
  if (write) {
    if (!existsSync(path.dirname(REPORT_PATH))) mkdirSync(path.dirname(REPORT_PATH), { recursive: true });
    writeFileSync(REPORT_PATH, serialized);
  } else if (!existsSync(REPORT_PATH) || readFileSync(REPORT_PATH, "utf-8") !== serialized) {
    stale = true;
  }

  for (const e of classErrors) console.error(`  CLASSIFICATION FAIL  ${e}`);
  if (missing.length) console.error(`  MISSING required pairs: ${missing.join(", ")}`);
  if (stale) console.error("  STALE committed contrast-report.json — run `npm run verify:contrast -- --write` and commit");
  console.log(`  pairs: ${rows.length} · lowest ${lowest.toFixed(2)}:1 · lowest normal-text ${Number.isFinite(lowestNormal) ? lowestNormal.toFixed(2) : "n/a"}:1 · result: ${report.result}`);
  process.exit(report.result === "PASS" && !stale ? 0 : 1);
}

if (import.meta.url === `file://${process.argv[1]}`) main();
