# Governance Studio P3D — Live-State Audit

| Item | Value |
|------|-------|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Starting commit | `340c29e1` (merge of PR #1322 — P3C hardening) |
| PR #1318 (P3B API) | merged (`f9bbda0d`) |
| PR #1320 (P3B packaging protections) | merged (`01fdf712`) |
| PR #1321 (P3C eligibility explorer) | merged |
| PR #1322 (P3C final hardening) | merged (`340c29e1`) |
| API distribution version | 0.1.0 |
| API contract | `governance_studio.api.v1` |
| OpenAPI sha256 | `dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656` (unchanged) |
| AWC version | 0.2.1 |
| Compiler version | 0.2.0 |
| Platform-freeze digest | `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036` (unchanged) |
| Frontend version | 0.1.0 → **0.2.0** |

## Scope

P3D extends the merged P3C eligibility explorer into a full **planning explorer**:
Ranking, Composition, Permission Proposals, Fallbacks, Replay, Comparison and a
controlled What-If explorer with deterministic export. It consumes the frozen
`governance_studio.api.v1` OpenAPI contract over HTTP only. No planning logic runs
in the browser; the frontend delegates every domain computation to the backend,
which delegates to AWC 0.2.1. The OpenAPI contract and the platform-freeze digest
are both unchanged by this phase.
