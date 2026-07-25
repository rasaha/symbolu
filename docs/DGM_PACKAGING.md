# Decision Governance Middleware — Packaging & Distribution (Phase 5E.1)

Phase 5E proved the kernel's **import-level** independence (it imports with no
consuming layer on the path). Phase 5E.1 adds **distribution-level**
independence: `decision_governance` now builds, installs, and is consumable as
its own Python distribution — validated *outside* the monorepo source tree so a
`pip install -e .` checkout cannot mask a packaging defect.

> This corrects the earlier overstatement that the kernel "installed as a
> third-party package." Before 5E.1 it installed **only** as part of the
> `symbolu` wheel.

## Three names, one kernel

| Concept | Name | Notes |
| --- | --- | --- |
| **Import package** | `decision_governance` | the Python package you `import`; unchanged |
| **Distribution package** | `decision-governance` | the standalone wheel/sdist built in `packaging/decision-governance/` |
| **Monorepo distribution** | `symbolu` | the root wheel; still bundles the kernel (+ domains, applications, ai_hiring) |

## No duplicated source

There is exactly **one** kernel source tree: `decision_governance/`. The
independent build packages it directly through a symlink —
`packaging/decision-governance/decision_governance → ../../decision_governance` —
so both distributions ship byte-identical kernel files. No copy is maintained,
and a fast test (`test_distribution_packaging.py`) fails if a second tree ever
appears or the symlink stops resolving to the canonical package.

> Symlink note: the build requires the checkout to preserve symlinks
> (`git config core.symlinks true`, the default on Linux/macOS). CI runs on such
> platforms.

## Building the DGM distribution

```bash
python -m build packaging/decision-governance
# → packaging/decision-governance/dist/decision_governance-1.0.0-py3-none-any.whl
#   packaging/decision-governance/dist/decision_governance-1.0.0.tar.gz
```

The wheel contains **only** `decision_governance/**` (excluding `tests/`) — no
`domains`, `applications`, `ai_hiring`, repo-root files, caches, or fixtures.

## Installing

```bash
pip install packaging/decision-governance/dist/decision_governance-1.0.0-py3-none-any.whl
# (or, once published:  pip install decision-governance==1.0.0)
```

## Version ownership

Single authoritative source: `decision_governance/version.py` (`__version__ =
"1.0.0"`). The independent build derives it dynamically
(`[tool.setuptools.dynamic] version = {attr = "decision_governance.version.__version__"}`)
— the version string is **not** duplicated in the packaging config. A test guards
this.

## Runtime dependencies

The kernel's only direct runtime dependency is **`pydantic>=2.0.0`**. The
independent distribution declares exactly that — it does **not** inherit the root
`symbolu` dependency set (numpy, provider SDKs, etc.). Dependency tiers:

| Tier | Contents |
| --- | --- |
| runtime | `pydantic>=2.0.0` |
| build | `setuptools>=61.0` (PEP 517 backend) |
| test / dev | `pytest>=7.0` (extra `[test]`) |

## Compatibility policy

Governed by `decision_governance/version.py` (see `docs/DGM_PLATFORM.md`):
PATCH = corrective, no surface change; MINOR = additive; MAJOR = behavioral /
lifecycle / serialization / hash / port / removal / enum-value change. Frozen
fingerprints (vocabulary, lifecycle, ports, serialization shape) enforce it.

## Dual-distribution ownership model

Both the `symbolu` wheel and the `decision-governance` wheel expose the same
import package `decision_governance`. Publishing **both** publicly, or installing
both into the **same** environment, creates dual file ownership under
`site-packages/decision_governance/` — a pip RECORD/uninstall hazard (uninstalling
one distribution can remove files the other still needs).

Three models were considered:

- **Model A — transitional dual ownership:** both wheels ship the kernel, versions
  must match exactly, CI verifies byte-equivalence. Smallest, but permits unsafe
  co-installation.
- **Model B — root dependency:** `symbolu` stops embedding the kernel and depends
  on `decision-governance==1.0.0`. Architecturally cleanest; a larger packaging
  change.
- **Model C — private independent build:** the kernel builds and is validated (and
  privately installable) as its own distribution, while the published root wheel
  remains the only public distribution for now.

### Selected: **Model C**

Rationale: public PyPI publication is explicitly out of scope for this corrective
phase, so the smallest *safe* additive step is to add and fully validate the
independent build **without** publishing a second public distribution of the same
import package. This delivers real distribution-level independence (build,
isolated install, third-party consumption) while avoiding unsafe co-installed dual
ownership. Drift between the root-embedded kernel and the independent kernel is
prevented by the byte-equivalence guard.

**Is simultaneous installation of `symbolu` and `decision-governance` supported?**
**No — it is discouraged and unsupported.** They are not meant to coexist in one
environment: use `symbolu` inside the monorepo (dev/deploy of the full stack); use
`decision-governance` for a standalone kernel consumer in its own environment.
Because both carry byte-identical kernel files at matching versions, an accidental
co-install is *functionally* consistent, but pip uninstall semantics are not — so
keep them in separate environments.

### Recommended next step (Model B)

Before any public PyPI publication, migrate to **Model B**: have `symbolu` declare
`decision-governance==<version>` as a dependency and stop embedding the kernel.
That removes dual ownership entirely and makes the kernel a true shared dependency.

## Release procedure (private)

1. Bump `decision_governance/version.py` per the compatibility policy.
2. Update/confirm the frozen fingerprints if the change is an intentional
   additive (MINOR).
3. `python packaging/verify_independent_distribution.py` (build + isolated
   install + consumer + byte-equivalence).
4. Run the full suite (`ai_hiring/tests domains/procurement/tests
   decision_governance/tests`).
5. Archive/deploy the wheel + sdist from
   `packaging/decision-governance/dist/`.

## PyPI publication readiness

The distribution metadata (name, version, description, runtime dep, README,
license, `requires-python`) is complete and the wheel/sdist build cleanly, so the
artifact is *technically* publishable. It is **not** published here (out of
scope), and public publication should first adopt **Model B** to avoid two public
distributions owning the same import package.

## CI validation matrix

Five independent paths, all of which must pass:

| # | Path | Command |
| --- | --- | --- |
| 1 | Monorepo source tests | `pytest ai_hiring/tests domains/procurement/tests decision_governance/tests` |
| 2 | Root `symbolu` wheel build + install | `python -m build --wheel .` then import in a fresh env |
| 3 | Independent `decision-governance` wheel build + isolated install | `python packaging/verify_independent_distribution.py` (steps 1,4–6) |
| 4 | External consumer against installed wheel | `python packaging/verify_independent_distribution.py` (step 6) |
| 5 | Root/independent byte-equivalence | `python packaging/verify_independent_distribution.py` (steps 2–3) |

Paths 3–5 are automated end-to-end by `packaging/verify_independent_distribution.py`;
path 1 includes the fast packaging guards in
`decision_governance/tests/test_distribution_packaging.py`.

## What Phase 5E.1 did **not** change

No kernel behavior, no lifecycle, no serialization, no hashes, no audit values, no
public API surface. The only source change is additive packaging scaffolding under
`packaging/` plus new tests; the kernel tree is byte-identical to the 5E baseline.
