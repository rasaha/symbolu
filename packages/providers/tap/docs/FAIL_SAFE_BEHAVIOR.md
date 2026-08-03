# Fail-safe behavior

**Outcome map** (uncertainty is never promoted to support):

| native TAP outcome | neutral coverage |
|---|---|
| SUPPORTED | SUPPORTED |
| UNSUPPORTED | UNSUPPORTED |
| CONSTRAINED | CONSTRAINED |
| INDETERMINATE | INDETERMINATE |
| UNKNOWN / unmapped | INDETERMINATE |

**Two modes:**

- `fail_safe=True` (default): a normalized infrastructure failure returns an
  **INDETERMINATE** result and never leaks a TAP-native exception.
- `fail_safe=False`: the classified framework `ProviderError` is raised for callers
  that own normalization.

In both modes: no native TAP exception crosses the boundary, failure never produces
`SUPPORTED`, error classification is deterministic, invocation logging stays
consistent, and no hidden retry or network behavior is added.

**Error translation:** invalid config → `ProviderConfigurationError`; protocol
mismatch → `ProviderProtocolError`; unavailable → `ProviderUnavailableError`;
timeout → `ProviderTimeoutError`; malformed result → `ProviderResultValidationError`;
unexpected → `ProviderError`.

This is the release gate — `tests/authority/test_outcome_safety.py`.
