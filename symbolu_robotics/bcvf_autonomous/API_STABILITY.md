# BCVF Autonomous — API Stability Policy

**Version:** 1 (effective from `bcvf_autonomous` 0.4.0)

The brief's v0.2 note promised a *"tested integration contract"* —
this document is the part of that promise that turns "the kernel
works" into "an integrator can build against this and not have a
random Tuesday rip a function out from under them."

## §1 What this document covers

A flat registry — `_api.STABLE_API` and `_api.PROVISIONAL_API` — pins
which symbols carry which level of commitment. Both are tuples of
canonical `submodule.Symbol` strings (e.g.
`characterization.run_primary_grid`,
`analysis.StreamingFleetMonitor`). The same symbol is also re-exported
from the top-level `symbolu_robotics.bcvf_autonomous` package for
convenience; both access paths fall under the same commitment.

The 80+ entries on the top-level `__all__` are **not** the stable
surface. The stable surface is the explicit `STABLE_API` tuple,
which is shorter, hand-curated, and machine-checked (see §6).

## §2 Three tiers

### 2.1 Stable

Symbol is in `STABLE_API`. The integrator commitment:

* The signature (parameter names, defaults, return type) does not
  change in a backwards-incompatible way without a deprecation cycle
  (§5).
* The symbol is reachable both via `bcvf_autonomous.<submodule>.X`
  and via `from bcvf_autonomous import X`.
* Behaviour changes are bug-fix-only (a class of input that used to
  produce a wrong number now produces the right one) or are
  explicitly opt-in via a new keyword argument with a default that
  preserves prior behaviour.
* `__version__` is bumped on every change to a stable signature
  (§3 — semver mapping).

### 2.2 Provisional

Symbol is in `PROVISIONAL_API`. The commitment is weaker:

* The signature **may** change in a minor version with a
  release-note line. No advance notice is required.
* Removal in a minor version is allowed with a release-note line.
* The symbol may graduate to `STABLE_API` once the design is
  load-tested by an integrator.

Newer surfaces typically start here. The post-v0.7 SOTIF
traceability template, the auditor-facing report writers, and the
v0.6 V2 promotion-decision sweep are currently provisional —
they're shipped, supported, and tested, but the layout may shift as
deployment partners exercise them.

### 2.3 Internal

Anything not listed in either tuple, or anything with a leading
underscore (`_evaluate_thresholds`, `_resolve_metric_path`,
`_eval_cell`, ...). No commitment. Treat as a free-form refactor
target. Integrators that depend on internal surfaces do so at their
own risk; the test suite does not pin them.

## §3 Semver mapping

`__version__` is the single source of truth (also exposed as
`VERSION_INFO: Tuple[int, int, int]`).

| Bump | Trigger |
|---|---|
| **Patch** (`0.4.0 → 0.4.1`) | Bug fix, doc edit, internal refactor, additive provisional change without removal. |
| **Minor** (`0.4.0 → 0.5.0`) | Additive `STABLE_API` change (new symbol added). Removal of a `PROVISIONAL_API` symbol with a release-note line. Behaviour change to a `PROVISIONAL_API` surface. |
| **Major** (`0.4.0 → 1.0.0`, then `1.x → 2.0`) | Backwards-incompatible change to a `STABLE_API` signature *after* a deprecation cycle has run for at least one minor version. |

Pre-1.0 (current state) the contract is "breaking changes get a
release-note line and a `DeprecationWarning`, but minor bumps may
introduce them." **The `0.4.0` release is the one that ratifies this
policy.** Subsequent bumps are bound by the table above.

## §4 Deprecation cycle (post-1.0)

To remove or rename a `STABLE_API` symbol:

1. **Mark deprecated** in the minor release before removal. Add a
   `DeprecationWarning` to the deprecated surface that names the
   replacement (or "no replacement — internal refactor").
2. **Release notes** call out the deprecation under a "Deprecated"
   heading with the planned removal version.
3. **Add a `WILL_BE_REMOVED_IN` constant** alongside the deprecated
   symbol so a downstream tool can grep the codebase for upcoming
   breakage.
4. **Removal** lands in the next minor or major release per §3.

Pre-1.0 we may compress this cycle but always emit a
`DeprecationWarning` and a release-note line.

## §5 What changed (the move from "implicit" to "explicit")

Before 0.4.0, the package re-exported 129 symbols at the top level
with no tier annotation. Every one was implicitly "stable" — which
in practice meant nothing. Removing or renaming any symbol risked
breaking an integrator who had picked up on a re-export they
shouldn't have depended on.

Starting at 0.4.0:

* The hand-curated `STABLE_API` is the contract. The 129 top-level
  re-exports stay (zero break for existing integrators) but are no
  longer the contract.
* `PROVISIONAL_API` makes "we ship this, it works, it may move" an
  explicit promise rather than a guess.
* `tests/test_api_stability.py` machine-checks both tuples on every
  commit — a renamed module fails CI loudly instead of silently
  invalidating the contract.

## §6 Machine-checked

`tests/test_api_stability.py` enforces:

1. Every entry in `STABLE_API` and `PROVISIONAL_API` resolves to an
   importable symbol.
2. The two tuples are disjoint (no symbol is both stable and
   provisional).
3. No `STABLE_API` entry has a leading underscore in its symbol
   name (no internal leakage).
4. Every `STABLE_API` symbol is re-exported at the top level
   (`from bcvf_autonomous import X` works).
5. The size of `STABLE_API` is locked to a literal count — adding
   / removing a stable symbol fails the suite, which forces the PR
   review to acknowledge the contract change.
6. `__version__` is a valid semver string and matches `VERSION_INFO`.

## §7 What this is not

* Not a feature list. Symbols not in `STABLE_API` may still be
  feature-complete and supported — they just don't carry the
  long-term commitment. The brief's capability table is the
  feature list.
* Not a SOTIF / ISO 26262 clause artifact. Software safety cases
  reference specific implementations (kernel, characterization
  grid, fleet harness) — the API stability policy is the upstream
  software-development discipline that keeps those references
  valid across versions, not direct clause evidence.
* Not a substitute for tests. Stable symbols still need behaviour
  tests; the registry just makes the surface explicit.
