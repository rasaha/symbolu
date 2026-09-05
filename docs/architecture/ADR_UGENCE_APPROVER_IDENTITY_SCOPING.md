# Ugence approver identity — scoping record

**Status: SCOPED AND RULED; AI-A, AI-B and AI-C implemented.** The five owner decisions in
§5 were ruled on 2026-09-05. Step AI-A of §6 shipped in `governed-review-service` 0.3.0
`[V]` (`identity.py`, `tests/test_identity.py`) and step AI-B in the studio `[V]`
(`clients/review.py`, `api/v2/review.py`, `client-v2.ts`,
`tests/test_review_proof_relay.py`); every later step is still entered only by its own
implementation prompt. This record adds no dependency, integrates no identity
provider and opens no route. It maps where a proven approver
identity enters the human-review path that GAS-7 built, states what already exists on
that path, and records the rulings. It reopens none of HR-1 to HR-5 or HE-1 to HE-5.

Three concerns stay separate throughout, and every ruling below preserves the
separation: **authentication** (who this is, proven by the IdP and carried as an
authentication reference), **eligibility and authorization** (what this principal may
decide, answered by the directory and carried as the authority reference), and
**decision recording** (what was decided, written by the ledger). No field carries two
of them, and no package answers more than one.

Evidence labels: `[V]` verified against this repository at the merge of PR #1626,
`[I]` inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question

Every decision the review service records is labelled `PRESENTED_UNPROVEN` `[V]`
(`governed-review-service/.../version.py`, `IDENTITY_PROOF`): the approver is a reference
the caller presented, and the eligibility port only says whether that reference *may*
decide. **Where can proof of who decided enter, without the studio holding identity,
without the directory reading the IdP, and without a second identity provider?**

## 2 — What exists, stage by stage

| # | Stage | What exists `[V]` | What is missing `[G]` |
|---|---|---|---|
| 1 | **The identity port** | Decision Authority owns the only identity seam: `IdentityProvider.authenticate(actor_id) -> ActorIdentity(actor_id, actor_type, authenticated)` (`decision-authority/.../identity/provider.py:17-32`); real deployments supply OIDC, SAML or workload identity; `StaticIdentityProvider` resolves unknown principals as unauthenticated SYSTEM, never as a human. Every case, action and execution authorization calls it, then a tenant-scoped `AccessRequest` (`services/_case_authz.py:24-56`). Human authorities require an authenticated `ActorType.HUMAN` (`decisions/status.py`, `HUMAN_AUTHORITIES`; `case_validation_service.py`). | No concrete provider exists anywhere in the repository. The review service may not import Decision Authority: its boundary test forbids `ugence_decision_authority` `[V]`. |
| 2 | **The directory** | Answers *what a principal may do*, never *who they are*; returns no `ActorType`; a role grant never substitutes for authentication; group-claim ingestion rejected (directory ADR D-4) `[V]` (`authority-directory/README.md:53-60`). | Nothing links a directory `principal_id` to an IdP subject except string equality by convention. |
| 3 | **The ledger** | `decide(approval_id, approver=ApproverRef, ...)` records `decided_by = approver.approver_id`, `decided_role`, `decided_authority_reference = approver.authority_reference`, `decided_at`, and an optional `signature_reference` (`approval-workflow/.../sqlite.py:254-266`; `workflow.py:80-95`); `is_fixture` marks offline examples. The ledger never authenticates (approval-workflow ADR §"Eligibility is a port"). | `decided_authority_reference` is whatever the caller put in the `ApproverRef`; today the review service copies the directory's `authority_reference` (`directory://roles/...`), which names a grant, not an authentication event. `signature_reference` is unused on this path. |
| 4 | **The review service** | `submit_decision(approval_id, decision, presented_approver, justification)`; the HTTP layer takes `presented_approver` from the request body; every outcome carries `identity_proof = PRESENTED_UNPROVEN` `[V]` (`service.py`, `http.py`). One `tenant_id` per service instance. | No session, no token validation, no assurance level, no tenant from the caller. The docstring of `http.py` already reserves the seam: "a deployment that fronts this app with an identity provider replaces the body field with the session's principal in its own composition root". |
| 5 | **The studio** | HR-1 `DISPLAY_AND_TRANSMIT`: relays the decision verbatim, holds no identity, computes no eligibility `[V]`; P3E authenticates one operator by HTTP Basic over HTTPS, single-tenant, no SSO, OIDC or SAML `[V]` (`docs/p3e/ACCESS_CONTROL.md:3-6`); the `authentication_seam` is a disabled placeholder that 401s when enabled `[V]` (`security/auth.py`). | The audit record stated "the studio forwards no credential and holds none"; ID-1 amends it to one forwarded, opaque, audience-bound token that the studio never parses, logs, persists or reuses. |
| 6 | **The linkage and the audit ledger** | `ReviewLinkage` carries `decided_by`, `decided_role`, `decided_at` and is appended to the control-plane ledger with `recorded_by` the service (HE-1) `[V]`. The control-plane ledger "says nothing about whether the writer was entitled" `[V]`. | No field carries an authentication reference; the linkage cannot distinguish a presented approver from a proven one. |
| 7 | **Tenancy** | Tenant-scoped today: the approval ledger (every record and the consumption key), the directory (every grant and event), the control-plane ledger (one chain per tenant), Decision Authority (every `AccessRequest`) `[V]`. | Tenant-unaware today: the durable engine (`ugence_art.*` has no tenant column; instance ids are unqualified) `[V]`, the runtime's checkpoint and execution state, the studio (single-tenant by P3E design), and the review service (one configured `tenant_id`, never taken from a caller). The roadmap's v1 criterion 2, "multi-tenant identity + org isolation enforced; approvals bound to real approver identity", is unmet `[V]` (roadmap §9). |

