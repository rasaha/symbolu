# Hybrid LLM — VC Brief

**Ugence Labs · Hybrid LLM: the governed hybrid-intelligence and evidence-reasoning layer**
*Version 3.0 — July 2026*

> **Product definition.** Hybrid LLM is Ugence's governed hybrid-intelligence and evidence-reasoning
> layer. It determines what can be computed exactly, what requires model interpretation, which model
> should perform that interpretation, what evidence may enter the authoritative pipeline, and what the
> resulting AI may claim.
>
> **Thesis.** *Compute what is knowable. Use language models only where interpretation is necessary.
> Validate model interpretations before they become enterprise facts, and validate generated claims
> before they influence decisions or actions.*
>
> **Two clearly separated things.** *Hybrid LLM* is the system-level product and runtime architecture
> (below). *HybridPhaseTransformer / Phase* is an experimental **model-backend research track** — **not
> a validated production dependency**. The production thesis does not depend on Phase succeeding; the
> enterprise results below use standard deterministic parsing, bounded softmax comparison, and
> deterministic governance, with no Phase in any enterprise arm.

**Evidence discipline.** Every material claim in this brief carries a status —
`VALIDATED` / `CONTROLLED-EVIDENCE` / `IMPLEMENTED` / `ROADMAP` / `UNSUPPORTED` / `RETIRED` — matched
to a committed result artifact. The full machine-readable record is `HYBRID_LLM_VC_CLAIM_LEDGER.json`
(source-of-truth commit `ae59749`; `FREEZE OK`; 98 frozen-phase + 30 experiment tests passing). All
enterprise results are on a **synthetic, controlled** procurement corpus with held-out and causal
checks; the semantic-interpreter arm uses a **controllable simulator**, not a live model.

---

## Page 1 — Problem and product thesis

Agentic systems can increasingly plan and call tools. But in most stacks the **model is still trusted
inside one probabilistic loop** to interpret evidence, state conclusions, and trigger actions. That is
where enterprise reliability breaks:

- retrieved context is **incomplete** — the relevant record fell outside the window;
- a model turns a **request into an approval** ("approval requested" read as "approval granted");
- a **stale policy version looks current**;
- an **interpretation silently becomes an enterprise fact** in the system of record;
- a **recommendation is delivered as a binding decision**;
- an **agent authorizes its own action** because a tool permission was mistaken for authority.

None of these are model-quality problems that a bigger model fixes. They are **separation-of-duties
problems**: interpretation, fact-admission, decision authority, and execution authority have been
collapsed into one generative call.

**Hybrid LLM is a deterministic-first, governed-intelligence layer** that separates those duties. It
computes what is knowable exactly, confines models to genuinely semantic judgments, converts model
outputs into *provisional* evidence that must be validated before it is trusted, computes enterprise
facts and outcomes deterministically where possible, and subjects every generated claim to independent
assertion governance before anything is delivered or acted on.

> **Runtime proposes. The Ugence Control Plane authorizes.**

---

## Page 2 — Architecture

Hybrid LLM is the intelligence-and-evidence layer connecting Agent Runtime, evidence normalization, the
evidence ledger, binding working memory, deterministic reasoning, bounded relational comparison, TAP
assertion governance, Decision Governance, and ActionGate:

```
  Raw enterprise sources
        ↓
  Deterministic extraction where exact  +  Bounded semantic interpretation where necessary
        ↓
  Normalization and provenance validation        ← blocks hallucinations / bad provenance / unauthorized
        ↓
  Provisional  or  Authoritative evidence ledger  ← uncertain interpretation never becomes fact
        ↓
  Deterministic identity, access, version, schema joins
        ↓
  P5 shared binding working memory                ← smallest sufficient evidence set, preserved over time
        ↓
  Deterministic typed fields  +  Bounded full slot-to-slot comparison where genuinely needed
        ↓
  Typed consistency constraints
        ↓
  Deterministic enterprise outcome mapper         ← exact outcome from exact fields
        ↓
  Hybrid LLM explanation  or  bounded model handoff
        ↓
  TAP assertion governance                        ← blocks unsupported / authority-exceeding claims
        ↓
  Decision Governance  →  ActionGate
```

**Responsibility boundaries** (each owned by a different layer, deliberately not collapsed):

- **Hybrid LLM** chooses and constrains *where model intelligence is used* — deterministic parsing owns
  every explicitly-represented field; the model is walled off to a few genuinely semantic fields and
  may only *propose* provenance-linked, span-verified records.
- **TAP** governs *what the system may assert* — it independently checks the generated explanation
  against the evidence and hard authority ceilings.
