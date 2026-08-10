# ADR — Architectural Placement of the Model Selection Policy

*Architecture Decision Record. Status: **Accepted (provisional)**. Date: July 2026. This ADR
resolves the placement inconsistency flagged in `WHY_ENTERPRISE_AI_NEEDS_A_RUNTIME_PLATFORM.md`
(Appendix D). It changes no production code, no evidence/maturity/benchmark claim, and does **not**
add an eleventh canonical platform module. Every factual claim is traceable to a repository source
cited inline.*

> **Terminology reconciliation (2026-08-01).** Per
> [`docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md`](docs/architecture/ADR_UGENCE_DECISION_GOVERNANCE_TERMINOLOGY_AND_BOUNDARIES.md),
> "AI Control Plane" now denotes **only** the optional, bypassable administration & coordination
> component. Where this ADR says Model Selection is "provisionally owned by the AI Control Plane,"
> read that as the **Governance Services Layer** (the governance neighborhood that governs the AI
> interaction boundary). This accepted ADR's argument is otherwise unchanged; no code, API, or
> maturity claim is modified.

---

## Context

The canonical Ugence platform taxonomy (`UGENCE_PLATFORM_OVERVIEW.md`) defines **exactly ten
components** across three layers (Specialized AI Systems, AI Control Plane, AI Infrastructure). The
category paper (`WHY_ENTERPRISE_AI_NEEDS_A_RUNTIME_PLATFORM.md`) lists *policy-aware model selection*
as a required capability of the missing runtime layer, but **no** canonical component owns it, and
the paper correctly flags this as unresolved (its Appendix D, item 1).

Model-selection behavior does exist in the repository, but as **research-stage** work outside the
canonical taxonomy:

- **ExecutionGate** (`execution_gate/gate.py`, `docs/execution_eligibility/`) — a fail-closed
  *eligibility* gate ("can this provider-model-request tuple execute?").
- **ModelPolicy** (`execution_gate/policy.py`, `model_selection_experiment/policy.py`) — a
  *selection* function that ranks the eligible set ("which eligible model should be selected?").
- Supporting experiments and a (credential-blocked) real-model shadow pilot
  (`model_selection_experiment/`, `model_selection_pilot/`), and a unified control-plane study
  (`control_plane/`, `control_plane_shadow/`).

No canonical component implements model selection implicitly: Hybrid LLM is a reasoning substrate (a
model, not a selector); the LLM Steering Controller frames *how* a chosen model generates; the Agent
Runtime proposes actions but does not choose the model. The gap is real, and the question is where
model selection belongs — a service, a subsystem, a policy engine, or a future product — and which
layer owns it.

---

## Decision drivers

- **Separation of responsibilities.** Model selection answers "which model may attempt this request";
  it must not absorb assertion truth (TAP), action authorization (ActionGate), physical/live
  clearance (ACP), answer framing (Steering), or capacity allocation (Cloud Scaling Controller).
- **Avoidance of taxonomy inflation.** The ten-component taxonomy is a deliberate, load-bearing
  commitment across three platform documents; adding an eleventh module casually would dilute it.
- **Policy ownership.** Selection is governed by *customer-owned* policy (approved providers,
  residency, privacy, cost/latency ceilings), not by a model provider — a governance concern.
- **Customer configuration.** Enterprises configure the eligibility and objective policy; the
  component must be a configurable policy surface, not a fixed algorithm.
- **Model-provider independence.** Selection is explicitly model-agnostic and provider-neutral
  (`EXECUTIONGATE_MODELPOLICY_CONTRACT.md`: reason codes, not raw provider strings).
- **Interaction with the other components.** It runs **before** reasoning and feeds the runtime; TAP,
  ActionGate, ACP, and Steering all run **on or after** a chosen model's output. It is temporally and
  logically *upstream* of the existing control-plane components.
- **Evidence and maturity status.** The capability is synthetic-evaluated and shadow-blocked (see
  *Maturity*), which itself argues against promoting it to a first-class product module today.