**Net finding.** Identity has exactly one ratified home, Decision Authority's
`IdentityProvider` port, and exactly one concrete implementation, a static one. The
human-review path bypasses that port entirely: it records a presented reference and
labels it honestly. Proof can enter only at the review service, at decision time,
through a port of the same shape; it must be carried as a reference the ledger and the
linkage already have fields for; and it must bind the caller's tenant to the
approval's tenant, which today nothing does.

## 3 — Boundaries

**Identity stays with the IdP.** No package in this repository becomes an identity
provider. The review service validates a proof it did not mint; the directory keeps
answering eligibility only; the studio keeps holding nothing.

**The port shape is compatible with Decision Authority's, the code is not.** The
review service may not import Decision Authority. Under ID-3 it defines an
`ApproverIdentityPort` of its own, structurally compatible with the existing seam
(`authenticate(...) -> (actor_id, actor_type, authenticated)` plus the verified claims
the ledger needs), so one OIDC adapter can serve both. It moves to governance-contracts
only when a second real consumer exists, by a separate ruling.

**A proven decision is a human decision.** Decision Authority's rule carries over
verbatim: `HUMAN_AUTHORITIES` require an authenticated `HUMAN`; an AI or SYSTEM actor
never decides; an unauthenticated principal is refused before the ledger is touched.

**The proof is a reference, never a secret, and it is not the authority reference.**
Tokens, sessions and credentials are never stored, logged or written to any ledger.
Under ID-2 three references are recorded, each answering one question: `decided_by`,
an unambiguously encoded issuer-qualified subject (who); `authentication_reference`, a
deterministic, digest-bound reference to the verified authentication claims (how it was
proven); and `decided_authority_reference`, the directory grant that authorized the
decision (why they may). The first two come from the IdP proof, the third from the
directory, and none is derived from another.

**Tenant comes from the proof; configuration is a labelled exception.** Under ID-4 a
verified tenant claim is authoritative and must equal the approval's `tenant_id`. A
configured tenant is used only by a service explicitly configured and labelled
`SINGLE_TENANT`; in multi-tenant mode a missing, ambiguous or mismatched claim is
refused. The durable engine stays tenant-unaware in this sequence; the join from
instance to tenant is the approval's `subject_ref`.

**Assurance is recorded now and gates enforcement later.** Under ID-5 the verified
`acr` and `amr` claims are recorded as presented, and no threshold is imposed while the
system is reference-grade and shadow-only. A separately ratified assurance policy is a
mandatory entry gate before controlled enforcement or LIVE execution; where that policy
is absent, enforcement fails closed.

**Prohibitions, stated once.** No IdP client, JOSE or crypto dependency in
`governed-review`, `approval-workflow` or `authority-directory`; no `ActorType` in the
directory; no credential in the studio backend beyond the one opaque, audience-bound
token ID-1 permits, never parsed, logged, persisted or reused; no `acr` or `amr` claim
invented where the IdP asserted none; no LIVE execution.

## 4 — Failure matrix