- **Decision Governance** governs *who has authority to decide*.
- **ActionGate** governs *which proposed action may execute*.

*HybridPhaseTransformer / Phase is a separate research track (Page 4), not part of this production
path.*

---

## Page 3 — What has been tested

All rows are **controlled evidence on a synthetic procurement corpus** with held-out entities/templates
and causal controls, unless marked otherwise. Numbers are from the committed result artifacts.

| Capability | Experiment | Metric | Result | Status | Scope limitation |
|---|---|---|---|---|---|
| Persistent evidence working memory | slots+quadratic | required-evidence survival; streaming accuracy | survival **0.30→1.00**; accuracy **~0.40→0.75** (deterministic P5) | CONTROLLED-EVIDENCE | streaming/multi-step only; synthetic |
| Slots vs retrieval; eviction causality | slots+quadratic (held-out) | evict-required vs evict-irrelevant | required-eviction **0.24** ≪ irrelevant-eviction **0.44**; global retrieval **0.50** < slots | CONTROLLED-EVIDENCE | one streaming workflow |
| Contradiction comparison | slots+quadratic; S5 vs S6 | conflict F1; attention type | conflict F1 **0.91–0.99**; full slot-to-slot **0.69** > query-to-slot **0.60** | CONTROLLED-EVIDENCE | small K |
| Active-version selection | slots+quadratic (verify) | version acc; active+stale co-survival | version **0.30→0.80**; co-survival **0.11** → credit **deterministic policy**, not Quadratic | CONTROLLED-EVIDENCE | Quadratic did *not* prove active-vs-stale reasoning |
| Smallest sufficient capacity | capacity sweeps | accuracy vs K | role task best at **K=4** (0.90; K=32→0.39); outcome contract needs **K=8** (0.80) | CONTROLLED-EVIDENCE | contract-dependent, not universal |
| Deterministic outcome mapper | output mapping | oracle acc; mapping error | true fields → **1.00**; deterministic mapper **0.00** mapping error (learned head 0.195) | VALIDATED | given correct fields |
| Deterministic field computation | field prediction (held-out) | outcome; field macro; conflict F1 | learned **0.64** → deterministic **1.00**; field macro **0.84→0.955**; conflict F1 **0.26→1.00** | CONTROLLED-EVIDENCE | one contract; small residual field-label gap (macro 0.955) that did not affect outcomes |
| ID & access integrity | all enterprise | ID preservation; unauthorized inclusion | **1.00 / 0.00** everywhere | VALIDATED | deterministic guarantee + tests |
| Semantic normalization safety | semantic+TAP | unsupported-fact admission; downstream | admission **0.000** at every simulated interpreter quality; governed downstream **0.92→0.947**; oracle **1.00**; ungoverned baseline **0.35** with **17.7%** admission | CONTROLLED-EVIDENCE | interpreter is a **simulator**; live-model pending |
| TAP assertion governance | semantic+TAP | unsupported / authority recall; precision | prompt-only **0.00/0.00**; TAP+ceilings **1.00/1.00**, supported precision **1.00**, qualifier preservation **1.00** | CONTROLLED-EVIDENCE | drafts use simulated overclaim injection |
| Governance causal controls | semantic+TAP; verify | span/provenance block; irrelevant invariance | span-removal & provenance-corruption **blocked 1.00**; irrelevant injection **invariant** | CONTROLLED-EVIDENCE | specified controls only |

**Precise attributions (do not overstate):**
- **Binding slots** preserve relevant evidence across streaming/multi-step workflows.
- The **deterministic P5 policy** selects the active and relevant evidence and deserves **primary
  credit for version accuracy** (active+stale co-survival was only ~0.11 — Quadratic did **not** prove
  active-vs-stale reasoning).
- **Full slot-to-slot Quadratic** improves contradiction/multi-record interaction.
- **Synergy of slots + Quadratic was validated for the controlled streaming/multi-step workflow**, not
  as a universal result.
- For the tested contract, the relevant enterprise fields were **deterministic functions of exact
  retained evidence and were better computed than predicted**.
- **Semantic normalization safety** (0.00 unsupported-fact admission) and **TAP governance** (100%
  unsupported/authority recall) are the strongest governance findings — obtained under **controlled
  failure injection with a simulated interpreter**; **live-model interpretation and TAP generalization
  remain externally unvalidated.**

> **Prompting asks a model to remain grounded. TAP independently checks whether it did.**

---

## Page 4 — Commercial significance, roadmap, and the ask

**Why this is commercially valuable**
- **Fewer unsupported enterprise facts** — a validation gate that admitted 0.00 unsupported facts in
  the controlled study regardless of model quality (vs 17.7% ungoverned).
