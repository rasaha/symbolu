import { describe, expect, it } from "vitest";
import {
  buildPairs,
  composite,
  contrastRatio,
  evaluatePairs,
  parseHex,
  relativeLuminance,
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
});
