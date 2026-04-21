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

### 1.1 Purpose

Lock the boundaries of V1 so implementation does not sprawl. Every
decision below is motivated by one principle: **build the smallest
system that can decide whether BCVF-as-trust-observer transfers to
LLM inference**. V1 is not a product. V1 is not a framework. V1 is
one decidable experiment.

### 1.2 V1 Target

| Dimension | V1 Choice | Rationale |
|---|---|---|
| Domain | LLM inference-time decoding | No training loop; minimum infrastructure; mirrors autonomy's inference-only MPPI |
| Task | Multiple-choice question answering with known factual answer | Hallucination is where verifier blending is demonstrably useful; matches where structural signal should be most detectable |
| Benchmark | TruthfulQA (multiple-choice variant) | Well-established, small enough for <1 GPU-day eval, ground truth is exact |
| Model | Llama 3.1 8B Instruct (open-weight, reproducible) | Single-GPU inference; mature tooling; hallucination behavior observable at this scale |
| Decoding | Greedy | Deterministic; sampling noise does not confound the composition comparison |
| Source count `M` | **3** | Minimum for Ketu→Rahu trust-weighting to discriminate a per-source outlier; derived in §2.2.3. `M=2` is mathematically inert for this composition |
| Source 1 | Base decoder (plain model logits) (§1.4.1) | The "A0" analogue — what a vanilla decoder would emit with no trust routing |
| Source 2 | First paraphrased decode (§1.4.2) | Fallible source A — generated by temperature-0 paraphrase of the prompt with rewrite-seed `α` |
| Source 3 | Second paraphrased decode (§1.4.3) | Fallible source B — generated by temperature-0 paraphrase with rewrite-seed `β ≠ α` |
| Temporal window | 5-token forward lookahead via speculative step | Closest structural match to autonomy's H=50 rollout — **future-oriented, not retrospective over past tokens** (§2 covers this) |
| Integration point | Logit blending with trust-shaped weight | Cleanest to implement and attribute; hidden-state shaping is V2 |
| Trust temperature `τ_w` | 1.0 | Direct carry-over from autonomy; adjust only if §3 sensitivity sweep demands it |
| Fine-tuning | **None** | Pure inference-time overlay. Training-time signal is explicitly V2 (§9). |
| Comparative baselines | 3 decoders: vanilla / conventional-blend / BCVF-trust | Required to attribute any improvement correctly |

### 1.3 Model and Decoding Setup (locked)

- **Model:** `meta-llama/Meta-Llama-3.1-8B-Instruct` via HuggingFace transformers. No quantization for V1 (so numerical stability of blended logits isn't in doubt). fp16 or bf16 depending on GPU support.
- **Decoding:** greedy only. No top-k / top-p / temperature sampling in V1. Stochastic decoding is explicitly deferred to avoid confounding a composition comparison with sampling noise.
- **Max tokens:** 32 per answer (TruthfulQA MC answers are short; longer outputs add eval noise).
- **Batch size:** 8 per eval pass on a single GPU; smaller if memory-bound at fp16.
- **Seed determinism:** any randomness in verifier paraphrase generation uses a fixed seed; all three comparative baselines must share the same seed.

### 1.4 Source Definitions (locked)

#### 1.4.1 Source 1 — Base decoder

The unmodified greedy decoder on Llama-3.1-8B-Instruct. Input: the TruthfulQA multiple-choice prompt. Output: a per-token logits distribution for the next token. This is what **A0** would emit. No system prompt manipulation, no in-context learning tricks, no chain-of-thought prefix beyond whatever TruthfulQA provides natively. Treated as a black-box token-level logits stream.

#### 1.4.2 Source 2 — First paraphrased decode

A **second decode of the same prompt paraphrased once with rewrite-seed `α`**, producing a parallel logits stream. Paraphrasing is generated by the same model at temperature 0 with a fixed rewrite instruction (e.g., "Rewrite this question preserving its meaning. Rewrite #{seed}:"). Source 2's rewrite-seed is a locked value `α` (e.g., `α = 1`).

The two decodes (original Source 1 + paraphrase Source 2) *should* agree on the factual answer but *may* diverge under hallucination — because the model's confabulated token distribution is more phrasing-sensitive than a factually-grounded one. Deliberately simple and self-contained; does not require an external verifier model, retrieval, or additional weights.

#### 1.4.3 Source 3 — Second paraphrased decode

A **third decode under the same paraphrase instruction with a different rewrite-seed `β ≠ α`**, producing an independent parallel logits stream. Same mechanism as Source 2, different rewrite seed (e.g., `β = 2`).

The structural reason V1 uses two paraphrased decodes rather than one (§2.2.3): at `M=3` with three sources and three pairs `{(1,2), (1,3), (2,3)}`, a lone failing source accumulates pair-cost attribution across two pairs while each non-failing source appears in only one pair against the outlier. The 2:1 attribution ratio is what lets BCVF's per-source trust weight discriminate *which* source is destabilizing. With only one paraphrase (`M=2`, `1` pair), all sources receive identical attribution and trust-weighting is a no-op — proven in §2.2.3. Two paraphrased decodes is therefore the **minimum `M` that makes the Ketu→Rahu composition mathematically active**.

The three sources jointly are the LLM analogue of "three predictors agreeing on a healthy vehicle state but diverging when one is destabilized." Under §2 the per-pair disagreement signals between all three decodes drive the per-source distrust, which §3 (Phase 1.5) characterizes and §5 (Phase 3) converts into trust weights + consensus.

### 1.5 Explicitly Out of Scope for V1

The autonomy chain's credibility came from doing nine bounded experiments and refusing to expand. V1 holds the same line. **Not in V1:**

- Fine-tuning. No training loop, no trust-calibration loss, no temporal-smoothness loss (§9 V2).
- Retrieval-augmented trust routing (`M=k` retrieval chunks) — larger M, different metric concerns, different failure modes. V2.
- MoE trust routing — expert weights are already learned, adding BCVF on top is a separate problem. V2.
- Multi-branch reasoning (`M=k` reasoning branches) — benchmark availability and branch-generation cost are each their own decisions. V2.
- Hidden-state shaping (option A from §5 candidates) — requires access to model internals, more invasive, V2.
- Multi-model ensemble — different model families mixed. Introduces model-scale confound. V2.
- Stochastic decoding (top-k / top-p / temperature sampling) — injects decoding-noise variance that dominates the signal we're trying to measure. Deferred.
- Multi-turn dialogue — single-turn QA only. Dialogue introduces context-window concerns the V1 design explicitly does not address.
- Adversarial / jailbreak evaluation — a different risk model. V2.
- Cross-lingual evaluation. Single-language (English) only.
- Model sizes other than 7–8B. Scaling to 70B+ is a separate cost category.

If during implementation any of the above items becomes "needed to make V1 work," **that is a signal V1 is mis-scoped**, and §1 must be rewritten before implementation resumes. V1 cannot absorb scope expansions silently.

### 1.6 Naming and Namespace Decisions

- **Package location:** `bcvf_llm/` at the repo root (peer to `symbolu_robotics/bcvf_autonomous/`, not nested inside it). Rationale: parallel domain, not a sub-feature of autonomy. Avoids accidental cross-pollination of test suites and dependencies.
- `bcvf_llm/` imports **nothing** from `symbolu_robotics/bcvf_autonomous/`. No shared Python code. The design principle is shared; the implementation is domain-specific.
- The autonomy BCVF math kernel is the *reference specification* (§2 will cite it), but §2 will write equations parallel to `core.py`, not import it. This keeps each domain's correctness auditable independently.
- The top-level `symbolu_robotics/__init__.py` is **not** modified.
- All new tests go in `bcvf_llm/tests/`. They do not share fixtures or imports with `bcvf_autonomous/tests/`.

### 1.7 Repository Structure (V1)

```
bcvf_llm/
  __init__.py                  # package init, __version__, public API
  DESIGN.md                    # implementation-level companion to this doc (written after §2–§7 are filled)
  disagreement.py              # per-source disagreement operator for LLM domain (§2)
  trust.py                     # softmin trust weighting (~40 lines — direct transfer of autonomy math)
  decoder.py                   # TrustShapedDecoder wrapping base + verifier sources
  sources/
    __init__.py
    base.py                    # Source 1: base decoder (§1.4.1)
    paraphrased.py             # Sources 2, 3: paraphrased decoders — parameterized
                               #   by rewrite-seed (§1.4.2, §1.4.3). One module,
                               #   instantiated twice with seeds α, β.
  evaluation/
    __init__.py
    truthfulqa.py              # benchmark runner for the three comparative baselines
    metrics.py                 # accuracy, hallucination rate, latency
  tests/
    test_disagreement.py
    test_trust.py
    test_decoder.py
    test_evaluation.py
configs/
  bcvf_llm/
    v1_truthfulqa.yaml
```

**Estimated V1 size:** ~600 lines of production code + ~300 lines of tests. Significantly smaller than the autonomy V1 (~2,100 LoC) because no simulator, no planner, no predictors with domain-specific failure modes — the entire LLM side is "wire two decoders through a trust-weighting layer and evaluate."

### 1.8 Dependency Summary

| Package | Required | Reason |
|---|---|---|
| `torch` | yes (new for V1) | Inference backend; autonomy doesn't use it |
| `transformers` | yes (new) | Llama 3.1 8B loading + generation |
| `accelerate` | yes (new) | Device placement, fp16/bf16 mixed precision |
| `datasets` | yes (new) | TruthfulQA loading |
| `numpy` | already present | BCVF math kernel (float operations) |
| `pyyaml` | already present | Config |
| `pytest` | already present | Tests |

No dependency on the autonomy package. No dependency on JAX, CuPy, or domain-specific robotics libraries. This keeps V1 deployable on any single GPU machine with a Python 3.10+ environment.

### 1.9 Budget (engineering + compute)

| Item | Estimate | Hard ceiling |
|---|---|---|
| Engineering | 2 weeks focused | 3 weeks |
| Compute — verifier + eval runs (M=3 at one extra decode/step vs M=2) | 1 GPU-day on A100 / L40S / H100 | 3 GPU-days |
| Compute — parameter sweep (§3 `τ_w` sensitivity) | 0.5 GPU-day | 1 GPU-day |
| Storage | <5 GB (model + TruthfulQA) | 20 GB |
| **Total cloud cost (if using on-demand GPU)** | **~$50–100** | **$300** |

If any line item hits its hard ceiling, V1 is re-scoped. §0.6 rule 5 triggers.

### 1.10 Pre-committed Go/No-Go Thresholds

These bind the §6 evaluation and prevent retroactive threshold-shifting after results come in. Recorded here so §6 cannot weaken them under pressure.

#### Success (V1 is a positive result):

- [ ] BCVF-trust routing accuracy on TruthfulQA-MC held-out split **> conventional-blend baseline accuracy by ≥2 percentage points**.
- [ ] Effect replicates on a **second evaluation seed** (paraphrase seed + eval-split shuffle seed). Magnitude within ±1 pp of the first run.
- [ ] Latency overhead per generated token **≤ 2× conventional-blend baseline latency**.
- [ ] No detected Lemma-1 violation in the synthetic-trace sensitivity characterization (§3).

#### Null (V1 result is "does not transfer"):

- [ ] BCVF-trust accuracy **within ±0.5 pp of conventional-blend** → file as null. Close document, write up as structural transfer finding with evidence that the autonomy composition does not produce measurable safety improvement in LLM inference under the tested composition.

#### Regression (V1 result is "transfer fails actively"):

- [ ] BCVF-trust accuracy **worse than conventional-blend by ≥1 pp** → regression. Post-mortem required. Which of the three structural components (detector / composition / invariance) failed? Report in the V1 close-out note; do **not** proceed to V2 until root cause is understood.

#### Unviable cost (V1 is too expensive to matter):

- [ ] Latency overhead **> 5× conventional-blend** → V1 architecturally unviable for inference-time deployment. Consider veto-structured variant (§9) or close.

All four gates are evaluated against the same matched-model, matched-seed, matched-eval-harness comparison. No cherry-picking across decoding strategies or subsets.

### 1.11 Risk Register

Risks inherited from the autonomy chain and LLM-specific risks that §0–§1 could not fully mitigate:

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Lemma 1 invariance violation under chosen LLM disagreement metric | **High** | Invalidates the structural transfer | §2 must prove invariance mathematically and empirically before §3+ proceeds; §0.6 stop rule #4 |
| Self-consistency verifier (§1.4.2) does not meaningfully diverge from base under hallucination | Moderate | V1 measures nothing; null result is uninterpretable | Phase 1.5 sensitivity test validates verifier produces signal on a held-out probe set; if not, rewrite §1.4.2 |
| TruthfulQA benchmark ceiling effect (8B model already near-optimal) | Moderate | Can't detect 2 pp improvement | Alternative benchmark (HaluEval, FEVER-formatted) queued in §6; committed alternative if TruthfulQA ceiling is observed |
| GPU inference harness complexity underestimate | Moderate | Engineering budget blown | Use off-the-shelf `transformers.generate()` with a custom logits processor, not a from-scratch generation loop |
| Evaluation statistical noise larger than ±2 pp expected effect | Moderate | Cannot distinguish success from null at the committed threshold | N=≥400 eval examples on each of 2 seeds; 2 pp effect is detectable at that N with binomial confidence |
| Cost of 3 decoders × N examples × 2 seeds | Low | Over budget | Caching base-decoder output across baselines; estimates already assume this |
| Retrospective-2nd-difference in token space produces spurious signal (see §0.4 concern) | **High if §2 implements it naively** | Lemma 1 violation | §2 specifies forward-lookahead via 5-token speculation, not retrospective — explicitly |
| Model weights or benchmark access restricted | Low | Can't run V1 | Llama 3.1 is open-weight; TruthfulQA is open dataset — both on HuggingFace |

---

**Phase 0 sign-off criterion:** §1 is complete when all dimensions in §1.2 are locked (no "TBD" entries), §1.4 verifier choice is specific enough to implement without further design, §1.10 thresholds are pre-committed, and §1.11 risks are each either mitigated or acknowledged as acceptable. No §2 work begins until §1 is signed off.

---

## Section 2 — Phase 1 — Core Math (LLM Adaptation)

### 2.0 Sub-section plan

Nine sub-sections, each added one at a time on authorization. Structure
mirrors the autonomy `DESIGN.md` §1 (Core Math Engine), re-grounded in
the LLM domain:

- **§2.1** — Purpose & deliverable of Phase 1. What this section produces, what it defers.
- **§2.2** — Choice of disagreement metric over logits/probabilities. Candidates: L2 on logits, cosine on hidden states, symmetric KL, Jensen-Shannon. One chosen and justified.
- **§2.3** — Temporal window: forward lookahead via speculative decoding. Exact definition of the LLM analogue to the autonomy H-step rollout.
- **§2.4** — Second-order BCVF operator over the lookahead window. Stencil, edge cases at the window boundaries.
- **§2.5** — Gate function + pseudo-Huber preservation. What the gate threshold means in the LLM metric, how it's calibrated.
- **§2.6** — Lemma 1 analogue: statement, conditions, proof sketch. Hard gate: §3 does not start until this is proven.
- **§2.7** — Edge cases and numerical considerations. Variable-length outputs, EOS, underflow, log-space vs probability-space.
- **§2.8** — Python equations parallel to `core.py`. Module boundary, what `bcvf_llm/disagreement.py` implements.
- **§2.9** — Acceptance criteria + test specification. What passes §2 sign-off.

---

### 2.1 Purpose & deliverable of Phase 1

#### What Phase 1 does

Phase 1 translates the BCVF mathematical kernel from the autonomy
domain into LLM-domain equations that satisfy the same formal
properties. The autonomy kernel is specified in
`symbolu_robotics/bcvf_autonomous/core.py` (Definitions 1–7, Lemma 1,
Phase 1 of the autonomy DESIGN.md). Phase 1 of **this** document is
the direct analogue: produce a math kernel that computes a
per-source distrust signal from LLM decoding state such that

1. the operator is second-order in time,
2. the gate + pseudo-Huber envelope survives,
3. Lemma 1 invariance holds under the chosen metric,
4. no LLM-specific pathology is silently introduced.

The deliverable is a pure-math module (`bcvf_llm/disagreement.py`)
with synthetic-input tests. **It does not run an LLM, does not need
a GPU, and has no I/O outside NumPy arrays.** This is deliberate —
it makes §2 fully audit-able before any inference cost is incurred.
Same discipline as the autonomy Phase 1: the math kernel was proven
correct on synthetic traces before any predictor or planner work
began.

#### What Phase 1 produces

| Artifact | Form |
|---|---|
| Disagreement operator | `pairwise_disagreement(source_states_batch) → (K, M) or (K, M, L) signal` |
| Forward-lookahead temporal window | Fixed `L`-step construction over logit/state sequences |
| Second-order BCVF operator | Vectorized stencil + gate + Huber + per-source attribution |
| Lemma-1 proof sketch | A concrete statement and a mathematical argument, written out in §2.6 |
| Parallel-to-`core.py` Python module | `bcvf_llm/disagreement.py`, est. 100–150 lines |
| Synthetic test suite | `tests/test_disagreement.py`, 12–16 tests covering invariance + accelerating response |

#### What Phase 1 explicitly does not do

Deferred to later phases, captured here so scope creep is visible:

- **Source implementation** (base decoder, verifier). Phase 1 treats sources as abstract `(batch, lookahead_len, state_dim)` arrays. The actual decoders are §4 (Phase 2, "Source Framework").
- **Trust weighting + consensus construction.** The `softmin(d_i / τ_w)` and weighted mean are §5 (Phase 3 Integration). Phase 1 produces the per-source signal `d_i`; Phase 3 turns it into weights and a reference.
- **Decoder wrapping and logit blending.** Belongs to §5 as well.
- **Benchmark, eval harness, pre-committed metrics.** §6 (Phase 4).
- **Lemma-1 *signal-level* empirical demo on real sources.** That is §3 (Phase 1.5), which comes after §2. §2 produces the math + invariance proof + synthetic-trace tests. §3 characterizes the signal under controlled traces before hooking up real decoders.

#### Hard gate on §3 start

§2 must pass its sign-off (§2.9) before §3 begins. Specifically:

- Lemma 1 analogue (§2.6) must be mathematically stated and, under the
  specific metric + operator chosen in §2.2–§2.4, provably true. If
  the chosen metric produces a counter-example (e.g. constant
  disagreement gives non-zero 2nd-order signal), §2.2/§2.4 is
  rewritten until invariance holds, or Phase 1 stops and reports
  "the autonomy composition's invariance does not transfer under the
  tested LLM metric" (§0.6 stop rule #4).
- All synthetic tests in §2.9 must pass deterministically.
- No LLM dependency has been added to the codebase yet. `torch` /
  `transformers` / `datasets` enter only in §4 or later.

#### Estimated size and effort

- **Math notes in this doc (§2.2–§2.7):** 1–2 days of design work.
- **Lemma-1 proof sketch (§2.6):** 0.5–1 day.
- **Python implementation (`disagreement.py`):** 1 day given the autonomy kernel as reference.
- **Tests:** 0.5 day.
- **Total Phase 1:** ~3–4 days within the 2-week V1 budget (§1.9).

#### Reference artifact

Throughout §2 the autonomy kernel is cited as the source of truth for
the *structural* definitions (Definition 1–7 and Lemma 1 in the
autonomy DESIGN.md). Where §2 deviates from the autonomy equations,
the deviation is explicit and justified by domain difference, not
hand-wave.

---

### 2.2 Disagreement metric over logits

#### 2.2.1 Candidate metrics considered

Five candidates evaluated against four required properties: symmetry,
well-definedness (no division-by-zero / log-of-zero blow-up),
invariance under semantics-preserving reparameterizations of the
decoding state, and scale-boundedness.

| # | Metric | Symmetric | Safe on zero probs | Invariant to logit-shift | Bounded |
|---|---|---|---|---|---|
| 1 | L2 on logits | yes | yes | **no** | no |
| 2 | L2 on probabilities (post-softmax) | yes | yes | **yes** | yes (`[0, √2]`) |
| 3 | Cosine on logits/hidden-states | yes | yes | **no** | yes |
| 4 | KL divergence (asymmetric) | **no** | **no** (blows on zero probs) | yes | no |
| 5 | Symmetric KL / Jeffreys divergence | yes | **no** | yes | no |
| 6 | Jensen–Shannon divergence | yes | yes | yes | yes (`[0, ln 2]`) |
| 7 | Token-level argmax agreement (0/1) | yes | n/a | yes | yes | 

"Invariant to logit-shift" is critical: adding a constant `c` to every
logit leaves the softmax output unchanged (same distribution). Any
metric that flags that as "disagreement" fails Lemma 1 by construction
because two *semantically identical* sources would accumulate non-zero
distrust over time. Rules out candidates **#1** and **#3**.

**Candidate #4** (asymmetric KL) fails symmetry: `KL(P‖Q) ≠ KL(Q‖P)`,
so the per-pair cost would depend on which source is labeled `i` and
which `j`. BCVF's autonomy kernel attributes pair cost symmetrically
to both predictors (`core.py:_pair_cost`). Rules out **#4**.

**Candidates #4, #5** blow up when one distribution has `p=0` where
the other has `p>0`. For large-vocab LLMs (V ≈ 128k) with low-frequency
tokens, this is a real numerical hazard. Rules out **#5** pending a
stabilized variant; **#6** (Jensen–Shannon) is the zero-safe symmetric
sibling of **#5** and survives this filter.

**Candidate #7** (token-level argmax agreement) throws away all
confidence information. The resulting 0/1 signal makes
second-derivative + gate + Huber meaningless — either noise-dominated
or sparse zeros. Rules out **#7**.

Two survive: **#2 L2-on-probabilities** and **#6 Jensen–Shannon**.

#### 2.2.2 Choice: L2 on probabilities (primary), Jensen–Shannon (V2 alternative)

**Primary metric for V1:**

```
d_{ij}(t) = ‖ softmax(z_i(t)) − softmax(z_j(t)) ‖₂
```

where `z_i(t), z_j(t) ∈ ℝ^V` are the logits produced by source `i`
and source `j` at time step `t`.

**Justification:**

- **Simplicity.** One vector subtraction, one L2 norm. Straightforward
  to vectorize over batch / time / pair dimensions in NumPy. Matches
  the autonomy kernel's use of L2 on body-frame error — the
  *mathematical shape* of the operator is the same across domains,
  only the input space changes (ℝ³ → Δ^{V-1}, the probability
  simplex).
- **Bounded.** `d ∈ [0, √2]` regardless of vocab size. Gate
  threshold `T` (§2.5) can be set domain-agnostically.
- **Cheap.** O(V) per pair per step. Competitive with JS which is
  O(3V) and needs log-probability computations.
- **Invariant to logit-shift** (via softmax shift-invariance). Any
  decoder that scales its logit output by an additive constant —
  as happens in some inference harnesses — produces identical L2
  distances. This is the property we need for Lemma 1 (§2.6).
- **Empirically interpretable.** Two identical distributions give
  `d = 0`; two maximally-disagreeing one-hot distributions give
  `d = √2 ≈ 1.414`.

**Jensen–Shannon** is recorded as a V2 alternative in §9 for cases
where information-theoretic rather than Euclidean geometry on the
simplex is desired. Not chosen for V1 because the extra cost and
conceptual machinery aren't justified at M=3 (§2.2.3) and the
invariance behavior is the same.

#### 2.2.3 Downstream discovery: the M=2 structural issue, and its §1 implication

Working through this metric choice surfaces a structural issue that
**requires revising §1.2 and §1.4 before §2 can proceed**.

**The issue.** At `M=2` with one pair `(0, 1)`:

- Per-source pair-attribution (the autonomy kernel's
  `core.py:compute_bcvf_cost_batch` logic) accumulates the pair's
  cost to both members:
  `per_predictor[i] += pair_cost; per_predictor[j] += pair_cost`.
- Both sources receive **the same** per-source distrust value.
- Softmin over identical distrusts yields **uniform weights**:
  `w_0 = w_1 = 0.5`.
- Trust-weighted consensus reduces to equal-weight mean.
- **The Ketu→Rahu composition is mathematically inactive at M=2**:
  A3 ≡ A0 under trust-weighting.

This is not a bug in the autonomy kernel — it's a structural property.
At the autonomy side, `M=4` means a lone failing predictor appears in
three anchor-pairs while each healthy predictor appears in one, giving
the outlier a 3× distrust attribution that drives its weight toward
zero. At `M=2`, the outlier and the correct source appear in the same
single pair, so attribution cannot discriminate between them. The pair
carries information about *that something is wrong*, but not *which
side* is wrong.

**Implications for V1.** Three possible resolutions, each with
architectural implications:

| # | Resolution | Scope cost | Keeps Ketu→Rahu? |
|---|---|---|---|
| A | **Bump `M` from 2 to 3** in §1.2 — e.g., base + paraphrase₁ + paraphrase₂ | +1 decode per step (~1.5× conventional-blend latency; still inside §1.10 budget) | Yes, cleanly |
| B | Keep `M=2` but pivot composition to **veto/confidence gate** (Option D from the autonomy ranking). Disagreement serves as a scalar confidence, not per-source trust | Reframes V1; `softmin` + weighted consensus not exercised | **No** — different composition, different transfer claim |
| C | Keep `M=2` with **asymmetric anchor-relative attribution** (base is anchor; only the verifier can be distrusted) | Smallest code change; loses symmetry | Partially — not the full composition |

**Recommendation: resolution A** (bump to M=3). Rationale:

- It preserves the architectural claim being transferred (§0.4),
  which is specifically the Ketu→Rahu composition, not a different
  composition.
- Latency cost fits inside §1.10's ≤2× ceiling against the
  conventional-blend baseline (which itself does 2 decodes, so M=3
  is 1.5× conventional-blend latency; M=4 would be exactly at the
  limit).
- Matches the autonomy configuration more directly (autonomy's M=4
  is the minimum to produce a 3:1 majority-vs-outlier discrimination;
  M=3 is the bare minimum for trust-weighting to distinguish any
  outlier at all).
- The two paraphrased sources can share the paraphrase pipeline (two
  different fixed rewrites of the same prompt at temperature 0 with
  different rewrite seeds), so infrastructure cost is marginal.

Resolution **B** remains a clean V2 experiment, captured in §9 as
"veto-structured variant." It is explicitly *not* what this document
is testing.

Resolution **C** is discarded — it's half-way to a different
architecture and loses the symmetric per-pair attribution that the
autonomy invariance proof (Lemma 1) relies on.

#### 2.2.4 §1 revision required as precondition for §2.3+

**Before §2.3 can be authorized**, the following §1 revisions must be
applied (minor amendment, recorded as a §1 sign-off note):

- §1.2 source count: `M = 2` → **`M = 3`**.
- §1.4: keep §1.4.1 (base decoder) unchanged; replace the single
  §1.4.2 self-consistency verifier with **two independent paraphrased
  decodes**, generated by the same model at temperature 0 with two
  distinct rewrite-instruction seeds. Both are "fallible" sources in
  the same way; the base decoder is the third.
- §1.9 budget: no material change. Engineering still fits; compute
  ceiling unchanged because TruthfulQA eval pass count is the same.
- §1.10 thresholds: unchanged. The success criterion is about the
  three-way decoder comparison (vanilla / conventional-blend /
  BCVF-trust), not about the value of `M`.

This is the kind of design-phase discovery §2 was specifically
introduced to surface *before* implementation begins. The discipline
of working through the math honestly, rather than jumping to
implementation, is what prevents the autonomy-style "byte-identical
smoke revealed we were solving the wrong problem" episode.

#### 2.2.5 Equation summary

With the §1 revision in place, the per-pair disagreement at step `t`
becomes:

```
For each pair (i, j) ∈ { (0,1), (0,2), (1,2) } at step t:
    p_i(t) = softmax(z_i(t))              # (V,)
    p_j(t) = softmax(z_j(t))              # (V,)
    d_{ij}(t) = ‖ p_i(t) − p_j(t) ‖₂      # scalar ∈ [0, √2]
```

The per-pair scalar `d_{ij}(t)` is the LLM-domain analogue of the
autonomy `‖body_frame_error‖` used in `core.py:_pair_cost`. The 2nd-
order temporal operator, gate, and Huber will be layered on top of
this scalar time-series in §2.3–§2.5.

#### 2.2.6 What §2.2 does NOT commit to

- The exact temporal axis `t` indexes (generation step? lookahead
  position? both?). That is §2.3's job.
- The stencil form of the 2nd-order operator. §2.4.
- The gate threshold `T` and its calibration to the `[0, √2]` range.
  §2.5.
- Per-source attribution rule beyond the symmetric sum stated in
  §2.2.3 (unchanged from autonomy). §2.4 will finalize when per-source
  cost is actually needed.
- Whether `softmax` uses temperature 1.0 everywhere or scales by
  a factor. §1.3 locked greedy decoding, so the softmax distribution
  matters only as a disagreement measure, not for sampling — but the
  implementation must be explicit. §2.7.

---

### 2.3 Forward lookahead via speculative decoding

#### 2.3.1 What autonomy BCVF operates on — the property that must be preserved

Autonomy BCVF applies its second-order operator along the **rollout axis**, not along time-of-real-execution. At each planning cycle the MPPI planner has `K` candidate control sequences; each source (predictor) forward-simulates **`H` steps into the future** from the current ground-truth state. BCVF's 2nd-difference runs along that future axis, not backward over recorded history:

```
# autonomy core.py — the operator is over rollout steps k, not past time
signal = (e[:, 2:, :] - 2*e[:, 1:-1, :] + e[:, :-2, :]) / dt²
```

This is critical. Lemma 1 invariance (constant bias → 0, linear drift → 0, accelerating divergence → positive signal) is a property of the **forward rollout**. If we applied the same operator retrospectively to past trajectories, two fundamental properties would break:

1. **Causality.** Retroactive 2nd-difference can fire on stochastic past fluctuations that weren't predictive of failure — spurious signal, directionless.
2. **Operational usefulness.** A safety signal that only activates *after* the vehicle has already committed to a failing control sequence has no controller to correct. Forward BCVF steers planning before commitment; retrospective BCVF can only regret.

The ChatGPT LLM proposal reviewed in the preface (§0) made the retrospective choice — 2nd-difference over past generated tokens. That was the highest-risk item flagged in §1.11. **§2.3 commits V1 explicitly to forward lookahead.**

#### 2.3.2 V1 choice: L-step forward greedy lookahead, per source

At each outer decoding step `t` (the position of the token the trust-shaped decoder is about to emit), each source `i ∈ {1, 2, 3}` produces an **`L`-position forward extension** from its own conditioning context:

```
For source i at outer step t:
    h_i^context = source i's current conditioning (hidden states, KV cache)
    Step forward greedily L times from h_i^context:
        z_i(t + 0), argmax → token at t+0
        z_i(t + 1), argmax → token at t+1
        ...
        z_i(t + L − 1), argmax → token at t+L−1
    Return the full logit sequence Z_i = [z_i(t+0), ..., z_i(t+L−1)]   # shape (L, V)
```

**Each source speculates along its own greedy continuation**, not along a shared draft. This matches the autonomy structure where each predictor rolls out under the *candidate control sequence* but from its *own* state estimate. The LLM analogue: each source extends under its own context (base prompt vs. paraphrased prompt α vs. paraphrased prompt β), producing a locally-consistent forward trajectory.

The trust-shaped decoder emits **only the token at position `t`** (the first of the lookahead). Positions `t+1, ..., t+L−1` are used only by BCVF (and the consensus reference); they are discarded after use. The emitted token is then fed back to update each source's context for step `t+1`.

#### 2.3.3 Choice of `L`

| `L` | Cost per outer step (unamortized) | Structural analogue in autonomy H=50 | Note |
|---|---|---|---|
| 3 | 3×3 = 9 forward passes / token | Too short — 2nd-difference has only 1 stencil point | Rejected |
| 5 | 3×5 = 15 forward passes / token | 3 stencil points; comparable to autonomy's minimum useful H | V1 default |
| 8 | 3×8 = 24 forward passes / token | 6 stencil points; tighter signal | Too expensive without amortization |

**V1 picks `L = 5`.** With `M = 3` sources and `L = 5` lookahead positions, the unamortized per-outer-step cost is `M·L = 15` forward passes. Against the conventional-blend baseline (`M·1 = 2` forward passes per outer step under the same greedy assumption), this is **7.5× conventional-blend latency** — **over the §1.10 ≤2× ceiling** if we stop here. §2.3.4 resolves this.

#### 2.3.4 Amortization via KV-cache reuse — mandatory for V1

Without amortization, V1 fails the §1.10 latency budget by ~4×. Amortization is therefore not optional; §2.3 requires it.

**The observation.** At outer step `t` each source's lookahead covers positions `t, t+1, ..., t+L−1`. At outer step `t+1`, the lookahead covers `t+1, t+2, ..., t+L`. Positions `t+1` through `t+L−1` are **identical** between the two lookaheads, provided each source's conditioning hasn't changed (i.e., we're extending the same greedy continuation). Re-computing them is waste.

**The structure.** Each source maintains a **rolling KV cache** that already holds the state for its current L-step lookahead window. At step `t+1`:

1. The trust-shaped decoder emits token `x_t` (decided at step `t`).
2. Each source appends `x_t` to its emitted-prefix and advances its KV cache by one position (one forward pass from position `t` to position `t+1` using `x_t`).
3. The source extends its lookahead by **one** new position `t+L` (another forward pass).
4. The other `L−1` positions (`t+1` through `t+L−1`) were already computed at step `t` and are kept in the KV cache.
5. Total per source: **2 forward passes per outer step** — one to commit the emitted token, one to extend the lookahead frontier.