- **The repository's own product-framing verdict.** `model_selection_experiment/ARCHITECTURE_NOTE.md`
  (Q3) concludes: **not a standalone AI Orchestrator**; primary framing is a **governance capability
  — "the pre-reasoning analogue of ActionGate — with model-selection optimization layered on top."**
  This is direct repository evidence for a *governance* (control-plane-affiliated), not
  *orchestration*, placement.

---

## Options considered

### Option 1 — Eleventh standalone product module
- **Benefits:** first-class visibility; a clean home for the capability; easy to sell as "smart
  routing."
- **Architectural problems:** inflates a deliberate ten-component taxonomy; model selection is a
  *decision function*, not an execution engine — the repo's own note rejects the "AI Orchestrator"
  framing (`ARCHITECTURE_NOTE.md` Q3); it would sit awkwardly beside four peers that all govern a
  model's *output*, while it governs *model admission*.
- **Commercial implications:** risks over-claiming a synthetic, shadow-blocked capability as a
  shipped product.
- **Maturity implications:** would force a product-module maturity label onto research-stage work —
  disallowed by the honesty discipline.

### Option 2 — Subsystem of Agent Runtime
- **Benefits:** the Agent Runtime is the natural caller; co-location is convenient.
- **Architectural problems:** binds a *cross-cutting* policy to *one* runtime (digital), when
  selection should serve any caller (Autonomous Runtime, direct API, other frameworks); it would put
  the model-selecting logic *inside* the same trust boundary as the proposer — the exact coupling the
  platform avoids elsewhere.
- **Commercial implications:** hides a reusable governance capability inside one product.
- **Maturity implications:** conflates Agent Runtime maturity (built, real-model-blocked) with
  model-selection maturity (synthetic) — two different evidence states.

### Option 3 — Subsystem of the AI Control Plane (a numbered fifth control-plane component)
- **Benefits:** correct governance neighborhood; the repo frames it as the "pre-reasoning analogue of
  ActionGate."
- **Architectural problems:** the canonical AI Control Plane governs the *interaction boundary of an
  existing model's output* (what enters reasoning, what is asserted, what acts, whether execution is
  safe). Model selection happens **before a model exists for the request** — a different temporal
  point. Making it a fifth *numbered* control-plane component still inflates the taxonomy (ten→eleven)
  and slightly stretches the layer's stated definition.
- **Commercial implications:** cleaner than Option 1 but still a taxonomy change.
- **Maturity implications:** same over-labeling risk as Option 1.

### Option 4 — Cross-cutting platform policy service (provisionally owned by the AI Control Plane)
- **Benefits:** matches what it *is* — a configurable, customer-owned, provider-neutral **policy
  decision service** that runs upstream of reasoning and feeds every runtime; preserves the
  ten-component taxonomy unchanged; sits in the governance neighborhood the repo's own note assigns
  it ("pre-reasoning analogue of ActionGate") without pretending it is a fifth boundary-governing
  component; keeps model-selection *policy* separate from any one runtime's *execution*.
- **Architectural problems:** "cross-cutting service" is a less crisp slot than a numbered module;
  requires discipline to keep it from accreting responsibilities that belong to TAP/ActionGate/ACP.
- **Commercial implications:** honest — describable as a capability the platform provides without
  claiming a shipped standalone product.
- **Maturity implications:** allows a *service/capability* maturity statement distinct from the ten
  modules' labels — exactly what the evidence supports.

### Option 5 — Research capability only, excluded from the canonical architecture
- **Benefits:** most conservative; zero taxonomy or positioning change.
- **Architectural problems:** the category paper *requires* the capability to describe the missing
  layer; excluding it leaves a named gap in the architecture argument; and the experiment shows
  measurable value (regret 0.016 vs 0.055 best simple baseline — `ARCHITECTURE_NOTE.md` Q1), so
  "excluded" understates it.
- **Commercial implications:** under-claims a real, if immature, differentiator.
- **Maturity implications:** accurate on maturity but architecturally incomplete.

---

## Decision

