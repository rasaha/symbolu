# Versioning

Four version concepts are kept explicit:

- **Implementation version** (`ugence_tap_provider.__version__`) = `0.1.0` —
  unchanged by the package relocation.
- **Canonical distribution version** (`DISTRIBUTION_VERSION`) = `0.1.0`.
- **Legacy compatibility distribution version** (`dgm-tap-provider`) = `0.1.0`.
- **Contract version** = `1.0.0`; **mapping version** = `tap-map-1`.

`version_info()` reports all of the above plus compatible kernel majors, resolved
dependency versions, and `production_certified = False`.

Compatibility policy: the public `.api` surface is byte-stable (PATCH). Additive
public helpers (e.g. `version_info`) are MINOR. Breaking the contract, the
authority boundary, or the fail-safe behavior would be MAJOR.
