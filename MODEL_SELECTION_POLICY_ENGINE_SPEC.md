# Model Selection Policy Engine — Specification

**Ugence Labs | The Governed AI Platform**
*The decision framework that determines, deterministically and explainably, which LLM should serve a given task.*
*Version 1.0 — July 2026*

> **What this document is.** A **policy specification**, not production code and not an orchestrator.
> It defines the measurable criteria, data structures, decision procedure, and governance separation
> that a future execution engine would run. The deliverable is the *decision framework*; the engine
> that executes it is downstream and, as this document argues, comparatively commoditized.
>
> **What this document is not.** It is not a ranking of today's models ("which model is best?"). That
> question is unanswerable in the abstract and obsolete within weeks. This specification answers the
> durable question: **"what measurable criteria determine which model should be chosen for a given task
> under given constraints?"** The policy is model-agnostic and must evaluate any present or future LLM
> without modification to its structure.
>
> **Reading discipline.** This document is written in the same falsification-first posture as the rest
> of the Ugence portfolio. **Section 1 tries to kill the idea before building it.** Every claim about
> competitive gaps is stated as a testable difference, not a marketing assertion. Where a mechanism is
> a specification rather than a validated result, it is labeled **[SPEC]**; where it is an empirical
> methodology to be run, **[METHOD]**; where it is an architectural argument, **[ARGUMENT]**.

---

## Table of contents

1. Falsification first — does this layer need to exist?
2. Deliverable 1 — Model Selection Policy Specification
3. Deliverable 2 — Decision dimensions, and hard constraints vs. preferences
4. Deliverable 3 — Task Taxonomy
5. Deliverable 4 — Capability Registry Schema
6. Deliverable 5 — Decision Pipeline
7. Deliverable 6 — Decision Explanation Format
8. Deliverable 7 — Benchmark Methodology
9. Deliverable 8 — Failure Recovery Policy
10. Deliverable 9 — Adaptive Learning Design
11. Deliverable 10 — Enterprise Governance Layer
12. Product recommendation — is the *policy* the product?
13. Appendix A — Worked example
14. Appendix B — Competitive differentiation matrix

---

## 1. Falsification first — does this layer need to exist?

The portfolio's discipline is to attempt to falsify a layer's necessity before asserting its value. A
Model Selection Policy Engine is only worth specifying if enterprises genuinely cannot get this
behavior for free from models, gateways, or existing routers. Four falsification attempts follow.

### 1.1 "Frontier models are converging — just always call the best one."

**The attack.** Capability is commoditizing and prices are collapsing. Pick the single strongest
general model and route everything to it; selection is a non-problem.

**Why it fails.** "Best" is not a scalar and not task-invariant. A model that leads a reasoning
benchmark can be the *wrong* choice for a 200-page extraction job (context and cost), a
sub-200 ms classification (latency), a regulated-data workload (residency), or a strict-JSON tool
step (structured-output reliability). More decisively, three of the elimination criteria have nothing
to do with capability at all:

- **Cost at scale.** A 40× price gap between a frontier reasoning model and an adequate small model,
  multiplied by millions of enterprise calls, is the difference between a viable and an unviable
  product line. "Always best" is an economic non-starter for high-volume, low-criticality tasks.
- **Latency.** Interactive workloads have SLAs the strongest model cannot meet.
- **Compliance and privacy.** A model may be *categorically forbidden* for a workload regardless of
  quality — data residency, no-training contractual clauses, approved-provider lists. No amount of
  capability overrides a legal prohibition.

"Always best" survives only in the narrow world of low-volume, unconstrained, non-regulated tasks.
Enterprises do not live there. **Falsification fails.**

### 1.2 "Routers already exist — this is solved plumbing."

**The attack.** LiteLLM, Portkey, OpenRouter, Kong/Cloudflare AI gateways, and learned routers
(Martian, NotDiamond, RouteLLM) already choose models. Ugence would reinvent a solved component.

**Why it partially lands — and where it fails.** These tools are real and cover parts of the surface,
so honesty requires precision about the gap (full matrix in Appendix B):

- **Gateways/proxies (LiteLLM, Portkey, OpenRouter, Kong AI Gateway, Cloudflare AI Gateway)** are
  *plumbing*: unified APIs, key management, fallback chains, load-balancing, and cost logging. Their
  "routing" is **operator-authored configuration** — static rules and retry lists. They do not
  *predict task fit*, do not model compliance as first-class elimination, and do not emit a
  per-decision explanation with constraint provenance.
- **Learned routers (Martian, NotDiamond, RouteLLM, and the research line on LLM routing)** *do*
  predict quality/cost trade-offs, and predict them well. But they are **optimizers, not governance**:
  they are typically trained end-to-end on preference/quality data, output a choice without an
  auditable elimination ledger, treat compliance as an out-of-band filter rather than a first-class
  constraint plane, and are difficult to explain to a regulator per decision. They answer "which is
  cheapest-good-enough?" not "which is *permitted, suitable, and defensible*, and why was every
  alternative rejected?"
- **Cloud model catalogs (Bedrock, Azure AI Foundry, Vertex)** offer guardrails and multi-model
  access but are **provider-scoped** and do not provide a portable, cross-vendor, declarative selection
  *policy artifact* an enterprise owns and audits.

The unoccupied space is a **declarative, auditable, constraint-first selection policy** — separable
from execution, explainable per decision, with an architecturally enforced split between technical
optimization and enterprise governance. That is precisely the "missing middle rebuilt as in-house
glue" pattern the platform overview describes. **Falsification fails, but narrows the claim:** the
novelty is *governed, explainable, deterministic selection*, not "smart routing." This document must
earn that specific ground and concede the rest.

### 1.3 "It's just a weighted score — a formula, not a product."

**The attack.** Strip away the prose and it is `argmax` over a weighted sum. Formulas are not products.

