# Conscious Generation LLM — VC Brief

**Cognade Labs — a model-agnostic semantic-control & audit layer for LLMs, with a deeper symbolic-architecture research moat**
*Updated June 2026*

---

## One-line positioning

**Conscious Generation is a model-agnostic semantic-control layer for LLMs that improves answer framing,
reduces semantic drift, and audits generated responses — without modifying model weights.** Behind that
shippable layer sits a deeper, patent-backed symbolic-generation architecture that is the long-term moat.

This brief is deliberately two-layer, and keeps the two separate on purpose:

| | **Near-term product (validated)** | **Long-term architecture (research / patent)** |
|---|---|---|
| What | C×R×S semantic-frame control · framed generation · answer audit · traceable diagnostics | Multi-field token-evaluation (`mistral_cg`): 32-D symbolic state, phase adapter, field-integrated generation |
| State | Deterministic, model-agnostic, **no weight changes**; metrics validated on an open model | Partial implementation; speculative tracks tested and **honestly bounded** below |
| Why it matters | Sellable, testable, integrable today | Defensible IP and the bet on *how* a next-gen model should generate |

Keeping these distinct is what makes the story credible: the company has a deep patent architecture, but
the near-term product is a practical wrapper that can be tested, integrated, and sold **without requiring a
new foundation model.**

---

## Page 1 — The Problem

Current LLMs often fail not because they cannot generate fluent text, but because they answer under the
**wrong meaning-frame**: they promote a secondary interpretation, drift into an unrelated domain, give
generic low-signal answers, or talk *about* the frame instead of answering naturally.

| Failure observed in standard LLMs | What the model does not explicitly isolate |
|---|---|
| Answering the wrong sense of a polysemous query | Which **semantic domain** the question actually lives in |
| Drifting into an unrelated/wrong domain mid-answer | A **rejected-domain** boundary |
| Promoting a minor reading to the headline answer | Primary-vs-secondary **frame ranking** |
| Generic, padded, low-signal answers | Whether the answer carries **frame-specific signal** |
| Talking about "frames/domains" instead of answering | The difference between **describing** and **answering** |

Post-hoc mitigations (RLHF, retrieval, moderation) act *after* the model has committed to a distribution.
Conscious Generation intervenes earlier and more cheaply — at the **meaning-frame**, before and around
generation — and does so deterministically, so the behavior is testable and auditable rather than
emergent.

---

## Page 2 — The Validated Product

### Pipeline (deterministic, model-agnostic, no weight changes)

```
Input
  → C×R×S semantic-frame matching        (primary / secondary / weak / rejected domains)
  → framed LLM generation                (the answer is generated inside the chosen frame)
  → answer audit / needs_rewrite gate    (pass · rewrite · escalate)
  → traceable diagnostics                (why an answer failed)
```

### The core engine — `MATCH(term, domain) = C × R × S`

The system decides whether a term/domain pairing is coherent **before** the LLM answers:

| Factor | Role | Implementation note (for technical diligence) |
|---|---|---|
| **C** | ontological allowance / constraint | derived from a phonemic 12-D profile of the term |
| **R** | structural realization strength | derived from the same phonemic profile |
| **S** | semantic type coherence | semantic embedding similarity |

> Honest framing note: the *C/R* factors are computed from a deterministic phonemic profile, not from a
> learned "identity vector." The ontological language is interpretive; the computation is phoneme- and
> embedding-based and fully deterministic.

This lets the system distinguish **primary, secondary, weak, and rejected** semantic domains, with frozen
thresholds, before any generation happens.

### Measured results (internal evaluation)

On an internal evaluation — **single open model (Mistral-7B-Instruct-v0.3), 110-item polysemy set, scored
by a deterministic rubric** — framed generation improved frame correctness and domain discipline while
preserving factuality:

| Metric | Base | Framed | Δ |
|---|---|---|---|
| Primary-frame correctness | 0.609 | **0.736** | +0.127 |
| Rejected-domain avoidance | 0.855 | **0.909** | +0.054 |
| Factuality preserved | 0.945 | **0.964** | +0.018 |

The **Phase 3 answer-audit gate** (`needs_rewrite`) is the current decision layer for whether an answer
should pass, be rewritten, or be escalated.

> Scope caveats (stated up front, not buried): these are **internal** results on **one** open model and a
> **110-item** set, scored by a **deterministic rubric** (not human raters). They are reproducible
> (`production_valid=True`) but are not an external benchmark or a cross-model claim. Human validation of
> the audit gate is the explicit purpose of the supervised-observation track (Page 4).

---

## Page 3 — Diagnostics (explanation-only today)

The system also emits interpretability diagnostics that explain **why** an answer failed:

