# Configuration Reference

Configuration is a small, **typed, fail-closed** surface
(`ai_hiring.product.config`). Build it two ways:

```python
from ai_hiring.product import ProductConfig, load_config

cfg = ProductConfig(tenant="acme")                 # typed constructor
cfg = load_config({"tenant": "acme", "max_retries": 3})   # from an untrusted mapping
```

## Fail-closed rules

| Rule | Behavior |
|---|---|
| Unknown key | `load_config` raises `UnknownConfigKeyError` — no silent typos |
| Invalid type/range | raises `InvalidConfigValueError` — never coerced to a default |
| Production execution mode | raises `UnsupportedExecutionModeError` — no such adapter ships |

An instance that exists is always valid: all invariants are enforced at
construction, so downstream composition never has to re-validate.

## Keys

| Key | Type | Default | Constraints |
|---|---|---|---|
| `tenant` | `str` | `"demo-tenant"` | non-empty |
| `execution_mode` | `ExecutionMode` / `str` | `DETERMINISTIC_SIMULATION` | **must** be `DETERMINISTIC_SIMULATION` |
| `max_retries` | `int` | `2` | `0 ≤ n ≤ 10` (bool rejected) |
| `redact_pii` | `bool` | `True` | — |
| `extra_reviewers` | `tuple[str, ...]` | `()` | each non-empty |

## `ExecutionMode`

```python
class ExecutionMode(str, Enum):
    DETERMINISTIC_SIMULATION   # the only supported value
    PRODUCTION_LIVE            # reserved; selecting it fails closed
    PRODUCTION_DRY_RUN         # reserved; selecting it fails closed
```

The two production members exist **only** so the boundary can name and reject them
explicitly. There is no code path in this package that performs a production
external effect; selecting a production mode raises before any service is wired.

## Error hierarchy

```
ProductConfigError (ValueError)
├── UnknownConfigKeyError
├── InvalidConfigValueError
└── UnsupportedExecutionModeError
```

## `redact_pii`

When `True` (default), accountability reports replace candidate subject references
and human/AI actor identifiers with stable, salted pseudonyms
(`subject:<hash>` / `actor:<hash>`), so a report can be shared for audit without
exposing personal or identity data. Redaction is deterministic — the same input
always yields the same pseudonym — so chains remain internally correlatable while
de-identified. A per-report override is available:
`build_accountability_report(product, id, redact=False)`.
