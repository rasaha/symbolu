# Ugence approver identity — scoping record

**Status: SCOPED, NOT RULED — nothing here is implemented.** This record authorizes
no code change, adds no dependency, integrates no identity provider and opens no
route. It maps where a proven approver identity could enter the human-review path
that GAS-7 built, states what already exists on that path, and records the five owner
decisions that must be ruled before any step is entered. It reopens none of HR-1 to
HR-5 or HE-1 to HE-5.

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
| 5 | **The studio** | HR-1 `DISPLAY_AND_TRANSMIT`: relays the decision verbatim, holds no identity, computes no eligibility `[V]`; P3E authenticates one operator by HTTP Basic over HTTPS, single-tenant, no SSO, OIDC or SAML `[V]` (`docs/p3e/ACCESS_CONTROL.md:3-6`); the `authentication_seam` is a disabled placeholder that 401s when enabled `[V]` (`security/auth.py`). | The audit record states "the studio forwards no credential and holds none" `[V]` (`HUMAN_REVIEW_SCREEN_API_AUDIT.md`), which forecloses one of the two viable session boundaries (§3, ID-1). |
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

**The port shape is Decision Authority's, the code is not.** The review service may not
import Decision Authority. It defines a structurally identical port of its own
(`authenticate(actor_id) -> (actor_id, actor_type, authenticated)` plus the claims the
ledger needs) so a single OIDC adapter can satisfy both. Whether that port belongs in
governance-contracts is ID-3.

**A proven decision is a human decision.** Decision Authority's rule carries over
verbatim: `HUMAN_AUTHORITIES` require an authenticated `HUMAN`; an AI or SYSTEM actor
never decides; an unauthenticated principal is refused before the ledger is touched.

**The proof is a reference, never a secret.** Tokens, sessions and credentials are
never stored, logged or written to any ledger. What is recorded is an issuer-qualified
subject and a reference to the authentication event, in fields that already exist.

**Tenant comes from the proof, not from configuration.** Once a session exists, the
approval's `tenant_id` must equal the session's tenant claim, and the service stops
being configured for one tenant. The durable engine stays tenant-unaware in this
sequence; the join from instance to tenant is the approval's `subject_ref`.

**Prohibitions, stated once.** No IdP client, JOSE or crypto dependency in
`governed-review`, `approval-workflow` or `authority-directory`; no `ActorType` in the
directory; no credential in the studio backend beyond the transient relay ID-1 may
permit; no MFA claim invented where the IdP asserted none; no LIVE execution.

## 4 — Failure matrix

| # | Failure | Required property | Holds today `[V]` | Gap `[G]` | Proving test |
|---|---|---|---|---|---|
| 1 | Unauthenticated caller submits a decision | Refused before any record changes | Nothing: the body is trusted | The whole seam | Submit with no session: `REFUSED_UNAUTHENTICATED`, ledger PENDING, no signal |
| 2 | Authenticated as A, presents approver B | Refused; the presented reference must equal the proven subject | Nothing | Binding rule | Session A, body B: refused; ledger unchanged |
| 3 | Proven subject is not the directory principal | Eligibility refused by the existing port | `EligibilityRefused` on unknown principal `[V]` | Subject-to-principal mapping is string equality | Subject not in directory: `REFUSED_INELIGIBLE`, `decided_by` unwritten |
| 4 | Session tenant ≠ approval tenant | Refused as not reviewable in this tenant | Service compares approval tenant to its configured tenant `[V]` | Tenant from proof | Session tenant-b, approval tenant-a: `REFUSED_NOT_REVIEWABLE` |
| 5 | AI or service actor with a human role grant | Refused: a role never makes a human | Decision Authority's rule `[V]`; the review service has none | Actor-type check at the service | `ActorType.SYSTEM` authenticated: refused |
| 6 | Session expires between queue read and decision | Refused at decision time; the queue read proves nothing | Nothing | Validation at the write, not the read | Expired token on submit: refused; earlier read irrelevant |
| 7 | IdP unreachable | Fail closed: no decision recorded, typed outcome | Nothing | Fail-closed rule | Adapter raises: `REFUSED_IDENTITY_UNAVAILABLE`, ledger unchanged |
| 8 | Replay of an identical decision under a different session | Row-1 replay requires the same proven subject, not only the same presented id | Replay compares `decided_by` and role `[V]` | Compare the authentication subject too | Same approval, second subject: `REFUSED_ALREADY_DECIDED` |
| 9 | Proof reference tampered after the fact | The linkage digest and the ledger chains detect it | Approval ledger and control-plane chains are hash-linked `[V]` | The reference is not yet in the linkage | Alter `decided_authority_reference`: chain verification fails |
| 10 | Assurance below the required level (no MFA where required) | Recorded in 0.1; enforced per ID-5 | Nothing | Assurance policy | Token without the required `amr`: outcome names the shortfall |
| 11 | Single-tenant deployment with no tenant claim | Configured tenant used only when the proof carries none, and the outcome says so | Configured tenant `[V]` | Precedence rule | No claim: decision carries `tenant_source = CONFIGURED` |