```
Derived trajectory diagnostics      GunaQuality diagnostics
  - secondary meaning promoted         - generic / low-signal
  - rejected-domain drift              - parroting-style response
  - frame-label parroting
  - generic escape
```

**These are diagnostic-only. They are not wired into runtime decisions.** A pre-registered policy test
(P-B) asked whether a deterministic policy gate built from these diagnostics could beat the existing Phase
3 audit gate. **It did not** (`PB_POLICY_NO_INCREMENTAL_VALUE`: policy F1 0.341 vs audit gate 0.526). Per
the pre-registered kill criterion, the policy track was stopped and the diagnostics remain
explanation-only. We treat that negative as a feature: it sharpens the product boundary and prevents us
from shipping a worse gate than the one we have.

---

## Page 4 — What Was Tested and Closed (and what we retain)

We ran several deeper latent-state tracks under strict pre-registration + kill criteria, and
**intentionally closed** them when they did not clear their bar:

| Track | Result |
|---|---|
| Direct "Bhava" hidden-state readout | **Negative** (read collapsed; no incremental value over a hidden-only baseline) |
| Residual "Bhava" after Guna/Vritti control | **Negative** (`PHASE4D_LEAKAGE_SUSPECTED` — decomposition not separable) |
| CSR_policy gate vs current audit gate (P-B) | **Negative** (`PB_POLICY_NO_INCREMENTAL_VALUE`) |

These negatives are commercially useful: **the product does not depend on any speculative hidden-state or
symbolic-state claim.** It remains a practical semantic-control and audit layer around existing LLMs.

**One research finding retained (not productized).** A separate research probe found that raw pre-answer
hidden states can *predict some* future semantic failures in internal tests — frame violation
(AUROC ≈ 0.76) and rejected-domain leakage (AUROC ≈ 0.83), within-model. This is a **correlational linear
probe, not causal, not wired into runtime control**, and demonstrated on a single model. It remains a
future **optional risk-scoring** direction, subject to further validation.

### Supervised-observation track (in progress)

A **de-biased human-labeling packet** (220 rows, leakage-checked) has been exported to test the product
against independent human judgement, not against the model's own rubric. It will answer two questions:

```
Does the current Phase 3 needs_rewrite gate match human judgement?
Do trajectory/Guna diagnostics add incremental predictive value on human labels?
```

The full pipeline (export → validate → evaluate) is built and tested; only human labels are pending.
**Until those labels are collected, no additional runtime-policy claims are made.** If the diagnostics
beat the gate against human labels, a *new* pre-registration governs any runtime policy — nothing ships on
an offline number alone.

---

## Page 5 — The Deeper Architecture (research moat / patent roadmap)

The broader patent architecture includes symbolic control concepts — **Vṛtti, Guna, Kosha, entropy
feedback, and stitching/relevance scoring** — and a research implementation, `mistral_cg`, that bets on a
different way to compute next-token probability: as the **integrated agreement of multiple semantic
fields** evaluating each candidate token, rather than a single continuation score from one projection.

What exists today (partial, honestly bounded):

| Component | Status |
|---|---|
| `MistralCGWrapper` forward pass (frozen Mistral-7B + ~5M trainable CG modules) | Implemented; `enable_conscious_generation` **defaults to False** |
| 32-D symbolic state + phase adapter (gated residual before the frozen LM head) | Implemented; phase adapter is the one inference-time mechanism that currently influences token selection |
| Per-token scorers (CSR · Vritti · Guna · Ontological · JEPA · Kosha/Bliss) | Implemented as **training-time** signals; auxiliary-loss lambdas **default to 0.0** |
| Field-integrated generation ("replace the softmax") | Implemented but **curriculum-gated**; not the default path |
| `MistralCGAdapter` → Agentic Framework | Smoke-tested adapter; exposes state-derived signals for governance experiments |

> Boundary discipline (applies to this whole page): this is a **research bet and IP position**, not
> shipped product. We do **not** claim consciousness is validated, that "Bhava" is decoded, that
> Guna/Vritti are runtime control signals, or that latent spiritual states are proven inside LLMs. The
> symbolic vocabulary names *designed axes the training stack optimizes against*, not demonstrated
> phenomena. The validated, sellable product is Pages 2–4; this page is the moat we are funding toward.

---

## Page 6 — Competitive Position, Honest Status & Ask

### Where we sit

Conscious Generation is best positioned as a **semantic reliability and governance layer for LLMs**. Its
near-term value is practical — better frame selection, better answer auditing, clearer failure
diagnostics — and it composes with the rest of the stack rather than replacing it.

