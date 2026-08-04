# Cloud Scaling Controller — Canonical Source Audit

**Phase:** Packaging / canonicalization / boundary-hardening (advisory-only).
**Repository:** `rasaha/symbolu`
**Audit commit (default tip at audit time):** `0d5d4dde5b68ef61e6dec994cc4b9e55fa57e363`
**Default branch:** `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`
**Working branch:** `claude/package-cloud-scaling-controller-ep84z9`
**Python:** 3.11.15 · **NumPy:** 2.4.6

Machine-readable companion: [`artifacts/source_inventory.json`](artifacts/source_inventory.json)
(153 file entries with path, size, SHA-256, import namespace, byte-identity flags).

---

## 1. Live-state gate results

| Check | Result |
|-------|--------|
| Repository | `rasaha/symbolu` |
| Current default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Current default tip | `0d5d4dde5b68ef61e6dec994cc4b9e55fa57e363` (matches expected tip) |
| Working tree clean | Yes (at audit start) |
| Python version | 3.11.15 |
| Existing controller locations | 3 physical copies + 1 stale nested copy (see §2) |
| Existing tests | `tests/cloud_controller/` — 19 files, **760 passed, 4 skipped** |

### Import resolution (live)

| Import | Resolves to | Notes |
|--------|-------------|-------|
| `cloud_controller` | `cloud_controller/__init__.py` (top-level) | Canonical executable package |
| `symbolu.cloud_controller` | **`cloud_controller/__init__.py` (top-level)** | Redirected by a meta-path finder in `symbolu/__init__.py` (`_SymboluFinder`, `_ROUTING["cloud_controller"] = ""`) |
| `cloud_controller.controller.Controller` | `<class 'cloud_controller.controller.Controller'>` | — |
| `symbolu.cloud_controller.controller.Controller` | **the same class object** | `A is B` → `True` (verified at runtime) |

**Key finding:** `symbolu.cloud_controller.*` is *already* an alias of the top-level
`cloud_controller.*` at runtime. The physical files under `symbolu/cloud_controller/`
are never imported — they are shadowed by the meta-path finder.

### `tests/cloud_controller/__init__.py` shadowing

The historical note about `tests/cloud_controller/__init__.py` shadowing the real
package **does not reproduce** on the live tree: there is no `tests/cloud_controller/__init__.py`
(and no `tests/__init__.py`), and the root `pyproject.toml` sets
`--import-mode=importlib`. Test collection succeeds. No repair was required; scope
was therefore not widened.

---

## 2. Source inventory — three physical copies

| Copy | Path | Tracked `.py` | Runtime role |
|------|------|---------------|--------------|
| **A — canonical** | `cloud_controller/` | 61 | **Executable canonical implementation.** Superset. Uniquely contains the `replay/` subpackage (14 files), `observability/efficiency_observer.py`, `shadow/live_efficiency.py`, and the newer `signals/prometheus.py`. |
| **B — nested stale** | `cloud_controller/cloud_controller/` | 46 | Stale nested duplicate. Imported by **no** live code (repo-wide grep for `cloud_controller.cloud_controller` is empty). Byte-identical to A for 45/46 files; the 46th (`signals/prometheus.py`) is an **older** revision. |
| **C — symbolu copy** | `symbolu/cloud_controller/` | 46 | **Dead physical copy.** Shadowed at runtime by `_SymboluFinder`. Differs from A only by the import-path prefix (`symbolu.cloud_controller.` → `cloud_controller.`) for 27/46 files; 18/46 are byte-identical; 1 (`signals/prometheus.py`) is an older revision. |

### Byte-identity analysis (vs canonical A)

Computed by normalizing the `symbolu.cloud_controller` → `cloud_controller` import
prefix and comparing file content:

- **B (nested):** 45 byte-identical, 1 real difference (`signals/prometheus.py`, older).
- **C (symbolu):** 18 byte-identical, 27 import-path-only differences, 1 real
  difference (`signals/prometheus.py`, older).

### The single behavioral difference: `signals/prometheus.py`

