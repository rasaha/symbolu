# ACP V1 — Frozen Baseline Fingerprint (§1)

ACP V1 (the Phase 0–3 core + robotics results) is frozen as a baseline for the
V2 cross-domain study. The V2 cloud adapter is **additive** and reuses the core
**unchanged**. Any core change must be separately justified as a true
cross-domain abstraction defect, not cloud-adapter convenience — and none was
required (verified at milestone end; see `ACP_CROSS_DOMAIN_REUSE_ANALYSIS.md`).

---

## 1. Frozen core modules (stdlib-only) — SHA-256 (first 16 hex)

| module | sha256[:16] | role in the reusable core |
|---|---|---|
| `errors.py` | `15fb05aaf80a693d` | typed fail-loud error hierarchy |
| `identity.py` | `e156ce50993f191e` | canonical serialization + domain-separated identity |
| `world_state.py` | `ec9fb4df86118e25` | state envelope pattern + `version` identity |
| `constraints.py` | `a6d07621689e84a5` | `ConstraintResult` / `ConstraintKind` (hard/soft) |
| `envelopes.py` | `6f1e5af0a3c2e75a` | `ActionDecision` (closed outcome set) + candidate pattern |
| `authorization.py` | `f3975bb0aeeeba8b` | `ControlAuthorization` + commit revalidator |
| `action_selection.py` | `e3b6c4edcdd80199` | `filter_admissible` + `LexicographicActionSelector` |
| `decision_trace.py` | `fe43773d0ef9a734` | structured `DecisionTrace` + bounded sink pattern |
| `failure_state.py` | `d60013db0ce150bd` | deterministic failure state machine |
| `interfaces.py` | `d4e8a588ad1a640c` | Protocol contracts |
| `predictor_evidence.py` | `49b32162624155eb` | (robotics-domain evidence; not reused by cloud) |
| `physical_evidence.py` | `6d4c0b57d8d57ec3` | (robotics-domain evidence; not reused by cloud) |
| `__init__.py` | `56938a4a4de42611` | public API surface |

**Combined hash of the 10 reusable-core modules** (errors, identity, world_state,
constraints, envelopes, authorization, action_selection, decision_trace,
failure_state, interfaces):

```
8f8660e293308cf94c983a26a2ae69c9
```

## 2. Frozen semantics (must not change)

canonical identity semantics · fail-closed defaults · explicit non-binary outcome
philosophy · hard-before-soft (non-compensatory) ordering · state/action binding ·
structured decision traces · shadow-only runtime behaviour.

## 3. Domain-specific (NOT core; not reused cross-domain)

`predictor_evidence.py`, `physical_evidence.py`, `constraint_library.py`,
`adapters.py`, `shadow.py`, and the `safety_adapters/` subpackage are the
**robotics** domain layer. The cloud adapter provides its own equivalents; none
of these transfer (nor should they — robotics thresholds/trajectory equations do
not apply to cloud, per §2 non-goal).

## 4. Verification contract

At V2 completion, the SHA-256 of every core module in §1 must be unchanged. If any
differs, the diff must be documented as a justified cross-domain abstraction fix.
