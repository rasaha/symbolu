// authority-plane-negative-fixtures — this file references forbidden operation ids and
// paths as NEGATIVE fixtures; the marker on this line exempts it from the verifier's
// forbidden-reference scan.
//
// The plane's boundary (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §11 step 3; §18, AP-3
// controlling): this app consumes exactly the four AP-5 reads the worker's committed
// contract marks served, its manifest is bound to that contract by hash, no write is
// reachable from its client while the contract serves none, and the verifier can fail.
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
import { OPERATIONS, PROOF_HEADER } from "@/api/client";

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

  it("the client consumes exactly the four served reads and declares the same set", () => {
    const { consumed, unmatched } = detectConsumption(clientText, contract);
    expect(unmatched).toEqual([]);
    expect([...consumed].sort()).toEqual([...OPERATIONS].sort());
    expect([...OPERATIONS].sort()).toEqual([...manifest.approved_operation_ids].sort());
    for (const id of OPERATIONS) {
      const op = ops.find((o) => o.operation_id === id)!;
      expect(op.kind).toBe("read");
      expect(op.served).toBe(true);
    }
  });

  it("the contract serves no write (AP-3 controlling), and the forbidden set is exactly its four writes", () => {
    expect(contract.served.writes).toEqual([]);
    expect(contract.implemented_unserved_writes.sort()).toEqual(["authority_grant_role", "authority_revoke_grant"]);
    const writes = ops.filter((o) => o.kind === "write");
    expect(writes.map((o) => o.operation_id).sort()).toEqual([...manifest.forbidden_operation_ids].sort());
    for (const w of writes) expect(w.served).toBe(false);
  });

  it("the client names no forbidden operation, no write path and no write method, and never sends the proof header", () => {
    expect(detectForbiddenReferences(clientText, manifest)).toEqual([]);
    expect(clientText).not.toMatch(/method:\s*["']POST["']/);
    for (const id of manifest.forbidden_operation_ids) expect(clientText).not.toContain(id);
    expect(clientText).not.toMatch(/\bpost<[^>]*>\(/);
    expect(clientText).not.toContain("/revoke");
    expect(clientText).not.toContain("/authority/constitutions");
    expect(clientText).not.toContain("/authority/issuances");
    // the header is declared, never placed in a request
    expect(clientText).not.toMatch(/\[PROOF_HEADER\]/);
  });

  it("the verifier can fail: a sneaky fetch, a revoke path, an activate path, an issue path, a write method", () => {
    expect(detectRawFetch('const r = await fetch("/authority/grants")')).toHaveLength(1);
    const sneaky = 'get<X>(`/authority/grants/${id}/revoke`)';
    const { unmatched } = detectConsumption(sneaky, contract);
    expect(unmatched).toEqual(["GET /authority/grants/{param}/revoke"]);
    // a post literal on an unserved write is consumed and would fail the approved-set comparison
    const { consumed } = detectConsumption('post<X>(`/authority/grants`)', contract);
    expect([...consumed]).toEqual(["authority_grant_role"]);
    expect(manifest.approved_operation_ids).not.toContain("authority_grant_role");
    expect(detectForbiddenReferences('x("/authority/constitutions/c1/activate")', manifest))
      .toContain("forbidden path /authority/constitutions/{constitution_id}/activate");
    const hits = detectForbiddenReferences(
      'fetch("/authority/issuances", { method: "POST" }) // authority_issue_record',
      manifest,
    );
    expect(hits).toContain("forbidden path /authority/issuances");
    expect(hits).toContain("forbidden operation authority_issue_record");
    expect(hits).toContain("a write method");
  });

  it("a manifest that approved a write would fail against the contract", () => {
    for (const id of ["authority_grant_role", "authority_revoke_grant", "authority_activate_constitution", "authority_issue_record"]) {
      const op = ops.find((o) => o.operation_id === id)!;
      expect(op.kind).toBe("write");
      expect(op.served).toBe(false);
      expect(manifest.approved_operation_ids).not.toContain(id);
    }
  });
});
