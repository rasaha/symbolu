# LLM Steering Controller — VC Brief

**Xozence Labs — a deterministic, model-agnostic steering & audit layer for LLM generation**
*June 2026*

> **Name (locked).** This product ships as the **LLM Steering Controller**. Its internal engine is the
> **CRS Controller** (C×R×S — Context × Semantic × Resonance). "Steering" is the deliberate, honest verb:
> the layer **influences the meaning-frame** a model generates within; it does not author the model's
> intelligence and does not decode meaning. This brief supersedes the framing in
> `CONSCIOUS_GENERATION_LLM_VC_BRIEF.md` for this product boundary; the deeper multi-field research
> architecture is referenced, not re-pitched, here.

---

## One-line positioning

**The LLM Steering Controller is a deterministic control layer that fixes *which meaning-frame* an LLM
answers in — making generation consistent, auditable, and governable, on top of any model, with no weight
changes.** It sells *control and trust*, not a smarter model.

What it is, in one honest sentence: a **steering wheel and trip-recorder** you bolt onto an LLM — the dial
is rule-based (same input → same framing), and because it is rule-based you can show *why* it steered the
way it did.

---

## Page 1 — The Problem

LLMs fail less often because they can't write fluently, and more often because they answer under the
**wrong frame**: they promote a secondary reading of a polysemous query, drift into an adjacent domain
mid-answer, give generic low-signal padding, or talk *about* the frame instead of answering.

| Failure in a raw LLM | What the model never explicitly isolates |
|---|---|
| Answers the wrong sense of a polysemous query | which **semantic domain** the question lives in |
| Drifts into an unrelated domain mid-answer | a **rejected-domain** boundary |
| Promotes a minor reading to the headline | primary-vs-secondary **frame ranking** |
| Generic, padded answer | whether the answer carries **frame-specific signal** |

Post-hoc fixes (RLHF, retrieval, moderation) act *after* the model commits to a distribution, and they are
**stochastic** — the same prompt yields different behavior across runs and silently drifts across model
versions. The Steering Controller intervenes **earlier and deterministically**: it sets the frame before
and around generation, so the behavior is reproducible, testable, and auditable rather than emergent.

---

## Page 2 — The Validated Product

### Pipeline (deterministic, model-agnostic, zero weight changes)

```
Input
  → C×R×S frame matching      (primary / secondary / weak / rejected domains, frozen thresholds)
  → framed generation         (the answer is produced inside the chosen frame)
  → answer-audit gate         (pass · rewrite · escalate)
  → traceable diagnostics     (a logged reason for every steering decision)
```

The frame decision is made **before** the LLM answers; the audit gate is a deterministic decision layer
*after* it. Nothing in the runtime requires hidden-state access or weight modification.

### Measured results (internal evaluation)

On an internal evaluation — **single open model (Mistral-7B-Instruct-v0.3), 110-item polysemy set, scored
by a deterministic rubric** — framed generation improved frame discipline while preserving factuality:

| Metric | Base | Steered | Δ |
|---|---|---|---|
| Primary-frame correctness | 0.609 | **0.736** | +0.127 |
| Rejected-domain avoidance | 0.855 | **0.909** | +0.054 |
| Factuality preserved | 0.945 | **0.964** | +0.018 |

> **Scope caveats (stated up front, not buried).** These are **internal** results on **one** open model, a
> **110-item** set, scored by a **deterministic rubric** (not human raters). They are reproducible
> (`production_valid=True`), but they are **not** an external benchmark or a cross-model claim. Human
> validation is the explicit purpose of the supervised-observation track (Page 4).

### Where the value is real (and where it is not)

The defensible value is **architectural, true-by-construction** — it does not depend on any contested signal:

- **Deterministic** — same input → same frame, every run. (A property of the engine, not an empirical bet.)
- **Auditable** — rule-based steering produces a legible record of *why* a frame was chosen. This is
  explainability **of the control layer**, not of the LLM's internal reasoning — a distinction we hold firmly.
- **Model-agnostic, no retraining** — clips on from outside; ports across model versions and vendors.
- **Cheap** — frame/affinity computation is low-dimensional and inline.

