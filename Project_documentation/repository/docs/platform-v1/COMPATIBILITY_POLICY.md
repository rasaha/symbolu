# Platform v1.0 — Compatibility Policy

## Compatibility review (required for MINOR)

A MINOR change is admissible only if, against the frozen snapshots, it introduces:

- no removed/renamed public symbol;
- no removed enum value, removed field, or field that became required;
- no new *required* function/constructor parameter;
- no protocol-method removal or signature change;
- no exception-base change;
- no dependency-direction change;
- no altered fail-safe behaviour.

Permitted additive changes: new public symbols, new optional fields/parameters,
new enum values, new protocol methods, new capabilities, new conformance
assertions, backward-compatible observability fields.

## Automated gate

```
python -m platform_freeze.verify           # fails on any BREAKING API diff
python -m platform_freeze.classify_change   # proposes PATCH/MINOR/MAJOR/APPLICATION_LOCAL
```

`platform_freeze.compat.compare_snapshots` returns per-symbol diffs with severity
BREAKING / ADDITIVE / INFO. Any BREAKING diff fails verification unless the
platform major is advanced.

## Provider compatibility contracts

Providers declare a contract version and compatible kernel majors in their
`ProviderCompatibility`. The registry rejects contract-incompatible providers at
registration; heterogeneity validation confirms incompatible/disabled/incapable/
unhealthy providers are never selected (H2–H4, H19). New provider *capabilities*
are additive (MINOR); a provider *contract redesign* is MAJOR.
