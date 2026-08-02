# Rollback

## This design phase

This phase adds **only** documentation:

- `ACTION_CLEARANCE_V0_1_DESIGN_SPEC.md`,
- `docs/design/action_clearance/**`,
- one cross-reference line in `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md`.

**Rollback = revert the documentation commits / close the PR.** There is no runtime, package, contract,
provider, API-snapshot, or freeze change to unwind. No robotics import, no `ProviderKind`, no
compatibility shim was touched. Reverting restores the exact prior tree; the platform-freeze substantive
digest (`d4ad77e1…a174a1a6`) and the robotics local freeze (`8f8660e293308cf94c983a26a2ae69c9`) are
unaffected either way.

## Future implementation phases (rollback per phase)

Each phase in [`IMPLEMENTATION_SEQUENCE.md`](IMPLEMENTATION_SEQUENCE.md) carries its own rollback; summary:

| Phase | Rollback |
|---|---|
| A skeleton | delete `packages/capabilities/action-clearance/` |
| B contracts+evaluator | revert to A (package present, no contracts) |
| C reference adapters | drop adapters (core unaffected) |
| D ActionGate integration (shadow) | disable the integration flag; no dispatch existed |
| E durable receipts | stop persisting receipts; evaluator unaffected |
| F GitHub profile (shadow) | disable the profile; core unaffected |
| G execution-ledger integration | fall back to no-dispatch (shadow) |
| H enforced merge | revert to shadow mode (recommendation only) |
| I merge queue + rebase | disable queue/rebase; direct+squash remain |

Because Phases D–G are shadow-only and enforced merge (H) is a mode flag over an already-proven shadow
path, every phase's rollback returns to a **known-good, non-executing** state without data migration.
