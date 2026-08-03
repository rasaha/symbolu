# Configuration

`ActionGateSettings` configures the provider:

| Field | Default | Meaning |
|---|---|---|
| `provider_id` | `"actiongate"` | registry id |
| `mode` | `"in_process"` | `in_process` or `remote` |
| `default` | `True` | default provider for its kind |
| `contract_version` | `"1.0.0"` | must be major `1` |
| `endpoint` | `"actiongate://in-memory"` | remote endpoint (abstraction) |
| `secret_refs` | `{}` | secret **references** only — never embedded secrets |

```python
from ugence_actiongate_provider.configuration import ActionGateSettings, build_actiongate_provider
settings = ActionGateSettings.from_settings({"mode": "remote"})
provider = build_actiongate_provider(settings=settings)
```

`validate()` raises `ProviderConfigurationError` for an unsupported mode or an
incompatible contract major. Secrets are never embedded — only opaque references are
accepted, and the provider records no secret material.