**Why it fails.** The scoring function is the *least* defensible part and is deliberately kept simple
and transparent (Section 6.8). The durable assets are everything the formula consumes and produces:
the **constraint algebra** that turns compliance into deterministic elimination; the **registry
schema** that separates declared vs. measured vs. observed values with provenance; the **explanation
contract** that makes every decision auditable; and the **closed-loop telemetry** that keeps the
scores calibrated over time. A competitor can copy the `argmax` in an afternoon and still not have a
governed, self-correcting, auditable selection layer. **Falsification fails.**

### 1.4 "Models will self-route."

**The attack.** A capable model can be asked "should another model handle this?" and route itself.

**Why it fails.** A model cannot evaluate models it is not; cannot see cost, live latency, deployment
location, or contractual terms; cannot be pinned to a deterministic, reproducible decision for audit;
and has an obvious incentive-and-blindspot problem when asked to judge its own suitability. Selection
must be an **external, deterministic, auditable function over telemetry and policy** — exactly what a
model is not. **Falsification fails.**

### 1.5 Honest residual risk

One scenario compresses the value: if frontier capability converges *and* prices collapse *and*
most enterprise volume is unconstrained, the *optimization* value of selection shrinks toward zero.
But note what survives even then — **compliance, privacy, residency, approved-provider governance,
and auditability do not commoditize**; they intensify with regulation. So the policy's floor value is
the **governance** portion, which is durable regardless of model convergence. The optimization portion
is the upside. This is the correct risk-adjusted framing: build the governance spine first.

**Conclusion of Section 1.** The Model Selection Policy is a meaningful architectural layer that
enterprises currently rebuild as in-house glue. Its defensible, non-commodity core is *governed,
explainable, deterministic selection* — not raw routing. The rest of this document specifies that core.

---

## 2. Deliverable 1 — Model Selection Policy Specification

### 2.1 The policy as a pure function

The policy is defined as a **deterministic pure function** over an explicit, versioned snapshot:

```
select : (Request, ConstraintSet, RegistrySnapshot, PolicyConfig) → Decision
```

- **Determinism.** Given identical inputs — including a pinned `RegistrySnapshot` and `PolicyConfig`
  version — the function returns an identical `Decision`, including identical ranking and explanation.
  This is a hard requirement, not an aspiration: audit, reproducibility, and regulatory defensibility
  depend on it. All non-determinism (live health, telemetry) is captured *as an input snapshot*, never
  read implicitly at evaluation time.
- **Purity.** The function performs no I/O. Data collection (telemetry, health, pricing) happens
  *before* evaluation and is frozen into the snapshot. This is what makes a decision replayable months
  later against the exact state that produced it.
- **Policy is data.** The `PolicyConfig` (weights, thresholds, constraint definitions, governance
  rules) is a **declarative, versioned artifact** — not code. The engine that evaluates it is generic.
  This separation is the central design commitment: *the policy is the product; the engine is the
  interpreter.*

### 2.2 Inputs and outputs

| Object | Contents |
|---|---|
| `Request` | Task vector (family + task + facets, Section 4), payload metadata (token estimate, modalities present, required output schema), tenant/customer identity, invocation context (interactive vs. batch). |
| `ConstraintSet` | Resolved hard constraints for this request: privacy tier, residency, approved providers, required modalities, max context, compliance regime, budget ceiling, latency SLA. Derived from tenant governance + request facets. |
| `RegistrySnapshot` | Pinned, versioned view of every candidate model: declared capabilities, measured benchmarks, observed telemetry, live health/price at snapshot time (Section 5). |
| `PolicyConfig` | Versioned weights, tier thresholds, scoring function, tie-break rules, governance overlay, learning bounds. |
| `Decision` | Selected model, ranked candidate list, **fallback chain**, per-model elimination ledger, per-dimension score contributions, confidence estimate, and a rendered explanation (Section 7). |

### 2.3 Core invariants

1. **Constraint supremacy.** No preference score can promote a model that fails any hard constraint.
   Elimination is absolute and precedes scoring.
2. **Governance precedence.** Enterprise-governance constraints outrank capability constraints, which
   outrank optimization scores (Section 11).
3. **Explainability totality.** Every model that entered the candidate pool exits with a recorded
   status — selected, ranked-but-not-selected, or eliminated-with-reason. There are no silent drops.
4. **Snapshot pinning.** Every `Decision` records the `RegistrySnapshot` hash and `PolicyConfig`
   version, so it is exactly reproducible.
5. **No empty success.** If the eligible set is empty after constraint filtering, the policy does not
   invent a choice; it returns a typed escalation outcome (Section 9.6).

### 2.4 Why "policy" and "engine" are separated

The engine is a stateless interpreter: load snapshot, evaluate policy, emit decision. All the durable
intellectual property — the constraint algebra, the registry schema, the scoring philosophy, the
governance split, the explanation contract, the learning bounds — lives in the **policy artifact and
the schemas it references**, which are versioned and portable across engines. This is the same
architectural move the platform makes with ActionGate: *governance is a declarative layer in front of
execution, not a feature buried inside it.*

---

## 3. Deliverable 2 — Decision dimensions, and hard constraints vs. preferences

### 3.1 The full dimension catalog

The task's starter list is necessary but not sufficient. Dimensions are grouped into seven families;
new dimensions beyond the brief are marked **[+]**.

**A. Capability / task-quality** (how well it does the *work*)
- reasoning (multi-step, mathematical, deductive)
- coding (generation, editing, repository-scale comprehension)
- extraction (entities, fields, tables from documents)
- summarization quality (faithfulness + compression)
- classification accuracy
- translation quality (per language pair)
- creative/authoring quality
- planning / decomposition
- long-context comprehension **[+]** (distinct from *advertised* context length — see B)
- instruction-following fidelity **[+]**

**B. Interface / functional** (what it can *do*, structurally)
- supported input modalities (text, image, audio, video, PDF-native)
- supported output modalities
- maximum context length (advertised)
- **effective context length [+]** — usable context before quality decays ("context rot"), measured, not declared
- structured-output reliability (valid JSON / schema-adherence rate)
- constrained decoding support **[+]** (grammar / JSON-schema-enforced generation)
- tool/function calling (support, arity, parallel calls, reliability)
- streaming support
- determinism controls **[+]** (temperature-0 stability, seed support)
- confidence-signal availability **[+]** (are logprobs / token confidences exposed? required for calibration and abstain logic)

