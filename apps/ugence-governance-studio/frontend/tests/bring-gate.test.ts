// bring-your-workflow-negative-fixtures — the gate's table tests (ADR §22, BW-2).
// Every refusal the ruling names, each by its typed code; the two real documents
// pass; and the client's canonical digest equals the one the real backend computed
// for the guided example, so the provenance the screen shows is the server's.
import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";
import {
  byteLength,
  canonicalText,
  clientDigest,
  declaredVersion,
  gateWorkflowText,
  LIMITS,
  measure,
  summarize,
} from "@/features/bring/gate";
import exampleV1 from "@/features/bring/example-workflow-ir.v1.json";
import exampleV2 from "./fixtures/bring.example-v2.json";
import validateFixture from "./fixtures/bring.validate.json";

const v1Text = JSON.stringify(exampleV1);
const v2Text = JSON.stringify(exampleV2, null, 2);

function withNodes(count: number) {
  const doc = JSON.parse(v1Text);
  const node = doc.workflow_ir.nodes[0];
  doc.workflow_ir.nodes = Array.from({ length: count }, (_, i) => ({ ...node, node_id: `n${i}` }));
  return JSON.stringify(doc);
}

function nested(depth: number) {
  let inner: Record<string, unknown> = {};
  const root = inner;
  for (let i = 1; i < depth; i++) {
    inner.child = {};
    inner = inner.child as Record<string, unknown>;
  }
  root.ir_version = "workflow_ir.v2";
  return JSON.stringify(root);
}

describe("BW-2 — the gate refuses by typed code", () => {
  const cases: Array<[string, string, string]> = [
    ["EMPTY", "   \n", "empty text"],
    ["NOT_JSON", "ir_version: workflow_ir.v2\nnodes: []\n", "YAML"],
    ["NOT_JSON", "import os\nprint('hi')", "Python"],
    ["NOT_JSON", "PKarchive", "a ZIP header"],
    ["NOT_AN_OBJECT", "[1, 2, 3]", "a JSON array"],
    ["NOT_AN_OBJECT", '"workflow"', "a JSON string"],
    ["UNSUPPORTED_VERSION", '{"ir_version": "workflow_ir.v9", "nodes": []}', "an unknown version"],
    ["UNSUPPORTED_VERSION", '{"nodes": [], "edges": []}', "no declared version (never guessed)"],
    ["CREDENTIAL_SHAPED", '{"ir_version": "workflow_ir.v2", "api_key": "abc"}', "a credential-shaped key"],
    ["CREDENTIAL_SHAPED", '{"ir_version": "workflow_ir.v2", "note": "-----BEGIN RSA PRIVATE KEY-----"}', "a private key"],
    ["CREDENTIAL_SHAPED", '{"ir_version": "workflow_ir.v2", "note": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc"}', "a JWT-shaped value"],
    ["REMOTE_REFERENCE", '{"ir_version": "workflow_ir.v2", "source": "https://example.invalid/wf.json"}', "an https URL"],
    ["REMOTE_REFERENCE", '{"ir_version": "workflow_ir.v2", "source": "file:///etc/passwd"}', "a file URL"],
    ["TOO_MANY_NODES", withNodes(LIMITS.nodes + 1), "one node over the limit"],
    ["TOO_DEEP", nested(LIMITS.depth + 1), "one level over the depth limit"],
  ];
  it.each(cases)("%s for %s", (code, text) => {
    const result = gateWorkflowText(text);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe(code);
  });

  it("TOO_LARGE before parsing, at one byte over 1 MiB", () => {
    const text = '{"ir_version":"workflow_ir.v2","pad":"' + "x".repeat(LIMITS.document_bytes) + '"}';
    expect(byteLength(text)).toBeGreaterThan(LIMITS.document_bytes);
    const result = gateWorkflowText(text);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("TOO_LARGE");
  });

  it("TOO_MANY_EDGES and TOO_MANY_ELEMENTS", () => {
    const edges = { ir_version: "workflow_ir.v2", base_ir: { edges: Array.from({ length: LIMITS.edges + 1 }, (_, i) => ({ edge_id: `e${i}` })) } };
    const r1 = gateWorkflowText(JSON.stringify(edges));
    expect(!r1.ok && r1.code).toBe("TOO_MANY_EDGES");
    const wide = { ir_version: "workflow_ir.v2", items: Array.from({ length: LIMITS.elements + 1 }, () => 0) };
    const r2 = gateWorkflowText(JSON.stringify(wide));
    expect(!r2.ok && r2.code).toBe("TOO_MANY_ELEMENTS");
  });

  it("a document at every limit passes the gate", () => {
    expect(gateWorkflowText(withNodes(LIMITS.nodes)).ok).toBe(true);
    expect(gateWorkflowText(nested(LIMITS.depth)).ok).toBe(true);
  });

  it("the figures are the owner's (BW-2)", () => {
    expect(LIMITS).toEqual({ document_bytes: 1048576, depth: 32, nodes: 200, edges: 400, elements: 50000 });
  });
});