| # | Failure | Required property | Holds today `[V]` | Gap `[G]` | Proving test |
|---|---|---|---|---|---|
| 1 | Unauthenticated caller submits a decision | Refused before any record changes | Nothing: the body is trusted | The whole seam | Submit with no proof: `REFUSED_UNAUTHENTICATED`, ledger PENDING, no signal |
| 2 | Authenticated as A, presents approver B | Refused; the presented reference must equal the proven, issuer-qualified subject | Nothing | Binding rule | Proof A, body B: refused; ledger unchanged |
| 3 | Proven subject is not a directory principal | Eligibility refused by the existing port; authentication alone authorizes nothing | `EligibilityRefused` on unknown principal `[V]` | Subject-to-principal mapping is string equality | Subject not in directory: `REFUSED_INELIGIBLE`, `decided_by` unwritten |
| 4 | Proof tenant ≠ approval tenant | Refused as not reviewable in that tenant | Service compares approval tenant to its configured tenant `[V]` | Tenant from proof (ID-4) | Proof tenant-b, approval tenant-a: `REFUSED_NOT_REVIEWABLE` |
| 5 | AI or service actor with a human role grant | Refused: a role never makes a human | Decision Authority's rule `[V]`; the review service has none | Actor-type check at the service | `ActorType.SYSTEM` authenticated: refused |
| 6 | Proof expires between queue read and decision | Refused at decision time; the queue read proves nothing | Nothing | Validation at the write, not the read | Expired proof on submit: refused; earlier read irrelevant |
| 7 | IdP unreachable or the token cannot be verified | Fail closed: no decision recorded, typed outcome | Nothing | Fail-closed rule | Adapter raises: `REFUSED_IDENTITY_UNAVAILABLE`, ledger unchanged |
| 8 | Replay of an identical decision under a different proof | Row-1 replay requires the same issuer-qualified subject, not only the same presented id | Replay compares `decided_by` and role `[V]` | Compare the authentication subject | Same approval, second subject: `REFUSED_ALREADY_DECIDED` |
| 9 | A recorded reference is altered after the fact | The ledger chains and the linkage digest detect it; `authentication_reference` is digest-bound to the verified claims | Approval ledger and control-plane chains are hash-linked `[V]` | `authentication_reference` is not yet a field of the ledger record or the linkage (ID-2) | Alter `decided_by` or `authentication_reference`: chain verification fails; recompute the reference from the claims: mismatch |
| 10 | Assurance below a later-required level (no MFA) | Recorded now; refused only under the ratified assurance policy (ID-5) | Nothing | Recording of `acr`/`amr` | Proof without `amr`: recorded, decision stands, outcome names the recorded assurance |
| 11 | `SINGLE_TENANT` service, proof carries no tenant claim | Configured tenant used and named as the source on the outcome | Configured tenant `[V]` | Explicit mode and label (ID-4) | No claim, `SINGLE_TENANT`: decision carries `tenant_source = CONFIGURED_SINGLE_TENANT` |
| 12 | Multi-tenant service, proof carries a missing, ambiguous or mismatched tenant claim | Refused; configuration never fills the gap | Nothing | Mode rule (ID-4) | No claim, multi-tenant: `REFUSED_TENANT_UNPROVEN`; two claims: refused |
| 13 | Enforcement or LIVE entered with no ratified assurance policy | Fails closed at the entry gate | Nothing: no enforcement path exists `[V]` | The gate (ID-5) | Enforcement configured, policy absent: refused at composition |
| 14 | The studio parses, logs, persists or reuses the forwarded token | Never; the token is opaque to the studio and audience-bound to the service | HR-1: the studio holds no identity `[V]` | The relay (ID-1) | Security tests assert no decode, no log line, no store, and a studio-audience token is refused by the service |

## 5 — Owner decisions (ruled 2026-09-05)

| # | Ruling |
|---|---|
| **ID-1** | **`PASS_THROUGH_OPAQUE_TOKEN`.** The studio may forward one IdP-issued token that is audience-bound to the review service. It never parses, logs, persists or reuses it. HR-D's five routes and single frontend client stand; the screen audit's "forwards no credential" is amended to this one opaque forward. |
| **ID-2** | **`SEPARATE_AUTHENTICATION_AND_AUTHORITY_REFERENCES`.** `decided_by` is an unambiguously encoded issuer-qualified subject. `decided_authority_reference` remains the organizational directory grant or reference proving authorization. A distinct `authentication_reference` carries a deterministic, digest-bound reference to the verified authentication claims, never the token; it binds issuer, subject, audience, tenant, authentication time, validity and the available `acr`/`amr`; a token-id digest is optional because `jti` may be absent. `signature_reference` remains unused. |
| **ID-3** | **`SERVICE_LOCAL_PORT_UNTIL_SECOND_CONSUMER`.** `ApproverIdentityPort` begins in `governed-review-service`, structurally compatible with the existing identity seam but importing no Decision Authority package. Promotion to governance-contracts requires a second real consumer and a separate ruling. |
| **ID-4** | **`TENANT_FROM_PROOF_WITH_EXPLICIT_SINGLE_TENANT_FALLBACK`.** A verified tenant claim is authoritative. The configured fallback is permitted only when the service is explicitly configured and labelled `SINGLE_TENANT`; multi-tenant mode refuses missing, ambiguous or mismatched tenant claims. |
| **ID-5** | **`RECORD_NOW_ENFORCE_BEFORE_LIVE`.** AI-A records verified `acr`/`amr` without imposing an assurance threshold while the system remains reference-grade and shadow-only. A separately ratified assurance policy is a mandatory entry gate before controlled enforcement or LIVE execution; absence of that policy fails closed. |