**Adopt Option 4: the Model Selection Policy is a cross-cutting platform policy service,
provisionally owned by the AI Control Plane, and is NOT counted as an eleventh canonical product
module.**

Rationale, traceable to repository evidence:

1. **It is a policy decision function, not an execution engine.** `ARCHITECTURE_NOTE.md` (Q3) rejects
   the standalone-orchestrator framing explicitly.
2. **It is a governance capability in the control-plane family** — "the pre-reasoning analogue of
   ActionGate" (`ARCHITECTURE_NOTE.md` Q3) — which is why the AI Control Plane is the natural
   provisional owner, without making it a fifth boundary-governing component (it governs *model
   admission*, upstream of the boundary the four control-plane components govern).
3. **It is cross-cutting.** The ExecutionGate↔ModelPolicy contract
   (`EXECUTIONGATE_MODELPOLICY_CONTRACT.md`) is model-agnostic and provider-neutral and is designed to
   feed *any* runtime, not one.
4. **The ten-component taxonomy is preserved.** No module is added, renamed, or removed.

"Provisional" is deliberate: the ownership is affirmed as AI Control Plane for now, with a defined
promotion path (see *Consequences*) should real-provider evidence later justify first-class module
status.

---

## Consequences

- **Diagrams.** Model Selection Policy appears as a **cross-cutting policy service** at the front of
  the governed loop (upstream of reasoning), drawn as an annotation/side-band, **not** as one of the
  ten numbered component boxes. See the *Canonical placement diagram* below.
- **The ten-module taxonomy does not change.** `UGENCE_PLATFORM_OVERVIEW.md` still enumerates ten
  components; this ADR adds a clarifying note, not a component.
- **Product descriptions.** It may be described as a **platform capability / policy service**, with
  its maturity stated, in technical architecture and (carefully qualified) strategic materials. It is
  **not** listed as a numbered product module in the pitchbook or as a shipped product.
- **Maturity label.** It receives a **service-level maturity statement** (see *Maturity*), explicitly
  distinct from the ten modules' labels — not a product-module maturity claim.
- **Customer-facing materials.** See the *Recommendation* section at the end; in short: technical
  architecture and confidential design **yes**; pitchbook and customer proposals **only as a
  qualified capability, not a shipped module**, and never with proprietary thresholds/weights.
- **Future promotion.** Promotion to an eleventh canonical module (or a numbered control-plane
  component) would require: (a) real-provider integration beyond synthetic/shadow; (b) a calibrated
  production-routing result on non-synthetic data; (c) a documented owner and interface parity with
  the existing modules; and (d) an explicit taxonomy amendment ADR superseding this one. Until all
  hold, it remains a cross-cutting service.

---

## Responsibility boundary

Owner column uses canonical component names. "MSP" = Model Selection Policy (the cross-cutting
service decided here). Inputs/Outputs reflect the repository contract
(`EXECUTIONGATE_MODELPOLICY_CONTRACT.md`, `REQUEST_ENVELOPE_SPEC.md`) and are not invented.

