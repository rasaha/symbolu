# Changelog — ugence-authority-directory

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
