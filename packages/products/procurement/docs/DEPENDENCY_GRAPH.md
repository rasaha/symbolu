# Dependency Graph

Ugence Procurement keeps a minimal, honest dependency surface. It depends on the
governance kernel and pydantic — nothing more in its core.

## Core dependencies (always present)

```toml
dependencies = [
    "pydantic>=2",
    "ugence-decision-authority>=1.0.0",
]
```

| Dependency | Role |
|---|---|
| `pydantic>=2` | Contract base (`DomainModel` frozen models) for purchase-request and assessment contracts |
| `ugence-decision-authority>=1.0.0` | The domain-neutral Decision Authority governance kernel this product composes |

## Optional extras (each backed by real code)

```toml
[project.optional-dependencies]
api = ["fastapi>=0.100.0", "uvicorn>=0.20.0"]
dev = ["pytest>=7.0", "build>=1.0"]
```

- `api` — reserved for a **future** thin HTTP layer. The core `ugence_procurement.routes.ProcurementAPI` is framework-agnostic and needs neither FastAPI nor uvicorn. `version_info()` probes availability at runtime.
- `dev` — test and build tooling.

## Explicitly absent (verified by search)

None of the following are imported by any procurement source path, and none are
added by this extraction:

`numpy`, `torch`, `fastapi`/`uvicorn` (core), `sqlalchemy`, `requests`, `httpx`,
`openai`, `anthropic`, `mistralai`, cloud SDKs, ERP SDKs, database drivers,
`ugence_governance_contracts`, `ugence_governance_provider_framework`,
`ugence_tap_provider`, `ugence_actiongate_provider`, `dgm-tap-provider`,
`dgm-actiongate-provider`, `ai_hiring` / `ugence_ai_hiring`,
`products.code_governance` / `ugence_code_governance`, Agent Runtime, Hybrid LLM,
Cloud Scaling Controller, H22.

There is **no** TAP, ActionGate, ERP, model, database, or cloud dependency. The
`BudgetAuthorityAdapter` implements the kernel `ActionControlPlanePort` directly and
is **not** ActionGate.

## Dependency direction

Dependency flows in **one direction only**: product → kernel. The kernel never
imports procurement. Procurement implements kernel ports and drives kernel
services; it never modifies the kernel.

```
ugence_procurement  ──depends on──▶  ugence_decision_authority
     (product vertical)                  (domain-neutral kernel)
```

## Canonical kernel namespace

Procurement imports the kernel from the **canonical** `ugence_decision_authority.*`
namespace — not the legacy `decision_governance` facade. The legacy
`decision_governance` name is itself a compatibility-only facade over
`ugence_decision_authority`, so this is a pure import-path choice with no behavior
change.