**C. Operational** (how it behaves in *production*)
- latency: time-to-first-token, and tokens/second
- throughput / max concurrency
- availability / SLA
- rate limits and quota
- **version stability [+]** — does the provider silently update the weights behind a name? Is a pinned/frozen version available? (Critical for regulated reproducibility.)

**D. Economic**
- input token cost, output token cost
- cache-read / cache-write pricing **[+]**
- minimum billing / request floor **[+]**
- amortized fixed cost for self-hosted models **[+]** (a per-token price is misleading for owned GPUs)
- **cost tail / variance [+]** — p95 cost per task, not mean; reasoning models emit unbounded output and mean cost hides blow-ups

**E. Trust / quality-risk**
- hallucination tendency (by task type)
- calibration / confidence quality (does stated/derived confidence track correctness?)
- refusal / over-refusal rate **[+]**
- jailbreak / prompt-injection resistance **[+]**
- bias and fairness characteristics **[+]**
- provider-injected moderation coupling **[+]** (does the provider apply its own filters that may conflict with, or duplicate, enterprise policy?)

**F. Governance / compliance** (mostly hard constraints — Section 3.2)
- privacy tier / data-handling guarantees
- deployment location / data residency
- retention & training-use policy (no-train contractual clauses)
- certifications (SOC 2, HIPAA, ISO 27001, FedRAMP, GDPR posture)
- approved-provider / customer-allowed list
- regulatory regime applicability (EU AI Act risk class, sector rules)

**G. Empirical / historical** (learned from *our own* production)
- historical task-success rate, segmented by task family
- retry frequency
- verification-failure rate (how often downstream validation rejects the output)
- human-review / escalation rate
- observed drift (has success on a task type degraded over time?)

**Portfolio-level dimensions** (not per-model; per-*decision-population*) **[+]**
- vendor concentration risk (over-reliance on one provider)
- energy / carbon per task (ESG reporting)
- fine-tunability / adaptability (can we customize this model for a workload?)
- prompt-portability / migration cost (how much rework to move a workload here?)

### 3.2 Hard constraints vs. preferences — the separation rule

The organizing principle: **a dimension is a hard constraint if any value on the wrong side of a
threshold makes the model unusable or impermissible for the task; it is a preference if all remaining
values are acceptable but some are better than others.** Constraints *eliminate*; preferences *rank*.

**Hard constraints (veto — eliminate the model entirely):**

| Constraint | Eliminates when |
|---|---|
| Privacy / data-handling tier | Model's guarantee is below the data's classification. |
| Data residency / deployment location | Model runs outside the required jurisdiction. |
| Approved-provider list | Provider is not on the customer's allow-list. |
| Required modality | Task needs an input/output modality the model lacks. |
| Maximum context | Payload exceeds the model's *effective* (not advertised) context. |
| Compliance regime | Model lacks a certification the workload legally requires. |
| Structured-output requirement | Task requires guaranteed schema adherence the model cannot provide (when strictness is non-negotiable). |
| Hard budget ceiling | Model's expected cost exceeds an absolute per-task cap. |
| Latency SLA (as a hard bound) | Model's p95 latency exceeds a contractual interactive deadline. |
| Tool-calling requirement | Agentic task needs reliable tool calls the model cannot make. |

**Preferences (scored — rank the survivors):**
task-fit quality (per family), incremental cost, latency headroom, throughput, structured-output
*reliability* (when strictness is a preference not a floor), hallucination risk, calibration quality,
historical success, retry rate, operational reliability, vendor-diversity contribution, energy.

**The pivotal design nuance.** Some dimensions appear on *both* lists depending on the task's facets.
Latency is a hard constraint for an interactive workload and a mere preference for an overnight batch
job. Structured output is a floor for a strict tool step and a preference for a draft. **This is why
constraints are resolved per-request from task facets (Section 4), not fixed globally.** The
constraint/preference split is a *function of the task*, not a static property of the dimension. This
single insight is what most existing routers miss: they hardwire the split.

---

## 4. Deliverable 3 — Task Taxonomy

### 4.1 Flat vs. hierarchical vs. faceted — the decision

A flat list of task types (extraction, reasoning, coding, …) is simple but wrong for three reasons:
it explodes combinatorially (is "legal contract extraction on a scanned PDF, latency-critical" one
category or four?); it hides shared capability requirements; and it forces a choice between too-coarse
buckets and an unmaintainable long tail.

**Recommendation: a two-level hierarchy of *what the task is*, crossed with orthogonal *facets* that
describe *how it must be done*.** Family+task drives **capability weighting**; facets drive
**constraints and operational requirements**. This factorization is the taxonomy's core idea:
capability and constraint are orthogonal axes and must not be collapsed into one flat label.

### 4.2 Task families and tasks (the "what") — vendor-neutral

| Family | Representative tasks |
|---|---|
| **Extraction & Structuring** | field extraction, table extraction, entity/relationship extraction, schema population, document parsing |
| **Comprehension & Summarization** | summarization, question-answering over provided text, semantic search grounding, long-document comprehension |
| **Reasoning & Analysis** | multi-step reasoning, mathematical/quantitative analysis, contract/clause analysis, root-cause analysis, decision support |
| **Generation & Authoring** | drafting, creative generation, report writing, response composition |
| **Transformation** | translation, format conversion, code editing/refactoring, style transfer, redaction |
| **Classification & Routing** | intent classification, categorization, triage, content moderation, sentiment |
| **Conversation & Assistance** | interactive assistant turns, clarification dialogues, guided workflows |
| **Agentic / Tool-using workflows** | tool-calling loops, planning-and-execution, multi-step orchestrated tasks |
| **Multimodal understanding** | image/document understanding, chart/diagram reading, audio transcription+reasoning |
| **Retrieval & Search** | query understanding, reranking, retrieval-grounded answering |

