import { describe, expect, it } from "vitest";
import {
  buildPairs,
  composite,
  contrastRatio,
  evaluatePairs,
  parseHex,
  relativeLuminance,
  validateClassifications,
  isLargeText,
  requiredRatio,
} from "../scripts/verify-contrast.mjs";

describe("contrast math (C4)", () => {
  it("computes relative luminance at the extremes", () => {
    expect(relativeLuminance("#000000")).toBeCloseTo(0, 5);
    expect(relativeLuminance("#ffffff")).toBeCloseTo(1, 5);
  });

  it("computes the canonical black/white contrast ratio", () => {
    expect(contrastRatio("#000000", "#ffffff")).toBeCloseTo(21, 2);
    expect(contrastRatio("#ffffff", "#000000")).toBeCloseTo(21, 2);
  });

  it("passes an exact-threshold pair and fails just below", () => {
    // white on a mid grey ~ near 4.5; verify comparator semantics
    const ratio = contrastRatio("#ffffff", "#767676");
    expect(ratio).toBeGreaterThanOrEqual(4.5);
    const { rows } = evaluatePairs([{ name: "x", fg: "#767676", bg: "#ffffff", kind: "normal", threshold: 4.5 }]);
    expect(rows[0].pass).toBe(true);
    const below = evaluatePairs([{ name: "y", fg: "#8a8a8a", bg: "#ffffff", kind: "normal", threshold: 4.5 }]);
    expect(below.rows[0].pass).toBe(false);
  });

  it("rejects a malformed color", () => {
    expect(() => parseHex("not-a-color")).toThrow();
    expect(() => relativeLuminance("#12")).toThrow();
  });

  it("composites alpha over an opaque background deterministically", () => {
    expect(composite("#ffffff", 0, "#000000")).toBe("#000000");
    expect(composite("#ffffff", 1, "#000000")).toBe("#ffffff");
    expect(composite("#ffffff", 0.5, "#000000")).toBe("#808080");
  });
});

describe("canonical token contrast (C4)", () => {
  const { rows, failures, ok } = evaluatePairs(buildPairs());

  it("evaluates all required critical pairs with no failures", () => {
    expect(rows.length).toBeGreaterThanOrEqual(20);
    expect(failures, failures.map((f: { name: string; ratio: number }) => `${f.name} ${f.ratio}`).join("; ")).toHaveLength(0);
    expect(ok).toBe(true);
  });

  it("covers the required categories", () => {
    const names = rows.map((r: { name: string }) => r.name).join(" | ");
    for (const cat of [
      "primary body text",
      "secondary text",
      "muted text",
      "focus indicator",
      "button text (disabled)",
      "eligible state",
      "ineligible state",
      "indeterminate state",
      "invalid state",
      "human-authority state",
      "human-review state",
      "governance-owned state",
      "deterministic-service state",
      "table header",
      "error title",
      "success/readiness",
    ]) {
      expect(names).toContain(cat);
    }
  });

  it("every pair meets its WCAG threshold", () => {
    for (const r of rows) expect(r.ratio, r.name).toBeGreaterThanOrEqual(r.threshold);
  });

  it("resolves the former 4.09 pair: every normal-text pair meets 4.5", () => {
    const normal = rows.filter((r: { content_type: string }) => r.content_type === "normal_text");
    for (const r of normal) expect(r.ratio, r.name).toBeGreaterThanOrEqual(4.5);
    // no pair relies on a large-text or inactive-component exception
    expect(rows.every((r: { content_type: string }) => r.content_type !== "large_text")).toBe(true);
    expect(rows.every((r: { content_type: string }) => r.content_type !== "inactive_component_exception")).toBe(true);
  });
});

describe("contrast classification enforcement (C3)", () => {
  it("the real token set classifies cleanly", () => {
    expect(validateClassifications(buildPairs())).toEqual([]);
  });

  it("large-text WCAG rule (≥24px, or ≥18.66px bold)", () => {
    expect(isLargeText(24, 400)).toBe(true);
    expect(isLargeText(19, 700)).toBe(true);
    expect(isLargeText(16, 700)).toBe(false);
    expect(isLargeText(18, 400)).toBe(false);
  });

  it("normal text requires 4.5, non-text/large/focus require 3.0", () => {
    expect(requiredRatio("normal_text")).toBe(4.5);
    expect(requiredRatio("large_text")).toBe(3.0);
    expect(requiredRatio("non_text_ui")).toBe(3.0);
    expect(requiredRatio("focus_indicator")).toBe(3.0);
    expect(requiredRatio("inactive_component_exception")).toBe(0);
  });

  const base = { name: "x", fg: "#ffffff", bg: "#000000", font_size_px: 14, font_weight: 400, rationale: "r" };
  it("rejects a missing content_type", () => {
    expect(validateClassifications([{ ...base, content_type: undefined }]).length).toBeGreaterThan(0);
  });
  it("rejects an unknown content_type", () => {
    expect(validateClassifications([{ ...base, content_type: "huge_text" }])[0]).toMatch(/unknown content_type/);
  });
  it("rejects normal text below 4.5 (cannot borrow the 3:1 threshold)", () => {
    // ~4.0:1 grey on white — below normal-text 4.5
    const errs = validateClassifications([{ ...base, fg: "#8a8a8a", bg: "#ffffff", content_type: "normal_text" }]);
    expect(errs.some((e: string) => e.includes("below required 4.5"))).toBe(true);
  });
  it("rejects large_text classification without qualifying size/weight", () => {
    const errs = validateClassifications([{ ...base, font_size_px: 14, font_weight: 400, content_type: "large_text" }]);
    expect(errs.some((e: string) => e.includes("large_text classification without qualifying"))).toBe(true);
  });
  it("rejects an inactive-component exception without rationale", () => {
    const errs = validateClassifications([{ ...base, content_type: "inactive_component_exception", rationale: "" }]);
    expect(errs.some((e: string) => e.includes("without documented rationale"))).toBe(true);
  });
  it("rejects a missing foreground/background", () => {
    expect(validateClassifications([{ ...base, fg: "", content_type: "normal_text" }]).some((e: string) => e.includes("missing foreground"))).toBe(true);
  });
});
