// Typed HTTP client for the v2 Governed Agent Studio contract.
//
// A SEPARATE module from `client.ts`, deliberately. The v1 boundary test asserts
// that client consumes exactly its 17 approved operations; adding v2 calls to it
// would break that assertion, and relaxing the assertion to accommodate them would
// discard the guarantee it exists to give. Two clients, two allowlists, two
// verifications.
//
// SD-2 holds here too: there is no method on this client that issues, activates,
// revokes, grants, authorizes, clears or executes, and `V2_OPERATIONS` below is the
// closed set the boundary verifier checks against the contract.
import { apiBaseUrl } from "@/lib/config";
import { ApiClientError } from "./client";
import {
  decodeGap,
  type ConstitutionPreflightBody,
  type ConstitutionValidateBody,
  type GapAware,
  type PolicyCompileBody,
  type PolicyPackBody,
  type PublishShadowBody,
  type RegistryRegisterBody,
  type ReviewDecisionBody,
  type ReviewStartShadowRunBody,
  type SimulateRunBody,
  type V2Envelope,
} from "./types-v2";

/** The complete set of v2 operations this client consumes. Verified against the contract. */
export const V2_OPERATIONS = [
  "v2_constitution_validate",
  "v2_constitution_preflight",
  "v2_policy_validate",
  "v2_policy_synthesize",
  "v2_policy_compile",
  "v2_authority_list_policies",
  "v2_authority_read_policy",
  "v2_authority_read_decision",
  "v2_simulate_run",
  "v2_publish_shadow",
  "v2_observe_audit_ids",
  "v2_observe_audit_chain",
  // GAS-7 HR-D — Review Queue and Run Detail: four reads and one verbatim relay.
  "v2_review_list_queue",
  "v2_review_read_run",
  "v2_review_read_run_events",
  "v2_review_read_approval",
  "v2_review_submit_decision",
  // Front-door seam 5 (FD-9): the Registration screen. Typed intake; register is the
  // only write, and it records what an administrator asserted, conferring nothing.
  "v2_registry_register",
  "v2_registry_list",
  // Front-door seam 6 (FD-10.1 START_IS_A_RELAY): ask the governed runtime worker to
  // start the worker's own shadow run. Nothing of the studio's crosses (FD-10.3).
  "v2_review_start_shadow_run",
  // Front-door seam 7 (FD-11.1 OBSERVE_OVER_WORKER_LEDGER): the worker's own tenant's
  // audit-ledger rows by correlation id, as the worker read them (FD-11.3).
  "v2_observe_ledger_chain",
] as const;

