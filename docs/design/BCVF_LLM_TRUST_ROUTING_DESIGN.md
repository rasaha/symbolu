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

### 2.6 Lemma 1 analogue — **pending**

### 2.6 Lemma 1 analogue — **pending**

### 2.7 Edge cases & numerical considerations — **pending**

### 2.8 Python equations parallel to `core.py` — **pending**

### 2.9 Acceptance criteria + test specification — **pending**

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
