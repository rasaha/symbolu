# BCVF LLM Trust Routing — Design Plan

**Status:** Skeleton (sections listed, details pending)
**Parent result:** Autonomy BCVF experiment chain, commits through `87a9bbf` on branch `claude/review-robotics-design-07ZMr`
**Motivating finding:** N=10 Ketu→Rahu smoke on `S3_map_error_accel` rescued both prior additive-cost-composition failure seeds (73, 81); 4× reduction in A3 mean final lateral, 3.4× reduction in std
**Scope:** Transfer the autonomy "BCVF as trust-shaper, not additive-cost competitor" composition into one bounded LLM inference-time experiment
**Discipline:** One-variable-at-a-time, the same pattern the autonomy DESIGN.md and its experiment chain used

---

## Section 0 — Preface & Transfer Premise

### 0.1 Where this document comes from

This design plan is a direct consequence of a nine-experiment chain on the
autonomy side (`symbolu_robotics/bcvf_autonomous/`), not a standalone
research proposal. The autonomy chain tested BCVF V3.1 closed-loop in an
MPPI planner and, one bounded experiment at a time, narrowed its failure
modes until it found a working architectural composition:

| # | Experiment | Finding |
|---|---|---|
| 1 | V2 B1 scenario-specific anchor | Unblocked the reference-frame contamination; necessary but not sufficient |
| 2 | Reach + horizon fixes | Vehicle engages obstacle zone at x=60–80 m |
| 3 | `S3_map_error_accel` quadratic failure | Produces persistent second-order signal; verified in isolation |
| 4 | `J_perf` lane-deviation cap | Broke MPPI softmax saturation |
| 5 | All-pairs BCVF | Empirically **worse** than anchor-pairs — ruled out |
| 6 | Anchor-pairs + capped J_perf | Byte-differentiated from baseline, but direction unstable (N=24: Fisher p=0.78, McNemar p=0.77) |
| 7 | Cross-sample replication (N=34, seeds 42–65 ∪ 72–81) | Null reproduced; mean alignment correlation +0.036 — BCVF directionless under additive composition |
| 8 | **Ketu→Rahu composition** (BCVF shapes trust, not softmax) | N=10 result: 2/2 prior A0-wins **rescued**; 4× reduction in A3 mean final \|y\|; 3.4× reduction in std |
| 9 | N=26 at seeds 72–97 (assumed to confirm) | See §0.3 |

The specific architectural change that flipped the result from null to
positive is small: per-predictor BCVF disagreement → softmin trust weights
→ trust-weighted consensus trajectory → `J_perf` on that consensus. No
additive BCVF term in the softmax. Commit `87a9bbf`.

### 0.2 Empirical anchor at N=10

The single ten-seed smoke on `S3_map_error_accel` under Ketu→Rahu
(`/tmp/bcvf_gate2_s3_accel_ketu_rahu_n10`, seeds 72–81):

