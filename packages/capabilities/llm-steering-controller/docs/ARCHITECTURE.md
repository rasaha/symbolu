# Architecture

The LLM Steering Controller is the deterministic **routing-recommendation layer** of the Ugence
platform. It turns a request's requirements plus a metadata-only candidate registry into a ranked,
explainable routing recommendation — and hands it to a separately governed runtime.

## Pipeline

```
SteeringRequest ──► discover ──► hard-constraint filter ──► score eligible ──► rank + tie-break ──► RoutingRecommendation
   (requirements)   (registry)   (fail-closed, pre-score)   (decomposable)     (deterministic)      (+ explanation + evidence)
```

| Stage | Module | Responsibility |
|---|---|---|
| Discovery | `candidates.py` | Pair each registry model with its provider (in-memory snapshot only). |
| Hard filtering | `constraints.py` | Apply hard constraints in fixed order, fail-closed, **before** scoring. |
| Scoring | `scoring.py` + `estimate.py` | Decomposable per-dimension fit scores over the eligible set only. |
| Policy | `policy.py` | Weight presets, overrides, deterministic tie-break rule. |
| Recommendation | `controller.py` | Rank, build recommendation + fallback/escalation recommendations. |
| Explanation | `explanation.py` | Human-readable + structured reasons. |
| Evidence | `evidence.py` | Fingerprints, decision id, reproducible rejection + score records, trace. |
| Contracts | `contracts.py` | All typed inputs/outputs (frozen dataclasses + str enums). |
| Registry | `registry.py` | Metadata-only candidate store; fails closed on secret-shaped keys. |
| Simulation | `simulation.py` | Deterministic offline replay over local fixtures (labelled). |
| CLI | `cli.py` | Offline, non-executing subcommands. |

## Design invariants

- **Determinism.** No clock, no randomness, no ambient state. `decision_id` is a pure hash of the
  registry/request/policy fingerprints and the ranked ids. Identical inputs → identical output.
- **Hard before soft.** Eligibility is decided entirely by `constraints.py`; scoring runs only over
  survivors and can never restore a disqualified candidate.
- **Fail-closed.** Missing capability metadata is treated as unsupported; privacy and residency reject
  on uncertainty; a negative budget is a contract error.
- **Advisory only.** Output carries `execution_status = NOT_EXECUTED`, `recommendation_only = True`.
  Fallback and escalation are recommendations, never actions.
- **Leaf.** Python standard library only; no third-party or sibling-package imports.

## Data model (summary)

- **Inputs:** `SteeringRequest` (with `TaskRequirements`), `CandidateRegistry` (of `ModelCandidate` +
  `ProviderCandidate`), optional `RoutingPolicy`.
- **Outputs:** `SteeringResult` → `RoutingRecommendation` (with `CandidateScore`, `RoutingConstraint`s,
  `FallbackRecommendation`, `RoutingExplanation`, `RoutingEvidence`, `RoutingDecisionTrace`), or a typed
  `NO_ELIGIBLE_CANDIDATE` outcome whose evidence still explains every rejection.