- **Smaller external-model handoffs** — only unresolved spans and tenant-safe identifiers leave the
  boundary; deterministic parsing keeps most work local.
- **Deterministic auditability** — every delivered fact resolves to a ledger evidence ID (1.00
  preservation) with append-only provenance.
- **Persistent workflow continuity** — a bounded working set survives across streaming/multi-step
  workflows where fresh retrieval loses distant evidence.
- **Model-agnostic governance** — the governance layers are deterministic; they wrap *any* model.
- **Build or govern** — Ugence can back its own agents or sit as a governance layer over existing
  agent stacks.

**Competitive positioning — architectural differences, not blanket market claims**

| Conventional agentic stack | Ugence Hybrid LLM |
|---|---|
| Model output treated as the result | Model interpretation treated as a **proposal** (provisional evidence) |
| Prompt-based grounding | **Independent TAP enforcement** (checks the output, not the prompt) |
| Query-time context retrieval | **Persistent governed evidence working set** |
| LLM predicts enterprise decisions end-to-end | Exact facts and policy outcomes **computed deterministically where possible** |
| Tool permission ≈ practical authorization | **ActionGate independently authorizes execution** |

*(We describe architectural differences; we do not assert that any specific competitor lacks these
features.)*

**Roadmap (capital priorities)** — external validity first, not synthetic Phase scaling:
1. **Live frontier/local-model external-validity study** of normalization + TAP (replace the simulated
   interpreter with real models).
2. **Human-adjudicated document corpus** and a **bounded real procurement shadow pilot**.
3. **End-to-end Agent Runtime + TAP + Decision Governance + ActionGate** integration test.
4. **Adversarial and bypass testing** of the governance gates.
5. **Long-running workflow and policy-revocation** testing.
6. **Second-domain transfer** (beyond procurement).

*Explicitly de-prioritized as central capital use: additional synthetic Phase scaling.*

**The ask.** We are raising to move Hybrid LLM from a **controlled-evidence governance layer** to an
**externally-validated one**: live-model normalization/TAP studies, a human-adjudicated corpus, and a
bounded real-workflow pilot through the full Agent Runtime → TAP → Decision Governance → ActionGate
path. The governance layers are implemented and tested; the funded risk is concentrated in external
validity, adversarial hardening, and second-domain transfer.

> Agentic systems are increasingly able to plan and use tools, but the model is still commonly trusted
> to interpret evidence, state conclusions, and trigger actions inside one probabilistic loop. Ugence
> separates those responsibilities. Hybrid LLM uses models only where interpretation is necessary,
> converts their outputs into provisional evidence, preserves a bounded traceable working set, computes
> exact enterprise facts and outcomes where possible, and subjects generated claims to TAP before
> Decision Governance and ActionGate determine whether anything may proceed.

---

## Appendix — Phase research track (separate; not a production dependency)

Phase is retained as **model-backend research**, reported honestly:
- Frozen V2-S **validated controlled selected-cue retention**; Phase mechanics remained intact in
  controlled retention tests (98 tests, `FREEZE OK`). A tiny (~240K-param) pure-phase model reached
  100% controlled needle retrieval at 10K tokens — **historical mechanism-level evidence only**.
- In the enterprise persistence / unresolved-recurrence auxiliary experiment (N=1024, late fusion),
  **Phase provided no causal incremental information**: normal / zeroed / shuffled / reversed /
  relevance-removed controls produced **no meaningful causal dependence**, and a **trained GRU baseline
  outperformed it** on the temporal target (A3 0.751 ≈ A1 0.752; GRU 0.834).
- **Phase has no authorized production role** in the current enterprise architecture. Further Phase
  work requires a **new mechanistic hypothesis and independent evidence** before any fusion.

Claims previously made for Phase — that it "removes the long-context decay tax," is "a validated global
retrieval substrate," that "serial Protected Phase beats other hybrids," that "quadratic is invoked
only where Phase confidence is low," or that "Phase retrieval superiority is ready for
commercialization" — are **retired or unsupported** (see the claim ledger) pending a committed external
benchmark. The small controlled needle task is mechanism-level history, clearly separated from current
product validation.

---

*Contact: Rakesh Mohan — Ugence Labs · Repo `rasaha/symbolu` · commit `ae59749` · `FREEZE OK`*
*Evidence: `experiments/enterprise_slots_quadratic/`, `experiments/enterprise_output_mapping/`,
`experiments/enterprise_field_prediction/`, `experiments/semantic_evidence_tap/`,
`experiments/phase_quality_auxiliary/` · claim ledger: `HYBRID_LLM_VC_CLAIM_LEDGER.json`*