These are exactly the four things stochastic prompting and activation-steering startups *cannot* offer as a
guarantee. They are the product.

---

## Page 3 — Open-Weight vs Closed-API (two honest deployment modes)

The Controller computes the frame **locally and model-free** (text in → deterministic frame), so the *frame*
is always reproducible. How the frame is **applied** depends on model access:

| Injection | Needs model internals? | Open weights (Mistral/Llama) | Closed API (Claude/GPT/Gemini) |
|---|---|---|---|
| Prompt-level steering (frame → instruction scaffold) | no | ✅ | ✅ |
| Output selection (best-of-N by frame fit) | no | ✅ | ✅ |
| Logit bias | partial | ✅ | ⚠️ GPT only; Claude/Gemini limited |
| Activation / mid-layer steering | **yes** | ✅ | ❌ not exposed |

- **On open-weight models** the Controller can reach inside (activation-level), so it offers full,
  end-to-end deterministic steering. Strongest story.
- **On closed APIs** it runs as a **vendor-agnostic control plane** — prompt-shaping + reproducible
  output-selection — one auditable steering layer that behaves the same across Claude, GPT, and Gemini.
  Honest limit: it makes the *control* deterministic, **not** the rented model's *output* (those models are
  stochastic and version-drift under you). We market closed-API value as **consistency + no lock-in + one
  audit trail across vendors**, never as activation steering or guaranteed output.

This open/closed split is a feature in the pitch: it gives a single product two buyers — a deep integration
for open-weight shops, and a switchable governance layer for teams locked into proprietary APIs.

---

## Page 4 — What Was Tested, Parked, and Retained (the honesty ledger)

We ran the deeper symbolic-signal tracks under strict pre-registration + kill criteria and **parked** them
when they didn't clear the bar. Putting this in the brief is deliberate: it is what makes the *validated*
layer credible to technical diligence.

| Track | Verdict | Source |
|---|---|---|
| Does the C×R×S decomposition carry signal beyond the hidden state? | **`CSR_REDUNDANT` → PARK** — parts decode, combination adds nothing over `hidden`; apparent "Resonance" signal (AUROC 0.832) is a **text-difficulty confound**, not phoneme meaning | `scripts/cg_wrapper_ablation/RESULTS_STL_CSR_PROBE.md` |
| Does the inference-time wrapper move generation? | **`ACTIVE_NO_EFFECT`** (ΔBhava = 0) — parked | same |
| Does a CSR-diagnostic policy gate beat the existing audit gate? | **`PB_POLICY_NO_INCREMENTAL_VALUE`** (F1 0.341 vs 0.526) — diagnostics stay explanation-only | `docs/RESULTS_CSR_POLICY_PB.md` |

**What this means for the product:** the Steering Controller depends on **none** of these speculative
signal claims. Its value (deterministic frame-control + audit) survives every one of these negatives. We do
**not** sell "Resonance decodes meaning," "Bhava is a runtime signal," or "the wrapper makes the model
smarter" — all parked, in writing.

**One thread retained (research, not productized).** The intended **match-filter** —
`MATCH(term, domain) = C × R × S` as a *multiplicative veto* against external domain templates — was **not**
tested by the static probe (which was additive and had no domain axis). It **remains untested**, recorded
as deferred IP, not a claim. A separate correlational probe found raw pre-answer hidden states predict some
future frame violations (AUROC ≈ 0.76) and rejected-domain leakage (≈ 0.83), **within one model,
correlational, not wired to runtime** — a future optional risk-scoring direction, not a current feature.

**Supervised-observation track (in progress).** A de-biased 220-row human-labeling packet is built and
exported to test the audit gate and diagnostics against **independent human judgement** rather than the
model's own rubric. Until those labels land, no new runtime-policy claims are made.

---

## Page 5 — Competitive Position

The honest competitor set is **not "nothing."** It is activation steering / control vectors /
representation engineering, system-prompt scaffolds, guardrails, and RAG. The Steering Controller's edge is
**determinism + auditability + cross-vendor portability**, not raw quality.

