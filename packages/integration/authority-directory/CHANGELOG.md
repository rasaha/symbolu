# Changelog — ugence-authority-directory

## [Unreleased] — public_api.json no longer records the interpreter it was generated on

No API change: every exported symbol, kind, field list and version is identical. The
manifest's `class` entries for exception types listed `add_note` and `with_traceback`,
which are inherited from `BaseException` rather than declared by this package — and
`add_note` exists only from Python 3.11, so a 3.10 run could never reproduce a file
generated on 3.11 whatever the package declared. `scripts/generate_public_api.py` now
excludes inherited exception methods, and the manifest is regenerated accordingly. This
is what unblocked the suite's 3.10 leg, which the package's own
`requires-python >= 3.10` had always claimed and no workflow had ever run.

## 0.1.0 — wave 2, initial release

Scoped and ratified by `docs/architecture/ADR_UGENCE_AUTHORITY_DIRECTORY_SCOPING.md`.

- `RoleGrant` bounded by `Validity` and evaluated with `status_at(as_of)`: a grant
  outside its window, or revoked at or before the instant, is **absent from every
  answer** rather than reported with a flag. No clock is read anywhere, asserted over
  the AST.
- `PrincipalRef` and `PrincipalKind`, with `quorum` meaningful only for a `COMMITTEE`
  and refused elsewhere; `/`-separated scopes with a strict cover rule and no wildcard.
- Delegation carrying `delegation_ref` and `delegated_from`, refused unless the
  delegator's grant is valid at the same instant, in the same tenant, of the same role,
  and covering the delegated scope; one hop only (D-3), and no self-delegation.
- `CommitteeReport`: quorum plus currently-valid members, with membership recorded as
  ordinary grants (D-4). The report has no "quorum met" field and the directory never
  counts votes.
- `DirectoryApproverEligibility`, satisfying the approval workflow's
  `ApproverEligibilityPort` structurally, without importing that package (D-1).
- Two adapters: `InMemoryAuthorityDirectory`, refused in production mode, and
  `SqliteAuthorityDirectory` — WAL, `BEGIN IMMEDIATE`, and one append-only hash-linked
  `directory_events` table.
- No key, trust anchor or credential, no new Decision Authority `Permission`, and no
  type named `…Authority` or `…TrustAnchorDirectory` (D-5).
- Risk Authority's `required_approvals` label resolver is deferred to 0.2.0 (D-2).
- Neighbours unmodified: approval-workflow 0.1.0, Decision Authority 1.0.0, Risk
  Authority, Policy Authority.
