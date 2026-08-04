# Canonical Source Decision

## Decision

The canonical LLM **routing / steering** implementation is, as of this phase, the single tree:

```
packages/capabilities/llm-steering-controller/src/ugence_llm_steering_controller
```

distributed as **`ugence-llm-steering-controller`** (import `ugence_llm_steering_controller`,
version `0.1.0`).

## Why it is new rather than adopted from an existing file

The repository already canonically packages the deterministic **selection leaf** as
`ugence-model-selection` (`packages/capabilities/model-selection/`), which explicitly disclaims routing.
The **routing layer** above it existed only as research (`model_selection_experiment/policy.py`,
`model_selection_pilot/policy.py`) — dict-based `route(...)` engines, each self-declared a *distinct
research algorithm* (see `docs/migrations/model_selection/RESEARCH_SEPARATION.md`), consumed only by
other research/shadow code, with no typed routing-recommendation contract set. The full audit
(`docs/audits/llm_steering/CANONICAL_SOURCE_AUDIT.md`) confirms via callers, tests, docs, and public API
— not file names — that **no canonical routing package existed**. This phase creates it.

The documented three-stage boundary is preserved:

> **Model Selection chooses within policy → routing dispatches (this controller) → provider execution invokes.**

## Name-collision disambiguation

`LLM_STEERING_CONTROLLER_VC_BRIEF.md` uses the name "LLM Steering Controller" for a **different**
artifact — the **CRS Controller (C×R×S)**, a model-free *generation-frame* concept (prompt-shaping +
output-selection) under `scripts/cg_wrapper_ablation/`. That work is orphaned, parked, and
diagnostics-only, and is **generation-control research**, which this task's scope excludes. This
task defines the "LLM Steering Controller" by its explicit capability list — model/provider selection,
routing recommendations, capability/cost/latency/quality routing, fallback/escalation recommendations,
candidate ranking, evidence — all of which are the **routing layer**. We therefore scope this package to
routing and classify the CRS/CG-wrapper work `RESEARCH_ONLY / OUT OF SCOPE`.

## Relationship to `ugence-model-selection`

Complementary, not overlapping, and **not a dependency**:

| | Model Selection (leaf) | Steering Controller (this package) |
|---|---|---|
| Input | already-approved candidate set | metadata registry + request requirements |
| Concern | eligibility + policy ranking | discovery + routing constraints + ranking + fallback/escalation recommendations |
| Contracts | `Candidate`, `Request`, `Selection`, `ExecutionGate` | `SteeringRequest`, `ModelCandidate`, `RoutingRecommendation`, … |
| Depends on the other? | no | no |

A governed runtime may compose the two; neither imports the other, and no logic is duplicated (see
`docs/audits/llm_steering/DUPLICATE_IMPLEMENTATION_REPORT.md`).

## Single-source guarantee

`scripts/audit_single_source.py` (CI-enforced) fails if the canonical controller's unique class
sentinels appear outside this tree. The research route engines carry none of those sentinels and remain
in place, unchanged, as distinct research algorithms.
