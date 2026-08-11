# Package Boundary — CM-TA1 integration

## One-way composition

This distribution imports **exactly** its two declared cores and nothing else from the
monorepo:

- `ugence_context_minimization` — the Context Minimization leaf (token-accounting
  contracts: `ApiCallTokenRecord`, `ProviderTokenUsage`, `RequestTokenEstimate`,
  `PreparedApiCall`, `reconcile_api_call_measurement`, `aggregate_logical_request_usage`,
  `TokenAccountingSink`, …).
- `ugence_agent_runtime` — the Agent Runtime core (`ProviderAttempt`, `AttemptObserver`,
  `PROVIDER_USAGE_METADATA_KEY`, and the H22-D `BudgetCoordinator` / `BudgetSettlement` /
  `BudgetEstimateExceeded`).

**Neither core imports this package.** The reverse-dependency guard is enforced by
`tests/packaging/test_packaging.py`, which parses both cores' source and asserts the
integration namespace never appears.

## No provider SDK, no tokenizer, no persistence

The base install declares **only** the two first-party cores — no OpenAI/Anthropic/Google
SDK, no `tiktoken`/`transformers`/`torch`, no database driver. The packaging test asserts
this against both the source imports and `pyproject.toml`. The isolated-install verifier
proves the package installs and runs end-to-end from the first-party wheelhouse with
`--no-index` (no third-party wheel needed).

Provider-specific usage normalizers (real vendor SDK adapters) are **optional** and live
**outside** this package. The bundled `MappingUsageNormalizer` is a mechanical key-mapping
helper, not a vendor adapter.

## What the integration is allowed to do

- Translate a neutral `ProviderAttempt` → typed `ApiCallTokenRecord` via an injected
  normalizer, delegating all strict validation to the CM core.
- Push records to a CM `TokenAccountingSink`.
- Feed **authoritative** provider-reported usage into the existing H22-D budget settlement
  seam; preserve conservative full-reservation settlement when usage is unavailable; surface
  `BudgetEstimateExceeded` on an overrun.

## What it must never do

- Import a provider SDK, tokenizer, database, or network client in the base install.
- Move provider-specific token semantics into either core.
- Fabricate usage (unknown stays `None`), silently drop an attempt (unregistered attempts
  are counted in `skipped_attempts`), or clamp/hide a budget overrun.
- Compute a cost or an invoice — no pricing authority lives here.