Two levels are sufficient. A third level (e.g. "invoice field extraction" under "field extraction")
is better expressed as a **domain facet** than as a new taxonomy node — otherwise the tree grows
without bound.

### 4.3 Facets (the "how") — orthogonal to family

Each request carries facet values. Facets are the bridge to `ConstraintSet`.

| Facet | Values (examples) | Primarily drives |
|---|---|---|
| Input modality | text / image / audio / video / mixed | constraint (required modality) |
| Output modality | text / structured / image / audio | constraint |
| Criticality / blast radius | informational / advisory / decision-bearing / irreversible | governance weight, human-review, confidence floor |
| Latency class | interactive / near-real-time / batch | constraint or weight on latency |
| Determinism requirement | best-effort / reproducible-required | constraint on version-stability + temperature |
| Context-size class | small / medium / large / extreme | constraint (effective context) |
| Structured-output requirement | none / preferred / strict | constraint vs. preference toggle |
| Autonomy level | suggest-only / human-approved / autonomous | governance, confidence floor |
| Domain | legal / healthcare / finance / general / … | constraint (certifications), quality weighting |
| Data sensitivity | public / internal / confidential / regulated | constraint (privacy tier, residency) |

**Why faceted beats hierarchical alone.** The pair *(family, task)* answers "what capabilities matter
and how should we weight them"; the facet vector answers "what is forbidden and what must be
guaranteed." A learned quality predictor keys off the former; the deterministic constraint filter keys
off the latter. Keeping them orthogonal is what lets the *same* task (say, extraction) route to a
cheap model for public data and a residency-locked model for regulated data **without duplicating the
taxonomy.** This directly implements the Section 3.2 insight that the constraint/preference split is
task-conditional.

---

## 5. Deliverable 4 — Capability Registry Schema

### 5.1 Design principles

1. **Three provenance classes, never conflated.** Every capability value is one of:
   **declared** (vendor spec sheet / documentation), **measured** (our own controlled benchmarks),
   or **observed** (our production telemetry). A declared 1M-token context and a measured effective
   context of 200K are *different fields*, and the policy trusts measured/observed over declared.
2. **Store measurements; derive tiers.** "reasoning tier," "cost tier," "latency tier" are **derived
   views** computed from raw measured values against policy thresholds — not primary storage. Storing
   tiers directly bakes today's buckets into the data and rots. Store the number and the unit; let the
   policy bucket.
3. **Every value carries metadata.** value, unit, `source`, `as_of` timestamp, `confidence`, and
   `method` (how it was obtained). A benchmark score with no date and no method is not admissible.
4. **Model identity is versioned.** A model is `(provider, family, version, deployment)`. "The same
   model name" behind a silently-updated endpoint is a *different* registry entry.

### 5.2 Schema sketch [SPEC]

```yaml
model_entry:
  id: string                      # stable internal id
  identity:
    provider: string              # WHY: approved-provider constraint, concentration risk
    family: string
    version: string               # WHY: reproducibility; silent updates = new entry
    deployment: enum              # saas | vpc | on-prem | self-hosted — WHY: residency + cost model
    endpoint_ref: string

  # ---- DECLARED (vendor) ----
  declared:
    modalities_in:  [enum]        # WHY: required-modality hard constraint
    modalities_out: [enum]
    max_context: int              # WHY: context constraint (upper bound only; trust measured)
    tool_calling: {supported: bool, parallel: bool}   # WHY: agentic-task constraint
    constrained_decoding: bool    # WHY: strict structured-output constraint
    confidence_signals: enum      # none | logprobs | token_conf — WHY: enables calibration + abstain
    version_frozen_available: bool# WHY: determinism/reproducibility constraint

  # ---- MEASURED (our benchmarks) ----
  measured:
    effective_context: {value:int, as_of:date, method:str, confidence:float}  # WHY: real usable context
    capability_scores:            # per task family — WHY: capability match / quality prediction
      extraction:      {value:float, ci:[float,float], as_of:date, method:str}
      reasoning:       {value:float, ...}
      coding:          {value:float, ...}
      summarization:   {value:float, ...}
      # ... one per task family
    structured_output_validity: {value:float, ...}   # WHY: schema-adherence preference/constraint
    hallucination_rate: {value:float, ...}            # WHY: trust scoring
    calibration_error: {value:float, ...}             # WHY: confidence quality, abstain thresholds
    language_quality: {en:float, fr:float, ...}       # WHY: language-support scoring/constraint

  # ---- OBSERVED (our production telemetry) ----
  observed:
    latency: {ttft_p50:ms, ttft_p95:ms, tps_p50:float, as_of:date}  # WHY: latency constraint + scoring
    availability: {rolling_uptime:float, open_incidents:int}         # WHY: health-aware exclusion
    task_success: {by_family: {extraction:float, ...}, as_of:date}   # WHY: historical-success scoring
    retry_rate: {by_family: {...}}                                   # WHY: operational reliability
    verification_failure_rate: {by_family: {...}}                    # WHY: predicts human review
    human_review_rate: {by_family: {...}}
    drift_flags: [ {family, direction, detected_at} ]                # WHY: trigger re-benchmark

  # ---- ECONOMIC ----
  economic:
    price_in_per_mtok: float      # WHY: cost scoring + budget constraint
    price_out_per_mtok: float
    cache_read_per_mtok: float
    request_floor: float
    self_hosted_amortized_per_tok: float   # WHY: owned-GPU cost realism
    cost_p95_per_task: {by_family: {...}}  # WHY: tail-cost, not mean — reasoning blow-ups

  # ---- GOVERNANCE (mostly hard-constraint inputs) ----
  governance:
    privacy_tier: enum            # WHY: privacy hard constraint
    residency: [jurisdiction]     # WHY: data-residency hard constraint
    retention_policy: enum        # WHY: no-train / retention constraint
    trains_on_data: bool
    certifications: [enum]        # soc2 | hipaa | iso27001 | fedramp | ... — WHY: compliance constraint
    contractual_terms_ref: string

  # ---- LIFECYCLE ----
  lifecycle:
    status: enum                  # candidate | active | deprecated | retired
    added_at: date
    last_benchmarked: date        # WHY: staleness → lower confidence
    fine_tunable: bool            # WHY: adaptability dimension
```