async function v2Request<T>(pathAndQuery: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${pathAndQuery}`, {
      ...init,
      headers: { Accept: "application/json", ...(init?.headers ?? {}) },
    });
  } catch (err) {
    throw new ApiClientError(
      0,
      "network_error",
      "the Governed Agent Studio API is unreachable",
      undefined,
      err,
    );
  }
  const text = await response.text();
  let body: unknown = undefined;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = undefined;
    }
  }
  if (!response.ok) {
    const errObj = (body as { error?: { code?: string; message?: string; request_id?: string } })?.error;
    throw new ApiClientError(
      response.status,
      errObj?.code ?? "http_error",
      errObj?.message ?? `request failed with status ${response.status}`,
      errObj?.request_id,
      body,
    );
  }
  return body as T;
}

/**
 * Unwrap the envelope and narrow `result` through the gap contract.
 *
 * Every v2 call goes through here, so no screen can accidentally read a raw result
 * and miss an `available: false`.
 */
async function gap(pathAndQuery: string, init?: RequestInit): Promise<GapAware> {
  const envelope = await v2Request<V2Envelope>(pathAndQuery, init);
  return decodeGap(envelope.result);
}

const enc = encodeURIComponent;
const postJson = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

// -- 1 · Constitution -------------------------------------------------------
export const validateConstitution = (body: ConstitutionValidateBody) =>
  gap("/api/v2/constitution/validate", postJson(body));

/** Preflight ONLY. Issuance and activation are authority acts and are not offered. */
export const preflightConstitution = (body: ConstitutionPreflightBody) =>
  gap("/api/v2/constitution/preflight", postJson(body));

// -- 2 · Policy -------------------------------------------------------------
export const validatePolicyPack = (body: PolicyPackBody) =>
  gap("/api/v2/policy/validate", postJson(body));

export const synthesizePolicyPack = (body: PolicyPackBody) =>
  gap("/api/v2/policy/synthesize", postJson(body));

/** Requires a real approval record; there is no compile-without-approval path. */
export const compilePolicyPack = (body: PolicyCompileBody) =>
  gap("/api/v2/policy/compile", postJson(body));

// -- 3 · Authority (reads only) --------------------------------------------
export const listAuthorityPolicies = () => gap("/api/v2/authority/policies");

export const readAuthorityPolicy = (recordId: string) =>
  gap(`/api/v2/authority/policies/${enc(recordId)}`);

export const readAuthorityDecision = (decisionId: string) =>
  gap(`/api/v2/authority/decisions/${enc(decisionId)}`);

// -- 4 · Simulate -----------------------------------------------------------
export const runSimulation = (body: SimulateRunBody) =>
  gap("/api/v2/simulate/run", postJson(body));

// -- 5 · Publish (shadow only) ---------------------------------------------
export const publishShadow = (body: PublishShadowBody) =>
  gap("/api/v2/publish/shadow", postJson(body));

// -- 6 · Observe ------------------------------------------------------------
export const listAuditCorrelationIds = () => gap("/api/v2/observe/audit");

export const readAuditChain = (correlationId: string) =>
  gap(`/api/v2/observe/audit/${enc(correlationId)}`);

/**
 * Front-door seam 7 (FD-11): the worker's own tenant's audit-ledger rows for one
 * correlation id, with the worker's chain verification, returned as the worker read
 * them. No tenant, filter or proof is sent; nothing is re-derived here (FD-11.4).
 */
export const readLedgerChain = (correlationId: string) =>
  gap(`/api/v2/observe/ledger/${enc(correlationId)}`);

// -- 7 · Review (GAS-7 HR-D; owner ruling HR-1: display and transmit) -------
export const listReviewQueue = (requiredRole = "") => {
  const query = requiredRole ? `?required_role=${enc(requiredRole)}` : "";
  return gap("/api/v2/review/queue" + query);
};

export const readReviewRun = (instanceId: string) =>
  gap(`/api/v2/review/runs/${enc(instanceId)}`);

export const readReviewRunEvents = (instanceId: string) =>
  gap(`/api/v2/review/runs/${enc(instanceId)}/events`);

export const readReviewApproval = (approvalId: string) =>
  gap(`/api/v2/review/approvals/${enc(approvalId)}`);

/**
 * ID-1 (`PASS_THROUGH_OPAQUE_TOKEN`): the one header an opaque, review-service-bound
 * approver proof may travel in. Sent on the decision operation and on no other; the
 * value is never decoded, logged, stored or reused by this client.
 */
export const APPROVER_PROOF_HEADER = "X-Ugence-Approver-Proof";

/**
 * Relay a human's decision, verbatim. The studio adds no identity and reads nothing
 * but the review service's typed answer; whether the instance proceeds is decided by
 * the review service and the governed composition behind it, never here.
 *
 * `proof`, when the operator supplied one, rides this one request in
 * `APPROVER_PROOF_HEADER` and is dropped as soon as the request is built.
 */
export const submitReviewDecision = (body: ReviewDecisionBody, proof = "") => {
  const init = postJson(body);
  if (proof) {
    init.headers = { ...(init.headers as Record<string, string>), [APPROVER_PROOF_HEADER]: proof };
  }
  return gap("/api/v2/review/decisions", init);
};

/**
 * Front-door seam 6 (FD-10): ask the worker to start the worker's own shadow run.
 *
 * The body is the operator's correlation id or nothing. There is no parameter for a
 * workflow, task, provider, mode or digest: the worker holds the definition, the backend
 * pins the mode word `shadow`, and the worker refuses any other (FD-10.3). No proof
 * header travels here (ID-1). The answer is the worker's typed outcome, unchanged.
 */
export const startWorkerShadowRun = (body: ReviewStartShadowRunBody) =>
  gap("/api/v2/review/runs", postJson(body));

// -- 8 · Registration (front-door seam 5, FD-9) ------------------------------
/**
 * Record one typed system registration for this deployment's tenant. The tenant,
 * the derived registration id and `registered_by` are never sent from here; the
 * `owner_ref` is recorded as presented and unproven (FD-9.3).
 */
export const registerSystem = (body: RegistryRegisterBody) =>
  gap("/api/v2/registry/registrations", postJson(body));

/** The registrations in force for this deployment's tenant at `asOf` (or now). */
export const listRegistrations = (asOf = "") => {
  const query = asOf ? `?as_of=${enc(asOf)}` : "";
  return gap("/api/v2/registry/registrations" + query);
};
