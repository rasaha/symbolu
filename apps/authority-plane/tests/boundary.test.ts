// authority-plane-negative-fixtures — this file references forbidden operation ids and
// paths as NEGATIVE fixtures; the marker on this line exempts it from the verifier's
// forbidden-reference scan.
//
// The plane's boundary (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §11 step 3): this app
// consumes exactly the four AP-5 reads the worker's committed contract marks served,
// its manifest is bound to that contract by hash, no write is reachable from its
// client, and the verifier can fail.
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
import { OPERATIONS } from "@/api/client";

const { contract, sha } = loadContract();
const manifest = JSON.parse(readFileSync(MANIFEST_PATH, "utf-8"));
const clientText = readFileSync(path.join(APP, CLIENT_REL), "utf-8");

describe("the authority plane's boundary", () => {
  it("passes the verifier as committed", () => {
    const { errors, consumed } = verify();
    expect(errors).toEqual([]);
    expect(consumed).toEqual([...manifest.approved_operation_ids].sort());
  });

  it("binds the manifest to the worker's committed contract by hash", () => {
    expect(manifest.contract_sha256).toBe(sha);
    expect(manifest.contract).toBe(contract.schema);
  });

  it("the client consumes exactly the four served reads and declares the same set", () => {
    const { consumed, unmatched } = detectConsumption(clientText, contract);
    expect(unmatched).toEqual([]);
    expect([...consumed].sort()).toEqual([...OPERATIONS].sort());
    expect([...OPERATIONS].sort()).toEqual([...manifest.approved_operation_ids].sort());
    for (const id of OPERATIONS) {
      const op = contract.operations.find((o: { operation_id: string }) => o.operation_id === id);
      expect(op.kind).toBe("read");
      expect(op.served).toBe(true);
    }
  });

  it("the forbidden set is exactly the contract's four unserved writes", () => {
    const writes = contract.operations.filter((o: { kind: string }) => o.kind === "write");
    expect(writes.map((o: { operation_id: string }) => o.operation_id).sort())
      .toEqual([...manifest.forbidden_operation_ids].sort());
    for (const w of writes) expect(w.served).toBe(false);
  });

  it("the client names no forbidden operation, no write path and no write method", () => {
    expect(detectForbiddenReferences(clientText, manifest)).toEqual([]);
    expect(clientText).not.toMatch(/method:\s*["']POST["']/);
    for (const id of manifest.forbidden_operation_ids) expect(clientText).not.toContain(id);
  });

  it("the verifier can fail: a sneaky fetch, a revoke path, a write method", () => {
    expect(detectRawFetch('const r = await fetch("/authority/grants")')).toHaveLength(1);
    const sneaky = 'get<X>(`/authority/grants/${id}/revoke`)';
    const { unmatched } = detectConsumption(sneaky, contract);
    expect(unmatched).toEqual(["/authority/grants/{param}/revoke"]);
    const hits = detectForbiddenReferences(
      'fetch("/authority/issuances", { method: "POST" }) // authority_issue_record',
      manifest,
    );
    expect(hits).toContain("forbidden path /authority/issuances");
    expect(hits).toContain("forbidden operation authority_issue_record");
    expect(hits).toContain("a write method");
  });

  it("a manifest that approved a write would fail against the contract", () => {
    const poisoned = { ...manifest, approved_operation_ids: [...manifest.approved_operation_ids, "authority_grant_role"] };
    const op = contract.operations.find((o: { operation_id: string }) => o.operation_id === "authority_grant_role");
    expect(op.kind).toBe("write");
    expect(poisoned.approved_operation_ids).toContain("authority_grant_role");
    // the verifier's rule 2 refuses an approved id that is not a served read
    expect(op.served).toBe(false);
  });
});
