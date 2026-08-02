# ACP Migration Sequence (PROPOSED — not executed)

Because the verdict is **NOT READY**, no migration is performed or authorized here. This document records
the prerequisites and the phase sequence a future migration would follow **after** the prerequisites are met.

## Prerequisites (must be resolved first — all documentation/architecture decisions)

| # | Prerequisite | Why |
|---|---|---|
| P0-a | **Resolve the authority definition** (robotics V1 authorizes vs cloud/console clears) | Packaging an authorization engine as "clearance" blurs the ActionGate/ACP boundary (`AUTHORITY_BOUNDARY.md`) |
| P0-b | **Choose the world the package serves** (robotics / console / governance-chain) | The three framings share no code (`CANONICAL_SOURCE_DECISION.md`) |
| P0-c | **Factor a neutral clearance kernel** out of robotics envelopes | `world_state.py`/`envelopes.py` are robotics-shaped |
| P0-d | **Define a stable `Clearance*` (or reuse `ActionGovernance*`) contract family** | No single request/result/status/reason-code type today (`REQUEST_RESULT_CONTRACTS.md`) |
| P0-e | **Decide one-time-use ownership** (received signal, not an ACP ledger) | `STATE_AND_PERSISTENCE.md` |
| P0-f | **Plan the ACP-local freeze amendment** | Import rewrites break the V1 digest (`FREEZE_IMPLICATIONS.md`) |

## Phase sequence (only after P0-a…f)

**Phase 1 — Canonical package skeleton.** `packages/capabilities/action-clearance/` with metadata, version
(`0.1.0`), policy version, a curated `api.py`, no behavior change. Deps `[]` or
`[ugence-governance-contracts>=0.1.0]`.

**Phase 2 — Core source move.** Move the neutral kernel verbatim; convert internal imports to relative
imports; preserve serialization and object behavior. *Blocked on P0-c and the freeze amendment (P0-f).*

**Phase 3 — Compatibility surface.** Legacy re-export shims at the deep-import paths `cer_v0_*` use, with
`sys.modules` identity preservation; no duplicated logic (`COMPATIBILITY_STRATEGY.md`).

**Phase 4 — Consumer migration.** Migrate `cer_v0_1 → v0_2 → v0_3` onto the curated API; retain
shadow/research consumers (`robotics_reliability_bench/acp_*`) where appropriate.

**Phase 5 — Equivalence.** Before/after semantic-equivalence capture (status + reason codes + obligations +
escalation + expiry + exception behavior + fingerprints) across all current implementations, per the schema
in `DETERMINISM_AND_EQUIVALENCE.md`.

**Phase 6 — Distribution verification.** Canonical-only wheel; clean virtual environment; no monorepo-path
dependency (the `verify_*_distribution.py` pattern).

**Phase 7 — Closure.** Post-merge validation; **no policy/behavior changes**.

## Explicitly out of scope for the migration (do not absorb)

ActionGate policy, Decision Authority logic, provider execution, GitHub/Kubernetes-specific checks (stay in
adapters), incident clients, credential acquisition, workflow orchestration, retry/reconciliation engines,
Code Governance product state, Model Selection, Hybrid LLM.

## Do not execute any of this now

This audit is documentation-only. The next action after this audit is a **decision** on P0-a…f, not code.