Only one module differs behaviorally across the copies. The canonical A version is
**newer**: it injects label selectors at explicit `__NSSEL__` / `__HPASEL__` tokens
(instead of naive first-brace splicing) and uses modern kube-state-metrics names
(`kube_horizontalpodautoscaler_status_*`) with an `or` fallback to the legacy
`kube_hpa_status_*` names. The B and C versions are the older revision.

**The live test suite asserts the A (newer) behavior** — e.g.
`tests/cloud_controller/test_signals.py:792-812` asserts both the modern and legacy
HPA metric names appear and that no `__NSSEL__`/`__HPASEL__` tokens leak into rendered
queries. Because `symbolu.cloud_controller.signals.prometheus` already resolves to A
via the finder, these tests pass today. `prometheus.py` is a **read-only signal
adapter**, not part of the scaling algorithm.

### The core scaling algorithm is already single-sourced

Every algorithm module — `controller.py`, `config.py`, `core/plasticity_gate.py`,
`core/adaptive_gain.py`, `core/damping.py`, `core/identity_ema.py`,
`core/coherence.py`, `core/replay_buffer.py` — is **byte-identical** (modulo import
prefix) across A and C, and identical across A and B. There is exactly **one**
scaling algorithm implementation in the tree today; B and C add no unique algorithm
code.

### Files unique to canonical A (would be lost if A were removed)

`replay/` (harness, tier_a, report, replay_source, efficiency_observer, and 7
adapters), `observability/efficiency_observer.py`, `shadow/live_efficiency.py`. None
of these exist in B or C. This confirms **A is the only complete copy**.

---

## 3. Canonicalization decision

- **Canonical implementation = A (`cloud_controller/`).** It is the documented
  canonical copy, the runtime target of both `cloud_controller` and
  `symbolu.cloud_controller`, the superset (only copy with `replay/`), and the copy
  whose behavior the live test suite verifies.
- **B (`cloud_controller/cloud_controller/`)** and the physical files under
  **C (`symbolu/cloud_controller/`)** are removable duplicates. They carry no unique
  runtime dependency (B is unimported; C is shadowed). They will be removed once the
  canonical package exists.
- After packaging there will be **exactly one** authoritative implementation, under
  `packages/capabilities/cloud-scaling-controller/src/ugence_cloud_scaling_controller/`.
  Legacy import paths (`cloud_controller`, `symbolu.cloud_controller`) become thin
  re-export shims containing **no** scaling algorithm.

No fourth copy is created: the canonical files are **moved** (via `git mv`) into the
package, not copied.

---

## 4. Baseline behavior freeze

- Full existing suite: **760 passed, 4 skipped** (skips = `opentelemetry` SDK absent,
  an optional dependency) via `python -m pytest tests/cloud_controller -q`.
- Deterministic behavior fixture:
  [`artifacts/prepackaging_behavior_baseline.json`](artifacts/prepackaging_behavior_baseline.json)
  — 8 deterministic scenarios, 280 controller steps, capturing per step: input
  observations, config, replica count, phase, deploy-active state, restart count,
  recommendation, replica delta, action score, pressure, component breakdowns
  (plasticity/gain/damping/coherence), explanation, and source commit.
- **Deterministic parity hash:** `bd5a367c6da7cecbb7b8a56d35f78bec21c5b381b3298ea69b98e79be9ec6bec`.

### Pre-existing nondeterminism (documented, not modified)

`cloud_controller/core/identity_ema.py:53` (and `:232`) initialize the identity
baseline with **unseeded** `np.random.randn(dim)`. This makes the `identity_deviation`
observability output (and the "Identity Drift" explanation line) vary between
`Controller` constructions. It is verified to **not** affect any decision field:
`action_score`, `recommendation`, `replica_delta`, `pressure`, `plasticity`, `gain`,
`damping`, and `coherence` are bit-stable across repeated runs. Per the task's
pre-existing-nondeterminism rule, `identity_deviation` is **excluded** from the
parity projection and the algorithm is **not** modified (seeding it would be an
algorithm change). This is the only nondeterminism observed.

The post-packaging implementation must reproduce the parity hash exactly.
