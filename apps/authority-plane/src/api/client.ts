/**
 * The authority plane's client — the only file in this app that opens an HTTP
 * connection, and it reaches exactly the four AP-5 reads the governed runtime worker
 * serves (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §11 step 3).
 *
 * `security/approved-operations.json` names those four, and `scripts/verify-boundary.mjs`
 * checks this file's call sites against it and against the worker's own committed
 * contract. There is no method here that grants, revokes, activates or issues: the
 * plane's four writes wait on the identity gate (AP-3), and until a later step's
 * record says otherwise this client cannot name them.
 */

const BASE = import.meta.env.VITE_WORKER_BASE_URL || "/api";

/** The four reads this client consumes. Verified against the manifest and the contract. */
export const OPERATIONS = [
  "authority_list_grants",
  "authority_list_holders",
  "authority_read_committee",
  "authority_read_grant_events",
] as const;

/** Every read answer the worker gives carries these, and the client shows all of them. */
export interface ReadEnvelope {
  result: "READ";
  plane: "authority";
  ruling: "AP-5";
  tenant_id: string;
  as_of: string;
  read_authenticated: false;
  decision_identity_proof: "IDP_AUTHENTICATED" | "PRESENTED_UNPROVEN";
  issuer_validation: string;
  provenance: string;
  maturity: string;
}

/** A typed refusal from the worker: a not-found or an untyped identifier. */
export interface Refusal {
  result: "NOT_FOUND" | "REFUSED_UNTYPED";
  plane: "authority";
  ruling: "AP-5";
  reason: string;
  maturity: string;
}

export type Grant = Record<string, unknown> & { grant_id: string; role: string; scope: string };
export type GrantEvent = Record<string, unknown> & { event_type: string; sequence: number };

export interface GrantsAnswer extends ReadEnvelope { principal_id: string; grants: Grant[]; grant_count: number }
export interface HoldersAnswer extends ReadEnvelope { role: string; scope: string; holders: Grant[]; holder_count: number }
export interface CommitteeAnswer extends ReadEnvelope {
  committee_id: string;
  report: {
    committee: { principal_id: string; principal_kind: string; display_ref: string; quorum: number };
    role: string; scope: string; quorum: number; members: Grant[]; member_count: number;
    quorum_met_at_as_of: boolean; as_of: string;
  };
}
export interface EventsAnswer extends ReadEnvelope { grant_id: string; grant: Grant; events: GrantEvent[]; event_count: number }

/** What a screen renders: the worker's answer, its typed refusal, or the plane being unreachable. */
export type Outcome<T> =
  | { kind: "answer"; answer: T }
  | { kind: "refusal"; status: number; refusal: Refusal }
  | { kind: "unreachable"; reason: string };

async function get<T extends ReadEnvelope>(path: string): Promise<Outcome<T>> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, { headers: { Accept: "application/json" } });
  } catch (err) {
    return { kind: "unreachable", reason: `the governed runtime worker is unreachable: ${String(err)}` };
  }
  const text = await response.text();
  let body: unknown;
  try {
    body = text ? JSON.parse(text) : undefined;
  } catch {
    body = undefined;
  }
  if (response.status === 404 || response.status === 422) {
    const refusal = body as Refusal | undefined;
    if (refusal && (refusal.result === "NOT_FOUND" || refusal.result === "REFUSED_UNTYPED")) {
      return { kind: "refusal", status: response.status, refusal };
    }
  }
  if (!response.ok) {
    return { kind: "unreachable", reason: `the worker answered ${response.status} without a typed refusal` };
  }
  const answer = body as T | undefined;
  if (!answer || answer.result !== "READ" || answer.plane !== "authority") {
    return { kind: "unreachable", reason: "the worker returned a shape this build does not recognise" };
  }
  return { kind: "answer", answer };
}

const enc = encodeURIComponent;

export const listGrants = (principalId: string) =>
  get<GrantsAnswer>(`/authority/grants?principal_id=${enc(principalId)}`);

export const listHolders = (role: string, scope: string) =>
  get<HoldersAnswer>(`/authority/holders?role=${enc(role)}&scope=${enc(scope)}`);

export const readCommittee = (committeeId: string, role: string, scope: string) =>
  get<CommitteeAnswer>(`/authority/committees/${enc(committeeId)}?role=${enc(role)}&scope=${enc(scope)}`);

export const readGrantEvents = (grantId: string) =>
  get<EventsAnswer>(`/authority/grants/${enc(grantId)}/events`);