### 5.3 Why the three-class split is the schema's whole point

The single most common failure of in-house registries is storing a vendor's advertised number as if it
were ground truth (advertised context, advertised "best-in-class reasoning"). This schema makes the
policy structurally prefer **measured** over **declared** and **observed** over **measured** where they
disagree, and it records *why* every value is trusted (source, method, date, confidence). That is what
makes the downstream explanation defensible: "selected on a **measured** effective-context of 200K,
not the **declared** 1M."

---

## 6. Deliverable 5 — Decision Pipeline

### 6.1 The proposed pipeline is close but under-specified

The starter pipeline (Task → Hard Constraint Filter → Capability Match → Business Policy → Quality
Prediction → Operational Cost → Confidence Estimate → Selection) is directionally right but is missing
five things: an explicit **classification/constraint-resolution** front stage, an **eligibility gate**
(what happens at zero survivors), the treatment of business policy as **both constraint and weight**,
the emission of a **ranked fallback chain** rather than a single winner, and a **decision-record /
explanation** terminal stage. The corrected pipeline:

```
   Request
      │
 (0)  Classification & Constraint Resolution   → task vector + ConstraintSet
      │
 (1)  Registry Snapshot Pin                     → frozen candidate state (determinism)
      │
 (2)  Hard Constraint Filter                    → eliminate; record every rejection + evidence
      │
 (3)  Eligibility Gate ──── empty? ─────────────→ Escalation Policy (§9.6)
      │ (≥1 survivor)
 (4)  Capability Match / Quality Prediction     → predicted task-fit per survivor
      │
 (5)  Enterprise/Governance Overlay             → mandatory/preferred providers, budget, weights (§11)
      │
 (6)  Operational Cost & Availability Scoring    → live price, latency headroom, health, load
      │
 (7)  Risk & Confidence Estimation               → predicted success + uncertainty; abstain gate
      │
 (8)  Aggregation & Selection                    → transparent weighted score; deterministic tie-break
      │
 (9)  Explanation Assembly                        → elimination ledger + score contributions (§7)
      │
 (10) Emit Decision + Ranked Fallback Chain       → winner + ordered alternates + canary hook
```

### 6.2 Stage notes

- **(0) Classification & Constraint Resolution.** Turns a raw request into `(task vector, facets)` and
  resolves facets + tenant governance into a concrete `ConstraintSet`. Classification may itself use a
  small model, but its *output* is data the deterministic pipeline consumes — the pipeline stays pure.
- **(2) Hard Constraint Filter.** Governance constraints evaluated **before** capability constraints,
  so a compliance rejection is never masked by a capability one (precedence, Section 11.3). Every
  eliminated model exits with `{constraint, expected, actual, evidence_ref}`.
- **(3) Eligibility Gate.** A first-class stage. Zero survivors is a *governed outcome*, not an
  exception — it routes to the escalation policy, which may relax a *preference*-derived pseudo-
  constraint, request human approval, or reject with a reason. It never relaxes a true hard constraint.
- **(4)/(7) Quality and Confidence are distinct.** Quality prediction estimates *how good* the output
  will be; confidence estimates *how sure we are of that prediction* (registry staleness, sparse
  telemetry, out-of-distribution task). Low confidence can trigger abstain/human-review even when
  predicted quality is high.
- **(5) Governance overlay is dual-nature.** Some governance is a veto already applied in (2); the
  remainder is *weight modification* (e.g. "prefer the sovereign provider, all else near-equal"),
  applied here as bounded score adjustments — never able to resurrect an eliminated model.
- **(10) Output is a chain, not a point.** The pipeline returns an ordered candidate list so failure
  recovery (Section 9) is a pre-computed fallback, not a re-run under pressure.

### 6.3 Route-time vs. policy-compile-time

Two clocks. **Policy-compile-time** (minutes–hours): benchmarking, tier derivation, weight fitting,
governance changes — heavy, reviewed, versioned. **Route-time** (milliseconds): filter + score + select
against a pre-compiled snapshot — cheap and deterministic. Keeping expensive learning off the
route-time path is what lets selection be both adaptive *and* fast *and* auditable.

---

## 7. Deliverable 6 — Decision Explanation Format

### 7.1 Requirement

Every decision must be explainable as *structured data first*, from which a natural-language rendering
is derived deterministically. "Claude was selected" is not an explanation; "Model C selected because
highest measured coding accuracy among the three residency-eligible models, tool-calling required and
supported, within the 2 s latency SLA, and lowest expected cost; Models A and B eliminated for stated
reasons" is.

### 7.2 The Decision Record schema [SPEC]

```json
{
  "decision_id": "uuid",
  "request_fingerprint": "hash",
  "policy_version": "1.4.2",
  "registry_snapshot": "sha256:...",
  "task": { "family": "coding", "task": "code_edit",
            "facets": { "latency_class": "interactive", "data_sensitivity": "internal" } },
  "resolved_constraints": [
    { "constraint": "residency", "required": "eu", "source": "tenant_governance" },
    { "constraint": "tool_calling", "required": true, "source": "task_facet" },
    { "constraint": "latency_slo_p95_ms", "required": 2000, "source": "task_facet" }
  ],
  "eliminated": [
    { "model": "model_a", "constraint": "max_context",
      "required": "<=180000 effective", "actual": "measured 128000",
      "evidence_ref": "bench:ctx:2026-06" },
    { "model": "model_b", "constraint": "approved_provider",
      "required": "customer_allowlist", "actual": "provider_x not listed",
      "evidence_ref": "gov:allowlist:tenant_42" }
  ],
  "scored": [
    { "model": "model_c", "total": 0.83, "selected": true,
      "contributions": { "capability_coding": 0.34, "cost": 0.19,
                         "latency_headroom": 0.15, "historical_success": 0.15 },
      "confidence": 0.79 },
    { "model": "model_d", "total": 0.71, "selected": false,
      "contributions": { "capability_coding": 0.28, "cost": 0.22, "...": 0.0 },
      "confidence": 0.74 }
  ],
  "selected": "model_c",
  "fallback_chain": ["model_d", "model_c_degraded"],
  "confidence": 0.79,
  "abstained": false,
  "rendered": "Selected Model C. Eliminated Model A (effective context 128K < 180K required); eliminated Model B (provider not on tenant allow-list). Among eligible models, C led on measured coding accuracy, supported required tool-calling, met the 2 s p95 latency SLA, and had the lowest expected cost. Fallback: Model D."
}
```

