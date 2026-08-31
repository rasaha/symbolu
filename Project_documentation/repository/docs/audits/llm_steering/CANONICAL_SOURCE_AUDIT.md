# LLM Steering Controller — Canonical Source Audit

**Repository:** `rasaha/symbolu`
**Baseline default tip:** `cbf899043f46db171e9a9ca0f3bcdc9f42442bc1` (Cloud Scaling shadow-harness merge, PR #1334)
**Default branch:** `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`
**Method:** repository-wide `ast` + `grep` search over `*.py` for steering / routing / model-selection / provider-selection / fallback / escalation / model-registry / completion-client symbols, plus **caller analysis** (who imports whom), **test coverage**, and **documentation intent** — not file names.

Machine-readable companions: `artifacts/llm_steering/steering_module_inventory.json`,
`artifacts/llm_steering/steering_call_graph.json`,
`artifacts/llm_steering/steering_public_api_inventory.json`.

---

## 1. Headline finding

There was **no canonical LLM *routing / steering* package** in the repository before this
phase. The documented architecture is a three-stage boundary:

> **Model Selection chooses within policy → routing dispatches (STEERING) → provider execution invokes.**
> (`Project_documentation/repository/docs/migrations/model_selection/RESEARCH_SEPARATION.md`)

- The **selection leaf** ("chooses within policy") is already canonically packaged as
  **`ugence-model-selection`** (`packages/capabilities/model-selection/`), which explicitly
  disclaims routing, retry, failover, load-balancing, provider registration, and credentials.
- The **routing / steering layer** ("routing dispatches") existed only as **research** — dict-based
  `route(...)` engines in `model_selection_experiment/policy.py` and `model_selection_pilot/policy.py`,
  each self-declared as a *distinct research algorithm*, not a product core.
- **Provider execution** ("provider execution invokes") existed only in the research pilot
  (`model_selection_pilot/provider.py`, `execute.py`) — the sole model-selection code that touches
  the network or credentials.

This phase establishes **`ugence-llm-steering-controller`**
(`packages/capabilities/llm-steering-controller/`) as the **first canonical, advisory routing
layer**, complementary to the selection leaf and free of provider execution.

## 2. Name-collision disambiguation (important)

`LLM_STEERING_CONTROLLER_VC_BRIEF.md` describes a **different** artifact under the same name — the
**CRS Controller (C×R×S)**, a model-free *generation-frame* concept (prompt-shaping + output-selection)
living in `scripts/cg_wrapper_ablation/`. That artifact is **orphaned, parked, diagnostics-only**, and
is **generation-control research** — outside this task's scope (which the task defines by its explicit
list: model/provider selection, routing recommendations, capability/cost/latency/quality routing,
fallback/escalation recommendations, candidate ranking, etc.). This audit therefore scopes the "LLM
Steering Controller" to the **routing layer** and classifies the CRS/CG-wrapper work `RESEARCH_ONLY /
OUT OF SCOPE`. See `CANONICAL_SOURCE_DECISION.md` in the package `docs/` for the full rationale.

## 3. Ranked candidate classification

| Rank | Path | Classification | Canonical? | Network/Creds |
|---|---|---|---|---|
| 1 | `packages/capabilities/llm-steering-controller/src/ugence_llm_steering_controller` | **CANONICAL_STEERING_CORE** | **CANONICAL (new)** | none |
| 2 | `packages/capabilities/model-selection/src/ugence_model_selection` | STEERING_POLICY (selection leaf) | canonical (separate distribution) | none |
| 3 | `execution_gate/` (root) | LEGACY_COMPATIBILITY (for the selection leaf) | shim | none |
| 4 | `model_selection_experiment/policy.py` | RESEARCH_ONLY (distinct route engine) | no | none |
| 5 | `model_selection_pilot/policy.py` | RESEARCH_ONLY (F1/F2/G ablation) | no | none |
| 6 | `model_selection_pilot/provider.py`, `execute.py` | **PROVIDER_EXECUTION_ADAPTER** | no | **network + creds** |
| 7 | `model_selection_reconciliation/variants.py` | RESEARCH_ONLY (policy A/B/C study) | no | none |
| 8 | `ugence_console_api/capabilities/registry.py` | APPLICATION_SPECIFIC (catalog metadata) | n/a | n/a |
| 9 | `scripts/cg_wrapper_ablation/` (CRS) | RESEARCH_ONLY / OUT OF SCOPE (name collision) | no | none |
| 10 | `symbolu_core.*.router`, `agentic.ontology.router`, `trading2/analysis/model_selector.py`, `sklearn.model_selection` | UNRELATED (false positives) | n/a | n/a |

## 4. Why the canonical routing source is *new*, not selected from an existing file

- **Callers:** no in-repo module imports any `route(...)` engine as a production dependency;
  the only production callers of model-selection code import the **selection leaf**
  (`ugence_model_selection`) or its `execution_gate` alias. The research route engines are consumed
  only by other research/shadow code.
- **Tests:** the route engines are covered only by their own research suites; none is a product
  contract.
- **Documentation:** every design doc positions routing as advisory and **separate** from both the
  selection leaf and provider execution, and none names an importable routing *package*.
- **Public API:** none of the research engines exposes a typed routing-recommendation contract set
  (`SteeringRequest`, `RoutingRecommendation`, `ModelCandidate`, …). The new package does.

Selecting a file by name (`*router*.py`) would have been wrong: those are neural/semantic/MoE routers
(§3 row 10), not LLM provider routing.

## 5. Disposition summary

- **Establish** `ugence-llm-steering-controller` as the canonical advisory routing layer (this phase).
- **Keep** `ugence-model-selection` unchanged as the complementary selection leaf (not a dependency).
- **Leave** the research route engines (`model_selection_experiment`, `model_selection_pilot`,
  `model_selection_reconciliation`) in place, unchanged and classified `RESEARCH_ONLY` — they are
  distinct algorithms already documented as separate; folding them in would change behavior.
- **Quarantine** provider execution (`model_selection_pilot/provider.py`, `execute.py`) outside the
  advisory wheel; document it as a future, independently-governed runtime adapter.
- **Exclude** the CRS/CG-wrapper "steering" (generation-control research) and all unrelated routers.