| Seed | Prior (additive) A3 outcome | Ketu→Rahu A3 outcome | Change |
|---|---|---|---|
| 72 | rescued (A3 recovered, A0 didn't) | rescued | preserved |
| 73 | **A0 wins** — A3 ended 23.4 m off-lane | both recovered, A3 at 0.08 m | **rescued** |
| 74 | both recovered | both recovered | unchanged |
| 75 | rescued | rescued | preserved |
| 76 | both recovered | both recovered | unchanged |
| 77 | both recovered | both recovered | unchanged |
| 78 | rescued | both failed — A3 at 7.4 m | **degraded** (isolated) |
| 79 | both recovered | both recovered | unchanged |
| 80 | both recovered | both recovered | unchanged |
| 81 | **A0 wins** — A3 ended 11.3 m off-lane | both recovered, A3 at 0.38 m | **rescued** |

Aggregate: A3 mean final \|y\| dropped from 3.54 ± 7.40 m (additive) to
**0.88 ± 2.17 m** (Ketu→Rahu) against an unchanged A0 mean of 5.29 ± 8.32 m.

### 0.3 Assumed N=26 confirmation (conditional anchor for this document)

**This document is written assuming the N=26 smoke at seeds 72–97
reproduces the N=10 per-seed pattern on the 16 additional seeds.**
Specifically, it assumes:

- **McNemar's exact p ≤ 0.10** on paired recovery, with at least 2⁄3 of
  discordant pairs favoring A3 (i.e. ≥4:0, ≥5:1, ≥6:2, or ≥7:3).
- **Recovery rate**: A3 ≥ 0.80, A0 ≈ 0.70–0.75 (replicating N=10 ratio).
- **Final \|y\| mean**: A3 < 2.0 m (replicating ~4× reduction vs A0).
- **Final \|y\| std**: A3 ≤ 3.0 m (replicating ~3× tightening vs A0).
- **No cluster** of seed-78-like degradations — at most one additional
  catastrophic A3 seed on fresh data (1–2 out of 16 new seeds).

If the actual N=26 result falls short of these conditions, this entire
document's empirical anchor is invalid and **§10 blocks progression**.
See §0.6.

### 0.4 The structural claim being transferred

The claim being carried into the LLM domain is **not** "BCVF works in
autonomy." That would be a weak claim — a single scenario, single
composition, single detector-order setting. The finer-grained claim the
nine-experiment chain actually supports is:

> For multi-source control systems where one source can silently
> destabilize, a second-order disagreement detector whose output
> **shapes the reference frame** via softmin trust weighting
> (and does **not** appear as an additive term in the control cost)
> converts the detector from a directionless penalty into a
> safety-aligned controller, provided the detector's Lemma-1
> invariance (insensitivity to constant and linear disagreement)
> is preserved.

That is a domain-general structural claim. Its three components are:

1. **Detector:** second-order disagreement-acceleration, gated, Huber-penalized — the BCVF math kernel unchanged.
2. **Composition:** BCVF output feeds trust weights, never the softmax cost. Ketu informs Rahu; they do not compete.
3. **Invariance:** Lemma 1 must carry. Constant and linear-in-time disagreement must produce zero distrust regardless of domain metric.

If any of the three components fails in the LLM instantiation, the
structural claim does not transfer, and the experiment should stop
and report that as the finding.

### 0.5 What this document is, and explicitly is not

**Is:**
- A bounded V1 plan for **one** LLM inference-time experiment.
- A specification of what "BCVF in LLMs" means in one concrete setting (verifier-guided decoding, M=2 sources), with pre-committed metrics, baselines, and success thresholds.
- A working catalog of failure modes inherited from the autonomy chain, adapted to LLM geometry.

**Is not:**
- A claim that BCVF will work in LLMs. That is exactly what the V1 experiment is designed to test.
- A general LLM architecture proposal (no fine-tuning, no training-time signal, no loss shaping).
- A multi-domain framework (no retrieval routing, no MoE, no multi-branch reasoning in V1).
- A publication or product plan. Those are separate documents that only become relevant if V1 produces a positive result.

### 0.6 Hard stop rules

The autonomy chain worked because at each phase, a pre-committed stopping
criterion prevented scope creep into unvalidated territory. The same
discipline applies here. Progression through this document halts if any
of the following is observed:

1. **Autonomy N=26 does not confirm** the conditions stated in §0.3.
   → Document is frozen. Return to autonomy first; consider veto-structured
   BCVF (Option D) or disagreement-weighted consensus variant as the next
   autonomy experiment. Do **not** begin the LLM experiment.

2. **V1 experiment produces a null result** (BCVF-trust routing matches
   the conventional verifier-blend baseline within noise on the
   pre-committed metric, see §6).
   → Document closes. V1 finding: "structural claim does not transfer
   to LLM inference under the tested composition." Write up, do not
   expand to V2 retrieval / MoE / fine-tuning paths.

3. **V1 experiment produces a *regression*** (BCVF-trust routing
   demonstrably worse than conventional verifier-blend baseline on
   the same eval set).
   → Document closes. V1 finding: "BCVF-trust composition introduces
   harm in LLM inference." Post-mortem, identify which assumption
   broke, do not proceed.

4. **Lemma 1 invariance is violated** in the LLM adaptation — i.e., the
   chosen disagreement metric + temporal window + gate combination
   produces non-zero distrust under constant or linear-in-time source
   disagreement.
   → Section §2 (Phase 1 Core Math) is rejected; section rewritten
   until invariance is provable. Do not proceed to §3+ until resolved.

5. **The smallest V1 experiment cannot be bounded below ~2 weeks of
   engineering and ~1 GPU-day of compute.**
   → Scope is wrong. Re-scope §1 (Phase 0) until the experiment fits,
   or stop.

### 0.7 Relationship to the autonomy codebase

This document does **not** modify `symbolu_robotics/bcvf_autonomous/`.
The BCVF math kernel implemented there is the reference; the LLM
adaptation (§2) will express its equations in a *parallel* module (not
yet created) rather than editing the autonomy code. The autonomy chain
continues to own its own test suite, V1 Lemma-1 demo, and Phase 4
ablation protocol, unaffected by work described here.

### 0.8 Discipline — what is and is not authorized per section

Every subsequent section in this document is gated by the same pattern
the autonomy `DESIGN.md` used: **no section is filled in until the
previous one is reviewed and authorized**. No implementation begins
until the design section is filled in, reviewed, and its sign-off
recorded in the section's header metadata. Scope expansion between
sections is not permitted; expansion is a V2 event documented in §9.

The intent is to carry the same discipline that produced the working
Ketu→Rahu composition into a domain where the temptation to skip
bounded experiments is higher — because LLM infrastructure costs
more per experiment and the success metrics are noisier.

---

## Section 1 — Phase 0 — Scope Lock

**Purpose:** Define V1 exactly. Pick the smallest LLM domain where BCVF trust-routing is decidable. Lock the V1 choice: inference-time overlay on verifier-guided decoding, M=2 sources, no fine-tuning, no training, no retrieval, no MoE. Define out-of-scope explicitly.

**Details pending.**

---

## Section 2 — Phase 1 — Core Math (LLM Adaptation)

**Purpose:** Translate the autonomy BCVF kernel into LLM-domain equations. Specifically decide:
- disagreement metric between LLM source states (L2, cosine, or domain-specific)
- temporal window semantics (lookahead via speculative decoding vs. retrospective over past tokens)
- 2nd-order stencil over the chosen temporal axis
- gate + pseudo-Huber preservation
- Lemma 1 analogue: which "constant disagreement" conditions must produce zero distrust

**Details pending.**

---

## Section 3 — Phase 1.5 — Signal Characterization

**Purpose:** Synthetic LLM trace families that isolate the distrust signal under controlled conditions, analogous to the autonomy Phase 1.5 sweep. Validate that the adapted BCVF math produces Lemma-1-invariant behavior in the LLM context *before* exposing it to real model outputs. Sweep the temperature `τ_w` and gate threshold `T`.

**Details pending.**

---

## Section 4 — Phase 2 — Source Framework

**Purpose:** Define the two V1 sources (base decoder + verifier), their output shape, how their states are sampled at each token, and the API contract they present to the trust-weighting layer. Discuss scaling from M=2 toward M=small-k (verifier ensemble) without committing V1 to it.

**Details pending.**

---

## Section 5 — Phase 3 — Integration Layer (Ketu→Rahu)

**Purpose:** Implement the trust-weighted consensus and its point of contact with generation. V1 chooses one of:
- **Hidden-state shaping:** `h̃_t = h_t + U · c*_t`
- **Logit blending:** `z* = z_base + α · consensus_projection`
- **Routing/gating:** use trust weights to select which source's logits win per step

Select one for V1, justify the choice, and document the other two as deferred alternatives.

**Details pending.**

---

## Section 6 — Phase 4 — Benchmark, Metrics, Pre-committed Success Criteria

**Purpose:** Lock benchmark, primary metric, baseline comparisons, and the pre-committed thresholds *before* running. Avoid the mistake autonomy made initially (using max|y| as the metric when recovery rate was the one that mattered). Candidates:
- Benchmark: TruthfulQA, HaluEval, or similar hallucination-focused suite
- Primary metric: hallucination rate / factuality score on a held-out split
- Baseline 1: vanilla greedy decoding (the "A0" analogue)
- Baseline 2: standard verifier blend with fixed weight (the "conventional engineering" baseline we must beat)
- Success threshold: BCVF-trust routing must beat Baseline 2 by a pre-committed margin

**Details pending.**

---

## Section 7 — Phase 5 — Packaging & Reproducibility

**Purpose:** What the V1 deliverable looks like: minimal package surface, inference harness, eval script, deterministic seed handling, reproduction instructions. Non-goal: publication-grade packaging.

**Details pending.**

---

## Section 8 — Failure-Mode Analysis

**Purpose:** Document ahead-of-time the failure modes we already know exist in the autonomy analogue, and their LLM counterparts. Critical because the autonomy chain learned its own failure modes only through painful smokes; here we catalog them before running.
- Correlated-source error (all sources wrong in same direction)
- Directionless trust when attractor is tepid
- Retrospective-2nd-difference catching noise rather than instability
- Latency blow-up at M>2

**Details pending.**

---

## Section 9 — V2 Roadmap (Deferred)

**Purpose:** Document the expansion directions we deliberately exclude from V1 — not as promises, as a reminder that each expansion is its own bounded experiment.
- Retrieval-augmented trust (M=k retrieval chunks)
- Multi-branch reasoning (M=k reasoning branches)
- MoE trust-routing
- Fine-tuning with trust-calibration loss
- Veto-structured variant (Option D analogue)
- Multi-source, cosine-metric, training-time signal

**Details pending.**

---

## Section 10 — Decision Gate: Proceed / Don't Proceed

**Purpose:** Pre-committed go/no-go checklist that must be satisfied before this experiment is authorized:
- [ ] Autonomy N=26 (or higher) confirmed the Ketu→Rahu structural advantage
- [ ] Infrastructure for LLM inference is available or cheaply acquirable
- [ ] Benchmark and baseline-2 are agreed upon
- [ ] Pre-committed success threshold is locked
- [ ] Owner has 1–2 weeks of engineering bandwidth

**Details pending.**

---

_End of skeleton. Each section to be filled in one at a time, on explicit authorization._