| Concern | Owner | Inputs | Output | Explicit non-responsibilities |
|---|---|---|---|---|
| Request normalization | RequestNormalizer / PolicyContext (control-plane research) | raw request | normalized envelope (task, risk class, constraints, pinned versions) | does not select a model; does not judge content |
| Task classification | RequestNormalizer (upstream of MSP) | normalized request | task type + required capabilities | not a truth or action judgment |
| Risk profiling | PolicyContext (upstream of MSP) | request + enterprise policy | risk class, residency/privacy requirements | does not decide model; does not authorize action |
| Eligibility filtering | **ExecutionGate** ("can execute") | candidates + verified operational/policy facts + evidence(TTL) | `EligibilityDecision` per candidate (ELIGIBLE/INELIGIBLE/CONDITIONAL/INDETERMINATE) | **never ranks or picks**; never interprets raw provider errors |
| Capability estimation | Executable Registry + MSP (quality prior) | registry metadata, telemetry, bounded advisory prior | capability/quality estimate per eligible candidate | does not verify the model's *answer* is true |
| Cost / latency estimation | MSP (from registry/telemetry) | declared prices, observed latency/health | expected cost & latency per candidate | not a billing system; not capacity allocation |
| **Selection** | **MSP (this service)** | ExecutionGate eligible set + capability/cost/latency estimates + customer objective policy | `selected model \| null`, ranked utilities, `abstained`, reason | **never selects INELIGIBLE/INDETERMINATE**; never verifies assertions or authorizes actions |
| Response evaluation (sufficiency) | MSP feedback (telemetry) / metrics | post-response outcome signals | prospective quality/telemetry update (future requests) | does not rewrite the in-flight decision; not assertion truth |
| Escalation / abstain / decompose | MSP (fail-fast) | empty eligible+conditional pool, or unmet requirements | abstain + reason (→ human review / decompose upstream) | does not itself perform human review or action |
| Assertion verification | **TAP** | model output + evidence | validate / qualify / abstain | **not MSP** — MSP has no authority over assertion truth |
| Action authorization | **ActionGate** | exact proposed action (CER), hashed | allow / deny / approve / escalate | **not MSP** — MSP does not authorize actions |
| Physical / live clearance | **ACP** | proposed action + live safety state | clear / hold | **not MSP** |
| Infrastructure placement | **Cloud Scaling Controller** / infrastructure | authorized workload | capacity, scaling | **not MSP** — MSP does not allocate capacity |

MSP owns exactly one decision — *which eligible model should attempt the request* — and abstains when
none qualifies. Everything to the right of selection (assert, act, clear, place) is owned elsewhere.

---

## Canonical placement diagram

Model Selection Policy is a cross-cutting **policy service** at the front of the governed loop, not a
numbered module. The ten-component taxonomy is unchanged.

```
   Application / Agent request
            │
            ▼
   ┌───────────────────────────────────────────────┐
   │  MODEL SELECTION POLICY  (cross-cutting        │  ── consumes ──▶  • Customer policy (approved providers, residency, privacy)
   │  policy service; provisionally AI Control      │                  • Executable model-capability registry
   │  Plane; NOT an 11th module; research-stage)    │                  • Cost / latency / health telemetry
   │   ├─ ExecutionGate: eligibility (can execute)  │                  • Risk & privacy requirements (per request)
   │   └─ ModelPolicy:   selection (should execute) │
   └───────────────────────────────────────────────┘
            │  selected eligible model  (or ABSTAIN → human review / decompose)
            ▼
      Selected model  (reasoning / generation)
            │
        ┌───┴───────────────────────────────┐
        ▼                                    ▼
   Assertion output → TAP            Action proposal → ActionGate → ACP
   (validate/qualify/abstain)        (authorize exact action)   (clear vs live safety)
        │                                    │
        └───────────────┬────────────────────┘
                        ▼
             Runtime execution (Agent / Autonomous Runtime)
                        │
                        ▼
             Infrastructure (KVPro · Cloud Scaling Controller — operate, never govern)
                        │
                        ▼
             Outcome & evidence → application  (and prospective telemetry → MSP, future requests only)
```

**Sufficiency is predicted before invocation, verified after.** MSP *predicts* that a chosen model
will meet quality/risk/confidence requirements **before** the model is invoked; downstream evaluation
(TAP for assertions; post-response telemetry for routing) *verifies actual sufficiency* **afterward**
and feeds it forward to future requests only. The two are distinct: prediction is MSP's job,
verification is not.

---

## Policy definition vs. implementation

### Policy objective (intended)
Choose the least-cost eligible model expected to meet quality, risk, and confidence requirements.

### Conceptual formalization (intended, not necessarily implemented)
```
m* = argmin ExpectedCost(m)      subject to      Q̂(m,x) ≥ Q_min(x),
                                                 R̂(m,x) ≤ R_max(x),
                                                 Ĉ(m,x) ≥ C_min(x)
```

### What the code actually computes (repository evidence — do not conflate with the above)
The current implementation is **NOT** this constrained optimization. It is a **two-stage
eligibility-gate + weighted-utility-scoring** mechanism:

