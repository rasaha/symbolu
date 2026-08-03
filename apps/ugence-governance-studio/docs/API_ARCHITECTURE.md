# Governance Studio API — Architecture (P3B)

## Position

```
Governance Studio API  (this phase, P3B)
        │  public API only
        ▼
ugence-agent-workforce-composer 0.2.1   (awc.v1 / awc.composition.v1 / awc.compiler_adapter.v2)
        │  data-only serialized artifacts
        ▼
Policy Workflow Compiler 0.2.0   (workflow_ir.v1 / workflow_ir.v2)
```

The API is a **thin orchestration and serialization layer**. It sequences public
AWC calls and serializes their results; it owns **no** planning algorithm.

## Layers

| Layer | Module | Responsibility |
|-------|--------|----------------|
| Presentation | `api/*` routers | HTTP surface, envelope wrapping, status mapping |
| Contracts | `contracts/*` | strict request models, response/error envelopes |
| Orchestration | `services/orchestration.py` | sequences public AWC calls (no logic) |
| Scenario execution | `services/scenario_service.py` | run + verify + workflow projection + export |
| Explanations | `services/explain.py` | projections of existing AWC outputs |
| Catalog | `scenarios/catalog.py` | read-only fixtures, hash verification, immutability |
| Security | `security/*` | headers, body-size limit, auth/rate-limit seams |
| Serialization | `serialization/canonical.py` | canonical JSON for presentation only |

## Delegation

`AwcOrchestrationService` mirrors the exact call sequence the frozen P3A fixture
generator uses:

```
adapt_compiled_workflow → evaluate_workflow_eligibility / evaluate_registry_for_role
    → rank_eligible_candidates → build_role_dependency_graph → compose_agent_team
    → build_agent_team_plan → build_replay_record → replay_agent_team_plan
```

Because these are the same public functions, built-in scenarios reproduce the
committed fingerprints byte-for-byte (`procurement` plan `sha256:c19735…`).

## Application factory

`create_app(settings: ApiSettings | None = None) -> FastAPI` is explicit and
import-light: it builds the read-only catalog and stateless orchestration service
once and stores them on `app.state.ctx`. No large fixture is loaded at import
time and there is no mutable global state.