| Category | How the Steering Controller differs | Validated? |
|---|---|---|
| Activation-steering / control-vector startups | theirs is *learned and stochastic*; ours is *rule-based, reproducible, and logged* — a steering decision you can put in a changelog | ✅ (determinism is by construction) |
| Closed labs (GPT/Claude/Gemini) | not a competitor — our **substrate**; we add a deterministic frame + audit layer on top, self-hostable, no weight changes | ✅ |
| Open backbones (Mistral/Llama/Qwen) | our deep-integration substrate; we add interpretable frame control they don't expose | ✅ |
| Guardrails / moderation (NeMo, Llama Guard) | they filter finished text; we shape and **audit** at the meaning-frame, with traceable reasons | ✅ |
| RAG (LangChain/LlamaIndex) | RAG grounds *what* the model sees; we govern *which frame* it answers in — complementary | ✅ |

**Why a vendor like Mistral cares.** Mistral's market is European, open-weight, sovereignty- and
compliance-led. Those buyers don't pay for "most capable" — they pay for **controllable, auditable,
on-prem-able.** A deterministic, human-legible steering knob is an AI-Act-friendly governance surface. That
is a near-exact fit, *provided* it is sold as control infrastructure, not understanding.

**The one gap before a credible vendor pitch:** a head-to-head **Steering Controller vs control-vectors** on
the same steering task, showing comparable control at lower cost and full reproducibility. Until that
benchmark exists, the closed-API differentiator is a strong story, not yet a proof.

---

## Page 6 — Safe Claim Language, Status & Ask

### Safe claim language (all outward materials)

**Use:** "improves and audits semantic-frame control for LLM outputs" · "deterministic, reproducible
steering with a traceable reason for every decision" · "model-agnostic; no weight changes; runs over open or
closed models." **Avoid:** "makes the model smarter / more coherent" · "decodes meaning" · "Resonance/Bhava
are validated runtime signals" · "guarantees the output of a closed API."

### Status

Deterministic engine, C×R×S frame-matching, framed generation, audit gate, and diagnostics are built and
reproducible. Validated on one open model by a deterministic rubric; human validation pending. Closed-API
control-plane mode (prompt-shaping + output-selection) is the straightforward wrapper build. The
control-vector head-to-head benchmark is the priority experiment.

### The ask

Seed capital to (1) complete **human validation** of the audit gate and diagnostics, (2) ship the
**model-agnostic Steering Controller** (open-weight deep mode + closed-API control plane) with design-partner
integrations, and (3) run the **Steering-vs-control-vector benchmark** that converts the closed-API story
into proof. The near-term product is deterministic, cheap, and validated on the metrics above; the long-term
moat is the auditable steering layer plus the compounding observation data on which frames actually hold.

---

## Appendix — Claims → Evidence (for technical diligence)

| Claim | Source artifact |
|---|---|
| Framed vs base: primary 0.609→0.736, rejected-avoidance 0.855→0.909, factuality 0.945→0.964; `production_valid=True` | `robustness_eval_v2.json` (real Mistral run); `docs/RUNPOD_SETUP.md` |
| CSR decomposition redundant with hidden; Resonance = text-difficulty confound; wrapper `ACTIVE_NO_EFFECT` | `scripts/cg_wrapper_ablation/RESULTS_STL_CSR_PROBE.md` |
| CSR-diagnostic policy did not beat the audit gate (F1 0.341 vs 0.526; `PB_POLICY_NO_INCREMENTAL_VALUE`) | `docs/RESULTS_CSR_POLICY_PB.md` |
| Hidden states predict frame violation (AUROC ≈ 0.76) / rejected-domain leak (≈ 0.83), correlational, single-model | `docs/RESULTS_PHASE4.md` §2 |
| Diagnostics are explanation-only (not wired to runtime decisions) | `scripts/cg_wrapper_ablation/csr_match_filter/{trajectory.py,guna.py}` |
| Match-filter `MATCH = C×R×S` (multiplicative veto) **untested**, deferred | `docs/STL_CSR_REFACTOR_PLAN.md` §scope note |

*Contact: Rakesh Mohan — Xozence Labs · Repo: `rasaha/symbolu`*
*Honesty boundary: this product is firewalled from any "decoded meaning" claim; the symbolic vocabulary
names **designed control axes**, not demonstrated phenomena.*
