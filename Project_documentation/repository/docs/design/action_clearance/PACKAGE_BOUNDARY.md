# Package Boundary (design; not created)

Proposed layout, adapted to the repository's `packages/capabilities/<kebab>` src-layout convention
(template: `packages/capabilities/model-selection/`). **Nothing is created in this phase.**

```text
packages/capabilities/action-clearance/
├── pyproject.toml            # name ugence-action-clearance; version 0.1.0; deps [] or [ugence-governance-contracts>=0.1.0]
├── README.md
├── LICENSE                   # Proprietary (repo convention)
├── src/
│   └── ugence_action_clearance/
│       ├── __init__.py       # curated re-exports (CORE_PUBLIC)
│       ├── api.py            # curated public surface
│       ├── request.py        # ClearanceRequest + AuthorizationContext/ActionIdentity/SignalBundle/ClearancePolicyContext
│       ├── result.py         # ClearanceResult, ClearanceReceipt, ClearanceStatus
│       ├── signals.py        # TrustedSignal, signal types, normalization
│       ├── policy.py         # ClearancePolicy, ClearanceProfile
│       ├── evaluator.py      # deterministic pure evaluate(request) -> ClearanceResult
│       ├── reason_codes.py   # ClearanceReasonCode catalog + classification
│       ├── fingerprint.py    # canonical serialization + SHA-256 domain-separated fingerprints
│       ├── errors.py         # typed exceptions
│       └── version.py        # __version__ = "0.1.0"; POLICY_VERSION = "action_clearance.v1"
├── tests/                    # core + serialization-equivalence + packaging tests
└── verify_action_clearance_distribution.py   # clean-venv wheel proof (repo convention)
```

## Public API classification

| Symbol | Classification |
|---|---|
| `evaluate` (`api.py`/`evaluator.py`) | CORE_PUBLIC |
| `ClearanceRequest`, `AuthorizationContext`, `ActionIdentity`, `SignalBundle`, `ClearancePolicyContext` | CORE_PUBLIC |
| `ClearanceResult`, `ClearanceReceipt`, `ClearanceStatus` | CORE_PUBLIC |
| `TrustedSignal`, `SignalType` | CORE_PUBLIC |
| `ClearanceReasonCode`, `REASON_CODE_CATALOG` | CORE_PUBLIC |
| `ClearancePolicy` | CORE_PUBLIC |
| `ClearanceProfile`, `GITHUB_EXACT_MERGE_PROFILE` | PROFILE_PUBLIC |
| `fingerprint(...)`, `canonicalize(...)` | INTERNAL (stable but not the primary surface) |
| `SignalAdapter` protocol | ADAPTER_ONLY |
| any `ACP*` / grant-minting symbol | UNNECESSARY (prohibited) |

## Dependency policy

Downward only. **Recommended:** a single downward dependency on `ugence-governance-contracts>=0.1.0` so
the core speaks the frozen `ActionGovernanceOutcome`/`ActionGovernanceResult`/`EXPIRED` seam natively
(like the provider-framework core). **Legal fallback:** stdlib-only leaf (like `ugence-model-selection`)
consuming a package-local authorization projection instead of the neutral types. Both are
platform-legal; the choice is a versioning/coupling decision recorded in
[`VERSIONING.md`](VERSIONING.md) and [`design_decisions.json`](design_decisions.json).

```text
ugence_action_clearance
    ↓ (optional, recommended)
ugence-governance-contracts >= 0.1.0        # neutral seam only
    ↓
Python standard library
```

## Must NOT depend upward on

Code Governance · robotics (`symbolu_robotics.autonomous_control_plane`) · console API
(`ugence_console_api`) · execution providers · incident clients · identity clients · workflow engines ·
Model Selection · Hybrid LLM · Decision Authority (`ugence_decision_authority` — references by id/hash
only).

A future package would add its own layered dependency rules (as decision-authority does in
`conformance/dependency_rules.py` + `tests/test_platform_boundaries.py`) and a
`verify_action_clearance_distribution.py` clean-venv wheel proof.

## Boundary exclusions (what the package must not absorb)

ActionGate policy · Decision-Authority logic · provider execution · GitHub/Kubernetes/DB-specific checks
(stay in adapters) · incident-management clients · credential acquisition · workflow orchestration ·
retry/reconciliation engines · Code Governance product state · Model Selection · Hybrid LLM. The
separation is: **core (neutral evaluation) + adapters (signal sources) + product workflow (assembles
request, invokes core, dispatches only on CLEAR)**.
