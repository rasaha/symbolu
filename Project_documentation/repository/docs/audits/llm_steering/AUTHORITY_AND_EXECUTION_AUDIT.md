# LLM Steering Controller — Authority & Execution Audit

This audit answers the four authority questions for the packaged controller and records
where any execution capability lives.

## 1. The four questions

| # | Question | Answer for `ugence-llm-steering-controller` |
|---|---|---|
| A | Does it recommend routing decisions only? | **Yes.** Every output is a `RoutingRecommendation` / `SteeringResult`. |
| B | Does it directly invoke an LLM provider? | **No.** No provider SDK is imported; no network call exists in packaged source. |
| C | Can it alter provider configuration or credentials? | **No.** No credential access; the registry fails closed on any secret-shaped key. |
| D | Can it trigger retries / fallbacks / escalations that produce external calls? | **No.** Fallback and escalation are *recommendations* (ordered candidates + conditions); the controller executes none of them. |

## 2. Declared authority

```
authority_class:                        ADVISORY
execution_capability:                   NONE
provider_invocation_capability:         NONE
credential_access:                      NONE
routing_decision_is_authority:          false
live_provider_calls_enabled_by_default: false
recommendation_only:                    true
```

(Source of truth: `packages/capabilities/llm-steering-controller/module_manifest.json`, asserted by
`tests/boundaries/test_advisory_boundary.py` and the distribution verifier.)

## 3. Required conceptual flow (enforced)

```
REQUEST REQUIREMENTS
    → MODEL/PROVIDER CANDIDATE DISCOVERY      (registry snapshot only; no catalog query)
    → POLICY AND CONSTRAINT FILTERING         (hard, fail-closed, BEFORE scoring)
    → CANDIDATE SCORING                        (soft, decomposable, over eligible only)
    → ROUTING RECOMMENDATION                   (rank + deterministic tie-break)
    → EXPLANATION AND EVIDENCE
```

The package returns a recommendation to a **separately governed runtime**. It performs none of:
provider API call, model inference call, credential loading, retry execution, fallback execution,
tool execution, agent execution, billing commitment, or network transmission.

## 4. Where execution capability actually lives (and stays)

| Capability | Location | Disposition |
|---|---|---|
| Provider HTTP/SDK calls (`urllib`, `boto3`) | `model_selection_pilot/provider.py` | **Outside** the advisory wheel; monorepo-only research; credential-blocked. |
| Credential discovery (`os.environ["*_API_KEY"]`) | `model_selection_pilot/provider.py`, `harness.py` | Outside the wheel. Never imported by the steering package. |
| Execution dispatch / retries / cost accounting | `model_selection_pilot/execute.py` | Outside the wheel. |
| Fallback *execution* | (belongs to Agent Runtime / a governed runtime) | Not implemented anywhere in this package. |

The distribution verifier proves, against the built wheel, that none of the above is present:
no forbidden imports, no network/credential source patterns, no provider-execution paths or symbols,
and — at runtime, under an audit hook that hard-fails on any socket/subprocess/exec — that import and
recommendation open no socket and read no poisoned credential env var.

## 5. Authority-conflict check

The steering core was authored fresh as an advisory layer; it did **not** require separating execution
out of an existing mixed module, because the only mixed module (`model_selection_pilot`) is research and
was already quarantined by the earlier Model Selection separation. No behavior-changing separation was
performed, so **no authority conflict arises**. Had the routing logic been entangled with
`provider.py`, the correct action would have been to stop and report — it was not.
