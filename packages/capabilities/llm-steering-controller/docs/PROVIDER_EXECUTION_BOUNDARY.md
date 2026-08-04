# Provider Execution Boundary

## The rule

The advisory wheel contains **no provider execution**. It never imports a provider SDK, opens a socket,
loads a credential, or invokes a model. This is enforced statically (source + wheel scans) and at
runtime (audit-hook probes) — see `AUTHORITY_BOUNDARY.md` and the distribution verifier.

## Where execution lives instead

Provider execution in this repository lives only in the **research pilot**, outside this distribution:

```
model_selection_pilot/provider.py   # urllib / boto3 adapters; os.environ API keys; credential-blocked
model_selection_pilot/execute.py    # dispatch / retries / cost accounting
```

These are **monorepo-only research** code, classified `PROVIDER_EXECUTION_ADAPTER`
(`docs/audits/llm_steering/`). They are:

- **not** a dependency of `ugence-llm-steering-controller`,
- **not** imported by any packaged module,
- **not** present in the built wheel (verified by wheel-content inspection),
- credential-blocked (they return a deterministic stub when no keys are set).

## Future runtime adapter

If provider execution is ever productized, it must be a **separate, independently-governed
distribution** (e.g. a runtime/agent execution layer) that *consumes* a `RoutingRecommendation` and owns
credentials, retries, and fallback **execution**. The steering controller will still only recommend.
This mirrors the Cloud Scaling split (advisory controller vs monorepo-only `cloud_scaling_operations`).

## Fallback / escalation

The controller emits `FallbackRecommendation` (ordered candidates + conditions) and escalation
conditions. It executes neither. Turning a recommendation into a call — including a fallback call after a
failure — is the runtime's responsibility, never the controller's. Converting an error into an external
call is explicitly outside this package.