## 6 — Sequence and maturity ceiling

Entry conditions are met; each step is entered only by its own implementation prompt.

1. **AI-A · Port and proof shape** in `governed-review-service`: the
   `ApproverIdentityPort` (ID-3), a static reference adapter refused in production
   mode, the verified-claims shape and the deterministic `authentication_reference`
   (ID-2), the binding and tenant rules with the explicit `SINGLE_TENANT` mode (ID-4),
   `acr`/`amr` recorded without a threshold (ID-5); rows 1 to 8, 10, 11 and 12 at unit
   level. Every decision carries `identity_proof` = `PRESENTED_UNPROVEN` or
   `IDP_AUTHENTICATED`. Label: **Core implemented, shadow-only**.
   **Shipped in 0.3.0 `[V]`**: `ApproverIdentityPort`, `VerifiedClaims`,
   `ApproverIdentity`, `subject_reference`, `authentication_reference`, `TenantMode`,
   `RecordedAssurance`, `StaticApproverIdentityAdapter` (refused in production mode);
   the decision route reads one opaque proof header (`PROOF_HEADER`); the reference,
   tenant source and assurance are carried on the decision outcome and the durable
   `EXTERNAL_SIGNAL:review_decision` payload. Rows 1 to 8, 10, 11 and 12 are proven at
   unit level. Not yet: the approval record and the linkage carry no
   `authentication_reference` (AI-D, row 9). With only the fixture adapter, every
   decision is still `PRESENTED_UNPROVEN`.
2. **AI-B · Relay** in the studio per ID-1: one opaque, audience-bound header, never
   parsed; the security tests assert it is never logged, persisted or reused (row 14).
   Label: **Core implemented**.
   **Shipped `[V]`**: the studio backend reads `X-Ugence-Approver-Proof` from the
   operator's decision request and forwards it, unread, on `POST /review/decisions`
   only; the review client refuses to attach it to any other route before a
   connection opens; the route declares no parameter, so the frozen v2 contract, the
   generated client and the boundary manifest are unchanged. The frontend takes the
   proof in a password field held in component state, sends it once in the header on
   the decision operation, and clears it. Row 14 is proven on both sides: no decode,
   no log line, no store, no reuse, absent from every read. The proof's origin is
   still the operator's paste: no IdP issues it (AI-C).
3. **AI-C · OIDC adapter** as its own small package, the first crypto and IdP-client
   dependency on this path, validated against a real issuer in CI only if a test issuer
   can run without egress. Label: **Reference-grade**.
   **Shipped `[V]`** as `packages/integration/approver-identity-jwt` 0.1.0 under
   IA-1 to IA-5 (`ADR_UGENCE_APPROVER_IDENTITY_ADAPTER_SCOPING.md`): locally
   validated RFC 9068 access tokens, PyJWT over `cryptography`, RS256/ES256/EdDSA
   only, a configured JWKS cached by `kid` with one refresh then fail-closed, the
   explicit IA-4 claim mapping, no wall clock, no token ever logged, stored or
   returned. Proven only against its in-process issuer: label
   `REFERENCE_GRADE_SHADOW_ONLY`, `ISSUER_VALIDATION = IN_PROCESS_ISSUER_ONLY`;
   real enterprise-issuer validation remains unproven, and no composition root
   wires it yet.
4. **AI-D · Ledger and linkage carry the proof** (ID-2): `authentication_reference` as
   an additive field of the approval record and of `ReviewLinkage`, digest-bound; row 9.
   Label: **Core implemented**.
5. **AI-E · Assurance policy and gate** (ID-5): the ratified policy, and the entry
   gate that fails closed without it (row 13). Entered only when enforcement or LIVE
   is itself being scoped.

**Ceiling.** Until AI-C runs against a real enterprise IdP, every decision stays
`PRESENTED_UNPROVEN` and the roadmap's v1 criterion 2 stays unmet. With AI-C, a
decision is `IDP_AUTHENTICATED` at reference-grade, shadow-only; it carries a recorded
assurance level and enforces none. Controlled enforcement and LIVE execution remain
behind AI-E's gate, the P3E external security review and the private OCI mirror, none
of which this sequence builds. Multi-tenant *isolation* of the durable engine is
outside this sequence entirely.

## 7 — Next step

AI-D, the approval record and the linkage carrying `authentication_reference` (row
9), then AI-E. Enterprise-issuer validation of AI-C waits on an owner-provisioned
issuer.
