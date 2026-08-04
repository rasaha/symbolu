// api-allowlist-negative-fixtures — this file intentionally references forbidden
// operation ids/paths as NEGATIVE test fixtures; the marker on this line exempts it
// from the verifier's own forbidden-reference scan.
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import {
  detectConsumption,
  validateManifest,
  detectRawFetch,
  detectForbiddenReferences,
  verify,
} from "../scripts/verify-api-boundary.mjs";

const FRONTEND = path.resolve(__dirname, "..");
const spec = JSON.parse(readFileSync(path.join(FRONTEND, "..", "contracts", "openapi.json"), "utf-8"));
const specSha = "dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656";
const manifest = JSON.parse(readFileSync(path.join(FRONTEND, "security", "approved-api-operations.json"), "utf-8"));
const clientText = readFileSync(path.join(FRONTEND, "src", "api", "client.ts"), "utf-8");

describe("C1 — public API operation allowlist", () => {
  it("the real client consumes exactly the approved 17 operations", () => {
    const { consumed, unmatched } = detectConsumption(clientText, spec);
    expect(unmatched).toEqual([]);
    expect([...consumed].sort()).toEqual([...manifest.approved_operation_ids].sort());
    expect(consumed.size).toBe(17);
  });

  it("consumed ∩ forbidden = ∅ and consumed ⊆ approved", () => {
    const { consumed } = detectConsumption(clientText, spec);
    const forbidden = new Set(manifest.forbidden_operation_ids);
    const approved = new Set(manifest.approved_operation_ids);
    for (const o of consumed) {
      expect(forbidden.has(o)).toBe(false);
      expect(approved.has(o)).toBe(true);
    }
  });

  it("an operation used through an indirect wrapper/hook is detected (scenario_what_if, compare_plans)", () => {
    // scenario_what_if is only reachable via useWhatIf -> scenarioWhatIf; compare_plans via useCompare -> comparePlans.
    const { consumed } = detectConsumption(clientText, spec);
    expect(consumed.has("scenario_what_if")).toBe(true);
    expect(consumed.has("compare_plans")).toBe(true);
  });

  it("a forbidden internal operation wired into a client fails", () => {
    const bad = clientText + '\nexport const sneak = () => envelope<unknown>("/api/v1/composition/compose", postJson({}));\n';
    const { consumed } = detectConsumption(bad, spec);
    expect(consumed.has("compose_workforce")).toBe(true);
    const forbiddenConsumed = [...consumed].filter((o) => manifest.forbidden_operation_ids.includes(o));
    expect(forbiddenConsumed).toContain("compose_workforce");
  });

  it("an unknown API path fails as unmatched", () => {
    const bad = 'export const x = () => envelope<unknown>("/api/v1/nope/nowhere");';
    const { unmatched } = detectConsumption(bad, spec);
    expect(unmatched.length).toBe(1);
    expect(unmatched[0].path).toBe("/api/v1/nope/nowhere");
  });

  it("a raw fetch to an unapproved path outside the canonical client fails", () => {
    const files = [{ rel: "src/features/whatif/Bad.tsx", text: 'fetch("/api/v1/workflows/validate")' }];
    expect(detectRawFetch(files)).toEqual([{ file: "src/features/whatif/Bad.tsx" }]);
  });

  it("refetch()/.fetch are not mistaken for a raw fetch", () => {
    const files = [{ rel: "src/app/CompatibilityGate.tsx", text: "onClick={() => refetch()}" }];
    expect(detectRawFetch(files)).toEqual([]);
  });

  it("an approved operation removed from OpenAPI fails validation", () => {
    const doctored = JSON.parse(JSON.stringify(spec));
    delete doctored.paths["/api/v1/scenarios/{scenario_id}/ranking"];
    const { errors } = validateManifest(manifest, doctored, specSha);
    expect(errors.some((e: string) => e.includes("get_scenario_ranking"))).toBe(true);
  });

  it("an OpenAPI hash mismatch fails validation", () => {
    const { errors } = validateManifest(manifest, spec, "deadbeef");
    expect(errors.some((e: string) => e.includes("hash"))).toBe(true);
  });

  it("a duplicate manifest entry fails validation", () => {
    const dup = { ...manifest, approved_operation_ids: [...manifest.approved_operation_ids, "get_health"] };
    const { errors } = validateManifest(dup, spec, specSha);
    expect(errors.some((e: string) => e.includes("duplicate"))).toBe(true);
  });

  it("an approved/forbidden overlap fails validation", () => {
    const overlap = {
      ...manifest,
      approved_operation_ids: [...manifest.approved_operation_ids, "validate_workflow"],
    };
    const { errors } = validateManifest(overlap, spec, specSha);
    expect(errors.some((e: string) => e.includes("overlap"))).toBe(true);
  });

  it("a generated-but-unused internal operation does not falsely fail (generated/ excluded)", () => {
    // The generated client type surface contains every operation id/path. If it were
    // scanned it would trip the forbidden-reference check; it must be excluded.
    const generatedLike = [{ rel: "src/generated/api.ts", text: '"/api/v1/composition/compose": compose_workforce' }];
    // detectForbiddenReferences is only ever handed non-generated files by verify();
    // prove that excluding generated leaves no forbidden refs for the real tree.
    const forbiddenInGenerated = detectForbiddenReferences(generatedLike, manifest);
    expect(forbiddenInGenerated.length).toBeGreaterThan(0); // would fail IF scanned
    // ...but the orchestrator never passes generated files, so a full run is clean:
    expect(realRun().ok).toBe(true);
  });

  it("the full verifier passes on the real tree", () => {
    expect(realRun().violations).toEqual([]);
  });
});

function loadTree(dir: string): { rel: string; text: string }[] {
  const out: { rel: string; text: string }[] = [];
  const walk = (d: string) => {
    for (const n of readdirSync(d)) {
      const full = path.join(d, n);
      if (statSync(full).isDirectory()) walk(full);
      else if (/\.(ts|tsx)$/.test(n)) out.push({ rel: path.relative(FRONTEND, full), text: readFileSync(full, "utf-8") });
    }
  };
  walk(dir);
  return out;
}

function realRun() {
  const appFiles = loadTree(path.join(FRONTEND, "src")).filter((f) => !f.rel.startsWith("src/generated/"));
  const testFiles = loadTree(path.join(FRONTEND, "tests"));
  return verify({ spec, specSha, manifest, clientText, appFiles, testFiles });
}
