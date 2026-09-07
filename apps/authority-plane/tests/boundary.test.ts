// authority-plane-negative-fixtures — this file references forbidden operation ids and
// paths as NEGATIVE fixtures; the marker on this line exempts it from the verifier's
// forbidden-reference scan.
//
// The plane's boundary (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §11 step 3, §16): this app
// consumes exactly the six operations the worker's committed contract marks served (four
// reads, two gated writes), its manifest is bound to that contract by hash, the two
// unserved writes are not reachable from its client, and the verifier can fail.
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";

import {
  APP,
  CLIENT_REL,
  MANIFEST_PATH,
  detectConsumption,
  detectForbiddenReferences,
  detectRawFetch,
  loadContract,
  verify,
} from "../scripts/verify-boundary.mjs";
import { OPERATIONS, PROOF_HEADER, READ_OPERATIONS, WRITE_OPERATIONS } from "@/api/client";

const { contract, sha } = loadContract();
const manifest = JSON.parse(readFileSync(MANIFEST_PATH, "utf-8"));
const clientText = readFileSync(path.join(APP, CLIENT_REL), "utf-8");
type Op = { operation_id: string; kind: string; served: boolean; method: string; path: string };
const ops: Op[] = contract.operations;

describe("the authority plane's boundary", () => {
  it("passes the verifier as committed", () => {
    const { errors, consumed } = verify();
    expect(errors).toEqual([]);
    expect(consumed).toEqual([...manifest.approved_operation_ids].sort());
  });

  it("binds the manifest to the worker's committed contract by hash, and the proof header to the contract's", () => {
    expect(manifest.contract_sha256).toBe(sha);
    expect(manifest.contract).toBe(contract.schema);
    expect(manifest.write_proof_header).toBe(contract.write_proof_header);
    expect(PROOF_HEADER).toBe(contract.write_proof_header);
  });

  it("the client consumes exactly the four reads and the two served writes, and declares the same set", () => {
    const { consumed, unmatched } = detectConsumption(clientText, contract);
    expect(unmatched).toEqual([]);
    expect([...consumed].sort()).toEqual([...OPERATIONS].sort());
    expect([...OPERATIONS].sort()).toEqual([...manifest.approved_operation_ids].sort());
    for (const id of READ_OPERATIONS) {
      const op = ops.find((o) => o.operation_id === id)!;
      expect(op.kind).toBe("read");
      expect(op.served).toBe(true);
    }
    for (const id of WRITE_OPERATIONS) {
      const op = ops.find((o) => o.operation_id === id)!;
      expect(op.kind).toBe("write");
      expect(op.served).toBe(true);
      expect(op.method).toBe("POST");
    }
  });

  it("the forbidden set is exactly the contract's two unserved writes: activate and issue", () => {
    const unserved = ops.filter((o) => o.served !== true);
    expect(unserved.map((o) => o.operation_id).sort())
      .toEqual([...manifest.forbidden_operation_ids].sort());
    expect(manifest.forbidden_operation_ids.sort()).toEqual(["authority_activate_constitution", "authority_issue_record"]);
    for (const u of unserved) expect(u.kind).toBe("write");
  });

  it("the client names no forbidden operation and no unserved path, and only the client names a write method", () => {
    expect(detectForbiddenReferences(clientText, manifest, { allowWriteMethod: true })).toEqual([]);
    expect(detectForbiddenReferences(clientText, manifest)).toEqual(["a write method"]);
    for (const id of manifest.forbidden_operation_ids) expect(clientText).not.toContain(id);
    expect(clientText).not.toContain("/authority/constitutions");
    expect(clientText).not.toContain("/authority/issuances");
  });

  it("the verifier can fail: a sneaky fetch, an activate path, an issue path, a write method outside the client", () => {
    expect(detectRawFetch('const r = await fetch("/authority/grants")')).toHaveLength(1);
    const sneaky = 'post<X>(`/authority/constitutions/${id}/activate`)';
    const { unmatched, consumed } = detectConsumption(sneaky, contract);
    expect(unmatched).toEqual([]);
    expect([...consumed]).toEqual(["authority_activate_constitution"]);
    // consumed but not approved: rule 3 fails on the set comparison; rule 5 on the literal
    expect(detectForbiddenReferences('x("/authority/constitutions/c1/activate")', manifest))
      .toContain("forbidden path /authority/constitutions/{constitution_id}/activate");
    const hits = detectForbiddenReferences(
      'fetch("/authority/issuances", { method: "POST" }) // authority_issue_record',
      manifest,
    );
    expect(hits).toContain("forbidden path /authority/issuances");
    expect(hits).toContain("forbidden operation authority_issue_record");
    expect(hits).toContain("a write method");
    // a GET literal behind post, or a write literal behind get, is unmatched
    expect(detectConsumption('get<X>(`/authority/grants/${id}/revoke`)', contract).unmatched)
      .toEqual(["GET /authority/grants/{param}/revoke"]);
    expect(detectConsumption('post<X>(`/authority/holders`)', contract).unmatched)
      .toEqual(["POST /authority/holders"]);
  });

  it("a manifest that approved an unserved write would fail against the contract", () => {
    const op = ops.find((o) => o.operation_id === "authority_activate_constitution")!;
    expect(op.kind).toBe("write");
    expect(op.served).toBe(false);
    expect(manifest.approved_operation_ids).not.toContain("authority_activate_constitution");
  });
});
