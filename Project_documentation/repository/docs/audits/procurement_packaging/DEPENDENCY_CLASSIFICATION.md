# Procurement Dependency Classification

## Before (original implementation, `IMPORT_GRAPH_BEFORE.json`)

Non-stdlib import roots across all 24 non-test source files:

| Root | Kind | Disposition |
|---|---|---|
| `decision_governance` | Legacy DGM kernel namespace (itself a compat facade over `ugence_decision_authority`) | **Migrate** to `ugence_decision_authority` (import-path only) |
| `pydantic` | Contract base (`DomainModel` frozen models) | **Keep** as core dependency (`pydantic>=2`) |

Stdlib only otherwise: `__future__`, `dataclasses`, `datetime`, `enum`, `typing`.

## Explicitly absent (verified by search)

None of the following are imported by any procurement source path, and none are
added by this extraction:

`numpy`, `torch`, `fastapi`, `uvicorn`, `sqlalchemy`, `requests`, `httpx`,
`openai`, `anthropic`, `mistralai`, cloud SDKs, ERP SDKs, database drivers,
`ugence_governance_contracts`, `ugence_governance_provider_framework`,
`ugence_tap_provider`, `ugence_actiongate_provider`, `dgm-tap-provider`,
`dgm-actiongate-provider`, `ai_hiring`, `ugence_ai_hiring`,
`products.code_governance`, `ugence_code_governance`, Agent Runtime, Hybrid LLM,
Cloud Scaling Controller, H22.

## After (canonical `ugence_procurement`)

Core dependencies:

```toml
dependencies = [
    "pydantic>=2",
    "ugence-decision-authority>=1.0.0",
]
```

Optional extras (each backed by real code):

```toml
[project.optional-dependencies]
api = ["fastapi>=0.100.0", "uvicorn>=0.20.0"]   # optional web surface (ugence_procurement.routes is framework-agnostic; extra reserved for a future thin HTTP layer)
dev = ["pytest>=7", "build>=1"]
```

TAP / ActionGate: the current procurement reference workflow does **not** use TAP or
ActionGate. `BudgetAuthorityAdapter` implements the kernel `ActionControlPlanePort`
directly and is **not** relabeled as ActionGate. No TAP/ActionGate dependency is
added in this bounded phase; a behavior-preserving optional ActionGate integration is
deferred to the next phase (see `NEXT_PHASES.md`).