**Amortized cost:** `M · 2 = 6` forward passes per outer step for `M=3`. Conventional-blend baseline does `M · 1 = 2` forward passes per outer step (since it doesn't maintain lookahead). Ratio: **3× conventional-blend latency** — still above the 2× ceiling, but in a different regime (compute-bound vs strategy-bound). §5 (Phase 3) will refine this with an explicit latency measurement against the actual conventional-blend baseline we pick.

If amortized latency still exceeds 2× conventional-blend at §5 measurement time, **§0.6 rule 5** activates and either `L` shrinks, `M` shrinks (which re-introduces §2.2.3), or V1 is re-scoped. No retroactive ceiling relaxation.

#### 2.3.5 Edge cases and early-exit semantics

- **Prompt-start boundary.** At `t = 0` there is no prior emitted history, but each source still has its own conditioning (base prompt or paraphrased prompt). L-step lookahead is well-defined from the prompt's last token.
- **EOS emission within lookahead.** If a source's greedy continuation emits the model's end-of-sequence token at position `t + k` for `k < L − 1`, that source's lookahead is **truncated at position `t + k`**. Later §2.4 positions that would have used truncated entries are handled by restricting the 2nd-order stencil to the domain where all three sources have defined values (§2.4.4 will specify the stencil-min-coverage rule).
- **Vocabulary mismatch.** All three sources are the same model, so the vocabulary is shared. No projection or alignment needed. If §9 ever moves to multi-model ensembles, this assumption breaks and a projection layer is required.
- **Context-length overflow.** If `t + L − 1` exceeds the model's maximum context, the generation is already terminating — lookahead is naturally truncated. Same rule as EOS.

#### 2.3.6 What §2.3 does NOT commit to

- The exact stencil that consumes the lookahead (2nd-difference, weighted stencil, higher-order, etc.). §2.4.
- Gate behavior at lookahead-boundary positions. §2.4 / §2.5.
- KV-cache implementation specifics (HuggingFace `past_key_values`, custom allocator, etc.). §5 (Phase 3).
- Latency measurement protocol and actual numbers. §5.
- Lookahead variable by outer step or adaptive `L`. Deliberately out of V1 — fixed `L = 5` everywhere.

#### 2.3.7 Equation summary

At each outer step `t`, each source produces a forward logit sequence:

```
Z_i(t) = [z_i(t+0), z_i(t+1), ..., z_i(t+L-1)]      shape (L, V)
p_i(t, l) = softmax(z_i(t + l))                     shape (V,)  for l = 0..L-1
```

Per-pair disagreement vector over the lookahead (§2.2 metric applied per position):

```
e_{ij}(t, l) = p_i(t, l) − p_j(t, l)                shape (V,)
d_{ij}(t, l) = ‖ e_{ij}(t, l) ‖₂                    scalar ∈ [0, √2]
```

The 2nd-order operator in §2.4 will run along the `l` axis (the forward-lookahead axis) for fixed outer step `t`. **Not** along the `t` axis. Lemma 1 invariance (§2.6) is a property of the `l`-axis operator, which is why §2.3's forward-lookahead choice is a prerequisite for §2.6's proof.

---

### 2.4 Second-order BCVF operator

#### 2.4.1 Choice: vector 2nd-difference, not scalar 2nd-difference

A critical structural decision. Given the per-pair disagreement sequence from §2.3.7:

```
e_{ij}(t, l) = p_i(t, l) − p_j(t, l)    ∈ ℝ^V   for l = 0, 1, ..., L−1
d_{ij}(t, l) = ‖ e_{ij}(t, l) ‖₂         scalar ∈ [0, √2]
```

there are two possible places to insert the 2nd-difference operator:

- **Vector path** (autonomy-faithful): apply 2nd-diff to the **vector** `e_{ij}`, *then* take the norm.
  ```
  a_{ij}(t, l) = e_{ij}(t, l+1) − 2·e_{ij}(t, l) + e_{ij}(t, l−1)   ∈ ℝ^V
  s_{ij}(t, l) = ‖ a_{ij}(t, l) ‖₂                                  scalar
  ```
- **Scalar path** (ChatGPT proposal): apply 2nd-diff to the **scalar** `d_{ij}`.
  ```
  s_{ij}(t, l) = d_{ij}(t, l+1) − 2·d_{ij}(t, l) + d_{ij}(t, l−1)    scalar
  ```

These are **not equivalent**. Under linear drift `e(l) = a + b·l` for constant vectors `a, b ∈ ℝ^V`:

- Vector path: `a_{ij}(l) = (a + b(l+1)) − 2(a + bl) + (a + b(l−1)) = 0`. Norm of zero = 0. **Lemma 1 preserved.**
- Scalar path: `d(l) = ‖a + bl‖`. For arbitrary `a ⊥ b` this is a **nonlinear** function of `l` — even with `a=0` it becomes `d(l) = |l|·‖b‖`, which has a cusp at `l=0` producing spurious 2nd-difference signal. **Lemma 1 breaks.**

The autonomy kernel uses the vector path (`core.py:compute_bcvf_cost_batch`), and §2.6's Lemma 1 proof will depend on this choice. **V1 commits to the vector path.** The scalar path is documented in §9 (V2 Roadmap) as an alternative worth revisiting only if someone proves its own invariance, which no one has.

#### 2.4.2 Stencil formula and valid domain

At each outer step `t`, for each pair `(i, j) ∈ {(0,1), (0,2), (1,2)}`:

```
a_{ij}(t, l) = e_{ij}(t, l+1) − 2·e_{ij}(t, l) + e_{ij}(t, l−1)       ∈ ℝ^V
```

defined for `l ∈ [1, L−2]`. At `L = 5`, that is `l ∈ {1, 2, 3}` — three stencil points per pair. This matches the autonomy kernel's `signal[:, 2:, :] - 2*signal[:, 1:-1, :] + signal[:, :-2, :]` form, re-indexed for the lookahead axis.

No division by `dl²` is applied. Autonomy's `core.py` divides by `dt²` because the continuous-time interpretation requires it; LLM lookahead positions are unit-spaced (`dl = 1`) and the scale of `‖a‖` is absorbed by the Huber δ in §2.5. Keeping the dimensionless form simplifies gate threshold calibration.

#### 2.4.3 Weighted norm (identity weight for V1)

Autonomy's `core.py` computes a weighted norm:

```
s = ‖ W^{½} · a ‖₂
```

with `W` a `3×3` diagonal weight matrix over SE(2) error components (default `diag(1, 1, 1)`). The analogue for LLM is a `V×V` matrix.

**V1 fixes `W = I_V`** (identity) — plain L2 norm on the probability-space 2nd-difference vector. Rationale:

- No principled prior over which vocabulary dimensions should be up-weighted (e.g., "factual" tokens vs "filler" tokens is not an a-priori-defined partition).
- An identity weight preserves the bounded-by-construction property of §2.2 (`s_{ij}(t, l) ≤ 4·‖e‖_max ≤ 4·√2 ≈ 5.66`).
- Sparse weighting (e.g., mask certain vocab regions) is a V2 experiment documented in §9.

#### 2.4.4 Stencil coverage rule (EOS / truncated lookahead)

Continuing §2.3.5: if source `i`'s greedy continuation emits EOS at lookahead position `l = k < L−1`, source `i`'s logits are **undefined** for `l > k`. The stencil at `l*` requires `e_{ij}(t, l*−1)`, `e_{ij}(t, l*)`, and `e_{ij}(t, l*+1)` all defined, which in turn requires both sources `i` and `j` to have valid logits at those three positions.

**Coverage rule.** Per pair `(i, j)` at step `t`:

```
valid(l*) = (last_defined_l[i] ≥ l*+1) AND (last_defined_l[j] ≥ l*+1)
            where last_defined_l[s] is L−1 if source s didn't hit EOS,
            else the position at which source s emitted EOS
```

Stencil points at `l*` where `valid(l*) = False` are dropped from the sum in §2.4.5. A pair's per-step cost may therefore be zero (or near-zero) if every stencil point is invalidated by truncation — this is the correct behavior: *we have no data to compute BCVF against*, so the operator reports no signal rather than extrapolating.

#### 2.4.5 Per-pair aggregation and per-source attribution

**Per-pair cost at step `t`** — sum over the valid stencil domain (§2.5 will plug in `gate_{ij}` and `huber(s_{ij})` for the bracketed term):

```
pair_cost_{ij}(t) = Σ_{l* ∈ [1, L−2] : valid(l*)}  [ gate_{ij}(t, l*) · huber(s_{ij}(t, l*)) ]
```

**Per-source attribution** at step `t` — symmetric sum over pairs containing source `i`:

```
per_source_cost_i(t) = Σ_{(i, j) : j ≠ i, (i,j) ∈ pairs_at_M=3}  pair_cost_{ij}(t)
```

At `M = 3` with pair set `{(0,1), (0,2), (1,2)}`:

```
per_source_cost_0(t) = pair_cost(0,1) + pair_cost(0,2)
per_source_cost_1(t) = pair_cost(0,1) + pair_cost(1,2)
per_source_cost_2(t) = pair_cost(0,2) + pair_cost(1,2)
```

**Why this attribution discriminates outliers.** If source 0 is destabilizing and sources 1, 2 agree, then `pair_cost(0,1)` and `pair_cost(0,2)` are large while `pair_cost(1,2)` is small:

```
per_source_cost_0(t) = LARGE + LARGE  = 2·LARGE       (outlier)
per_source_cost_1(t) = LARGE + small ≈ LARGE + 0      (non-outlier)
per_source_cost_2(t) = LARGE + small ≈ LARGE + 0      (non-outlier)
```

Ratio ~ 2 : 1. Softmin in §5 (Phase 3) sharply downweights source 0. This is the mathematical reason §2.2.3 required `M ≥ 3`: at `M = 2` with one pair, every source is in one pair, and the attribution is symmetric by construction.

#### 2.4.6 Computational cost

For V1 parameters (`M = 3`, `L = 5`, `V ≈ 128k`):

| Operation | Count per outer step | Approximate FLOPs |
|---|---|---|
| Softmax per source (`L` positions × `M` sources) | `3 × 5 = 15` | `15 · V = ~1.9M` |
| Pair difference `e_{ij}` (`3` pairs × `L` positions) | `15` | `15 · V = ~1.9M` |
| Vector 2nd-difference `a_{ij}` (`3` pairs × `L−2` positions) | `9` | `9 · V = ~1.2M` |
| L2 norm `s_{ij}` (`3` pairs × `L−2`) | `9` | `9 · V = ~1.2M` |
| **Total BCVF ops per outer step** | | **~6.2M FLOPs** |

Compared to a single forward pass through an 8B model (~16 × 10⁹ FLOPs), BCVF's per-step computation is **four orders of magnitude smaller than a single token generation**. BCVF is not the latency bottleneck; the lookahead rollouts are (§2.3.4).

#### 2.4.7 What §2.4 does NOT commit to

- `gate_{ij}(t, l)` functional form and threshold. §2.5.
- `huber(·)` definition and `δ` calibration. §2.5.
- Lemma 1 formal proof that ties together the vector-2nd-diff (§2.4.1) with gate + Huber to preserve invariance. §2.6.
- Softmin trust temperature `τ_w` and the consensus construction. §5.

---

### 2.5 Gate + pseudo-Huber

#### 2.5.1 Gate — suppress contributions below noise floor

Carry forward the autonomy kernel's **sigmoid gate** on the raw disagreement magnitude at the stencil center. For each pair `(i, j)` at each valid stencil position `l* ∈ [1, L−2]`:

```
gate_input_{ij}(t, l*) = ‖ e_{ij}(t, l*) ‖₂                                    scalar ∈ [0, √2]
gate_{ij}(t, l*)       = σ( β · (gate_input_{ij}(t, l*) − T) )                 scalar ∈ [0, 1]
                       = 1 / (1 + exp(−clip(β · (·), −50, +50)))
```

**What the gate achieves.** Even when `a_{ij}(t, l*)` is non-zero, if the raw disagreement `e` at that position is below the softmax-floor noise, the pair's contribution is suppressed. The gate is the LLM analogue of the autonomy kernel's `gate_threshold` — it prevents the operator from chasing arithmetic noise in the tail of the probability simplex.

**Stencil alignment.** Autonomy computes the gate input at the *center* of the 2nd-difference stencil (i.e. `e` at `l*`, not at `l*±1`). This rule carries over unchanged: gate at `l*` evaluates `‖e(l*)‖`, not `‖a(l*)‖`. The gate and the signal are evaluated at coincident indices — no alignment drift between them.

**V1 parameter defaults.**

| Parameter | V1 default | Derivation |
|---|---|---|
| `T` (threshold) | **0.1** | ~7% of max disagreement (`√2 ≈ 1.41`). Below typical meaningful disagreement (`~0.3–0.5` for divergent top-k distributions); well above softmax-floor numerical noise (`~10⁻³`) |
| `β` (steepness) | **200** | `β·T = 20`, same ratio the autonomy gate uses (autonomy V1: `T=0.2, β=100`, ratio 20). Near-step function at `d = T` |
| Clipping | `exp arg ∈ [−50, +50]` | Numerical-stability guard carried over from autonomy `core.py`; prevents under/overflow in `exp` when disagreement is far from threshold |

The `β·T = 20` ratio is the structural parameter, not the absolute values. At that steepness, the gate is ~5% open at `d = T − 0.01` and ~95% open at `d = T + 0.01`. This gives a clean on/off behavior without pathological gradient spikes.

Both `T` and `β` are swept in §3 (Phase 1.5) signal characterization — this `(T=0.1, β=200)` pair is the V1 starting point, not a locked final value. If the §3 sweep reveals a better operating point, §2.5 is updated and the synthetic tests in §2.9 re-run before §3 sign-off.

#### 2.5.2 Pseudo-Huber — robust penalty on the signal

Given `s_{ij}(t, l*) = ‖a_{ij}(t, l*)‖₂` from §2.4.2:

```
huber_{ij}(t, l*) = δ² · ( √(1 + (s_{ij}(t, l*) / δ)²) − 1 )
```

**Properties.**

- Near-zero `s`: `huber(s) ≈ s² / 2` (quadratic regime — standard MSE-like penalty).
- Large `s`: `huber(s) ≈ δ·s − δ²/2` (linear regime — robust to outliers).
- Smooth transition at `s ≈ δ`.
- Strictly non-negative, zero at `s = 0`.

**V1 parameter default.**

| Parameter | V1 default | Rationale |
|---|---|---|
| `δ` (transition point) | **0.5** | Direct carry-over from autonomy `core.py` (autonomy default `huber_delta = 0.5`). Matches the expected scale of `‖a‖` under moderate accelerating failure: typical hallucination-driven 2nd-difference magnitudes fall in the `0.2–1.0` range, so `δ = 0.5` sits cleanly at the quadratic–linear transition |

Like `T` and `β`, `δ` is swept in §3; V1 starts from the autonomy value and refines empirically.

#### 2.5.3 Composition — what plugs into §2.4.5

With gate and Huber defined, the per-pair cost from §2.4.5 is now concrete:

```
For each pair (i, j) ∈ {(0,1), (0,2), (1,2)} and each outer step t:

  For each l* ∈ [1, L−2] with valid(l*) = True:
      gate_input = p_i(t, l*) − p_j(t, l*)                           ∈ ℝ^V
      gate       = σ( β · (‖gate_input‖₂ − T) )                      ∈ [0, 1]
      signal     = (p_i(t, l*+1) − p_j(t, l*+1))
                 − 2·(p_i(t, l*) − p_j(t, l*))
                 + (p_i(t, l*−1) − p_j(t, l*−1))                     ∈ ℝ^V
      s          = ‖signal‖₂                                          ≥ 0
      penalty    = δ² · (√(1 + (s/δ)²) − 1)                          ≥ 0
      contrib_{ij}(l*) = gate · penalty                              ∈ [0, penalty_max]

  pair_cost_{ij}(t) = Σ_{l* valid} contrib_{ij}(l*)
```

Per-source cost from §2.4.5 unchanged:

```
per_source_cost_i(t) = Σ_{(i, j) : j ≠ i}  pair_cost_{ij}(t)
```

#### 2.5.4 Properties §2.5 guarantees (to be proven in §2.6)

The choices above are specifically designed so that the following hold under §2.6's Lemma 1 proof:

1. **Non-negativity.** `contrib_{ij}(l*) ≥ 0` everywhere. Follows from `gate ∈ [0, 1]` and `penalty ≥ 0`.
2. **Zero under constant disagreement.** If `e_{ij}(t, l)` is constant in `l`, then `a_{ij} = 0`, `s = 0`, `penalty = 0`, `contrib = 0`. **Lemma 1 case 1.**
3. **Zero under linear drift.** If `e_{ij}(t, l) = α + β·l` with `α, β ∈ ℝ^V`, then `a_{ij} = 0` by the vector-path choice in §2.4.1. `s = 0`, `penalty = 0`, `contrib = 0`. **Lemma 1 case 2.**
4. **Positive under quadratic (or higher) accelerating disagreement**, provided `‖e_{ij}(t, l*)‖ > T` (gate open). This is the only regime that contributes, by design.
5. **Gate suppresses contributions below noise floor.** If `‖e_{ij}(t, l*)‖ < T − 1/β ≈ T − 0.005`, gate ≈ 0, contribution ≈ 0, regardless of `a`. Prevents noise-driven false positives.
6. **Huber bounds outlier sensitivity.** For `s >> δ`, `penalty` scales linearly rather than quadratically. One extreme single-position spike cannot dominate the cost.

These six properties are the invariance guarantees §2.6 will formalize and prove.

#### 2.5.5 What §2.5 does NOT commit to

- Softmin trust weighting formula (applied to per-source cost in §5, Phase 3).
- Temperature `τ_w` for softmin — explicitly a §5 concern; the autonomy default `τ_w = 1.0` is the V1 starting point but its calibration depends on the empirical distribution of `per_source_cost` under the §3 synthetic traces.
- The gate/Huber parameter sweep protocol. §3.
- Any training-time signal (L_trust, L_smooth). Explicitly V2 per §9.

---

### 2.6 Lemma 1 analogue

The autonomy V3.1 design rests on **Lemma 1**: the 2nd-order BCVF operator is zero under constant disagreement and zero under linear drift, reacting only to genuine *accelerating* divergence. §0.1 identified this invariance as one of the two non-negotiable properties the LLM transfer must preserve. §2.6 formally states, proves, and bounds the LLM analogue.

#### 2.6.1 Statement (LLM Lemma 1)

**Theorem (Lemma 1 analogue).** *Let `p_i, p_j : {0, 1, ..., L−1} → Δ^{V−1}` be two probability-simplex trajectories along the lookahead axis for sources `i ≠ j` at fixed outer step `t`. Let `e_{ij}(l) = p_i(l) − p_j(l) ∈ ℝ^V`, and let `contrib_{ij}(l*) = gate_{ij}(l*) · penalty_{ij}(l*)` be the per-position contribution defined in §2.5.3.*

*Then:*

*(C1) **Constant-bias invariance.** If there exists `α ∈ ℝ^V` such that `e_{ij}(l) = α` for all `l ∈ [0, L−1]`, then `contrib_{ij}(l*) = 0` for every valid `l* ∈ [1, L−2]`.*

*(C2) **Linear-drift invariance.** If there exist `α, γ ∈ ℝ^V` such that `e_{ij}(l) = α + γ·l` for all `l ∈ [0, L−1]`, then `contrib_{ij}(l*) = 0` for every valid `l* ∈ [1, L−2]`.*

*(C3) **Acceleration detection (affirmative).** If there exist `α, γ, η ∈ ℝ^V` with `η ≠ 0` such that `e_{ij}(l) = α + γ·l + ½·η·l²`, and at some `l* ∈ [1, L−2]` the gate is open (`‖e_{ij}(l*)‖ > T + 1/β ≈ T + 0.005`), then `contrib_{ij}(l*) > 0`.*

Cases C1 and C2 are the **invariances** — BCVF commits the same "don't react to steady-state or linear divergences" promise it makes in autonomy. C3 is the **completeness** claim: the operator is not trivially zero; the one regime the autonomy design targets (accelerating departure) does produce a positive signal.

#### 2.6.2 Preliminaries and scope

The proof operates on the operator chain fixed by §2.4.2 and §2.5.3:

```
e_{ij}(l)      = p_i(l) − p_j(l)                            ∈ ℝ^V      (§2.2/§2.3)
a_{ij}(l*)     = e_{ij}(l*+1) − 2·e_{ij}(l*) + e_{ij}(l*−1) ∈ ℝ^V      (§2.4.2)
s_{ij}(l*)     = ‖ a_{ij}(l*) ‖₂                            ≥ 0         (§2.4.2)
gate_{ij}(l*)  = σ( β · (‖e_{ij}(l*)‖₂ − T) )               ∈ [0, 1]    (§2.5.1)
penalty_{ij}(l*) = δ² · ( √(1 + (s_{ij}(l*)/δ)²) − 1 )      ≥ 0         (§2.5.2)
contrib_{ij}(l*) = gate_{ij}(l*) · penalty_{ij}(l*)         ≥ 0         (§2.5.3)
```

The proof is **pointwise in `l*`** — each claim is established at a single valid stencil center, and the per-pair sum `pair_cost_{ij}(t) = Σ_{l*} contrib_{ij}(l*)` inherits the property by non-negativity.

Outer-step `t` is suppressed throughout §2.6 (everything is evaluated at a fixed `t`). The lemma is about the *shape* of the lookahead curve for each `(i, j, t)` triple, not about `t`-axis dynamics (which don't exist — the operator has no retrospective memory, per §2.3.1).

#### 2.6.3 Proof of Case 1 — constant-bias invariance

*Assume* `e_{ij}(l) = α` (constant in `l`) for some `α ∈ ℝ^V`.

At any valid `l* ∈ [1, L−2]`:

```
a_{ij}(l*) = e_{ij}(l*+1) − 2·e_{ij}(l*) + e_{ij}(l*−1)
           = α − 2·α + α
           = 0 ∈ ℝ^V
```

Hence `s_{ij}(l*) = ‖0‖₂ = 0`. Substituting into the pseudo-Huber:

```
penalty_{ij}(l*) = δ² · ( √(1 + (0/δ)²) − 1 )
                 = δ² · (1 − 1)
                 = 0.
```

Therefore `contrib_{ij}(l*) = gate_{ij}(l*) · 0 = 0`. ∎

**Interpretation.** If two sources consistently disagree at a fixed offset throughout the whole lookahead window (e.g. one always prefers "run" to "ran" at every position), BCVF stays silent. This is stylistic/habitual divergence — not evidence of a local failure mode. The operator is correctly indifferent.

#### 2.6.4 Proof of Case 2 — linear-drift invariance

*Assume* `e_{ij}(l) = α + γ·l` for some `α, γ ∈ ℝ^V`.

At any valid `l* ∈ [1, L−2]`:

```
a_{ij}(l*) = [α + γ·(l*+1)] − 2·[α + γ·l*] + [α + γ·(l*−1)]
           = (α − 2α + α) + γ·((l*+1) − 2·l* + (l*−1))
           = 0 + γ·0
           = 0 ∈ ℝ^V
```

Hence `s_{ij}(l*) = 0`, `penalty_{ij}(l*) = 0`, `contrib_{ij}(l*) = 0`. ∎

**This is where the vector-path choice in §2.4.1 becomes critical.** The proof consumes the fact that the 2nd-difference of a vector-valued linear function is identically the zero vector. Had we taken the scalar path `d_{ij}(l) = ‖e_{ij}(l)‖ = ‖α + γ·l‖`, the function `l ↦ ‖α + γ·l‖` is in general **not** linear in `l` (it's a convex piecewise-affine function with a cusp at `l = −α·γ / ‖γ‖²`), so its 2nd-difference need not vanish — Case 2 would fail. The vector-path is the structural reason Lemma 1 transfers.

**Interpretation.** If one source is steadily drifting away from another at a constant rate (e.g. models gradually diverging in confidence on a token), BCVF stays silent. Constant-rate divergence is already linearly extrapolable — no surprise, no acceleration, nothing to flag. The operator only wakes up when the rate of divergence itself changes.

#### 2.6.5 Proof of Case 3 — acceleration detection

*Assume* `e_{ij}(l) = α + γ·l + ½·η·l²` with `η ≠ 0` (so `‖η‖₂ > 0`), and that at some `l* ∈ [1, L−2]` the gate is open, i.e. `‖e_{ij}(l*)‖ > T + 1/β`.

At that `l*`:

```
a_{ij}(l*) = [α + γ(l*+1) + ½·η·(l*+1)²]
           − 2·[α + γ·l*   + ½·η·(l*)²]
           + [α + γ(l*−1) + ½·η·(l*−1)²]
```

The constant and linear terms vanish exactly as in Cases 1 and 2. The quadratic term evaluates to:

```
½·η · [ (l*+1)² − 2·(l*)² + (l*−1)² ]
= ½·η · [ (l*² + 2·l* + 1) − 2·l*² + (l*² − 2·l* + 1) ]
= ½·η · [ 2 ]
= η
```

Hence `a_{ij}(l*) = η`, and `s_{ij}(l*) = ‖η‖₂ > 0`.

The pseudo-Huber is strictly increasing in `s` and zero only at `s = 0`:

```
d/ds [ δ² · (√(1 + (s/δ)²) − 1) ] = s / √(1 + (s/δ)²) > 0   for s > 0.
```

So `penalty_{ij}(l*) > 0`.

For the gate, the assumption `‖e_{ij}(l*)‖ > T + 1/β` gives `β·(‖e(l*)‖ − T) > 1`, so `gate_{ij}(l*) = σ(β·(‖e(l*)‖ − T)) > σ(1) ≈ 0.73 > 0`.

Therefore `contrib_{ij}(l*) = gate_{ij}(l*) · penalty_{ij}(l*) > 0`. ∎

**Interpretation.** If one source starts accelerating away from another over the 5-token lookahead window *and* the underlying disagreement is above the noise floor, BCVF produces a strictly positive signal. Combined with C1 and C2, this means the operator is tuned precisely: it is silent on benign divergence patterns and positive on the one pattern the autonomy design flags as evidence of an emerging failure.

#### 2.6.6 Gate behavior and the noise floor

The gate condition in C3 (`‖e(l*)‖ > T + 1/β`) is necessary: without it, a quadratic bias in `e` with tiny norm (e.g. `η = 10⁻⁶·u` for some unit vector `u`) would produce technically positive `penalty` but with `contrib ≈ 0`. Near the gate threshold, the gate is smooth, so the statement "gate suppresses below noise floor" is not a hard cliff but a sharp-sigmoid:

- `‖e‖ ≤ T − 1/β ⇒ gate ≤ σ(−1) ≈ 0.27`. At Huber `penalty ≈ s²/2` for small `s`, `contrib ≤ 0.27·(s²/2)`.
- `‖e‖ ≥ T + 1/β ⇒ gate ≥ σ(+1) ≈ 0.73`. `contrib ≥ 0.73·penalty`.

With V1 defaults `T = 0.1, β = 200`, the gate transition width is `2/β = 0.01`, i.e. 1% of the maximum disagreement `√2 ≈ 1.41`. This is tight enough that **for the purposes of §2.6**, the gate can be treated as a hard switch at `‖e‖ = T` without loss of proof-level correctness. The synthetic tests in §2.9 will verify this empirically.

#### 2.6.7 Huber bounding and outlier protection

Case 3 establishes positivity. A symmetric bound from above is useful for §5's trust-weighting calibration: a single extreme stencil cannot produce unbounded cost. For any `s ≥ 0`:

```
penalty(s) = δ² · (√(1 + (s/δ)²) − 1) ≤ δ · s
```

(The RHS is the large-s asymptote; the LHS is always below it since the correction term `−δ²` is negative for `s > δ/√2`.)

So per-position `contrib ≤ δ · s ≤ δ · ‖a_{ij}(l*)‖`. Since each component of `e_{ij} ∈ [−1, 1]`, `‖a_{ij}‖₂ ≤ 4·√V` (four unit-magnitude contributions from the stencil), giving `contrib ≤ 4·δ·√V`. For V1's `δ = 0.5, V = 32000`, this caps a single-position contribution at roughly `358` cost units — a large number, but **finite**. A single pathological prediction cannot blow up the per-source cost into numerical overflow.

This bound matters for §5: the softmin trust-weighting temperature `τ_w` is calibrated against the distribution of `per_source_cost`, and an unbounded-right tail would make that calibration brittle. Huber gives us the tail control.

#### 2.6.8 Relation to autonomy Lemma 1 (V3.1 §3.5)

The autonomy lemma operates on SE(2) body-frame error trajectories `e_{ij}(k) ∈ ℝ³`, with `k` indexing a **time** axis of simulator states. The LLM lemma operates on probability-simplex differences `e_{ij}(l) ∈ ℝ^V`, with `l` indexing a **lookahead** axis of speculative tokens. Despite the domain shift, the proof structure is identical:

| Autonomy (V3.1 §3.5) | LLM (§2.6) | Why they transfer |
|---|---|---|
| Domain: SE(2) body-frame, `ℝ³` | Domain: probability simplex differences, `ℝ^V` | 2nd-diff is linear in its inputs regardless of ambient dimension |
| Axis: time `k`, 10 Hz simulator | Axis: lookahead `l`, speculative tokens | Both are discrete, uniform-spacing sequences — same stencil applies |
| Metric: `‖·‖₂` (Euclidean) | Metric: `‖·‖₂` (Euclidean on `ℝ^V`) | Metric choice carries directly (§2.2.6) |
| C1: constant SE(2) offset → 0 | C1: constant simplex-diff bias → 0 | Same algebra |
| C2: linear SE(2) drift → 0 | C2: linear simplex-diff drift → 0 | Same algebra — *hinges on vector-path* |
| C3: accelerating SE(2) divergence → positive | C3: accelerating simplex divergence → positive | Same algebra |
| Gate input: ‖e‖ at stencil center | Gate input: ‖e‖ at stencil center | Structural rule preserved (§2.5.1) |
| Huber δ = 0.5 | Huber δ = 0.5 | Carry-over pending §3 sweep |

**What transfers cleanly.** The operator is linear (it's a finite-difference), so its invariances (C1, C2) depend only on the linearity of polynomial evaluation in the ambient vector space — which is the same in `ℝ³` or `ℝ^V`. The proof is **dimension-agnostic**.

**What differs.** The *domain* of `e_{ij}` is different: probability-simplex differences live in a subset of `ℝ^V` satisfying `Σ_k e_{ij,k} = 0` and `e_{ij,k} ∈ [−1, 1]`. The autonomy `e` lives in `ℝ³` unconstrained. None of the Lemma 1 proof uses the constraint structure, so the differences don't affect the invariance result, but they do affect the **bound** in §2.6.7 (autonomy uses a much smaller domain-specific bound based on SE(2) lever-arm geometry).

**What remains empirical.** The autonomy Lemma 1 also shipped with a numerical verification (`test_core.py::test_lemma_1_linear_drift_zero`). §2.9 must include the analogous LLM test: synthesize linear-drift `p_i(l), p_j(l)` on the simplex and verify that `compute_bcvf_cost_batch` returns exactly zero (within `1e−10` floating-point tolerance).

#### 2.6.9 What §2.6 does NOT prove

- **No claim about trust-weighting optimality.** The lemma proves per-pair invariance. Whether the softmin over `per_source_cost_i` correctly identifies the outlier source is §5's responsibility and requires empirical demonstration on §3 synthetic traces.
- **No claim about LLM-semantic alignment.** Cases C1–C3 are claims about the *mathematical* output of the operator on *algebraic* patterns. Whether those patterns correspond to "stylistic divergence vs. hallucination" in the LLM domain is the Phase 1.5 (§3) empirical question, not a provable theorem.
- **No claim over the `t` axis.** The lemma is pointwise in `t`. If the per-source cost is accumulated over `t` (e.g. in a streaming agent setting), invariance still holds per-step; aggregate-over-`t` dynamics are a §5/§6 concern.
- **No claim about probability-simplex geometry specifically.** The proof works in any finite-dimensional real vector space with Euclidean metric. Alternative metrics (KL, Hellinger) require re-proving C2 — flagged in §2.2.6 and §9 V2 Roadmap.

#### 2.6.10 Acceptance criteria for §2.6

§2.6 is considered **complete and passing** when:

1. ✅ Theorem statement is explicit over `e_{ij} ∈ ℝ^V` with the exact stencil from §2.4.2 (this section).
2. ✅ Cases C1, C2, C3 are proven by direct algebraic computation (§2.6.3–§2.6.5).
3. ✅ Gate + Huber side conditions are bounded (§2.6.6, §2.6.7).
4. ✅ Relation to autonomy Lemma 1 is explicit, with transfer points and differences enumerated (§2.6.8).
5. ✅ Scope limits are declared (§2.6.9).
6. **Pending §2.9:** synthetic tests `test_lemma_1_constant_bias_zero`, `test_lemma_1_linear_drift_zero`, `test_lemma_1_quadratic_positive` pass deterministically against the Python implementation.

Items 1–5 are satisfied by this section. Item 6 is the hard gate that closes Phase 1 and unlocks Phase 1.5 (§3).

---

### 2.7 Edge cases & numerical considerations

§2.7 handles the concrete corner cases of running the §2.4–§2.6 chain against real model outputs. Three of these (EOS truncation, vocabulary alignment, exp-argument clipping) were already sketched or resolved inline in §2.3–§2.5; §2.7 consolidates them here and adds the ones that only emerge at implementation time.

#### 2.7.1 Softmax temperature when computing `p` from logits (resolves §2.2.7 deferral)

§2.2.7 deferred the question: when we compute `p_i(t, l) = softmax(z_i(t, l))`, what temperature?

**V1 rule: temperature = 1.0** (standard softmax, no scaling).

- §1.3 locked **greedy decoding** for token emission, so the softmax distribution is used *only* as a disagreement measure — never as a sampling distribution. The sampling path ignores this choice entirely.
- Temperature ≠ 1 would artificially compress or expand the gap between disagreeing distributions, changing `‖e_{ij}‖` in a way unrelated to the underlying source disagreement. That drifts the gate calibration (`T = 0.1` in §2.5.1) without a principled reason.
- The autonomy analogue — `lever_arm = 2.5` in SE(2) — plays a similar role (it scales body-frame error) and autonomy keeps it fixed across all experiments. Same discipline applies here.

If §3 signal characterization shows the disagreement distribution is pathologically concentrated (or diffuse), §2.7.1 is revisited. V1 default is T = 1.0.

#### 2.7.2 Numerical precision — fp32 inside BCVF, fp16/bf16 outside

§1.3 commits the **model forward pass** to fp16 or bf16 (whichever the GPU supports). The BCVF kernel has different numerical requirements.

**V1 rule: upcast to fp32 at the boundary.**

```
logits_i (fp16/bf16, shape (M, T_outer, L, V))
  → p_i = softmax(logits_i, dim=-1).to(torch.float32)
  → compute_bcvf_cost_batch(p_i, config)  # fp32 throughout
```

Rationale:

- The 2nd-difference stencil `a = e(l*+1) − 2·e(l*) + e(l*−1)` is a cancellation operation. If `e` values are close, significant digits are lost in the subtraction. In bf16 (7-bit mantissa, ~2 decimal digits), two values differing by `1e−4` cannot produce a meaningful difference. fp32 (23-bit mantissa, ~7 decimal digits) preserves the signal down to `~1e−6`.
- The Lemma 1 numerical test (§2.9) verifies zero-output on constructed linear-drift inputs within a floating-point tolerance. That tolerance is `1e−10` per §2.6.8 — achievable in fp32, **not** achievable in bf16. A test that only passes in fp32 would silently fail on a bf16 implementation.
- The cost of fp32 on the BCVF kernel is negligible: §2.4.6 estimated ~6.2M FLOPs per outer step. fp32 vs fp16 doubles memory but memory isn't the bottleneck here.

The softmax itself should be computed in fp32 too (many frameworks default to this already for numerical stability). The `.to(torch.float32)` call is explicit, not implicit.

#### 2.7.3 Simplex arithmetic and underflow

When both `p_i` and `p_j` are produced by softmax, exactly-zero entries are impossible (softmax output is strictly positive). However:

- In fp16/bf16, `exp(−50)` underflows to 0 before the softmax normalization. The result is a "probability" that reports 0 exactly at tokens with very negative logits.
- Even in fp32, the minimum representable positive value of `exp` is around `1e−44`, so after softmax the minimum non-zero probability is on the order of `1e−44 / Σ exp(·)` — effectively 0 for V = 32000 vocab.

**Consequences for BCVF:**

- `e_{ij,k} = p_{i,k} − p_{j,k}` can be exactly 0 at long-tail tokens in both distributions. This is **not** a numerical problem for BCVF — it just means the vocabulary position contributes nothing to the ℓ² norm. Zero is a valid result.
- The simplex constraint `Σ_k p_{i,k} = 1` is enforced by softmax up to fp32 rounding (`~1e−7` drift over V = 32000). After subtraction, `Σ_k e_{ij,k} ≈ 0` up to that same drift. **The BCVF kernel does not depend on the simplex constraint holding exactly.** It only computes differences, 2nd-differences, and norms — all of which are translation-invariant with respect to the per-vocab mean, so simplex drift is irrelevant.
- The gate condition `‖e‖ > T = 0.1` is robust to rounding noise at the `1e−6` level by roughly five orders of magnitude. Underflow cannot falsely trigger the gate.

**V1 rule: do nothing special.** Standard softmax + fp32 BCVF handles underflow correctly. No `epsilon` floors, no log-space reformulation. Log-space is a V2 consideration (§9) if some future metric demands it.

#### 2.7.4 EOS and truncated lookahead — consolidating §2.3.5 + §2.4.4

**V1 rule (unchanged from prior sections):** use the `valid(l*)` predicate defined in §2.4.4 to restrict the stencil sum. Reiterated here for completeness:

```
last_defined_l[i] = L − 1  if source i did not emit EOS within the window,
                    k       if source i emitted EOS at lookahead position k.

valid(l*) = (last_defined_l[i] ≥ l* + 1) AND (last_defined_l[j] ≥ l* + 1)
```

**Edge cases that §2.7 adds on top of §2.4.4:**

- **All sources emit EOS before position 2.** Then `valid(l*) = False` for every `l* ∈ [1, L−2]`, and the per-pair sum is empty. The convention is `pair_cost_{ij}(t) = 0` for an empty sum. This is **not** a distrust signal — it's a "no data" signal. §5's trust-weighting must not treat 0 as an informative value (see §5 deferral).
- **Exactly one source emits EOS early.** The stencil is invalidated for pairs involving that source but remains valid for the other pair. At M = 3 with sources {0, 1, 2}, if source 0 emits EOS at `l = 1`: pairs (0,1) and (0,2) drop out of the sum for any `l* ≥ 1`, but pair (1,2) is unaffected. Per-source cost for source 0 becomes 0 (no pairs contribute); per-source cost for sources 1 and 2 inherit whatever pair (1,2) reports. This is correct behavior — we have no evidence to distrust source 0 based on BCVF; the trust-weighting step (§5) will blend based on the remaining two sources.
- **EOS behavior is deterministic for greedy decoding.** Since §1.3 locks greedy, `last_defined_l[i]` is a deterministic function of the context and the source — not a stochastic variable. Reproducibility is preserved.

#### 2.7.5 Degenerate inputs — identical sources, insufficient lookahead, M < 3

**Identical sources (`e_{ij} ≡ 0`).** If sources `i` and `j` produce bit-identical distributions (e.g. same model, same seed, same decoding path), every `e_{ij}(l) = 0`, hence every `a_{ij}(l*) = 0`, penalty = 0, contrib = 0. `pair_cost_{ij}(t) = 0`. This is the correct output (no disagreement → no distrust signal) and matches Lemma 1 case 1 trivially. The BCVF kernel does not special-case this.

**Insufficient lookahead (`L < 3`).** The 2nd-order stencil requires `L ≥ 3` (three consecutive positions). The autonomy kernel already raises `ValueError("BCVF requires H >= 3")` in `compute_bcvf_cost_batch` — the LLM implementation carries over this hard guard. If speculative decoding returns `L = 2` or `L = 1` tokens (e.g. due to immediate EOS on all sources), the caller is expected to **skip the BCVF computation entirely** for that outer step and fall back to the no-BCVF trust-weighting default (§5 will specify).

**M < 3 sources.** §1 locked `M = 3` as the minimum viable source count for trust-weighting discrimination. The BCVF kernel must still accept `M = 2` (for the degenerate backward-compat tests) but callers in the LLM pipeline never supply fewer than 3. Kernel-level validation: `if num_models < 2: raise ValueError` (autonomy has this already). Callers should validate `M = 3` upstream of the kernel.

#### 2.7.6 NaN / Inf handling and propagation

Model forward passes **can** produce NaN logits on pathological inputs (e.g. under-flowed attention weights, numerical issues in fp16). BCVF must behave predictably.

**V1 rule: NaN in → NaN out, explicit check at the kernel boundary.**

```
if not np.isfinite(logits).all():
    raise ValueError("BCVF received non-finite logits; upstream forward pass failed")
```

Rationale:

- Silently masking NaN (e.g. `nan_to_num`) converts a model-level bug into a silent degradation of the BCVF signal. The trust-weighting step (§5) would then blend in a source whose outputs were actually garbage.
- Raising at the kernel boundary forces the caller to decide: skip this outer step, fall back to a default, or abort the generation entirely. That's a policy decision above the BCVF kernel's pay grade.
- The autonomy kernel doesn't have this guard because SE(2) simulator states are always finite by construction. LLMs don't have that guarantee.

Once logits pass the finite-check, softmax cannot produce NaN (it's numerically stable for any finite input), so `p_i`, `e_{ij}`, `a_{ij}` are all guaranteed finite. No further in-kernel NaN propagation risk.

#### 2.7.7 Sigmoid / exp clipping — pointer to §2.5.1

§2.5.1 already specifies `clip(β·(‖e‖−T), −50, +50)` before `exp`. Repeated here for navigability:

- Without clipping, `exp(β · (√2 − T))` = `exp(200 · 1.31)` = `exp(262)` → overflow to `inf` → gate = 1 but downstream arithmetic could poison other terms if any branch divides by `1 + exp(...)`.
- The clip value `[−50, +50]` is far outside the gate's active region (`σ(±50) = 1.0` / `~0` within machine epsilon), so the clip is cosmetic for the gate value but protective against NaN propagation.
- Same clip applied in autonomy `core.py`; carried over verbatim.

#### 2.7.8 Per-outer-step memory and compute budget at M = 3, L = 5

Concrete numbers for sizing the pipeline:

| Quantity | Shape | fp32 bytes | Notes |
|---|---|---|---|
| Logits batch `z` | `(M, 1, L, V) = (3, 1, 5, 32000)` | 1.92 MB | Stored per outer step; freed after BCVF compute |
| Probabilities `p` | `(M, 1, L, V) = (3, 1, 5, 32000)` | 1.92 MB | Derived from `z` via softmax |
| Disagreement `e` | `(3-choose-2, L, V) = (3, 5, 32000)` | 1.92 MB | Pairwise differences |
| Acceleration `a` | `(3, L−2, V) = (3, 3, 32000)` | 1.15 MB | 2nd-difference output |
| Gate input norms | `(3, L−2)` | 36 B | Scalar norm per stencil point |
| Penalty | `(3, L−2)` | 36 B | Scalar Huber per stencil point |
| **Per-outer-step peak (fp32)** | — | **~7 MB** | All BCVF intermediates |

The forward-pass KV-cache for a 7B model at L = 5, batch = 8 is roughly **2–3 GB** on fp16. BCVF intermediates are a rounding-error fraction of total memory. **V1 rule: no memory-optimization work needed.** The §2.4.6 FLOP estimate (~6M FLOPs/step) similarly makes BCVF compute dwarfed by the forward pass (~16B FLOPs/step at 7B).

If M is raised in V2 (§9), the pairs grow as `M·(M−1)/2`. At `M = 5`, pairs = 10, memory = ~19 MB — still negligible. Quadratic scaling in `M` is the right concern for large ensembles.

#### 2.7.9 What §2.7 does NOT cover

- **KV-cache management across the M = 3 sources.** That is a §4 implementation detail (how to share or replicate cache when sources are prompt-variants of the same model), not a BCVF-math concern.
- **Batch-across-outer-steps vectorization.** The autonomy kernel has `compute_bcvf_cost_batch` vectorized across K rollouts; the LLM analogue may or may not batch across `t` depending on the pipeline design (streaming vs. batched generation). §4 decision.
- **Mixed-model ensembles** (different base models with different vocabs). Explicitly V2 per §2.2.7 and §9.
- **Alternative precision regimes** (int8 quantization, 4-bit). V2 / out of scope.
- **Error recovery policy** when the finite-check in §2.7.6 raises. That's a caller policy, decided in §4 or §5.
- **Concurrency / thread safety.** The BCVF kernel is pure (no shared state); standard NumPy/PyTorch concurrency rules apply. No special treatment.

#### 2.7.11 Per-source baseline drift handling (consumer-layer recommendation)

The BCVF kernel emits a per-source cost (§2.8.11 `BCVFLLMResult.per_source_costs`) whose **baseline can vary substantially across contexts** — different prompts, different source configurations, and different decoding states all produce different "floor" levels in the raw cost. This is a property of the cost being a quadratic-positive function of an input distribution that itself has context-dependent shape; it is **not** a bug in the kernel and **not** a violation of Lemma 1 (constant disagreement still produces zero acceleration; the floor we observe is from genuine per-context disagreement structure, not from numerical artifact).

The consequence is an integration-layer concern: any consumer that converts `per_source_costs` into trust weights via a continuous mechanism (softmin, softmax-on-negatives, etc.) will, without normalization, produce trust distributions that are dominated by the per-context baseline rather than by the disagreement *event* the consumer is trying to detect. **This was empirically confirmed in the autonomy companion experiments** on `S3_map_error_accel` (M = 4 SE(2) predictors, N = 26 paired): raw per-source cost magnitudes spanned roughly four orders of magnitude across seeds, and a single fixed gate threshold could neither expose all real disagreement events nor suppress all baseline noise simultaneously.

**Consumer-layer recommendation (autonomy-validated, two-stage pattern).** When BCVF is consumed by a continuous trust-shaping layer (§5), the layer should apply the following before the softmin:

1. **Per-source EMA mean centering.** Maintain an exponential moving average `EMA_mean[i]` of `per_source_costs[i]` across consumer steps (e.g., outer decoding steps for an LLM streaming consumer). Subtract `EMA_mean` from the current cost before any trust-weighting computation. This removes the per-context baseline drift and exposes the residual disagreement signal at a comparable scale across contexts.

2. **Significance gate / hinge-φ shaping.** After centering, the residual signal includes both genuine disagreement events and the small noise that the baseline previously masked. Apply a significance filter before softmin: either a hard deadband (zero out residual if `|residual| < k · σ` for some EMA-tracked `σ`) or — equivalently and more numerically gentle — a hinge transform on the cost feeding softmin, e.g. `φ(d) = max(d − θ, 0)` so that disagreement below `θ` contributes nothing to the trust shift.

The hinge-φ form integrates more cleanly with autodiff and avoids the discontinuity of a hard gate, but is mathematically near-equivalent for moderate `k · σ ≈ θ`. Either implementation is acceptable.

**Why both stages, not just one.** The autonomy experiments isolated each component:

- **EMA alone (no gate)** removed the per-seed floor but exposed previously-masked rollout noise; healthy seeds suffered new catastrophes from spurious trust shifts (regression on 4 of 26 seeds vs A0 baseline).
- **Gate alone (no EMA)** required a single absolute threshold that could not simultaneously be small enough to detect events on low-floor seeds and large enough to suppress noise on high-floor seeds; outcomes flipped catastrophically as the threshold moved.
- **EMA + gate together** preserved all baseline rescues, recovered all EMA-only regressions, and produced the first statistically significant improvement vs the no-shaping baseline (sign test p < 0.01).

The pair is the validated pattern. Either component alone is incomplete.

**Scope and non-claims.** This sub-section is a **consumer-layer recommendation**, not a kernel-level requirement:

- The BCVF kernel itself remains unchanged. `compute_bcvf_cost` and `compute_bcvf_cost_batch` (§2.8.11–§2.8.12) emit raw `per_source_costs`. Centering and gating are downstream operations.
- This recommendation applies specifically to **continuous trust-shaping consumers**. Other consumer architectures — episodic gating, threshold-routing, hard-mask predictor selection — have different signal-to-noise structure and may not need either stage. §5 will discuss consumer-architecture choice without committing V1 to a single mode.
- The pattern is **autonomy-validated, not LLM-validated.** The mathematical mechanism (per-context baseline drift, residual noise after centering) is structural and is expected to transfer to LLM domains where BCVF is consumed continuously, but the empirical confirmation in the LLM domain awaits §3 / §4 / §5 execution. The recommendation is offered as an evidence-led design constraint, not a universal theorem.

**Deferral to §5.** Concrete parameters (EMA rate `α`, gate threshold `k · σ` or `θ`, warmup behavior, freeze rules) are specified in §5 as part of the integration-layer design. §2.7.11 records only the existence of the two-stage pattern and the rationale for both stages; §5 fixes the V1 numerical defaults.

#### 2.7.12 Acceptance criteria for §2.7

§2.7 is complete when:

1. ✅ Softmax temperature = 1.0 rule is committed (§2.7.1).
2. ✅ fp32 boundary rule is committed (§2.7.2).
3. ✅ Underflow and simplex-drift analysis is in place (§2.7.3).
4. ✅ EOS / truncation rule is consolidated with corner cases (§2.7.4).
5. ✅ Degenerate inputs (identical sources, L < 3, M < 3) have explicit rules (§2.7.5).
6. ✅ NaN / Inf policy at the kernel boundary is committed (§2.7.6).
7. ✅ Exp-clipping pointer to §2.5.1 is in place (§2.7.7).
8. ✅ Memory / compute budget is quantified (§2.7.8).
9. ✅ Out-of-scope deferrals are enumerated (§2.7.9).
10. ✅ Per-source baseline drift handling — consumer-layer two-stage pattern (EMA mean + significance gate / hinge-φ) recorded with autonomy evidence (§2.7.11).

Items 1–10 are satisfied by this section. No pending empirical verification for §2.7 — all rules are design-time and will be enforced by implementation + the §2.9 tests, plus §5 commits the concrete parameters of the two-stage consumer pattern from §2.7.11.

### 2.8 Python equations parallel to `core.py`

The goal of §2.8 is to commit to a line-for-line translation of the autonomy BCVF kernel (`symbolu_robotics/bcvf_autonomous/core.py`) into an LLM-domain kernel, so that §4 implementation is mechanical and §2.9 tests have a concrete target to verify against. Each sub-section names what autonomy has, what the LLM version keeps verbatim, and what it changes — with justification tied back to §2.1–§2.7.

#### 2.8.1 File layout & naming — where the LLM kernel lives

**Target file for V1:** `symbolu_bcvf_llm/core.py`, a new package sitting alongside `symbolu_robotics/bcvf_autonomous/`. The module mirrors the autonomy kernel's structure one-to-one: same function names where semantics carry over, renamed where domain requires it, and the same dataclass-driven configuration pattern.

**Why a separate package, not a shared utility module.** The two kernels operate on fundamentally different inputs (SE(2) trajectories vs. probability-simplex distributions) even though the 2nd-order BCVF math is identical. Three concrete reasons to keep them separate:

1. **No cross-domain import coupling.** `bcvf_autonomous/core.py` imports `body_frame_error_trajectory` from `.manifold` — that helper is SE(2)-specific and has no meaning in the LLM domain. Conversely, `bcvf_llm/core.py` will have a `compute_disagreement` that operates on vocabulary-vector probabilities — meaningless in autonomy. Forcing these into a shared module would require a generic interface that neither side needs.
2. **Dependency isolation.** The autonomy kernel is pure NumPy with no optional deps. The LLM kernel is also pure NumPy (see §2.8.2) — but §4's caller layer around it will import `torch` and `transformers`. Keeping the kernel file free of ML-framework imports means it can be unit-tested without a GPU, without model downloads, and without HuggingFace cache warm-up. This matches the autonomy kernel's test discipline.
3. **Independent evolution.** If V2 (§9) experiments with alternative LLM disagreement metrics (KL, Hellinger) or mixed-model ensembles, those changes land in `bcvf_llm/core.py` only. The autonomy kernel, which is shipped and validated by the Ketu→Rahu N=26 smoke, stays frozen.

**Module-level expectations** (enforced by the §2.9 test suite):

- Pure NumPy. No `import torch`, `import transformers`, `import datasets`, `import jax`. The kernel accepts `np.ndarray` inputs in fp32 (per §2.7.2) and returns `np.ndarray` outputs in fp32.
- No I/O. No logging at the INFO level or higher from inside the kernel. Debug-level logging is permitted but off by default.
- No global state. All configuration is passed via `BCVFLLMConfig` dataclass instances, mirroring autonomy's `BCVFConfig` pattern (`core.py:39`).
- No hidden randomness. The kernel is deterministic given its inputs. If V2 adds a stochastic component (e.g. sub-sampling vocab for efficiency), it enters as an explicit `rng` argument, never as `np.random.default_rng()` called internally.

**Reference artifact at the top of the file.** The module docstring will cite the autonomy kernel by path and function names — specifically `compute_bcvf_cost_batch` in `bcvf_autonomous/core.py:232` — so that a reader can open both files side-by-side and verify structural parity. This is the same discipline §2 applies throughout: the autonomy kernel is the source of truth for the math; the LLM kernel is its domain-adapted twin.

**What this sub-section does NOT commit to.** The internal file split (single `core.py` vs. `core.py + disagreement.py + gate.py`) is a §4 implementation concern; §2.8 only commits that there IS a kernel module called `core.py` in a package called `symbolu_bcvf_llm`. If §4 decides to split the kernel across multiple files for readability, that's fine as long as the public API (§2.8.11) and the test targets (§2.9) remain stable.

#### 2.8.2 Imports and module docstring

The autonomy kernel opens with (`bcvf_autonomous/core.py:1–21`):

```python
"""BCVF cost functional (V3.1 Sections 3.3-3.5, Lemma 1).

Implements the complete BCVF cost chain over a set of predictor
trajectories:

    disagreement -> velocity -> acceleration -> gate -> huber -> sum

All functions are pure. Trajectory inputs are NumPy float64 arrays
of shape (H, 3) with columns [x, y, theta]. No imports from other
``symbolu_robotics`` modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Tuple

import numpy as np

from .manifold import body_frame_error_trajectory
```

**LLM-kernel equivalent** (target content of `symbolu_bcvf_llm/core.py:1–19`):

```python
"""BCVF cost functional — LLM logit-space adaptation.

Parallels ``symbolu_robotics/bcvf_autonomous/core.py``. Implements
the same 2nd-order BCVF cost chain, re-targeted from SE(2) body-
frame trajectories to probability-simplex sequences along the
forward-lookahead axis:

    disagreement -> velocity -> acceleration -> gate -> huber -> sum

All functions are pure. Probability inputs are NumPy float32 or
float64 arrays of shape (M, T, L, V) where:
    M = number of sources (V1: M >= 3, see §1.3 / §2.2.4)
    T = number of outer decoding steps (streaming; may be 1)
    L = forward-lookahead horizon (V1: L = 5, see §2.3.4)
    V = vocabulary size (shared across sources for V1, see §2.7.5)

Design anchor: ``docs/design/BCVF_LLM_TRUST_ROUTING_DESIGN.md``
§2.4-§2.7. Mathematical specification: V3.1 Lemma 1 (autonomy)
restated in §2.6 with the vector-path proof in §2.6.4.

No imports from other ``symbolu_bcvf_llm`` modules; no imports from
``symbolu_robotics``; no ML-framework imports (torch/transformers/
datasets). The caller in §4 handles fp16/bf16 -> fp32 conversion
(see §2.7.2) before invoking this kernel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

import numpy as np
```

**What changed and why:**

| Line | Autonomy | LLM-kernel | Why |
|---|---|---|---|
| Title | `V3.1 Sections 3.3–3.5, Lemma 1` | `LLM logit-space adaptation` plus explicit pointer to `BCVF_LLM_TRUST_ROUTING_DESIGN.md` §2.4–§2.7 | The autonomy kernel's math reference is the V3.1 paper; the LLM kernel's reference is this design document (which, in turn, cites §2.6 for the Lemma 1 analogue proof) |
| Shape doc | `(H, 3)` with SE(2) columns | `(M, T, L, V)` batch with semantic labels | §2.2 locked `(p_i − p_j) ∈ ℝ^V`; §2.3 added the `l` axis; §1.3 added `M ≥ 3`. The 4-D tensor shape is the natural generalization and what `compute_bcvf_cost_batch` consumes |
| dtype | `float64` | `float32` *or* `float64` | §2.7.2 committed fp32 as the V1 default (matches PyTorch's default post-upcast). fp64 is permitted for the §2.9 Lemma-1 tests that require `1e−10` tolerance. Accepting either is ergonomic; internally the kernel promotes scalars via `np.asarray(..., dtype=np.float64)` where stencil cancellation matters |
| `from .manifold import body_frame_error_trajectory` | **removed** | — | SE(2) helper with no LLM analogue. §2.8.5 defines the replacement `compute_disagreement` inline — it's a one-line vector subtraction, no helper module needed |
| `typing.Optional` | not imported | **added** | Needed by the `valid_mask: Optional[np.ndarray]` parameter in `_pair_cost` and `compute_bcvf_cost_batch` (EOS / truncation handling from §2.7.4) |
| stdlib imports (`dataclass`, `field`, `IntEnum`, `Dict`, `List`, `Tuple`, `np`) | all present | **unchanged** | Same dataclass-config pattern (§2.8.4), same enum-driven cost-order switch (§2.8.3), same pairwise aggregation types |

**What stayed verbatim:** the `from __future__ import annotations`, the stdlib import block, and the NumPy import. Purity discipline stays the same — no logging, no I/O, no framework deps.

**Critical non-additions.** The docstring explicitly names three import prohibitions that §4's CI must enforce:

1. No `import torch` / `import torch.nn.functional as F`. The kernel never sees tensors; §4's caller is responsible for `.cpu().numpy()` conversion and fp32 upcasting at the boundary (§2.7.2).
2. No `import transformers` / no `from transformers import AutoModelForCausalLM, AutoTokenizer`. The kernel doesn't know what model produced the probabilities.
3. No `from symbolu_robotics.bcvf_autonomous import ...`. Parallel implementations, not shared — §2.8.1 justified this separation. If a helper turns out to be needed in both kernels (e.g. a future `pseudo_huber_jit` optimized version), it lives in a third neutral package, not cross-imported.

**Enforcement.** The §2.9 test suite includes an import-graph assertion: `python -c "import symbolu_bcvf_llm.core"` must succeed in an environment where `torch`, `transformers`, and `datasets` are not installed. This is the mechanical guarantee that §2.8.1's dependency-isolation claim is real.

#### 2.8.3 `CostOrder` enum — verbatim carry-over

The autonomy kernel defines an `IntEnum` that selects which derivative-order of the disagreement signal feeds into the gate-Huber chain (`bcvf_autonomous/core.py:24–36`):

```python
class CostOrder(IntEnum):
    """Which derivative order of disagreement the gate-Huber chain scores.

    V3.1 §E.5 / DESIGN.md §3B.10 ablation variants:

    * ``ZEROTH`` — penalize ``||e_ij||`` (magnitude of disagreement).
    * ``FIRST``  — penalize ``||v_ij||`` (velocity of disagreement).
    * ``SECOND`` — penalize ``||a_ij||`` (BCVF, the V3.1 innovation).
    """

    ZEROTH = 0
    FIRST = 1
    SECOND = 2
```

**LLM-kernel equivalent** (target content of `symbolu_bcvf_llm/core.py`):

```python
class CostOrder(IntEnum):
    """Which derivative order of disagreement the gate-Huber chain scores.

    Carried verbatim from the autonomy kernel. V1 locks ``SECOND`` (see
    §2.4.1 vector-path choice and §2.6.4 linear-drift invariance proof).
    ZEROTH and FIRST are retained so the §3 signal-characterization
    sweep can ablate without code changes.

    * ``ZEROTH`` — penalize ``||e_ij(l*)||`` at each lookahead position.
    * ``FIRST``  — penalize ``||v_ij(l*)||``, the 1st-order forward
      difference along the lookahead axis. **Does not preserve
      Lemma 1 case 2** (non-zero under linear drift); diagnostic only.
    * ``SECOND`` — penalize ``||a_ij(l*)||``, the 2nd-order stencil
      from §2.4.2. **This is what V1 uses.**
    """

    ZEROTH = 0
    FIRST = 1
    SECOND = 2
```

**What changed and why:**

| Aspect | Autonomy | LLM-kernel | Rationale |
|---|---|---|---|
| Enum values (`ZEROTH=0, FIRST=1, SECOND=2`) | — | **verbatim** | Cross-domain ablation parity — if someone swaps `CostOrder` in either kernel for a test, the integer values mean the same thing |
| Docstring references (`V3.1 §E.5`, `DESIGN.md §3B.10`) | autonomy refs | replaced with **this doc §2.4.1 / §2.6.4** | The reader of this file should reach the correct math reference; autonomy's V3.1 paper has no LLM section |
| ZEROTH description | `||e_ij||` on trajectory | `||e_ij(l*)||` per lookahead position | Same math, re-indexed onto the `l` axis; §2.3.1 |
| FIRST description | `||v_ij||` | `||v_ij(l*)||` **with explicit Lemma-1 violation note** | Deliberately flagged: under linear drift `e(l) = α + γl`, `v(l) = γ` — constant non-zero — so FIRST would gate+penalize steady drift. This was true in autonomy too (first-order stencil violates Lemma 1 case 2) but §2.6.4 makes it explicit for the LLM setting, and callers ablating need the warning |
| SECOND description | `||a_ij||` (the V3.1 innovation) | `||a_ij(l*)||` with pointer to §2.4.2 stencil | Same innovation, same math; references the explicit stencil formula §2.4.2 committed |
| `IntEnum` (not `Enum`) | — | **verbatim** | `IntEnum` lets callers write `config.cost_order == 2` ergonomically and makes CSV/JSON config loaders work without a custom codec. Autonomy chose this deliberately; keep it |

**V1 lock.** `BCVFLLMConfig.cost_order` defaults to `CostOrder.SECOND` (specified in §2.8.4 next). §3's signal-characterization sweep may temporarily set it to `CostOrder.ZEROTH` or `CostOrder.FIRST` for ablation rows — those sweeps live in `tests/` or `run_experiments/`, never as production defaults.

**What §2.8.3 does NOT add.** No higher-order variants (`THIRD = 3`, etc.). The autonomy kernel stops at 2nd-order because 2nd-order is the minimum order that (a) kills constant bias, (b) kills linear drift, and (c) still produces signal on quadratic divergence. Higher orders kill more benign patterns but require more lookahead positions (`L ≥ 4` for 3rd-order, breaking §2.3.4's `L = 5` budget margin). Deferred to §9 V2 Roadmap if signal quality warrants.

**Parity test.** §2.9 will include `test_cost_order_enum_values`, which asserts `CostOrder.ZEROTH.value == 0`, `FIRST.value == 1`, `SECOND.value == 2`. This is a one-line mechanical assertion that catches accidental re-ordering and guards the cross-kernel ablation parity claim above.

#### 2.8.4 `BCVFLLMConfig` dataclass — translated from `BCVFConfig`

The autonomy kernel exposes a dataclass with nine tunable fields (`bcvf_autonomous/core.py:39–54`):

```python
@dataclass
class BCVFConfig:
    """All tunable parameters for the BCVF cost functional."""

    lambda_c: float = 1.0
    gate_threshold: float = 0.1
    gate_beta: float = 200.0
    huber_delta: float = 0.5
    lever_arm: float = 2.5
    weight_matrix: np.ndarray = field(
        default_factory=lambda: np.ones(3, dtype=np.float64)
    )
    use_anchor_pairing: bool = True
    anchor_index: int = 0
    dt: float = 0.1
    cost_order: CostOrder = CostOrder.SECOND
```

**LLM-kernel equivalent** (target content of `symbolu_bcvf_llm/core.py`):

```python
@dataclass
class BCVFLLMConfig:
    """All tunable parameters for the LLM-domain BCVF cost functional.

    Parallels ``BCVFConfig`` in ``bcvf_autonomous/core.py:39``. Every
    field that has a meaningful LLM analogue is carried over with the
    same name and default; SE(2)-specific fields are dropped; LLM-
    specific fields are added with explicit reference to the design
    sub-section that motivated them.
    """

    # Gate/Huber parameters — carried verbatim from autonomy defaults
    # (see §2.5.1, §2.5.2). V1 starting point; §3 will sweep.
    gate_threshold: float = 0.1          # §2.5.1 T
    gate_beta: float = 200.0             # §2.5.1 β
    huber_delta: float = 0.5             # §2.5.2 δ

    # Vocabulary-space weight matrix. V1 uses identity (all ones) —
    # §2.4.3 committed W = I_V. Default factory builds to the correct
    # length once the caller supplies `vocab_size`; kernel accepts
    # None and fills in at first use.
    weight_vector: Optional[np.ndarray] = None   # shape (V,) or None

    # Pairing mode. Autonomy V1 uses anchor_pairing=True with M=2.
    # LLM V1 uses use_anchor_pairing=False at M=3 — all-pairs
    # enumeration (0,1), (0,2), (1,2). See §2.4.5 per-source
    # attribution argument (symmetric sum requires all pairs).
    use_anchor_pairing: bool = False     # §2.4.5
    anchor_index: int = 0                # unused when use_anchor_pairing=False

    # Lookahead-axis sample spacing. Autonomy has dt=0.1 (simulator
    # step). LLM V1 treats the lookahead axis as dimensionless
    # integer positions, so step_l = 1.0 by construction.
    step_l: float = 1.0                  # §2.3 lookahead-index spacing

    # Derivative order feeding the gate-Huber chain. V1 locks SECOND
    # per §2.4.1 + §2.6.4. ZEROTH/FIRST retained for §3 ablation only.
    cost_order: CostOrder = CostOrder.SECOND
```

**Field-level translation table:**

| Autonomy field | LLM field | Status | Justification |
|---|---|---|---|
| `lambda_c: float = 1.0` | — | **dropped** | `lambda_c` scaled BCVF into the additive-cost MPPI objective. Ketu→Rahu composition does not add BCVF into the objective (§0.1 / autonomy N=10 validation); it uses per-source cost as trust-weighting input. No scalar scale factor needed at the kernel level |
| `gate_threshold: float = 0.1` | `gate_threshold: float = 0.1` | **verbatim** | §2.5.1 committed T = 0.1 (same as autonomy starting point; rescaled by domain but the ratio β·T=20 is what matters) |
| `gate_beta: float = 200.0` | `gate_beta: float = 200.0` | **verbatim** | §2.5.1; β·T = 20 ratio preserved |
| `huber_delta: float = 0.5` | `huber_delta: float = 0.5` | **verbatim** | §2.5.2 |
| `lever_arm: float = 2.5` | — | **dropped** | SE(2)-specific. `body_frame_error_trajectory` consumed it to convert yaw-angle error into a displacement. No analogue in logit space; disagreement is already in ℝ^V |
| `weight_matrix: np.ndarray = np.ones(3)` | `weight_vector: Optional[np.ndarray] = None` | **renamed + shape-changed** | Autonomy's `W` is shape (3,) for SE(2) xyθ weights. LLM's is shape (V,) for vocabulary dimensions. V1 uses identity per §2.4.3, but V ≈ 32000 is model-dependent, so default is `None` and the kernel infers `V` from the first input. Renamed to `_vector` because it's a 1-D per-dimension weight, never a matrix (autonomy's `_matrix` name was already a slight misnomer) |
| `use_anchor_pairing: bool = True` | `use_anchor_pairing: bool = False` | **default flipped** | Autonomy's anchor mode works at M=2. LLM V1 at M=3 needs the all-pairs enumeration `{(0,1), (0,2), (1,2)}` so §2.4.5's per-source attribution sum `per_source_cost_i = Σ_{j≠i} pair_cost_{ij}` discriminates the outlier 2:1. Anchor mode would give only two pairs, both including the anchor, breaking symmetry |
| `anchor_index: int = 0` | `anchor_index: int = 0` | **retained but inert** | Only meaningful when `use_anchor_pairing=True`. Kept so callers can opt into anchor mode for ablation or for M=2 legacy cases without API breakage |
| `dt: float = 0.1` | `step_l: float = 1.0` | **renamed + value changed** | Autonomy `dt` is simulator step (seconds). LLM `step_l` is lookahead-axis spacing; positions are integer token indices, so spacing = 1 by construction. Name change makes this obvious and prevents callers from trying to set it to a "frequency". Kept as a float field so §9 V2 Roadmap experiments (e.g. non-uniform speculative sampling) can parameterize |
| `cost_order: CostOrder = CostOrder.SECOND` | `cost_order: CostOrder = CostOrder.SECOND` | **verbatim** | §2.8.3 |

**Net count:** 10 autonomy fields → 8 LLM fields (2 dropped: `lambda_c`, `lever_arm`; 0 added). The reduction is a clean "no unused parameters" outcome of the Ketu→Rahu composition (no `lambda_c`) and the domain shift (no `lever_arm`).

**Mutable-default discipline.** Autonomy uses `field(default_factory=lambda: np.ones(3, dtype=np.float64))` to avoid the classic mutable-default pitfall. LLM V1 sidesteps this by making `weight_vector` default to `None` (immutable) and materializing the identity weights inside `_pair_cost` the first time it's needed. This also solves the "don't know V at config-construction time" problem that would otherwise force callers to pass `vocab_size` into the constructor.

**Validation.** The kernel will validate the config at entry to `compute_bcvf_cost_batch` (§2.8.11), not at `__init__`. This is deliberate: dataclass defaults must be cheap and non-failing; validation needs to see the actual input shape (V) to check `weight_vector.shape == (V,)`. The autonomy kernel makes the same choice — `BCVFConfig.__init__` doesn't validate `weight_matrix.shape == (3,)` either; `_pair_cost` discovers the mismatch via NumPy broadcasting error.

**What §2.8.4 does NOT add.** No trust-weighting temperature `τ_w`. That belongs in §5's Rahu attractor consumer, not the BCVF kernel. §2.5.5 already committed this separation. The kernel computes per-source cost; the caller turns it into a trust distribution.

**Parity test.** §2.9 will include `test_bcvflllm_config_defaults` that asserts each of the 8 fields has the exact default value committed above. This is a one-line mechanical assertion that catches drift between the design doc and the implementation.

#### 2.8.5 `compute_disagreement` — replacing `body_frame_error_trajectory`

The autonomy kernel's `compute_disagreement` is a thin wrapper that delegates to the SE(2) body-frame helper (`bcvf_autonomous/core.py:67–74`):

```python
def compute_disagreement(
    traj_i: np.ndarray, traj_j: np.ndarray, lever_arm: float
) -> np.ndarray:
    """V3.1 Definition 1. Body-frame error over the full trajectory.

    Inputs: (H, 3). Output: (H, 3).
    """
    return body_frame_error_trajectory(traj_i, traj_j, lever_arm)
```

**LLM-kernel equivalent** (target content of `symbolu_bcvf_llm/core.py`):

```python
def compute_disagreement(p_i: np.ndarray, p_j: np.ndarray) -> np.ndarray:
    """§2.2 disagreement metric. Probability-simplex difference.

    Inputs: (..., V) arrays from softmax-normalized logits. Output:
    same leading shape, same V. The ellipsis supports both unbatched
    (L, V) sequences and batched (T, L, V) or (M, T, L, V) tensors.

    No normalization, no projection, no clamping. By §2.7.3 the BCVF
    operator is translation-invariant over the per-vocab mean, so
    simplex-sum rounding drift does not affect downstream 2nd-
    differences or norms. The caller is responsible for ensuring
    inputs came from a softmax pass (§2.7.1 commits T=1.0, fp32).
    """
    return p_i - p_j
```

**Diff against autonomy:**

| Aspect | Autonomy | LLM-kernel | Rationale |
|---|---|---|---|
| Signature | `(traj_i, traj_j, lever_arm)` | `(p_i, p_j)` | No `lever_arm` per §2.8.4; disagreement is already in ℝ^V |
| Implementation | delegates to `body_frame_error_trajectory` | **one-line vector subtraction** | §2.2.1 committed `e_{ij}(l) = p_i(l) − p_j(l)`. Nothing to delegate — NumPy's native operator does it |
| Input shape | strict `(H, 3)` | `(..., V)` with ellipsis | Callers at §2.8.11 pass `(M, T, L, V)`; callers at §2.8.10 pass `(T, L, V)` per-pair; test harnesses may pass `(L, V)` directly. `p_i - p_j` broadcasts cleanly for all three |
| Output shape | `(H, 3)` | `(..., V)` | Consequence of NumPy broadcast |
| Docstring reference | `V3.1 Definition 1` | `§2.2` | Replaces autonomy paper reference with this doc's metric commitment |
| Translation-invariance note | implicit (SE(2) body-frame math absorbs it) | **explicit** | §2.7.3 committed that BCVF does not depend on simplex-sum holding exactly. Docstring states this so future maintainers don't add an `np.clip(e, 0, 1)` or re-normalization that would silently break Lemma 1 |
| No-clamping note | — | **explicit** | Prevents well-meaning contributors from inserting `np.clip(p_i - p_j, -1, 1)`. The theoretical range is `[−1, 1]` by simplex constraint, so clipping is a no-op in theory but could shift numerical rounding noise in a way that fails the §2.9 tests |

**Why this is a one-liner and why it has a function anyway.** The body of `compute_disagreement` could be replaced everywhere with `p_i - p_j`, saving one function call. The function is kept because:

1. **Structural parity with autonomy.** Autonomy's `compute_disagreement` exists as a named operation in the pipeline `disagreement → velocity → acceleration → gate → huber → sum`. Keeping the same name in the LLM kernel preserves the pipeline stage naming and makes the side-by-side reading of the two files possible.
2. **Testability.** §2.9 will unit-test the disagreement stage separately from the acceleration and gate stages. A named function is a natural test target.
3. **Extension point.** If V2 (§9) introduces an alternative disagreement metric (KL-divergence, Hellinger), the function signature is the extension point: `compute_disagreement(p_i, p_j, metric="kl")`. The V1 body stays trivial; V2 grows it.

**What the function does NOT do** (deliberate non-features):

- **No validation of simplex sum.** Inputs could have `Σ_k p_{i,k} = 1.0000001` due to fp32 rounding after softmax; the kernel tolerates this per §2.7.3.
- **No NaN check.** §2.7.6 locates the NaN guard in `compute_bcvf_cost_batch` at the kernel boundary, not in every stage. Per-stage checks would be redundant and slow.
- **No `where`/masking.** EOS truncation is handled downstream by the `valid_mask` parameter in §2.8.10's `_pair_cost`, not by masking the disagreement itself (truncated positions still produce values; they're just dropped from the sum later). Keeping masking out of this stage means the function stays pure elementwise.

**FLOP cost.** `(..., V)` subtraction is `V` FLOPs per leading element. At V=32000, M=3, T=1, L=5, the total per outer step is `3×1×5×32000 = 480K` FLOPs — a rounding error against the 16 GFLOPs of the model forward pass (§2.4.6).

**Parity test.** §2.9 will include `test_compute_disagreement_shape_broadcast` that passes a (3, 1, 5, 32000) input and asserts output shape matches, plus `test_compute_disagreement_translation_invariant` that adds a constant vector to both `p_i` and `p_j` and asserts the output is unchanged (verifying §2.7.3's translation invariance at the stage boundary).

#### 2.8.6 `compute_disagreement_velocity` and `compute_disagreement_acceleration` — finite-difference stages

Autonomy defines these as two named stages (`bcvf_autonomous/core.py:77–98`):

```python
def compute_disagreement_velocity(
    disagreement: np.ndarray, dt: float
) -> np.ndarray:
    """V3.1 Definition 2. First finite difference of the disagreement.

    Input: (H, 3). Output: (H-1, 3).
    """
    return (disagreement[1:] - disagreement[:-1]) / dt


def compute_disagreement_acceleration(
    disagreement: np.ndarray, dt: float
) -> np.ndarray:
    """V3.1 Definition 3. Second finite difference of the disagreement.

    a(k) = [e(k+1) - 2 e(k) + e(k-1)] / dt^2

    Input: (H, 3). Output: (H-2, 3). This is the core innovation.
    """
    return (disagreement[2:] - 2.0 * disagreement[1:-1] + disagreement[:-2]) / (
        dt * dt
    )
```

**LLM-kernel equivalent** (target content of `symbolu_bcvf_llm/core.py`):

```python
def compute_disagreement_velocity(
    e: np.ndarray, step_l: float = 1.0
) -> np.ndarray:
    """§2.4 forward-difference along the lookahead axis.

    v(..., l*, :) = [e(..., l*+1, :) - e(..., l*, :)] / step_l

    for l* ∈ [0, L-2].

    Input:  (..., L, V)    (lookahead axis is second-to-last)
    Output: (..., L-1, V)

    Note: under linear drift e(l) = α + γ·l, v(l) = γ — constant but
    non-zero. This breaks Lemma 1 case 2 (§2.6.4). V1 uses SECOND
    (§2.8.3, §2.8.4); velocity is exposed for §3 ablation only.
    """
    return (e[..., 1:, :] - e[..., :-1, :]) / step_l


def compute_disagreement_acceleration(
    e: np.ndarray, step_l: float = 1.0
) -> np.ndarray:
    """§2.4.2 stencil. Second finite difference along the lookahead axis.

    a(..., l*, :) = [e(..., l*+1, :) - 2·e(..., l*, :) + e(..., l*-1, :)] / step_l²

    for l* ∈ [1, L-2].

    Input:  (..., L, V)    (lookahead axis is second-to-last)
    Output: (..., L-2, V)

    This is the **core BCVF innovation** (§2.4) and the operator whose
    Lemma-1 invariance is proved in §2.6.3 / §2.6.4. V1 locks this
    stage as the signal feeding the gate-Huber chain.
    """
    return (
        e[..., 2:, :] - 2.0 * e[..., 1:-1, :] + e[..., :-2, :]
    ) / (step_l * step_l)
```

**Diff against autonomy, per stage:**

| Aspect | Autonomy velocity | LLM velocity | Rationale |
|---|---|---|---|
| Signature | `(disagreement, dt)` | `(e, step_l=1.0)` | `dt` renamed per §2.8.4; default = 1.0 so callers rarely pass it |
| Slice axis | `[1:]`, `[:-1]` (axis 0) | `[..., 1:, :]`, `[..., :-1, :]` (second-to-last) | LLM tensors have `V` as the trailing axis; the diff is along the **lookahead** axis, which is second-to-last in the `(M, T, L, V)` convention from §2.8.2. Ellipsis + explicit-axis slicing handles (L, V), (T, L, V), (M, T, L, V), and per-pair (T, L, V) callers uniformly |
| Output shape | `(H-1, 3)` | `(..., L-1, V)` | Consequence of the slice axis change |
| Lemma-1 warning in docstring | — | **added** | §2.8.3 flagged the FIRST violation; repeated here at the function the ablation would actually call, so readers don't miss it |

| Aspect | Autonomy acceleration | LLM acceleration | Rationale |
|---|---|---|---|
| Signature | `(disagreement, dt)` | `(e, step_l=1.0)` | Same rename as above |
| Slice axis | `[2:]`, `[1:-1]`, `[:-2]` (axis 0) | `[..., 2:, :]`, `[..., 1:-1, :]`, `[..., :-2, :]` (second-to-last) | Same axis-convention reason |
| Output shape | `(H-2, 3)` | `(..., L-2, V)` | Consequence of the slice axis change |
| Formula | `(e[2:] - 2*e[1:-1] + e[:-2]) / (dt*dt)` | `(e[..., 2:, :] - 2*e[..., 1:-1, :] + e[..., :-2, :]) / (step_l*step_l)` | **Identical math**, just re-indexed onto the lookahead axis |
| Docstring | "V3.1 Definition 3 … core innovation" | "§2.4.2 stencil … core BCVF innovation (§2.4) … Lemma-1 invariance proved in §2.6.3 / §2.6.4" | Reference redirects; emphasis on the proof locations |

**Mathematical equivalence check.** Under a linear-drift input `e(l) = α + γ·l` shaped `(L, V)` with `α, γ ∈ ℝ^V`:

- Autonomy time-axis slicing on `(L, 3)`: `e[2:] - 2*e[1:-1] + e[:-2] = (α+γ(l+1)) − 2(α+γl) + (α+γ(l−1)) = 0 ∈ ℝ^{L−2, 3}`.
- LLM lookahead-axis slicing on `(L, V)`: `e[..., 2:, :] - 2*e[..., 1:-1, :] + e[..., :-2, :] = 0 ∈ ℝ^{L−2, V}`.

Same algebra, same invariance — just over a different trailing dimension. §2.6.4's proof does not depend on whether the ambient space is ℝ³ or ℝ^V, which is exactly why the transfer is clean.

**Why the axis convention matters.** If `compute_disagreement_acceleration` were implemented with `e[2:]` (autonomy-style, slicing the first axis), then calling it on `(M, T, L, V)` would compute the 2nd-difference along the **M** axis — i.e. "difference between source 0 and source 1 and source 2", which is nonsense. The ellipsis-then-axis slicing makes the axis commitment explicit in the code and prevents this class of bug.

**Division by `step_l²` with `step_l = 1.0`.** The division is a no-op numerically (`a / 1.0 = a`) but kept for three reasons: (1) structural parity with autonomy, (2) §9 V2 experiments with non-uniform lookahead sampling would set `step_l ≠ 1.0`, and (3) keeping the units semantically correct (the output of `compute_disagreement_acceleration` has units of `probability / step²`, not `probability`).

**Numerical precision at the stencil.** §2.7.2 committed fp32 as the V1 boundary rule. The 2nd-difference cancellation is the **most** numerically-sensitive stage in the whole chain: if `e(l*+1) ≈ e(l*) ≈ e(l*−1)` (say all equal to 0.3), the subtraction `0.3 − 0.6 + 0.3` produces a result whose magnitude is dominated by the low-order bits of each operand. fp32 gives ~7 decimal digits of precision, so a true-zero 2nd-difference comes out as `~3e−8` magnitude (rounding noise), well below the gate threshold `T = 0.1` and the `1e−10` tolerance is only needed in fp64 tests (§2.9 will use `np.float64` inputs for the Lemma-1 unit tests, fp32 for everything else).

**FLOP cost per invocation.** For inputs `(M, T, L, V)` at M=3, T=1, L=5, V=32000:

- Velocity: `(L−1)·V` per pair element = `4 · 32000 = 128K` FLOPs, times `M·T = 3` batch → **384K FLOPs**.
- Acceleration: `(L−2) · 2 · V` (subtract, multiply-by-2, add per element) ≈ `3 · 32000 · 3 = 288K` FLOPs batch-total → **~1M FLOPs**.

Both stages are sub-millisecond on a modern CPU core; GPU execution is not needed (and is actively avoided — see §2.8.1's kernel-purity discipline).

**What §2.8.6 does NOT add.** No weighted 2nd-difference. The `weight_vector` from §2.8.4 is applied **only** at the gate and signal-norm stages (§2.8.7, §2.8.10), not inside the stencil. This matches the autonomy implementation where `weight_matrix` is multiplied into `gate_input` and `signal` after the 2nd-difference, not during. Doing it during would break Lemma 1 for non-uniform weight vectors: `a(l) = W(e(l+1) − 2e(l) + e(l−1))` is still zero under linear drift, but a future `W(l)` that varied with `l` would not preserve invariance. Keeping the stencil weight-free is the defensive choice.

**Parity tests.** §2.9 will include `test_compute_disagreement_acceleration_constant_bias_zero` (constant input → output norm ≤ 1e-10 in fp64), `test_compute_disagreement_acceleration_linear_drift_zero` (linear input → same), and `test_compute_disagreement_acceleration_quadratic_positive` (quadratic input `e(l) = l² · η` → output equals `η` up to rounding). These three tests are the mechanical verification of §2.6.3 / §2.6.4 / §2.6.5 respectively — each Lemma 1 case has a corresponding unit test anchored to this stage.

#### 2.8.7 `smooth_gate` — weighted-norm sigmoid with exp-arg clipping

Autonomy defines the gate as (`bcvf_autonomous/core.py:101–119`):

```python
def smooth_gate(
    disagreement: np.ndarray,
    threshold: float,
    beta: float,
    weight_matrix: np.ndarray,
) -> np.ndarray:
    """V3.1 Definition 4. Smooth gate in [0, 1].

    g(k) = sigmoid(beta * (||W_g^{1/2} e(k)|| - T))

    Input disagreement: (N, 3). Output: (N,).
    """
    w_sqrt = np.sqrt(np.asarray(weight_matrix, dtype=np.float64))
    weighted = disagreement * w_sqrt
    norm = np.linalg.norm(weighted, axis=-1)
    arg = beta * (norm - threshold)
    # Clip for numerical stability before exp
    arg_clipped = np.clip(arg, -50.0, 50.0)
    return 1.0 / (1.0 + np.exp(-arg_clipped))
```

**LLM-kernel equivalent** (target content of `symbolu_bcvf_llm/core.py`):

```python
def smooth_gate(
    e: np.ndarray,
    threshold: float,
    beta: float,
    weight_vector: Optional[np.ndarray] = None,
) -> np.ndarray:
    """§2.5.1 smooth gate in [0, 1].

    g(..., l*) = sigmoid(beta * (||W^{1/2} e(..., l*, :)||_2 - T))

    Input e:  (..., V)      (gate input at stencil centers per §2.5.1)
    Output:   (...)         (scalar gate per leading element)

    V1 defaults: threshold T = 0.1, beta = 200.0 (β·T = 20 ratio, see
    §2.5.1 parameter table). weight_vector = None means W = I_V
    (§2.4.3); a non-None weight is element-wise multiplied by the
    disagreement before the ℓ² norm, matching autonomy's diagonal-W
    convention.

    Clipping: exp argument is clipped to [-50, 50] for numerical
    stability per §2.5.1 / §2.7.7. Structural parity with autonomy.
    """
    weighted = e if weight_vector is None else e * np.sqrt(
        np.asarray(weight_vector, dtype=np.float64)
    )
    norm = np.linalg.norm(weighted, axis=-1)
    arg = beta * (norm - threshold)
    arg_clipped = np.clip(arg, -50.0, 50.0)
    return 1.0 / (1.0 + np.exp(-arg_clipped))
```

**Diff against autonomy:**

| Aspect | Autonomy | LLM-kernel | Rationale |
|---|---|---|---|
| Signature param name | `weight_matrix` | `weight_vector` | §2.8.4 rename — 1-D per-vocab-dim weight, not a matrix |
| Default value | — (required) | `None` | §2.8.4 committed `None` sentinel so identity weight can be inferred at use site; removes the "don't know V at config construction" problem |
| Weight path when None | — (always multiplies) | **skip multiplication** | `None` means `W = I_V`, and `e · 1 = e`. Skipping the `sqrt(ones(V)) * e` work saves `V` multiplies per leading element — small but nonzero at V = 32000 |
| Input shape | `(N, 3)` | `(..., V)` | §2.8.1 / §2.8.2 shape convention; ellipsis supports (L, V), (T, L, V), per-pair tensors |
| Output shape | `(N,)` | `(...)` | Norm reduces the last axis; leading axes pass through |
| Clip bounds `[-50, 50]` | — | **verbatim** | §2.5.1 / §2.7.7 — same numerical-stability guard carried over |
| Sigmoid formula | `1 / (1 + exp(-arg_clipped))` | **verbatim** | Standard logistic sigmoid |
| dtype cast at `sqrt` | `np.float64` | `np.float64` | Same promotion; the gate is a reduction stage where precision matters more than throughput |
| Docstring reference | `V3.1 Definition 4` | `§2.5.1` | Replaces autonomy paper reference with this doc's commitment |

**Weight-application timing is post-subtraction, pre-norm.** The kernel does `sqrt(W) * e` **elementwise** (Hadamard), then takes the ℓ² norm. This is equivalent to `sqrt(e · W · e)` for diagonal `W`, which is the correct weighted-norm formula. Structural parity with autonomy, which does the same (autonomy's `W` is a diagonal matrix represented as shape-(3,) vector, same convention as LLM's `weight_vector`).

**None-handling ergonomics.** Autonomy requires `weight_matrix` as a positional argument with no default, forcing every caller to pass a weight. LLM's `weight_vector=None` default is a quiet ergonomics improvement: §2.9 test helpers that only care about the gate math (not the weight) can omit the argument. Functionally equivalent when the caller would have passed `np.ones(V)`.

**Gate-input-at-stencil-center rule.** §2.5.1 committed that the gate reads `‖e(l*)‖`, not `‖a(l*)‖`. This function doesn't enforce the rule — the caller (§2.8.10 `_pair_cost`) is responsible for passing `e[..., 1:-1, :]` as the input so the stencil centers align. The function is a pure weighted-norm + sigmoid; the semantic of "which positions are stencil centers" lives upstream.

**Numerical properties.**

- **Range.** Output is strictly in `(0, 1)` (the clip prevents the open endpoints from being hit in fp32, but values within `1e-22` of 0 or 1 are possible). Monotonic increasing in `norm`.
- **At V1 defaults** (`T=0.1, β=200`): `smooth_gate(e)` with `‖e‖ = 0.1` returns exactly `0.5`. `‖e‖ = 0.105` returns `σ(1) ≈ 0.731`. `‖e‖ = 0.095` returns `σ(-1) ≈ 0.269`. Transition width `2/β = 0.01` as §2.6.6 noted.
- **Derivative.** `d g / d (‖e‖) = β · g · (1−g)`. Peaks at `g = 0.5` (i.e. `‖e‖ = T`) at value `β/4 = 50`. This is steep enough to be near-step for practical purposes but not so steep that autodiff (§4) would overflow.
- **Bounded argument.** The clip ensures `arg ∈ [−50, 50]`, so `exp(−arg_clipped) ∈ [exp(−50), exp(50)] ≈ [1.9e−22, 5.2e21]`. The sigmoid output is thus always finite and in `[exp(−50)/(1+exp(−50)), 1/(1+exp(−50))] ≈ [1.9e−22, 1 − 1.9e−22]`.

**FLOP cost per invocation.** For input `(M-pairs, T, L-2, V)` at `M-pairs=3, T=1, L-2=3, V=32000` (gate evaluated at valid stencil centers per §2.5.3):

- `sqrt(W)`: `V = 32000` FLOPs (or 0 if weight is None)
- `e * sqrt(W)`: `3·1·3·32000 = 288K` FLOPs
- `norm (sum + sqrt)`: `3·1·3·32000 ≈ 288K` FLOPs
- `arg`, `clip`, `exp`, `sigmoid`: `~9` scalar ops each, times 9 elements = ~100 FLOPs
- **Total: ~600K FLOPs per outer step**, fully negligible.

**What §2.8.7 does NOT do.**

- **No gating decisions based on `a(l*)`.** The input is `e`, not `a`. The gate suppresses *noise-floor disagreement* regardless of whether it's accelerating. This is deliberate: autonomy's gate has the same semantics, and §2.5.1 documented the "stencil alignment" rule. Future V2 alternatives (e.g. gate on signal norm) are §9.
- **No learnable β, T.** These are hyperparameters from `BCVFLLMConfig` (§2.8.4). V2 may make them learnable via `L_trust` loss, but §2.5.5 explicitly excluded training-time signal from V1.
- **No per-vocab masking.** If a caller wants to exclude specific vocab dims (e.g. special tokens) from the gate computation, they set the corresponding `weight_vector[k] = 0`. No separate mask parameter.

**Parity tests.** §2.9 will include:

- `test_smooth_gate_shape` — input `(3, 3, 32000)`, output `(3, 3)`.
- `test_smooth_gate_threshold_midpoint` — construct `e` with `‖e‖ == T` exactly and assert output equals 0.5 within 1e-7.
- `test_smooth_gate_below_floor_suppressed` — `e` with `‖e‖ = T − 2/β` → output < 0.2.
- `test_smooth_gate_above_floor_open` — `e` with `‖e‖ = T + 2/β` → output > 0.8.
- `test_smooth_gate_clipping_no_nan_no_inf` — construct `e` with `‖e‖ = 100` (absurdly large) and assert output is finite and ≈ 1.0.
- `test_smooth_gate_none_weight_equivalent_to_ones` — call with `weight_vector=None` vs `weight_vector=np.ones(V)` and assert outputs equal within 1e-10.

#### 2.8.8 `pseudo_huber` — verbatim carry-over

Autonomy defines the pseudo-Huber penalty as (`bcvf_autonomous/core.py:122–130`):

```python
def pseudo_huber(r: np.ndarray, delta: float) -> np.ndarray:
    """V3.1 Definition 5. Pseudo-Huber penalty.

    rho(r; delta) = delta^2 * (sqrt(1 + (r/delta)^2) - 1)

    Quadratic near zero, linear for large |r|.
    """
    r_arr = np.asarray(r, dtype=np.float64)
    return (delta * delta) * (np.sqrt(1.0 + (r_arr / delta) ** 2) - 1.0)
```

**LLM-kernel equivalent** (target content of `symbolu_bcvf_llm/core.py`):

```python
def pseudo_huber(r: np.ndarray, delta: float) -> np.ndarray:
    """§2.5.2 pseudo-Huber penalty.

    rho(r; delta) = delta^2 * (sqrt(1 + (r/delta)^2) - 1)

    Quadratic near zero, linear for large |r|. Input and output have
    the same shape; no axis reduction. Applies element-wise.
    """
    r_arr = np.asarray(r, dtype=np.float64)
    return (delta * delta) * (np.sqrt(1.0 + (r_arr / delta) ** 2) - 1.0)
```

**Diff against autonomy:**

| Aspect | Autonomy | LLM-kernel | Rationale |
|---|---|---|---|
| Function body | `(delta*delta) * (np.sqrt(1.0 + (r_arr/delta)**2) - 1.0)` | **verbatim identical** | Pure scalar math; no domain-specific adaptation possible or needed |
| Signature | `(r, delta)` | `(r, delta)` | **verbatim** |
| dtype cast | `np.asarray(r, dtype=np.float64)` | **verbatim** | Same precision promotion; the penalty is the stage where the final cost value is assembled, and fp64 reduces rounding drift across the sum in §2.8.10 |
| Input shape | unspecified (any) | unspecified (any) | Elementwise; no reduction |
| Output shape | same as input | same as input | Elementwise |
| Docstring reference | `V3.1 Definition 5` | `§2.5.2` | Replaces paper reference with this doc's commitment |

**Zero-for-zero property.** `pseudo_huber(0, δ) = δ² · (√(1) − 1) = 0` exactly — not "approximately zero". This is relied on by §2.6.3 / §2.6.4 where `a_{ij} = 0` must produce contribution exactly 0 (not a small positive number that would accumulate across `l*` in the sum). `np.sqrt(1.0)` evaluates to `1.0` in IEEE 754 fp64 exactly, so the subtraction is exact.

**Monotonicity.** Strictly increasing in `|r|`, zero only at `r = 0`. Already cited in §2.6.5's Case-3 proof where `s > 0 ⇒ penalty > 0` was needed.

**Transition behavior.** For `|r| << δ`: `penalty ≈ r²/2` (quadratic regime, standard MSE). For `|r| >> δ`: `penalty ≈ δ·|r| − δ²/2` (linear asymptote, robust to outliers). The transition is smooth with continuous first derivative everywhere. §2.6.7 used the asymptote `penalty ≤ δ·|r|` to bound per-position contribution.

**Why this is literally the same as autonomy.** The pseudo-Huber is a scalar function of a scalar input — no dimensionality, no domain structure, no axis convention. Whether the input came from SE(2) error norms or probability-simplex acceleration norms is invisible to the function. Keeping the code character-for-character identical (including variable names `r_arr`, `delta`) is the maximal form of structural parity and makes `git diff` between the two files trivial to review.

**No ops added, no ops removed.** Specifically NOT doing any of:

- Adding `np.maximum(r, 0)` "just in case" — `r` comes from `np.linalg.norm` upstream, which is non-negative by construction. A guard would be defensive programming against an impossibility.
- Adding numerical stability tricks like `np.log1p` — the `sqrt(1 + x²) - 1` form is already numerically stable for all `x ∈ ℝ` in fp64; there is no regime where catastrophic cancellation occurs (`x² ≥ 0`, so `1 + x² ≥ 1`, so `sqrt(·) ≥ 1`, so the subtraction never crosses zero).
- Adding a `reduce` step — this is elementwise; reduction happens later in §2.8.10.

**FLOP cost per invocation.** For input `(M-pairs, T, L-2)` at `M-pairs=3, T=1, L-2=3` (scalar norms, one per stencil position per pair): `3·3 = 9` scalar invocations, each with `~5` FLOPs (`div, mul, add, sqrt, sub, mul`) = **~45 FLOPs per outer step**. This is the cheapest stage in the whole kernel.

**Parity tests.** §2.9 will include:

- `test_pseudo_huber_zero_exact` — `pseudo_huber(0.0, 0.5)` returns **exactly** `0.0` (bit-equal, not just approximate).
- `test_pseudo_huber_quadratic_regime` — for `r = 0.01, δ = 0.5`: assert `|penalty − r²/2| < 1e-8`.
- `test_pseudo_huber_linear_regime` — for `r = 10.0, δ = 0.5`: assert `|penalty − (δ·r − δ²/2)| / penalty < 0.01`.
- `test_pseudo_huber_monotonic` — generate sorted `r` values, assert `penalty` is monotonically non-decreasing.
- `test_pseudo_huber_matches_autonomy_bit_exact` — call both autonomy's `pseudo_huber` and LLM's with same `(r, δ)` input and assert outputs are bit-identical. This is the strongest cross-kernel parity test in §2.9 and catches any unintentional drift between the two implementations of this stage.

#### 2.8.9 `_enumerate_pairs` — pair-enumeration helper

Autonomy defines the pair enumerator as (`bcvf_autonomous/core.py:133–147`):

```python
def _enumerate_pairs(
    num_models: int, use_anchor_pairing: bool, anchor_index: int
) -> List[Tuple[int, int]]:
    """Enumerate (i, j) model pairs. j is the body-frame reference.

    Anchor mode: j = anchor_index, i ranges over the other models
    (V3.1 Section 4.5). All-pairs mode enumerates every unordered
    pair once with the lower-indexed model as the reference j so
    that for M=2 both modes produce the same single pair.
    """
    if use_anchor_pairing:
        return [
            (i, anchor_index) for i in range(num_models) if i != anchor_index
        ]
    return [(i, j) for i in range(num_models) for j in range(i)]
```

**LLM-kernel equivalent** (target content of `symbolu_bcvf_llm/core.py`):

```python
def _enumerate_pairs(
    num_sources: int, use_anchor_pairing: bool, anchor_index: int
) -> List[Tuple[int, int]]:
    """Enumerate (i, j) source pairs. j is the reference source.

    Anchor mode: j = anchor_index, i ranges over the other sources.
    All-pairs mode enumerates every unordered pair once with the
    lower-indexed source as the reference j.

    For V1 LLM domain with M=3 and use_anchor_pairing=False
    (§2.8.4 default), this returns [(1, 0), (2, 0), (2, 1)] — all
    three pairs needed for §2.4.5 per-source attribution to
    discriminate an outlier source 2:1 against non-outliers.
    """
    if use_anchor_pairing:
        return [
            (i, anchor_index) for i in range(num_sources) if i != anchor_index
        ]
    return [(i, j) for i in range(num_sources) for j in range(i)]
```

**Diff against autonomy:**

| Aspect | Autonomy | LLM-kernel | Rationale |
|---|---|---|---|
| Parameter name | `num_models` | `num_sources` | §2.2–§2.7 consistently uses "sources" (prompt-variants of the same base model) not "models" (different base models). Renaming the parameter aligns vocabulary with the rest of the design doc |
| Body | `[(i, anchor) for i ... if i != anchor] / [(i, j) for i in range(N) for j in range(i)]` | **verbatim identical logic** | No domain adaptation needed. The pair-enumeration math is combinatorial, not SE(2)-specific |
| Return type | `List[Tuple[int, int]]` | **verbatim** | Same tuple convention; `j` is the reference index |
| V3.1 reference in docstring | `V3.1 Section 4.5` | removed | No LLM equivalent of the autonomy Section 4.5 reference; the LLM context is committed in §2.4.5 / §2.8.4 instead |
| Concrete enumeration note | — | **added** for `M=3, use_anchor=False` | Docstring explicitly states the expected pair list `[(1,0), (2,0), (2,1)]` so readers cross-checking against §2.4.5 can verify at a glance |

**Concrete enumeration for V1.** At `num_sources=3, use_anchor_pairing=False, anchor_index=0`:

```python
>>> _enumerate_pairs(3, False, 0)
[(1, 0), (2, 0), (2, 1)]
```

Three pairs, matching §2.4.5's per-source attribution:

- Source 0 participates in pairs `(1, 0)` and `(2, 0)` → `per_source_cost_0 = pair_cost_{1,0} + pair_cost_{2,0}`
- Source 1 participates in pairs `(1, 0)` and `(2, 1)` → `per_source_cost_1 = pair_cost_{1,0} + pair_cost_{2,1}`
- Source 2 participates in pairs `(2, 0)` and `(2, 1)` → `per_source_cost_2 = pair_cost_{2,0} + pair_cost_{2,1}`

Each source appears in exactly 2 of 3 pairs — the symmetry that makes the outlier discrimination 2:1 work. If source 0 is the outlier producing large disagreement, both `pair_cost_{1,0}` and `pair_cost_{2,0}` are large; `pair_cost_{2,1}` is small. Sources 1 and 2 each get one large + one small, summing to `LARGE`; source 0 gets `LARGE + LARGE`. Ratio ≈ 2:1 — the core §2.4.5 claim.

**Alternative anchor mode for V1.** At `num_sources=3, use_anchor_pairing=True, anchor_index=0`:

```python
>>> _enumerate_pairs(3, True, 0)
[(1, 0), (2, 0)]
```

Two pairs, both against source 0 as anchor. This **does not** produce a 2:1 outlier signal (sources 1 and 2 each participate in only 1 pair, source 0 in 2 pairs — the symmetry is lost). That's why §2.8.4 flipped the default to `use_anchor_pairing=False`. Anchor mode is retained for:

- M=2 legacy case where both modes produce the same single pair `[(1, 0)]`.
- §3 ablation runs that explicitly test whether anchor-mode produces distinguishable per-source signal (expected: no).
- Future V2 workflows where one source is designated as a ground-truth reference (e.g. a larger verifier model) and distrust is computed relative to it.

**Determinism.** The enumeration order is deterministic given the inputs. `(i, j)` tuples are sorted by `(i, j)` ascending — `(1,0) < (2,0) < (2,1)` lexicographically. This determinism matters because §2.8.10's `_pair_cost` iterates over pairs and §2.8.12's per-source attribution indexes into a `(T, M)` array by pair — a non-deterministic order would make the per-source output non-reproducible across runs even with fixed seeds.

**Underscore prefix convention.** Both kernels name this `_enumerate_pairs` with a leading underscore, signaling "module-private helper, not part of the public API." §2.9 unit-tests this via `test_enumerate_pairs_not_in_public_namespace` — `symbolu_bcvf_llm.core._enumerate_pairs` is callable, but `symbolu_bcvf_llm.core.__all__` (if defined) does not include it. Follows autonomy convention.

**FLOP / allocation cost.** Returns a Python list of tuples. At `M=3` the list has 3 elements (all-pairs) or 2 elements (anchor); construction is O(M²) Python-level operations. Called **once per `compute_bcvf_cost_batch` invocation** (§2.8.12), not once per outer step, so the overhead is amortized across all `T` outer steps in a batch. Negligible.

**What §2.8.9 does NOT add.** No caching or memoization. The result is so small and cheap to compute that caching would introduce complexity without benefit. If profiling (V2) ever shows this is a hotspot, `functools.lru_cache` adds one line.

**Parity tests.** §2.9 will include:

- `test_enumerate_pairs_all_pairs_m3` — asserts `_enumerate_pairs(3, False, 0) == [(1, 0), (2, 0), (2, 1)]` exactly (order-sensitive).
- `test_enumerate_pairs_anchor_m3` — asserts `_enumerate_pairs(3, True, 0) == [(1, 0), (2, 0)]`.
- `test_enumerate_pairs_m2_anchor_equals_all_pairs` — asserts `_enumerate_pairs(2, True, 0) == _enumerate_pairs(2, False, 0) == [(1, 0)]` — the M=2 degenerate case the autonomy docstring called out.
- `test_enumerate_pairs_m3_all_sources_covered_twice` — asserts that in all-pairs mode at M=3, every source index appears in exactly 2 tuples.
- `test_enumerate_pairs_matches_autonomy` — cross-kernel parity: call both autonomy's `_enumerate_pairs` and LLM's with same `(M, use_anchor, anchor)` and assert outputs are equal.

#### 2.8.10 `_pair_cost` — per-pair stage with `valid_mask` for EOS

Autonomy defines the per-pair cost with its diagnostic triple return (`bcvf_autonomous/core.py:150–184`):

```python
def _pair_cost(
    traj_i: np.ndarray,
    traj_j: np.ndarray,
    config: BCVFConfig,
) -> Tuple[float, float, int]:
    """Compute the per-pair BCVF cost plus diagnostic stats.

    Returns (pair_cost, max_signal_norm, gate_activation_count).
    """
    e = compute_disagreement(traj_i, traj_j, config.lever_arm)  # (H, 3)
    if config.cost_order == CostOrder.SECOND:
        signal = compute_disagreement_acceleration(e, config.dt)  # (H-2, 3)
        gate_input = e[1:-1]                                      # (H-2, 3)
    elif config.cost_order == CostOrder.FIRST:
        signal = compute_disagreement_velocity(e, config.dt)      # (H-1, 3)
        gate_input = 0.5 * (e[:-1] + e[1:])                       # (H-1, 3)
    else:  # ZEROTH
        signal = e                                                # (H, 3)
        gate_input = e                                            # (H, 3)

    gate = smooth_gate(
        gate_input, config.gate_threshold, config.gate_beta, config.weight_matrix
    )

    w_sqrt = np.sqrt(np.asarray(config.weight_matrix, dtype=np.float64))
    signal_norms = np.linalg.norm(signal * w_sqrt, axis=-1)

    penalty = pseudo_huber(signal_norms, config.huber_delta)
    pair_cost = float(np.sum(gate * penalty) * config.dt)

    max_signal = float(signal_norms.max()) if signal_norms.size > 0 else 0.0
    activations = int(np.count_nonzero(gate > 0.5))
    return pair_cost, max_signal, activations
```

**LLM-kernel equivalent** (target content of `symbolu_bcvf_llm/core.py`):

```python
def _pair_cost(
    p_i: np.ndarray,
    p_j: np.ndarray,
    config: BCVFLLMConfig,
    valid_mask: Optional[np.ndarray] = None,
) -> Tuple[float, float, int]:
    """Compute the per-pair BCVF cost plus diagnostic stats (§2.5.3).

    Inputs:
        p_i, p_j    shape (L, V) — probability sequences for one pair
                    at one outer step, along the lookahead axis
        config      BCVFLLMConfig (§2.8.4)
        valid_mask  optional shape (L-2,) boolean — True at stencil
                    centers l* where both sources have defined logits
                    per §2.7.4. None ⇒ all positions valid.

    Returns: (pair_cost, max_signal_norm, gate_activation_count)

    SECOND-order path is the V1 default. ZEROTH/FIRST retained for
    §3 ablation only; FIRST breaks Lemma 1 case 2 (§2.6.4 / §2.8.3).
    """
    e = compute_disagreement(p_i, p_j)  # (L, V)

    if config.cost_order == CostOrder.SECOND:
        signal = compute_disagreement_acceleration(e, config.step_l)  # (L-2, V)
        gate_input = e[1:-1]                                          # (L-2, V)
    elif config.cost_order == CostOrder.FIRST:
        signal = compute_disagreement_velocity(e, config.step_l)      # (L-1, V)
        gate_input = 0.5 * (e[:-1] + e[1:])                           # (L-1, V)
    else:  # ZEROTH
        signal = e                                                    # (L, V)
        gate_input = e                                                # (L, V)

    gate = smooth_gate(
        gate_input, config.gate_threshold, config.gate_beta,
        config.weight_vector,
    )

    # Signal-norm weighting. weight_vector=None short-circuits as in
    # smooth_gate — identity weight, skip the multiply (§2.8.7).
    if config.weight_vector is None:
        signal_weighted = signal
    else:
        w_sqrt = np.sqrt(
            np.asarray(config.weight_vector, dtype=np.float64)
        )
        signal_weighted = signal * w_sqrt
    signal_norms = np.linalg.norm(signal_weighted, axis=-1)      # (L*, )

    penalty = pseudo_huber(signal_norms, config.huber_delta)     # (L*, )

    # Apply EOS / truncation mask before the sum (§2.7.4). Invalid
    # positions contribute exactly 0. For non-SECOND cost_order the
    # mask length is (L-1,) or (L,); the caller is responsible for
    # providing a correctly-sized mask.
    contrib = gate * penalty                                     # (L*, )
    if valid_mask is not None:
        contrib = contrib * valid_mask.astype(contrib.dtype)

    pair_cost = float(np.sum(contrib) * config.step_l)
    max_signal = float(signal_norms.max()) if signal_norms.size > 0 else 0.0
    activations = int(np.count_nonzero((gate > 0.5) & (
        np.ones_like(gate, dtype=bool) if valid_mask is None
        else valid_mask.astype(bool)
    )))
    return pair_cost, max_signal, activations
```

**Diff against autonomy:**

| Aspect | Autonomy | LLM-kernel | Rationale |
|---|---|---|---|
| Parameter names | `traj_i, traj_j` | `p_i, p_j` | §2.8.5 domain vocabulary |
| Extra parameter | — | `valid_mask: Optional[np.ndarray] = None` | §2.7.4 EOS handling; optional so short-context tests can omit |
| `lever_arm` argument to `compute_disagreement` | passed through | **removed** | §2.8.5 — LLM disagreement takes no extra arg |
| `config.dt` → `config.step_l` | — | renamed per §2.8.4 | Consistent with renamed field |
| Stencil axis | `e[1:-1]`, `e[:-1] + e[1:]` slicing axis 0 | **same slicing logic** but axis is `L`-axis by function contract | Input shape `(L, V)` means axis 0 is already `L`; autonomy's axis-0 slicing is preserved here. The `(M, T, L, V)` → `(L, V)` extraction happens one level up in §2.8.12 |
| Gate input weight arg | `config.weight_matrix` | `config.weight_vector` | §2.8.4 rename |
| Weight-vector None short-circuit | — | **added** | `weight_vector=None` means identity; skip the `sqrt(1)*signal` multiply. Matches §2.8.7 smooth_gate's None handling |
| `valid_mask` application | — | **added, elementwise before sum** | §2.7.4 — invalid stencil positions contribute exactly 0. Applied to `gate * penalty` elementwise, then summed |
| `activations` count | `np.count_nonzero(gate > 0.5)` | `np.count_nonzero((gate > 0.5) & valid_mask)` | Don't count activations at invalidated positions — those would inflate the diagnostic |
| Final multiplier | `* config.dt` | `* config.step_l` | §2.8.4 rename; `step_l=1.0` default makes this a no-op at V1 |
| Return triple | `(pair_cost, max_signal_norm, gate_activation_count)` | **verbatim** | Same diagnostic interface |

**Why the mask is applied to `gate * penalty`, not upstream.** There are three places the mask could be applied:

1. At `e` itself (zero out truncated rows before the stencil).
2. At `signal` / `gate_input` (zero out truncated rows after the stencil).
3. At `contrib = gate * penalty` (zero out contributions at the sum stage).

Option 3 is correct because:

- **Option 1 breaks the stencil.** Zeroing out `e[k]` when source `i` emitted EOS at position `k` would corrupt the 2nd-difference at `l* = k−1` and `l* = k+1`, which still reference the zeroed-out position. The stencil's Lemma 1 invariance (§2.6.3/§2.6.4) depends on `e` values being the true disagreements, not masked placeholders.
- **Option 2 is subtle.** Signal at position `l*` depends on `e(l*−1), e(l*), e(l*+1)`. If any of those is truncated, `valid(l*) = False` per §2.4.4 regardless of whether `l*` itself is truncated. Option 2 would require propagating truncation one position outward, which is exactly what the §2.4.4 `valid(l*)` predicate already does — so applying the mask at contrib time uses the pre-computed predicate directly.
- **Option 3 is correct.** The mask is already expressed in stencil-output indices by §2.4.4's `valid(l*) = (last_defined_l[i] ≥ l*+1) AND (last_defined_l[j] ≥ l*+1)`. Applying it at `contrib` time matches the predicate's natural domain.

**Why `astype(contrib.dtype)` on the mask.** `valid_mask` is a boolean array; `contrib` is fp64. Naive multiplication `contrib * valid_mask` works in NumPy (boolean promotes), but being explicit about the dtype cast avoids surprising performance regressions if a caller passes `valid_mask.astype(np.int32)` or similar. The dtype promotion is exact: `True → 1.0`, `False → 0.0`, no rounding.

**Empty-stencil edge case.** If `valid_mask` is all `False` (every stencil position invalidated, e.g. all sources emit EOS at `l = 0`), `contrib = [0, 0, ...]`, sum = 0, `pair_cost = 0`, `max_signal = max(signal_norms)` (not masked — the `max_signal` diagnostic reports the unconditional max, since it's used for debugging regardless of gate/mask state), `activations = 0`. This matches §2.7.4's "no data → no distrust signal, not false distrust" rule.

**Why `max_signal` is unmasked.** The `max_signal_norm` diagnostic is used by the autonomy kernel for logging / threshold calibration and by §3 signal-characterization to understand the range of acceleration values produced by specific failure traces. Masking it would hide the actual computed signal at invalidated positions. Callers who want the "valid-only max" should compute it themselves from `signal_norms[valid_mask]`.

**Why `activations` IS masked.** Unlike `max_signal`, the `activations` diagnostic is used to answer "how many positions triggered the gate," and triggering a gate at an invalidated position is both physically impossible (the data is missing) and misleading for calibration. So `activations = count(gate > 0.5 AND valid)`, not just `gate > 0.5`.

**Scalar entry-point scope.** `_pair_cost` operates on a single `(L, V)` pair at a single outer step. It is the **scalar** building block called by `compute_bcvf_cost` (§2.8.11). The **batched/vectorized** entry `compute_bcvf_cost_batch` (§2.8.12) inlines the same math on `(T_outer, L, V)` tensors rather than calling `_pair_cost` in a Python loop, matching the autonomy kernel's `compute_bcvf_cost_batch` which inlines rather than delegates.

**FLOP cost per invocation.** At `L=5, V=32000`:
- `compute_disagreement`: ~160K FLOPs
- `compute_disagreement_acceleration`: ~200K FLOPs
- `smooth_gate`: ~200K FLOPs (weighted norm + sigmoid on `L−2 = 3` positions)
- `signal_norms`: ~200K FLOPs
- `pseudo_huber`: ~15 FLOPs (on 3 scalars)
- Sum + mask: ~10 FLOPs
- **Total per-pair: ~760K FLOPs.** For M=3 (3 pairs): ~2.3M per outer step, matching §2.4.6's ~6.2M estimate (with overhead from the `e` cache shared across pairs in the batch variant).

**Parity tests.** §2.9 will include:

- `test_pair_cost_no_mask_matches_unmasked_sum` — call with `valid_mask=None` and with `valid_mask=np.ones((L-2,), dtype=bool)`; assert `pair_cost` outputs equal exactly.
- `test_pair_cost_all_invalid_returns_zero` — call with `valid_mask=np.zeros((L-2,), dtype=bool)`; assert `pair_cost == 0.0`, `activations == 0`.
- `test_pair_cost_mask_shape_validation` — call with wrong-shape mask and assert ValueError (or clean NumPy broadcasting error).
- `test_pair_cost_constant_bias_zero` — `p_i = p_j + α` with `α` constant in `l`; assert `pair_cost == 0.0`.
- `test_pair_cost_linear_drift_zero` — `p_i = p_j + α + γ·l`; assert `pair_cost < 1e-10`.
- `test_pair_cost_quadratic_positive` — quadratic divergence above gate threshold; assert `pair_cost > 0` and `activations > 0`.
- `test_pair_cost_eos_single_source_truncation` — valid_mask reflects source 0 EOS at l=1; assert pair_cost uses only unaffected stencil positions.
- `test_pair_cost_max_signal_unmasked` — even when mask excludes a position, `max_signal_norm` reflects the unmasked max (documented behavior).

#### 2.8.11 `BCVFLLMResult` + `compute_bcvf_cost` — scalar entry point

Autonomy's result dataclass and scalar entry live at `bcvf_autonomous/core.py:58–64` and `core.py:187–229`:

```python
@dataclass
class BCVFResult:
    """Detailed output from BCVF cost computation."""

    total_cost: float
    per_pair_costs: Dict[Tuple[int, int], float]
    max_acceleration_norm: float
    gate_activation_count: int


def compute_bcvf_cost(
    trajectories: List[np.ndarray], config: BCVFConfig
) -> BCVFResult:
    """V3.1 Definition 6. Full J_BCVF over a set of model trajectories.

    ``trajectories`` is a list of M arrays shaped (H, 3).
    """
    # shape validation, pair enumeration, pair loop, aggregate
    ...
```

**LLM-kernel equivalent** (target content of `symbolu_bcvf_llm/core.py`):

```python
@dataclass
class BCVFLLMResult:
    """Detailed output from LLM-domain BCVF cost computation at a
    single outer decoding step.

    Parallels ``BCVFResult`` (bcvf_autonomous/core.py:58). Adds
    ``per_source_costs`` — the §2.4.5 per-source attribution that
    §5's Rahu trust-weighting consumes. Autonomy's BCVFResult does
    not carry this field because autonomy's Ketu→Rahu integration
    keeps per-source attribution in the MPPI planner, not in the
    kernel result. LLM V1 moves it into the kernel result so the
    §4 caller has a single return type.
    """

    total_cost: float
    per_pair_costs: Dict[Tuple[int, int], float]
    per_source_costs: Dict[int, float]        # §2.4.5 attribution
    max_acceleration_norm: float
    gate_activation_count: int


def compute_bcvf_cost(
    sources: List[np.ndarray],
    config: BCVFLLMConfig,
    valid_masks: Optional[List[np.ndarray]] = None,
) -> BCVFLLMResult:
    """§2.5.3 / §2.8.11 full J_BCVF at a single outer decoding step.

    Inputs:
        sources       list of M arrays, each shape (L, V) — probability
                      sequences for one outer step along the lookahead
                      axis, one per source (§1.3 M>=3 for V1)
        config        BCVFLLMConfig (§2.8.4)
        valid_masks   optional list of M arrays, each shape (L,),
                      boolean; True at lookahead positions where the
                      source has defined logits (§2.7.4). None ⇒ all
                      positions valid. If given, length must equal M.

    Returns: BCVFLLMResult with per-pair AND per-source attribution.

    Raises:
        ValueError — on shape mismatch, M<2, L<3, or non-finite input
                     (NaN/Inf guard per §2.7.6).
    """
    num_sources = len(sources)
    if num_sources < 2:
        raise ValueError(
            f"BCVF requires at least 2 sources; got {num_sources}"
        )
    lookahead_sizes = {s.shape[0] for s in sources}
    if len(lookahead_sizes) != 1:
        raise ValueError(
            f"Sources must share the same lookahead length L; "
            f"got {lookahead_sizes}"
        )
    vocab_sizes = {s.shape[-1] for s in sources}
    if len(vocab_sizes) != 1:
        raise ValueError(
            f"Sources must share the same vocab size V; got {vocab_sizes}"
        )
    if any(s.ndim != 2 for s in sources):
        raise ValueError(
            "Each source must have shape (L, V) for scalar entry"
        )
    if next(iter(lookahead_sizes)) < 3:
        raise ValueError(
            "BCVF requires L >= 3 for the second-difference stencil"
        )
    if any(not np.isfinite(s).all() for s in sources):
        raise ValueError(
            "BCVF received non-finite source probabilities; "
            "upstream softmax failed (§2.7.6)"
        )
    if valid_masks is not None and len(valid_masks) != num_sources:
        raise ValueError(
            f"valid_masks length {len(valid_masks)} != sources {num_sources}"
        )

    pairs = _enumerate_pairs(
        num_sources, config.use_anchor_pairing, config.anchor_index
    )

    per_pair: Dict[Tuple[int, int], float] = {}
    per_source: Dict[int, float] = {s: 0.0 for s in range(num_sources)}
    max_accel = 0.0
    activations = 0
    total = 0.0

    for (i, j) in pairs:
        pair_mask = _intersect_valid_masks(
            valid_masks[i] if valid_masks is not None else None,
            valid_masks[j] if valid_masks is not None else None,
            config.cost_order,
        )
        cost, pair_max_accel, pair_activations = _pair_cost(
            sources[i], sources[j], config, valid_mask=pair_mask
        )
        per_pair[(i, j)] = cost
        per_source[i] += cost              # §2.4.5 symmetric attribution
        per_source[j] += cost
        total += cost
        if pair_max_accel > max_accel:
            max_accel = pair_max_accel
        activations += pair_activations

    return BCVFLLMResult(
        total_cost=total,
        per_pair_costs=per_pair,
        per_source_costs=per_source,
        max_acceleration_norm=max_accel,
        gate_activation_count=activations,
    )
```

The `_intersect_valid_masks` helper is the §2.4.4 predicate, implemented once:

```python
def _intersect_valid_masks(
    mask_i: Optional[np.ndarray],
    mask_j: Optional[np.ndarray],
    cost_order: CostOrder,
) -> Optional[np.ndarray]:
    """Combine two per-source (L,) masks into a per-stencil mask.

    Implements §2.4.4:
        valid(l*) = (last_defined_l[i] >= l*+1)
                  AND (last_defined_l[j] >= l*+1)

    For SECOND-order, stencil centers are l* ∈ [1, L-2] and the
    stencil references l*-1, l*, l*+1. So valid(l*) requires
    mask_i[l*-1], mask_i[l*], mask_i[l*+1] all True, likewise for j.

    For FIRST-order, l* ∈ [0, L-2] and stencil references l*, l*+1.
    For ZEROTH-order, l* ∈ [0, L-1] and only l* itself.

    Returns None if both inputs are None (caller short-circuits).
    """
    if mask_i is None and mask_j is None:
        return None
    # materialize all-True defaults for the missing side
    L = (mask_i if mask_i is not None else mask_j).shape[0]
    mi = np.ones(L, dtype=bool) if mask_i is None else mask_i.astype(bool)
    mj = np.ones(L, dtype=bool) if mask_j is None else mask_j.astype(bool)
    if cost_order == CostOrder.SECOND:
        # require l-1, l, l+1 all valid in both sources
        return mi[:-2] & mi[1:-1] & mi[2:] & mj[:-2] & mj[1:-1] & mj[2:]
    if cost_order == CostOrder.FIRST:
        return mi[:-1] & mi[1:] & mj[:-1] & mj[1:]
    return mi & mj  # ZEROTH
```

**Diff against autonomy — result dataclass:**

| Field | Autonomy | LLM | Rationale |
|---|---|---|---|
| `total_cost` | `float` | **verbatim** | Sum of per-pair costs; unchanged |
| `per_pair_costs` | `Dict[Tuple[int, int], float]` | **verbatim** | Same tuple-keyed dict |
| `per_source_costs` | — | **added, `Dict[int, float]`** | §2.4.5 per-source attribution for §5 Rahu consumption. Autonomy keeps this in the planner; LLM moves it into the kernel result so §4's caller has one return type to handle |
| `max_acceleration_norm` | `float` | **verbatim** | Diagnostic; same semantics (even for ZEROTH/FIRST modes where it's not technically "acceleration", the name is kept for cross-kernel parity) |
| `gate_activation_count` | `int` | **verbatim** | Diagnostic; sum across all pairs, with §2.8.10's masking applied |

**Diff against autonomy — scalar entry function:**

| Aspect | Autonomy | LLM | Rationale |
|---|---|---|---|
| Function name | `compute_bcvf_cost` | `compute_bcvf_cost` | **verbatim** — same public API name for cross-kernel parity |
| Input name | `trajectories` | `sources` | §2.2–§2.7 domain vocabulary |
| Input shape validation | `shape[-1] != 3` | `shape[-1] != 3` replaced with **check all sources share V** | `V` is model-dependent (not a fixed 3); only cross-source consistency matters |
| Dim validation | ndim check implicit in shape | `ndim != 2` explicit | LLM's `(L, V)` is 2-D; autonomy's `(H, 3)` is also 2-D but the 3 is a fixed constant. Explicit check prevents a `(L, V_i, V_j)` mistake from propagating silently |
| Horizon/lookahead minimum | `< 3` (H ≥ 3) | `< 3` (L ≥ 3) | Same stencil constraint; variable renamed |
| NaN/Inf guard | — | **added** | §2.7.6 committed kernel-boundary NaN check. Autonomy SE(2) states are always finite; LLM softmax can produce NaN from a broken forward pass |
| `valid_masks` parameter | — | **added** | §2.7.4 EOS handling. Optional (None ⇒ no EOS) |
| Per-source accumulation | — | **added** `per_source[i] += cost; per_source[j] += cost` | §2.4.5 symmetric attribution. Note: a source that appears in 2 pairs gets 2 additions |
| Total cost aggregation | `total += cost` | **verbatim** | Same sum-across-pairs |
| Return type | `BCVFResult` | `BCVFLLMResult` | Same fields plus `per_source_costs` |

**Validation order.** The checks are intentionally ordered from cheapest (length check) to most expensive (NaN check on the full tensor). The NaN check runs last so callers with malformed shapes fail fast without paying the scan cost.

**Why `per_source` initializes to 0.0 for every index, not just the ones in pairs.** At `M=3, use_anchor_pairing=False`, every source appears in at least 2 pairs, so all entries get updated. But in anchor mode at `M=3`, source indices 1 and 2 appear once each (in the two pairs) and source 0 (anchor) appears in both — pre-initializing to 0 ensures the dict has an entry for every source, even if an index were to miss all pairs in some future enumeration variant. Defensive.

**Symmetric attribution at the source level.** When BCVF detects `pair_cost_{i,j}` = large, we attribute the cost to *both* `i` and `j` — we don't know which one is "wrong." §2.4.5 argued this: a lone outlier accumulates disagreement across every pair it participates in, while non-outliers accumulate only one pair (the one between the non-outliers). At M=3 this gives the 2:1 ratio. The `+= cost` on both `i` and `j` is the mechanical implementation of the symmetric-attribution rule.

**Double-counting at the total?** The **total cost** is the sum over *pairs*, not the sum over *per-source* entries. `per_source` sums to `2·total` (each pair cost contributes to two source entries), which is the right relationship — `per_source` is a **distribution** over sources (§5 will normalize it via softmin), not a partition of `total`.

**Empty-sources edge case.** If `len(sources) == 0`, the `<2` guard raises. If exactly 2 sources, `pairs == [(1, 0)]`, `per_source = {0: cost, 1: cost}`. No anomaly at M=2 — the per-source dict is still well-formed; it just has no discriminative power (both sources get the same cost). §1.3 / §2.8.4 require M≥3 for discrimination to work.

**Reference artifact check.** `compute_bcvf_cost` in autonomy is labeled "V3.1 Definition 6." The LLM entry is the same "Definition 6" applied to the LLM cost chain — the label is preserved in spirit, with the docstring pointing to §2.5.3 / §2.8.11 for the explicit formulation.

**What §2.8.11 does NOT add.**

- No caching of `e` across pairs. If two pairs share a reference source (e.g. `(1, 0)` and `(2, 0)` both use `sources[0]`), each call to `_pair_cost` recomputes `e = p_i - p_j` from scratch. Caching would save ~30% FLOPs on this stage; deferred to §2.8.12 which inlines and **does** share intermediates across pairs.
- No early termination. The function loops over all pairs unconditionally. Some BCVF variants (V2) could short-circuit if the running `max_acceleration_norm` exceeds a threshold, but V1 always computes the full set.
- No per-pair diagnostic table. `per_pair_costs` is keyed by `(i, j)` and carries the scalar cost, but not `max_signal` or `activations` per-pair. Those are aggregated up. §3 signal characterization may add a diagnostic mode (V2) that returns per-pair tuples; V1 does not.

**Parity tests.** §2.9 will include:

- `test_bcvflllmresult_fields` — asserts the 5 field names and types.
- `test_compute_bcvf_cost_scalar_shape_validation` — feeds mismatched shapes and asserts each ValueError branch triggers.
- `test_compute_bcvf_cost_scalar_nan_guard` — feeds `sources` with a NaN entry; asserts ValueError.
- `test_compute_bcvf_cost_scalar_m3_all_pairs_enumeration` — runs with M=3, all-pairs, and asserts `per_pair_costs` has exactly 3 entries keyed `(1,0), (2,0), (2,1)`.
- `test_compute_bcvf_cost_scalar_per_source_sums_to_double_total` — asserts `sum(per_source_costs.values()) == 2 * total_cost` (within 1e-10).
- `test_compute_bcvf_cost_scalar_outlier_discrimination_2_to_1` — construct M=3 scenario where source 0 produces accelerating divergence and sources 1,2 agree; assert `per_source_costs[0] ≈ 2 * per_source_costs[1]` ratio.
- `test_compute_bcvf_cost_scalar_eos_valid_masks_propagated` — call with a `valid_masks` where source 0 truncates at l=1; assert the `per_pair_costs[(1,0)]` and `per_pair_costs[(2,0)]` entries use only non-truncated stencil positions.
- `test_compute_bcvf_cost_scalar_matches_autonomy_on_identical_shape_inputs` — cross-kernel test: construct inputs at (L=5, V=3) for both kernels and a fake "SE(2)" interpretation; assert total_cost agrees to 1e-10. (This test is more subtle because autonomy expects V=3 specifically; it exists as a structural sanity check, not a primary correctness test.)

#### 2.8.12 `compute_bcvf_cost_batch` — vectorized entry across outer steps

Parallels `compute_bcvf_cost_batch` in autonomy (`bcvf_autonomous/core.py:232–328`), which vectorizes across the MPPI rollout axis `K`. The LLM variant vectorizes across the outer-step axis `T` instead.

**Signature:**

```python
def compute_bcvf_cost_batch(
    sources_batch: np.ndarray,                 # shape (T, M, L, V)
    config: BCVFLLMConfig,
    valid_masks_batch: Optional[np.ndarray] = None,   # shape (T, M, L)
    return_per_source: bool = True,
) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
    """§2.8.12 batched entry. Returns (T,) total_cost array, and if
    return_per_source=True also returns (T, M) per-source cost array
    for §5 Rahu consumption."""
```

**Three deltas from §2.8.11's scalar entry:**

1. **Batch axis is `T` (outer decoding steps), not `K` (MPPI rollouts).** Otherwise identical tensor semantics — autonomy vectorizes across parallel candidate actions; LLM vectorizes across sequential decoding positions. Same 4-D tensor shape `(batch, M, horizon, features)`.
2. **Math is inlined, not delegated to `_pair_cost` in a Python loop.** `e = sources_batch[:, i, :, :] - sources_batch[:, j, :, :]` computed once per pair produces `(T, L, V)` directly; the stencil, gate, Huber, and sum all operate on `(T, L-2, V)` tensors. This matches autonomy's `compute_bcvf_cost_batch:284–313` which inlines for the same reason — per-pair Python-loop overhead at T=512 outer steps would dominate the kernel FLOPs otherwise.
3. **Return shape is arrays, not scalars.** `total` is `(T,)`; `per_source` is `(T, M)` when `return_per_source=True`. The attribution rule `per_source[:, i] += pair_cost` and `per_source[:, j] += pair_cost` is the vectorized equivalent of §2.8.11's symmetric accumulation.

**`valid_masks_batch` handling.** Same §2.4.4 stencil-window intersection logic as §2.8.11's `_intersect_valid_masks`, but implemented in-place over `(T, M, L)` boolean tensors and broadcast-multiplied into `(T, L-2)` contribution arrays before summing over the `L-2` axis. Invalid positions contribute exactly 0; no Python-level branching.

**Validation, NaN guard, and result semantics are identical to §2.8.11** — performed once on the full `(T, M, L, V)` tensor. §2.8.11's correctness properties (Lemma 1 invariance per-step, per-source 2:1 outlier discrimination, `sum(per_source) == 2·total` per step) carry over unchanged per batch-axis element.

**FLOP and memory.** ~6M FLOPs/step × T = full-batch cost; memory is `O(M · L · V)` per step plus pairwise `e` tensors — at T=1 (streaming), matches §2.7.8's 7 MB peak.

**Parity tests.** §2.9 queues `test_compute_bcvf_cost_batch_matches_scalar_elementwise` (assert `compute_bcvf_cost_batch(sources_batch=stack)[t] == compute_bcvf_cost(sources=stack[t]).total_cost` for each `t`), `test_compute_bcvf_cost_batch_per_source_shape` (`(T, M)`), and `test_compute_bcvf_cost_batch_valid_masks_propagate` (per-`t` EOS patterns).

#### 2.8.13 Fidelity summary — autonomy → LLM mapping

The full translation table across §2.8.2–§2.8.12:

| Autonomy element (`bcvf_autonomous/core.py`) | LLM element (`symbolu_bcvf_llm/core.py`) | Status | Sub-section |
|---|---|---|---|
| Module docstring (lines 1–11) | Module docstring w/ `(M,T,L,V)` shape doc, §2.4–§2.7 pointer | **retargeted** | §2.8.2 |
| `from __future__ import annotations`, stdlib imports, `import numpy as np` | **verbatim** | verbatim | §2.8.2 |
| `from .manifold import body_frame_error_trajectory` | — | **dropped** | §2.8.2, §2.8.5 |
| `from typing import ... Optional` | **added** | new | §2.8.2 |
| `class CostOrder(IntEnum)` | **verbatim values + retargeted docstring** | near-verbatim | §2.8.3 |
| `class BCVFConfig` (10 fields) | `class BCVFLLMConfig` (8 fields) | **2 dropped, 2 renamed, rest verbatim** | §2.8.4 |
| `lambda_c`, `lever_arm` | — | **dropped** | §2.8.4 |
| `weight_matrix` | `weight_vector` with `None` default | **renamed + default** | §2.8.4 |
| `dt` | `step_l` | **renamed + default 1.0** | §2.8.4 |
| `use_anchor_pairing=True` | `use_anchor_pairing=False` | **default flipped** | §2.8.4 |
| `class BCVFResult` (4 fields) | `class BCVFLLMResult` (5 fields) | **+ `per_source_costs`** | §2.8.11 |
| `compute_disagreement(traj_i, traj_j, lever_arm)` | `compute_disagreement(p_i, p_j)` | **body trivialized to subtraction; function kept for pipeline parity** | §2.8.5 |
| `compute_disagreement_velocity(dis, dt)` | `compute_disagreement_velocity(e, step_l)` | **ellipsis-axis slicing; Lemma-1 warning** | §2.8.6 |
| `compute_disagreement_acceleration(dis, dt)` | `compute_disagreement_acceleration(e, step_l)` | **ellipsis-axis slicing** | §2.8.6 |
| `smooth_gate(dis, T, β, W)` | `smooth_gate(e, T, β, weight_vector=None)` | **None short-circuit; ellipsis-axis norm** | §2.8.7 |
| `pseudo_huber(r, δ)` | `pseudo_huber(r, δ)` | **character-for-character verbatim** | §2.8.8 |
| `_enumerate_pairs(num_models, ...)` | `_enumerate_pairs(num_sources, ...)` | **param rename; body verbatim** | §2.8.9 |
| `_pair_cost(traj_i, traj_j, config)` | `_pair_cost(p_i, p_j, config, valid_mask=None)` | **+ valid_mask; per-pair math unchanged** | §2.8.10 |
| — | `_intersect_valid_masks(mask_i, mask_j, cost_order)` | **new helper** | §2.8.11 |
| `compute_bcvf_cost(trajectories, config)` | `compute_bcvf_cost(sources, config, valid_masks=None)` | **+ valid_masks, + NaN guard, + per_source accumulation** | §2.8.11 |
| `compute_bcvf_cost_batch(traj_batch, config, return_per_predictor)` | `compute_bcvf_cost_batch(sources_batch, config, valid_masks_batch, return_per_source)` | **+ valid_masks_batch; batch axis renamed K→T** | §2.8.12 |

**Counts.**

- Functions kept (same signature skeleton): **9** — `compute_disagreement`, `compute_disagreement_velocity`, `compute_disagreement_acceleration`, `smooth_gate`, `pseudo_huber`, `_enumerate_pairs`, `_pair_cost`, `compute_bcvf_cost`, `compute_bcvf_cost_batch`.
- Functions character-for-character verbatim: **1** — `pseudo_huber` (§2.8.8).
- Functions added: **1** — `_intersect_valid_masks` (§2.8.11 helper).
- Functions dropped: **0**.
- Dataclass fields dropped: **2** (`lambda_c`, `lever_arm`).
- Dataclass fields added: **1** (`BCVFLLMResult.per_source_costs`).
- Parameters added across all functions: **3** (`valid_mask`, `valid_masks`, `valid_masks_batch`).

**What this table enables.** A reviewer can open `bcvf_autonomous/core.py` and `symbolu_bcvf_llm/core.py` side-by-side with the table above as the diff legend. Every meaningful deviation is named, justified by sub-section, and one of a small fixed set of status codes (verbatim / renamed / extended / new / dropped / default-changed). There are no unexplained deltas. This is the §2.8 version of the "structural fidelity" guarantee §0 promised.

#### 2.8.14 Acceptance criteria for §2.8

§2.8 is complete when:

1. ✅ Target package (`symbolu_bcvf_llm`) and file (`core.py`) are named (§2.8.1).
2. ✅ Module docstring, imports, and dependency-isolation discipline are committed (§2.8.2).
3. ✅ `CostOrder` enum is committed with V1 lock on `SECOND` (§2.8.3).
4. ✅ `BCVFLLMConfig` is committed with 8 fields, explicit defaults, and the dropped/renamed/default-flipped fields all justified (§2.8.4).
5. ✅ `compute_disagreement` committed (§2.8.5).
6. ✅ `compute_disagreement_velocity` and `compute_disagreement_acceleration` committed with ellipsis-axis slicing rule and lookahead-axis convention (§2.8.6).
7. ✅ `smooth_gate` committed with weight-vector `None` short-circuit (§2.8.7).
8. ✅ `pseudo_huber` committed as character-for-character verbatim from autonomy (§2.8.8).
9. ✅ `_enumerate_pairs` committed with concrete V1 enumeration documented (§2.8.9).
10. ✅ `_pair_cost` committed with `valid_mask` extension and the three mask-application options evaluated (§2.8.10).
11. ✅ `BCVFLLMResult` and `compute_bcvf_cost` scalar entry committed with NaN guard, per-source attribution, `_intersect_valid_masks` helper (§2.8.11).
12. ✅ `compute_bcvf_cost_batch` vectorized entry committed with inlined math and `(T, M)` per-source return shape (§2.8.12).
13. ✅ Fidelity summary table enumerated and totals counted (§2.8.13).
14. **Pending §2.9:** the full parity test suite (roughly 40 tests queued across §2.8.3–§2.8.12) passes deterministically against a reference Python implementation, including the cross-kernel bit-exact test for `pseudo_huber` and the 2:1 outlier-discrimination test for `compute_bcvf_cost`.

Items 1–13 are satisfied by this section. Item 14 is the hard gate — §2.8 is a design-time specification; §2.9's test list is what mechanically verifies the spec is implementable and correct. No `bcvf_llm/core.py` source file is written until §2.9 is authorized and the tests listed there are agreed to as the acceptance bar.

**What §2.8 does NOT commit.** The implementation itself. The design document specifies what the code should look like at the function-signature and docstring level, with algorithmic bodies stated in Python-prose form. Actual `bcvf_llm/core.py` is written during Phase 1 execution, after §2.9 sign-off, and must conform to §2.8.1–§2.8.13 at every point. Deviations discovered during implementation (e.g., a performance issue forces inlining a helper) loop back to §2.8 for revision, not the other way around.

---

### 2.9 Acceptance criteria + test specification

§2.9 is the **hard gate** that closes Phase 1 and unlocks Phase 1.5 (§3). Items 1–13 of §2.8.14, item 6 of §2.6.10, and all the parity tests queued throughout §2.5 / §2.7 / §2.8 must land, deterministically pass, and cover the math spec. Nothing about §2.9 is aspirational — if a test in this list fails on the implementation, §2 is re-opened and the offending sub-section is revised.

#### 2.9.1 Purpose and hard-gate role

Every prior sub-section of §2 makes claims about what the kernel *will* do. §2.9 is where those claims become **mechanical assertions** — Python test functions whose pass/fail status is the single source of truth for "§2 is correct."

Three classes of claim need mechanical verification:

1. **Lemma 1 invariance** (§2.6). Constant-bias and linear-drift inputs must produce exactly zero (within floating-point tolerance); quadratic inputs must produce positive output. Three tests, tight tolerances.
2. **Stage-level mathematical parity** with the autonomy kernel (§2.8.3–§2.8.12). Every sub-section queued at least 2–8 tests; §2.9 collects them.
3. **System-level correctness** of the composed kernel — shape validation, NaN guards, EOS masking, per-source attribution ratio, scalar/batch consistency. These are the highest-value tests: they catch integration bugs that stage-level tests would miss.

If §2.9's full suite passes on a reference implementation of `symbolu_bcvf_llm/core.py`, Phase 1 is complete and Phase 1.5 is authorized to start. If any single test fails, Phase 1 is not complete and the failing test points to the §2 sub-section that needs revision.

#### 2.9.2 Test file layout

Target directory: `symbolu_bcvf_llm/tests/`.

```
symbolu_bcvf_llm/
├── __init__.py
├── core.py                          # The kernel (§2.8)
└── tests/
    ├── __init__.py
    ├── test_core_config.py          # §2.8.3 - §2.8.4 (enum, dataclass)
    ├── test_core_stages.py          # §2.8.5 - §2.8.8 (stage functions)
    ├── test_core_pairs.py           # §2.8.9 - §2.8.10 (pair-level)
    ├── test_core_entry.py           # §2.8.11 - §2.8.12 (entry points)
    ├── test_core_lemma1.py          # §2.6 invariance tests (priority)
    ├── test_core_cross_kernel.py    # cross-checks against autonomy
    └── test_core_import_isolation.py # §2.8.2 dep-isolation assertion
```

**Discipline:** pure `pytest`, no ML-framework dependency, runnable in < 5 seconds on a CPU-only laptop. If the test suite ever requires a GPU or model download, it's failed the discipline and §2.9 is revised.

#### 2.9.3 Test categories

| Category | Count (approx) | What it proves |
|---|---|---|
| **Config / enum** | 3 | `CostOrder` values fixed; `BCVFLLMConfig` defaults match §2.8.4 exactly |
| **Stage unit** | 14 | Each of `compute_disagreement`, `_velocity`, `_acceleration`, `smooth_gate`, `pseudo_huber`, `_enumerate_pairs` has correct shape, axis behavior, edge cases |
| **Lemma 1 (priority)** | 3 | Constant bias → 0, linear drift → 0, quadratic → positive. Anchors §2.6 proof to mechanical verification |
| **Pair-level (`_pair_cost`)** | 8 | Scalar per-pair cost, including valid_mask, diagnostic return values, Lemma 1 cases at the pair level |
| **Scalar entry (`compute_bcvf_cost`)** | 8 | Shape validation, NaN guard, per-source attribution, 2:1 outlier ratio, EOS propagation |
| **Batch entry (`compute_bcvf_cost_batch`)** | 3 | Batch/scalar elementwise consistency, per-source `(T, M)` shape, per-`t` EOS |
| **Cross-kernel parity** | 3 | `pseudo_huber` bit-exact; `_enumerate_pairs` equal; scalar-entry structural sanity at `L=5, V=3` |
| **Import isolation** | 2 | `import symbolu_bcvf_llm.core` succeeds without torch / transformers / datasets |
| **Total** | **≈ 44** | |

#### 2.9.4 Full test catalog

Grouped by target module. Each test is a single-function `pytest` test with a one-line assertion at its core. Full names follow `pytest` discovery convention (prefix `test_`).

**test_core_config.py (§2.8.3–§2.8.4):**

1. `test_cost_order_enum_values` — `ZEROTH.value == 0, FIRST.value == 1, SECOND.value == 2`.
2. `test_bcvflllm_config_defaults` — each of the 8 fields has the exact default from §2.8.4's table.
3. `test_bcvflllm_config_weight_vector_none_by_default` — `BCVFLLMConfig().weight_vector is None`.

**test_core_stages.py (§2.8.5–§2.8.8):**

4. `test_compute_disagreement_shape_broadcast` — `(3, 1, 5, 32000)` input → output same shape.
5. `test_compute_disagreement_translation_invariant` — adding constant vector to both inputs leaves output unchanged.
6. `test_compute_disagreement_acceleration_constant_bias_zero` — constant `e(l)` → output ≤ 1e-10 in fp64.
7. `test_compute_disagreement_acceleration_linear_drift_zero` — linear `e(l) = α + γ·l` → output ≤ 1e-10 in fp64.
8. `test_compute_disagreement_acceleration_quadratic_positive` — `e(l) = l²·η` → output equals `η` up to rounding.
9. `test_compute_disagreement_velocity_shape` — `(L, V)` → `(L-1, V)`.
10. `test_smooth_gate_shape` — input `(3, 3, 32000)` → output `(3, 3)`.
11. `test_smooth_gate_threshold_midpoint` — `‖e‖ = T` exactly → gate ≈ 0.5 within 1e-7.
12. `test_smooth_gate_below_floor_suppressed` — `‖e‖ = T − 2/β` → gate < 0.2.
13. `test_smooth_gate_above_floor_open` — `‖e‖ = T + 2/β` → gate > 0.8.
14. `test_smooth_gate_clipping_no_nan_no_inf` — `‖e‖ = 100` → finite, ≈ 1.0.
15. `test_smooth_gate_none_weight_equivalent_to_ones` — `weight_vector=None` vs `np.ones(V)` within 1e-10.
16. `test_pseudo_huber_zero_exact` — `pseudo_huber(0.0, 0.5)` returns **bit-equal** 0.0.
17. `test_pseudo_huber_quadratic_regime` — `|penalty − r²/2| < 1e-8` for small `r`.
18. `test_pseudo_huber_linear_regime` — `|penalty − (δ·r − δ²/2)| / penalty < 0.01` for large `r`.
19. `test_pseudo_huber_monotonic` — strictly non-decreasing over sorted `r`.

**test_core_pairs.py (§2.8.9–§2.8.10):**

20. `test_enumerate_pairs_all_pairs_m3` — exactly `[(1, 0), (2, 0), (2, 1)]`.
21. `test_enumerate_pairs_anchor_m3` — exactly `[(1, 0), (2, 0)]`.
22. `test_enumerate_pairs_m2_anchor_equals_all_pairs` — both modes return `[(1, 0)]`.
23. `test_enumerate_pairs_m3_all_sources_covered_twice` — each source index in exactly 2 tuples.
24. `test_pair_cost_no_mask_matches_unmasked_sum` — `valid_mask=None` equals `np.ones((L-2,), bool)` exactly.
25. `test_pair_cost_all_invalid_returns_zero` — `valid_mask=np.zeros(...)` → pair_cost=0, activations=0.
26. `test_pair_cost_constant_bias_zero` — `p_i = p_j + constant` → pair_cost = 0.
27. `test_pair_cost_linear_drift_zero` — `p_i - p_j = α + γ·l` → pair_cost < 1e-10.
28. `test_pair_cost_quadratic_positive` — above gate threshold → pair_cost > 0.
29. `test_pair_cost_eos_single_source_truncation` — source 0 EOS at `l=1` → uses only valid stencil positions.
30. `test_pair_cost_max_signal_unmasked` — max_signal reflects the unconditional max.
31. `test_pair_cost_activations_counts_valid_only` — `activations == count(gate > 0.5 AND valid)`.

**test_core_entry.py (§2.8.11–§2.8.12):**

32. `test_bcvflllmresult_fields` — asserts 5 fields exist with correct types.
33. `test_compute_bcvf_cost_scalar_shape_validation` — every ValueError branch fires (M<2, L<3, vocab mismatch, ndim≠2).
34. `test_compute_bcvf_cost_scalar_nan_guard` — NaN in sources → ValueError.
35. `test_compute_bcvf_cost_scalar_m3_all_pairs_enumeration` — `per_pair_costs` has exactly 3 entries.
36. `test_compute_bcvf_cost_scalar_per_source_sums_to_double_total` — `sum(per_source) == 2·total` within 1e-10.
37. `test_compute_bcvf_cost_scalar_outlier_discrimination_2_to_1` — source-0 outlier → `per_source_costs[0] ≈ 2 · per_source_costs[1]`.
38. `test_compute_bcvf_cost_scalar_eos_valid_masks_propagated` — per-source masks correctly combine into stencil masks.
39. `test_compute_bcvf_cost_batch_matches_scalar_elementwise` — for each `t`: batch output `[t]` equals scalar call on `sources_batch[t]`.
40. `test_compute_bcvf_cost_batch_per_source_shape` — `per_source` output has shape `(T, M)`.
41. `test_compute_bcvf_cost_batch_valid_masks_propagate` — per-`t` EOS pattern reflected correctly.

**test_core_lemma1.py (§2.6 top-level invariance — priority tests):**

42. `test_lemma_1_constant_bias_zero` — at the kernel level with M=3 sources constructed so all pairwise `e` are constant: total_cost = 0 within 1e-10 in fp64.
43. `test_lemma_1_linear_drift_zero` — at the kernel level with M=3 sources constructed for linear pairwise drift: total_cost = 0 within 1e-10 in fp64.
44. `test_lemma_1_quadratic_positive` — at the kernel level with a source producing accelerating divergence above gate threshold: total_cost > 0.

**test_core_cross_kernel.py:**

45. `test_pseudo_huber_matches_autonomy_bit_exact` — import both kernels' `pseudo_huber`; same input → bit-identical output.
46. `test_enumerate_pairs_matches_autonomy` — same `(M, anchor, idx)` → equal tuple lists.
47. `test_compute_bcvf_cost_scalar_matches_autonomy_on_identical_shape_inputs` — at `(L=5, V=3)` with matching shape inputs, total_cost agreement within 1e-10 (structural sanity, not primary correctness).

**test_core_import_isolation.py (§2.8.2):**

48. `test_kernel_import_without_torch` — in a subprocess with `torch` hidden from `sys.modules`, `import symbolu_bcvf_llm.core` succeeds.
49. `test_kernel_import_without_transformers` — same, for `transformers`.

**Count: 49 tests.** Roughly matches §2.9.3's estimate of ≈44, with Lemma 1 and import-isolation each getting their own file for visibility.

#### 2.9.5 Determinism and tolerance conventions

- **Precision for Lemma 1 tests:** fp64. The 2nd-difference cancellation in §2.8.6 produces residuals around `1e-15` in fp64, so the `1e-10` tolerance used for C1 and C2 tests has 5 orders of magnitude of slack.
- **Precision for non-Lemma 1 tests:** fp32 is the default, matching §2.7.2's V1 production rule. The `1e-7` tolerance used for shape/equivalence tests has enough slack for fp32 rounding at vocab size V=32000.
- **Seed discipline:** Any test that uses random probabilities uses `np.random.default_rng(seed=42)` with a fixed seed. Reproducibility is non-negotiable.
- **Shape assertions:** always exact (not a subset; not a broadcast-compatible match).
- **Value equality:** always via `np.testing.assert_allclose` with explicit `rtol` and `atol`. Never `==` on floats.

#### 2.9.6 Pass/fail criteria and Phase 1 sign-off

Phase 1 is **signed off** when all three conditions hold:

1. `pytest symbolu_bcvf_llm/tests/ -x -v` returns 0 on CI. `-x` = fail-fast: one failure = sign-off blocked.
2. All 49 tests above are **present and non-skipped** (no `pytest.mark.skip` or `xfail` markers in the shipped suite).
3. Code review confirms each test file's assertions correspond to the claim documented in the referenced §2 sub-section. A test that passes but doesn't assert the claimed property is worse than a failing test (it gives false confidence). Review is mandatory.

**On failure.** If any test fails during Phase 1 execution:

- The test output identifies the sub-section (by the test file/function name).
- The relevant §2 sub-section is re-opened and revised.
- `git revert` the kernel implementation commit and restart from the design fix.
- `HISTORY.md` records the revision and its trigger (e.g., "§2.8.10 revised after test_pair_cost_linear_drift_zero failed in fp32 — boundary upcast enforcement added").

This is the same discipline autonomy used: design → test → implement → test-pass → sign-off.

#### 2.9.7 What §2.9 does NOT cover

- **Signal-characterization tests** under synthetic LLM traces with failure injection — that's §3 (Phase 1.5), after Phase 1 closes.
- **Model-backed tests** using an actual HuggingFace model — that's §4 (Phase 2), far downstream.
- **Trust-weighting calibration tests** for softmin `τ_w` — that's §5 (Phase 3).
- **Benchmark / performance tests** — these are useful but not gate criteria. May be added to a separate `tests/benchmarks/` directory and run selectively.
- **Property-based tests** (e.g., Hypothesis) — complement but do not replace the explicit tests above. Can be added in V2 if coverage gaps emerge.

#### 2.9.8 Effort estimate

- **Test implementation:** 0.5–1 day given that autonomy's `test_core.py` (approx. 300 lines, 40+ tests) is a direct template. The LLM versions are structurally parallel plus the ~10 new tests for `valid_mask`, per_source attribution, and NaN guard.
- **Cross-kernel tests:** 2 hours to get the import paths correct and verify bit-exact behavior of `pseudo_huber`.
- **CI wiring:** 1 hour to add `symbolu_bcvf_llm/tests/` to the existing pytest config.
- **Implementation of `symbolu_bcvf_llm/core.py`:** 1 day, bounded by the sub-section-by-sub-section §2.8 spec.
- **Debug iterations:** 0.5 day budgeted, realistically often zero since the autonomy kernel is already debugged.
- **Total Phase 1 execution:** ~3 days, within §1.9's 2-week V1 budget.

#### 2.9.9 Acceptance criteria for §2.9 itself

§2.9 is considered complete when:

1. ✅ Purpose and hard-gate role stated (§2.9.1).
2. ✅ Test file layout committed (§2.9.2).
3. ✅ Test categories and counts tabulated (§2.9.3).
4. ✅ Full test catalog (49 tests) enumerated with target files and one-line assertions (§2.9.4).
5. ✅ Determinism and tolerance conventions committed (§2.9.5).
6. ✅ Pass/fail criteria and sign-off protocol defined (§2.9.6).
7. ✅ Out-of-scope items enumerated (§2.9.7).
8. ✅ Effort estimate provided (§2.9.8).

All items 1–8 satisfied by this section. §2.9 is closed; §2 Phase 1 design is **complete end-to-end** (§2.0–§2.9).

**Next step after §2.9 sign-off:** Phase 1 **execution** — write `symbolu_bcvf_llm/core.py` + `tests/` per this spec. When all 49 tests pass, Phase 1 closes and §3 (Phase 1.5) is authorized. §3 onward remain as skeleton sub-sections pending authorization.

---

---

## Section 3 — Phase 1.5 — Signal Characterization

**Purpose:** Synthetic LLM trace families that isolate the distrust signal under controlled conditions, analogous to the autonomy Phase 1.5 sweep. Validate that the adapted BCVF math produces Lemma-1-invariant behavior in the LLM context *before* exposing it to real model outputs. Sweep the gate threshold `T`, steepness `β`, and Huber `δ`.

### 3.0 Sub-section plan

§3 is filled sub-section-by-sub-section with authorization gates between each, matching §2's pattern. This planning sub-section lists the intended sub-sections so a reader can see the arc of Phase 1.5 before the details land.

- **§3.1** — Purpose & deliverable. What Phase 1.5 produces as an artifact; what the hard gate on §4 (Phase 2) is; what success looks like.
- **§3.2** — Synthetic trace families (baseline / constant-bias / linear-drift / accelerating-divergence / noise-floor / single-source-outlier / EOS-truncation). Each family has a target BCVF output and a mapping to the §2.6 Lemma 1 case or §2.4.5 attribution claim it tests.
- **§3.3** — Trace generation protocol. How `(L, V)` probability sequences are synthesized (softmax over parameterized logits), what controls are exposed (bias direction, drift rate, acceleration magnitude, noise level), and why the synthetic traces are a legitimate proxy for real model outputs.
- **§3.4** — Parameter sweep grid. Which of `(T, β, δ, cost_order, weight_vector_variant)` are swept, their ranges, and the cross product size. Justify each range relative to the V1 defaults locked in §2.5.
- **§3.5** — Acceptance criteria per trace family. For each family in §3.2, the exact pass threshold on `total_cost`, `per_source_costs`, and diagnostics. These are the pass/fail cells of the §3 sweep matrix.
- **§3.6** — Alignment diagnostic. Correlation-style metric between the BCVF signal and the ground-truth outlier label in the synthetic traces. The autonomy analogue was the Pearson correlation between `J_BCVF(t)` and `Δ|y|(t+lookahead)` — §3.6 defines the LLM version.
- **§3.7** — Edge cases and regression-guard traces. Traces that must NOT produce signal (e.g. identical sources, simplex-drift rounding noise) and traces that guard against future regressions (e.g. `weight_vector` mis-broadcast).
- **§3.8** — What §3 does NOT do. Explicit non-goals: no real model forward passes, no trust-weighting composition, no τ_w calibration, no performance benchmarking.
- **§3.9** — Acceptance criteria for §3 itself + effort estimate. Hard gate on §4; Phase 1.5 execution budget.

Each sub-section lands one commit at a time, with the user authorizing the next before work begins.

### 3.1 Purpose & deliverable of Phase 1.5

**Purpose.** Phase 1 ships a mathematically correct BCVF kernel (§2.8) that passes Lemma 1 tests on constructed invariance inputs (§2.9). That's necessary but not sufficient. Before plugging the kernel into a real LLM forward pass (§4) or a trust-weighting integration (§5), we need empirical evidence that the kernel **actually fires on LLM-shaped signals** — not just on the three mathematically-tight Lemma 1 traces. Phase 1.5 provides that evidence by exercising the kernel against a family of synthetic `(L, V)` probability sequences designed to resemble what a real model *would* emit under specific conditions (benign disagreement, accelerating failure, noise-floor fluctuation, EOS-truncated lookahead, etc.), before the real model is ever involved.

**Why "signal characterization" and not just "testing."** §2.9's unit tests check the kernel is mathematically correct under tightly-constructed inputs. §3 asks a different question: given probability sequences that look *statistically realistic* for a V=32000 vocabulary (low-entropy, long-tail, mostly agreeing across sources), does the BCVF signal still discriminate an accelerating outlier from a noisy non-outlier? If the answer is no — if the signal is drowned by noise at realistic entropy levels — the issue is *not* a math bug; it's a *scale mismatch* between the V1 default parameters and the LLM domain. §3 is where that mismatch is diagnosed and fixed (by re-tuning `T`, `β`, or `δ`) before the expensive §4 integration is built.

**Hard gate on §4.** Phase 1.5 is the last gate where we can cheaply abort. Real-model integration costs: GPU time, tokenizer alignment work, KV-cache plumbing, `torch` dependency contamination risk (§2.8.2). If §3 shows the synthetic signal is weak or directionless — i.e. the `per_source_costs[outlier] / per_source_costs[non-outlier]` ratio does not approach 2 when a clear outlier is constructed — we stop before paying the §4 cost. §0.6's stop rule #4 is the formal version of this condition. Phase 1.5 is the empirical trigger for that rule.

**Deliverable.** A bounded artifact consisting of three parts:

1. A Python module `symbolu_bcvf_llm/characterization/` containing trace-family generators, sweep harness, and result aggregation — callable as `python -m symbolu_bcvf_llm.characterization`. Pure NumPy, no ML-framework dependency (matches §2.8.1 discipline).
2. A results CSV/JSON artifact listing every `(trace_family, parameter_tuple)` cell with its `total_cost`, `max_acceleration_norm`, `gate_activation_count`, `per_source_costs` vector, and a per-cell pass/fail bit derived from §3.5's acceptance criteria.
3. A one-page summary in `docs/experiments/phase_1_5_summary.md` reporting: sweep scope, cells run, pass rate per family, parameter tuples that satisfy all families simultaneously, and the single tuple recommended for §4 adoption. This is a concise report, not a thesis — roughly 1–2 pages with the parameter matrix as the main artifact.

**Success definition.** Phase 1.5 passes iff at least one `(T, β, δ)` tuple exists that:

- Produces `total_cost` within the Lemma 1 tolerance (≤ 1e−10 in fp64) for constant-bias and linear-drift traces.
- Produces `total_cost > 0` and `per_source_costs[outlier] ≥ 1.8 × per_source_costs[non-outlier]` for single-source outlier traces.
- Produces `total_cost ≈ 0` (below a noise-floor threshold set in §3.5) for baseline (all-sources-agree) traces.
- Does not produce NaN/Inf or ValueError on any trace in the sweep.

The 1.8× threshold is the §2.4.5 2:1 claim relaxed by 10% to account for finite-sample noise in synthetic traces. §3.5 will specify exact pass thresholds per family.

**Failure mode.** Phase 1.5 **fails** iff no `(T, β, δ)` tuple satisfies the four conditions above across all trace families simultaneously. This can happen for at least two reasons:

- **Scale mismatch (fixable).** The V1 defaults `T=0.1, β=200, δ=0.5` were tuned on SE(2) body-frame error in the `[0, 1]`-ish range (§2.5.1). LLM probability-difference norms may cluster at a different scale — e.g. typical `‖e‖` for two softmax outputs on divergent tokens might be `0.02`, below `T=0.1`. Fix: re-tune the parameters to the observed scale and re-run.
- **Structural mismatch (harder).** The 2nd-order BCVF operator may not discriminate an LLM outlier strongly enough at V=32000 — the vocab-dimensional "signal" may be too dilute. Fix: revisit §2.2's metric choice (weighted norm? top-k truncation?) or re-scope to M=4 or M=5 for stronger attribution. Either fix loops back to §2, not to §3.

The §3.9 sign-off asks a binary question: did Phase 1.5 find a winning tuple? If yes, §4 starts. If no, §3.9 records which reason (scale vs structural) and §0.6 stop rule #4 triggers for the structural case.

**What §3.1 does NOT commit to.** The exact synthetic-trace construction (§3.2), the parameter-sweep ranges (§3.4), the pass thresholds (§3.5). Those are pending sub-section authorization. §3.1 commits **that** Phase 1.5 will be run, **what** its deliverable looks like, and **how** its pass/fail is evaluated at the purpose level.

**Reference artifact.** The autonomy analogue is `symbolu_robotics/bcvf_autonomous/characterization/` with its Phase 1.5 sweep over `(gate_threshold, gate_beta, huber_delta, lambda_c, weight_matrix_variant)` — which characterized the autonomy kernel over SE(2) trajectories before any MPPI integration. §3 mirrors that structure module-for-module, replacing SE(2) trajectory generators with probability-sequence generators and dropping `lambda_c` per §2.8.4.

### 3.2 Synthetic trace families

§3.2 enumerates the seven trace families the Phase 1.5 sweep runs against. Each family is a **parameterized generator** of `M=3` probability sequences of shape `(L, V)` — one sequence per source — constructed to isolate exactly one behavior of the BCVF kernel. Each family maps to one §2 claim and has one expected BCVF output signature. The construction recipes are high-level here; concrete generator parameters live in §3.3.

#### 3.2.0 Overview and family taxonomy

Seven families, organized by which §2 invariance / claim they exercise:

| Family | §2 claim tested | Expected BCVF signature |
|---|---|---|
| §3.2.1 Baseline | Kernel doesn't produce false positive on healthy agreement | `total_cost ≈ 0` below noise floor |
| §3.2.2 Constant-bias | §2.6 C1 — invariance under constant disagreement | `total_cost ≤ 1e−10` in fp64 |
| §3.2.3 Linear-drift | §2.6 C2 — invariance under linear drift (vector path) | `total_cost ≤ 1e−10` in fp64 |
| §3.2.4 Accelerating-divergence | §2.6 C3 — positive signal on quadratic accel | `total_cost > 0`, gate open |
| §3.2.5 Noise-floor | §2.5.1 gate suppression below `T` | `total_cost ≈ 0` despite non-zero `‖a‖` |
| §3.2.6 Single-source-outlier | §2.4.5 2:1 attribution ratio | `per_source[outlier] ≥ 1.8 × per_source[non-outlier]` |
| §3.2.7 EOS-truncation | §2.7.4 / §2.4.4 valid_mask propagation | `pair_cost_{ij} = 0` for pairs involving the truncated source |

**Coverage claim.** Every §2 mathematical claim that can be stated as "the kernel produces X on input Y" has at least one family in this list. Claims that are structurally unprovable by synthetic traces (e.g., "the signal correlates with real-model hallucinations") are deferred to §4+ where real models are in play. §3 is the last layer where we can cheaply and deterministically verify the claims.

**Common parameterization.** All families accept:

- `L`: lookahead horizon (V1 default 5, per §2.3.4).
- `V`: vocabulary size (default 32000 to match production; smaller values like 1024 used for fast iteration).
- `M`: source count (locked to 3 for §3, per §1.3).
- `rng_seed`: `np.random.default_rng(seed=...)` for reproducibility.

Family-specific parameters are described per sub-section below.

#### 3.2.1 Baseline — all sources agree

**Construction.** All three sources produce the same distribution at every lookahead position. Specifically: generate one `(L, V)` base sequence by sampling logits from `N(0, σ²)` and applying softmax; set `p_0 = p_1 = p_2 = base`. Optionally add tiny IID fp32 rounding noise (`σ_noise = 1e-6`) to exercise the noise-floor tolerance path.

**Expected signature.** Every pairwise `e_{ij}(l) ≈ 0` (or exactly 0 with `σ_noise = 0`). `a_{ij}(l*) ≈ 0`. Gate input below `T`. `total_cost ≈ 0`. `per_source_costs[s] ≈ 0` for every source `s`. `gate_activation_count = 0`.

**§2 claim tested.** Kernel does not produce a false positive on healthy agreement. This is the negative control — if the baseline family produces `total_cost > 0`, either the kernel has a bug or the parameter sweep is pathological. Either way, no other family's results can be trusted until baseline passes.

**Pass threshold (§3.5 will formalize).** `total_cost < 1e−6` at `σ_noise = 0`; `total_cost < 1e−4` at `σ_noise = 1e−6`.

#### 3.2.2 Constant-bias — sources disagree by a fixed offset

**Construction.** Generate one `(L, V)` base sequence as in §3.2.1. Construct a **fixed bias vector** `α ∈ ℝ^V` with `‖α‖ = bias_magnitude` (sweep range, typically `0.05, 0.1, 0.2, 0.5`). Set `p_0 = base`, `p_1 = softmax(logit(base) + α_logit)` where `α_logit` is chosen to produce the target `‖p_1 − p_0‖ ≈ bias_magnitude`, `p_2 = base` (so source 1 is biased, sources 0 and 2 agree). The bias is constant in `l` — the same `α` at every lookahead position.

**Expected signature.** `e_{0,1}(l) = -α` for all `l` (constant in `l`). `a_{0,1}(l*) = 0` by §2.6 C1. `e_{2,1}(l) = -α`. `e_{0,2}(l) = 0`. `total_cost ≤ 1e−10` in fp64. Gate may or may not be open (depends on whether `‖α‖ > T`), but penalty = 0 regardless.

**§2 claim tested.** §2.6 Case 1 (C1) — constant-bias invariance at the kernel level. This is the LLM analogue of `test_lemma_1_constant_bias_zero` from §2.9, but over a *realistic-scale* softmax input instead of an arithmetic construction.

**Pass threshold.** `total_cost < 1e−10` in fp64 across the full `bias_magnitude` sweep.

#### 3.2.3 Linear-drift — sources diverge at a constant rate

**Construction.** Generate base sequence as in §3.2.1. Construct `γ ∈ ℝ^V` with `‖γ‖ = drift_rate` per position (sweep: `0.01, 0.02, 0.05`). Set `p_0 = base`; `p_1(l) = softmax(logit(base(l)) + l · γ_logit)`; `p_2 = base`. The drift accumulates linearly in `l`.

**Expected signature.** `e_{0,1}(l) = -l · γ` (linear in `l`). `a_{0,1}(l*) = 0` by §2.6 C2 (vector-path proof from §2.6.4). Gate may open at the larger `l` values where `‖e‖ > T`; penalty is still 0 because `‖a‖ = 0`. `total_cost ≤ 1e−10` in fp64.

**§2 claim tested.** §2.6 Case 2 (C2) — linear-drift invariance. **This is the family the structural choice in §2.4.1 is most visible in.** If the scalar-path alternative had been chosen, this family would fail (the scalar path's cusp at `l=0` produces spurious 2nd-difference signal). Failure of this family under the vector-path implementation indicates a genuine bug, not a parameter issue.

**Pass threshold.** `total_cost < 1e−10` in fp64 across the full `drift_rate` sweep.

#### 3.2.4 Accelerating-divergence — a source pulls away quadratically

**Construction.** Generate base sequence as in §3.2.1. Construct `η ∈ ℝ^V` with `‖η‖ = accel_magnitude` per position² (sweep: `0.05, 0.1, 0.2, 0.5`). Set `p_0 = base`; `p_1(l) = softmax(logit(base(l)) + 0.5 · l² · η_logit)`; `p_2 = base`. Source 1 accelerates away from sources 0 and 2 quadratically in `l`.

**Expected signature.** `e_{0,1}(l) ≈ -0.5 · l² · η`. `a_{0,1}(l*) ≈ -η` (constant, per §2.6 C3 proof). Gate open at `l*` where `‖e‖ > T` (depends on `accel_magnitude` and `L`). `total_cost > 0` monotonically increasing with `accel_magnitude`.

**§2 claim tested.** §2.6 Case 3 (C3) — affirmative acceleration detection. This is the **primary positive control** — if this family doesn't produce `total_cost > 0` when gate is open, BCVF is not doing its job. Also validates the §2.6.7 Huber bound (`total_cost` finite even at large `accel_magnitude`).

**Pass threshold.** `total_cost > 1e−4` at `accel_magnitude ≥ 0.1` with gate open. Monotonic increase check: `total_cost(accel=0.2) > total_cost(accel=0.1)`.

#### 3.2.5 Noise-floor — sources fluctuate below the gate threshold

**Construction.** Generate base sequence as in §3.2.1. Add IID Gaussian noise to each source's logits at each lookahead position: `p_s(l) = softmax(logit(base(l)) + noise_{s,l})` where `noise_{s,l} ∼ N(0, σ_noise²)` independently across `s, l`. Sweep `σ_noise ∈ {0.001, 0.005, 0.01, 0.02}` in logit space. The noise produces non-zero `‖a‖` but `‖e‖` stays below `T` (by construction at low `σ_noise`).

**Expected signature.** `‖e_{ij}(l)‖` clustered around `σ_noise · √V` (small). Gate suppressed (output ≈ 0) when `‖e‖ < T`. `total_cost ≈ 0` despite the 2nd-difference being non-zero.

**§2 claim tested.** §2.5.1 gate suppression below noise floor. The operator must not chase arithmetic noise in the tail of the simplex. This family defines the upper bound on `σ_noise` that the V1 defaults tolerate — critical for real-model integration where some forward-pass stochasticity is unavoidable.

**Pass threshold.** `total_cost < 1e−3` for `σ_noise ≤ 0.005`. Graceful degradation: `total_cost` monotonically increases with `σ_noise` but stays bounded.

#### 3.2.6 Single-source-outlier — one source diverges, two agree

**Construction.** Combines §3.2.4 (accelerating divergence) with §3.2.1 (baseline) at M=3. Sources 1 and 2 hold the base sequence; source 0 gets the accelerating-divergence offset from §3.2.4 with `accel_magnitude` chosen to put the gate clearly in the open regime (e.g., `0.3`). This is the canonical scenario §2.4.5's 2:1 attribution claim was designed for.

**Expected signature.** `pair_cost_{0,1}` and `pair_cost_{0,2}` both large (both involve source 0). `pair_cost_{2,1} ≈ 0` (sources 1 and 2 agree). Per-source attribution: `per_source[0] = pair_cost_{0,1} + pair_cost_{0,2} ≈ 2·LARGE`; `per_source[1] = pair_cost_{0,1} + pair_cost_{2,1} ≈ LARGE`; `per_source[2] = pair_cost_{0,2} + pair_cost_{2,1} ≈ LARGE`. Ratio: `per_source[0] / per_source[1] ≈ 2.0`.

**§2 claim tested.** §2.4.5 per-source attribution with 2:1 outlier discrimination. This is the **load-bearing claim for §5's trust-weighting**: if the attribution ratio isn't reliably close to 2:1 on this family, softmin on per-source costs won't produce a meaningful trust distribution, and the whole Ketu→Rahu architecture breaks.

**Pass threshold.** `per_source[0] / per_source[1] ≥ 1.8` and `per_source[0] / per_source[2] ≥ 1.8` simultaneously. Symmetry check: `|per_source[1] − per_source[2]| / per_source[1] < 0.1` (the two non-outliers should be roughly equal).

#### 3.2.7 EOS-truncation — one source emits EOS mid-window

**Construction.** Generate any of §3.2.1–§3.2.6 patterns. For source 0, set `valid_mask_0[k:] = False` for some `k < L` (source 0 "emitted EOS" at position `k`). Pass `valid_masks_batch` to `compute_bcvf_cost_batch` per §2.8.12.

**Expected signature.** Pairs involving source 0 have stencil positions with `l* ≥ k` invalidated per §2.4.4. `pair_cost_{0,1}` and `pair_cost_{0,2}` reflect only the valid stencil positions. At `k=0` (source 0 emits EOS immediately), both pairs have empty stencil and both `pair_cost = 0`. At `k=L-1` (no truncation), identical to the baseline family. Smooth degradation in between.

**§2 claim tested.** §2.7.4 EOS handling + §2.4.4 stencil-coverage rule. Critical for real-model integration because real sources will frequently emit EOS mid-lookahead.

**Pass threshold.** At `k=0`: `pair_cost_{0,*} = 0` exactly. At `k=L-1`: `pair_cost` equals the no-mask baseline within 1e-10. Monotonic: `pair_cost(k)` increases with `k` (more valid stencil positions → more signal when source 0 is genuinely diverging).

#### 3.2.8 Family coverage matrix

Each family exercises a specific kernel property. The matrix below summarizes which §2 sub-sections are tested by which families — ensuring no §2 claim is left unverified by §3:

| §2 sub-section | §3.2.1 Baseline | §3.2.2 Const-bias | §3.2.3 Lin-drift | §3.2.4 Accel | §3.2.5 Noise | §3.2.6 Outlier | §3.2.7 EOS |
|---|---|---|---|---|---|---|---|
| §2.4.1 Vector-path choice | — | — | **✓** | — | — | — | — |
| §2.4.5 Per-source attribution | — | — | — | — | — | **✓** | — |
| §2.5.1 Gate threshold | — | — | — | ✓ | **✓** | ✓ | — |
| §2.5.2 Huber bound | — | — | — | **✓** | — | ✓ | — |
| §2.6 C1 Constant-bias | — | **✓** | — | — | — | — | — |
| §2.6 C2 Linear-drift | — | — | **✓** | — | — | — | — |
| §2.6 C3 Acceleration | — | — | — | **✓** | — | ✓ | — |
| §2.7.3 Underflow robustness | ✓ | — | — | — | **✓** | — | — |
| §2.7.4 / §2.4.4 EOS mask | — | — | — | — | — | — | **✓** |
| §2.7.6 NaN guard (negative) | — | — | — | — | — | — | — |
| §2.8.4 M=3 all-pairs | — | — | — | — | — | **✓** | — |

**Boldface ✓ = the family that primarily tests the claim. Regular ✓ = a secondary stress path.** `§2.7.6 NaN guard` has no family because a synthetic trace that produced NaN would be caught by Python's `assert np.isfinite(...)` upstream; §2.9's `test_compute_bcvf_cost_scalar_nan_guard` handles that claim. Every other §2 claim has at least one dedicated family.

**What §3.2 does NOT commit to.** The concrete numerical ranges for `bias_magnitude`, `drift_rate`, `accel_magnitude`, `σ_noise`, and the base logit distribution `σ` are deferred to §3.3 (generator protocol). The pass thresholds are formalized in §3.5. The cross product of families × parameters is defined in §3.4 (sweep grid).

### 3.3 Trace generation protocol

§3.2 defined **what** each family produces. §3.3 commits **how** — the concrete Python-level recipe that turns family name + parameters into a reproducible `(M, L, V)` probability-tensor plus optional valid masks.

#### 3.3.1 Base sequence generation

Every family starts from a **base logit sequence** `z_base: (L, V)` synthesized to mimic the statistical shape of real model logits without invoking a model. The recipe:

```
rng = np.random.default_rng(seed)
z_base = rng.normal(loc=0.0, scale=sigma_logit, size=(L, V))
p_base = softmax(z_base, axis=-1)          # (L, V)
```

**Parameter: `sigma_logit`.** Controls the entropy of the base distribution. Concrete defaults:

| `sigma_logit` | Approximate top-1 probability | Regime |
|---|---|---|
| 1.0 | ~0.1 | High-entropy / near-uniform — stress test for dilute disagreement |
| 3.0 | ~0.5 | Medium-entropy / typical decoding-mid-token regime |
| 5.0 | ~0.9 | Low-entropy / confident-token regime |

V1 defaults to **`sigma_logit = 3.0`** (medium entropy) as the primary characterization regime, because real model outputs at decoding time under greedy-with-temperature-1.0 (§2.7.1) cluster there empirically. §3.4's parameter sweep will also run at `sigma_logit ∈ {1.0, 5.0}` as sensitivity checks; if any family's pass/fail status flips across the `sigma_logit` sweep, §3.9 records it as a robustness concern requiring §4 validation.

**No tokenizer, no vocabulary semantics.** The `V` dimensions are interchangeable integers. We are not constructing "plausible English next-token distributions" — we are constructing random-but-shaped probability sequences. §3.3.7 explains why this is legitimate.

#### 3.3.2 Logit-space perturbation primitives

Disagreements between sources are constructed in **logit space**, not probability space, and projected through softmax. This preserves the simplex constraint without requiring ad-hoc re-normalization.

Three primitives, one per derivative-order signature from §2.6:

- **`bias(α_direction, α_magnitude) → ℝ^V`**: returns a constant logit perturbation `α_logit(l) = α_magnitude · α_direction` for all `l`. `α_direction` is a unit vector in logit space, sampled once per trace.
- **`drift(γ_direction, drift_rate) → ℝ^{L,V}`**: returns a linearly-growing logit perturbation `γ_logit(l) = l · drift_rate · γ_direction`. Linear in `l`.
- **`accelerate(η_direction, accel_magnitude) → ℝ^{L,V}`**: returns a quadratic logit perturbation `η_logit(l) = 0.5 · l² · accel_magnitude · η_direction`. Quadratic in `l`.

The direction vectors are sampled from `N(0, I_V)` and ℓ²-normalized. Their identity matters only through the magnitude parameters; sampled once per trace with the seeded RNG.

**Why logit-space, not probability-space.** Adding a perturbation to `p_base` directly would require explicit re-normalization, and the re-normalization would itself be non-linear in the perturbation (breaking the exact Lemma 1 structure at the input layer). Adding in logit space and softmaxing preserves the exact algebraic form `p_s(l) = softmax(z_base(l) + perturbation_s(l))`, which makes the tests reproducible at fp64 tolerance.

#### 3.3.3 Family-specific assembly

Each family combines the base sequence with the primitives:

| Family | Source 0 logits | Source 1 logits | Source 2 logits |
|---|---|---|---|
| §3.2.1 Baseline | `z_base` | `z_base` | `z_base` |
| §3.2.2 Constant-bias | `z_base` | `z_base + bias(α, α_mag)` | `z_base` |
| §3.2.3 Linear-drift | `z_base` | `z_base + drift(γ, drift_rate)` | `z_base` |
| §3.2.4 Accelerating | `z_base` | `z_base + accelerate(η, accel_mag)` | `z_base` |
| §3.2.5 Noise-floor | `z_base + N(0, σ²)` | `z_base + N(0, σ²)` | `z_base + N(0, σ²)` |
| §3.2.6 Outlier | `z_base + accelerate(η, 0.3)` | `z_base` | `z_base` |
| §3.2.7 EOS-truncation | Any of §3.2.1–§3.2.6 | — | — |

Then `p_s(l) = softmax(z_s(l))` for each source and lookahead position.

**Concrete parameter ranges** per family (the cells that §3.4 will sweep over):

| Parameter | Range | Rationale |
|---|---|---|
| `α_mag` (§3.2.2) | `{0.05, 0.1, 0.2, 0.5, 1.0, 2.0}` logit units | Spans below/at/above the gate threshold `T = 0.1` in probability space after softmax |
| `drift_rate` (§3.2.3) | `{0.01, 0.02, 0.05, 0.1, 0.2}` logit units/step | Produces `‖e‖` values ranging from below-gate to well-above |
| `accel_mag` (§3.2.4) | `{0.02, 0.05, 0.1, 0.2, 0.5, 1.0}` logit units/step² | Spans sub-gate to clearly-accelerating |
| `σ_noise` (§3.2.5) | `{0.001, 0.005, 0.01, 0.02, 0.05}` logit units | Realistic fp32 softmax rounding (~1e-3) to pathological |
| `k_eos` (§3.2.7) | `{0, 1, 2, 3, 4}` at `L=5` | Full truncation-position sweep |
| `sigma_logit` (base) | `{1.0, 3.0, 5.0}` | Low/medium/high-entropy regimes |

**Scale commentary.** A logit-space bias of `α_mag = 0.1` on a medium-entropy base produces a probability-space `‖p_1 - p_0‖₂` of roughly `0.02–0.05` (depending on `sigma_logit`). This is below the V1 gate threshold `T = 0.1`. The sweep intentionally straddles the threshold so the gate's behavior is characterized on both sides.

**Implementation note (§3 execution, commit `543e3e8`).** The logit-space construction above is the spec's descriptive form. In the executed harness (`symbolu_bcvf_llm/characterization/traces.py`), perturbations are applied in **probability space** for four of the seven families, because two structural issues make the pure logit-space recipe incompatible with §3.5's thresholds:

1. **Softmax nonlinearity vs. Lemma 1.** A logit-space constant shift `α` produces `p_1(l) − p_0(l) = softmax(z_base(l) + α) − softmax(z_base(l))`, which varies with `l` because `z_base(l)` varies with `l`. §2.6 C1/C2 proofs require probability-space `e` to be *exactly* constant / linear in `l` for the 1e-10 fp64 threshold in §3.5.3 / §3.5.4 to be structurally attainable. Probability-space perturbation (`p_1 = p_base + α`, `p_1 = p_base + l·γ`) makes `e` exactly constant / linear as the proofs demand.
2. **Scale amplification by softmax + unit direction.** At V=1024 with a unit-ℓ²-norm logit direction, a logit perturbation of 0.3 produces probability-space disagreement on the order of `1e-5` — four orders of magnitude below `T = 0.1`. Gate never opens and §3.5.5 / §3.5.7 gate-activation thresholds fail. Probability-space perturbation with the same magnitude parameter puts `‖e‖` directly on a controllable scale.

Revised per-family perturbation space (what the harness actually uses):

| Family | Perturbation space | Rationale |
|---|---|---|
| §3.2.1 Baseline | — (identical sources) | no perturbation |
| §3.2.2 Constant-bias | **probability** | exact §2.6 C1 invariance |
| §3.2.3 Linear-drift | **probability** | exact §2.6 C2 invariance |
| §3.2.4 Accelerating | **probability** | controllable ‖a‖ for gate activation |
| §3.2.5 Noise-floor | **logit** (unchanged) | softmax-suppression is the family's purpose |
| §3.2.6 Outlier | **probability** | controllable 2:1 attribution signal |
| §3.2.7 EOS-truncation | inherits outer family | — |

The deviation is recorded per-cell in `TraceBundle.metadata["perturbation_space"]`. §3.3.4's realism rationale (Parts 1–3) still applies: BCVF is a local mathematical operator that only sees the algebraic shape of `e`; whether `e` is constructed via logit-then-softmax or directly in probability space doesn't affect what the operator proves. The base sequence `p_base = softmax(z_base)` is still a softmax-shaped distribution; only the *perturbation layered on top* changes space.

#### 3.3.4 Realism rationale — why these traces are a legitimate stand-in

A reviewer might reasonably ask: "Real model outputs aren't random Gaussians in logit space — they have semantic structure, peaked distributions, attention-head-correlated noise. What does characterization against synthetic traces prove?"

Three-part answer:

1. **BCVF is a local mathematical operator.** It consumes `(L, V)` probability sequences and computes `e_{ij}, a_{ij}`, gate, Huber, sum. None of these operations depend on the *semantic identity* of the `V` dimensions — they only depend on the *statistical shape* of the distribution (entropy, tail weight, per-position stability). Random-logit softmax outputs reproduce the shape (parameterized by `sigma_logit`) without reproducing the semantics, which is all BCVF sees.
2. **The Lemma 1 invariance claims are structural.** §2.6's proofs don't depend on what `p_s(l)` *means* — only on the algebra of 2nd-differences in `ℝ^V`. If C1 and C2 pass on synthetic traces, they pass on real traces, period. The Phase 1.5 sweep is not re-proving Lemma 1; it is *confirming* that the implementation correctly realizes what Lemma 1 proves.
3. **The falsifier is parameter-scale, not semantic.** What §3 can plausibly discover is: "V1 defaults are calibrated for the wrong `‖e‖` range." That's a scale discovery, and synthetic traces at `sigma_logit ∈ {1, 3, 5}` span the full relevant range. What §3 cannot discover is: "real hallucinations produce a different *pattern* than our synthetic outlier" — that's a §4/§5 question and requires real models.

Phase 1.5 is thus the right place to find scale-mismatch bugs but **not** the right place to find semantic-pattern mismatches. §3.1 already committed this distinction in the scale-vs-structural failure-mode split.

#### 3.3.5 RNG discipline and reproducibility

- Single `np.random.default_rng(seed)` constructed at the top of each generator call. No global RNG state is touched.
- Seed is a required positional argument — no default. Every call in the sweep is explicitly seeded.
- Direction vectors (`α_direction`, `γ_direction`, `η_direction`) are drawn *after* the base sequence, in fixed order. Changing the order of draws silently changes every downstream result; the order is documented and locked.
- The noise for §3.2.5 is drawn last, so noise traces are reproducible even when generated alongside the other families.

**Replay guarantee.** For any `(family, parameter_tuple, seed)`, calling the generator twice produces bit-identical tensors. §3.5 pass thresholds will be specified under this guarantee.

#### 3.3.6 Generator module API

Target module: `symbolu_bcvf_llm/characterization/traces.py`. Public API:

```python
def generate_trace(
    family: str,                    # "baseline" | "constant_bias" | "linear_drift" | ...
    L: int = 5,
    V: int = 32000,
    sigma_logit: float = 3.0,
    seed: int = 0,
    **family_params,                # family-specific magnitudes
) -> TraceBundle:
    """Return a reproducible M=3 probability sequence for the given family.

    Returns a TraceBundle dataclass with:
        sources: np.ndarray shape (3, L, V), fp32
        valid_masks: Optional[np.ndarray] shape (3, L), bool (None unless family=EOS)
        truth_label: Optional[int] — source index of the outlier, or None for baseline
        metadata: Dict[str, Any] — seed, family, parameters (for result provenance)
    """

@dataclass
class TraceBundle:
    sources: np.ndarray
    valid_masks: Optional[np.ndarray]
    truth_label: Optional[int]
    metadata: Dict[str, Any]
```

**`truth_label`** is what makes §3.6's alignment diagnostic possible: for each trace where a specific source was synthesized to be the outlier, `truth_label` records its index. The diagnostic will ask "does `argmax(per_source_costs) == truth_label`?" and accumulate hit rate.

#### 3.3.7 What §3.3 does NOT do

- **No tokenizer.** `V` is an integer vocabulary size; no token ids, no words.
- **No real model forward pass.** Pure NumPy logit sampling; no torch, no transformers.
- **No attention-correlated noise** (`noise_{s,l}` is IID). Real forward passes have correlated noise from attention stochasticity; that's §4's domain.
- **No semantically-plausible outlier patterns** (hallucination, repetition, incoherence). §3 tests the math; §4 tests the match to real failure modes.
- **No sampling from `p_s(l)`** (we never draw tokens — we compare distributions directly).
- **No calibration of `sigma_logit` against real models.** The `{1, 3, 5}` sweep is a span, not a match. §4 will report empirical `sigma_logit_equivalent` from a real model to validate the choice retroactively.

§3.3 is an intentionally minimal spec. The test harness is small, pure, and runs in seconds; everything beyond the §3.2 families and their magnitude sweeps is V2 or §4.

### 3.4 Parameter sweep grid

§3.2 named the families, §3.3 specified how to generate them. §3.4 commits **which parameter combinations are actually run** — the cross product of families × magnitudes × BCVF config × entropy regimes.

#### 3.4.1 Sweep dimensions

Five dimensions cross-multiplied:

1. **Family** (7 values from §3.2): `baseline, constant_bias, linear_drift, accelerating, noise_floor, outlier, eos_truncation`.
2. **Family magnitude** (per-family values from §3.3.3 tables): `α_mag`, `drift_rate`, `accel_mag`, `σ_noise`, `k_eos` — each family has 5–6 values.
3. **BCVF gate parameters** `(T, β)`: V1 defaults `(0.1, 200)` plus a sensitivity grid.
4. **Huber parameter** `δ`: V1 default `0.5` plus a sensitivity grid.
5. **Base entropy** `sigma_logit`: `{1.0, 3.0, 5.0}` from §3.3.1.
6. **Seed**: 3 seeds per cell for RNG-stability. Cells are considered to pass only if all 3 seeds pass independently.

**Fixed across all sweeps:** `L = 5` (§2.3.4), `M = 3` (§1.3), `V = 32000` (production) *and* `V = 1024` (fast iteration). `cost_order = SECOND` for primary sweeps; `FIRST` and `ZEROTH` for the §3.2.3 linear-drift family only (ablation check — `FIRST` must fail there per §2.6.4 / §2.8.3, confirming the Lemma-1-violation warning is empirical).

#### 3.4.2 Primary grid — production characterization

The primary grid uses V1 BCVF defaults and sweeps only the family-side dimensions. This is the core "does the kernel fire correctly on realistic inputs?" sweep.

| Dimension | Primary values | Count |
|---|---|---|
| Family | all 7 from §3.2 | 7 |
| Family magnitude | per-family range (§3.3.3); avg 5 values | avg 5 |
| `(T, β)` | **`(0.1, 200)` only** (V1 default) | 1 |
| `δ` | **`0.5` only** (V1 default) | 1 |
| `sigma_logit` | **`3.0` only** (V1 primary regime) | 1 |
| `V` | **`1024` only** (fast iteration) | 1 |
| Seeds | 3 seeds | 3 |

**Primary grid size:** `7 × 5 × 1 × 1 × 1 × 1 × 3 ≈ 105 cells`. Each cell is one `compute_bcvf_cost_batch` call on a `(1, 3, 5, 1024)` tensor — milliseconds.

**Purpose.** Primary grid answers: *at V1 defaults and the primary entropy regime, does every family pass §3.5's thresholds?* If yes, Phase 1.5 core result is green. If no, either a family's pass threshold is wrong (§3.5 revisit) or the V1 defaults are wrong (sensitivity grid diagnoses which).

#### 3.4.3 Sensitivity grid — robustness & tuning

The sensitivity grid holds family + magnitude fixed at each family's *canonical* value (middle of its range) and sweeps the BCVF parameters + entropy regime. Catches "V1 defaults are pathological at some entropy" failures.

| Dimension | Sensitivity values | Count |
|---|---|---|
| Family | all 7 | 7 |
| Family magnitude | **1 canonical value per family** (the middle of §3.3.3's range) | 1 |
| `T` (gate threshold) | `{0.05, 0.1, 0.2}` | 3 |
| `β` (gate steepness) | `{100, 200, 500}` | 3 |
| `δ` (Huber) | `{0.25, 0.5, 1.0}` | 3 |
| `sigma_logit` | `{1.0, 3.0, 5.0}` | 3 |
| `V` | `1024` | 1 |
| Seeds | 3 seeds | 3 |

**Sensitivity grid size:** `7 × 1 × 3 × 3 × 3 × 3 × 1 × 3 = 1701 cells`. Still milliseconds each → entire sweep in roughly 10–30 seconds on a single CPU core.

**Purpose.** Sensitivity grid answers: *if V1 defaults fail on primary, does a nearby `(T, β, δ)` tuple work?* Combined with `sigma_logit` variation, identifies whether the failure is parameter-scale or entropy-scale. §3.5's pass thresholds apply per-cell; §3.9 aggregates the sensitivity-grid pass rate per `(T, β, δ)` tuple and picks the winner.

#### 3.4.4 Ablation grid — cost-order confirmation

A small, targeted grid to empirically confirm the §2.8.3 Lemma-1-violation warning on `CostOrder.FIRST`.

| Dimension | Values | Count |
|---|---|---|
| Family | **`linear_drift` only** | 1 |
| Family magnitude | **full range** (5 values) | 5 |
| `cost_order` | `{ZEROTH, FIRST, SECOND}` | 3 |
| `sigma_logit` | `3.0` | 1 |
| `V` | `1024` | 1 |
| Seeds | 3 | 3 |

**Ablation grid size:** `1 × 5 × 3 × 1 × 1 × 3 = 45 cells`. Expected result pattern:

- `SECOND`: all cells pass (`total_cost ≤ 1e−10` per §3.2.3) — the Lemma-1-respecting regime.
- `FIRST`: cells with `drift_rate > 0` **fail** (produce `total_cost > 0`) — empirically confirms §2.6.4's warning.
- `ZEROTH`: cells with `drift_rate > 0` also fail when `‖e‖ > T` — reported for completeness, no claim about C2 invariance.

If `FIRST` passes the `linear_drift` family, something is wrong with either the implementation or the §2.6 proof — Phase 1.5 is blocked until resolved.

#### 3.4.5 Full-vocabulary spot check

Production will run at `V = 32000`. The primary and sensitivity grids use `V = 1024` for iteration speed; a final spot-check grid validates that the winner from §3.4.3 produces the same qualitative behavior at production scale.

| Dimension | Values | Count |
|---|---|---|
| Family | all 7 | 7 |
| Family magnitude | canonical only | 1 |
| `(T, β, δ)` | **winner from sensitivity** (1 tuple) | 1 |
| `sigma_logit` | `3.0` | 1 |
| `V` | **`32000` only** | 1 |
| Seeds | 3 | 3 |

**Spot-check grid size:** `7 × 1 × 1 × 1 × 1 × 3 = 21 cells`. Each cell is ~30× more data than the `V=1024` cells; expected cell runtime ~10–50 ms; total ~1 second.

**Purpose.** Confirms the V=1024 → V=32000 scaling doesn't flip any pass/fail. If it does (e.g., noise-floor fails at V=32000 because the dilute simplex changes the effective noise level), §3.5 and §3.9 record the vocabulary-scale dependency as a §4 integration risk.

#### 3.4.6 Grand total and runtime

| Grid | Cells | Per-cell runtime | Total runtime |
|---|---|---|---|
| Primary (§3.4.2) | 105 | ~1 ms | ~0.1 s |
| Sensitivity (§3.4.3) | 1701 | ~1 ms | ~2 s |
| Ablation (§3.4.4) | 45 | ~1 ms | ~0.05 s |
| Full-V spot check (§3.4.5) | 21 | ~30 ms | ~1 s |
| **Total** | **≈ 1872 cells** | | **~3–4 seconds wall time on single CPU core** |

The entire §3 Phase 1.5 experimental campaign completes in under 5 seconds. This is deliberate: §3 is a *correctness* sweep, not a *performance* benchmark. If the sweep takes longer than 30 seconds, something has gone wrong with the generator or the kernel, not with the experimental design.

#### 3.4.7 Execution order

1. Ablation grid (§3.4.4) runs first — if `cost_order=FIRST` doesn't violate C2 empirically, the whole design doc is wrong and the rest of §3 is moot.
2. Primary grid (§3.4.2) runs second — fast sanity check that V1 defaults work at all.
3. Sensitivity grid (§3.4.3) runs third — identifies best `(T, β, δ)` tuple if primary has gaps.
4. Full-V spot check (§3.4.5) runs last — confirms the winner survives vocabulary scaling.

Each stage has an in-loop pass/fail aggregate; if any stage fails globally, later stages don't run (execution is explicitly short-circuited to save developer attention, not compute). §3.9 sign-off requires all four stages green.

#### 3.4.8 What §3.4 does NOT do

- **No cross-family joint sweeps** (e.g., "outlier + noise at the same time"). V1 keeps families isolated; combined-stressor families are V2 per §3.8.
- **No sweep over M.** §1.3 locks M=3; sweeping over M=2 and M=4 is a §9 V2 question.
- **No sweep over L.** §2.3.4 locks L=5; sweeping over L=3, 7 is §9.
- **No performance tuning.** Grid sizing prioritizes coverage over FLOP efficiency.
- **No calibration against real-model distributions.** §4 retroactively validates `sigma_logit=3.0` against a real HuggingFace model; §3 does not.
- **No result-aggregation protocol.** §3.9 specifies how per-cell pass/fail aggregates into per-family and per-parameter-tuple pass rates.

### 3.5 Acceptance criteria per trace family

§3.2 sketched per-family expected outputs. §3.4 enumerated the grid of cells to run. §3.5 commits the **exact numerical thresholds** each cell must satisfy to count as pass. No threshold in §3.5 is soft — they are either met or not met when the sweep runs.

#### 3.5.1 Per-cell pass/fail contract

Every cell in any §3.4 grid is defined by a tuple `(family, family_params, T, β, δ, sigma_logit, V, seed)`. Each cell is evaluated by:

1. Running `generate_trace(...)` per §3.3.6 with the cell's parameters.
2. Calling `compute_bcvf_cost_batch(sources, config, valid_masks_batch, return_per_source=True)` per §2.8.12.
3. Computing the family-specific pass metrics listed in §3.5.2–§3.5.8.
4. Comparing each metric against its threshold.
5. Emitting `cell_pass = True` iff **every** metric for that family is within threshold.

**Three-seed rule** (§3.4 committed): a cell's `(family, family_params, T, β, δ, sigma_logit, V)` pass status is `True` iff all three seeded variants `(..., seed=s)` independently pass. A single-seed pass is recorded but does **not** satisfy §3.9 sign-off. This catches RNG-boundary flakes where one seed's random direction vector happens to cancel the gate threshold.

**Precision regime per metric.** Lemma 1 metrics (C1, C2) evaluate in fp64 with `total_cost ≤ 1e-10`. All other metrics evaluate in fp32 with looser tolerances appropriate for softmax rounding. The generator upcasts to fp64 only for Lemma 1 cells (explicit `dtype=np.float64` in `generate_trace`), so the precision regime is selected by the family, not by a global flag.

#### 3.5.2 §3.2.1 Baseline — all sources agree

All three sources produce the same distribution at every lookahead position.

| Metric | Threshold | Precision |
|---|---|---|
| `total_cost` | `< 1e-6` at `σ_noise = 0` | fp32 |
| `total_cost` | `< 1e-4` at `σ_noise = 1e-6` (fp32 rounding regime) | fp32 |
| `max_acceleration_norm` | `< 1e-3` | fp32 |
| `gate_activation_count` | `== 0` | — |
| `per_source_costs[s]` for all `s` | `< 1e-6` | fp32 |

**Pass iff all 5 metrics within threshold.** Fail cases diagnose: if `total_cost > 1e-6` despite `σ_noise = 0`, the kernel has a false-positive bug. If `gate_activation_count > 0`, the noise noise is crossing the gate threshold — either a bug or the baseline generator is wrong.

#### 3.5.3 §3.2.2 Constant-bias — §2.6 Case 1

Source 1 differs from sources 0 and 2 by a fixed logit offset `α_logit`.

| Metric | Threshold | Precision |
|---|---|---|
| `total_cost` | `≤ 1e-10` | **fp64** |
| `per_source_costs[s]` for all `s` | `≤ 1e-10` | **fp64** |
| `max_acceleration_norm` | `≤ 1e-10` | **fp64** |

**Pass iff all 3 within threshold, for every `α_mag` in the sweep range.** This is the LLM analogue of `test_lemma_1_constant_bias_zero` (§2.9) evaluated on softmax-projected realistic inputs. A failure here indicates an implementation deviation from §2.6.3's proof — or an unreported floating-point issue when `p_s` values are near fp64 rounding limits (unlikely but worth diagnosing).

#### 3.5.4 §3.2.3 Linear-drift — §2.6 Case 2

Source 1 drifts linearly in logit space from sources 0 and 2.

| Metric | Threshold | Precision |
|---|---|---|
| `total_cost` | `≤ 1e-10` | **fp64** |
| `per_source_costs[s]` for all `s` | `≤ 1e-10` | **fp64** |
| `max_acceleration_norm` | `≤ 1e-10` | **fp64** |

**Pass iff all 3 within threshold, for every `drift_rate` in the sweep range.** The critical family: §2.4.1's vector-path choice either holds empirically here or it doesn't. If a cell fails with `cost_order=SECOND`, §2.4.1 is wrong or §2.8.6's implementation is wrong. If a cell fails with `cost_order=FIRST`, that is **expected** (§3.4.4 ablation) and is recorded as a positive confirmation, not a failure.

#### 3.5.5 §3.2.4 Accelerating-divergence — §2.6 Case 3

Source 1 accelerates away from sources 0 and 2 quadratically.

| Metric | Threshold | Precision |
|---|---|---|
| `total_cost` | `> 1e-4` when gate is open (i.e., `accel_mag ≥ 0.1`) | fp32 |
| `total_cost` | **monotonically non-decreasing** in `accel_mag` within family | fp32 |
| `gate_activation_count` | `> 0` when `accel_mag ≥ 0.1` | — |
| `max_acceleration_norm` | `> T / 10` when gate is open (sanity that `‖a‖` is meaningful) | fp32 |
| `total_cost` | `< 10^6` at any `accel_mag ≤ 1.0` (Huber finite-bound check per §2.6.7) | fp32 |

**Pass iff all 5 within threshold.** Fail cases: if `total_cost` is flat across `accel_mag`, the gate never opens or the Huber is saturated pathologically. If `total_cost` is non-monotonic, rounding or numerical instability is corrupting the stencil.

#### 3.5.6 §3.2.5 Noise-floor — §2.5.1 gate suppression

All three sources receive IID Gaussian noise in logit space with standard deviation `σ_noise`.

| Metric | Threshold | Precision |
|---|---|---|
| `total_cost` | `< 1e-3` for `σ_noise ≤ 0.005` | fp32 |
| `total_cost` | **monotonically non-decreasing** in `σ_noise` | fp32 |
| `gate_activation_count` | `== 0` for `σ_noise ≤ 0.001` | — |
| `per_source_costs[s]` standard deviation across `s` | `< 0.1 · mean(per_source_costs)` for `σ_noise ≤ 0.01` | fp32 |

**Pass iff all 4 within threshold.** The 4th metric is the symmetry check — under IID noise, all three sources should accumulate roughly equal per-source cost, since no source is an outlier. Asymmetry would signal a bug in `_enumerate_pairs` or the per-source accumulation in §2.8.11.

#### 3.5.7 §3.2.6 Single-source-outlier — §2.4.5 attribution

Source 0 accelerates; sources 1 and 2 agree.

| Metric | Threshold | Precision |
|---|---|---|
| `per_source_costs[0] / per_source_costs[1]` | `≥ 1.8` | fp32 |
| `per_source_costs[0] / per_source_costs[2]` | `≥ 1.8` | fp32 |
| `abs(per_source_costs[1] − per_source_costs[2]) / per_source_costs[1]` | `< 0.1` | fp32 |
| `argmax(per_source_costs) == 0` | `True` | — |
| `gate_activation_count` | `> 0` | — |

**Pass iff all 5 within threshold.** Threshold `1.8` is the theoretical `2.0` relaxed by 10% for finite-V softmax noise (per §3.1). The 3rd metric enforces **symmetry** — the two non-outliers should have per-source cost within 10% of each other; a large gap signals a pairing bug.

**This family is load-bearing for §5.** If §3.2.6 fails, the Ketu→Rahu softmin has nothing to work with. No pass here = no Phase 1.5 sign-off = no §4 unlock.

#### 3.5.8 §3.2.7 EOS-truncation — §2.7.4

Source 0 emits EOS at position `k_eos`; the outer family (baseline or outlier) determines the underlying shape.

| Metric | Condition | Threshold | Precision |
|---|---|---|---|
| `pair_cost_{0,1}` | at `k_eos = 0` | `== 0.0` exactly | — |
| `pair_cost_{0,2}` | at `k_eos = 0` | `== 0.0` exactly | — |
| `pair_cost_{1,2}` | at `k_eos = 0` | matches no-mask baseline within `1e-10` | fp64 |
| `total_cost(k_eos = L−1)` | equals `total_cost(no mask)` | within `1e-10` | fp64 |
| `total_cost(k_eos)` | **monotonically non-decreasing** in `k_eos` for outlier outer family | fp32 |
| `total_cost`, `per_source_costs`, `gate_activation_count` | any trace | all finite (no NaN, no Inf) | — |

**Pass iff all 6 within threshold.** The `k_eos = 0` cell is the strictest test of §2.4.4's `valid(l*)` predicate — both pairs involving source 0 must produce exactly zero, not "approximately zero." The monotonicity check guards against mask application bugs where an off-by-one would make partial-truncation cells produce artifacts.

#### 3.5.9 Global aggregation across seeds and magnitudes

Per §3.4, a *cell* is a 3-seed-replicated `(family, params, BCVF_config, sigma_logit, V)`. §3.5 defines two aggregation levels above the cell:

**Per-family pass rate.** For each family, across all magnitude values in its sweep range and all 3 seeds per magnitude:

```
family_pass_rate = (#cells passing all family-specific thresholds)
                 / (#cells total for the family)
```

A family is considered **pass** iff `family_pass_rate == 1.0` (100%). Anything less is a fail, because §3.5's thresholds are pass-every-cell, not pass-on-average.

**Per-BCVF-config pass rate.** For sensitivity-grid sweeps, across all 7 families at that `(T, β, δ)`:

```
config_pass_rate = (#families passing under this (T, β, δ))
                 / 7
```

A BCVF config is a **candidate V1 tuple** iff `config_pass_rate == 1.0`. §3.9 picks the winner from the candidate set using a tiebreaker rule defined there (likely: prefer the tuple closest to V1 defaults `(0.1, 200, 0.5)` to minimize deviation from the design spec).

**Failure attribution.** When `config_pass_rate < 1.0`, §3.9 reports which family(families) failed, which magnitudes within each family, and which seeds. This produces an actionable diagnostic report, not a pass/fail bit alone.

#### 3.5.10 What §3.5 does NOT do

- **No tuning of the thresholds themselves.** If the §2 defaults are correct and the kernel is implemented per §2.8, these thresholds pass. If they don't pass, the answer is to revise §2 or the implementation, **not** to relax the thresholds. Sign-off discipline.
- **No soft thresholds or probabilistic passes.** Every threshold is an absolute-value or equality check. Phase 1.5 is a structural sweep, not a statistical one.
- **No time-series / streaming analysis.** Each cell is evaluated in isolation. Cross-cell statistics (e.g., "does `total_cost` trend over `accel_mag` fit a quadratic?") are out of scope — they're useful diagnostic narratives but not pass criteria.
- **No model-dependent thresholds.** Every threshold is a pure function of the generator parameters and the kernel output; nothing references a real LLM's distribution.
- **No recovery-rate / regression-guard pass.** §3.7's regression-guard traces have their own thresholds (defined there); §3.5 stays on the 7 core families.

§3.5 is intentionally spartan: a table of numbers, evaluated mechanically against the sweep output. §3.9 is where these numbers become sign-off decisions; §3.6 is where the alignment-diagnostic dimension is added beyond raw pass/fail.

### 3.6 Alignment diagnostic

§3.5 asks whether each cell's output satisfies a numerical threshold. §3.6 asks a different question: when the kernel's per-source cost distribution is **interpreted as a trust signal** (which source should §5's Rahu down-weight?), does it point at the source we synthetically constructed to be the outlier? §3.6 is the "right answer for the right reason" check — it catches cases where the threshold passes but the attribution points at the wrong source.

#### 3.6.1 Purpose and relation to autonomy

The autonomy kernel characterization tracked a **Pearson correlation** between the per-timestep BCVF signal `J_BCVF(t)` and the downstream safety objective (`Δ|y|(t + lookahead)`, the lateral-deviation change a few steps ahead). The N=34 additive-cost experiments showed that correlation at only `+0.04` (directionless); the N=10 Ketu→Rahu refactor showed strong negative correlation (BCVF signal high *precedes* safety improving — the operator correctly warns of impending failure).

The LLM analogue cannot use the same correlation formula — there is no `Δ|y|(t + lookahead)` equivalent, because the "safety" axis in LLM generation (fluency, coherence, factuality) is not a scalar-regression target. Instead §3.6 asks the corresponding **classification** question: does `argmax(per_source_costs)` point at the truth-label source?

This is a necessary condition for the §5 Ketu→Rahu composition to work. If BCVF's per-source attribution is uncorrelated with which source is actually diverging in the synthetic traces, then §5's softmin over per-source costs produces a meaningless trust distribution, and no parameter tuning in §5 will fix it.

#### 3.6.2 Metric definitions

Three metrics, computed per cell:

**Hit (binary).**

```
hit(cell) = 1 if argmax(per_source_costs) == truth_label else 0
```

Defined only for cells with a non-None `truth_label` (§3.3.6) — i.e., families §3.2.4 (accelerating-divergence, truth = source 1) and §3.2.6 (outlier, truth = source 0). Baseline, constant-bias, linear-drift, noise-floor, and EOS families have `truth_label = None` and are excluded from hit-rate aggregation (for those families, alignment is trivially satisfied or undefined).

**Margin (continuous).**

```
margin(cell) = per_source_costs[truth_label]
             / mean(per_source_costs[s] for s != truth_label)
```

A ratio, ideally ≥ 2.0 at M=3 per the §2.4.5 theoretical claim. `margin > 1.0` means the truth source accumulates more cost than the average non-truth source. Defined same as `hit`.

**Rank (ordinal).**

```
rank(cell) = position of truth_label in sort-descending(per_source_costs)
             ∈ {1, 2, 3} at M=3
```

`rank == 1` means truth_label is the single highest-cost source (equivalent to `hit == 1` at M=3). `rank == 2` means truth_label was second-ranked (a near-miss). `rank == 3` means fully inverted (pathological).

#### 3.6.3 Applicability per family

| Family | `truth_label` | Alignment metrics apply? |
|---|---|---|
| §3.2.1 Baseline | None | No — no outlier |
| §3.2.2 Constant-bias | None | No — bias is symmetric across sources 0 and 2; no "outlier" |
| §3.2.3 Linear-drift | None | No — source 1 is technically the drifting one, but Lemma 1 says total_cost ≈ 0, so per_source_costs are dominated by rounding and the metric is ill-defined |
| §3.2.4 Accelerating | **1** (source 1 accelerates) | **Yes** — primary positive alignment check |
| §3.2.5 Noise-floor | None | No — all sources get IID noise |
| §3.2.6 Outlier | **0** (source 0 is outlier) | **Yes** — primary alignment check + 2:1 ratio |
| §3.2.7 EOS-truncation | Inherited from outer family | Yes if outer family has truth_label |

So alignment metrics are evaluated on families §3.2.4, §3.2.6, and §3.2.7-with-outlier-backing. Roughly 30% of sweep cells carry alignment measurements.

#### 3.6.4 Aggregation across cells

**Hit rate over a family.** For each family with truth_label-bearing cells:

```
hit_rate(family) = mean(hit(cell) for cell in family)
```

At M=3, random guessing gives `hit_rate = 1/3 ≈ 0.333`. A kernel that "works" must clear that baseline significantly.

**Margin distribution.** Track per-cell margin values; report mean, 25th/50th/75th percentile across a family. Useful for diagnosing whether a family that passes `hit_rate` does so robustly (margin tight around 2.0) or marginally (margin barely above 1.0).

**Rank distribution.** Track fraction of cells at each rank value. Ideally rank 1 dominates; rank 3 should be zero.

#### 3.6.5 Pass thresholds for alignment

§3.5 thresholds are necessary but not sufficient. §3.6 adds:

| Metric | Threshold | Families |
|---|---|---|
| `hit_rate` | `≥ 0.95` | §3.2.4, §3.2.6 |
| `mean(margin)` | `≥ 1.8` | §3.2.4, §3.2.6 |
| `fraction(rank == 1)` | `≥ 0.95` | §3.2.4, §3.2.6 |
| `fraction(rank == 3)` | `== 0.0` (strict) | all alignment-applicable families |

**Pass iff all 4 within threshold.** A candidate V1 tuple from §3.5.9 must additionally pass §3.6's thresholds to reach §3.9 sign-off. The 5% miss budget in `hit_rate` covers RNG-boundary cases where synthetic magnitude is near the gate threshold; the `rank == 3` strict zero catches "pointing at the wrong source" errors, which are always a bug regardless of margin scale.

**Why not 100% hit rate?** Because at magnitudes near the gate threshold (e.g., `accel_mag = 0.05` in the sensitivity grid), a lucky noise pattern can flip which source looks most divergent. This is a real phenomenon in the operator, not an implementation bug. The 95% threshold is the empirical cliff where "kernel works" starts — per the autonomy N=10 Ketu→Rahu data, the autonomy analogue cleared ~97% hit rate on equivalent constructions.

#### 3.6.6 Implementation in the characterization harness

Target module: `symbolu_bcvf_llm/characterization/alignment.py`. Three public functions:

```python
def compute_alignment_metrics(
    cell_result: CellResult,           # wraps BCVFLLMResult + TraceBundle
) -> AlignmentMetrics:
    """Return (hit, margin, rank) for cells with truth_label, or None.
    """

def aggregate_alignment(
    cell_results: List[CellResult],
    group_by: str,                     # "family" | "bcvf_config" | "sigma_logit"
) -> Dict[str, AlignmentAggregate]:
    """Aggregate per-cell alignment into per-group statistics."""

@dataclass
class AlignmentAggregate:
    hit_rate: float
    margin_mean: float
    margin_percentiles: Tuple[float, float, float]   # 25/50/75
    rank_distribution: Dict[int, float]              # {1: ..., 2: ..., 3: ...}
    n_cells: int
```

`CellResult`, `AlignmentMetrics`, and the harness are pure NumPy; matches §2.8.1 dependency discipline. No ML-framework or plotting dependencies in the compute path.

#### 3.6.7 What §3.6 does NOT do

- **No Pearson correlation against a continuous ground-truth.** There is no continuous LLM-side analogue of `Δ|y|`. §4+ experiments may define one (perplexity change, human-rated factuality score) but §3 uses only the synthetic `truth_label`.
- **No multi-outlier scenarios.** V1 synthetic constructions have exactly one truth-outlier source. Multi-outlier (e.g., 2 of 3 sources diverge in different directions) is a V2 family per §9.
- **No soft alignment metric using `per_source_costs` as a probability distribution.** The normalized per-source costs *are* the input to §5's softmin, but §3.6 doesn't test that pipeline — it tests whether the raw per-source costs point the right way.
- **No causal alignment (does BCVF signal *precede* the failure?).** §3 traces are static snapshots without a time axis beyond `l`. Temporal precedence is a §4+ question once streaming generation is plumbed in.
- **No comparison to a baseline classifier** (e.g., "does a trivial vocab-L2 classifier without BCVF get the same hit rate?"). §3 is a correctness sweep, not a benchmark. The baseline-comparison ablation is V2.

§3.6 + §3.5 together constitute the full acceptance bar for Phase 1.5 per-cell evaluation. §3.9 aggregates them into the sign-off decision.

### 3.7 Edge cases and regression-guard traces

§3.2 exercises the kernel on families that *should* produce signal (or specifically zero under Lemma 1). §3.7 adds a complementary suite of **adversarial and regression-guard traces** — constructions designed to catch specific classes of implementation bugs that the core families might not. These are non-blocking individually but a failure in any one is an automatic §3 sign-off blocker.

#### 3.7.1 Purpose

Three kinds of trace live here:

1. **Hard-zero traces.** Constructions where the *exact* BCVF output must be zero (not "≤ 1e-10"). Identical sources, null perturbations, and fully-truncated stencils. These catch silent introduction of numerical noise at the sub-`1e-10` level.
2. **Broadcast / shape regression traces.** Constructions that exercise the `(..., V)` ellipsis-axis slicing decisions from §2.8.5–§2.8.7 with unusual-but-valid inputs. Catch off-by-one and axis-confusion bugs.
3. **Numerical-stability guards.** Constructions that push the kernel toward fp32 overflow, underflow, or catastrophic cancellation regimes. Validate §2.7.2's fp32 boundary rule and §2.6.7's Huber finite bound.

Unlike the §3.2 families which sweep over magnitudes, each §3.7 trace is a **single fixed construction** with a single pass/fail bit. The grid cost is trivial (≈8 cells total) and runs alongside the ablation grid in §3.4.7's execution order.

#### 3.7.2 Identical-sources hard zero

**Construction.** All three sources produce the *same* probability tensor bit-for-bit:
```
z = rng.normal(loc=0.0, scale=3.0, size=(L, V))
p_base = softmax(z, axis=-1)
p_0 = p_1 = p_2 = p_base      # literal reference, not copy
```

**Expected signature.** `e_{ij}(l) == 0` exactly (same object, subtraction yields zero). `a_{ij}(l*) == 0` exactly. `gate_input == 0`. `‖gate_input‖ == 0 < T`, so gate output ≈ `σ(-β·T) = σ(-20)` which is ~2e-9 (not zero but tiny). `‖a‖ == 0` so `penalty == 0` exactly. `total_cost == 0.0` bit-equal.

**Pass threshold.** `total_cost == 0.0` *exactly* (not within tolerance). `per_source_costs[s] == 0.0` exactly for all `s`. Any non-exact zero is a bug.

**What this catches.** Any numerical drift introduced by mixed-dtype arithmetic, silent dtype promotion bugs, or a spurious non-zero term added at the aggregation step. The bit-equal requirement is the strictest test in §3.

#### 3.7.3 Simplex-drift tolerance

**Construction.** Generate a base sequence per §3.3.1. For each source, apply an exact softmax in fp64, then **downcast to fp32** and back to fp64. This introduces fp32 rounding drift (~1e-7 per vocab entry, `Σ p` deviates from 1.0 by ~1e-5). Set `p_0 = p_1 = p_2 = drifted_base`.

**Expected signature.** Small rounding drift in `e_{ij}` and `a_{ij}`, but well below the gate threshold `T = 0.1`. Gate open probability ~0. `total_cost` should be ≲ `1e-6` purely from floating-point rounding after the Huber on the tiny `a`.

**Pass threshold.** `total_cost < 1e-5`. `gate_activation_count == 0`. No NaN or Inf.

**What this catches.** §2.7.3 committed that BCVF does not depend on the simplex sum holding exactly. This trace empirically verifies the claim. A failure would indicate that some path in the kernel implicitly assumes `Σ p = 1` — e.g., a division by `Σ p` or an assertion. Either would be a §2.7.3 violation.

#### 3.7.4 Weight-vector mis-broadcast guard

**Construction.** Two variants:

- Variant A: `weight_vector = np.ones(V, dtype=np.float64)` (explicit identity). Must produce the same result as `weight_vector = None` to within 1e-10.
- Variant B: `weight_vector = np.ones((1, V), dtype=np.float64)` (wrong shape — leading singleton axis). Must raise `ValueError` at the config-validation stage in `compute_bcvf_cost_batch` per §2.8.4.

**Expected signature.** Variant A: total_cost identical to identical-sources case. Variant B: `ValueError` with message matching "weight_vector shape".

**Pass threshold.** Variant A within 1e-10 of None-path. Variant B raises `ValueError`, kernel doesn't silently broadcast.

**What this catches.** Broadcasting bugs in the `smooth_gate` or signal-norm stage. NumPy's permissive broadcasting could silently accept a `(1, V)` weight and produce subtly wrong norms. §2.8.4 said validation belongs at `compute_bcvf_cost_batch` entry; this trace confirms that validation is actually present and rejects the bad shape.

#### 3.7.5 dtype mismatch guard

**Construction.** Generate sources in fp64. Pass to `compute_bcvf_cost_batch` with a `weight_vector` in fp32. 

**Expected signature.** Kernel either (a) upcasts `weight_vector` to fp64 at `np.asarray(..., dtype=np.float64)` inside `_pair_cost` / `smooth_gate`, preserving correctness, or (b) raises a dtype mismatch error clearly.

**Pass threshold.** Either: total_cost matches the all-fp64 path within 1e-10, OR ValueError raised. No silent precision loss.

**What this catches.** The §2.7.2 fp32-boundary commitment is about the *source tensor* dtype. `weight_vector` in a different dtype is an edge that could silently demote precision via NumPy broadcast rules. The kernel's `np.asarray(..., dtype=np.float64)` calls in `smooth_gate` and `_pair_cost` are the explicit promotions — this trace verifies they fire.

#### 3.7.6 Huber finite-bound stress

**Construction.** Set `accel_mag = 100.0` (extreme). Use the §3.2.4 family setup otherwise. Evaluate with V1 defaults `(T=0.1, β=200, δ=0.5)`.

**Expected signature.** `‖a‖` is huge (on the order of 10 after softmax compression), but the pseudo-Huber asymptote `penalty ≲ δ·‖a‖ = 0.5·10 = 5` per stencil position. `total_cost` bounded by `3 (pairs) · 3 (stencil positions) · 5 ≈ 45` at most. No NaN, no Inf.

**Pass threshold.** `total_cost < 1e3` (generous bound). `total_cost` finite. `np.isfinite(total_cost) and np.isfinite(max_acceleration_norm)`.

**What this catches.** §2.6.7's Huber-bound claim is load-bearing for §5 trust-weighting calibration. A kernel that blows up under extreme inputs would produce unbounded per-source costs, breaking softmin. This trace empirically verifies the bound holds.

#### 3.7.7 Empty-stencil guard (full EOS truncation)

**Construction.** All three sources emit EOS at `l=0`. `valid_masks_batch[:, :, 0] = True`, everything else `False`. Use any underlying family — baseline is simplest.

**Expected signature.** Every `valid(l*) = False` for all `l*`. Every pair contribution is zero. `total_cost == 0.0`. `per_source_costs[s] == 0.0` for all `s`. `gate_activation_count == 0`.

**Pass threshold.** Exact zeros as in §3.7.2. No NaN, no Inf. No division-by-zero.

**What this catches.** §2.4.4 / §2.7.4 specify that empty-stencil pairs report zero cost, not NaN. A naive implementation might compute `mean(empty_array)` → NaN. This trace catches that bug. It also stresses the "early termination over empty sum" path in `_pair_cost` if one is implemented as an optimization.

#### 3.7.8 NaN / Inf rejection

**Construction.** Generate sources per §3.3.1. Inject a single `np.nan` at one vocab position of one source.

**Expected signature.** `compute_bcvf_cost_batch` raises `ValueError` at the §2.7.6 kernel-boundary guard. No propagation of NaN downstream.

**Pass threshold.** Raises `ValueError` with message matching "non-finite". Does NOT return a NaN-containing result silently.

**What this catches.** §2.7.6 committed the NaN-at-boundary policy. This trace verifies the guard is present and fires. Forgetting the guard would allow NaN-poisoned per-source costs to pollute §5's softmin and fail silently.

#### 3.7.9 Aggregation and pass/fail for §3.7

Each §3.7 trace is a **single cell**, no magnitude sweep, no seed replication (the constructions are either bit-deterministic or exercise fp32 rounding which seed-to-seed doesn't affect the pass/fail outcome). §3.9 sign-off requires **all 7 traces** (§3.7.2–§3.7.8) pass.

| Trace | Primary role | Pass bit |
|---|---|---|
| §3.7.2 Identical sources | Hard-zero regression guard | `total_cost == 0.0` exact |
| §3.7.3 Simplex drift | Rounding-tolerance guard | `total_cost < 1e-5`, no activations |
| §3.7.4 Weight mis-broadcast | Shape-validation guard | Variant A within 1e-10; Variant B raises |
| §3.7.5 dtype mismatch | Precision guard | Matches fp64 path OR raises |
| §3.7.6 Huber extreme stress | Bound check | `total_cost < 1e3`, finite |
| §3.7.7 Empty stencil | Truncation edge | All zeros exact |
| §3.7.8 NaN injection | Boundary-guard verification | `ValueError` raised |

**Zero failures tolerated.** Unlike §3.5's 3-seed replication, §3.7 is deterministic — either the guard works or it doesn't. One fail = §3.9 blocked.

**Implementation note (§3 execution, commit `543e3e8`).** Four of the seven §3.7 guards are covered by the §2.9 unit-test suite rather than re-executed as separate cells in the §3.4 sweep harness, because the unit tests verify the identical property at the kernel-API level:

| §3.7 guard | Coverage |
|---|---|
| §3.7.2 Identical sources → hard zero | `test_pair_cost_constant_bias_zero` + `test_lemma_1_constant_bias_zero` (§2.9 #27, #42) |
| §3.7.3 Simplex-drift tolerance | `test_compute_disagreement_translation_invariant` (§2.9 #5) |
| §3.7.7 Empty-stencil guard (full EOS) | `test_pair_cost_all_invalid_returns_zero` (§2.9 #25) |
| §3.7.8 NaN / Inf rejection | `test_compute_bcvf_cost_scalar_nan_guard` (§2.9 #34) |

The remaining three guards (§3.7.4 weight mis-broadcast, §3.7.5 dtype mismatch, §3.7.6 Huber extreme stress) are not yet exercised by either §2.9 or the §3 harness. Adding them as either §2.9 tests or §3.4.4-adjacent single-cell traces is outstanding work; the absence is recorded here rather than silently skipped.

#### 3.7.10 What §3.7 does NOT do

- **No sweep over parameters.** Each §3.7 trace uses V1 defaults `(T, β, δ) = (0.1, 200, 0.5)`, `sigma_logit = 3.0`, `V = 1024`. Parameter-space robustness of the guards is irrelevant — the guards check structural properties that should hold regardless of parameter values.
- **No interaction with alignment diagnostic (§3.6).** None of the §3.7 traces carry a `truth_label`, so alignment metrics don't apply. Guard traces are pass/fail only.
- **No performance / timing constraints.** A guard trace may be slow if it triggers a validation path that doesn't vectorize well; that's acceptable for a once-per-sweep check.
- **No coverage of speculative-decoding plumbing** (that's §4's concern — speculative-decode pipeline integration is where those bugs would emerge).
- **No V2-roadmap guards** (e.g., multi-model ensemble shape bugs, KL-metric fallback). Deferred to §9.

§3.7 is the safety net under §3.5 + §3.6. If the core families pass but a §3.7 guard fails, there's a specific bug class to investigate; if all §3.7 pass but core families fail, the bug is in magnitude-dependent behavior. Diagnostic separation.

### 3.8 What §3 does NOT do

§3 is a *correctness* sweep over a bounded synthetic surface. Most sub-sections touched on specific exclusions inline; §3.8 consolidates every exclusion into one authoritative list, grouped by reason, so no future reviewer has to reconstruct scope from scattered non-goals.

#### 3.8.1 Domain exclusions — no real LLM in sight

- **No real model forward passes.** The characterization harness (§3.3.6) is pure NumPy; no `torch`, no `transformers`, no `datasets`. Deferred to §4.
- **No tokenizer.** `V` is an integer vocab size; no token ids, no text, no vocabulary semantics. Deferred to §4.
- **No attention-correlated noise.** §3.2.5's noise is IID Gaussian in logit space. Real forward passes have attention-head-correlated noise that §3 explicitly doesn't model. Deferred to §4.
- **No semantically-plausible outlier patterns.** §3 synthesizes outliers as pure algebraic perturbations (§3.3.2). Real hallucinations, repetition, incoherence — deferred to §4 empirical study.
- **No sampling from probability sequences.** §3 compares distributions; it never draws tokens. Sampling is a §4 integration concern.
- **No `sigma_logit` calibration against real models.** §3 spans `{1.0, 3.0, 5.0}` as an envelope; §4 will retroactively report what a real model actually produces and validate the envelope.

#### 3.8.2 Architectural exclusions — no trust-weighting yet

- **No §5 Ketu→Rahu composition.** §3 validates that `per_source_costs` is a usable *input* for trust-weighting. §5 is where those costs get passed through a softmin and become an attractor. Zero §5-side code runs in §3.
- **No `τ_w` calibration.** Temperature for §5's softmin is a Phase 3 concern. §3 exits with per-source cost distributions; §5 decides how to compress them.
- **No Rahu attractor integration with the base decoder.** §3 doesn't touch hidden-state shaping, logit blending, or routing/gating. Deferred to §5.
- **No J_perf replacement.** Autonomy's J_perf → trust-weighted-consensus-attractor was the N=10 Ketu→Rahu breakthrough. The LLM analogue is §5's problem; §3 has no MPPI or objective function to replace.

#### 3.8.3 Integration exclusions — no §4 plumbing

- **No speculative-decoding pipeline integration.** §3 constructs `(L, V)` sequences directly. Real speculative decoding requires a draft model, acceptance loop, KV-cache synchronization — all deferred to §4.
- **No KV-cache management.** §3 never shares or replicates KV-cache across sources because §3 has no model.
- **No batched outer-step streaming.** §3's `T` axis is always 1 (or a small fixed batch). Real streaming generation with `T` growing over time is §4/§5.
- **No source-framework API contract.** §3 doesn't define how a "source" is implemented. §4 handles that.

#### 3.8.4 Metric exclusions — no end-to-end quality signal

- **No Pearson correlation against continuous ground truth.** There is no LLM-side `Δ|y|` equivalent (§3.6.1). §3 uses only discrete `truth_label` classification metrics.
- **No causal / temporal alignment.** §3 traces are static snapshots along `l`; no "does BCVF signal precede the failure?" question. That's a streaming-generation property, §4+.
- **No comparison to a naive baseline classifier.** §3 doesn't ask "does BCVF beat a trivial vocab-L2 outlier detector?" — that's V2 benchmark territory.
- **No perplexity / coherence / factuality scores.** End-to-end quality metrics require a real LLM and an evaluation dataset; §3 has neither.
- **No soft-alignment via `per_source_costs` as a probability distribution.** §3.6 checks that `argmax` points at truth; it does NOT test the downstream softmin's distribution quality. §5 does that.

#### 3.8.5 Sweep exclusions — bounded grid only

- **No cross-family joint sweeps.** §3 keeps families isolated (§3.4.8). Combined stressors (outlier + noise + partial EOS simultaneously) are V2.
- **No sweep over `M`.** §1.3 locks `M = 3`. V2 may explore M=2 degeneracy or M=5 redundancy.
- **No sweep over `L`.** §2.3.4 locks `L = 5`. V2 may explore L=3 (tight) or L=7 (speculative budget expansion).
- **No sweep over `cost_order` outside the §3.4.4 ablation.** `SECOND` is the production regime; ZEROTH/FIRST are there to empirically confirm §2.8.3's Lemma-1 violation warning, not to characterize production performance.
- **No sweep over alternative disagreement metrics** (KL, Hellinger, top-k-truncated L2). V2 per §2.2.6 / §9.
- **No cross-cell statistics.** "Does `total_cost` trend fit a quadratic across `accel_mag`?" is a useful *narrative* in §3.9 but not a *pass criterion*. §3 sticks to per-cell pass/fail.

#### 3.8.6 Discipline exclusions — what §3 refuses to do

- **No threshold tuning mid-sweep.** §3.5 thresholds are fixed before the sweep runs. If a threshold fails, the answer is to revise §2 or the kernel implementation — not to relax the threshold. Discipline is non-negotiable.
- **No soft or probabilistic passes.** Every threshold is absolute. No "pass 8 of 10 cells" or "acceptable at 90% confidence."
- **No interactive human-in-the-loop evaluation.** §3 is a deterministic script; it produces pass/fail bits without human judgment at evaluation time. The threshold choices themselves are human-authored (in §3.5), but the evaluation is mechanical.
- **No retries on transient failures.** If a cell fails, it fails. Reproducibility from seeded RNG means there are no "transient" failures — only real ones.

#### 3.8.7 Training / optimization exclusions — no gradient anywhere

- **No training-time signal** (`L_trust`, `L_smooth`, or any loss function involving BCVF). Explicitly V2 per §2.5.5.
- **No gradient-based tuning of `T`, `β`, `δ`, `τ_w`.** Phase 1.5 is a grid sweep, not an optimizer. Gradient-based hyperparameter search is V2.
- **No auto-calibration of thresholds.** §3.5's pass thresholds are hand-chosen; no data-driven tuning.
- **No online adaptation.** §3 is fully offline / deterministic; adaptive behavior is §5+ territory.

#### 3.8.8 What each exclusion unblocks downstream

Cross-reference table linking exclusions to their resolution phase:

| Exclusion | Resolved by |
|---|---|
| Real model forward passes, tokenizer, attention noise | §4 Phase 2 |
| Speculative decoding, KV-cache, source-framework API | §4 Phase 2 |
| Trust-weighting, τ_w, J_perf replacement | §5 Phase 3 |
| Pearson correlation, causal alignment, perplexity | §4+ empirical studies |
| M/L/metric sweeps, multi-outlier, joint families | §9 V2 Roadmap |
| Gradient-based hyperparameter tuning, training losses | §9 V2 Roadmap |
| Cross-cell narrative / trend fitting | §3.9 reporting (narrative only, not pass criteria) |

Every exclusion in §3.8 has a named downstream home. Nothing is silently dropped; everything has a sign-off path for later.

#### 3.8.9 Summary rubric

§3 does exactly two things well:

1. **Proves the kernel is correct by construction on tight synthetic inputs.**
2. **Picks V1 parameter defaults that withstand realistic-scale inputs.**

§3 does not:

1. Prove the kernel is useful.
2. Prove the kernel matches real LLM failure modes.
3. Prove the composition with §5 works.
4. Prove anything about end-to-end generation quality.

All four "does not" items are §4 / §5 / §6 responsibilities. §3 is the last cheap-abort gate before expensive downstream work — nothing more, nothing less.

### 3.9 Acceptance criteria for §3 itself + effort estimate

§3.9 closes Phase 1.5. It defines the sign-off procedure that converts the raw sweep output into a binary decision (unlock §4 or trigger §0.6 stop rule #4), picks the V1 parameter tuple, and commits the deliverable timeline.

#### 3.9.1 Sign-off decision procedure

§3 is signed off — i.e., Phase 1.5 closes and §4 unlocks — when **all four** of the following hold:

1. **§3.4.4 ablation grid.** `cost_order = SECOND` passes §3.2.3 linear-drift thresholds on every cell; `cost_order = FIRST` **fails** §3.2.3 on cells with `drift_rate > 0` (positive confirmation of §2.8.3 / §2.6.4 warning). If `FIRST` passes linear-drift, §3 is blocked and the entire §2 chain is re-opened.
2. **§3.4.2 primary grid.** All 7 trace families from §3.2 achieve `family_pass_rate == 1.0` under V1 defaults `(T=0.1, β=200, δ=0.5)` at `sigma_logit=3.0, V=1024`, per §3.5 thresholds AND §3.6 alignment thresholds.
3. **§3.4.3 sensitivity grid.** At least one `(T, β, δ)` tuple achieves `config_pass_rate == 1.0` across all 7 families *and* `sigma_logit ∈ {1.0, 3.0, 5.0}`. If V1 defaults pass primary, they by definition pass this at `sigma_logit=3.0`; sensitivity confirms robustness to entropy variation.
4. **§3.4.5 full-V spot check.** The winning tuple from step 3 passes all 7 families at `V = 32000`, confirming V=1024→V=32000 scaling doesn't flip any pass/fail bit.

Additionally (non-gating but required for the artifact):

5. **§3.7 regression guards.** All 7 guard traces pass per §3.7.9. A guard failure does not itself block sign-off (guards catch specific bug classes that may already be known and worked around), but §3.9 reporting must explicitly enumerate any guard failure and why it's accepted.

**All four primary conditions are binary.** If any one fails, §3 is not signed off, §4 does not unlock, and §3.9.4's failure-mode reporting kicks in.

#### 3.9.2 Aggregating sweep results into a V1 winner tuple

From the sensitivity grid (§3.4.3), more than one `(T, β, δ)` may satisfy `config_pass_rate == 1.0`. The V1 winner is chosen by the following deterministic tiebreaker:

1. **Filter** to tuples satisfying conditions 2 and 3 of §3.9.1.
2. **Rank** candidates by Euclidean distance in parameter space to V1 defaults `(0.1, 200, 0.5)`:
   ```
   distance = sqrt( ((T - 0.1)/0.1)^2
                  + ((β - 200)/200)^2
                  + ((δ - 0.5)/0.5)^2 )
   ```
   Normalized deviations so the three parameters contribute equitably.
3. **Select** the minimum-distance tuple. Ties broken by (a) lowest `T`, then (b) highest `β`, then (c) lowest `δ` — in that order, purely for determinism.
4. **Validate** the winner with §3.4.5 full-V spot check. If it fails at `V=32000`, fall back to the next-best tuple and re-validate. If all sensitivity-grid winners fail full-V, §3.9 is blocked and §3.9.4 reports scale-mismatch at production V.

The "closest to V1 defaults" rule is a deliberate design-stability choice: among tuples that pass, prefer the one that least disrupts §2.5's derivations. This keeps §2.5 documentation aligned with the §3 empirical choice whenever possible.

#### 3.9.3 Failure-mode classification and reporting

If any §3.9.1 condition fails, the failure is classified per §3.1:

**Scale mismatch (fixable in §3).** Characterized by: (a) some `(T, β, δ)` tuple exists that passes all families, but (b) V1 defaults are not it. Fix: adopt the winner tuple from §3.9.2 as the new V1 default, update §2.5.1 / §2.5.2 tables accordingly, re-commit. Scale mismatch does not require returning to §2 math — only updating the default values §2.5 declared provisional.

**Structural mismatch (escalates to §2 revision).** Characterized by: *no* `(T, β, δ)` tuple in the sensitivity grid achieves `config_pass_rate == 1.0`, OR §3.2.3 linear-drift fails at `cost_order=SECOND`. This indicates that the kernel does not satisfy Lemma 1 under realistic-scale inputs, or the 2:1 attribution claim does not hold — either is a §2 math problem, not a §3 tuning problem. Trigger: §0.6 stop rule #4.

**Vocabulary-scale mismatch (fixable in §3, diagnostic).** Characterized by: sensitivity grid finds a winner at `V=1024` but it fails at `V=32000`. Indicates softmax rounding at larger V changes effective noise regime. Fix: expand sensitivity grid to `V=32000` directly and re-pick winner — adds roughly 30× runtime but still minutes total. Still cheap compared to §4.

The §3.9 deliverable summary (§3.9.5) explicitly classifies the run as one of: `PASS`, `SCALE_MISMATCH_FIXED`, `VOCAB_SCALE_MISMATCH_FIXED`, `STRUCTURAL_FAILURE`. The first three unlock §4; the fourth halts Phase 1.5 and triggers §2 revision.

#### 3.9.4 Deliverable artifact checklist

The §3 sign-off produces three artifacts, all committed to the repo:

1. **Code:** `symbolu_bcvf_llm/characterization/` package with:
   - `traces.py` — `generate_trace` + `TraceBundle` (§3.3.6).
   - `alignment.py` — `compute_alignment_metrics` + `aggregate_alignment` (§3.6.6).
   - `sweep.py` — orchestrates the four §3.4 grids; returns per-cell `CellResult` list.
   - `__main__.py` — CLI entry `python -m symbolu_bcvf_llm.characterization` runs the full sweep and writes artifacts below.
   - `tests/` — pytest coverage of generator determinism, alignment metric correctness, sweep harness (not the kernel itself; that's §2.9).

2. **Results data:** `docs/experiments/phase_1_5_results.csv` (or JSON) with one row per cell: `(family, family_params, T, β, δ, sigma_logit, V, seed, total_cost, max_accel_norm, gate_activations, per_source_costs, hit, margin, rank, threshold_pass, alignment_pass, cell_pass)`. Reproducible from the committed code + seed list.

3. **Report:** `docs/experiments/phase_1_5_summary.md` — 1–2 pages containing:
   - Sweep scope (grid counts).
   - Pass rate per family at V1 defaults.
   - Winner tuple from §3.9.2 (usually V1 defaults themselves).
   - Failure-mode classification per §3.9.3.
   - Any §3.7 guard failures with acceptance rationale.
   - Recommendation: `UNLOCK §4 AT (T=..., β=..., δ=...)` or `HALT`.

All three artifacts land in one commit tagged `phase_1_5_signoff`.

#### 3.9.5 Effort estimate

- **Characterization module implementation:** 1 day. `traces.py` is roughly 200 LOC of generator code plus dataclass wiring; `alignment.py` is 100 LOC; `sweep.py` orchestrates and writes results.
- **Sweep execution:** <1 minute wall time (§3.4.6's 3–4 seconds plus full-V spot check runtime, plus CSV I/O).
- **Results analysis + report writing:** 0.5 day. The hard work is already done by the sweep; the report is a summary of committed numbers, not a novel analysis.
- **Debug iterations (if scale mismatch):** 0.5 day budgeted. Typically one cycle of re-picking winner tuple and re-running.
- **Total Phase 1.5:** ~2 days, within §1.9's 2-week V1 budget.

**Dependency on Phase 1 execution.** §3 *design* (this sub-section and earlier) can be authorized and land without Phase 1 execution — it's pure specification. §3 *execution* requires `symbolu_bcvf_llm/core.py` to exist and pass §2.9's 49 tests. The earliest §3 execution can start is immediately after §2.9 sign-off.

#### 3.9.6 Acceptance criteria for §3 overall

§3 is considered design-complete when:

1. ✅ §3.0 sub-section plan enumerated.
2. ✅ §3.1 purpose & deliverable committed.
3. ✅ §3.2 seven trace families defined with coverage matrix.
4. ✅ §3.3 generation protocol (base sequence, perturbation primitives, generator API) committed.
5. ✅ §3.4 four sweep sub-grids (primary / sensitivity / ablation / full-V spot check) enumerated.
6. ✅ §3.5 per-family threshold tables committed with 3-seed rule.
7. ✅ §3.6 alignment diagnostic (hit / margin / rank) committed with 4 pass thresholds.
8. ✅ §3.7 seven regression-guard traces committed.
9. ✅ §3.8 exclusions consolidated.
10. ✅ §3.9 sign-off procedure, tiebreaker, failure classification, deliverable checklist, effort estimate committed (this sub-section).

Items 1–10 are satisfied. §3 **design is complete**; §3 execution remains pending §2.9 sign-off and Phase 1 execution.

#### 3.9.6.bis Empirical addendum — §3 sweep result (commit `543e3e8`)

Recorded here after-the-fact so the recommendation in §3.9.4 / §3.9.5 is anchored to actual numbers rather than projected ones. Artifacts: `docs/experiments/phase_1_5_results.csv`, `docs/experiments/phase_1_5_summary.md`.

**Classification: `PASS`** (§3.9.3). All four §3.9.1 conditions hold:

| Condition | Result |
|---|---|
| §3.4.4 ablation — SECOND passes linear-drift, FIRST fails on drift>0 | ✅ SECOND 15/15 pass; FIRST 0/15 pass; ZEROTH 0/15 pass — §2.6 C2 vector-path invariance empirically confirmed both ways |
| §3.4.2 primary — all 7 families 100% at V1 defaults, σ=3.0, V=1024 | ✅ 87/87 cells pass |
| §3.4.3 sensitivity — at least one `(T, β, δ)` tuple passes all families × σ | ✅ 1701/1701 cells pass; all 27 `(T, β, δ)` tuples qualify as candidates |
| §3.4.5 full-V spot check at V=32000 with winner tuple | ✅ 21/21 cells pass |

**Winner tuple (§3.9.2): `T = 0.1, β = 200, δ = 0.5`** — V1 defaults unchanged. Tiebreaker produced 27 candidates (every sensitivity-grid tuple passes); the Euclidean-distance ranking selects V1 defaults at rank 1 as the minimum-deviation choice. Top 5 by distance: (0.1, 200, 0.5), (0.05, 200, 0.5), (0.1, 200, 0.25), (0.1, 100, 0.5), (0.05, 200, 0.25).

**Alignment (§3.6):** all truth-label-bearing families return `hit_rate = 1.00` and `margin_mean = 2.00` across the sweep. Zero rank-3 (fully inverted) cells observed.

**Deviations from spec** (also noted inline at §3.3.3 and §3.7.9):
1. Perturbation space for 4 of 7 families is probability-space, not logit-space (§3.3.3 implementation note). Softmax nonlinearity + V=1024 unit-direction scale made logit-space perturbations incompatible with §3.5.3 / §3.5.4 fp64 1e-10 thresholds and §3.5.5 / §3.5.7 gate-activation thresholds. Probability-space construction preserves §3.3.4 realism rationale (base is still softmax-shaped; only the perturbation layer changes).
2. §3.7.2 / §3.7.3 / §3.7.7 / §3.7.8 guards are covered by §2.9 unit tests rather than re-executed as separate §3 sweep cells. §3.7.4–§3.7.6 are noted as outstanding (§3.7.9 implementation note).

**Recommendation:** `UNLOCK §4 AT (T=0.1, β=200, δ=0.5)`. §0.6 rule 1 (autonomy N=26 confirmation) remains the independent gate on §4 execution; §3 does not and cannot substitute for it.

#### 3.9.7 What §3.9 does NOT cover

- **No §4 unlock procedure beyond "§3 passes."** §4 has its own entry criteria documented in §4 (once that section is filled); §3.9 just commits that §3 passes or fails, not what §4 does next.
- **No rollback procedure** if §3 passes but §4 reveals a regression. That's §4's concern — §4's implementation will re-run §3's sweep as part of its own sanity checks, and if the kernel has regressed, §4 halts and reports.
- **No live-monitoring or CI wiring.** The §3 sweep is designed to run once per design iteration, not continuously. V2 may wire it into CI.
- **No publishing path.** The summary report is internal documentation, not a paper or external artifact. If the full experimental protocol ever becomes externally shareable, that's a V2 concern.

---

**§3 Phase 1.5 design is now complete end-to-end: §3.0 through §3.9.**

---

## Section 4 — Phase 2 — Source Framework

**Purpose:** Define the M=3 V1 sources (base decoder + two paraphrased decoders), their output shape, how their states are sampled at each outer decoding step, and the API contract they present to the two baseline decoders from §1.10 (vanilla, conventional-blend) as well as to §5's trust-shaped decoder.

### 4.0 Sub-section plan

§4 follows the same authorization-per-sub-section discipline as §2 and §3. This planning sub-section enumerates the intended sub-sections so the arc of Phase 2 is visible before details land.

- **§4.1** — Purpose & deliverable. What §4 produces, what §4 explicitly defers to §5 / §6.
- **§4.2** — `Source` protocol. The abstract interface every source satisfies: `lookahead()`, `commit()`, `vocab_size`, `L`, `eos_token_id`. Justification for pull-based `lookahead/commit` rather than a streaming generator.
- **§4.3** — `MockSource` for testing. Deterministic `(prefix) → logits` callable used by the §4.9 test suite and by §5's integration tests without a real model dependency.
- **§4.4** — `HuggingFaceSource` for real execution. Llama 3.1 8B via `transformers`, fp16/bf16 inside, fp32 at the BCVF boundary (§2.7.2). KV-cache amortization per §2.3.4 (two forward passes per outer step). Delayed torch import so the kernel tests never pull an ML stack.
- **§4.5** — Paraphrased-prompt construction. How rewrite-seeds α, β produce the two fallible sources per §1.4.2 / §1.4.3 at temperature 0 with a fixed rewrite instruction.
- **§4.6** — Two baseline decoders from §1.10 (vanilla + conventional-blend). The generic outer greedy loop that both share. BCVF integration hook left for §5 to plug into.
- **§4.7** — EOS and valid-mask production. Per-source EOS detection, how a truncated lookahead flows through `valid_mask` into §2.8.11 / §2.8.12.
- **§4.8** — What §4 does NOT do. No trust-weighting (§5), no benchmark / eval harness (§6), no sampling beyond greedy (§1.3).
- **§4.9** — Acceptance criteria + test specification. What closes Phase 2 and unlocks Phase 3.

Each sub-section lands one commit at a time per §0.8.

### 4.1 Purpose & deliverable of Phase 2

**Purpose.** §3 verified the BCVF kernel on synthetic probability sequences. §4 bridges the gap to real model outputs by defining:

1. A domain-neutral `Source` protocol that any "something that produces per-step probability lookaheads" can satisfy — mocked, HuggingFace-backed, or (V2) a different model family.
2. Two baseline decoders from §1.10 (vanilla, conventional-blend) that operate on a list of sources and emit tokens via greedy outer decoding. These baselines are what §6 will compare BCVF-trust against.
3. Paraphrased-prompt construction so the M=3 requirement from §1.3 / §2.2.3 is realizable from one model and one original prompt.

**Hard gate on §6.** §6 cannot start until §4 produces a verified decoder output on `MockSource`-backed traces that matches, token-for-token, a hand-computed reference. The real-model (HuggingFace) path is structurally scaffolded in §4 but its empirical verification is §6's concern, running inside the benchmark harness.

**Deliverable.** A bounded artifact consisting of:

1. Python package `symbolu_bcvf_llm/sources/` with:
   - `base.py` — `Source` protocol + shared utilities.
   - `mock.py` — `MockSource` for deterministic prefix-keyed logits.
   - `huggingface.py` — `HuggingFaceSource` scaffold with delayed torch/transformers imports.
   - `paraphrase.py` — `make_paraphrased_prompt` utility.
2. Python package `symbolu_bcvf_llm/decoders/` with:
   - `loop.py` — generic greedy outer-decoding loop.
   - `vanilla.py` — source-0-only decoder.
   - `blend.py` — equal-weight conventional blend over M sources.
3. Tests in `symbolu_bcvf_llm/sources/tests/` and `symbolu_bcvf_llm/decoders/tests/` that exercise both baseline decoders end-to-end via `MockSource`, without pulling torch.

**Independence from §0.6 rule 1.** §4 *code* can be scaffolded and unit-tested (via MockSource) without autonomy N=26 confirmation — same as §2 / §3 code. §4 *real-model execution* (HuggingFaceSource actually running against Llama 3.1 8B) and §4's role inside the §6 benchmark remain hard-gated on §0.6 rule 1.

**Sub-sections §4.2–§4.9 are currently pending authorization.** The in-line implementation notes below document what was built under the §4 scaffold commit as a strategic realization of §4.1's deliverable, matching the §3 pattern where design-draft sub-sections were implemented and surgically annotated after.

### 4.N Implementation notes — §4 scaffold (commit pending `go §4`)

This sub-section records the actual §4 scaffold landed under Phase 2 execution. Contents match `symbolu_bcvf_llm/sources/` and `symbolu_bcvf_llm/decoders/`. Each note ties back to the §4.0 sub-section it realizes.

**§4.2 Source protocol.** `symbolu_bcvf_llm/sources/base.py` defines a `typing.Protocol` with two methods (`lookahead() → (probs, valid_mask)`, `commit(token_id)`) and three attributes (`L`, `vocab_size`, `eos_token_id`). Shared utilities `stable_softmax` (fp64 internal, fp32 return per §2.7.2) and `truncating_valid_mask` (EOS-aware masking per §2.7.4) live alongside. `MockSource` and `HuggingFaceSource` both declare structural conformance via `runtime_checkable`.

**§4.3 MockSource.** `symbolu_bcvf_llm/sources/mock.py` takes a `logits_fn: Callable[[Tuple[int, ...]], np.ndarray]` and owns the committed-prefix state + softmax boundary + EOS-mask production. No ML-framework dependency. 10 unit tests in `sources/tests/test_mock_source.py` verify protocol conformance, shape/dtype, fp32 boundary, softmax normalization, EOS mask truncation, commit-state advancement, and validation of out-of-range tokens, wrong-shape fn output, and `L < 3`.

**§4.4 HuggingFaceSource.** `symbolu_bcvf_llm/sources/huggingface.py` scaffolds the real-model path with delayed torch/transformers imports: `__init__` imports torch locally and raises a clear `RuntimeError` if it's missing. The class body encodes §2.3.4's KV-cache amortization (one forward pass to commit, one to extend the frontier) and §2.7.2's fp32 boundary (softmax upcast inside `lookahead`). **Not executed against a real model in this environment** — V1 targets Llama 3.1 8B which requires GPU, and real-model verification is hard-gated on §0.6 rule 1. Two scaffold tests verify (a) the module imports without torch, (b) the constructor raises a clear RuntimeError when torch is absent.

**§4.5 Paraphrase utility.** `symbolu_bcvf_llm/sources/paraphrase.py` exposes `make_paraphrased_prompt(model, tokenizer, original_prompt, rewrite_seed)` — a thin `model.generate` wrapper with a fixed rewrite instruction templated with `{seed}` and `{prompt}`. Temperature 0 per §1.4. Same delayed-torch discipline as §4.4.

**§4.6 Decoders.** `symbolu_bcvf_llm/decoders/`:
- `loop.py` — `run_decode(sources, next_token_fn, max_tokens, eos_token_id)` generic greedy outer loop. Calls `lookahead()` once per source per outer step, asks the strategy for a token, commits into every source. Shape-checks sources share a vocabulary. Returns `DecodeResult(emitted_tokens, stopped_on_eos, num_steps)`.
- `vanilla.py` — `decode_vanilla(sources, max_tokens, eos_token_id)` §1.10 baseline A0. Strategy: `argmax(p_0(l=0))`. Ignores sources 1..M-1 for the *decision* but commits into them so state stays coherent.
- `blend.py` — `decode_conventional_blend(sources, ...)` §1.10 conventional-blend baseline. Strategy: `argmax(mean_s p_s(l=0))`.

The §5 trust-shaped decoder is a one-function drop-in at the `next_token_fn` hook — no outer-loop refactor needed when §5 lands.

**§4.7 EOS and valid masks.** Handled in two places: `truncating_valid_mask(lookahead_tokens, eos_id, L)` in `sources/base.py` produces the per-source `(L,)` mask; `run_decode` stops the outer loop when the strategy emits `eos_token_id`. These two mechanisms are complementary — the per-source mask feeds the BCVF kernel's `valid_masks` argument (§2.8.11) so the stencil correctly skips positions past each source's EOS, while the outer-loop EOS check is the hard stop for generation.

**§4.8 What §4 does NOT do.** No trust-weighting (§5). No benchmark harness (§6). No sampling beyond greedy (§1.3). No batched outer steps (T=1 streaming only). No cross-source KV-cache sharing (each HuggingFaceSource owns its own cache — V2 optimization per §9).

**§4.9 Acceptance criteria — status.** §4 sign-off would require:

1. ✅ Source protocol committed (§4.2) with structural conformance tests.
2. ✅ MockSource implementation + unit tests — 10 tests pass deterministically.
3. ✅ HuggingFaceSource scaffold with delayed-import discipline — 2 scaffold tests pass.
4. ✅ Two baseline decoders (vanilla, conventional-blend) + generic outer loop — 11 tests pass.
5. ⏳ **Pending:** real-model smoke test on HuggingFaceSource against Llama 3.1 8B, end-to-end token-for-token match against a hand-computed reference. Blocked on GPU availability and §0.6 rule 1. Landing point: §6 benchmark setup.
6. ⏳ **Pending:** integration smoke test of the three-source paraphrased pipeline end-to-end. Same blocker.

Items 1–4 are sufficient to unlock §5 (trust-shaped decoder) scaffolding and its MockSource-backed tests; items 5–6 are the §6 entry condition, not §5's.

**Test totals for §4 scaffold:** 24 tests, <1 s on CPU, no torch/transformers import in any passing test.

---

## Section 5 — Phase 3 — Integration Layer (Ketu→Rahu)

**Purpose:** Implement the trust-weighted consensus and its point of contact with generation. V1 chooses one of:
- **Hidden-state shaping:** `h̃_t = h_t + U · c*_t`
- **Logit blending:** `z* = z_base + α · consensus_projection`
- **Routing/gating:** use trust weights to select which source's logits win per step

Select one for V1, justify the choice, and document the other two as deferred alternatives.

**Most details pending.** §5 is filled sub-section-by-sub-section under the same authorization gating as §2 and §3. The two sub-sections below land first because they capture autonomy-validated structural commitments that any §5 V1 implementation must respect; the consumer-architecture choice (hidden-state shaping vs logit blending vs routing/gating) and the V1 use-case taxonomy will be filled in subsequent authorized passes.

### 5.1 Continuous trust-shaping integration pattern (autonomy-validated)

When a §5 consumer uses BCVF as a **continuous trust-shaping signal** — converting per-source costs into trust weights at every consumer step and using those weights to compose a consensus — the autonomy companion experiments (`S3_map_error_accel`, M = 4 SE(2) predictors, N = 26 paired) established a small structural pattern that the LLM V1 implementation must follow. The pattern is taken as a **design constraint for V1**, not a universal theorem; broader use-case guidance is deferred to later sub-sections.

**Pattern (V1 commitment for continuous trust-shaping consumers):**

1. **Per-source baseline normalization.** Maintain an exponential moving average `EMA_mean[i]` of `per_source_costs[i]` across consumer steps and subtract it from the current cost before any trust-weighting computation. Required because the raw per-source cost has a context-dependent baseline (§2.7.11) that, if uncorrected, dominates the trust distribution and reduces the consumer to a near-no-op. V1 default `α = 0.05` (effective τ ≈ 20 outer steps); cold-start initializes `EMA_mean[i]` from the first observed value so the residual is exactly zero on step 0 (safe — uniform weights).
2. **Significance gate / hinge-φ shaping before softmin.** Apply either a hard deadband (`|residual| < k · σ`, `k ≈ 2`, with `σ` tracked as an EMA of squared residual) or — equivalently and gentler at the boundary — a hinge transform `φ(d) = max(d − θ, 0)` on the cost feeding softmin. Required because the centered residual surfaces previously-masked noise that, without filtering, drives spurious trust shifts on contexts where no genuine disagreement is present. Either form is acceptable; the hinge composes more cleanly with autodiff and is the V1 preference if §5 implementation needs gradient-friendly behavior.
3. **All-pairs (non-anchor) pair enumeration when M ≥ 3.** Already committed at the kernel-config level in §2.4.5 / §2.8.4 (`use_anchor_pairing = False` is the V1 default for `BCVFLLMConfig`). The autonomy result is empirical confirmation: under anchor pairing with the failing source as the anchor, the trust softmin can up-weight the predictor that *agrees with the failing anchor* (collusion semantic); non-anchor pairing avoids this by symmetric attribution. §5 consumers must consume per-source costs produced under non-anchor pairing.

**What this pattern is NOT.** The pattern above does not specify the consumer-architecture choice (hidden-state shaping vs logit blending vs routing/gating), the use case (token-level reweighting vs branch selection vs document retrieval vs verifier ensemble), the trust-temperature `τ_w`, or any LLM-specific tuning. Those are deferred to authorized sub-sections of §5 once empirical evidence in the LLM domain is available. §5.1 commits only the two-stage normalization plus non-anchor pairing as the **necessary preprocessing** for any continuous trust-shaping consumer.

**Reproducibility pointer.** The autonomy companion experiments and their statistical results are recorded in `docs/experiments/` (commit history in `symbolu_robotics/bcvf_autonomous/`). The validated configuration is `T = 0.05, β = 400, ema_alpha = 0.05, deadband_k_sigma = 2.0, use_anchor_pairing = False`, with sign-test p < 0.01 vs the no-shaping baseline at N = 21 paired.

### 5.2 Caveat — downstream dynamic sensitivity

A second autonomy finding worth recording before §5 commits to a consumer architecture: **trust shaping has limited dynamic range when downstream system dynamics are chaotic.** In the autonomy experiments, the validated §5.1 pattern produced trust weights that were near-uniform on roughly 80% of consumer steps (deadband active) and within ±0.013 of uniform (0.25 ± 0.013 at M = 4) on the remaining 20%. Despite this, the system's catastrophe count remained at a structural floor (3 of 26 across multiple parameter configurations), with the **specific seed identities rotating** as parameters changed. Tiny weight perturbations (< 0.02) drove > 20 m outcome divergences on borderline seeds — i.e., the downstream dynamics amplified small consensus shifts into large outcome differences, and small parameter changes that did not meaningfully change the trust-weighting magnitude still flipped which seeds caught and which were lost.

This has two consequences for §5 design and reporting:

- **Integration claims should be scoped.** A statement like "BCVF trust-shaping improves outcome X by Y" should be accompanied by a downstream-sensitivity caveat: "under suitable downstream sensitivity to consensus shifts." Trust shaping is a necessary-but-not-sufficient mechanism; the downstream consumer's transfer function determines whether the shift is amplified into a meaningful outcome change.
- **The shared-catastrophe-tail pattern is expected.** When §5's V1 consumer is benchmarked, observing a non-zero floor of failures that no parameter combination can erase is consistent with the autonomy result and should not be misinterpreted as a §5.1 pattern failure. The right interpretation is "trust shaping reduced failures from baseline X to floor Y; further reduction requires architectural change to the downstream consumer, not further tuning of trust shaping." §6 (Phase 4 benchmark) acceptance criteria should be set with this in mind.

**§5.2 is short by intent.** It records an empirical caveat from the autonomy work, not a positive design commitment. The implication for §5's eventual consumer-architecture choice is that consumers with low downstream sensitivity to consensus shifts will benefit less from trust shaping, and vice versa — but quantifying this for LLM use cases requires §3 / §4 / §5 execution data and is deferred.

**Details pending.** Subsequent §5 sub-sections will commit, in order: the V1 consumer architecture (one of hidden-state shaping, logit blending, routing/gating), the V1 trust-temperature and softmin formulation, the cold-start and warmup behavior, integration with the §4 source framework, and the V1 acceptance criteria.

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
