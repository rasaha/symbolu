# Public API Reference

The supported surface is exactly what `ai_hiring.product` exports. Names not listed
here are internal and may change without notice, even within the pre-1.0 line.

```python
import ai_hiring.product as P
```

## Composition & runtime

### `build_dev_platform(config: ProductConfig | None = None) -> HiringProduct`
Compose a development product from a validated config (defaults if `None`).
Deterministic simulation only.

### `build_demo_platform() -> HiringProduct`
Compose the product under the fixed, safe `DEMO_CONFIG`.

### `class HiringProduct`
Thin facade over the assembled in-memory environment.
- `.config: ProductConfig`
- `.run_case(spec: CaseSpec) -> CaseRun` — drive one case through the full governed
  lifecycle.
- `.reconstruct(action_proposal_id: str) -> ActionReconstruction` — reconstruct the
  end-to-end accountable chain.

## Configuration

- `class ProductConfig` — typed, fail-closed (see [`CONFIG_REFERENCE.md`](CONFIG_REFERENCE.md)).
- `load_config(mapping: dict | None) -> ProductConfig`
- `class ExecutionMode(str, Enum)`
- Errors: `ProductConfigError`, `UnknownConfigKeyError`, `InvalidConfigValueError`,
  `UnsupportedExecutionModeError`

## Case shaping

- `class CaseSpec` — describes one synthetic case (re-exported from the validation
  lifecycle). Analysis-only attributes never enter the operational pipeline.
- `class CaseRun` — the result of a lifecycle run: stage reached, record ids, final
  states.

## Demo

### `run_demo(product: HiringProduct | None = None) -> DemoResult`
Run the canonical cohort; build a sample accountability report. Constructs the fixed
demo product if none is supplied.

### `class DemoResult`
- `.product_version: str`
- `.runs: list[CaseRun]`
- `.sample_report: AccountabilityReport | None`
- `.summary() -> list[dict]`

### `canonical_cohort() -> list[CaseSpec]`
The five-case demo cohort (advance / hold / reject / review-required / denied).

## Accountability

### `build_accountability_report(product, action_proposal_id, *, redact=None) -> AccountabilityReport`
Assemble the governed record for one executed action. `redact` defaults to the
product's `redact_pii`.

### `class AccountabilityReport`
- `.to_dict() -> dict` — machine-readable.
- `.render_text() -> str` — human-readable.
- Fields: `product_version`, `tenant_id`, `action_proposal_id`, `redacted`,
  `recommendation`, `claims`, `human_decision`, `authorization`, `execution`,
  `reconciliation`, `compensation`, `integrity`, `audit`.

The report is derived **read-only** from the platform's own reconstruction; it adds
no facts, scoring, or conclusions.

## Version

- `PRODUCT_VERSION: str` = `"0.6.0"`
- `PLATFORM_BASELINE: str` = `"v1.0"`
- `STABILITY: str`
- `version_info() -> VersionInfo` — `.production_certified` is always `False`.

## CLI

`python -m ai_hiring.product {version|demo|report|verify}` — see
[`QUICKSTART.md`](QUICKSTART.md). `--json` for machine-readable output;
`report --no-redact` for un-redacted identifiers.

## Stability contract

This surface is **pre-1.0**. It is stable enough to pilot and demo; the `0.` prefix
reserves the right to change it before 1.0. See [`VERSIONING.md`](VERSIONING.md).