## 5 — Owner decisions `[R]`

| # | Decision | Recommendation |
|---|---|---|
| **ID-1** | Where does the human's session reach the review service? `PASS_THROUGH_OPAQUE_TOKEN`: the studio forwards the browser's IdP-issued, audience-bound token as an opaque header it never parses, logs or stores. `BROWSER_DIRECT_SESSION`: the browser holds a session with the review service and posts decisions to it directly; the studio's decision relay retires. | **`PASS_THROUGH_OPAQUE_TOKEN`.** It keeps HR-D's five routes, the single frontend client and the SD-2 scans intact, and the audience binding means the studio cannot use what it forwards. It amends one sentence of the screen audit ("forwards no credential") to "forwards one opaque, audience-bound proof and holds none". |
| **ID-2** | What the ledger records as proof. | **`decided_by` = issuer-qualified subject (`<issuer>#<sub>`); `decided_authority_reference` = a reference to the authentication event (issuer, `auth_time`, a digest of `jti`), never the token; `signature_reference` unused until a signing decision exists.** The linkage gains `identity_proof` and `authentication_reference`. |
| **ID-3** | Where the port lives. | **A neutral `ApproverIdentityPort` in the review service in 0.1, structurally identical to Decision Authority's `IdentityProvider` plus tenant and assurance claims; promoted to governance-contracts only when a second consumer exists.** No import of Decision Authority. |
| **ID-4** | Tenant binding. | **`TENANT_FROM_PROOF`**: the session's tenant claim binds; the configured tenant is the fallback for single-tenant deployments and is named as such on every outcome (row 11). The durable engine stays tenant-unaware; a tenant column is a separate DBOS ADR amendment if ever needed. |
| **ID-5** | Assurance level. | **`RECORD_ACR_ENFORCE_LATER`**: 0.1 records `acr`/`amr` as presented and refuses nothing on assurance; enforcement (MFA for GRANT) is a later ruling, matching readiness open question 9's pilot-versus-production framing. |

## 6 — Sequence and maturity ceiling

Entered only after ID-1 to ID-5 are ruled, each step by its own prompt.

1. **AI-A · Port and proof shape** in `governed-review-service`: the port, a static
   reference adapter (refused in production mode), the binding and tenant rules of
   §4, rows 1 to 8 and 11 at unit level. Every decision now carries
   `identity_proof` = `PRESENTED_UNPROVEN` or `IDP_AUTHENTICATED`. Label: **Core
   implemented, shadow-only**.
2. **AI-B · Relay** in the studio per ID-1: one opaque header, never parsed; the
   security tests assert it is never logged or stored. Label: **Core implemented**.
3. **AI-C · OIDC adapter** as its own small package (the first crypto and IdP-client
   dependency on this path), validated against a real issuer in CI only if a
   test issuer can be run without egress. Label: **Reference-grade**.
4. **AI-D · Linkage and ledger carry the proof** (ID-2); row 9. Label: **Core
   implemented**.
5. **AI-E · Assurance enforcement** per ID-5, when ruled.

**Ceiling.** Until AI-C runs against a real enterprise IdP, every decision stays
`PRESENTED_UNPROVEN` and the roadmap's v1 criterion 2 stays unmet. With AI-C, a
decision is `IDP_AUTHENTICATED` at reference-grade; production certification needs
the P3E external security review and the private OCI mirror, neither of which this
sequence builds. Multi-tenant *isolation* of the durable engine is outside this
sequence entirely.

## 7 — Next step

Rule ID-1 to ID-5. Nothing is implemented by this record.
