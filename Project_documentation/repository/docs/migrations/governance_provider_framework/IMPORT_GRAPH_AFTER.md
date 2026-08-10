# Import Graph (AFTER) — Governance Provider Framework

Verified directly after the canonical-package migration. Companion:
`IMPORT_GRAPH_BEFORE.md`.

## Physical layout

```
packages/governance-provider-framework/src/ugence_governance_provider_framework/   (canonical, one impl)
governance_providers/__init__.py                                                    (legacy shim, single file)
```

## Outbound (what the canonical framework imports)

Unchanged in substance from BEFORE — the same two external roots, plus the
canonical package now depends on the neutral contracts leaf as its ONLY hard
distribution dependency; the kernel facade is an **optional** extra.

```
ugence_governance_provider_framework  ──▶  ugence_governance_contracts   (errors/lifecycle/metadata/contracts shims; HARD dep)
ugence_governance_provider_framework  ──▶  decision_governance.api        (ONLY in adapters/*; OPTIONAL 'adapters' extra)
```

Verified directly:
- The canonical **core** (everything except `adapters/`) imports no
  `decision_governance`, `ugence_decision_authority`, `tap_provider`,
  `actiongate_provider`, or any bounded capability. (`conformance/common.py`
  contains the string `"decision_governance"` in an AST boundary check only; the
  package `__init__` mentions it in a docstring only.)
- Only the three `adapters/*` modules reference `decision_governance.api`, and they
  do so **lazily** (at invocation) via the cached `_kernel()` loader and
  `adapters/_kernel.py::require_decision_authority()` — no module-level kernel
  import remains.
- `import ugence_governance_provider_framework` (top level) imports only `.version`
  (+ the contracts bootstrap). **Optional-dependency boundary correction:** `.api`
  and `.adapters` now also import WITHOUT Decision Authority. Proven in a clean venv
  WITHOUT Decision Authority: core, `.adapters`, and `.api` all import; only
  *invoking* a kernel-bound adapter raises a precise `ModuleNotFoundError` naming
  `ugence-governance-provider-framework[adapters]`.

## Dependency direction (correct, acyclic — unchanged)

```
applications / ai_hiring / domains
        ▼
concrete providers (tap_provider, actiongate_provider, baseline_*)
        ▼
ugence_governance_provider_framework   (Governance Provider Framework)
   ├── pure core ───────▶ ugence_governance_contracts   (pure stdlib leaf, HARD dep)
   └── adapters/ ───────▶ decision_governance.api        (kernel facade, OPTIONAL) ─▶ ugence_decision_authority
        ▲
        │  (legacy compatibility, identity-preserving)
governance_providers  ──alias──▶  ugence_governance_provider_framework
```

Zero upward imports (framework → provider/app/domain), verified by the relocated
`tests/boundaries/test_dependency_boundaries.py` (scan target repointed to the
canonical src) and the new core-without-Decision-Authority guard. Freeze invariant
**F20** (acyclic) remains green.

## Inbound (who imports the framework) — unchanged, all via the shim

All 66 external consumers still import the `governance_providers` name (top-level +
deep: `.api`, `.contracts[.action]`, `.reference.*`, `.conformance`, `.version`,
`.errors`, `.lifecycle`, `.metadata`), now resolved by the identity-preserving
legacy shim to the canonical package. No consumer was edited. Verified green:
TAP 38, ActionGate 30, baselines 10, contracts 45, ai_hiring 778,
enterprise_validation_pilot 164, provider_heterogeneity_validation 51,
comparative_governance_benchmark 56.

## Packaging graph

```
ugence-governance-provider-framework   (canonical wheel; dep: ugence-governance-contracts; extra 'adapters': decision-governance==1.0.0)
dgm-provider-framework (compat shell)  ──▶  ugence-governance-provider-framework[adapters]==0.1.0
dgm-tap-provider / dgm-actiongate-provider / baselines  ──▶  decision-governance==1.0.0 + dgm-provider-framework==0.1.0
```

The framework and its concrete providers remain physically decoupled at the
distribution layer. One physical framework implementation only.