1. **Stage A — hard eligibility filter** (`execution_gate/gate.py`, `model_selection_experiment/
   policy.py:hard_filter`). Enforces, as **hard constraints**: approved providers, privacy tier,
   residency/on-prem, required modality/tools/structured output, declared context, a **hard cost
   ceiling** (`max_cost`) and **hard latency SLA** (`max_latency_ms`) where set, and a
   **reliability floor**; unknown/stale critical evidence → INDETERMINATE (fail-closed). This
   realizes `R̂ ≤ R_max` and hard capability/policy constraints.
2. **Stage B — weighted utility scoring** (`execution_gate/policy.py:select`,
   `model_selection_experiment/policy.py:score`). Picks `argmax` of a **soft weighted sum**:
   `U = w_quality·Q̂ − w_cost·(cost/cost_ref) − w_latency·(latency/lat_ref)`, with a
   deterministic tie-break by model id and a penalty ranking CONDITIONALLY_ELIGIBLE below ELIGIBLE.

**Precise divergence (repository-confirmed):** the quality requirement `Q̂ ≥ Q_min` is **NOT enforced
as a hard constraint**. `acceptable_quality_threshold` is carried on the task and read only by
`metrics.py` (to *score* outcomes) — `policy.py` never reads it. The repo's own
`FALSIFICATION_ASSESSMENT.md` §5 states the quality threshold is "modeled as a **soft target, not a
hard constraint**" and that, if an enterprise needs the quality bar guaranteed, it "should be
promoted to a hard constraint." Likewise, "prefer the least-cost sufficient model" is only
*approximately* realized (cost is a soft penalty, not a lexicographic minimand).

**Classification of the current mechanism:** *hard eligibility filter (deterministic constraint
gate) followed by soft weighted-utility scoring* — **not** constrained cost-minimization, **not**
pure lexicographic selection, **not** a learned router. This ADR does **not** claim the constrained
formula is implemented; it documents the intended objective and the divergent implemented mechanism
side by side, per the honesty constraint.

---

## Maturity

Assigned strictly from repository evidence; no maturity is invented.

| Stage | Present? | Evidence |
|---|---|---|
| Architectural specification | ✅ | `docs/execution_eligibility/EXECUTION_ELIGIBILITY_SPEC.md`, `EXECUTIONGATE_MODELPOLICY_CONTRACT.md`, `ARCHITECTURE_NOTE.md` |
| Prototype selector (runnable code) | ✅ | `execution_gate/`, `model_selection_experiment/policy.py` (deterministic, tested) |
| Synthetic evaluation | ✅ | 37-task deterministic experiment: mean regret **0.016** vs 0.055 best simple baseline, **0% constraint violations**, 100% complete decision records — *conditional on synthetic assumptions* (`ARCHITECTURE_NOTE.md`, `FALSIFICATION_ASSESSMENT.md`) |
| Real-provider integration | ❌ **blocked** | real-model shadow pilot "fully built and one command from running" but **BLOCKED on credentials** (all provider keys empty; Vertex token invalid) — `model_selection_pilot/PILOT_STATUS.md`; live-shadow verdict **LIMITED GO** contingent on retention + access-control decisions — `docs/execution_eligibility/LIVE_SHADOW_GO_NO_GO.md` |
| Calibrated production routing | ❌ | no non-synthetic calibration exists |
| Post-response feedback learning (closed loop) | ⚠️ partial | a **bounded advisory/telemetry prior** exists and helps at cold start (decaying to ~0 as telemetry matures); this is **not** a trained closed-loop routing policy |

**Maturity statement (service-level, distinct from the ten modules):**

> *Model Selection Policy — architecturally specified and prototyped, synthetically evaluated
> (deterministic; conditional on synthetic assumptions); real-provider integration built but
> credential-blocked; no calibrated production routing and no trained closed-loop feedback. Its
> demonstrated value is conditional — it widens with workload/provider heterogeneity, cold start, and
> audit requirements, and narrows toward unnecessary in a stable, homogeneous, one-or-two-provider
> setting (`ARCHITECTURE_NOTE.md` Q1).*