### 7.3 Properties

- **Total accounting.** Every candidate is either in `eliminated` or `scored`. No silent drops.
- **Evidence links.** Each elimination and each score contribution references the registry field and
  benchmark/telemetry that justified it — the explanation is auditable back to source data.
- **Deterministic rendering.** `rendered` is generated from the structure by template, not by a model,
  so the prose can never disagree with the data. (A model may *polish* phrasing, but the canonical
  record is the structure.)
- **Two audiences, one record.** Machines consume the JSON for monitoring and off-policy evaluation;
  humans (and regulators) read `rendered` and can drill into `contributions`.

---

## 8. Deliverable 7 — Benchmark Methodology

### 8.1 Two distinct measurement problems — do not conflate them

- **Model benchmarking** populates the `measured` registry fields (per-family capability, effective
  context, structured-output validity, calibration, hallucination). Standard eval discipline: held-out
  sets, confidence intervals, dated, method-documented, re-run on drift flags. **[METHOD]**
- **Routing-quality benchmarking** measures the *policy itself* — did it choose well given its
  objective and constraints? This is the metric that matters for *this product*, and it is routinely
  neglected because it is harder. **[METHOD]**

### 8.2 Routing-quality metrics, and which are actually predictive

| Metric | Definition | Predictive value |
|---|---|---|
| **Selection regret** | quality/cost gap between chosen model and the best *eligible* model, measured counterfactually | **High** — the direct objective; the north-star |
| **Constraint-violation rate** | fraction of decisions that breached a hard constraint | **Absolute** — must be ~0; any non-zero is a defect, not a metric to optimize |
| **Successful-completion rate** | task met acceptance criteria without escalation | High (lagging) |
| **Retry rate** | fraction requiring a retry | **High leading indicator** — rises before success falls |
| **Verification-failure rate** | downstream validation rejected the output | **High leading indicator** — predicts human review |
| **Human-review rate** | routed to a human | Medium (also policy-driven, not pure quality) |
| **Blended cost per *successful* task** | total spend ÷ successful tasks (retries included) | High — the honest cost metric; per-call price is misleading |
| **Latency-SLA attainment** | fraction within SLA | High for interactive tiers |
| **Hallucination frequency** | measured on sampled outputs | Medium–High |
| **Business success** | downstream KPI (conversion, resolution) | **Ground truth but lagging and noisy** — validates, does not steer |

**The predictive-vs-vanity distinction.** *Leading* indicators — retry rate, verification-failure
rate, calibration error — move *before* outcomes degrade and are the ones worth alerting on and
learning from. *Lagging* indicators — business success, completion rate — are the validators of record
but too slow and confounded to drive route-time decisions. **Selection regret is the single metric that
most directly scores the policy**; everything else is either a constraint (violation rate → zero) or a
leading proxy for regret.

### 8.3 Counterfactual evaluation — the methodological core [METHOD]

You cannot measure "would Model D have done better?" from production alone, because you only observe
the chosen model. Three techniques, in increasing cost:

1. **Shadow routing.** Run the candidate policy in parallel without serving its choice; compare its
   would-be selections to the live policy on logged outcomes.
2. **Off-policy / logged-bandit estimation.** Use exploration logs and inverse-propensity weighting to
   estimate a new policy's expected reward without deploying it.
3. **Canary / interleaving.** Serve the new policy to a small, bounded traffic slice with guardrails.

**Goodhart warning.** Every metric here is gameable (e.g. minimize cost by always choosing the cheapest
model and absorbing the retry cost elsewhere). Guard by (a) always reporting *blended cost per
successful task*, not per-call price; (b) treating constraint-violation as a hard gate, not a weighted
term; and (c) evaluating on a **held-out task distribution** the policy was not tuned on.

---

## 9. Deliverable 8 — Failure Recovery Policy

Every recovery action is itself a **logged decision with an explanation** — recovery is not an escape
hatch from governance.

### 9.1 Fallback models
The pipeline emits a **ranked fallback chain** (Section 6.2). On failure, advance to the next eligible
candidate — never to a model that failed the original hard-constraint filter. Fallbacks are
pre-computed at route-time, so recovery is a lookup, not a re-derivation under pressure.

### 9.2 Retry logic — typed, not blind
Classify failures before retrying:
- **Transient** (timeout, 5xx, rate-limit): retry *same* model with backoff, up to a per-request retry
  budget; then advance the chain.
- **Semantic** (invalid output, verification failure, refusal): do **not** retry the same model with
  the same prompt — advance to a *different* model in the chain. Repeating a semantic failure on the
  same model is the classic retry-storm anti-pattern.

### 9.3 Verification failures
When downstream validation (schema check, Truth-Assurance-style grounding, or a rule) rejects an
output, treat it as a semantic failure: re-route to the next candidate, and record the verification
failure into `observed.verification_failure_rate` so it feeds learning (Section 10).

### 9.4 Confidence failures
If the confidence estimate (Section 6.2, stage 7) is below the task's floor — floors are higher for
high-criticality facets — the policy **abstains from autonomous action**: escalate to a stronger
model, to human review, or return a typed low-confidence result. Confidence failure is a *governed
outcome*, not an error.

