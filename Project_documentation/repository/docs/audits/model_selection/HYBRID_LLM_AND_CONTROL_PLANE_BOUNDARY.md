# Model Selection — Hybrid LLM & AI Control Plane Boundary

Sections 11–12. Does live Model Selection code bleed into Hybrid LLM, the AI Control Plane, the Optional
Orchestrator, provider execution, or a generic provider registry? Verified by reading the neighboring
code, not by folder name.

## 1. Established capability separation (from the terminology boundary audit)

`UGENCE_TERMINOLOGY_PRODUCT_CAPABILITY_BOUNDARY_AUDIT.md` pins **Model Selection = capability #8**
("Policy-bounded model/provider selection"), **distinct from Hybrid LLM = #9** ("Local/frontier handover,
research or runtime"). The live code confirms this separation holds.

## 2. Hybrid LLM boundary

| Neighbor | What it actually does | Is it Model Selection? |
|---|---|---|
| `symbolu/hybrid/router.py` (`SemanticRouter`), `rich_routing.py`; `symbolu_core/hybrid/*` (mirror) | routes a query to **internal specialized 7B sub-models** (ACTION/REASONING/RELATIONSHIP/CREATIVE) by phoneme/ontological-layer signature, to replace a single large model | **No — Hybrid LLM.** Composition/handover among internal model specializations; not policy selection among approved *provider* models |
| `symbolu/providers/enterprise/phoneme_router.py`, `consumer/trained_router.py`, `interfaces/router_provider.py` | wrap the `SemanticRouter` (phoneme vs trained-classifier query routing) | **No — Hybrid LLM** |
| `experiments/hybrid_token_event_attention/real_model/reasoning_router.py` | maps a decision task-family to a reasoning **pathway** (DETERMINISTIC / +EVENT_ATTENTION / QUARANTINE); "does NOT train a router; fixed function of the decision contract" | **No — Hybrid LLM** (local-vs-attention handover) |
| `agentic/hybrid_handover/` (`frontier.py` + evaluation harness) | local/frontier handover scaffold | **No — Hybrid LLM** (the canonical #9 location) |

**Finding:** no Model Selection code performs handover, egress minimization, local/frontier composition,
prompt transformation, context filtering, or model-runtime orchestration. Conversely, no Hybrid LLM
module performs policy-constrained provider eligibility or governed selection. **The boundary is clean.**
Model Selection legitimately decides "use local A / frontier B / escalate C / no eligible model"; Hybrid
LLM owns *how* the handover is executed. These must not be merged merely because both "choose a model."

## 3. AI Control Plane & Optional Orchestrator boundary

| Neighbor | What it does | Coupling to Model Selection |
|---|---|---|
| `control_plane/orchestrator.py` | reference orchestrator; "holds NO decision authority … only routes, guards, records"; wires ExecutionGate→ModelPolicy→Provider→TAP→ActionGate | **Consumes** Model Selection via `ExecutionGateAdapter`/`ModelPolicyAdapter`. Correct direction. |
| `control_plane/policy_context.py` (`PolicyContext`), `contracts.py` (RequestNormalizer contract) | pins policy/registry/contract versions per trace; "Holds no model/eligibility authority"; carries provider allow/deny as data-flow constraints | Upstream envelope that *feeds* MSP; does not implement selection |
| `control_plane_shadow/adapters/model_policy_adapter.py` | wraps `model_selection_experiment.policy.route`; intersects result with eligible set; emits `MODEL.SELECTED_MODEL_NOT_ELIGIBLE` rather than override | **Consumes** MSP; enforces the eligibility invariant on the consumer side |
| `ai_control_plane_v3/` | 11 markdown docs, no code | Unrelated (documentation) |
| `cloud_controller/` | Kubernetes autoscaling (scale_out/scale_in) | Unrelated (infra) |

**Finding:** the control plane and orchestrator **depend on** Model Selection (adapter pattern); neither
transfers its authority *into* MSP, and MSP does not import them (see `IMPORT_GRAPH.md`). MSP remains
**independently usable and bypassable** — an application can supply a pre-authorized model directly and
skip selection. There is **no improper coupling** of Model Selection to platform administration or
orchestration in the live code.

## 4. Provider execution & generic provider registry boundary

| Neighbor | What it does | Verdict |
|---|---|---|
| `agentic/llm/providers.py`, `symbolu/llm/providers.py` | unified Anthropic/Google client; concrete API calls; **static tier→model-name lookup** by presentation tier | **Provider execution / gateway** — not eligibility, scoring, or a governed registry |
| `model_selection_pilot/provider.py` | Anthropic/OpenAI/Bedrock adapters (credential-blocked → Stub) | **Provider execution** co-located in the pilot; not selection |
| `provider_heterogeneity_validation/selection/resolve.py` | selects governance-**provider implementations** with FIXED/ORDERED/CAPABILITY_REQUIRED/BOUNDED_FALLBACK | **Governance-provider resolution** — selection-*shaped* but a different object; not Model Selection and not a generic model registry |
| `execution_gate/registry.py` (`ExecutableRegistry`) | model-candidate registry with declared/verified status + TTL, driven by the gate | **Model Selection's own registry port** — governed, not a generic provider registry; correctly owned |

**Finding:** Model Selection does not own provider invocation, retry, secret management, or billing, and
its registry is a governed candidate-metadata port, **not** a generic provider registry. The one caution
is that `model_selection_pilot/` physically co-locates provider-execution code with selection code — a
research-harness convenience that must **not** migrate into a canonical Model Selection package.

## 5. Boundary verdict

Model Selection is **cleanly bounded** against Hybrid LLM (separate), the AI Control Plane / Orchestrator
(they consume it; it stays bypassable), and provider execution (not owned). The only boundary hygiene
item is physical co-location of execution code inside `model_selection_pilot/`, which the migration must
leave behind. No boundary bleed forces a redesign.
