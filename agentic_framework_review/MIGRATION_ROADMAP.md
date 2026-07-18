# Migration Roadmap (Part 8 — current → future, with compatibility)

How to move from today's Agentic Framework to V2 (the Agent Runtime that feeds the AI Control Plane) without breaking existing users and without touching ACP/ActionGate/Context Minimization/CSR.

Labels: `FACT` / `RECOMMENDATION` / `INTERPRETATION`. This is a proposed roadmap; nothing here has been executed (no production code was modified in this milestone).

---

## 0. Compatibility contract (non-negotiable)

**FACT — the surface to preserve:** `__init__.py` exports ~120 public symbols (v1.9.0), and `agent.py` documents an additive, backward-compatible primitives design (R1–R11 added opt-in params without changing existing signatures).

**RECOMMENDATION.** Every step below is additive or internal. Public `AgenticLLMWrapper.run()/run_stream()/run_structured()` signatures and the exported symbol set stay stable through V2. The control-plane integration arrives as **new opt-in constructor params** (`actiongate_client=`, `context_min_client=`, `evidence_mode=`), defaulting OFF, so existing embedders see no behavior change until they opt in. Removals (CG governance, dead adapters) are internal, non-exported symbols.

---

## Stage 0 — Truth-in-labeling (no behavior change)

Prerequisite: the docs currently contradict the code (framework readiness audit). Fix claims before architecture.

| Action | Evidence | Risk |
|---|---|---|
| Correct "replayable trace" → "event-summary trace"; "hard cost caps" → "token caps (cost inert)"; "token streaming" → "lifecycle streaming"; "1550+ passing in CI" → "1550+ local, no CI gate" | framework readiness audit findings | none (docs) |
| Mark CG sovereign-state governance as deprecated/off in developer docs to match `signal_config` (AUROC 0.457) | `signal_config.py`, founder notes | none |
| Unify version numbers and the two import roots (`agentic.` vs `symbolu.agentic_framework`) | v1.4→v6.2 spread; dual roots | low (alias shim) |
| Add a CI workflow that actually runs the suite; fix the cross-test state pollution causing the "51 failed" clean-run | readiness audit | medium (test hygiene) |

**Compatibility:** 100%. Docs + CI only.

---

## Stage 1 — Consolidate the internal duplication (internal refactor)

Resolve the framework-vs-itself duplication before touching siblings.

| Action | From → To | Compatibility |
|---|---|---|
| Merge World A `mcp_gateway` decision + World B `GovernanceService` into one internal `prescreen/` path | two PDPs → one | Public API unchanged; `GovernanceService` kept as a thin facade over the merged path |
| Route `safety_contract` thresholds from `policy_bundle.SafetyPolicy` | hardcoded → policy-sourced | Behavior identical if bundle mirrors current constants |
| Collapse the two governance schema families; delete `governance_adapter` P52 facade | two → one | `governance_adapter` is non-exported; safe |
| Fix `coherence_tracker.factual_alignment` (drop the constant 0.7 from the weighted sum or compute it) | fabricated input removed | Coherence scores shift slightly — gate behind a flag |
| Demote `jepa_governance`, `trust/`, `sovereign_bridge`, `olm_bridge`, signal_adapters to explicit ADVISORY (non-blocking) | blocking-capable → advisory | Only affects deployments that flipped them (few/none; trust default LEGACY) |
| Remove CG sovereign-state governance from the decision path | falsified signal removed | Off by default already; internal removal |

**Compatibility:** ~100% for public embedders; internal-only churn.

---

## Stage 2 — Stand up the control-plane integration seams (additive, opt-in)

New clients; default OFF. The framework becomes a *proposer* when opted in.

