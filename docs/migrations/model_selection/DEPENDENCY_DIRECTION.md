# Model Selection — Dependency Direction

## Rule

```
applications / pilots / control-plane adapters / research
        ↓  (import)
   ugence-model-selection   (leaf: Python standard library only)
```

## Verified

- `ugence_model_selection` imports only the Python standard library and its own modules — a leaf.
- It does **not** import: applications, domains, control plane, AI Control Plane, optional orchestrator,
  Agent Runtime, Hybrid LLM, Governance Provider Framework, concrete providers, the governed-inference
  pilot, the model-selection experiments/pilots, benchmark harnesses, external provider SDKs, or
  credentials/secrets.
- It intentionally does **not** depend on Governance Contracts — the live core requires no
  capability-neutral shared contract, so none was added (avoiding architectural-symmetry coupling).
- All consumers depend on it (directly or via the `execution_gate` compatibility surface); nothing it
  imports depends back on a consumer. No inversion, no cycle.

## Platform validators

- `platform_freeze.dependencies.dependency_report()` → `passed=True`, 0 violations (unchanged).
- `python -m platform_freeze.verify` → PASS, digest `d4ad77e16516e0db6bf2faf3275c8ac8351644e7561d33f157bb55b5a174a1a6`
  (unchanged — Model Selection is not a frozen core tree and is invisible to the freeze).

## Note on provider metadata

`ExecutableRegistry`/`ModelRecord` already serve as the candidate-metadata **port**: consumers supply
`Candidate` metadata and operational `Signal`s; the core never calls a provider. No new port abstraction
was required.