| Category | How Conscious Generation differs | Validated today? |
|---|---|---|
| Closed foundation labs (GPT/Claude/Gemini) | We don't compete on pre-training; we add a deterministic semantic-control + audit layer on top, self-hostable, no weight changes | ✅ |
| Open-weights backbones (Mistral/Llama/Qwen) | These are our **substrate**; we add interpretable frame control + audit they don't expose | ✅ |
| RAG (LangChain/LlamaIndex + vector DBs) | RAG grounds *what* the model sees; we govern *which meaning-frame* it answers in. Complementary | ✅ |
| Guardrails / moderation (NeMo, Llama Guard) | Guardrails filter finished text; we shape and **audit** the answer at the meaning-frame, with traceable reasons | ✅ |
| Interpretability/steering startups | We ship deterministic, **traceable** frame + audit diagnostics as a product surface, not a post-hoc probe | ✅ (diagnostics are explanation-only) |
| Token-selection re-architecture ("replace the softmax") | The multi-field generation thesis | 🔬 research/roadmap (Page 5) |

**Why enterprises care:** they don't only need more fluent answers — they need answers that **stay inside
the correct meaning, domain, and policy boundary**, with an audit trail. That is exactly what the
validated layer provides, on top of existing LLMs, governably.

### Safe claim language (for all outward materials)

**Use:**
- "Conscious Generation improves semantic-frame control and answer auditability for LLM outputs."
- "The system provides traceable diagnostics for semantic drift, secondary-frame promotion, and
  low-signal responses."
- "The current runtime does not require model-weight changes or hidden-state steering."

**Avoid:**
- "Consciousness is validated." · "Bhava is decoded." · "Guna/Vritti are runtime control signals." ·
  "The system proves latent spiritual states inside LLMs."

### The ask

We are raising seed capital to (1) complete **human validation** of the audit gate and diagnostics
(supervised-observation track), (2) harden the C×R×S + framed-generation + audit layer into a deployable,
model-agnostic product with design-partner integrations, and (3) advance the deeper multi-field
token-evaluation architecture from partial research implementation toward a measurable, ablated generation
path. The near-term product is validated, deterministic, and cheap to run; the long-term moat is the
symbolic-architecture patent portfolio around C×R×S, Vṛtti/Guna/Kosha-inspired control variables, entropy
feedback, and semantic stitching.

---

## Appendix — Claims → Evidence (for technical diligence)

Every quantitative claim in this brief is reproducible from the repo. Branch:
`claude/cg-wrapper-quality-ablation-gro5iw`.

| Claim | Source artifact |
|---|---|
| Framed vs base: primary 0.609→0.736, rejected-avoidance 0.855→0.909, factuality 0.945→0.964; `production_valid=True` | `robustness_eval_v2.json` (real Mistral run); recipe `docs/RUNPOD_SETUP.md` |
| CSR_policy did not beat the audit gate (F1 0.341 vs 0.526; `PB_POLICY_NO_INCREMENTAL_VALUE`) | `docs/RESULTS_CSR_POLICY_PB.md`; eval `scripts/cg_wrapper_ablation/csr_match_filter/csr_policy_eval.py` |
| Bhava readout negative; residual Bhava negative (`PHASE4D_LEAKAGE_SUSPECTED`) | `docs/RESULTS_PHASE4.md`, `docs/RESULTS_PHASE4_STAGEB2.md`, `docs/RESULTS_PHASE4D.md` |
| Hidden states predict frame violation (AUROC ≈ 0.76) / rejected-domain leak (≈ 0.83), correlational, single-model | `docs/RESULTS_PHASE4.md` §2 |
| Diagnostics are explanation-only (not wired to decisions) | `scripts/cg_wrapper_ablation/csr_match_filter/{trajectory.py,guna.py}` |
| Human-labeling packet exported (220 rows, leakage-checked); evaluator built + tested | `docs/CSR_SUPERVISED_OBSERVATION_PREREG.md`, `export_supervised_observation_packet.py`, `eval_supervised_observation.py`, `validate_labels.py` |
| Deeper `mistral_cg` architecture: CG off by default, scorer lambdas 0.0, field-integrated softmax curriculum-gated | `docs/audits/CG_MISTRAL_SIGNAL_AUDIT.md`; `scripts/train_mistral_cg.sh` |

*Contact: Rakesh Mohan — Cognade Labs*
*Repo: `rasaha/symbolu` · Validated product: `scripts/cg_wrapper_ablation/csr_match_filter/` ·
Deeper architecture: `symbolu_training/training/conscious_generation/`, `agentic/agentic_framework/inference_mistral.py`*
*Design & audits: `docs/design/CONSCIOUS_GENERATION_DESIGN.md` · `docs/audits/CG_MISTRAL_SIGNAL_AUDIT.md`*
