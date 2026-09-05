// Security and boundary properties of the six studio screens (SD-2).
//
// The recurring question is not "does the UI hide the button" but "can this code path
// reach an authority act at all". Hiding a control is a design choice; not being able
// to reach the route is a property.
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { createHash } from "node:crypto";
import path from "node:path";

import {
  detectAuthorityActs,
  detectV2Consumption,
  verifyV2,
} from "../scripts/verify-v2-api-boundary.mjs";
import { V2_OPERATIONS } from "@/api/client-v2";
import { CONSOLE_PROHIBITED } from "./studioSecurityFixtures";

const FRONTEND = path.resolve(__dirname, "..");
const CONTRACT_PATH = path.join(FRONTEND, "..", "contracts", "openapi_v2.json");
const raw = readFileSync(CONTRACT_PATH, "utf-8");
const spec = JSON.parse(raw);
const specSha = createHash("sha256").update(raw).digest("hex");
const manifest = JSON.parse(
  readFileSync(path.join(FRONTEND, "security", "approved-v2-api-operations.json"), "utf-8"),
);
const clientText = readFileSync(path.join(FRONTEND, "src", "api", "client-v2.ts"), "utf-8");

function loadTree(dir: string): { rel: string; text: string }[] {
  const out: { rel: string; text: string }[] = [];
  const walk = (d: string) => {
    for (const name of readdirSync(d)) {
      const full = path.join(d, name);
      if (statSync(full).isDirectory()) walk(full);
      else if (/\.(ts|tsx)$/.test(name)) {
        out.push({ rel: path.relative(FRONTEND, full), text: readFileSync(full, "utf-8") });
      }
    }
  };
  walk(dir);
  return out;
}

const appFiles = loadTree(path.join(FRONTEND, "src"));

describe("SD-2 — no screen can reach an authority act", () => {
  it("the whole v2 contract is free of authority verbs", () => {
    expect(detectAuthorityActs(spec, manifest.prohibited_verbs)).toEqual([]);
  });

  it("the guard catches a contract that gained one", () => {
    const poisoned = {
      paths: {
        "/api/v2/policy/issue": { post: { operationId: "v2_policy_issue_release" } },
      },
    };
    expect(detectAuthorityActs(poisoned, manifest.prohibited_verbs).length).toBeGreaterThan(0);
  });

  it("the v2 client consumes exactly the seventeen approved operations", () => {
    const { consumed, unmatched } = detectV2Consumption(clientText, spec);
    expect(unmatched).toEqual([]);
    expect([...consumed].sort()).toEqual([...manifest.approved_operation_ids].sort());
    expect(consumed.size).toBe(17);
    expect([...V2_OPERATIONS].sort()).toEqual([...manifest.approved_operation_ids].sort());
  });

  it("the full v2 boundary verifier passes on the real tree", () => {
    expect(verifyV2({ spec, specSha, manifest, clientText, appFiles }).violations).toEqual([]);
  });

  it("no screen opens its own HTTP connection", () => {
    const screens = appFiles.filter((f) => f.rel.startsWith("src/features/studio/"));
    expect(screens.length).toBeGreaterThan(5);
    for (const file of screens) {
      expect(file.text).not.toMatch(/(^|[^A-Za-z0-9_$.])fetch\s*\(/);
      expect(file.text).not.toMatch(/XMLHttpRequest|EventSource|WebSocket/);
    }
  });

  it("the review-service routes the studio can reach are four reads and one relay (HR-1)", () => {
    const routes: string[] = manifest.review_service_routes_reachable_from_the_studio;
    expect(routes).toHaveLength(5);
    expect(routes.filter((r) => r.startsWith("POST "))).toEqual(["POST /review/decisions"]);
    for (const route of routes) {
      for (const verb of [...CONSOLE_PROHIBITED, "resume", "signal", "release", "continue"]) {
        expect(route.toLowerCase()).not.toContain(verb);
      }
    }
  });

  it("the approver proof is sent on the decision operation only and never stored or decoded (ID-1)", () => {
    const uses = appFiles.filter((f) => /APPROVER_PROOF_HEADER|approver[-_ ]?proof|submitReviewDecision/i.test(f.text));
    expect(uses.map((f) => f.rel).sort()).toEqual([
      "src/api/client-v2.ts",
      "src/features/studio/ReviewQueueScreen.tsx",
      "src/features/studio/hooks.ts",
    ]);
    const client = clientText;
    const headerUses = client.split("APPROVER_PROOF_HEADER").length - 1;
    expect(headerUses).toBe(3); // the declaration, its doc mention, and the one decision request
    expect(client.indexOf("APPROVER_PROOF_HEADER]")).toBeGreaterThan(client.indexOf("submitReviewDecision"));
    for (const file of uses) {
      expect(file.text).not.toMatch(/localStorage|sessionStorage|indexedDB|document\.cookie/);
      expect(file.text).not.toMatch(/atob\s*\(|JSON\.parse\s*\(\s*proof|proof\.split|console\.(log|info|debug|warn|error)/);
    }
  });

  it("the console routes the studio can reach are the four read/shadow ones", () => {
    expect(manifest.console_routes_reachable_from_the_studio).toHaveLength(4);
    for (const route of manifest.console_routes_reachable_from_the_studio) {
      for (const verb of CONSOLE_PROHIBITED) {
        expect(route.toLowerCase()).not.toContain(verb);
      }
    }
  });
});

describe("the canvas registry is closed", () => {
  it("no source file registers a node kind outside the registry", async () => {
    const { NODE_KINDS } = await import("@/features/canvas/nodeRegistry");
    const registryFile = appFiles.find((f) => f.rel.endsWith("nodeRegistry.ts"))!;
    // Every quoted key in the registry object must be a declared kind.
    const declared = new Set<string>(NODE_KINDS as readonly string[]);
    const keys = [...registryFile.text.matchAll(/^\s{2}(\w+):\s*\{$/gm)].map((m) => m[1]);
    for (const key of keys) {
      expect(declared.has(key)).toBe(true);
    }
  });

  it("no generic LLM, prompt or API node exists anywhere in the canvas feature", () => {
    const canvasFiles = appFiles.filter((f) => f.rel.startsWith("src/features/canvas/"));
    expect(canvasFiles.length).toBeGreaterThan(2);
    for (const file of canvasFiles) {
      // Matched as identifier-ish tokens so prose in a comment does not trip it.
      for (const banned of [
        /\bllmNode\b/i,
        /\bpromptNode\b/i,
        /\bapiNode\b/i,
        /"llm"/i,
        /"prompt"/i,
        /"api"/i,
      ]) {
        expect(file.text).not.toMatch(banned);
      }
    }
  });
});
