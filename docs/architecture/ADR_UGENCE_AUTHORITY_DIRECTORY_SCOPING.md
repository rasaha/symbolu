# Ugence authority directory — scoping record and ratification

**Status:** ratified 2026-09-04 by the repository owner. Scoping only: no package
exists yet, and this record amends no package ADR, port, test or manifest.
Sequenced by `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 2,
"Organizational authority directory", line 54): consumed by the approval workflow
and Risk Authority, with identity proof staying at the IdP. It closes the first gap
`ADR_UGENCE_APPROVAL_WORKFLOW_SCOPING.md` left open — `ApproverEligibilityPort` has
no production adapter.

## The question

Every consumer in this repository already asks *who holds which role, in what scope,
until when* — and every one of them answers it with an injected stub. Is the answer a
new package, and if so what may it own without becoming a second identity provider or
a second authority? **A directory of time-bounded role grants, and nothing else.** It
decides nothing, so it is never an *Authority*: it reports grants, and each consumer
applies its own rules to what it reports.

## What the repository already fixed

| Finding | Where |
|---|---|
| `ApproverEligibilityPort` needs exactly two answers — the eligible set for a role, and a typed `EligibilityDecision` for one presented approver — each at a caller-supplied `as_of` `[V]` | `packages/integration/approval-workflow/src/ugence_approval_workflow/eligibility.py:95-106` |
| The consumer refuses `AI`, `SERVICE` and `DELEGATED_POLICY` kinds and the self-approving requester itself, so no adapter answer can widen those `[V]` | same, `:112-127` |
| The port carries no quorum concept: the workflow only requires the eligible set to be non-empty `[G]` | `.../approval-workflow/.../workflow.py:76-82` |
| Decision Authority already spells delegation and quorum: `AuthorityContext(… effective_from, effective_until, limits, segregation_of_duties, required_approvals: int, delegation_ref)`, with `DELEGATED_POLICY` refused unless bounded by a granting policy and a scope or limits `[V]` | `packages/capabilities/decision-authority/src/ugence_decision_authority/decisions/authority.py:23-38,49-57` |
| A human authority requires an authenticated **human** `ActorType`, and that type comes from `IdentityProvider.authenticate` — never from a role `[V]` | `.../decisions/status.py:87-89`; `.../services/case_validation_service.py:120-122`; `.../identity/provider.py:24-32` |
| Segregation of duties is a fact about the *case* (the decider may not be the recommendation author), not about the directory `[V]` | `.../services/case_validation_service.py:136-139` |
| `AccessGrant` grants kernel **API permissions**, tenant- and subject-scoped, with no role and no time bound `[V]` | `.../policy/access.py:76-91` |
| Risk Authority carries `required_approvals: frozenset[str]` — opaque labels combined by union only, never removed `[V]` | `packages/integration/risk-authority-runtime/src/ugence_risk_authority_runtime/contracts.py:166`; `restrictions.py:126`; `decision_authority_adapter.py:102-109` |
| Policy Authority assigns *approver* to an external process and *approval verifier* to the composition root's injected trust boundary; its `ApprovalVerification` binds an `approving_authority_id` and an optional approved window `[V]` | `packages/policy-authority/README.md:26-41,87`; `.../core/approval.py:82-131` |
| "Directory" is reserved in one sense only — the **trust-anchor** directory, of which there is expressly no second `[V]` | `packages/integration/cloud-scaling-producer-attestation/README.md:96` |
| No README or NEXT_PHASES reserves *organizational authority directory*, *role*, or *role grant* `[G]` | repository-wide search over `README.md` and `NEXT_PHASES.md` |
| DD-3 — which Policy Authority instance may verify benchmark approvals — stays deferred and undecided `[V]` | `packages/benchmark-registry/README.md:440` |

The sequencing ADR's one prohibition (line 85) is satisfied by **scope**: the package
takes no reserved noun, and it settles DD-3 not at all.

## Ratified decisions

| # | Decision | Ruling |
|---|---|---|
| D-1 | Package, home and name | **`packages/integration/authority-directory`, distribution `ugence-authority-directory`.** Deliberately not `…Authority`: every `…Authority` package here decides something, and this one decides nothing. No type it exports may be named `…Authority`, and none may end in `TrustAnchorDirectory` — the trust-anchor directory has no second, and this package holds no key material to put in one. |
| D-2 | First-release scope | **The `ApproverEligibilityPort` adapter only.** Risk Authority's `required_approvals` label resolver is deferred to 0.2.0: the labels are opaque strings today, and a resolver would have to fix their vocabulary before an owner has ratified one. |
| D-3 | Delegation depth | **One hop in 0.1.0.** A delegated grant may not itself be delegated. Arbitrary depth needs a cycle check and a widening proof that a single hop makes unnecessary; the refusal is typed, so raising the cap later is additive. |
| D-4 | Committee membership | **Recorded here, as ordinary role grants.** The quorum lives on the committee principal and each member holds a grant of their own, so a member whose grant has lapsed simply stops being reported. Deriving membership from an IdP group claim is rejected for 0.1.0: it would make the directory read the IdP, which is the boundary this package exists to keep. |
| D-5 | Permissions and custody | **No key, no trust anchor, no credential, and no new Decision Authority `Permission`.** `AccessGrant` (`.../policy/access.py:76-91`) stays the only kernel permission store; an organizational role is not an API permission and never becomes one. |

## What a role grant is

`RoleGrant(tenant_id, principal_ref, principal_kind, role, scope, validity,
granting_policy_ref, delegation_ref, delegated_from, is_delegated)`.

`principal_ref` is a non-secret reference — a directory handle, never a credential and
never proof of identity. `role` and `scope` are free, uninterpreted labels, in the
same spirit as `VersionedRef.kind` (`.../decisions/subject.py:33-34`): the directory
reports them and never reasons about what a role means.

`validity` is a `ugence_governance_contracts.contracts.validity.Validity`, evaluated
by `status_at(as_of)` with a caller-supplied, timezone-aware instant. A grant outside
its window is **absent from the answer** — not reported-and-flagged — so a lapsed role
cannot be argued around downstream. `NOT_YET_VALID` and `EXPIRED` are equally absent;
`STALE` is reported and is not by itself a refusal. **The package reads no clock** —
no `time.time()`, no `datetime.now`, no `utcnow`, no `uuid4` — and a test asserts it
over the AST of every source file, as the approval workflow and execution-reservation
packages already do
(`packages/integration/approval-workflow/tests/test_boundaries.py::test_no_clock_is_read_anywhere`).

## The boundary against the IdP

The directory answers *what a principal may currently do*; the IdP answers *who the
principal is*. So the package **never authenticates**, never returns an `ActorType`,
never resolves a session, token or credential, and exports no method whose name could
be mistaken for one. Decision Authority keeps taking its `ActorType` from
`IdentityProvider.authenticate` (`.../identity/provider.py:24-32`), and a role grant
never substitutes for that: a principal the IdP has not authenticated is not made a
human by holding a human role. A test asserts the absence of an authentication
surface, exactly as the approval workflow already does for its own adapters.

## Delegation and quorum, without authenticating anyone

**Delegation** is an ordinary grant carrying `delegation_ref` and `delegated_from`. It
is refused unless the delegator's own grant is valid at the same `as_of` **and** the
delegated scope is a subset of the delegator's — never a wider one, and never a
sibling scope. A delegated grant may not be delegated again (D-3). This is the shape
Decision Authority already requires of `DELEGATED_POLICY`: bounded, with a granting
reference and an explicit scope (`.../decisions/authority.py:49-57`).

**A committee** is a `principal_ref` of kind `COMMITTEE` carrying `quorum: int` — the
same integer spelling as `AuthorityContext.required_approvals` — plus the member
grants. The directory reports the quorum and the members whose grants are valid at
`as_of`, and stops. It never counts votes, never tallies approvals, never decides that
a quorum was met, and never learns whether any member actually approved: that is the
approval workflow's ledger and Decision Authority's `required_approvals`, not this
package's business.

## Consumers, and the direction of every edge

The package **ships an `ApproverEligibilityPort` adapter** for
`packages/integration/approval-workflow`. The port itself stays owned there
(`.../approval-workflow/.../eligibility.py:95-106`): the consumer defines the seam,
the directory satisfies it, and the approval package's boundary test keeps refusing
the reverse import.

Risk Authority's `required_approvals` labels and Policy Authority's injected
`ApprovalVerifier` are **consumers of this package's answers, never dependencies of
it**. Risk Authority keeps combining labels by union only (`restrictions.py:126`);
Policy Authority keeps taking a verifier its composition root selects
(`policy-authority/README.md:87`). Neither imports this package; a composition root
may hand either one an adapter built over it. `[I]` Whether a resolved
`approving_authority_id` held its authority at the instant claimed is exactly the
question this directory can answer for such a verifier — as an answer the verifier
consults, never as a verification it performs.

## Dependencies

`ugence-governance-contracts>=0.4.0` (`Validity`, `ValidityStatus`) and the Python
standard library, `sqlite3` included. Nothing else: not Decision Authority, not Risk
Authority, not Policy Authority, not the approval workflow, not
execution-reservation, not `ugence_storygraph`, no product, no IdP client, no LDAP or
SCIM library, no network client, no cloud SDK, no pydantic. Composition roots,
products and applications may import it; **no capability package may**. A boundary
test asserts the import set over the AST and the declared dependency list.

## Gaps that survive this package `[G]`

- Nothing here proves organizational truth. A grant is what an administrator loaded;
  the directory reports it faithfully and attests nothing about whether it should
  exist.
- No IdP integration, no group-claim ingestion, no SCIM or LDAP adapter, and no
  reconciliation against an HR system of record.
- Risk Authority's label vocabulary stays unratified, so the label resolver is
  deferred (D-2).
- Single-node durability only, as under D-22 Posture B; distributed consistency stays
  disclaimed.
- DD-3 is untouched: nothing here says which Policy Authority instance may verify a
  benchmark approval.

One prohibition: the package never authenticates, never approves, never mints
authority and never holds custody of anything. A reported grant is an input to
somebody else's decision, not a decision.

## Next step

Implement `packages/integration/authority-directory` 0.1.0 under the decisions above.