### 9.5 Provider outage
Health-aware exclusion: a model with an open incident or degraded rolling uptime is filtered at
snapshot time (it simply is not in the eligible set). A **circuit breaker** with hysteresis prevents
flapping — a provider must be healthy for a minimum dwell time before re-entering the pool, so a
recovering provider does not cause oscillation.

### 9.6 Empty eligible set / cost-limit exceeded
- **Empty set after hard filtering** → escalation policy: (a) if the emptiness is due to a
  *preference-derived pseudo-constraint*, relax it and re-run with the relaxation logged; (b) request
  human approval to proceed under a documented exception; (c) reject with a precise reason
  ("no residency-eligible model supports the required modality"). **True hard constraints are never
  auto-relaxed.**
- **Cost ceiling exceeded by all eligible models** → downgrade the task tier if the facets permit,
  queue for batch (if latency allows), or reject with a cost-reason. The choice is governed by tenant
  policy, not made silently.

### 9.7 Recovery invariants
Idempotent retries (dedupe keys), bounded retry budgets, exponential backoff with jitter, hysteresis
on health transitions, and a hard cap on chain length. No recovery path may violate a hard constraint;
a recovery that would require doing so terminates in a governed rejection instead.

---

## 10. Deliverable 9 — Adaptive Learning Design

### 10.1 Should routing be static or adaptive?

**Adaptive — but only within governed bounds, and never at the expense of reconstructability.** A
purely static policy rots as models change and as our own telemetry accumulates evidence a static
table cannot use. A fully adaptive end-to-end learned router is the opposite failure: opaque,
un-auditable, and capable of drifting into constraint violations. The design threads between them.

### 10.2 What may be learned

Learning updates **parameters inside the transparent scoring function** — never the function's
structure and never constraints:
- capability/task-fit priors, corrected by observed `task_success` per family
- retry-rate, verification-failure, and human-review estimates
- latency and cost estimates (including p95 tails)
- calibration corrections (mapping a model's raw confidence to empirical correctness)
- tier thresholds (slowly, under review)

### 10.3 What must never be learned

- hard constraints (privacy, residency, approved providers, required modality, compliance)
- safety/criticality floors and confidence thresholds for high-blast-radius tasks
- governance precedence and the constraint/preference boundary itself
- anything that would let optimization override governance

These are **human-owned, declarative, and change-controlled** (Section 11). The learner may propose;
only a governed change process may alter them.

### 10.4 Avoiding oscillation

- **Hysteresis and minimum dwell time** on any switch between models for a task class — a model must
  win by a margin *and* hold it for a window before the policy flips.
- **Bounded exploration.** Any epsilon-exploration is capped, budgeted, and disabled for
  high-criticality facets.
- **Change gates.** Learned weight changes are staged: shadow-evaluated (Section 8.3), then canaried,
  then promoted — never hot-applied to the live route-time path.
- **Regularization toward the prior.** Updates are damped so sparse or noisy telemetry cannot swing a
  weight; confidence-weighted so a field with 10 observations barely moves and one with 10,000 moves
  meaningfully.

### 10.5 Preserving explainability

Learned values remain **named parameters in the same transparent function**, versioned with provenance
("this capability prior was updated on 2026-07-10 from 4,182 production outcomes"). Because learning
only tunes coefficients of an explicit weighted score — never replacing it with a black box — every
decision stays explainable in exactly the Section 7 format, and the **static policy of record is always
reconstructable** by pinning `PolicyConfig` to a prior version. This is the non-negotiable difference
from a learned end-to-end router.

---

## 11. Deliverable 10 — Enterprise Governance Layer

### 11.1 The separation is architectural, not cosmetic

Technical optimization and enterprise governance are **two planes with different owners, change
processes, and precedence** — not two sets of weights in one config. This mirrors the platform's
core thesis: governance is a deterministic layer *in front of* reasoning/optimization, never a knob
inside it.

| Plane | Contents | Owner | Change process | Nature |
|---|---|---|---|---|
| **Technical Optimization Plane** | quality prediction, latency, cost, throughput, historical success | ML/platform team | continuous, learned, canaried | mutable, adaptive |
| **Enterprise Governance Plane** | approved providers, privacy tier, residency, compliance regimes, human-approval requirements, budget authority, criticality floors | risk/compliance/tenant admin | deliberate, reviewed, versioned, separation-of-duties | declarative, human-owned |

### 11.2 How governance expresses itself

Two mechanisms only:
1. **Constraints (veto).** Applied in pipeline stage (2). Eliminate models absolutely. This is where
   privacy, residency, approved-provider, and compliance live.
2. **Bounded weight modifiers.** Applied in stage (5). Nudge ranking among *already-eligible* models
   (e.g. "prefer the sovereign provider when scores are within 5%"). Bounded so they can never
   resurrect an eliminated model or override a capability floor.

Governance never reaches into the scoring function's internals; it sits above it.

### 11.3 Precedence (strict, total order)

```
Enterprise-governance constraints   (veto — highest)
        ▶ Capability constraints    (veto)
              ▶ Governance weight modifiers
                    ▶ Optimization scores   (lowest)
```

A model that fails compliance is gone *before* capability is considered; a cheaper, faster, better
model that violates residency is never selected, and the explanation says exactly that. Optimization
can only choose among what governance permits.

### 11.4 Why this must be architectural

If governance were "just more weights," a large enough optimization score could overwhelm a compliance
preference — a latent path to an illegal or contract-breaching selection. Making governance a separate,
higher-precedence, human-owned plane with veto power is what makes the system *defensible*: an auditor
can inspect the governance plane in isolation, and no model change or learning update can silently
weaken it. This is the same reason ActionGate is a distinct deterministic layer rather than a runtime
feature.

---

## 12. Product recommendation — is the *policy* the product?

### 12.1 The four options, assessed

| Option | Verdict |
|---|---|
| **AI Orchestrator** | **Reject as the product framing.** The orchestrator (invoke, retry, stream, wire tools) is the commoditized execution engine — LiteLLM/Portkey/gateways already do it adequately. Positioning here concedes the defensible ground and competes on plumbing. |
| **Hybrid LLM Routing** | **Reject as the primary framing.** "Routing" signals cost/quality optimization — the crowded, learned-router space (Martian, NotDiamond, RouteLLM). It undersells governance and invites a feature-comparison Ugence does not want to win on. |
| **Intelligent Model Selection Engine** | **Closer, but "intelligent" oversells and "engine" points at execution.** Directionally right in that it centers *selection*. |
| **Model Selection *Policy* (a governance capability)** | **Recommended.** Center the **declarative, auditable, constraint-first policy artifact with per-decision explanation and a governance/optimization plane split.** The policy is the product; the engine is its interpreter. |

### 12.2 Recommended positioning

Position this as a **governance capability in the AI Control Plane**, the *pre-reasoning* analogue of
ActionGate — call it, in the platform's naming grammar, something like **"ModelGate."** ActionGate
answers "may *this action* execute?"; ModelGate answers "may *this model* be used for this task, and
which permitted model should serve it — and why was every alternative rejected?" It sits at the entry
boundary of reasoning, deciding *which reasoner may enter*, exactly as Context Minimization governs
*what context may enter* and ActionGate governs *what action may leave*.

The productizable, non-commodity asset is the bundle this document specifies:
**the policy artifact + the registry schema (with declared/measured/observed provenance) + the
explanation contract + the closed-loop benchmark + the governance/optimization plane split.** The
orchestrator that executes it is real and necessary but is the *engine*, not the *product* — and
should be positioned, priced, and defended accordingly.

### 12.3 Direct answer to the framing question

**Yes — the Model Selection Policy is the true product, and the AI Orchestrator is its execution
engine — with one honest qualification.** The policy's *optimization* value is exposed to model
convergence and price collapse (Section 1.5); its *governance* value (compliance, privacy, residency,
approved-provider, auditability, explainability) is durable and intensifies with regulation. The
correct build order therefore leads with the governance spine — the constraint algebra, registry
provenance, explanation contract, and plane separation — and treats learned optimization as the upside
layer on top. Built that way, the policy is defensible even in the world where models converge, which
is the world a critic should assume.

### 12.4 What would falsify this recommendation

Stated plainly, so it can be tested: this recommendation is wrong if (a) a cloud provider ships a
portable, cross-vendor, declarative selection policy with per-decision compliance-grade explanation
and a governance/optimization plane split — occupying this exact ground before Ugence; or (b) enterprise
buyers demonstrably do *not* require per-decision auditability and treat model choice as pure
cost/quality optimization, in which case the crowded learned-router space is the whole market and the
governance premium does not exist. Both are empirical questions; neither is settled by today's evidence,
and the second runs against the regulatory direction of travel (EU AI Act and sector rules all push
toward auditable, explainable automated decisions).

---

## 13. Appendix A — Worked example

**Request.** Extract 14 structured fields from a 90-page scanned healthcare contract; output strict
JSON; internal deadline is overnight batch; data is regulated PHI subject to US residency.

**Resolved constraints.** `residency=us`; `privacy_tier≥regulated`; `certifications⊇{hipaa}`;
`modalities_in⊇{pdf/image}`; `effective_context≥~120K`; `structured_output=strict`;
`latency_class=batch` (so latency is a *preference*, not a floor).

**Filtering.** Model A eliminated — no HIPAA certification. Model B eliminated — SaaS endpoint outside
US residency. Model E eliminated — declared 1M context but *measured* effective context 96K < 120K
required. Survivors: C, D.

**Scoring (latency down-weighted, batch).** C leads on measured extraction accuracy and structured-
output validity; D is cheaper but has a higher verification-failure rate on extraction in our
telemetry, which raises its blended cost per *successful* task above C's. **Selected: C.** Fallback: D.

**Rendered explanation.** "Selected Model C. Eliminated A (no HIPAA certification), B (endpoint outside
US residency), E (measured effective context 96K < 120K required). Among eligible models, C led on
measured extraction accuracy and strict-JSON validity; though D's per-call price is lower, its higher
extraction verification-failure rate makes its blended cost-per-successful-task higher. Latency
down-weighted (batch). Fallback: D."

