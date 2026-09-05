# ugence-authority-directory

**Reference-grade, shadow-only, not enforcement-ready.** Time-bounded organizational
role grants: who holds which role, in which scope, until when — plus bounded
delegation and committee reporting. Scoped and ratified by
`docs/architecture/ADR_UGENCE_AUTHORITY_DIRECTORY_SCOPING.md`; sequenced by
`ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 2). It closes the gap the
approval-workflow ADR left open: `ApproverEligibilityPort` had no production adapter.

> This package reports role grants. It **never authenticates**, never approves, never
> mints authority, and holds custody of nothing. A reported grant is an input to
> somebody else's decision, not a decision.

## Not an authority

Every `…Authority` package in this repository decides something; this one decides
nothing. No exported type is named `…Authority`, and none ends in
`TrustAnchorDirectory` — the trust-anchor directory has no second
(`packages/integration/cloud-scaling-producer-attestation/README.md:96`), and this
package holds no key material to put in one. Boundary tests assert both, over the
class definitions themselves.

## The role grant

`RoleGrant(grant_id, tenant_id, principal, role, scope, validity, authority_reference,
granting_policy_ref, delegation_ref, delegated_from, member_of, revoked_at)`.

`role` and `scope` are free, uninterpreted labels; the directory reports them and never
reasons about what a role means. `authority_reference` is a non-secret handle, never a
credential. The grant id is derived from the tenant, principal, role, scope and window,
so replaying an administrator's file does not multiply a grant — and there is no UUID
and no clock.

**A scope is a `/`-separated path.** One scope covers another when they are equal or
the other is a strict descendant: `approval/case` covers `approval/case/abc` and never
`approval`, `approval/casebook`, or a sibling. There is no wildcard — a grant that
covers everything must name the root it covers, so no scope is silently unbounded.

## The window, and what "absent" means

Every grant is bounded by a
`ugence_governance_contracts.contracts.validity.Validity`, evaluated with
`status_at(as_of)` at a caller-supplied, timezone-aware instant. **A grant outside its
window is absent from every answer** — not reported with a flag — so a lapsed role
cannot be argued around downstream. Revocation behaves the same way and is
forward-only: from the revoking instant the grant is gone from the answers, while a
query at an earlier instant still reports it.

**The package reads no clock** — no `time.time()`, no `datetime.now`, no `utcnow`, no
`uuid4` — and `tests/test_boundaries.py::test_no_clock_is_read_anywhere` asserts it
over the AST of every source file.

## The boundary against the IdP

The directory answers *what a principal may currently do*. The IdP answers *who the
principal is*. So this package never authenticates, never resolves a session, never
holds a token or credential, and **never returns an `ActorType`** — a boundary test
asserts that no identifier or string literal in the code so much as names one.
Decision Authority keeps taking its `ActorType` from `IdentityProvider.authenticate`;
a role grant never substitutes for that. A principal the IdP has not authenticated is
not made a human by holding a human role.

## Delegation — one hop, narrowing only

A delegated grant carries `delegation_ref` (the delegator's grant) and `delegated_from`
(their principal). It is refused unless, at the same instant:

- the delegator's grant exists and is valid;
- it sits in the same tenant and carries the same role;
- its scope **covers** the delegated scope — a delegation may only narrow, never widen
  and never move sideways;
- the delegator's own grant is not itself delegated — delegation stops after
  `MAX_DELEGATION_HOPS == 1`;
- the delegator is not delegating to itself.

`delegation_refusals()` is pure and reports every reason at once. This is the shape
Decision Authority already requires of `DELEGATED_POLICY` authority: bounded, with a
granting reference and an explicit scope.

## Committees — quorum and members, never a verdict

A committee is a `PrincipalRef` of kind `COMMITTEE` carrying `quorum`; its members hold
ordinary grants marked `member_of`. `committee_report()` returns the quorum and the
members whose grants are valid at `as_of`, and stops. `CommitteeReport` deliberately
has **no** `quorum_met` field, and a test asserts its whole attribute surface: whether
enough members actually approved is the approval workflow's ledger and Decision
Authority's `required_approvals`, not this package's business. A member whose grant
lapses simply stops being reported — including below quorum, which the directory
reports without comment.

## The eligibility adapter

`DirectoryApproverEligibility` satisfies the approval workflow's
`ApproverEligibilityPort`
(`packages/integration/approval-workflow/src/ugence_approval_workflow/eligibility.py:95-106`)
**without importing that package**. The port is owned by the consumer; the seam is
structural, so `DirectoryApproverRef` carries exactly the four attributes the port
reads and its `approver_kind` is a `str` enum whose values match the consumer's
`ApproverKind` — `PrincipalKind.HUMAN`, `ApproverKind.HUMAN` and `"HUMAN"` compare and
hash equal. A ref this adapter returns can be handed straight to `decide()`, and
`tests/integration/` proves it against the real package, including that the consumer's
own `structural_refusals` accepts it.

The adapter derives one deterministic scope, `approval/<subject_kind>/<subject_digest>`.
A composition root that scopes its roles differently supplies its own adapter rather
than subclassing this one.

```python
directory = SqliteAuthorityDirectory("directory.sqlite3")
directory.put_grant(grant, as_of=now, loaded_by="admin-1")
store = SqliteApprovalWorkflowStore("approvals.sqlite3", DirectoryApproverEligibility(directory))
```

## Two adapters

| Adapter | Store | Posture |
|---|---|---|
| `InMemoryAuthorityDirectory` | process-local dict under one lock | tests and local composition; refused in production mode |
| `SqliteAuthorityDirectory` | single-node stdlib `sqlite3` | WAL, `BEGIN IMMEDIATE`, one append-only hash-linked `directory_events` table whose triggers refuse UPDATE and DELETE |

Both apply the same pure delegation and selection rules, and every grant, delegation
and committee test runs against both. A stored grant that no longer re-derives its
digest is refused on read, and `verify_chain()` recomputes the event chain end to end.
Distributed strong consistency stays disclaimed (D-22 Posture B).

## Consumers, and the direction of every edge

Risk Authority's union-only `required_approvals` labels
(`packages/integration/risk-authority-runtime/.../restrictions.py:126`) and Policy
Authority's injected `ApprovalVerifier` (`packages/policy-authority/README.md:87`) are
**consumers of this package's answers, never dependencies of it**. Neither imports it;
a composition root may hand either one an adapter built over it.

## Dependencies

`ugence-governance-contracts>=0.4.0` and the standard library, `sqlite3` included.
Nothing else — not the approval workflow, not Decision Authority, not Risk Authority,
not Policy Authority, no IdP client, no LDAP or SCIM library, no cryptography, no
network client, no cloud SDK, no pydantic. Composition roots, products and applications
may import it; no capability package may.

## Gaps that survive this release

- Nothing here proves organizational truth. A grant is what an administrator loaded;
  the directory reports it faithfully and attests nothing about whether it should exist.
- No IdP integration, no group-claim ingestion, no SCIM or LDAP adapter, and no
  reconciliation against an HR system of record.
- Risk Authority's label vocabulary is unratified, so its label resolver is deferred to
  0.2.0 (D-2).
- Single-node durability only, and no console surface.
