# ACP Canonical-Package Readiness

## Question

Is ACP ready for a canonical capability package such as `packages/capabilities/action-clearance/`
(namespace `ugence_action_clearance`, distribution `ugence-action-clearance`)? These names are **candidates**,
not decisions.

## Answer: NOT READY

The package *shape* is well understood (the repo has a proven template), but the **content** a package would
carry is not yet a single, neutral, contract-stable, authority-resolved product core. Readiness is blocked by
prerequisites, not by packaging mechanics.

## The proven template (what "ready" would look like)

`packages/capabilities/model-selection/` is the closest structural template — a stdlib-only leaf:

```
packages/capabilities/action-clearance/
  pyproject.toml            # name ugence-action-clearance; version 0.1.0; deps [] or [ugence-governance-contracts>=0.1.0]
  src/ugence_action_clearance/
    version.py              # __version__ = "0.1.0"; POLICY_VERSION = "acp_v1"
    api.py                 # curated public surface
    …core modules…
  tests/                   # core + serialization-equivalence + packaging tests
  verify_action_clearance_distribution.py   # clean-venv wheel proof
action_clearance/ (or legacy path)          # logic-free re-export shim, sys.modules identity-preserved
```

Common build config across all packages: `setuptools>=61`, `build_meta`, `[tool.setuptools.dynamic]` version
from `version.__version__`, `packages.find where=["src"]`, `license = Proprietary`.

## Readiness checklist against this template

| Item | Ready? | Why |
|---|---|---|
| Canonical source directory | **No** | No single core spans robotics/console/governance-chain framings; robotics core is domain-shaped |
| Files to move / leave behind | Drafted | `acp_migration_manifest.json` — but the "move" set needs a neutral kernel first |
| Compatibility namespace | Understood | `cer_v0_*` need identity-preserving re-exports of `.cloud.*` |
| Public API | **No** | consumers depend on deep `.cloud.*`, not a curated surface; no `Clearance*` family |
| Package dependencies | Decidable | `[]` (leaf) or `[ugence-governance-contracts>=0.1.0]` if it consumes the seam |
| Distribution deps | Decidable | mirror model-selection/GPF |
| Version / policy version | Decidable | 0.1.0 / `acp_v1` |
| Test package | Partial | 112 tests exist but are robotics-shaped; need packaging + serialization-equivalence tests |
| Wheel contents / clean-venv | Not attempted | migration not recommended |
| Consumer migration plan | Drafted | `MIGRATION_SEQUENCE.md` |

## Prerequisites before a package can exist (all documentation-only to resolve here)

1. **Resolve the authority definition** (authorizes vs clears) — pick one meaning for the product.
2. **Choose the world the package serves** (robotics core / console digital clearance / governance-chain
   seam) — they share no code today.
3. **Factor a neutral clearance kernel** out of robotics envelopes (`world_state.py`/`envelopes.py` are
   robotics-shaped).
4. **Define a stable `Clearance*` (or reuse `ActionGovernance*`) request/result/status/reason-code family.**
5. **Curate a public API** and migrate `cer_v0_*` off deep `.cloud.*` imports.
6. **Decide one-time-use ownership** (received signal, not an ACP-owned ledger).
7. **Plan an ACP-local freeze amendment** (import rewrites break the V1 digest).

## Not a standard-library-only mandate

A valid ACP package **may** depend downward on `ugence-governance-contracts` if the architecture requires it
(to speak the neutral `ActionGovernanceOutcome.EXPIRED` seam). Do not force it to be a stdlib-only leaf if
that severs it from the neutral governance vocabulary the rest of the platform uses. Either shape is
platform-legal; the choice is part of prerequisite #4.

## Boundary exclusions (what the package must NOT absorb)

ActionGate policy, Decision Authority logic, provider execution, GitHub merge checks, Kubernetes-specific
checks (stay in the cloud adapter), incident-management clients, credential acquisition, workflow
orchestration, retry engines, reconciliation engines, Code Governance product state, Model Selection, Hybrid
LLM. The likely separation is **ACP core (neutral clearance evaluation) + ACP adapters (incident / identity /
target-state / authorization-state) + product workflow (assembles request, invokes ACP, dispatches only on
CLEAR)** — validated by the live cloud/console composition, which already keeps target logic in adapters.
