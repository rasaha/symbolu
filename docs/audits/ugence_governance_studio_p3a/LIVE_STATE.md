# Live-State Audit — Ugence Governance Studio P3A

Stage **P3A** (Demo Architecture, Contract Freeze and Credible Demonstration
Fixtures) for the Agent Workforce Composer (AWC) web application. This stage adds
**no web server and no UI** — only the application boundary, the demo scenario
fixtures (in the real AWC schemas), frozen canonical expected outputs, narratives,
and regression tests.

## Repository state at branch creation

| Item | Value |
|---|---|
| Repository | `rasaha/symbolu` |
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default-branch tip / starting commit | `edea48d37855d3247da735291a332f2fca40e1de` (merge of PR #1311) |
| Working branch | `claude/governance-studio-p3a-ficdup` (env `claude/` prefix; supersedes the suggested `chatgpt/governance-studio-p3a-demo-foundation`) |
| **PR #1308** — Agent Workforce Composer **P1** | **merged** — `d1cfad24777ae0bbd49f7be4a699786fed1ffb3b` |
| **PR #1310** — Agent Workforce Composer **P2** | **merged** — `0f5a461fb6714a4c55637d29e488814a2fe1a646` (verified via GitHub: `merged=true`, base = default branch, merged_at `2026-08-03T14:59:57Z`) |
| PR #1311 (subsequent, unrelated slots research) | merged — `edea48d3…` (current default tip) |
| Working tree at branch creation | clean |
| Existing Governance Studio application | **None** (`apps/` contained only `console`) |

Both prerequisite AWC PRs are in this branch's ancestry, so the P1 canonical
object model, contracts, eligibility engine, and the full P2 pipeline (ranking,
composition, permission bounding, fallback, AgentTeamPlan, replay, diff) are
present and authoritative. P3A builds strictly on top and **re-implements none of
them**.

## AWC package under test

| Item | Value |
|---|---|
| Package (import) | `ugence_agent_workforce_composer` |
| Distribution | `ugence-agent-workforce-composer` |
| Location | `packages/capabilities/agent-workforce-composer/` |
| Version | `0.2.0` |
| P1 contract | `awc.v1` |
| P2 composition contract | `awc.composition.v1` |
| Core dependency | `pydantic>=2` (stdlib + pydantic only; leaf capability) |
| Public API surface | `ugence_agent_workforce_composer.api` — **93 exported names** (frozen in `artifacts/public_api.json`) |

## Verification performed before writing fixtures

| Gate | Result |
|---|---|
| AWC P1/P2 test suite (`pytest tests/`) | **156 passed, 1 skipped** (compiler-reference auto-skips: optional dep absent) |
| Isolated distribution verification (`verify_agent_workforce_composer_distribution.py`) | **`AWC_P2_DISTRIBUTION_VERIFIED`** — wheel `e283b716998f06e349a1260273acb9a799fe2680c7345d7f13994109f860e101`, sdist `0b20d2deea8cd7fb488abed683b95540baedc16d1d69fe64a630d9e7f7314077`, wheel bit-for-bit reproducible |
| Platform-freeze verification (`python -m platform_freeze.verify`) | **PASS** — substantive digest `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036` |
| Public AWC API inspection | see `AWC_API_INVENTORY.md` |
| Existing Procurement/Support/Security fixtures | reproduced via `fixtures.run_compose_demo(...)`; see `EXISTING_FIXTURE_REVIEW.md` |
| Commercially unintuitive assignments identified | provider-concentration non-greedy swap; diversity-vs-ranking trade-offs — see `EXISTING_FIXTURE_REVIEW.md` |
| Monorepo web-app / frontend / backend / Docker / CI conventions | inspected (`apps/console`, `.github/workflows/*-ci.yml`); see `DEMO_ARCHITECTURE_OPTIONS.md` |

## Platform-freeze impact of P3A

P3A adds only new files under `apps/ugence-governance-studio/` and
`docs/audits/ugence_governance_studio_p3a/`. It modifies **no** frozen governance
artifact, no package under `packages/`, and no `platform/` manifest. Platform-freeze
re-verification after the change is expected to remain **PASS** at the same digest
(`d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`).