| Action | New surface | Behavior |
|---|---|---|
| Add `ActionGateClient` — submit `(proposed_action, evidence)` → 6-outcome verdict + token; execute only with a minted token | `actiongate_client=` ctor param, default None | When set, final authorization delegates to ActionGate; the framework's pre-screen becomes evidence. When None, legacy local gateway path (dev/mock) unchanged. |
| Emit framework risk/uncertainty (`ToolRiskClassifier`, raw-entropy, confidence-risk-gap) as ActionGate evidence | evidence emitter in `prescreen/` | Evidence "can only raise scrutiny" — matches ActionGate's contract exactly (`ACTIONGATE_VC_BRIEF.md`) |
| Add `ContextMinimizationClient` — optional pre-read compression | `context_min_client=` ctor param, default None | When set, context is compressed before the LLM reads; decision-invariant by construction |
| Add an agent principal to the proposal so ActionGate can bind agent identity | `agent_identity=` | Feeds ActionGate's caller/identity binding |
| Bind authoritative human approval to ActionGate's quorum; keep AF approval as routing/UX | approval bridge | AF `approval_workflow` becomes the UX/record; ActionGate owns the quorum decision |

**Compatibility:** Additive. An embedder that passes none of the new params runs exactly as today. **FACT-anchored safety:** because ActionGate evidence can only *raise* scrutiny, opting in can never make an agent *more* permissive than the framework alone — a monotonic, safe migration.

**Constraint honored:** these are *new clients in the framework calling ActionGate/Context-Min interfaces*. They do **not** modify ActionGate, ACP, or Context Minimization (per the milestone constraints). If those subsystems lack a network transport today (FACT: ActionGate transport is in-process/planned), the client targets the in-process reference until a transport ships.

---

## Stage 3 — Build the agent-runtime capability gaps (additive, V2-defining)

The capabilities that separate a single-agent library from an agent runtime platform (Part 5, bucket 3).

| Capability | Action | Compatibility |
|---|---|---|
| Agent identity + registry | New `runtime/registry` (register agents, resolve principals) | Additive; single-agent embedders ignore it |
| Capability registry | Extend the existing tool registry to agent capabilities | Additive |
| Multi-agent coordination | Opt-in coordination layer (handoff, shared memory scoping) — the explicit README gap | Additive; off by default |
| Lifecycle + checkpointing | Durable run state + resumable checkpoints (replaces the overstated "replayable trace") | Additive |
| Observability export | OTel exporter alongside in-memory tracing | Additive; in-memory path unchanged |
| Activate dormant primitives | Wire `rate_limiter`, `safety_bounds`, `readiness` cooldown, `proactive_scheduler.confidence_gate` | Additive/fixes |

**Compatibility:** Additive throughout.

---

## Stage 4 — Rename & repackage (product, not code)

| Action | Detail |
|---|---|
| Rename product to **Agent Runtime ("Proposer", codename Sentinel)** | Part 9 |
| Reserve "AI Control Plane" for the ACP stack; rename framework `policy_control_plane` → "agent behavior policy surface" | resolve the 4-way "control plane" collision |
| Publish the framework↔control-plane boundary contract as the canonical integration doc | Part 7 boundary |

---

## What is reused unchanged (compatibility summary)

**FACT-grounded — no code change required for:**
- The entire reasoning tier (`goal_decomposition`, `reflective_loop`, `reasoning_workflows`, `adaptive_prompts`, `local_critic`, `coherence_tracker` minus the one constant).
- Memory (`memory_store`, `memory_retention`).
- Agent-behavior policy (`policy_bundle`, `domain_policy`, `adaptive_policy`, `policy_simulation`, `policy_replay`).
- Tool registry + risk taxonomy (`ToolSpec`, `ToolCatalog`, `ToolRiskClassifier`).
- Validated signals (`raw_entropy_adapter`, `confidence_risk_gap`).
- Runtime plumbing (streaming events, cancellation, structured output, tracing scaffolding, token/duration budgets).
- The public `AgenticLLMWrapper` API and the ~120 exported symbols.

**Changes are concentrated in:** the *authorization authority* (moves to ActionGate via evidence), the *falsified signal apparatus* (removed/demoted), and *new opt-in seams*. The reasoning, memory, and policy value that defines the product is preserved intact.

---

## Sequencing rationale (INTERPRETATION)

Stage 0 first because the docs currently overstate the product and no architecture decision should rest on contested claims. Stage 1 before Stage 2 because you cannot cleanly delegate to ActionGate while two internal PDPs disagree. Stage 2 before Stage 3 because the control-plane boundary defines *what the runtime no longer has to build*, which shrinks Stage 3. Stage 4 last because names should follow the architecture, not lead it. Every stage is independently shippable and backward-compatible; the migration can pause after any stage with a coherent product.