**Not claimed:** a closed-loop production routing policy; real-provider validation; calibrated
routing; universal value.

---

## Unresolved implementation questions

1. **Hard vs. soft quality floor.** Should `acceptable_quality_threshold` be promoted to a hard
   eligibility constraint (as `FALSIFICATION_ASSESSMENT.md` §5 suggests), which would make the code
   match the conceptual `Q̂ ≥ Q_min` formula? This is a *code* change, deferred (this ADR does not
   modify code).
2. **Effective vs. declared context.** The "context trap" (declared 200k / effective 128k) is a
   shared blind spot; effective context should be a *measured* registry field feeding eligibility —
   currently unexercised (`FALSIFICATION_ASSESSMENT.md` §5).
3. **Confidence estimator `Ĉ(m,x)`.** The conceptual `C_min` constraint presumes a per-request
   confidence estimator; the repo has a bounded advisory prior + reliability floor, not a calibrated
   confidence model. What estimator, if any, should own `Ĉ`?
4. **Escalation/decompose semantics.** Current behavior is *abstain on empty eligible pool*; "decompose"
   and "request human review" are named in the intended policy but not implemented as distinct paths.
5. **Owner of record within the AI Control Plane.** "Provisionally owned by the AI Control Plane" needs
   a named owning interface if/when the control-plane research components are productized.
6. **Real-provider evidence.** All quantitative results are synthetic; the credential-blocked pilot
   must run before any production or calibrated-routing claim.

---

## Documents changed by this ADR

See the companion change list; this ADR restricts changes to: (a) this new file; (b) a resolution
note in `WHY_ENTERPRISE_AI_NEEDS_A_RUNTIME_PLATFORM.md` (Appendix D item 1 and the §6 flag) pointing
to this decision; (c) a small non-normative clarifying note in `UGENCE_PLATFORM_OVERVIEW.md` that the
ten-component taxonomy is unchanged and model selection is a cross-cutting service. No production
code, evidence, maturity, or benchmark claim is modified.

---

## Recommendation — where the capability should appear

| Surface | Include? | How |
|---|---|---|
| **Pitchbook** | Qualified | As a **platform capability** ("policy-aware model selection / eligibility governance"), **not** a numbered module; no proprietary thresholds/weights; state it is research-stage where maturity is implied. |
| **Platform overview** (`UGENCE_PLATFORM_OVERVIEW.md`) | Yes, minimally | A small non-normative note that it is a **cross-cutting policy service** (not an 11th module); taxonomy unchanged. |
| **Customer proposals** | Qualified | Only as a capability with its honest maturity ("architecturally specified, synthetically evaluated, real-provider validation pending"); never as a shipped, production-calibrated router. |
| **Technical architecture** | Yes | Full placement, responsibility boundary, and the eligibility→selection→abstain mechanism (this ADR is the source). |
| **Patent / confidential design** | Yes | Full mechanism, thresholds, weights, and evaluator logic may appear **only** here — never in public-facing materials (per constraints). |

---

*Sources: `UGENCE_PLATFORM_OVERVIEW.md`, `UGENCE_PLATFORM_VALUE_PROPOSITIONS.md`,
`UGENCE_PLATFORM_COST_SAVINGS.md`, `WHY_ENTERPRISE_AI_NEEDS_A_RUNTIME_PLATFORM.md`,
`model_selection_experiment/ARCHITECTURE_NOTE.md`, `model_selection_experiment/FALSIFICATION_ASSESSMENT.md`,
`model_selection_pilot/PILOT_STATUS.md`, `docs/execution_eligibility/EXECUTIONGATE_MODELPOLICY_CONTRACT.md`,
`docs/execution_eligibility/LIVE_SHADOW_GO_NO_GO.md`, `execution_gate/policy.py`, `model_selection_experiment/policy.py`.
No production code, benchmark result, or evidence/maturity claim was modified in producing this ADR.*
