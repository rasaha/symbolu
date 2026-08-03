# Configuration

`TapSettings` (immutable) with `validate()`:

| field | default | notes |
|---|---|---|
| `provider_id` | `"tap"` | |
| `mode` | `"in_process"` | `in_process` \| `remote` |
| `default` | `True` | default provider for its kind |
| `contract_version` | `"1.0.0"` | major must be `1` |
| `endpoint` | `"tap://in-memory"` | remote endpoint reference |
| `policy_bundle` | `"default"` | |
| `evidence_resolution` | `"caller_supplied"` | one of caller_supplied/provider_client/external_resolver |
| `fail_safe` | `True` | see FAIL_SAFE_BEHAVIOR.md |
| `secret_refs` | `{}` | **references only** (`ref:...`); embedded secrets rejected |

Invalid mode, incompatible contract version, invalid evidence-resolution mode, and
embedded secrets are all rejected with `ProviderConfigurationError`.

Build a provider with `build_tap_provider(engine=..., settings=..., invocation_log=...)`.
