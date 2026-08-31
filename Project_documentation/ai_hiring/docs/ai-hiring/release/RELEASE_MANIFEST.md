# AI Hiring — Release Manifest (Canonical Release Record)

This manifest is the canonical release record for the AI Hiring controlled-pilot
freeze. It records the frozen source, the built artifacts and their hashes, the build
and runtime environment, and the documentation/validation inventory. It records
existing state only; it introduces no new behavior.

## Identity

| Field | Value |
|---|---|
| Product | AI Hiring |
| Product version | `0.6.0` (pre-1.0 / controlled-pilot) |
| Distribution | `symbolu` `0.1.0` (the repository the product ships inside) |
| Source commit (frozen baseline) | `b9a0e3a18e57fed5a9a10fbcb231eec9f9cc3973` |
| Readiness classification | `PACKAGE_READY_FOR_CONTROLLED_PILOT` |
| Platform baseline | Decision Governance Platform `v1.0` (frozen) |
| Production certified | **No** (`version_info().production_certified == False`) |

## Component versions (installed surface)

| Package | Version | Role |
|---|---|---|
| `decision_governance` | `1.0.0` | Frozen kernel (Platform v1.0) |
| `governance_providers` | `0.1.0` | Provider framework + deterministic validation providers |
| `tap_provider` | `0.1.0` | Assertion-governance provider |
| `actiongate_provider` | `0.1.0` | Action-governance provider |
| `ai_hiring` (`ai_hiring.product`) | `0.6.0` | Hiring domain + product packaging layer |

## Build environment

| Field | Value |
|---|---|
| Python (build/verify) | `3.11.15` |
| Supported Python | `>=3.10` (declared in `pyproject.toml`) |
| Platform | `Linux-6.18.5-x86_64-with-glibc2.39` |
| Build backend | `setuptools` `68.1.2` (`build` `1.5.0`) |
| Determinism input | `SOURCE_DATE_EPOCH=1785057132` (commit `b9a0e3a` author timestamp) |

## Build & install commands

```bash
# Build (deterministic)
SOURCE_DATE_EPOCH=1785057132 python -m build --outdir dist .

# Install (either path)
pip install dist/symbolu-0.1.0-py3-none-any.whl        # wheel
pip install -e .                                        # editable, from checkout

# Clean-environment verification (run from a non-repository directory)
python -m ai_hiring.product verify        # -> RESULT: PASS
```

## Artifacts & hashes (SHA-256)

| Artifact | SHA-256 | Reproducibility |
|---|---|---|
| `symbolu-0.1.0-py3-none-any.whl` | `45b2d9352f3d040fd04a88215fd068245b6ce9d770c96bd2c6ca28662beb16d0` | **Bit-for-bit reproducible** across builds with the pinned `SOURCE_DATE_EPOCH` |
| `symbolu-0.1.0.tar.gz` (sdist) | `6f8c8b6743fe7bff25de3e534561305c6bc916536f0586826ea812a695efc5c5` | **Content-reproducible** — see note below |

Wheel tag: `py3-none-any` (pure-Python; `Root-Is-Purelib: true`).

**Reproducibility note (honest):** The **wheel is bit-for-bit reproducible** — two
independent builds from commit `b9a0e3a` with `SOURCE_DATE_EPOCH=1785057132` produce
the identical SHA-256 `45b2d935…`. The **sdist is content-reproducible but not
bit-identical**: two builds contain the identical file set with byte-identical file
contents (`diff -rq` reports no differences), but the `tar.gz` archive framing
(member ordering / embedded archive metadata) is not fully deterministic in
`setuptools 68.1.2`, so the outer `.tar.gz` hash varies between builds. The recorded
sdist hash above is the reference build; verify sdist reproducibility by comparing
**extracted file contents**, and treat the **wheel** as the canonical
bit-reproducible artifact for hash-pinned distribution.

## Runtime dependencies

| Dependency | Declared floor | Resolved at verification |
|---|---|---|
| `pydantic` | `>=2.0.0` | `2.13.4` (`pydantic_core 2.46.4`) |
| `numpy` | `>=1.24.0` | `2.4.6` (pulled by the distribution; not used by product code paths) |

No vendor AI SDKs, database drivers, or web frameworks are required. Optional extras
(`openai`, `anthropic`, `mistral`, `all`) are **not** product dependencies and are
never imported by the product. Enforced by `ai_hiring/tests/test_h6_boundary.py`.

## Validation inventory (recorded at `b9a0e3a`)

| Check | Result |
|---|---|
| AI Hiring tests | **778 passed** |
| Kernel + framework + TAP + ActionGate + AI Hiring | **917 passed** |
| Platform Freeze | **PASS** (substantive digest `8b382d9bfed65b8bcf44f9d6f3f9a7138db08bff411c57297dff5721bc2da703`) |
| Dependency-direction violations | **0** |
| Frozen-platform files modified | **none** |
| Clean-env install (wheel + editable), non-repo cwd | **PASS** |
| Final release validation (version/verify/demo/report/reconstruction/metadata) | **PASS** |

## Documentation inventory

**Product docs** (`docs/ai-hiring/product/`): README, INSTALL, QUICKSTART,
CONFIG_REFERENCE, API_REFERENCE, ARCHITECTURE, DEPLOYMENT, OPERATIONS_RUNBOOK,
SECURITY_REVIEW, DEPENDENCY_REVIEW, PACKAGING, VERSIONING, KNOWN_LIMITATIONS,
PRODUCT_CLAIMS_AUDIT, CHANGELOG.

**Release-governance docs** (`docs/ai-hiring/release/`): RELEASE_MANIFEST,
FREEZE_DECLARATION, CONTROLLED_PILOT_ENTRY_CHECKLIST, CONTROLLED_PILOT_PLAN,
OPERATIONAL_READINESS_CHECKLIST, KNOWN_LIMITATIONS, FINAL_RELEASE_SUMMARY.

**Phase reports** (`docs/ai-hiring/`): H0–H6 completion reports, H5 (8 companions) and
H6 readiness assessments, roadmap, platform boundary.

## Known limitations & deferred work

See [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) (release-level) and
[`../product/KNOWN_LIMITATIONS.md`](../product/KNOWN_LIMITATIONS.md). In brief: no
production HRIS/communication/offer/payroll/identity adapters; deterministic
simulation only; bounded synthetic/de-identified pilot; fairness analysis descriptive
only; local performance is not a production benchmark; repository-wide unrelated
baseline issues remain outside this release.
