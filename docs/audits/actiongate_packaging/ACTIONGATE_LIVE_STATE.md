# ActionGate Packaging — Live-State Audit

Mandatory pre-migration audit of the **live** repository state, captured before any
source was modified. Every value here was measured against the working tree, not
copied from the task brief.

## Repository state

| Field | Value |
|---|---|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Starting commit | `3b521f0f9517e12c8c379a9ad26ed57de1da4309` |
| Working branch | `claude/actiongate-canonical-package-bn39s6` |
| Working tree at start | clean |
| Python | 3.11.15 |

## Prerequisite PR #1297 (TAP canonical migration)

| Field | Value |
|---|---|
| State | **MERGED** |
| Merge commit | `179fdc35c13dc99ba0b5847fba157fc2d4676316` |
| Head sha | `3b8d3055d670b57b0d2b94463a0df2d2840c7269` |
| Note | Its PR body explicitly names *"the next phase … is the ActionGate canonical package migration"* — this work. |

No open or merged **ActionGate** canonical-packaging PR exists (searched
`repo:rasaha/symbolu actiongate canonical package`). This migration is the first.

## Canonical framework packages (live)

| Distribution | Namespace | Path | Version |
|---|---|---|---|
| `ugence-governance-contracts` | `ugence_governance_contracts` | `packages/governance-contracts` | leaf |
| `ugence-governance-provider-framework` | `ugence_governance_provider_framework` | `packages/governance-provider-framework` | 0.1.0 |
| `ugence-decision-authority` | `ugence_decision_authority` | `packages/capabilities/decision-authority` | kernel |
| `ugence-tap-provider` | `ugence_tap_provider` | `packages/providers/tap` | 0.1.0 (PR #1297) |
| `ugence-ai-hiring` | `ugence_ai_hiring` | `packages/products/ai-hiring` | (PR #1296) |

The legacy `governance_providers` root namespace is now itself a logic-free facade
over `ugence_governance_provider_framework`. ActionGate's provider layer currently
imports `governance_providers.api`; the canonical package rewrites that to
`ugence_governance_provider_framework.api`.

## ActionGate implementation (live)

| Field | Value |
|---|---|
| Implementation namespace | `actiongate_provider` |
| Implementation version | `0.1.0` |
| Private distribution | `dgm-actiongate-provider` (0.1.0) |
| Private distribution deps | `decision-governance==1.0.0`, `dgm-provider-framework==0.1.0` |
| Private packaging | `packaging/dgm-actiongate-provider` — `actiongate_provider` is a symlink to the root tree |

## Baseline verification (measured)

| Field | Value |
|---|---|
| Baseline ActionGate tests | **30 passed** (`actiongate_provider/tests`) |
| Baseline test result | PASS |
| Baseline wheel | `dgm_actiongate_provider-0.1.0-py3-none-any.whl` |
| Baseline wheel SHA-256 | `77b1f73ef071709e6eb88eeac40f7899f4ff1cebd137cea2d5ebd71f18098425` |
| API export count | 26 |
| API snapshot hash | `9eeb66e31430d9e65982826e9910fc571fbae0331b797c5bb1b735bc53887300` |
| Behavioral capture hash | `d805e6cfa4e2638c4c7542023de4861a3b962b6430c8cfb60f26eb3c885ed200` |
| Platform-freeze verify | **PASS** |
| Freeze manifest digest | `815a9250f833a253a621f26b341cd5b0a7cb8d283165fc9142013ff109c524c6` |
| Freeze substantive digest | `ee7f083ebb21111cb01e3fdb0fb3f37f39cc0fcf00238ef918a9a5d5984ec47a` |

The API snapshot hash equals the frozen `public_api_manifests.actiongate_provider.api`
value in `platform/PLATFORM_FREEZE_V1.json` — the baseline is consistent with the
freeze.

## Baseline failures (recorded before modifying source)

Running `pytest actiongate_provider/tests` in the fresh container first reported **5
failures**, all in `test_end_to_end.py`, all `ModuleNotFoundError: No module named
'pydantic'`. Those tests reach the Decision Authority kernel (which uses pydantic)
via the enterprise composition. The failure is purely an **absent environment
dependency**, not a code defect: after `pip install pydantic`, **all 30 tests pass**.
No source change was required to reach a green baseline.

## Existing limitations (carried forward, not "fixed" during packaging)

- ActionGate **authorizes only**: no dispatch, execute, observe, or reconcile surface.
- `tenant` is not carried by the neutral `ActionGovernanceRequest` (intentionally lossy).
- `expiry` is **emitted** by the provider; enforcement is a downstream concern.
- `single_use` is emitted as a constraint; ActionGate does not itself consume/enforce
  it — there is **no durable replay protection** in the provider.
- **Not production certified**; packaging verification is not production certification.

## Baseline artifacts

- `artifacts/actiongate_public_api_baseline.json` — full introspected `.api` snapshot.
- `artifacts/actiongate_equivalence_before.json` — deterministic behavioral capture
  (hash `d805e6cf…`), produced by `scripts/actiongate_equivalence_capture.py`.