Note what carried the decision: two governance constraints, one **measured-over-declared** context
correction, and a **blended-cost-per-success** comparison — none of which a price/quality router or a
config-driven gateway would have produced with an auditable trail.

---

## 14. Appendix B — Competitive differentiation matrix

| Capability | Gateways/proxies (LiteLLM, Portkey, OpenRouter, Kong/Cloudflare AI GW) | Learned routers (Martian, NotDiamond, RouteLLM) | Cloud catalogs (Bedrock, Azure AI, Vertex) | **This policy (ModelGate)** |
|---|---|---|---|---|
| Unified multi-provider access | ✅ | partial | provider-scoped | assumed (engine) |
| Fallback / load-balance | ✅ (config) | partial | partial | ✅ (ranked chain) |
| Task-fit quality prediction | ❌ | ✅ | ❌ | ✅ |
| Cost/quality optimization | manual | ✅ | ❌ | ✅ |
| Compliance/residency as **first-class hard constraint** | ❌ (out-of-band) | ❌ | partial (guardrails) | ✅ (veto plane) |
| **Per-decision explanation with elimination ledger** | ❌ | ❌ (opaque) | ❌ | ✅ |
| Declared/measured/observed **provenance split** | ❌ | ❌ | ❌ | ✅ |
| Governance/optimization **plane separation + precedence** | ❌ | ❌ | ❌ | ✅ |
| Deterministic, replayable decisions (audit) | ❌ | ❌ | ❌ | ✅ |
| Governed adaptive learning (reconstructable static baseline) | ❌ | learned e2e (not reconstructable) | ❌ | ✅ |
| Portable policy artifact the enterprise owns | ❌ | ❌ | ❌ | ✅ |

The pattern is consistent: existing tools own **access, plumbing, and optimization**; none owns
**governed, explainable, deterministic selection as a portable policy**. That column is the product.

---

*End of specification — Version 1.0.*
