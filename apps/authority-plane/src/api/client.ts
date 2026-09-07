/**
 * The authority plane's client — the only file in this app that opens an HTTP
 * connection. It reaches exactly the six operations the governed runtime worker's
 * committed contract marks served: the four AP-5 reads, and since ADR §16 (AW-1,
 * AW-2) the two directory writes, load and revoke, each behind the identity gate.
 *
 * `security/approved-operations.json` names those six, and `scripts/verify-boundary.mjs`
 * checks this file's call sites against it and against the worker's own committed
 * contract. The two unserved writes, activate and issue, cannot be named here.
 *
 * A write carries the operator's issuer token on the proof header and nothing else; a
 * read never carries it (AW-3). Without a presented token no write is sent.
 */

const BASE = import.meta.env.VITE_WORKER_BASE_URL || "/api";

/** The header the worker reads a write's proof from: the decision route's own. */
export const PROOF_HEADER = "X-Ugence-Approver-Proof";

/** The four reads this client consumes. */
export const READ_OPERATIONS = [
  "authority_list_grants",
  "authority_list_holders",
  "authority_read_committee",
  "authority_read_grant_events",
] as const;

/** The two served writes this client consumes, behind the identity gate. */
export const WRITE_OPERATIONS = ["authority_grant_role", "authority_revoke_grant"] as const;

/** Everything this client consumes. Verified against the manifest and the contract. */
export const OPERATIONS = [...READ_OPERATIONS, ...WRITE_OPERATIONS] as const;

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

/** A typed refusal of a read: a not-found or an untyped identifier. */
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

/** A recorded write: what the worker says about who did it, and what it now holds. */
export interface WriteRecorded {
  result: "RECORDED";
  recorded: true;
  plane: "authority";
  ruling: string;
  operation: string;
  tenant_id: string;
  as_of: string;
  identity_proof: "IDP_AUTHENTICATED";
  subject: string;
  authentication_reference: string;
  issuer_validation: string;
  provenance: string;
  maturity: string;
  event: "GRANTED" | "REVOKED";
  grant: Grant;
}

/** A typed refusal of a write: the gate (AW-5) or the intake (AW-4), never recorded. */
export interface WriteRefusal {
  result: string;
  recorded: false;
  plane: "authority";
  ruling: string;
  operation: string;
  reason: string;
  issuer_validation: string;
  maturity: string;
  grant?: Grant;
}

export type WriteOutcome =
  | { kind: "recorded"; answer: WriteRecorded }
  | { kind: "refusal"; status: number; refusal: WriteRefusal }
  | { kind: "unreachable"; reason: string };

/** The typed fields of a role grant, and nothing else (AW-4). The worker derives the id. */
export interface LoadGrantRequest {
  principal: { principal_id: string; principal_kind: string; display_ref?: string; quorum?: number };
  role: string;
  scope: string;
  issued_at: string;
  expires_at: string;
  authority_reference?: string;
  member_of?: string;
}

function parse(text: string): unknown {
  try {
    return text ? JSON.parse(text) : undefined;
  } catch {
    return undefined;
  }
}

async function get<T extends ReadEnvelope>(path: string): Promise<Outcome<T>> {
  let response: Response;
  try {
    // a read carries no proof: the header is never sent here (AW-3)
    response = await fetch(`${BASE}${path}`, { headers: { Accept: "application/json" } });
  } catch (err) {
    return { kind: "unreachable", reason: `the governed runtime worker is unreachable: ${String(err)}` };
  }
  const body = parse(await response.text());
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

async function post<T extends WriteRecorded>(path: string, body: unknown, proof: string): Promise<WriteOutcome> {
  if (!proof) {
    // never sent: the screens disable every write control without a token, and this
    // is the client's own refusal should one reach it anyway
    return {
      kind: "refusal", status: 0,
      refusal: { result: "REFUSED_NO_TOKEN_PRESENTED", recorded: false, plane: "authority", ruling: "AW-3",
                 operation: "", reason: "no issuer token is presented in this session; the write was not sent",
                 issuer_validation: "", maturity: "" },
    };
  }
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json", [PROOF_HEADER]: proof },
      body: JSON.stringify(body),
    });
  } catch (err) {
    return { kind: "unreachable", reason: `the governed runtime worker is unreachable: ${String(err)}` };
  }
  const parsed = parse(await response.text()) as Partial<WriteRefusal> | Partial<T> | undefined;
  if (!response.ok) {
    if (parsed && parsed.recorded === false && typeof parsed.result === "string") {
      return { kind: "refusal", status: response.status, refusal: parsed as WriteRefusal };
    }
    return { kind: "unreachable", reason: `the worker answered ${response.status} without a typed refusal` };
  }
  const answer = parsed as T | undefined;
  if (!answer || answer.result !== "RECORDED" || answer.plane !== "authority" || answer.recorded !== true) {
    return { kind: "unreachable", reason: "the worker returned a shape this build does not recognise" };
  }
  return { kind: "recorded", answer };
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

/** Load one time-bounded role grant (AW-1, AW-4). Sent only with a presented token. */
export const grantRole = (request: LoadGrantRequest, proof: string) =>
  post<WriteRecorded>(`/authority/grants`, request, proof);

/** Revoke one grant with a reason (AW-1). Sent only with a presented token. */
export const revokeGrant = (grantId: string, reason: string, proof: string) =>
  post<WriteRecorded>(`/authority/grants/${enc(grantId)}/revoke`, { reason }, proof);
