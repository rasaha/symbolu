# StoryGraph Import Graph — Before / After

Gate **S7** deliverable. External (non-stdlib) import roots of the canonical
StoryGraph source tree, verified by AST scan.

## Before (baseline — `cyber_security/composite_threat_detector/composite_threat_detector/` + `evaluation/` + `demos/`)

```
composite_threat_detector (core)  →  Python standard library ONLY
evaluation                        →  composite_threat_detector (internal), stdlib
demos                             →  composite_threat_detector (internal), stdlib
```
- **Third-party import roots:** NONE
- **Ugence-package import roots:** NONE
- The three trees were separate top-level packages linked only by `sys.path`
  (via `conftest.py`), with `evaluation`/`demos` importing the core absolutely.

## After (canonical — `packages/capabilities/storygraph/src/ugence_storygraph/`)

```
ugence_storygraph (core + policypack + evaluation + demos + replay_intake)
    →  Python standard library ONLY
```
- **External (non-stdlib, non-self) import roots:** **NONE**
- **Stdlib roots used:** `argparse, copy, dataclasses, datetime, fnmatch,
  hashlib, json, os, platform, random, re, sqlite3, sys, time, tracemalloc,
  types, typing` (+ `__future__`)
- `evaluation` and `demos` became internal subpackages; all cross-module imports
  are now package-relative or `ugence_storygraph`-qualified (self).

## Prohibited edges (all absent, before and after)

StoryGraph imports none of: ActionGate (`action_gate*`, `actiongate_provider`),
ACP (`autonomous_control_plane`, `symbolu_robotics`), Decision Governance
(`decision_governance`, `governance_providers`), Agent Runtime
(`agent_runtime_*`, `agentic`), console/API (`ugence_console_api`), products,
research (`experiments`, `model_selection_pilot`, `symbolu_training`), or CER
(`cer_v0_*`). Advisory results flow through public contracts, not authority
imports.

**Machine-enforced** by `tests/compatibility/test_dependencies.py` (AST scan,
fails on any prohibited or non-stdlib/self import) and by
`verify_storygraph_distribution.py` (clean-venv `--no-index` install proves no
third-party dependency and no unrelated Ugence package is reachable).