describe("BW-2 — the two real documents pass, and are read verbatim", () => {
  it("the guided example is workflow_ir.v1 with its nine nodes and eight edges", () => {
    const r = gateWorkflowText(v1Text);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.declaredVersion).toBe("workflow_ir.v1");
    expect(r.summary.nodeCount).toBe(9);
    expect(r.summary.edgeCount).toBe(8);
    expect(r.measures.nodes).toBe(9);
    expect(r.summary.policyPack).toBe("gs_procurement@1");
    expect(Object.values(r.summary.kinds).reduce((a, b) => a + b, 0)).toBe(9);
  });

  it("the v2 conformance document is workflow_ir.v2 and carries its semantics", () => {
    const r = gateWorkflowText(v2Text);
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.declaredVersion).toBe("workflow_ir.v2");
    expect(r.summary.nodeCount).toBe(9);
    expect(r.summary.workflowFingerprint).toMatch(/^sha256:/);
  });

  it("the declared version follows the backend's rule and is never inferred", () => {
    expect(declaredVersion({ ir_version: "workflow_ir.v2" })).toBe("workflow_ir.v2");
    expect(declaredVersion({ contract_version: "workflow_ir.v1" })).toBe("workflow_ir.v1");
    expect(declaredVersion({ workflow_ir: { ir_version: "workflow_ir.v1" } })).toBe("workflow_ir.v1");
    expect(declaredVersion({ nodes: [], edges: [] })).toBe("");
  });

  it("measure reports depth, elements and the longest node and edge lists", () => {
    const { measures, refusal } = measure(exampleV1);
    expect(refusal).toBeNull();
    expect(measures.nodes).toBe(9);
    expect(measures.edges).toBe(8);
    expect(measures.depth).toBeGreaterThanOrEqual(3);
    expect(measures.elements).toBeGreaterThan(17);
  });

  it("summarize reads only what is declared", () => {
    const s = summarize({ workflow_ir: { nodes: [{ node_id: "a", kind: "HUMAN_REVIEW", disposition: "BLOCKING" }], edges: [] } });
    expect(s.kinds).toEqual({ HUMAN_REVIEW: 1 });
    expect(s.dispositions).toEqual({ BLOCKING: 1 });
    expect(s.humanReviewNodes).toEqual(["a"]);
    expect(s.toolRefs).toEqual([]);
    expect(s.policyPack).toBeNull();
  });
});

describe("BW-4 — provenance: the client digest is the server's canonical digest", () => {
  it("canonicalText matches Python's json.dumps(sort_keys=True, indent=2) + newline", () => {
    expect(canonicalText({ b: [1, "x"], a: { d: null, c: true } })).toBe('{\n  "a": {\n    "c": true,\n    "d": null\n  },\n  "b": [\n    1,\n    "x"\n  ]\n}\n');
  });

  it("clientDigest of the guided example equals the digest the real backend computed for it", async () => {
    const digest = await clientDigest(exampleV1);
    const expected = createHash("sha256").update(canonicalText(exampleV1)).digest("hex");
    expect(digest).toBe(`sha256:${expected}`);
    expect(digest).toBe(validateFixture.integrity.computed_digest);
  });
});
