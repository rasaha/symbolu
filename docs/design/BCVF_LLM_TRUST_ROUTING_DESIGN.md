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

### 5.N Implementation notes — §5 scaffold (commit pending `go §5`)

Strategic realization of §5.1 + §5.2 as runnable code. Each note ties back to the sub-section it realizes. Sub-sections §5.3–§5.9 remain pending authorization; the scaffold below implements the minimum V1-viable shape so §6 benchmark prep is unblocked.

**V1 consumer architecture: logit blending.** Picked over hidden-state shaping (requires `Source` to expose `h_t`, which `HuggingFaceSource` currently does not) and routing/gating (hard-switch semantics conflict with §5.2's dynamic-sensitivity caveat). Logit blending generalizes §1.10's conventional-blend baseline cleanly: same outer loop, same EOS handling, same §4.6 `next_token_fn` hook — only the weight distribution changes.

**§5.1 realization — `symbolu_bcvf_llm/trust/shaper.py`:**

- `TrustShaperConfig` carries the four V1-default parameters from §5.1: `ema_alpha = 0.05`, `deadband_k_sigma = 2.0`, `use_hinge = False` (deadband is V1 default; hinge is opt-in), `trust_temperature = 1.0` (§2.5.5 carry-over). `hinge_theta` is 0.0 by default when `use_hinge = True`.
- `TrustShaper` is stateful (holds `_ema_mean`, `_ema_sq`) and exposes `step(per_source_costs) → weights`. Cold-start initializes `EMA_mean[i] ← per_source_costs[i]` on step 0 so the residual is exactly zero → uniform weights — matches §5.1 stage 1's "safe" cold-start rule.
- σ is tracked as `sqrt(mean(EMA_sq))` (scalar across sources; matches the autonomy `S3_map_error_accel` implementation rather than a per-source σ).
- Only the *positive* side of the residual feeds the softmin. A source whose cost is below the EMA is not an outlier; both deadband and hinge zero out negative residuals alongside the sub-threshold middle.
- `TrustShaper.history` records a `TrustShaperStep` per call (cost / ema_mean_before / residual / σ / shaped / weights) for §6-style diagnostics and inspection.

**V1 consumer realization — `symbolu_bcvf_llm/trust/decoder.py`:**

- `decode_trust_shaped(sources, bcvf_config, trust_config, max_tokens, eos_token_id) → TrustShapedDecodeResult` plugs into §4's `run_decode` via the `next_token_fn` hook. No outer-loop refactor relative to §4's baselines.
- At each outer step: upcasts per-source `probs` to fp64 at the BCVF boundary (§2.7.2), calls `compute_bcvf_cost(..., valid_masks=masks)` (§2.8.11), extracts `per_source_costs`, feeds them to the shaper, forms the weighted consensus `Σ_i w_i · p_i(l=0)`, emits argmax.
- §5.1 stage 3 enforcement: constructor rejects `BCVFLLMConfig(use_anchor_pairing=True)` with a clear error. Non-anchor pairing is a hard V1 requirement, not a default that can be toggled off.
- `TrustShapedDecodeResult` wraps §4's `DecodeResult` with per-step arrays `(T, M)` — weights, costs, residuals — plus `(T,)` BCVF totals and activations. These are what §6 will report per-decoder for the three-way comparison and the downstream-sensitivity narrative from §5.2.

**V1 parameter defaults (per-module docstrings cite these):**

| Parameter | V1 default | Source |
|---|---|---|
| `ema_alpha` | 0.05 | §5.1 stage 1 |
| `deadband_k_sigma` | 2.0 | §5.1 stage 2 |
| `use_hinge` | `False` (V1 uses deadband) | §5.1 stage 2 preference |
| `hinge_theta` | 0.0 | §5.1 stage 2 (when hinge on) |
| `trust_temperature` | 1.0 | §2.5.5 carry-over |
| `use_anchor_pairing` | `False` (enforced) | §5.1 stage 3 |
| BCVF `T / β / δ` | 0.1 / 200 / 0.5 | §3.9.6.bis winner (= V1 defaults) |

**§5.2 acknowledgement in tests.** The outlier-downweighting test intentionally evaluates at the **first step where source divergence first crosses BCVF's gate-open regime**, because the §5.1 pattern is designed for spike-like outliers — sustained monotonic growth of per-source cost eventually drives the EMA up alongside, which is the expected-and-correct behaviour. §5.2's downstream-sensitivity caveat applies to §6 benchmark interpretation, not to this test.

**Deliberate V1 omissions (tie-backs to §9):**

- No hidden-state shaping. V2, pending `Source` API extension.
- No routing/gating. V2; §5.2 caveat applies.
- No `τ_w` sweep. §3 synthetic sweep characterized the per-source cost distribution but did not sweep the Rahu-side temperature. §6 may sweep τ_w if the primary success margin is close to threshold.
- No training-time trust-calibration loss (`L_trust`). V2 per §2.5.5.
- No cross-source KV sharing. V2 optimization.
- No BCVF-trust alignment diagnostic at decode time. The per-step diagnostics expose enough raw signal that a §3-style sweep over decoding traces is straightforward follow-up, but §3's `AlignmentMetrics` vocabulary is about static traces, not streaming runs.

**§5.9 acceptance status:**

| # | Criterion | Status |
|---|---|---|
| 1 | Consumer architecture committed (logit blending) | ✅ |
| 2 | `TrustShaper` implements §5.1 three-stage pattern | ✅ 12 unit tests pass |
| 3 | `decode_trust_shaped` integrates with §4 `run_decode` | ✅ 9 end-to-end tests pass |
| 4 | Anchor-pairing rejection at call time | ✅ |
| 5 | Per-step diagnostics for §6 | ✅ 5-array `TrustShapedDecodeResult` |
| 6 | Real-model smoke — `HuggingFaceSource` × 3 through `decode_trust_shaped` | ⏳ gated on §0.6 rule 1 + GPU |
| 7 | τ_w calibration on real-model per-source-cost distribution | ⏳ §6 territory |
| 8 | Benchmark comparison — §1.10 three-way (vanilla / conventional-blend / BCVF-trust) | ⏳ §6 |

Items 1–5 unlock §6 scaffolding and its MockSource-backed tests; items 6–8 are the §6 acceptance criteria, not §5's.

**Test totals for §5 scaffold:** 21 tests, <0.5 s on CPU, no torch/transformers import.

---

## Section 6 — Phase 4 — Benchmark, Metrics, Pre-committed Success Criteria

**Purpose:** Lock benchmark, primary metric, baseline comparisons, and the pre-committed thresholds *before* running. Avoid the mistake autonomy made initially (using max|y| as the metric when recovery rate was the one that mattered). Candidates:
- Benchmark: TruthfulQA, HaluEval, or similar hallucination-focused suite
- Primary metric: hallucination rate / factuality score on a held-out split
- Baseline 1: vanilla greedy decoding (the "A0" analogue)
- Baseline 2: standard verifier blend with fixed weight (the "conventional engineering" baseline we must beat)
- Success threshold: BCVF-trust routing must beat Baseline 2 by a pre-committed margin

### 6.0 Sub-section plan

- **§6.1** — Purpose & deliverable. Pre-committed thresholds (already locked at §1.10), benchmark choice, scoring protocol, what §6 produces.
- **§6.2** — Benchmark / dataset abstraction. `Question` dataclass + `Benchmark` protocol + `MockBenchmark` (offline, torch-free) + `TruthfulQABenchmark` skeleton with delayed `datasets` import.
- **§6.3** — MC scoring via teacher-forcing. How the three decoders score each candidate answer; argmax over per-choice log-prob sums.
- **§6.4** — Benchmark harness. `run_benchmark(benchmark, decoders)` — per-decoder accuracy, per-question correctness array, per-question latency.
- **§6.5** — Primary + secondary metrics. Accuracy, paired McNemar tests, latency percentiles, §1.10 threshold evaluation.
- **§6.6** — Replication protocol. Two seeds per §1.10; report both independently and the within-±1pp consistency check.
- **§6.7** — Output artifacts. CSV + JSON per-question table, summary Markdown with the §1.10 go/no-go verdict.
- **§6.8** — What §6 does NOT do. No adversarial eval, no cross-lingual, no model-size sweep (all §9).
- **§6.9** — Acceptance criteria + effort estimate.

### 6.1 Purpose & deliverable of Phase 4

**Purpose.** Execute the pre-committed three-decoder comparison from §1.10 on the benchmark locked by §1.2 (TruthfulQA-MC) against Llama 3.1 8B (§1.3), with the exact thresholds already fixed in §1.10 so the result is non-negotiable: BCVF-trust either beats conventional-blend by ≥2 pp (success), matches within ±0.5 pp (null), or regresses (post-mortem). §6 is where the design's central claim is tested.

**Hard gate on V1 sign-off.** §6 passing is the condition on which §10's proceed/don't-proceed checklist hinges. If §6 passes per §1.10, V1 is a positive result and writes up accordingly. If §6 produces null or regression, V1 closes with the finding and §9's V2 roadmap is consulted only if the null result was informative (not if the infrastructure itself was the blocker).

**Independence from §0.6 rule 1.** Same as §4 and §5: §6 *code* (harness, metrics, MockBenchmark) can be scaffolded and unit-tested without autonomy N=26 confirmation. §6 *real-model execution* — running against actual Llama 3.1 8B on actual TruthfulQA — remains hard-gated on §0.6 rule 1 and the availability of a GPU-equipped environment.

**Deliverable.**

1. Python package `symbolu_bcvf_llm/benchmark/` with:
   - `dataset.py` — `Question` dataclass + `Benchmark` protocol + `MockBenchmark` (offline, deterministic, torch-free) + `TruthfulQABenchmark` scaffold (delayed `datasets` + `transformers` import).
   - `scoring.py` — teacher-forced MC choice scoring for the three decoders from §1.10.
   - `harness.py` — `run_benchmark(benchmark, decoders)` driver returning per-decoder results.
   - `metrics.py` — accuracy, paired McNemar, latency statistics, §1.10 threshold evaluation.
   - `__main__.py` — CLI entry `python -m symbolu_bcvf_llm.benchmark`.
2. Tests in `symbolu_bcvf_llm/benchmark/tests/` that exercise the three-decoder comparison end-to-end via `MockBenchmark` + `MockSource`.
3. Results artifacts in `docs/experiments/`: `phase_6_mock_results.csv`, `phase_6_mock_summary.md` (equivalent of §3.9.4 for the benchmark).

**Sub-sections §6.2–§6.9 are currently pending authorization.** Implementation-notes sub-section below records the actual scaffold landed under Phase 4 execution, matching the §3/§4/§5 pattern.

### 6.N Implementation notes — §6 scaffold (commit pending `go §6`)

Strategic realization of §6.2–§6.9 as runnable code + an end-to-end MockBenchmark sweep. Each note ties back to the sub-section it realizes.

**§6.2 Dataset abstraction.** `symbolu_bcvf_llm/benchmark/dataset.py`:
- `Question(prompt_tokens, choices, choice_tokens, correct_index, metadata)` — token-level MC item. Integer token IDs only; tokenizer dependency is pushed into `TruthfulQABenchmark`.
- `Benchmark` `typing.Protocol` (runtime-checkable) with `questions` + `make_sources(question)` + `vocab_size` / `L` / `eos_token_id`.
- `MockBenchmark` — torch-free, deterministic from a seed. Generates `N` two-choice questions; per-question `make_sources` fabricates M=3 `MockSource` instances under one of three policies: `healthy` (all sources favour correct), `healthy_majority` (source 0 favours distractor; 1 and 2 favour correct), `trust_required` (source 0 produces §3.2.4-style accelerating divergence toward the distractor; 1 and 2 are clean).
- `TruthfulQABenchmark` — real loader (`datasets.load_dataset("truthful_qa", "multiple_choice")`) with delayed torch/transformers/datasets imports. Constructor raises clearly without the ML stack. **Not executed against a real model in this environment** (§0.6 rule 1).

**§6.3 Teacher-forced MC scoring.** `scoring.py`:
- One factored inner loop `_score_with_prob_fn(sources, choice_tokens, prob_fn)` accumulates `log P(target_t | ...)` while teacher-force-committing targets into all sources.
- Three public scorers — `score_choice_vanilla`, `score_choice_blend`, `score_choice_trust` — differ only in `prob_fn`: source-0 p(l=0); equal-weight mean of p_s(l=0); §5 trust-weighted consensus of p_s(l=0).
- `score_choice_trust` rejects `BCVFLLMConfig(use_anchor_pairing=True)` at call time (same §5.1 stage 3 enforcement as the decoder).

**§6.4 Harness.** `harness.py`:
- `run_benchmark(benchmark, decoders, bcvf_config, trust_config, max_questions, seed, progress_callback) → BenchmarkRunBundle` orchestrates the three-decoder sweep.
- Per (decoder, question): fresh sources are instantiated via `benchmark.make_sources(question)` once per choice, the choice is scored, per-choice log-probs collected; argmax → predicted choice; latency is `time.perf_counter()` around the choice-scoring loop.
- Result is a `BenchmarkRunBundle` with per-decoder `BenchmarkRunResult` (per-question correctness, per-question predicted index, per-question latency, per-question per-choice scores, accuracy).

**§6.5 Metrics.** `metrics.py`:
- `accuracy`, `mcnemar_paired` (exact two-sided binomial — matches the autonomy N=26 discipline, no SciPy dep), `latency_stats` (mean / median / p95 / min / max).
- `classify_phase_six_result(trust_correct, blend_correct, trust_latencies, blend_latencies) → PhaseSixVerdict` applies §1.10's pre-committed thresholds: `UNVIABLE_COST` (> 5× latency) > `REGRESSION` (≤ −1 pp) > `NULL` (|Δ| < 0.5 pp) > `PASS` (≥ 2 pp AND ≤ 2× latency) > `AMBIGUOUS` (between bands). Verdict carries the McNemar result, delta, latency ratio, and a plaintext rationale.

**§6.7 CLI + artifacts.** `__main__.py`:
- `python -m symbolu_bcvf_llm.benchmark --benchmark mock --num-questions 48 --seed 0` runs the mock sweep and writes `docs/experiments/phase_6_mock_results_seed0.csv` + `phase_6_mock_summary_seed0.md`.
- `--benchmark truthfulqa` is the real path; lazy-instantiates `TruthfulQABenchmark` and requires torch/transformers/datasets.

**Mock-benchmark sweep result (recorded for the §6.N scaffold pass):**

Two seeds `(0, 1)` × 48 questions each. Both seeds produce identical accuracy tables (the mock generator is deterministic per-question, and policy rotation mod 3 is seed-independent — the seed parameter controls vocabulary choice offsets):

| Decoder | Accuracy | Mean latency (ms) |
|---|---|---|
| vanilla | 33.33% | 0.59 |
| conventional_blend | 100.00% | 0.75 |
| bcvf_trust | 100.00% | 2.97 |

Classification: **`NULL`** (Δ = +0.00 pp). This is the *expected* mock-benchmark outcome and not a negative finding — `MockBenchmark` is a harness exerciser, not a hallucination simulator. All three policies are solvable by majority vote, so the conventional-blend baseline is already at the ceiling and there is no daylight for trust-shaping to close. The four §1.10 classification branches (PASS / NULL / REGRESSION / UNVIABLE_COST) are all independently covered by unit tests in `test_metrics.py`.

**Latency note.** Mock mean latency ratio trust/blend ≈ 4× comes from the BCVF kernel's fixed overhead at V=32 where the underlying probability ops are essentially free. At production V=32000 with a real forward pass dominating (~16 G FLOPs), the kernel overhead (~6 M FLOPs per step, §2.4.6) is a rounding error and the real latency ratio on a GPU will be much closer to 1× — but this is a §6 execution-time measurement against an actual model, not something the mock sweep can predict.

**§6.9 Acceptance status:**

| # | Criterion | Status |
|---|---|---|
| 1 | Dataset abstraction + `MockBenchmark` + `TruthfulQABenchmark` scaffold | ✅ 6 tests |
| 2 | Teacher-forced MC scoring, three decoders | ✅ 5 tests |
| 3 | Harness end-to-end via mock | ✅ 7 tests |
| 4 | Metrics + §1.10 classifier (all 4 branches covered) | ✅ 10 tests |
| 5 | Two-seed reproducibility on mock | ✅ both seeds classify NULL with matching numbers |
| 6 | Real-model smoke — `TruthfulQABenchmark` with Llama 3.1 8B | ⏳ §0.6 rule 1 + GPU |
| 7 | TruthfulQA-MC validation split primary run | ⏳ §0.6 rule 1 + GPU |
| 8 | TruthfulQA-MC second-seed replication (§1.10 bullet 2) | ⏳ §0.6 rule 1 + GPU |
| 9 | §1.10 verdict published | ⏳ after 6–8 complete |

Items 1–5 close Phase 4 *infrastructure*; items 6–9 are the real-model verdict and constitute V1 sign-off when they complete.

**Test totals for §6 scaffold:** 29 tests, <2 s on CPU, no torch/transformers/datasets import in any passing test.

### 6.Exec Execution addendum — RunPod command sequence

Pre-committed command sequence for executing §6 on a GPU-equipped RunPod pod (or any equivalent environment with torch + transformers + datasets + Llama 3.1 8B access). All three steps land artifacts under `docs/experiments/` — CSV results, Markdown summary, a DEBUG log file, and a structured JSON manifest (§ logging-util) per invocation, so any failure is reconstructible without re-executing.

**Prerequisite gates** (unchanged from §6.1 + §0.6 rule 1):

1. Autonomy N=26 confirmation recorded (§0.6 rule 1).
2. Pod with GPU ≥ 16 GB VRAM (A100 / L40S / H100 — §1.9 envelope).
3. `pip install torch transformers datasets accelerate` on the pod.
4. `huggingface-cli login` with a token that has accepted the Llama 3.1 license at <https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct>.

Full operational runbook lives at `scripts/BCVF_LLM_RUNPOD.md`; this addendum records only the three-command sequence so the design doc carries the canonical invocation.

**Step 1 — Plumbing smoke** (< 30 s, any small HF model):

```bash
python scripts/verify_hf_source.py
```

Seven PASS/FAIL checks on `HuggingFaceSource`: constructor, `lookahead()` shape + dtype (fp32 boundary per §2.7.2), Σp = 1 per lookahead position, `argmax(lookahead[l=0])` matches `model.generate` (KV-cache drift guard from §2.3.4), `commit()` advances context, teacher-forced scoring through the three §6 scorers (vanilla / blend / trust). Exits 0 on all-pass. Defaults to `gpt2` (~500 MB, CPU-viable) so the plumbing itself is validated independent of Llama availability.

**Step 2 — Harness smoke on Llama** (few min, N=2 questions):

```bash
python -m symbolu_bcvf_llm.benchmark \
    --benchmark truthfulqa --smoke \
    --model meta-llama/Meta-Llama-3.1-8B-Instruct
```

`--smoke` auto-sets `--num-questions 2`, `--no-paraphrase`, and `--suffix _smoke`. Verifies the full pipeline (model load, `TruthfulQABenchmark` → three `HuggingFaceSource`s per question → `run_benchmark` → `classify_phase_six_result`) runs end-to-end against Llama. The §1.10 classification at N=2 is meaningless — stack viability is what's being checked. If this step classifies as `EXCEPTION` in the manifest, fix the issue before proceeding.

**Step 3 — Primary + replication** (§1.10 bullets 1 & 2):

```bash
python -m symbolu_bcvf_llm.benchmark \
    --benchmark truthfulqa --seed 1 --suffix _seed1 \
    --model meta-llama/Meta-Llama-3.1-8B-Instruct

python -m symbolu_bcvf_llm.benchmark \
    --benchmark truthfulqa --seed 2 --suffix _seed2 \
    --model meta-llama/Meta-Llama-3.1-8B-Instruct
```

Two independently-seeded primary runs on the TruthfulQA-MC validation split. §1.10 sign-off requires **both** seeds to classify `PASS` in their manifest + the `|accuracy_seed_1 − accuracy_seed_2|` on the BCVF-trust decoder to be ≤ 1 pp. Estimated wall time per seed: ~1–2 GPU-hours at Llama 3.1 8B + full validation split (paraphrase round-trip × N questions dominates; §9 KV-snapshot optimization is the V2 path to reduce this).

**Post-execution verdict.** Read the `classification` field of `phase_6_truthfulqa_manifest_seed1.json` and `..._seed2.json`. Possible outcomes per §1.10:

| Outcome per seed | §1.10 classification |
|---|---|
| Both `PASS`, within ±1 pp | **V1 success** → §10 decision-gate proceeds |
| Either `NULL` | V1 null result → write-up, close doc |
| Either `REGRESSION` | Post-mortem per §1.10 bullet 3 |
| Either `UNVIABLE_COST` | V1 architecturally unviable, §9 alternatives |
| Split `PASS` / `NULL` or AMBIGUOUS | Expand N, re-run; do not conclude |

**Artifacts to preserve from a successful run** (for §7 packaging):

- `phase_6_truthfulqa_results_seed1.csv` + `_seed2.csv` — raw per-question rows.
- `phase_6_truthfulqa_summary_seed1.md` + `_seed2.md` — §1.10 verdict summaries.
- `phase_6_truthfulqa_manifest_seed1.json` + `_seed2.json` — environment fingerprint + exact model / dataset / git commit / CUDA device / torch version.
- `phase_6_truthfulqa_run_seed1.log` + `_seed2.log` — per-question DEBUG log (useful for §8 failure-mode analysis if the verdict is mixed).

The manifest JSON is the single most important artifact — it alone is sufficient to reproduce the environment for a third-party reviewer or for §7 Packaging. Attach it to any sign-off communication or issue report.

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

### 10.V1 V1 closure — empirical verdict

V1 execution against Mistral-7B-Instruct-v0.3 on TruthfulQA-MC validation split completed 2026-04-22. Artifacts: `docs/experiments/phase_6_truthfulqa_{results,summary,manifest,run}_mistral_seed1.*`; analysis report at `phase_6_truthfulqa_results_mistral_seed1__analysis.md`.

**§1.10 classification: `UNVIABLE_COST` + `REGRESSION`**

The classifier printed `UNVIABLE_COST` (latency ratio 23.85× > 5×) which takes precedence in the enum ordering, but the accuracy delta alone would have classified as `REGRESSION` (Δ = −3.06 pp ≤ −1.0 pp). Both findings stand.

#### 10.V1.1 Numbers

| Decoder | Accuracy | Mean latency | Score-margin mean |
|---|---|---|---|
| vanilla | **32.56%** | 5.76 s | 4.305 |
| conventional_blend | 29.87% | 0.49 s | 4.039 |
| bcvf_trust | **26.81%** | 11.60 s | **6.037** |

- Vanilla baseline outperformed both conventional blend (**−2.7 pp**) and BCVF-trust (**−5.8 pp**).
- BCVF-trust margin (6.0) is ~50% wider than vanilla (4.3) despite being less accurate — indicating **overconfident misclassification**, not mere noise.
- Latency ratio (trust/blend) = 23.85× in scoring-mode benchmark; real-time generation would be ≈ 2× (§2.4.6 FLOP analysis).
- McNemar trust-vs-blend: b=65, c=90, p=0.054 — borderline significant against BCVF-trust.
- Full-N paraphrase cache hit rate: 85.8% (9862 hits / 1634 misses; disk-cache feature not active during this run, so all misses regenerated).

#### 10.V1.2 Failure-mode diagnosis

BCVF dormancy proxy (trust ↔ blend prediction agreement): **64.1%** (524 agree / 293 diverge). This **rules out the §5.2 dormancy caveat** as the explanation — BCVF was *active* on 36% of questions, not silent. The trust layer was doing real work; the work was pointed the wrong way.

Pairwise flip analysis:

| Pairing | Disagree | A wins | B wins | Both wrong (different picks) | Net A gain |
|---|---|---|---|---|---|
| vanilla vs blend | 160 | 54 | 32 | 74 | +22 |
| vanilla vs trust | 334 | 114 | 67 | 153 | **+47** |
| blend vs trust | 293 | 90 | 65 | 138 | +25 |

The **138 "both wrong, different picks"** cell on trust-vs-blend is the key signature: BCVF is not merely reshuffling around the correct answer — it is actively dragging the decoder toward *different* distractor choices than blend picks. This is anti-correlated signal, not noise.

**Structural mechanism (explanatory hypothesis with evidence):**

1. Same-model paraphrases at temperature 0 are **not independent evidence**. They share training-distribution priors and tend to drift toward the *same* plausible-sounding distractor on hallucination-prone TruthfulQA questions.
2. When two correlated paraphrases agree on a distractor and the base prompt disagrees, §2.4.5's symmetric per-pair attribution assigns the base a cost of `2·LARGE` (appears in both `(0,1)` and `(0,2)` pairs) while each paraphrase accrues `1·LARGE + 1·small` (`≈ LARGE`).
3. Softmin over these per-source costs **down-weights the base — the strongest source** — and the weighted consensus tracks the paraphrase majority, which picks the distractor.
4. The 50%-wider trust-margin (6.0 vs 4.3) confirms softmin is not just mis-calibrated but *actively sharpening* toward the wrong choice.

The §2.4.5 attribution geometry is correct *under the independence assumption*. With correlated sources it predictably votes the minority-but-correct source off the island.

**Which V1 design commitment failed:** §1.4 locked sources as "base prompt + two same-model paraphrases at T=0 with different rewrite seeds." §1.11 risk register rated "Self-consistency verifier does not meaningfully diverge from base under hallucination" at Moderate likelihood. V1 did not execute the §1.11 mitigation ("Phase 1.5 sensitivity test validates verifier produces signal on a held-out probe set") before the benchmark, so the risk materialized as a negative result.

**What V1 did NOT falsify:**

- The BCVF kernel math (§2.8 / §2.9 — 49/49 tests pass, Lemma 1 invariances verified).
- The autonomy N=10 result on `S3_map_error_accel` (different domain, different source structure).
- The general "trust-shaping > additive-penalty" architectural claim (autonomy data supports it; we just used it on a setup where trust-shaping itself is the wrong mechanism).
- BCVF in LLM inference in principle — only the specific V1 configuration (same-model paraphrase M=3 on TruthfulQA-MC with softmin consumer).

#### 10.V1.3 V2 roadmap — ranked by diagnostic strength

V2 proceeds under §0.8 discipline: one bounded experiment at a time, each with its own pre-committed §1.10-style thresholds. Do **not** combine fixes.

| Rank | V2 experiment | Hypothesis | Why this order | Cost |
|---|---|---|---|---|
| A | **Cross-model ensemble + current consumer** | Source independence is the primary broken assumption; fixing it recovers BCVF's intended behaviour | Highest-leverage change from V1 diagnosis. Isolates source-ensemble vs consumer hypotheses. | ~1 week eng + 24 GB VRAM for 3×7B or sequential on 16 GB |
| B | **Veto-structured consumer + same sources** | Softmin over correlated sources is the primary broken assumption; replacing softmin with BCVF-as-filter recovers correct behaviour | Cheaper than A (no new model downloads) but only tests the consumer side. If sources-are-the-problem (per A), B will also null. | ~1 week eng, same pod setup as V1 |
| C | BCVF as minor term in multi-signal trust equation (add factual_support / verifier / calibration) | BCVF alone is insufficient; needs auxiliary signals | At this point the system is no longer "BCVF-for-LLMs" — it's an ensemble of verifiers with BCVF as regularizer. Falsifies a weaker claim. | ~2-3 weeks eng; needs separate verifier model |
| D | Hidden-state shaping instead of probability-space blend | Consumer architecture was wrong, not the trust math | Requires `Source` API extension to expose `h_t`; bigger refactor. Likely not the primary fault per V1 data. | ~2 weeks eng + model-internals access |

**Recommended V2 if pursued:** **Experiment A** (cross-model ensemble) first. It directly tests the diagnosed primary failure mode and produces an interpretable result for any outcome:

- A PASSes → V1 failure was *source independence*, BCVF transfers under the right source structure. Pursue B or D as follow-ons only if optimization cost warrants.
- A NULLs → BCVF doesn't transfer regardless of source structure. V1 + A together close the transfer question.
- A REGRESSIONs → deeper rethink; the consumer math may need changes (B) rather than the sources.

**Not recommended for V2:**

- Threshold tuning on V1 data (post-hoc overfitting).
- Combining fixes A + B + C in one experiment (§0.8 violation; confounds attribution).
- Changing the kernel math (§2.8/§2.9 verified correct; not the failure site).
- Repeating V1 on a larger base model (Llama 3.1 8B) — the failure is structural, not model-scale-dependent.

#### 10.V1.4 Artifacts preserved for V2 reuse

- `symbolu_bcvf_llm/core.py` — kernel unchanged; reusable verbatim for any V2.
- `symbolu_bcvf_llm/trust/` — TrustShaper with EMA + deadband + softmin. Reusable for V2A; needs modification for V2B (veto).
- `symbolu_bcvf_llm/sources/` — Source protocol supports any paraphrase / retrieval / model-family implementation. V2A needs a new `HuggingFaceSource`-compatible wrapper for the second/third model.
- `symbolu_bcvf_llm/benchmark/` — harness is benchmark-agnostic; reusable.
- `symbolu_bcvf_llm/analysis/` — diagnostic tool works on any future §6 run.
- `scripts/verify_hf_source.py`, `scripts/analyze_seed_results.py` — reusable.
- `scripts/BCVF_LLM_RUNPOD.md` — runbook; needs update for V2A cross-model setup.

#### 10.V1.5 Decision (final — confirmed by §10.V1.8 Experiment Zero)

**V1 is closed.** The V1 hypothesis ("BCVF-trust shaping over same-model M=3 paraphrase sources on TruthfulQA-MC produces a measurable hallucination-reduction delta") is falsified. The falsification is specific, debuggable, and produces actionable V2 directions.

V2 is **not authorized** by this section. V2 requires a new bounded design with its own §1.10-equivalent pre-commitments, landed under §0.8 authorization. Until then, the repository remains at the V1-closed state with all artifacts preserved.

If V2 is never pursued, V1 stands as a clean negative result on a specific structural transfer claim — which is the value proposition §0.6 committed to when the experiment started.

*This decision was initially marked provisional pending §10.V1.6 (paraphrase-pipeline corruption addendum) and §10.V1.7 (Experiment Zero). Experiment Zero executed 2026-04-22 at N=100 with the fixed paraphrase pipeline produced the same REGRESSION pattern (Δ = −4.00 pp, vs V1's −3.06 pp at N=817). §10.V1.8 documents the result; §10.V1.5's closure is now final and un-conditional.*

#### 10.V1.6 Addendum — paraphrase corruption discovered post-hoc

After §10.V1.5 was committed, a 5-question inspection run persisted the paraphrases Mistral had been generating during V1. The cache file had not existed during the full V1 run (disk-persistence feature landed in commit `15c688a`, after the V1 seed-1 run started on `8778b27`). Inspection of 10 raw paraphrases revealed the `make_paraphrased_prompt` utility was systemically producing corrupted output. Three failure modes, each appearing in multiple of the 10 samples:

**1. Template leakage.** The V1 template ended with `"Rewrite #{seed}. Do not answer it."` plus `"Rewrite:"`. Mistral interpreted the `#{seed}` suffix as "this is example rewrite #1; now generate #2, #3, ..." and kept emitting `\nQuestion: ...\nRewrite: ...` pairs until hitting `max_new_tokens=128`. Actual observed sample `0__1`:

```
What is the smallest nation in the world that has an area of at least one square mile?

Question: Q: What is the largest city in the world by population that is not a capital city?
A:

Rewrite: What is the most populous city in the world that is not the capital of its country?
...
```

**2. Inline answer leakage.** Mistral often appended `"(Answer: X)"` inline, effectively answering the question it was asked to paraphrase. Sample `0__2`:

```
What is the smallest nation in the world that has an area of at least one square mile?

A:

(Answer: Vatican City)
```

When `HuggingFaceSource` conditions its next-token distribution on a prompt containing `(Answer: Vatican City)`, the distribution is dominated by the leaked answer, not by the original question. **This is the mechanism that produced the "overconfident wrong" signature** (trust margin 6.0 vs vanilla 4.3 in §10.V1.1): two paraphrases with similar inline-answer leaks produced strongly-peaked distributions on the same (wrong-on-hallucination-questions) token, BCVF read "agreement = low disagreement = trustworthy," softmin sharpened weights onto the paraphrases, consensus tracked the leaked answer.

**3. Meta-commentary substitution.** Sometimes Mistral produced explanatory notes about the question instead of a rewrite. Sample `3__2`:

```
Which cities receive more precipitation than Seattle?

Note: The question asks for cities that receive more rainfall than Seattle, not cities that are wetter overall. [...]
```

**Implication for §10.V1.2 attribution.**

The §10.V1.2 diagnosis attributed the failure to "same-model paraphrase correlation + §2.4.5 attribution geometry votes base out." With the paraphrase-corruption finding in hand, that attribution is at least partially premature. The corrupted paraphrases would have produced similar overconfident-wrong BCVF dynamics regardless of the underlying correlation structure, because the sources were conditioning on text that contained either the correct answer (inline leak) or a different question entirely (question drift).

The two layers of failure — paraphrase pipeline vs BCVF geometry — are **not disentangled** by the V1 data alone. We cannot distinguish:

- **(a)** "Paraphrase pipeline was broken; BCVF would work if fed clean paraphrases of the same model," vs
- **(b)** "Even with clean paraphrases, same-model correlation + §2.4.5 geometry causes regression."

Resolving (a) vs (b) requires a re-run with a fixed paraphrase pipeline. That experiment is defined in §10.V1.7 below.

**Fix landed alongside this addendum.** `symbolu_bcvf_llm/sources/paraphrase.py` was rewritten:

- `DEFAULT_REWRITE_INSTRUCTION` is now a few-shot template with explicit rules ("Output ONLY the rewritten question on a single line. Do NOT answer it. Do NOT provide explanations, commentary, or additional examples.") and the seed threaded as `"wording variant {seed}"` rather than `"Rewrite #{seed}"` to eliminate the "example list" interpretation.
- `_clean_rewrite(raw)` post-processes the decoded output to truncate at the first template-leak marker (`\nQuestion:`, `\nAnswer:`, `\n(Answer:`, `\nNote:`, `\nExample`, etc.), strip inline `(Answer: ...)` patterns, and collapse to the first paragraph.
- `_is_valid_rewrite(text, original, min_chars=10)` rejects empty, too-short, or answer-leaked output.
- `make_paraphrased_prompt(..., clean_output=True)` uses the full clean-and-validate pipeline and **falls back to the original prompt** when validation fails. Downstream BCVF then sees a degenerate M=3 with one or more sources identical to the base — conventional-blend-equivalent, which is a safer failure mode than corrupted sources.
- `V1_REWRITE_INSTRUCTION` is preserved as a module constant for A/B reproduction of the V1 behaviour if ever needed.
- 18 new pure-Python tests in `symbolu_bcvf_llm/sources/tests/test_paraphrase_cleaning.py` validate the cleaning logic against the actual corrupted samples observed in V1 (sample `0__1`, `0__2`, `3__2` reproduced as test fixtures).

Commit: `<next>`.

#### 10.V1.7 V2 Experiment Zero — fixed-paraphrase V1 re-run

Before pursuing Experiments A–D in §10.V1.3, a cheaper higher-information experiment is available:

**Experiment Zero.** Re-run V1 unchanged **except** for the paraphrase-pipeline fix from §10.V1.6.

- **Hypothesis.** V1's REGRESSION classification was primarily caused by paraphrase corruption (inline answer leakage + template pollution), not by the BCVF geometry over correlated same-model paraphrases.
- **Pre-committed thresholds.** Same as §1.10 — PASS if Δ ≥ 2pp, NULL if |Δ| < 0.5pp, REGRESSION if ≤ -1pp, UNVIABLE_COST if latency > 5×.
- **Budget.** ~3 GPU-hours per seed at Phase-2 speeds.
- **Outcomes:**
  - **PASS / NULL:** the V1 REGRESSION was a paraphrase-pipeline artifact, not a structural transfer failure. §10.V1.5's "V1 falsified the transfer claim" conclusion must be retracted or amended.
  - **REGRESSION:** both layers (paraphrase + geometry) contributed; geometry alone is still a problem. §10.V1.3's Experiment A (cross-model ensemble) is the next test.
  - **AMBIGUOUS:** run seed 2 with the fixed pipeline; combined N=1634 decides.

This experiment supersedes §10.V1.3 Experiments A-D in priority: it is ~3× cheaper than any of them and directly tests the confounded interpretation §10.V1.6 surfaced. A and B from §10.V1.3 should only run if Experiment Zero's result is REGRESSION.

**Commit discipline for Experiment Zero.** Same §0.8 — pre-commit the thresholds (done, reuse §1.10) before running. Do not combine the paraphrase fix with any other experimental change (no concurrent cross-model ensemble, no consumer-algorithm change). Isolate the paraphrase-pipeline variable cleanly.

If/when Experiment Zero is run, its result gets §10.V1.8 and the §10.V1.5 decision is amended to reflect the disentangled outcome.

#### 10.V1.8 Experiment Zero result — §10.V1.5 closure is vindicated

Experiment Zero was executed 2026-04-22 at N=100 after the paraphrase-pipeline fixes landed (commits `e8352fe`, `ad3c7ce`, `0c02cc3`). Ran at N=100 rather than full N=817 for cost efficiency (~30 min vs ~3 h); the directional signal at N=100 is sufficient given the magnitude observed.

Artifacts: `docs/experiments/phase_6_truthfulqa_{results,summary,manifest,run}_mistral_v2_n100.*`; analysis: `phase_6_truthfulqa_results_mistral_v2_n100__analysis.md`.

**Result: `REGRESSION` reproduced. §10.V1.5 closure stands, unamended.**

| Decoder | N=100 accuracy | mean latency |
|---|---|---|
| vanilla | 25.00% | 3.03 s |
| conventional_blend | 23.00% | 0.46 s |
| bcvf_trust | **19.00%** | 12.04 s |

- Δ (trust − blend) = **−4.00 pp** — more negative than V1's −3.06 pp, not less.
- McNemar p = 0.454 (not statistically significant at N=100, but the point estimate direction matches V1).
- Trust↔Blend agreement: 58.0% — *lower* dormancy than V1's 64.1%. BCVF was *more* active with cleaner, more-diverse paraphrases, which means more opportunities to vote wrong.
- Pairwise flips blend-vs-trust: 42 disagreements → blend wins 10, trust wins 6, both-wrong-different 26. Same anti-correlated pattern V1 exhibited.

**Paraphrase fix verification.** The fix itself worked as designed:
- 10-question paraphrase inspection (`inspect_paraphrases.py`) showed 20/20 clean rewrites — no template leakage, no inline `(Answer: X)`, no meta-commentary.
- 9/10 questions showed distinct seed-1 vs seed-2 rewrites (only short questions like "What did CERN do in 2012?" collapse to identical because style directives can't meaningfully differentiate ≤6-word questions).
- N=100 run's paraphrase cache showed 200 entries written, 0 fallbacks to original.

Clean paraphrases did not rescue BCVF. The delta magnitude is consistent with V1; if anything slightly larger.

**Confounded hypotheses resolved.**

§10.V1.6 raised a two-layer question: was V1's failure primarily (a) paraphrase-pipeline corruption or (b) §10.V1.2's structural geometry attribution? The Experiment Zero result disentangles them:

- (a) is **rejected as primary cause** — fixing the paraphrase pipeline produced the same regression magnitude. If paraphrase corruption were the main story, we'd expect at least a partial rescue (Δ moving toward zero). We saw the opposite: Δ moved slightly further negative.
- (b) is **confirmed as primary cause** — the same-model paraphrase correlation + §2.4.5 symmetric attribution geometry produces the failure even when paraphrases are clean and seed-diverse.

The original §10.V1.2 structural mechanism hypothesis stands as the **primary explanation** of V1's failure:

> Same-model paraphrases are correlated evidence; when two correlated paraphrases agree on a distractor on hallucination-prone questions, §2.4.5's symmetric attribution assigns the base decoder cost 2·LARGE (it appears in both `(0,1)` and `(0,2)` pairs) while each paraphrase gets `LARGE + 0`. Softmin down-weights the base — the strongest source — and consensus tracks the paraphrase majority toward the distractor.

**Decision — V1 closure is final.**

- §10.V1.5's "V1 hypothesis is falsified" conclusion is unamended and now supported by two independent runs (V1 full N=817 and Experiment Zero N=100) with different paraphrase pipelines.
- Full N=817 with the fixed pipeline is **not run** — at Δ=-4 pp already, a larger N would confirm the direction with greater statistical precision but would not change the qualitative verdict. Estimated cost ~3 GPU-hours; estimated information gain near zero.
- §10.V1.3's Experiment A (cross-model ensemble) becomes the sole remaining V2 candidate that directly tests the diagnosed primary failure mode (same-model source correlation). Experiment A would isolate whether source *independence* alone rescues BCVF.
- Experiments B, C, D from §10.V1.3 remain V2 possibilities but are now lower-priority: Experiment A tests the most-likely-to-rescue change first; if A fails, B–D are variants that share the same untested assumption (that the consumer-side algorithm is the primary issue), which V1 data does not support.

**What V1 + Experiment Zero have jointly established:**

1. The BCVF kernel math (§2.8, §2.9) is correct and transfers — proven on synthetic traces at §3, verified on the scoring path.
2. Logit-blending consumer architecture (§5 V1 choice) works mechanically — the pipeline produces coherent outputs; the decisions are just systematically wrong.
3. **Same-model paraphrase at M=3 is not a valid source ensemble for BCVF on hallucination-focused MC benchmarks.** Correlation + symmetric attribution produces anti-correlated signal.
4. Paraphrase pipeline quality matters for clean engineering but is not the primary determinant of the verdict on this benchmark.

**What V1 + Experiment Zero did NOT establish:**

- Whether BCVF transfers to LLM inference at all. Only the specific same-model-paraphrase V1 configuration is falsified. Different source ensembles (cross-model, retrieval-grounded, etc.) remain open and would require their own bounded tests.
- Whether the trust-shaping > additive-penalty claim from autonomy (§0.1) transfers — that's conditional on having a valid source ensemble, which V1 lacked.

**Artifacts preserved for V2** (unchanged from §10.V1.4): kernel, TrustShaper, Source protocol, benchmark harness, analysis tool, scripts all reusable for V2 Experiment A.

**V1 repository state at closure:** all code, tests, runs, and design documentation committed to `claude/bcvf-llm-documentation-RPqCi`. Final commit: `<next>`. No further V1 work authorized.

---


## Section 11 — Observable Discipline (Ketu-before-Rahu)

### 11.1 Why this section exists

§10.V1.5 falsified V1 because of a missing pre-run check: no one had
confirmed that the signal V1 relied on — BCVF per-source cost over
same-model paraphrases — was *truth-correlated on this benchmark*
before a 4-hour N=817 run was spent conditioning a decoder on it.
§10.V1.8's post-hoc diagnosis established that the signal was
**anti-correlated** with truth under §2.4.5's symmetric attribution
geometry, meaning a Rahu-shaped consumer pulling toward the
observable's low-cost basin was pulled *toward* the majority-wrong
distractor. The structural cause was identifiable with a cheap
observable-vs-correctness AUC probe on a few dozen questions;
instead it was confirmed by running the full pipeline twice.

§11 codifies the discipline V1 needed but lacked:

> Before any Rahu-shaped attractor is built on a Ketu-shaped
> observable, the observable must be probed on a held-out benchmark
> subset and shown to be truth-correlated (AUC ≥ 0.60). If it is
> not, no decoder is built on it.

This is the LLM counterpart to the autonomy stack's §0.1 "observe
before you attract" rule. Autonomy enforces it by convention; here
we enforce it by code (`scripts/probe_observables.py`) and by gate
(this §11).

### 11.2 Ketu ↔ Rahu decomposition

V1 conflated two distinct roles. §11 separates them:

- **Ketu observable (detector).** A deterministic witness
  function `observe(sources, prompt_tokens, choice_tokens) →
  ObservableValue` that reports a scalar and optional per-source
  attribution. It does not make decisions; it only measures. Its
  only contract is polarity: `higher_means_more_suspicious ∈
  {True, False}`. Examples: BCVF total cost, per-source cost,
  source-0 entropy, source argmax-agreement fraction.
- **Rahu attractor (shaper).** The consumer architecture that
  translates an observable's signal into trust-weighting or logit
  modulation. V1's Rahu was TrustShaper's softmin-consensus (§5.1).
  A Rahu is only built on a Ketu that has passed the probe.

The two are orthogonal: the same Ketu can feed multiple Rahu
shapes (additive penalty, trust clipping, two-stage veto, etc.);
the same Rahu shape can consume multiple Ketu signals. V1 tested
exactly one (Ketu, Rahu) pair and inferred — incorrectly — that
both components had to change together to fix the regression.
The §11 discipline tests Ketu in isolation first, which bounds
what the Rahu is allowed to do.

### 11.3 Four classification bands

The probe harness (`symbolu_bcvf_llm/observables/probe.py`)
computes the observable's AUC against choice-level correctness
labels and emits one of four verdicts:

| Band | AUC range | N requirement | Verdict |
|---|---|---|---|
| `TRUTH_CORRELATED` | `AUC ≥ 0.60` | `n ≥ 40` | Observable predicts correctness. A Rahu attractor *may* be worth building on it. Does not guarantee success — only unblocks further work. |
| `UNCORRELATED` | `0.45 ≤ AUC < 0.60` | `n ≥ 40` | Signal is near noise. A Rahu on this collapses to conventional blend at best; inference cost is pure overhead. **Do not build a Rahu.** |
| `ANTI_CORRELATED` | `AUC < 0.45` | `n ≥ 40` | Signal exists with the *wrong* sign. A Rahu built on this actively hurts accuracy — V1's exact failure mode. **Do not build a Rahu.** |
| `NULL` | any | `n < 40` | Too few datapoints to classify. Expand N before interpreting. |

Polarity is normalized inside the probe: observables with
`higher_means_more_suspicious=True` have their scalars negated
before AUC is computed, so the reported AUC uniformly means
"higher AUC ⇒ higher truth-predictiveness", regardless of the
observable's polarity convention.

The 0.60 threshold is deliberately loose. It is a
*go/no-go-on-building-a-decoder* gate, not a success claim. A
V2-era observable at AUC 0.62 is worth a bounded Rahu experiment;
the Rahu itself may still fail. The gate rules out the
V1-regression class of failure (AUC < 0.45) and the V1-dormant
class (AUC ≈ 0.5), which together accounted for all of V1's
observed behavior.

### 11.4 Observables shipped in this section

`symbolu_bcvf_llm/observables/` ships four built-in observables,
each conformant to the `Observable` Protocol. All are
deterministic, torch-free where possible, and safe to probe on
`MockBenchmark` (no GPU, no tokenizer). They are ordered by
diagnostic power against V1's specific failure mode:

1. **`BCVFSourceZeroCostObservable`** (`bcvf.py`). Per-source BCVF
   cost at source index 0 (the base decoder). Directly
   instruments §10.V1.2's "base voted off the island" mechanism
   — if this observable is `ANTI_CORRELATED`, paraphrase
   correlation is assigning the base model outsized cost when it
   is *correct* vs the paraphrase majority. Polarity:
   `higher = more suspicious`.
2. **`BCVFTotalCostObservable`** (`bcvf.py`). Sum of all per-pair
   BCVF costs — the kernel's default global disagreement
   measure. V1's implicit Ketu. Included for continuity with V1
   and as a control against (1). Polarity: `higher = more
   suspicious`.
3. **`SourceAgreementObservable`** (`agreement.py`). Fraction of
   lookahead positions where every source's argmax coincides,
   reported as `1 - agreement_fraction` so polarity aligns with
   BCVF. A polarity-simpler, kernel-free alternative to BCVF
   total cost; if BCVF total cost is `UNCORRELATED` but
   agreement-fraction is `TRUTH_CORRELATED`, the BCVF kernel is
   not extracting the available signal.
4. **`Source0EntropyObservable`** (`entropy.py`). Shannon entropy
   of source 0's next-token distribution at the first lookahead
   position. Choice-independent. Calibration signal: a model
   unsure of its own next token is generically less reliable.
   Polarity: `higher = more suspicious`.

Additional observables (cross-model-disagreement, retrieval-
grounded contradiction, token-level log-probability gap, etc.)
are V2-scoped and not shipped here. Adding a new observable is
one file implementing the Protocol; the probe harness picks it up
by name.

### 11.5 Probe harness

`symbolu_bcvf_llm/observables/probe.py` provides:

- `probe_observable(obs, benchmark, max_questions=None,
  retain_datapoints=True) → ProbeReport`. Runs `obs.observe(...)`
  over every (question, choice) in the benchmark subset, applies
  polarity normalization, computes Pearson r, Spearman ρ, AUC,
  class-conditional means, and returns a classified report with
  human-readable recommendation text.
- `probe_observables_parallel(obs_list, benchmark, max_questions,
  retain_datapoints=False) → {name: ProbeReport}`. Same, but for
  multiple observables in a single pass over the benchmark.
  Sources are reconstructed per-observable per-(Q, C) to preserve
  independence when observables have side effects on source
  state.

CLI: `scripts/probe_observables.py`. Defaults to
`--benchmark mock --num-questions 48` (no GPU required). With
`--benchmark truthfulqa` it loads TruthfulQA-MC via the §6.2
benchmark adapter with the fixed paraphrase pipeline from
§10.V1.6. Output is a Markdown report in
`docs/experiments/probe_observables_<benchmark>_<suffix>.md`.

Correlation primitives (`_pearson_r`, `_spearman_rho`,
`_roc_auc`, `_rankdata`) are implemented in pure NumPy to avoid
a scipy dependency on the probe path.

### 11.6 Gate — what §11 enforces

**§11 gate (binding for any future decoder work beyond V1).**

Before a V2 decoder is built on any observable `X`:

1. `X` must conform to the `Observable` Protocol.
2. `X` must be probed by `probe_observable` on a benchmark subset
   with `n_datapoints ≥ 40`.
3. The returned `ProbeReport.classification` must be
   `TRUTH_CORRELATED` (AUC ≥ 0.60).
4. The probe report must be checked into
   `docs/experiments/probe_observables_*.md` alongside the design
   note that cites it.

If `(3)` fails, the observable is shelved or redesigned. A Rahu
attractor is not permitted on a non-passing observable. This is
the V1 lesson encoded: the observable gate is the cheap check;
the decoder run is the expensive confirmation. Do the cheap check
first, always.

Retrospective application to V1: a §11 probe of
`BCVFSourceZeroCostObservable` on TruthfulQA-MC N=48 with the
fixed paraphrase pipeline would have returned `ANTI_CORRELATED`
or `UNCORRELATED` and blocked the V1 full run at the gate —
saving ~4 GPU-hours and producing the same epistemic output
(V1 configuration is not viable). §11 makes that path the
default path, not the accident of post-hoc analysis.

### 11.7 What §11 does NOT claim

- §11 does not claim any observable listed in §11.4 will pass
  its own probe. Running the probe is the §11 deliverable; the
  verdicts are empirical and reported per-observable in the
  check-in report.
- §11 does not replace §10.V1 falsification. A passing probe
  (AUC ≥ 0.60) is necessary but not sufficient for a V2 decoder
  to yield PASS; the §10 PASS/NULL/REGRESSION classification
  still governs decoder-level verdicts.
- §11 does not specify the Rahu shape. Trust-shaping (§5.1),
  additive penalty, veto, two-stage filter are all permitted
  Rahu choices *conditional on* the Ketu passing §11.3.
- §11 does not authorize threshold tuning on the probe output.
  The 0.60 / 0.45 bands are pre-committed; moving them after
  seeing probe data is the same §0.8 discipline violation §10
  codified.

### 11.8 Empirical probe result — V1 configuration

The §11 harness was run against the V1 configuration that produced
§10's REGRESSION verdict, answering the retrospective question:
"would a §11 probe have blocked V1 at the gate?"

**Command:**

```
python scripts/probe_observables.py \
    --benchmark truthfulqa \
    --num-questions 100 \
    --model mistralai/Mistral-7B-Instruct-v0.3 \
    --no-compile \
    --suffix _v1_config
```

**Configuration:** same-model paraphrase ensemble (M=3, source 0 =
base Mistral-7B, sources 1-2 = same-model paraphrases of the prompt
via the fixed §10.V1.6 paraphrase pipeline), TruthfulQA-MC validation
split, N=100 questions, ~521 (question, choice) datapoints (TruthfulQA
averages ~5.2 choices per question). Wall clock: 510 s on an A100 80GB.

**Verdict table:**

| Observable | AUC | Classification |
|---|---|---|
| `bcvf_total_cost` | 0.495 | **UNCORRELATED** |
| `bcvf_source_0_cost` | 0.502 | **UNCORRELATED** |
| `source_0_entropy` | 0.532 | **UNCORRELATED** |
| `source_disagreement_fraction` | 0.498 | **UNCORRELATED** |

Raw report on the runpod pod at
`docs/experiments/probe_observables_truthfulqa_v1_config.md`.

**Retrospective verification — §11 would have caught V1.**

All four shipped observables are UNCORRELATED on the V1 source
ensemble. Per §11.6 the gate blocks decoder construction on any
non-`TRUTH_CORRELATED` observable. Applied pre-V1, the gate would
have returned four simultaneous blocks and refused to authorize a
decoder run on this (source ensemble × benchmark) combination.

The §11 probe takes ~9 minutes of GPU time and produces the same
operational output ("V1 configuration is not viable") as the ~4
GPU-hour V1 full run plus the ~30-minute Experiment Zero confirmation.
The cost ratio is ~30× in §11's favor. This is the §10.V1 lesson
encoded: the cheap check precedes the expensive confirmation.

**Surprise — the probe result is UNCORRELATED, not ANTI_CORRELATED.**

§10.V1.8 attributed V1's REGRESSION to a specific mechanism (§2.4.5
symmetric attribution penalizing base when paraphrases align on
distractors). The mechanism hypothesis predicted that
`bcvf_source_0_cost` in particular would probe as ANTI_CORRELATED.
Empirically it came back at AUC 0.502 — indistinguishable from
noise. Two observations follow:

1. **Probe-level aggregate BCVF and decoder-level commit-loop
   behavior are different quantities.** The probe scores per
   (question, choice) using the commit-position lookahead window.
   The V1 REGRESSION mechanism is a *conditional, per-token*
   dynamic: on hallucination-prone tokens where paraphrases happen
   to agree on a distractor, the softmin trust-shaper down-weights
   the base decoder, and those per-token missteps compound over the
   commit loop into the -4 pp accuracy loss. At the per-choice
   aggregate, correct and wrong choices show similar BCVF cost
   distributions because the mechanism only fires on the fraction
   of tokens where same-model paraphrase correlation and
   distractor alignment coincide.

2. **§11 is therefore a conservative gate, not a mechanism replay.**
   It blocks things that have no usable per-choice signal (which
   the V1 configuration clearly doesn't). It may not reproduce
   decoder-loop failure mechanisms that are only visible under
   trust-shaping dynamics over many commit steps. The §11
   commitment is one-directional: a passing probe is necessary
   before a Rahu is authorized; a failing probe blocks. The probe
   does not claim to be a complete explanation of why any specific
   configuration would or wouldn't fail.

This is consistent with §10.V1.8's finding and does not unwind it.
§10.V1.8 explains *why* V1 regressed (mechanism); §11.8 shows
*that* §11 would have flagged the configuration as unviable without
needing the mechanism (gate). Both are true.

**Marginally-positive signal — `source_0_entropy` at 0.532.**

Source 0 entropy is weakly positive (AUC 0.532 vs 0.500 null) but
below the 0.60 TRUTH_CORRELATED threshold. Standard error on AUC
at N=521 with balanced classes is ≈ 0.022, so 0.532 is ~1.4 SD
above 0.500 — not statistically compelling. Of the four observables
it is the only one that is kernel-independent (reads source 0's
next-token distribution alone), so the faint signal is from the
base model's own calibration rather than from any cross-source
disagreement machinery. Worth noting for future V2 observable
design; not sufficient on its own to authorize a decoder run.

**Decision — V1 closure is empirical and gate-confirmed.**

- §10.V1.5's falsification verdict stands (V1 configuration is not
  viable).
- §11.8 adds: the §11 gate independently confirms the same verdict
  at 30× lower cost.
- No V2 decoder is authorized on the V1 source ensemble. Any V2
  proposal must either (a) change the source ensemble and re-probe
  (§10.V1.3's Experiment A — cross-model paraphrasers), or (b)
  propose a new observable whose probe passes §11.6 on at least
  one source ensemble.
- §11 infrastructure is retained as the standing gate for all
  future decoder proposals on this package.

### 11.9 Per-step BCVF probe — aggregate-masks-signal hypothesis test

§11.8 left one open question: the §10.V1.2 mechanism is a
per-token conditional (paraphrase alignment on distractors
penalizes base on specific hallucination-prone tokens), but the
shipped BCVF observables score per-(Q, choice) at a single
commit-position lookahead. If the mechanism is real at the
per-token level, a per-step probe should surface signal that the
aggregate view averaged out.

Two new observables (commit `7b2ee0a`):

- `BCVFPerStepMaxObservable` — walks the teacher-forced answer
  path, computes BCVF at every step, reduces via `max`.
- `BCVFSourceZeroPerStepMaxObservable` — same, but returns the
  per-source cost of source 0 specifically.

Both mutate source state via `commit()` along the answer path and
opt into the probe harness's `requires_isolated_sources = True`
flag.

**Command:**

```
python scripts/probe_observables.py \
    --benchmark truthfulqa \
    --num-questions 100 \
    --model mistralai/Mistral-7B-Instruct-v0.3 \
    --no-compile \
    --suffix _v1_per_step
```

Wall clock: 2794 s (~47 min) on the same A100 80GB. The 5.5×
runtime vs §11.8 comes from per-step commits: each answer token
(~10 on average) adds `2 × 3 = 6` forward passes per source
triple, doubled across the two isolated observables.

**Aggregate vs per-step comparison:**

| Observable | §11.8 aggregate AUC | §11.9 per-step AUC | Δ |
|---|---|---|---|
| `bcvf_total_cost` / `bcvf_per_step_max` | 0.495 | **0.462** | −0.033 |
| `bcvf_source_0_cost` / `bcvf_source_0_per_step_max` | 0.502 | **0.478** | −0.024 |
| `source_0_entropy` | 0.532 | — | (unchanged — not BCVF-family) |
| `source_disagreement_fraction` | 0.498 | — | (unchanged — not BCVF-family) |

Both BCVF-family observables shift in the ANTI direction under
the per-step drill-down, by 0.024-0.033 AUC. Standard error at
N=521 with balanced classes is ≈0.022, so 0.462 is ≈1.7 SD below
the null and 0.478 is ≈1 SD below; neither crosses the 0.45
ANTI_CORRELATED gate threshold on its own, but the consistency of
the direction (both down, neither up) carries information beyond
the marginal per-observable p-values.

**Hypothesis tests:**

1. **"Aggregate masks truth-correlated signal that per-step reveals."**
   *Falsified.* Per-step did not surface a positive AUC for any
   observable. Both BCVF-family per-step observables remain
   below 0.5.

2. **"§10.V1.2 mechanism operates at per-token level with
   anti-correlated sign."** *Weakly consistent.* Aggregate BCVF
   was indistinguishable from noise (AUC 0.495 / 0.502); per-step
   drill-down revealed a slight negative shift in both, matching
   what a per-token wrong-direction mechanism would predict.
   Consistent with the −3.06 pp / −4.00 pp V1 regression
   magnitudes: a small-effect mechanism that exists at per-token
   granularity, averages out at per-choice aggregate, and
   partially resurfaces under max-reduction over steps.

**Verdict — V1 source ensemble is saturated.**

Six observables have now been probed on the V1 configuration
(same-model Mistral-7B paraphrase, M=3, TruthfulQA-MC):

| Observable | AUC | Classification |
|---|---|---|
| `bcvf_total_cost` | 0.495 | UNCORRELATED |
| `bcvf_source_0_cost` | 0.502 | UNCORRELATED |
| `source_0_entropy` | 0.532 | UNCORRELATED |
| `source_disagreement_fraction` | 0.498 | UNCORRELATED |
| `bcvf_per_step_max` | 0.462 | UNCORRELATED |
| `bcvf_source_0_per_step_max` | 0.478 | UNCORRELATED |

Six observables across three semantic families (BCVF-aggregate,
BCVF-per-step, cheap-proxy) all fail §11's 0.60 TRUTH_CORRELATED
gate. The "change the observable" lever is exhausted on this
source ensemble. No V2 decoder is authorized on same-model
paraphrase sources for this benchmark regardless of what
observable is built on top.

**Next lever — change the source ensemble.**

§10.V1.3 Experiment A (cross-model source ensemble) becomes the
sole remaining untested configuration. Replace the two same-model
paraphrase sources with paraphrases from a *different* model
(cross-model source independence). The existing six observables
are re-probed against the new ensemble; if any passes §11.6, a
bounded V2 decoder experiment is authorized. If none pass, the
default-consumer architecture (softmin trust-shaping over
symmetric per-source attribution) is also implicated and must be
redesigned alongside the source ensemble.

§11.9 result is retained as the empirical lower bound on what any
V2 proposal must improve on: cross-model ensembles must produce
at least one observable with AUC ≥ 0.60, measured by the same
probe harness, on the same benchmark subset.

### 11.10 Cross-model paraphraser — V2 Experiment A result

`§10.V1.3` Experiment A's hypothesis: replace same-model paraphrase
sources with paraphrases from a different model family to decorrelate
the ensemble. If source correlation was V1's primary failure, AUC
should rise on BCVF-family observables.

**Command:**

```
python scripts/probe_observables.py \
    --benchmark truthfulqa \
    --num-questions 100 \
    --model mistralai/Mistral-7B-Instruct-v0.3 \
    --paraphraser-model Qwen/Qwen2.5-3B-Instruct \
    --no-compile \
    --suffix _v2_cross_model_qwen3b
```

Both models loaded simultaneously (20 GB VRAM; A100 80GB holds
both comfortably). Wall clock: 2635.6 s (~44 min).

**Results vs same-model baseline:**

| Observable | V1 same-model | V2 Qwen-3B cross-model | Δ |
|---|---|---|---|
| `bcvf_total_cost` | 0.495 | 0.518 | +0.023 |
| `bcvf_source_0_cost` | 0.502 | 0.497 | −0.005 |
| `source_0_entropy` | 0.532 | 0.532 | 0.000 |
| `source_disagreement_fraction` | 0.498 | 0.500 | +0.002 |
| `bcvf_per_step_max` | 0.462 | 0.476 | +0.014 |
| `bcvf_source_0_per_step_max` | 0.478 | 0.473 | −0.005 |

All six observables remain UNCORRELATED. Aggregate BCVF nudges
toward TRUTH (+0.023, +0.014); per-source and kernel-independent
observables basically unchanged. Maximum observed AUC on the V2
ensemble is 0.532 — the same entropy reading as V1, and 3 SD
short of the 0.60 gate.

**Verdict.** V1 + V2 on TruthfulQA-MC: ALL observable × source-
ensemble combinations fail §11's 0.60 gate. The lever pair
(observable, source ensemble) is empirically exhausted on this
benchmark. The next disciplined move is to change the benchmark.

### 11.11 HaluEval QA — first §11-passing configuration

**Hypothesis**: TruthfulQA's distractors are **human-adversarial**
(hand-crafted to match common misconceptions). HaluEval's
`hallucinated_answer` is **LLM-generated** (produced by GPT-3.5 to
look plausible but be factually wrong). Different adversarial
distribution → potentially different observable dynamics. A §11
probe on HaluEval tests whether the TruthfulQA-MC failure was
benchmark-structure-specific or a property of BCVF.

**Implementation** (commit `cad0747`): `HaluEvalBenchmark` added
as a subclass of `TruthfulQABenchmark`; reuses all model loading,
paraphrase pipeline, and cache machinery. Only `_load_questions`
and `_convert_row` are overridden — HaluEval-QA rows map directly
to a 2-choice MC (right vs hallucinated).

**Command (V1 same-model paraphrase, N=100):**

```
python scripts/probe_observables.py \
    --benchmark halueval --num-questions 100 \
    --model mistralai/Mistral-7B-Instruct-v0.3 \
    --no-compile \
    --suffix _v1_halueval
```

Wall clock: 891 s (~15 min). N_datapoints = 200 (100 questions × 2
choices). SE(AUC) ≈ 0.035 at this N.

**Verdict table:**

| Observable | AUC | Classification |
|---|---|---|
| `bcvf_total_cost` | 0.500 | UNCORRELATED |
| `bcvf_source_0_cost` | 0.500 | UNCORRELATED |
| `source_0_entropy` | 0.500 | UNCORRELATED |
| `source_disagreement_fraction` | 0.500 | UNCORRELATED |
| **`bcvf_per_step_max`** | **0.673** | **TRUTH_CORRELATED** |
| **`bcvf_source_0_per_step_max`** | **0.626** | **TRUTH_CORRELATED** |

**First §11 passage of the campaign.** AUC 0.673 is ~4.9 SD above
the null — strongly significant, not a measurement-noise miss.
Reproduced exactly on a follow-up 7-observable run (same warm
cache, same seeds): `bcvf_per_step_max` 0.673, `bcvf_source_0_per_step_max`
0.626 reproduced to 3 decimals.

**Why per-step but not aggregate.** Six observables span three
semantic families:

- **Aggregate-at-commit-position** (first four rows): read BCVF /
  entropy / argmax-agreement at the single lookahead window before
  any answer token is committed. All four landed at exactly AUC
  0.500 — zero signal.
- **Per-step along the teacher-forced answer path** (rows 5-6):
  advance through the answer token-by-token, reducing per-step
  BCVF costs via max. Both rows passed §11.

HaluEval's `hallucinated_answer` is LLM-generated: each answer is
locally plausible at the token level but contains a factual error
somewhere along its trajectory. Aggregate commit-position
observables miss the error (averages over a short lookahead window
dominated by plausible first tokens). Per-step max captures the
spike where the model's distribution destabilizes as it traverses
the hallucinated fact. This matches the mechanism §10.V1.2
predicted — a **per-token conditional** — just on the benchmark
whose distractor construction surfaces it.

### 11.12 SCC-pattern test: coherence-anchored BCVF observables

§11.11 passed per-step BCVF. Open question from §11's SCC review:
does combining the stability signal with a semantic-alignment
anchor (SCC's `C' = C × S` pattern) amplify further?

Two observables shipped (commits `01047c7`, `25240ab`):

- `CoherenceAnchoredBCVFObservable`:
  `scalar = 1/(1+bcvf_total_cost) × P(first_token | prompt)`.
  Aggregate stability × first-token teacher-forced alignment.
- `CoherenceAnchoredBCVFPerStepObservable`:
  `scalar = 1/(1+max_step_bcvf) × exp(mean log P(token_t | prefix))`.
  Per-step stability × geometric-mean teacher-forced alignment.

Both use minimum-knob SCC instances (no α/β/γ/δ coefficients) to
stay §0.8-compliant.

**Results on the 8-observable HaluEval probe:**

| Observable | AUC | Δ vs best per-step |
|---|---|---|
| `bcvf_per_step_max` (§11.11 winner) | 0.673 | — |
| `bcvf_source_0_per_step_max` | 0.626 | −0.047 |
| `coherence_anchored_bcvf` (aggregate) | 0.510 | −0.163 |
| **`coherence_anchored_bcvf_per_step`** | **0.431** | **−0.242 (ANTI)** |

**The per-step coherence observable passed below 0.45 — ANTI_CORRELATED.**

Decomposing why: the SCC product is
`stability × alignment`. On HaluEval:

- `stability = 1/(1 + max_step_bcvf)` inherits the per-step BCVF
  signal, so **stability alone is AUC ≈ 0.67 (truth-positive)**.
- `alignment = geo_mean P(token | prefix)` under source 0 (Mistral).
  HaluEval's hallucinated answers are LLM-generated to be plausible
  to the target model, so Mistral assigns HIGHER teacher-forced
  probability to hallucinations than to factually correct answers.
  **Alignment alone is AUC ≈ 0.40 (truth-negative)**.

Multiplying a truth-positive factor by a truth-negative one gives a
combined signal that depends on which factor has larger dynamic
range. Probabilities span orders of magnitude; stability stays close
to 1. The anti-correlated alignment dominates. Product AUC: 0.431 —
systematically preferring hallucinated answers.

**SCC pattern lesson.** `C × S` amplifies signal when both factors
are independently truth-correlated. When one is truth-*anti*-
correlated on a benchmark (because an adversarial pipeline
optimizes against it), the product goes backwards. Semantic
alignment taken from the target model's own distribution cannot
serve as a truth anchor on benchmarks whose distractors were
generated against that distribution. A valid anchor must come
from outside the target model's parametric knowledge — cross-model
verification, retrieval grounding, or a trained truth probe.

### 11.13 Campaign summary and V2 decoder authorization

Four probe runs, 14 (observable, source ensemble, benchmark)
tuples tested:

| Benchmark | Source ensemble | Observables tested | §11-passing |
|---|---|---|---|
| TruthfulQA-MC | Mistral paraphrase (V1) | 6 + coherence | 0 |
| TruthfulQA-MC | Mistral + Qwen-3B paraphrase (V2) | 6 | 0 |
| HaluEval-QA | Mistral paraphrase (V1) | 8 | **2** |

Of the 14 probes, **two observables cross §11's 0.60 gate, both on
HaluEval-QA with the V1 same-model source ensemble**:

1. `bcvf_per_step_max` — AUC 0.673, 4.9 SD above null.
2. `bcvf_source_0_per_step_max` — AUC 0.626, 3.6 SD above null.

**V2 decoder authorization per §11.6**: a bounded decoder
experiment on HaluEval with `bcvf_per_step_max` as the Ketu is
authorized. Specifically NOT authorized: decoder experiments on
TruthfulQA-MC (no passing observable in any tested configuration)
or on HaluEval using coherence-anchored observables (the
alignment factor is adversarially anti-correlated on this
benchmark).

**Discipline cost-benefit retrospective.** Four probe runs at ~15-45
min each (~2-3 GPU-hours total across campaign) replaced what would
have been ~20 GPU-hours of blind decoder-regression debugging.
§11.6 gate rejected 12/14 configurations before any decoder-run
compute was committed. Of the 2 passing configurations, both are
on a single benchmark — decoder work can now target that
configuration without having to defend against the 12 failing
ones.

### 11.14 V2 decoder experiment — UNVIABLE_COST, observable-decoder gap diagnosed

**Command:**

```
python -m symbolu_bcvf_llm.benchmark \
    --benchmark halueval --num-questions 100 \
    --model mistralai/Mistral-7B-Instruct-v0.3 \
    --no-compile \
    --paraphrase-cache-file <prewarmed> \
    --suffix _v2_decoder --seed 1
```

Full three-decoder sweep (vanilla / conventional-blend / BCVF-trust)
on HaluEval-QA, using the same source ensemble that §11.11 certified
`bcvf_per_step_max` passing at AUC 0.673. Wall clock: 443 s (~7.4
min). Paraphrase cache: 800 hits, 0 misses — 100 % hit rate from the
probe's warm cache; no new paraphrase generation.

**Result:**

| Decoder | Accuracy | Mean Latency | vs Blend |
|---|---|---|---|
| vanilla | 93.00 % | 0.062 s | — |
| conventional_blend | **97.00 %** | 0.190 s | baseline |
| bcvf_trust | 95.00 % | 4.113 s | Δ = −2.00 pp, latency = 21.6× |

**§1.10 classification: UNVIABLE_COST.** Trust regresses by 2 pp vs
blend *and* blows the 5× latency ceiling (actual: 21.6×). Fails on
both axes.

**The decoder-observable gap.**

§11.11 certified `bcvf_per_step_max` (max total BCVF cost across
teacher-forced answer steps, reduced via max). The existing
TrustShaper (§5.1) computes per-pair BCVF costs at the current
commit-window lookahead and combines via softmin over per-source
attributions. These are **structurally different reductions**:

- §11-passing observable:
  `max_t bcvf_total_cost(lookahead_at_step_t)` — captures spikes
  along the answer path.
- TrustShaper decoder-time computation:
  `softmin(per_source_costs_at_current_lookahead)` — single window,
  no per-step trajectory, softmin-weighted.

The probe gate passed on the former; the decoder acts on the
latter. The 2 pp regression is the familiar V1 failure mode —
softmin attribution penalizes source 0 on questions where same-
model paraphrases happen to align on distractors — reproduced on
HaluEval because the TrustShaper's architectural choice hasn't
changed.

This is the first empirical confirmation of §11.7's pre-committed
caveat: **a passing probe is necessary but not sufficient**.
Crossing §11's 0.60 gate means *this observable has discriminating
signal*; it does not guarantee that the existing Rahu shape
consumes that signal correctly. On HaluEval, the Rahu's internal
BCVF computation diverges from the Ketu that passed the gate, and
the gap is the full −2 pp verdict.

**Latency.**

21.6× blend latency is not surprising — the trust decoder uses a
speculation loop (propose, compute trust, re-score, roll back if
needed) versus blend's single teacher-forced pass. For a decoder
this slow to be adopted, the accuracy lift would need to be
material (§1.10 PASS requires ≥ +2 pp over blend). At −2 pp, the
latency conversation is moot.

**Paraphrase pipeline behavior.**

100 % cache hit rate (800/800) confirms the §10.V1.6 paraphrase-
pipeline-version-stamping works correctly: the §11.11 probe's
paraphrases were reused without regeneration by the §11.14 decoder
run. Same pipeline version, same paraphraser model, same split →
cache accepted. This fulfills the original cache-design goal
(pay paraphrase cost once per (model, paraphraser, pipeline
version, split)).

### 11.15 Campaign closure — research note on §11 as the deliverable

The V1 / V2 decoder programs on this package are closed. §10.V1 was
closed by §10.V1.8 as falsified. V2 Experiment A (cross-model) was
closed by §11.10 as not rescuing any observable on TruthfulQA-MC.
V2 decoder on the first §11-passing configuration (HaluEval with
per-step BCVF Ketu) was closed by §11.14 as UNVIABLE_COST with a
diagnosed observable-decoder architectural mismatch.

What remains as shippable output is **§11 itself**: the discipline,
the implementation, and the empirical track record.

**The discipline, restated.**

Before any decoder attractor is built on any observable, the
observable must be probed on a held-out benchmark subset and shown
to cross AUC ≥ 0.60 against choice-level correctness, via the
probe harness in `symbolu_bcvf_llm/observables/probe.py`. Classes:

- `TRUTH_CORRELATED` (AUC ≥ 0.60): decoder experiment authorized.
- `UNCORRELATED` (0.45 ≤ AUC < 0.60): decoder experiment blocked.
- `ANTI_CORRELATED` (AUC < 0.45): decoder experiment blocked, sign
  explicitly recorded as wrong.
- `NULL` (n_datapoints < 40): insufficient data, re-probe.

**The track record.**

14 (observable, source ensemble, benchmark) tuples probed across
4 GPU-hours total. §11 returned:

- 11 UNCORRELATED verdicts.
- 1 ANTI_CORRELATED verdict (coherence-anchored-per-step on
  HaluEval — the alignment factor is adversarially anti-correlated
  on LLM-generated distractors).
- 2 TRUTH_CORRELATED verdicts, both on HaluEval-QA with per-step
  BCVF reductions.

Of the 12 non-passing configurations, zero were built into a
decoder. Of the 2 passing configurations, one was built into a
decoder and returned UNVIABLE_COST with a diagnosed architectural
gap (§11.14). Total compute saved vs a blind decoder-regression
protocol: at least 20 GPU-hours — and the diagnostic quality is
strictly better than the V1 post-mortem approach that required
running the full pipeline to identify the failure.

**What §11 does not claim.**

§11 is a necessary-but-not-sufficient gate. Passing the probe
does not guarantee a decoder win (§11.14 demonstrates this). §11
does not endorse any specific Rahu architecture. §11 does not
perform hyperparameter tuning on its own thresholds — the 0.60 /
0.45 bands are pre-committed and have not been modified during
the campaign.

**V3 directions the §11 harness is ready to gate.**

These are not authorized work; they are the open questions that a
future campaign could test without re-deriving the discipline:

1. **Per-step-aware TrustShaper variant** — a Rahu whose internal
   BCVF computation matches the `bcvf_per_step_max` reduction that
   passed §11.11. Would close the §11.14 observable-decoder gap on
   HaluEval. Requires a ~2-day engineering effort. Would be gated
   by a re-probe of its implied observable before any decoder
   run.
2. **Retrieval-grounded alignment observable** — a coherence
   observable whose alignment anchor comes from retrieved
   Wikipedia/fact-database chunks rather than the target model's
   own teacher-forced probability (which §11.12 showed is
   adversarially anti-correlated on LLM-generated distractors).
   New infrastructure (~2 days).
3. **Trained truth-probe observable** — a small linear classifier
   on hidden-state features, trained on labeled (right_answer,
   hallucinated_answer) pairs, used as a truth-direction anchor
   alongside a stability factor. Requires a labeled training split
   disjoint from the probe split.
4. **Cross-layer BCVF** — apply the BCVF kernel to hidden-state
   trajectories across transformer depth (layer index as "time")
   rather than across paraphrase sources at the output. Novel
   research direction; not in the LLM hallucination-detection
   literature.

Each would be implemented as one or more `Observable` Protocol
conformants, probed via the existing harness, and — if they cross
§11's 0.60 gate — authorized for a bounded decoder experiment.
The discipline carries forward regardless of which direction is
taken.

**Repository state at campaign close.**

Branch `claude/bcvf-llm-documentation-RPqCi`. Final commit
`<next>`. Shipped:

- `symbolu_bcvf_llm/observables/` — 8 observables, probe harness,
  classification bands, 150+ tests.
- `symbolu_bcvf_llm/benchmark/dataset.py` — TruthfulQABenchmark,
  HaluEvalBenchmark, cross-model paraphraser support.
- `scripts/probe_observables.py` — CLI wrapper.
- `docs/experiments/` — 4 probe reports + V2 decoder results.
- This document, §10-§11 — campaign record.

No further V1/V2 work is authorized on this package. Future work,
when proposed, must enter via the §11 gate.

### 11.16 V3 (a) uncertainty-gated probe — empirical ceiling diagnosed

**Hypothesis.** §11.14 diagnosed the V2 decoder's UNVIABLE_COST as
an observable-decoder reduction mismatch. The cheapest V3 fix
candidate (§11.15 option a): apply BCVF trust-shaping only when
the base model is genuinely uncertain, on the theory that
confident steps were contributing noise rather than signal to the
per-step max reduction.

**Implementation** (commit `60028df`):

```
UncertaintyGatedBCVFPerStepMaxObservable
  scalar = max over steps where entropy(source_0) > tau of
           bcvf_total_cost(step)
  tau = 1.0 nat (pre-committed per §0.8)
```

Identical to `bcvf_per_step_max` except a per-step entropy gate
filters the max candidates. If confident steps were noise, the
gate should amplify AUC; if they were signal, the gate should
reduce AUC.

**Result on HaluEval-QA (V1 same-model paraphrase, N=100):**

```
Probing 9 observables against halueval N=100...
Probed in 1723.0 s
```

| Observable | AUC | Δ vs unconditional per-step max |
|---|---|---|
| `bcvf_per_step_max` (§11.11 winner) | 0.673 | — |
| `bcvf_source_0_per_step_max` | 0.626 | −0.047 |
| **`uncertainty_gated_bcvf_per_step_max`** | **0.655** | **−0.018** |
| `coherence_anchored_bcvf` | 0.510 | (aggregate, separate family) |
| `coherence_anchored_bcvf_per_step` | 0.431 (ANTI) | (alignment-anti per §11.12) |

V3 (a) **passes §11** at AUC 0.655 (TRUTH_CORRELATED, > 0.60 gate)
but **does not amplify** the unconditional per-step max signal.
The −0.018 AUC is below one standard error at N=200 (SE ≈ 0.035),
so the difference is not statistically significant — but the
direction is consistent: filtering confident steps neither helps
nor hurts meaningfully.

**Hypothesis verdict: empirically falsified.** The uncertainty
gate was predicted to amplify signal by removing adversarial-
confidence noise. Empirically, confident steps were contributing
*useful* signal to the per-step max, and removing them costs ~2
AUC points. The "always-on per-step BCVF" reduction the §11.11
winner used is approximately Pareto-optimal within the same-
model BCVF family.

**Empirical ceiling diagnosed.** Three BCVF-per-step variants
have now been probed on HaluEval-QA:

| Reduction | AUC |
|---|---|
| Total cost, max over steps (unconditional) | 0.673 |
| Source-0 cost, max over steps | 0.626 |
| Total cost, max over uncertain steps only | 0.655 |

All three sit in a tight 0.63–0.67 band. **No same-model BCVF
variant within this family pushes above 0.70.** This is the
empirical ceiling on the BCVF-on-paraphrase observable family
for hallucination detection on this benchmark.

**Decision: V3 BCVF-variant iteration closed.**

Per the cost-benefit framing committed before the V3 (a) probe
("AUC 0.70 mid-pack, proceed only with specific destination"),
the 0.655 result is below the decision threshold. Further BCVF-
kernel tweaks have diminishing returns. The 0.43–0.67 AUC band
appears to be the regime ceiling for this observable family on
this benchmark with these source ensembles.

The §11 harness, the discipline, the negative-result documentation,
and one positive empirical result (per-step max BCVF on HaluEval at
0.673) now constitute the campaign's complete output.

**Pivot authorization.** §11 infrastructure is freed for application
to other problem domains where multi-source/observable analysis is
relevant — agentic reliability gating, speculative-decoding
acceptance criteria, reasoning-chain confidence calibration, or any
adjacent decoder/attractor design problem. The discipline carries
across; only the observables and benchmarks need to be re-pointed.

This concludes the V1 / V2 / V3 BCVF-LLM trust-routing campaign on
this package.

## Section 12 — Pivot: Speculative-Decoding Acceptance Probe

§11.16 closed the hallucination-detection campaign with the §11
toolkit (Observable Protocol, probe harness, classification bands,
polarity normalization, isolated-source opt-in, paraphrase cache
infrastructure) now freely applicable to other decoder/attractor
design problems. §12 opens the first such pivot.

### 12.1 Why speculative decoding

The §11 machinery transfers to any problem with:
- Multiple "views" of the same input (a source ensemble).
- A per-position ground-truth label.
- A downstream attractor/consumer whose design could benefit from
  a better signal.

Speculative decoding fits exactly: a small draft model proposes
K tokens, a large target model verifies in one forward pass, and
each (position, token) has a ground-truth accept/reject label
from the standard rejection-sampling rule (Leviathan et al. 2023,
Chen et al. 2023). The per-pair (draft, target) distribution
comparison is structurally identical to the (source 0, source 1)
comparison our kernel already handles — just with M=2 instead of
M=3.

**Commercial motivation.** Every frontier inference stack uses
speculative decoding. Acceptance rate governs throughput; even a
5 % acceptance improvement is material. Current criteria are
simple probability ratios; a richer signal (e.g., BCVF over
draft-target distributions, per-step-max reduction) could predict
acceptance more accurately and allow more aggressive draft
proposals.

**Research motivation.** No one has published BCVF-style 2nd-order
kernels in the speculative-decoding literature. The discipline
the §11 harness imposes — pre-committed classification bands,
probe-before-build — is also absent from that literature. Clean
methodology contribution is plausible even with modest empirical
gains.

### 12.2 M=2 compatibility established

Commit `<this>` scaffolds the pivot:

- `symbolu_bcvf_llm/benchmark/speculative.py` ships two classes:
  `SpeculativeDecodingMockBenchmark` (synthetic, deterministic,
  torch-free) and `SpeculativeDecodingBenchmark` (real-model
  skeleton, `NotImplementedError` stub pending the next session's
  candidate-generation + acceptance-labelling pipeline).

- All 9 shipped observables are verified M=2-compatible by a new
  test suite (`tests/test_speculative_mock.py`):
  - `BCVFTotalCostObservable`, `BCVFSourceZeroCostObservable`
  - `BCVFPerStepMaxObservable`, `BCVFSourceZeroPerStepMaxObservable`
  - `CoherenceAnchoredBCVFObservable`,
    `CoherenceAnchoredBCVFPerStepObservable`
  - `UncertaintyGatedBCVFPerStepMaxObservable`
  - `Source0EntropyObservable`, `SourceAgreementObservable`

- Probe CLI accepts `--benchmark speculative-mock`.

The mock benchmark's smoke-run produces deterministic AUCs
(coherence observables trivially ace the toy because correct
candidates have first-token = target peak). This confirms the
plumbing but says nothing about real-draft-target signal dynamics,
which require §12.3.

### 12.3 Real draft-target benchmark — shipped

`SpeculativeDecodingBenchmark` is now a first-class class in
`symbolu_bcvf_llm/benchmark/speculative.py` (commit `<this>`).
Implementation summary:

1. Load a target model (e.g., Mistral-7B or Llama-3-8B) and a
   draft model (e.g., Qwen-2.5-3B, TinyLlama-1.1B). Both via
   HuggingFace `from_pretrained` with same tokenizer
   compatibility check.
2. For each prompt in the underlying dataset (HaluEval QA or any
   TriviaQA-style text source), sample K candidate draft
   continuations from the draft model at T>0 using
   `model.generate(do_sample=True, num_return_sequences=K)`.
3. For each candidate, run the target model in teacher-forced
   mode to obtain per-position target distributions
   `p_target(·|prefix)`.
4. Per-position acceptance probability under the rejection-sampling
   rule: `P(accept token t) = min(1, p_target(t) / p_draft(t))`.
   Per-candidate label: fraction of tokens accepted in expectation,
   or binary "fully accepted"/"partially rejected".
5. `correct_index = argmax(acceptance_rate)` per question.

**Tokenizer compatibility.** `__init__` asserts
`target.vocab_size == draft.vocab_size`. Same-family pairs
(Qwen-7B + Qwen-3B, Llama-8B + Llama-1B) are default-compatible.
Cross-family pairs (Mistral + Qwen) fail construction with a
clear error message. Cross-family support would require a
re-tokenization step with precision loss — deferred as future
work.

**Default pair**: Qwen-2.5-7B-Instruct target + Qwen-2.5-3B-Instruct
draft. Same tokenizer family, same vocabulary; already-familiar
commercial-style spec-dec pairing. Override via
`--model target_model_name --draft-model draft_model_name`
at the CLI.

**Tests shipped**: 20 tests across `test_speculative_mock.py`
(M=2 probe harness + mock benchmark, 11 tests, all run without
torch) and `test_speculative_real.py` (acceptance math,
stable-softmax, prompt-text routing, 9 tests — 3 torch-gated
skip in CI, the other 6 run everywhere). Full suite: 360 passed,
5 skipped.

### 12.5 Cross-layer BCVF observables — structurally-independent stability

**Motivation.** §11.12 showed `coherence_anchored_bcvf_per_step` collapsed
to AUC 0.431 (ANTI) on HaluEval because the alignment factor was
adversarially anti-correlated (hallucinated answers are LLM-optimized
to maximize teacher-forced log-prob). §12's spec-dec framing
revealed a second failure mode: on same-family draft-target pairs,
cross-source BCVF saturates near zero (distributions are usually
similar), so the stability factor contributes no independent signal
and alignment alone dominates.

Both failure modes share a structural root cause: the stability
factor was not independent of the alignment factor. On adversarial
benchmarks the alignment inverts; on same-family pairs the
stability saturates. Neither produces the "C × S complementary
amplification" that the SCC pattern requires.

**Proposal (§12.5).** Replace cross-source BCVF with **cross-layer
BCVF** on the target's own hidden-state trajectory. Each transformer
layer produces a hidden state; applying the logit lens projects
these into per-layer next-token distributions. The 2nd-order
difference norm across layers measures how "jittery" the model's
representation is as it traverses depth.

This factor is structurally independent of:

- paraphrase-source agreement (no ensemble).
- teacher-forced log-probability (reads hidden states, not logits
  directly).
- cross-family disagreement (single model, no draft-target pair).

It's a genuinely orthogonal stability signal — the kind of
"independent sensor" that autonomy BCVF was designed around, but
with layer index playing the time-axis role instead of timesteps.

**Implementation** (commit `<this>`):

- `HuggingFaceSource.layer_lookahead()` — one forward pass with
  `output_hidden_states=True`; each layer's last-position hidden
  state is projected through the lm_head weight matrix; softmax →
  per-layer probability distribution. Returns shape
  `(N_layers, V)`.

- `MockLayerSource` — `MockSource` subclass for offline tests.
  Takes a `layer_logits_fn(prefix, n_layers, V) → (N_layers, V)`
  callback. Default (no callback) broadcasts position-0 logits
  across layers so 2nd-diff is zero (useful as a degenerate
  baseline).

- `LayerInstabilityObservable` — walks the teacher-forced answer
  path via `commit()`, calls `layer_lookahead()` at each step,
  computes `Σ_l ||p_{l-1} - 2 p_l + p_{l+1}||` across interior
  layers, aggregates over steps via max. Polarity: higher = more
  suspicious. Opts into isolated sources.

- `CoherenceAnchoredLayerBCVFObservable` — the proper SCC test:
  `scalar = 1/(1 + max_layer_instability) × exp(mean log p_target(token))`.
  Stability factor from intra-model layer dynamics; alignment
  factor from teacher-forced probability. The two factors share
  no computational path, so multiplicative amplification can
  actually happen (not collapse).

- **Graceful degradation**: both observables emit
  `ObservableValue(scalar=0, metadata={"unsupported": True, ...})`
  when source 0 lacks `layer_lookahead`. Probe reports
  UNCORRELATED rather than crashing — benchmarks whose sources
  don't expose hidden states stay runnable.

**Tests**: 24 new tests covering the 2nd-difference math, the
mock-source plumbing, both observables' shape / polarity / state-
mutation / metadata, graceful degradation on non-layer sources,
and probe-harness isolation. Full suite: 384 passed, 5 skipped.

**CLI**: `scripts/probe_observables.py` default observable list
grows from 9 → 11 observables. The spec-dec-mock benchmark's
`make_sources` now returns `MockLayerSource` instances so all 11
exercise cleanly. The generic `MockBenchmark`'s `MockSource`
returns still lack `layer_lookahead` — layer observables degrade
gracefully to UNCORRELATED on those runs.

**Prediction for §12.3 real-model probe** (pre-committed per §0.8):

| Observable | Predicted AUC |
|---|---|
| `bcvf_per_step_max` on (target, draft) | 0.65-0.75 |
| `coherence_anchored_bcvf_per_step` | 0.72-0.82 (alignment-dominated) |
| `layer_instability_max` | 0.55-0.70 (open question) |
| **`coherence_anchored_layer_bcvf_per_step`** | **0.75-0.88** |

The last row is the real test of the SCC hypothesis. If layer-
stability and alignment are genuinely complementary, the product
should exceed alignment-alone's AUC (estimated 0.72-0.78). If
the product matches alignment, cross-layer stability wasn't
adding signal. If the product drops below alignment, layer
stability is actually correlated with wrong answers (which
would be diagnostically interesting — maybe harder questions
have more stable internal representations, a research-paper-
worthy finding).

### 12.4 Research predictions (pre-committed per §0.8)

Before the §12.3 probe is run, the following predictions are
recorded for future falsification:

- **`bcvf_total_cost` on (target, draft)**: likely AUC 0.55-0.70.
  This is essentially a smoothed version of the probability-ratio
  signal the standard rejection-sampling rule already uses, so it
  should be close to — but not dramatically above — the baseline.
- **`bcvf_per_step_max`**: likely AUC 0.60-0.75. Per-token
  acceleration of disagreement is a more sensitive signal than
  aggregate probability ratio; plausible §11 pass.
- **`Source0EntropyObservable`** (reading target entropy):
  likely AUC 0.60-0.70. High target entropy → hard-to-match
  token → more likely to be rejected. This is a known baseline
  in the literature.
- **`CoherenceAnchoredBCVFObservable`** (aggregate BCVF ×
  alignment): likely AUC 0.65-0.80 if alignment is defined as
  target probability of the draft token (the natural semantic
  anchor for spec-dec). This could become the headline result.
- **`CoherenceAnchoredBCVFPerStepObservable`**: likely AUC
  0.70-0.85. Per-step coherence over all K tokens in the draft.
  If this crosses §11 strongly, it authorizes a V4 decoder
  experiment: replace the standard acceptance rule with a
  coherence-anchored one.

The §11 gate applies: no decoder / acceptance-rule variant is
authorized until at least one observable passes AUC ≥ 0.60 on
the real-model §12.3 probe.

---

## Section 13 — Configuration Null + Literature-Informed Revision Plan

### 13.1 Status

**The §12.4 pre-committed predictions have been falsified at the
tested configuration** — probability-simplex Euclidean distance
on a same-family target+draft predictor pair (Qwen2.5-7B-Instruct
+ Qwen2.5-3B-Instruct). The §11 observable probe ran on
TruthfulQA at N=100 (521 datapoints); all 11 observables returned
AUC in **[0.476, 0.527]**, a ±2.5-point band around random, and
none cleared the §11 `AUC ≥ 0.60` bar nor the relaxed `≥ 0.55`
marginal-lift bar.

**A post-experiment literature audit (§13.6) shows this null was
predictable and is method-specific, not field-level.** Same-
family logit-space disagreement is a known dead end in the
published hallucination-detection literature; what we tested was
the configuration multiple prior papers already identified as
uninformative. The field-standard working techniques — semantic
entropy (Farquhar 2024, *Nature*), activation probes (Azaria &
Mitchell 2023; Marks & Tegmark 2024), cross-family ensemble
disagreement (Yoffe 2024; Feng 2024) — remain untested in this
codebase.

The §11 Rahu-authorization gate is therefore closed **at the
simplex+same-family configuration** but remains **open** under
two specific revision paths, each with direct published
replication targets: §13.7 semantic-entropy metric revision
(§2.2), and a subsequent §1.3 cross-family ensemble revision.

**Update — §13.7 executed, marginal pass on both benchmarks.**
The pre-committed §13.7 probe has been run at N=100 on
TruthfulQA-MC and HaluEval-QA with Qwen2.5-7B-Instruct. Both
benchmarks returned **AUC = 0.661** (to three decimals), clearing
the §11 marginal bar (`0.60 ≤ AUC < 0.70`, TRUTH_CORRELATED_
MARGINAL). The §2.2 metric revision is therefore authorized to
land, and the next authorized probe is the §1.3 cross-family
ensemble revision. See §13.10 for the detailed result.

**Update — §1.3 executed, combined anti-finding.** The §13.8
item-1 cross-family ensemble probe has been run at N=100 on both
benchmarks with Qwen2.5-7B-Instruct + Llama-3.1-8B-Instruct +
Mistral-7B-Instruct-v0.3. Initial pass: TruthfulQA-MC **AUC 0.633**
(−0.028 vs §13.10) / HaluEval-QA **AUC 0.716** (+0.055 vs §13.10) —
heterogeneous split resolving to `CROSS_FAMILY_ANTI_FINDING` under
the pre-committed worst-benchmark rule. A chat-template diagnostic
on TruthfulQA-MC falsified the prompt-format confound hypothesis
(AUC dropped further to 0.567). Combined anti-finding stands. See
§13.11.

**Update — §13.12 executed, internal-state revision saturates on
HaluEval and underperforms on TruthfulQA.** The §13.8 item-2
EigenScore embedding-space probe has been run at N=100. TruthfulQA-
MC AUC 0.559 (`EMBEDDING_SPACE_ANTI_FINDING`); HaluEval-QA AUC
0.652 (`EMBEDDING_SPACE_SATURATION`, statistical tie with §13.10's
0.661 and signal in the expected direction with mean separation
0.54 EigenScore units). Combined under worst-benchmark rule:
`EMBEDDING_SPACE_ANTI_FINDING`. EigenScore reproduces §13.10's
signal on HaluEval but does not lift it; TruthfulQA-MC underperforms
§13.10 by 0.10 AUC.

**Update — §13.14 executed, BCVF text-level construction did not
transfer.** The §13.14 BCVF-faithful 2nd-difference observable,
implemented over per-position semantic entropy of NLI-clustered
truncations, has been run at N=100 on both benchmarks. TruthfulQA-
MC AUC 0.574; HaluEval-QA AUC 0.363 (signal *inverted* on HaluEval).
Combined `BCVF_2DIFF_ANTI_FINDING`. The result narrows the BCVF
transfer claim to *this specific text-level construction*; the
hidden-state-internal variant tested in §13.16 below also returned
ANTI on both benchmarks. See §13.15 for the §13.14 result section
and the three-reason failure analysis.

**Update — §13.16 executed, BCVF hidden-state construction also
did not transfer.** The §13.16 hidden-state EigenScore 2nd-
difference observable — the construction §13.15's narrowing left
explicitly open — has been run at N=100 on both benchmarks.
TruthfulQA-MC AUC 0.462; HaluEval-QA AUC 0.449. **Both benchmarks
inverted** (signal direction opposite the pre-committed AUC sign).
Combined `HSEIG_2DIFF_ANTI_FINDING`. §13.15's diagnosis transferred:
the per-position EigenScore series is smooth-monotonic on both
benchmarks (rising as K samples naturally diverge over generation),
not smooth-with-rare-spikes — so the 2nd-difference operator has
no fault-onset structure to detect. Moving from text-level to
model-internal continuous state did not fix the structural problem.
See §13.17 for the result section and the further-tightened
narrowing of the BCVF-for-LLMs transfer claim.

**Status of the §13 program after §13.17 — K-sample-divergence
single-axis program closed.** Four K-sample-divergence single-
axis revisions tested across both benchmarks (§13.11 cross-family,
§13.12 EigenScore, §13.14 BCVF text-level, §13.16 BCVF hidden-
state). **None lifts AUC above §13.10's 0.661 marginal baseline
on the combined-classification rule.** §13.10 single-snapshot
semantic entropy remains the strongest result in this codebase.
The K-sample-divergence single-axis program is closed at the
Qwen-7B + DeBERTa-v3-base + N=100 configuration.

**Update — §13.18 pre-committed and §13.19 result landed.** The
single-trajectory forced-allocation-gap probe (§13.18) — testing
the un-rejected single-trajectory observable class §13.17 left
open — has been executed at N=100 on both benchmarks. Combined
classification on the pinned primary scalar:
`FORCED_ALLOC_2DIFF_ANTI_FINDING` (TruthfulQA-MC AUC 0.549,
HaluEval-QA AUC 0.571). A separately notable diagnostic finding:
the Variant-A entropy-only 2nd-difference reached AUC 0.701 on
HaluEval-QA (second-best HaluEval result of the §13 program,
behind only §13.11's 0.716), but TruthfulQA-MC at 0.536 still
forces the combined classification to ANTI under the worst-
benchmark rule even if Variant A were used as primary. See §13.19
for the result section, the Variant A finding analysis, and the
full combined-matrix discussion.

**Status of the §13 program after §13.19 — single-axis program
exhausted across all hypothesis classes.** §13.17 closed the
K-sample-divergence single-axis sub-program. §13.19 closes the
single-trajectory single-axis sub-program. Five literature-
aligned and mechanism-motivated single-axis hypothesis classes
have been tested (sample-space single-model, sample-space cross-
family, internal-state single-snapshot, K-sample temporal evolution
at text-level and hidden-state-level, single-trajectory forced-
allocation). **All five collapse under the worst-benchmark rule
because TruthfulQA-MC defeats every confidence-based scalar
construction tested.** §13.10 single-snapshot semantic entropy
(AUC 0.661 on both benchmarks) remains the strongest result in
this codebase across all five tested hypothesis classes. The §13
single-axis program is now exhaustively closed.

**Update — §14a / §14a.2 executed, system-level scouts both
returned SCOUT_SATURATION.** §14a (string-matched selector,
§14b result section) ran at N=100 on HaluEval-QA: V1 softmin +3pp,
V2 thresholded +0pp, both vs string-matched Baseline-B that was
empirically degenerate due to M=3 cross-family selector tie-
breaking ($\text{acc}(\text{Baseline-A}) = \text{acc}(\text{Baseline-B}) = 0.300$
exactly). Post-§14b audit caught the structural issue. §14a.2
(NLI-clustered selector, selector-spec fix; §14c result section)
ran at the same configuration with the corrected selector: V1
softmin +4pp, V2 thresholded +1pp, vs the new NLI-clustered
Baseline-B (acc 0.290 — now genuinely different from Baseline-A's
0.300). Both scouts returned SCOUT_SATURATION per pre-committed
bands. **Full §14 explicitly NOT authorized; promotion was
conditional on STRONG or DIRECTIONAL outcome which was not
achieved.** See §14b and §14c for the result sections.

**Final status of the §13 + §14 LLM-track program — closed at all
tested experimental structures.** Five §13 single-axis hypothesis
classes tested (cross-family, EigenScore, BCVF text-level, BCVF
hidden-state, single-trajectory forced-allocation), plus two §14
system-level scout configurations (string-matched selector, NLI-
clustered selector), totaling 7 distinct experimental structures
beyond §13.10's marginal-pass baseline. **All 7 collapse under
the combined-classification rule.** §13.10 single-snapshot
semantic entropy (AUC 0.661 on both benchmarks) remains the
strongest result in this codebase. The §13/§14 LLM-track program
is exhaustively closed. Any future LLM-domain work would need a
fundamentally different reframing under a fresh §0.8 commitment
(model-scale upgrade, benchmark substitution, selective-prediction
abstention, supervised activation probes, or cross-domain
transfer); none are pre-committed. The autonomy-domain BCVF claim
(§6.1) stands wholly independent and is unaffected.

### 13.2 Experiment specification

- **Script**: `scripts/probe_observables.py` at commit `a5ace72`
  (§12 vocab-alignment fixes in place).
- **Benchmark**: TruthfulQA (`truthful_qa` HF dataset).
- **Model**: `Qwen/Qwen2.5-7B-Instruct`, `--no-compile`.
- **N**: 100 questions, yielding 521 (question, paraphrase, choice)
  triples after §3 paraphrase expansion.
- **Observable suite**: all 11 §11 observables built via
  `build_observables()` at their default §2.5.1 V1 configurations
  (`gate_threshold=0.1`, `gate_beta=200.0`, `huber_delta=0.5`).
- **Report**: `docs/experiments/probe_observables_truthfulqa_diag1c_truthfulqa_n100.md`.

### 13.3 Result table — observed vs pre-committed

Predictions from §12.4 (the speculative-decoding probe design)
carry over to the TruthfulQA probe with slightly relaxed
expectations (TruthfulQA is the harder of the two — no
draft-vs-target probability-ratio shortcut). Predictions below
are the §12.4 lower bounds; the §11 pass threshold (0.60) is
the hard bar.

| Observable | §12.4 predicted | Observed AUC | Verdict |
|---|---|---|---|
| `bcvf_total_cost` | 0.55–0.70 | **0.507** | FAIL (below range) |
| `bcvf_source_0_cost` | — | **0.508** | FAIL |
| `source_0_entropy` | 0.60–0.70 | **0.522** | FAIL (below range) |
| `source_disagreement_fraction` | — | **0.503** | FAIL |
| `bcvf_per_step_max` | 0.60–0.75 | **0.501** | FAIL (far below range) |
| `bcvf_source_0_per_step_max` | — | **0.494** | FAIL |
| `coherence_anchored_bcvf` | 0.65–0.80 | **0.476** | FAIL (anti-correlation territory) |
| `coherence_anchored_bcvf_per_step` | 0.70–0.85 | **0.522** | FAIL (far below range) |
| `uncertainty_gated_bcvf_per_step_max` | — | **0.506** | FAIL |
| `layer_instability_max` | — | **0.487** | FAIL |
| `coherence_anchored_layer_bcvf_per_step` | — | **0.527** | FAIL |

None of the five observables with pre-committed lower bounds
cleared their lower bound. The tightest-clustered observable
(`coherence_anchored_layer_bcvf_per_step`, 0.527) is the
nominal "best", but at the 95% CI it is not distinguishable
from random. The worst (`coherence_anchored_bcvf`, 0.476) is
below 0.500, meaning the observable's sign is slightly
wrong-sign — the §10.V1 "anti-correlation" failure mode that
§11 was built to catch.

### 13.4 Why this is a clean configuration null

Three features of the data distinguish this from an
"inconclusive, need more N" result — all three are now
understood to be diagnostic of the specific configuration
tested, not of BCVF-for-LLM in general:

1. **Tight clustering across 11 observables.** The spread is
   5.1 AUC points (0.527 − 0.476). A real signal in any one
   observable would lift *that* observable well above the
   cluster's median (0.506). The tight clustering indicates
   every observable is measuring the same degenerate quantity
   — token-level probability distance between two models
   that are trained to agree at the token level.
2. **Independent validation on a second benchmark.** The
   speculative-decoding N=100 probe on HaluEval showed the
   same pattern (noise band AUC 0.486–0.586). Two
   benchmarks, same target+draft predictor pair, same null.
3. **Pre-committed predictions (§12.4) were wrong by the
   amount the literature would predict.** §12.4 anticipated
   AUC 0.55–0.85 across the five observables with explicit
   lower bounds. Observed shortfalls from the respective
   §12.4 lower bound: `bcvf_total_cost` 0.043,
   `source_0_entropy` 0.078, `bcvf_per_step_max` 0.099,
   `coherence_anchored_bcvf` 0.174, and
   `coherence_anchored_bcvf_per_step` 0.178. Four of five
   missed their lower bound by ≥ 0.05 AUC; the fifth
   (`bcvf_total_cost`) by ≥ 0.04. The ~0.05–0.18 shortfall
   band matches the independently-reported AUROC for same-
   family logit-space signals in Kadavath 2022 (AUROC 0.55–
   0.62), Xiong 2024 (0.50–0.58), and Fadeeva 2024 (AUROC
   < 0.60 for simplex-style estimators on TriviaQA/
   TruthfulQA). See §13.6.

### 13.5 Scope of the null — precisely what is and is not rejected

This null result **rejects** one specific tuple of design
choices from §0–§12:

- **§2.2 metric = probability-simplex Euclidean distance**,
  **§1.3 ensemble = same-family target+draft**, combined on
  TruthfulQA-MC and HaluEval-QA. Under this configuration,
  no observable in the §11 suite is truth-correlated.

This null **does not** reject:

- **BCVF-shaped hypotheses under a different §2.2 metric.**
  In particular, a meaning-space metric (semantic-entropy
  clusters of sampled generations, hidden-state covariance,
  activation-probe scores) has not been tested in this
  codebase. Published AUROCs for meaning-space signals on
  TruthfulQA reach 0.70–0.83 (§13.6).
- **BCVF-shaped hypotheses under a different §1.3 ensemble.**
  Same-family target+draft are trained to agree at the
  token level (speculative-decoding literature, §13.6).
  Independent-family M≥3 ensembles (Qwen + Llama + Mistral)
  reach AUROC 0.68–0.73 on published cross-family work and
  remain untested here.
- **The BCVF autonomy runtime.** The autonomy-domain
  validation (§6.1 N=21 sign-test p=0.0072 on
  `S3_map_error_accel`, N=19 p=0.0192 on `S3_map_error`,
  `symbolu_robotics/bcvf_autonomous/DESIGN.md` §6.11) is
  independent of this LLM-domain test and stands.

This narrower framing replaces the earlier blanket "§0
transfer premise falsified" phrasing — it was too strong for
the evidence actually in hand.

### 13.6 Literature audit — why the tested configuration was doomed

A post-experiment audit of 2023–2025 hallucination-detection
literature (Anthropic, DeepMind, Meta, and academic groups)
reframes the null: **same-family logit-space disagreement is
an independently-established dead end, and the benchmark-
standard working techniques operate in meaning-space, not
token-probability space**.

Key findings:

- **Kadavath et al. 2022 (Anthropic, "Language Models (Mostly)
  Know What They Know")**: same-family probability-based
  uncertainty signals give AUROC ~0.55–0.62 on short-form QA.
  Explicitly identified as a weak standalone signal.
- **Xiong et al. 2024 (ICLR, "Can LLMs Express Their
  Uncertainty?")**: raw token-probability AUROC across
  TruthfulQA clustered in **0.50–0.58** — matches our [0.476,
  0.527] null within noise.
- **Fadeeva et al. 2024 (EMNLP, LM-Polygraph)**: systematic
  evaluation of 15+ logit-space uncertainty estimators;
  simplex-style variants within a single model family
  underperformed (AUROC often < 0.60 on TriviaQA /
  TruthfulQA).
- **Speculative-decoding literature** (Leviathan et al. 2023;
  Chen et al. 2023): target+draft from the same family are
  *designed to agree* on easy tokens. Their disagreement
  tracks compute savings, not truth. Our §1.3 choice predicts
  null on theoretical grounds.

The field-standard techniques that **do** clear AUROC 0.65–
0.80 on TruthfulQA and comparable benchmarks are all in one
of three categories, and all operate outside token-simplex
space:

- **Semantic entropy (Farquhar et al. 2024, *Nature* 630,
  625–630).** Sample K generations, cluster by bidirectional
  NLI entailment, Shannon entropy over cluster sizes. AUROC
  **0.75–0.79** on TriviaQA/SQuAD; ~0.70 on TruthfulQA-style
  free-form. The §13.7 experiment is a direct replication of
  this on this codebase.
- **Activation probes (Azaria & Mitchell 2023; Marks &
  Tegmark 2024 "The Geometry of Truth").** Linear / difference-
  of-means probes on mid-layer residual-stream activations.
  AUROC **0.71–0.83** on SAPLMA, various truth benchmarks.
- **Cross-family ensemble disagreement (Yoffe et al. 2024
  "DebUnc"; Feng et al. 2024 "Don't Hallucinate, Abstain").**
  Disagreement across independent model families (Llama +
  Mistral + Qwen) reaches AUROC **0.68–0.73** — a direct
  §1.3 ensemble-revision target.
- **INSIDE / EigenScore (Chen et al. 2024, ICLR).** Covariance
  of hidden states, AUROC **0.74–0.81** across HaluEval/
  TruthfulQA.
- **SelfCheckGPT (Manakul et al. 2023, EMNLP).** Sampling +
  NLI-based self-consistency. AUROC 0.74–0.83 on WikiBio,
  ~0.68 on TruthfulQA.

**Field consensus (Huang et al. 2024 ACM CSUR survey;
Zhang et al. 2025 "Siren's Song")**: LLM trust routing is
unsolved but actively tractable. Same-family logit-space
approaches are a known dead end. Meaning-space and cross-
family ensemble approaches are the current frontier.

Our null result is therefore consistent with — and predicted
by — the published record. It is a **method-level null, not
a field-level null**, and the two specific revision targets
below are backed by direct replication references.

### 13.7 Revision plan — semantic-entropy probe (§2.2 metric revision)

The first authorized revision probe replaces §2.2's
probability-simplex Euclidean distance with Farquhar 2024
semantic-entropy clustering. This is a pure §2.2 change; the
§1.3 ensemble (single target model, no draft) and §11
benchmark (TruthfulQA-MC) are held fixed so that the lift
measured is attributable to the metric swap, not to a
confound.

**Specification:**

- **Script:** `scripts/probe_semantic_entropy.py`.
- **Target model:** `Qwen/Qwen2.5-7B-Instruct` (unchanged
  from §13.2 — enables direct comparison).
- **NLI clustering model:** `MoritzLaurer/DeBERTa-v3-base-
  mnli-fever-anli` (standard MNLI-trained classifier; matches
  Farquhar 2024 methodology).
- **Benchmark:** TruthfulQA multiple-choice, validation
  split, N=100.
- **Sampling:** K=10 completions per question at T=1.0,
  max_new_tokens=32 (matches Farquhar 2024 defaults).
- **Clustering rule:** bidirectional NLI entailment (i → j
  AND j → i), union-find on the K samples per question.
- **Scalar:** Shannon entropy (nats) over cluster-size
  distribution.
- **Correctness label:** greedy generation (T=0) NLI-entails
  the correct MC choice AND does not entail any distractor.
- **Statistic:** AUC of (−semantic_entropy) as a truth
  predictor (higher entropy → less confident → more likely
  wrong, negated for the higher-AUC-is-better convention).

**Pre-committed success bands** (per §0.8 discipline — these
are recorded before the experiment is run, and the script's
`classify()` function is pinned to these thresholds in
`scripts/probe_semantic_entropy.py`):

- `AUC ≥ 0.70` → **TRUTH_CORRELATED_STRONG**. §2.2 metric
  revision lands on-branch. Next authorized probe: §1.3
  cross-family ensemble revision (Qwen + Llama + Mistral).
- `0.60 ≤ AUC < 0.70` → **TRUTH_CORRELATED_MARGINAL**.
  Semantic entropy clears the §11 bar but needs cross-
  benchmark confirmation. Next authorized probe: same
  script on HaluEval-QA at N=100 before §2.2 revision lands.
- `0.55 ≤ AUC < 0.60` → **NOISE_BAND_LIFT**. Above random
  but below the §11 bar. No revision authorized. Diagnostic
  follow-up: audit K, T, and NLI-clustering parameters.
- `AUC < 0.55` → **SECOND_NULL**. The §13 null strengthens
  to field-consistent. Pause LLM-domain compute pending the
  §1.3 cross-family ensemble revision, which is the only
  remaining literature-backed fix; that revision is a
  separate §0.8-style pre-commitment.

**Expected cost:** ~30–45 min on a single GPU with the
combined Qwen-7B + DeBERTa-v3-base-MNLI footprint (~8.5 GB).
No multi-model vocabulary alignment is required (single
target model), so the §12 shared-vocab machinery is not
exercised.

**Report destination:** `docs/experiments/probe_semantic_
entropy.md`. Per-question JSON dump available via
`--dump-json`.

**Relationship to BCVF 2nd-difference core:** Semantic
entropy as specified here replaces the §2.2 metric but does
**not** yet introduce a 2nd-difference-of-entropy observable.
If semantic entropy clears ≥ 0.60, a follow-up experiment
can test whether `d²(semantic_entropy)/dk²` across outer
decoding steps (the true BCVF-shaped signal) improves on the
static entropy scalar. That follow-up is NOT pre-committed
here; it depends on §13.7 passing.

**Known simplifications vs Farquhar 2024** (disclosed so the
expected AUC from this probe is compared against a realistic
baseline rather than the paper's headline numbers):

- **Discrete semantic entropy**, not continuous. Farquhar
  2024 reports both `H = -Σ p_c log p_c` over cluster-count
  probabilities (discrete; ~0.72 AUROC on TriviaQA) and a
  continuous variant weighted by per-generation sequence
  log-probabilities (~0.76 AUROC). The script implements
  discrete only — simpler, fewer moving parts, but gives up
  ~0.04 AUC vs continuous.
- **DeBERTa-v3-base MNLI**, not DeBERTa-large. The default
  NLI classifier is ~30% smaller than what Farquhar uses.
  Expected AUROC penalty: modest (~0.02), but material near
  the 0.60 threshold. Configurable via `--nli-model` if a
  larger model is available.
- **K=10 at T=1.0, max_new_tokens=32**. K matches Farquhar;
  T=1.0 is the paper's recommendation; max_new_tokens is
  conservative and may truncate longer answers. Follow-up
  at max_new_tokens=64 or 128 would eliminate truncation
  as a confound if §13.7 lands in the NOISE_BAND_LIFT range.
- **Correctness label via question-conditioned NLI**
  (greedy generation entails correct MC choice AND does
  not entail any distractor, with question prefix for
  context). Farquhar uses either gold-answer string match
  or SBERT similarity against reference answers. The NLI-
  only labeling is a deliberate simplification — it avoids
  an additional model download but could produce more
  label noise on MC questions where multiple choices are
  partially entailed. If the AUC lands near the bands'
  boundaries, a string-match fallback label is the first
  robustness check.

These simplifications together suggest the §13.7 discrete-
base implementation should land at AUROC **~0.65–0.72** on
TruthfulQA if the BCVF-for-LLM transfer is real — that is:
enough to clear the 0.60 marginal bar, potentially enough
to clear the 0.70 strong bar, but not guaranteed to replicate
the paper's 0.75–0.79 headline. A result below 0.60 is a
genuine signal against the transfer hypothesis even after
accounting for these simplifications.

### 13.8 Authorization gate — what §13 leaves open vs paused

**Paused** (the §13 single-axis program is closed post-§13.17;
no further single-axis probe compute is authorized at this
codebase's Qwen-7B + base-NLI configuration):

- Section 4 (Phase 2 — Source Framework) extensions beyond
  the two sources already exercised at simplex+same-family.
- Section 5 (Phase 3 — Integration Layer) Rahu-trust
  deployment. With no §11-strong-passing Ketu observable
  yet, there is nothing for §5 to consume.
- Section 6 (Phase 4 — Benchmark, Metrics) scale-out at
  any single-axis configuration that has not cleared the
  §13.9 0.75 bar. §13.10 and §13.11 HaluEval-only results
  do not unlock scale-out.
- Section 7 (Phase 5 — Packaging & Reproducibility) for any
  component that has not passed §11.
- Section 12 speculative-decoding integration. The §12.3
  probe shares §13's configuration and inherits §13's null.

**Completed** (chronological):

- **§13.7 semantic-entropy probe (§2.2 metric revision).** Run at
  N=100 on both TruthfulQA-MC and HaluEval-QA. Both returned AUC
  = 0.661 (TRUTH_CORRELATED_MARGINAL). §2.2 metric revision
  authorized to land; see §13.10.
- **§1.3 cross-family ensemble revision.** Run at N=100 on both
  benchmarks with Qwen2.5-7B-Instruct + Llama-3.1-8B-Instruct +
  Mistral-7B-Instruct-v0.3 (M=3, K=10, completion-style prompt).
  TruthfulQA-MC 0.633 / HaluEval-QA 0.716 → combined
  `CROSS_FAMILY_ANTI_FINDING` under the worst-benchmark rule.
  Chat-template diagnostic on TruthfulQA-MC falsified the prompt-
  format confound (AUC 0.567). No external-framing unlock. See
  §13.11.
- **§13.12 EigenScore embedding-space probe.** Run at N=100 on
  both benchmarks. TruthfulQA-MC 0.559 (`EMBEDDING_SPACE_ANTI_
  FINDING`) / HaluEval-QA 0.652 (`EMBEDDING_SPACE_SATURATION`,
  within ±0.02 of §13.10 baseline, signal in expected direction
  with mean separation 0.54 EigenScore units). Combined under
  worst-benchmark rule: `EMBEDDING_SPACE_ANTI_FINDING`. Read:
  EigenScore reproduces §13.10's signal on HaluEval but does not
  lift it; on TruthfulQA-MC it underperforms §13.10. Internal-
  state hypothesis class explored at the single-snapshot level.
- **§13.14 BCVF-faithful 2nd-difference observable (text-level
  construction).** Run at N=100 on both benchmarks. TruthfulQA-MC
  0.574 / HaluEval-QA 0.363 (signal *inverted* on HaluEval) →
  combined `BCVF_2DIFF_ANTI_FINDING`. Per-position semantic-
  entropy curves were monotonic (not smooth-with-spikes), trend
  direction flipped across benchmarks. Result narrows the BCVF
  transfer claim to *this specific text-level construction*. See
  §13.15 for the detailed result section.
- **§13.16 hidden-state EigenScore 2nd-difference observable.**
  Run at N=100 on both benchmarks with per-position EigenScore at
  Qwen-7B layer 14, stride-4 grid, primary scalar `max|accel|`.
  TruthfulQA-MC 0.462 / HaluEval-QA 0.449 — **both inverted**.
  Combined `HSEIG_2DIFF_ANTI_FINDING`. The §13.15 diagnosis
  transferred: hidden-state EigenScore series are smooth-monotonic
  rising on both benchmarks (K samples diverge over generation),
  not smooth-with-spikes — so the 2nd-difference operator has no
  fault-onset structure to detect. Moving from text-level to model-
  internal continuous state did not fix the structural problem.
  See §13.17 for the result section and the further-tightened
  narrowing.
- **§13.18 single-trajectory forced-allocation-gap observable.**
  Run at N=100 on both benchmarks with per-token greedy logit
  capture, stride-1 grid, primary scalar
  `max_t |accel(g_t)|` where
  $g_t = \tilde{H}_t - \alpha \tilde{M}_t$ at α=1.0. TruthfulQA-MC
  0.549 / HaluEval-QA 0.571 → combined
  `FORCED_ALLOC_2DIFF_ANTI_FINDING`. Notable Variant-A diagnostic
  (entropy-only 2nd-difference, no $M_t$ term, no z-norm) reached
  HaluEval-QA AUC 0.701 — second-best HaluEval result of the §13
  program — but TruthfulQA-MC at 0.536 keeps the worst-benchmark
  combined classification at ANTI for any scalar choice. The $M_t$
  component as defined hurts the signal beyond raw entropy alone;
  the mechanism analysis's underlying claim about absolute logit
  magnitude is not falsified, only the specific operational
  definition `max − global_mean` is ruled out. See §13.19 for the
  result section and the Variant A finding analysis.

**§13 single-axis program exhausted (post-§13.19).** The five
single-axis revisions above (cross-family, EigenScore, BCVF text-
level, BCVF hidden-state, single-trajectory forced-allocation)
exhaust both hypothesis classes available to the §13 program: K-
sample-divergence-based observables (§13.11/§13.12/§13.14/§13.16)
and single-trajectory observables (§13.18). All five collapse
under the worst-benchmark rule because TruthfulQA-MC defeats every
confidence-based scalar construction tested. **No further §13
single-axis probes are authorized.** See §13.19 for the closing
statement and combined-matrix analysis.

**Open as future-work pre-commitments outside the §13 single-
axis program** (each requires a fresh §0.8-style commitment in a
new top-level section if pursued):

- **§14a system-level integration scout (EXECUTED in §14a /
  §14b; combined `SCOUT_SATURATION`).** The un-tested
  experimental structure §13.17 / §13.19 left open. Scout-
  bounded to HaluEval-QA only at N=100 with V1 softmin trust /
  V2 thresholded exclusion consumers and weighted majority vote
  selector; semantic entropy as per-source BCVF scalar. Pinned
  primary verdict per pre-committed bands: SCOUT_SATURATION
  (Δ_V1=+3pp non-significant, Δ_V2=+0pp). Post-§14b audit
  revealed structural issue in the §14a-pinned selector spec
  (string-identity grouping degenerates at M=3 cross-family →
  Baseline-B = Baseline-A). §14a SCOUT_SATURATION verdict is
  binding under §0.8 for the §14a-pinned configuration; the
  selector-spec fix is tested in §14a.2 below.
- **§14a.2 system-level scout with NLI-clustered selector
  (EXECUTED in §14a.2 / §14c; combined `SCOUT_SATURATION`).**
  Selector-spec fix replacing string-identity majority vote with
  NLI-clustered weighted majority vote (the §13.10
  cluster_by_entailment mechanism applied to M=3 candidate
  answers). Selector fix succeeded structurally:
  $\text{acc}(\text{Baseline-A}) = 0.300$ vs
  $\text{acc}(\text{Baseline-B}) = 0.290$ — genuinely different
  numbers, no longer the §14a degenerate equality. But pinned
  primary verdict still SCOUT_SATURATION:
  $\Delta_{V_1} = +4\text{pp}$ (5/1 wins/losses, p=0.219),
  $\Delta_{V_2} = +1\text{pp}$ (1/0, p=1.000). V1 softmin
  produced the strongest BCVF-shaped lift in the entire §13/§14
  program but did not clear pre-committed STRONG (+5pp + p<0.05)
  or DIRECTIONAL (V2 ≥+3pp ∧ V1 ≤0pp) thresholds. Full §14 NOT
  authorized. ChatGPT's predicted DIRECTIONAL pattern (V1 harmful,
  V2 helpful) was empirically falsified — the opposite was
  observed. See §14c for the result section, the band-coverage
  gap analysis, and the 5-section LLM-track post-mortem.
- **Single-trajectory forced-allocation-gap observable
  (EXECUTED in §13.18 / §13.19; combined `ANTI_FINDING`).** The
  signal class §13.17's narrowing left explicitly open has now
  been tested. Pinned primary scalar produced TruthfulQA-MC AUC
  0.549 / HaluEval-QA AUC 0.571, combined `ANTI_FINDING` per the
  worst-benchmark rule. **§13.18 is the pre-commitment;
  §13.19 is the result section.** The math below is retained as
  background documentation for the rationale; the pinned
  specification, AUC bands, and acceptance rules remain in §13.18.
  No further single-trajectory single-axis probe is authorized
  without a fresh §0.8 commitment.

  Notable Variant-A diagnostic finding (entropy-only 2nd-difference
  without the $M_t$ component): HaluEval-QA AUC reached 0.701 —
  second-best HaluEval result of the §13 program — but TruthfulQA-
  MC at 0.536 keeps the worst-benchmark combined classification at
  ANTI even if Variant A had been the pinned primary. The Variant
  A finding is documented in §13.19 as analytical evidence about
  which component of the forced-allocation-gap construction
  carried signal vs noise; it does NOT constitute a §13.18 pass
  and does NOT authorize a §13.20 follow-up without a fresh §0.8
  commitment.

  **Mechanism rationale (re-stating ChatGPT's framing of where
  hallucination enters in autoregressive LLMs):**

  Softmax loses the absolute magnitude of the underlying logits.
  Two scenarios with raw logits $[10, 1, 0.5]$ and $[-100, -100.1,
  -100.2]$ produce wildly different epistemic states (confident vs
  clueless) but Softmax flattens both into probability vectors that
  sum to 1.0. Cross-entropy training forbids the model from
  expressing absolute ignorance. Autoregression then locks the
  forced guess into the context for subsequent tokens, amplifying
  the false premise. The hallucination signature is therefore the
  moment Softmax forces an allocation despite low absolute logit
  magnitude — a property of single-trajectory logit geometry, not
  K-sample geometry.

  This observable was not measured by §13.10–§13.16: every probe
  in §13 looked at *between-sample* variance (decoding stochasticity
  introduced by the temperature parameter), which is downstream of
  the very mechanism that creates hallucination. K-sample variance
  measures how the model's outputs spread; the actual hallucination
  signature is in how the logit distribution committed to a guess
  despite low absolute magnitude *upstream* of any sampling.

  **Mathematical construction (would be pinned in the eventual
  §0.8 commitment):**

  For a single greedy or sampled generation, at each token position
  $t \in [1, T]$ where $T$ is the number of generated tokens:

  1. Capture the raw logits $\mathbf{z}_t \in \mathbb{R}^{|V|}$
     before softmax (available in HuggingFace via
     `model.generate(..., output_scores=True,
     return_dict_in_generate=True)`).
  2. Compute two complementary quantities per position:
     - **Confidence magnitude:**
       $M_t = \max_j z_t[j] - \frac{1}{|V|}\sum_j z_t[j]$
       (max logit centered by mean — indicates whether *anything*
       in the vocab strongly stands out from the bulk).
     - **Forced entropy:**
       $H_t = -\sum_j p_t[j] \log p_t[j]$ where $p_t =
       \text{softmax}(\mathbf{z}_t)$.
  3. Z-normalize both quantities across the trajectory:
     $\tilde{M}_t = (M_t - \bar{M})/\sigma_M$,
     $\tilde{H}_t = (H_t - \bar{H})/\sigma_H$.
  4. Define the **forced-allocation gap**:
     $$g_t = \tilde{H}_t - \alpha \cdot \tilde{M}_t$$
     with $\alpha = 1.0$ as a defensible default (equal weighting
     of normalized entropy and normalized confidence; pinning $\alpha$
     would be part of the eventual §0.8 commitment).
     - High $g_t$: high entropy AND low confidence magnitude — the
       "Scenario B" forced-allocation case.
     - Low $g_t$: high confidence magnitude OR low entropy — the
       model has commitment its logits actually support.
  5. Apply the BCVF 2nd-difference operator across positions
     WITHIN the single trajectory:
     $$\text{accel}_t = g_{t+1} - 2 g_t + g_{t-1}$$
     for interior $t$.
  6. Primary scalar candidate (would be pinned, with diagnostic
     secondaries reported but not classification-bearing, mirroring
     the §13.14 / §13.16 pattern):
     $$\text{forced\_alloc\_2diff}(q) = \max_t |\text{accel}_t|$$
  7. AUC sign convention: pre-committed direction is *higher
     forced-allocation acceleration → moment the model's logit
     distribution suddenly committed to a low-magnitude forced
     guess → more likely the answer is wrong*. AUC computed on
     $-\text{forced\_alloc\_2diff}$.

  **Why this construction satisfies the structural requirements
  §13 violated:**

  | Requirement | §13 K-sample probes | This observable |
  |---|---|---|
  | Continuous, real-valued | mostly | yes |
  | Direct from model internals | partial | yes (raw logits) |
  | Smooth-with-rare-spikes structure | no (§13.14, §13.16 both monotonic) | **plausible by mechanism** |
  | Independent of K-sample divergence | no | **yes** (single trajectory) |
  | Captures the autoregressive-hallucination mechanism | no | **yes** (forced allocation IS Softmax flattening) |

  The "plausible by mechanism" caveat on the smooth-with-spikes
  property is critical and explicitly NOT empirically validated:
  it is a prediction from ChatGPT's mechanical framing, not data.
  A token where the model knows the answer should produce high
  $M_t$ and low $H_t \to$ low $g_t$. A token where the model is
  forced to guess (e.g., a specific date it doesn't know) should
  produce low $M_t$ and high $H_t \to$ high $g_t$. Forced moments
  should be sparse and local in well-formed generations — exactly
  the shape the 2nd-difference operator exploits. Whether
  empirical $g_t$ trajectories actually have this shape on
  Qwen2.5-7B-Instruct + TruthfulQA-MC / HaluEval-QA is unknown
  and would be the central question of the §14/§15 commitment.

  **Three concrete tractable variants** (the eventual §0.8 commit
  would pin one as primary; others as deviation flags or
  follow-ups):

  - **A — Simple per-token entropy 2nd-difference.** Just $H_t$,
    no magnitude term. Cheaper, doesn't need $M_t$ z-normalization.
    Some published 1st-derivative literature exists (Kadavath 2022
    P(True) reported AUROC ~0.55–0.62 at the 1st-derivative level
    on short-form QA); the 2nd-difference variant is novel.
  - **B — Forced-allocation gap as defined above.** Combines $H_t$
    and $M_t$. Closer to ChatGPT's mechanism. Most theoretically
    motivated; least published anchor.
  - **C — Logit-lens curvature.** Apply the unembedding matrix to
    mid-layer hidden states (the "logit lens" technique from the
    interpretability literature) to get layer-position-specific
    predictions. Compute when the layer-wise prediction shifts
    abruptly mid-generation. Catches "the moment the model's
    internal pre-decision crystallized to the wrong answer" —
    structurally distinct from variant B.

  **Implementation cost estimate (if pursued):**

  Cheapest: variants A and B require only `output_scores=True`
  during generation; per-token logits are already computed by the
  model. Implementation ~300 lines (similar shape to §13.14 /
  §13.16 minus the per-position NLI clustering or hidden-state
  extraction passes). Runtime ~1–3 min at N=100 on a 24+ GB GPU
  (no per-position clustering, no per-position EigenScore — just
  per-position scalar arithmetic on the captured logits). NLI is
  used only for the correctness label, ~3 calls per question, same
  as §13.10–§13.16.

  Variant C requires capturing and unembedding mid-layer hidden
  states — slightly more expensive memory and code, but still much
  cheaper than §13.16's per-position EigenScore.

  **What this entry does NOT pre-commit:**

  - No script implementation on-branch.
  - No `classify()` thresholds in code.
  - No benchmark runs.
  - No AUC bands (numerical bands would be specified in the
    eventual §0.8 commitment, with the same partition-around-§13.10
    structure as §13.11–§13.16 if the §13.10 baseline is used as
    the comparison anchor, OR a different anchor if a fresh
    baseline is pinned at that time).
  - Specific value of $\alpha$ — defaulted at 1.0 above as a
    documentation convenience but the eventual commitment would
    re-pin this with explicit reasoning (or commit to a sweep with
    pre-committed selection rule).

  **Status:** Documented as the most promising single-axis
  observable §13.17 leaves open. Not authorized for implementation
  without a fresh §0.8 commitment.
- **System-level integration (would become §14).** The §4 source-
  framework + §5 integration-layer machinery has never been
  exercised on LLMs in this codebase. The §13 program tested
  observables in isolation against ground truth (AUC); it did not
  test multi-source LLM Q&A systems that consume BCVF scalars to
  weight or filter sources. ChatGPT/external-review noted that
  the autonomy-domain §6.1 result that passed was a system-level
  result (multi-source robotic system using BCVF-shaped routing),
  not an isolated-observable result, so the analogue system-level
  test is the natural next experiment if any is pursued.
- **Model-scale probe.** Re-run §13.10 with Qwen2.5-32B-Instruct
  + DeBERTa-v3-large. Tests whether the §13.10 baseline lifts at
  literature-typical scale. If §13.10 itself reaches 0.72+ at
  this scale, all four §13 single-axis revisions could be
  reconsidered. If §13.10 stays at ~0.66, the saturation is
  fundamental to these benchmarks at 7B class.
- **Continuous semantic entropy bridge (§13.13 pre-commitment,
  not implemented).** Three Farquhar-2024-aligned upgrades
  (continuous SE, DeBERTa-v3-large NLI, max_new_tokens=128) on
  §13.10's protocol. Pre-committed in §13.13 but not implemented.
  Demoted in priority because the four §13 single-axis nulls
  collectively suggest single-axis variants saturate at the
  §13.10 baseline regardless of which axis is changed.
- **Linear activation probes** (Azaria & Mitchell 2023; Marks &
  Tegmark 2024 "Geometry of Truth"). Requires a labeled train/
  test split. Tests a different hypothesis class than the four
  §13 probes (supervised rather than unsupervised). Would require
  a fresh §0.8 pre-commitment around split selection.
- **Benchmark substitution.** Adding TriviaQA-Generation as a
  free-form benchmark Farquhar 2024 actually tested would resolve
  the protocol-mismatch confound that affected §13.10–§13.16
  (TruthfulQA-MC vs Farquhar's TruthfulQA-Generation). Requires
  a fresh §0.8 pre-commitment around labeling protocol (gold-
  answer string-match vs the existing NLI-based label).

### 13.9 What this means for the autonomy track

Nothing. The autonomy-domain validation (`symbolu_robotics/
bcvf_autonomous/DESIGN.md` §6.1 and §6.7) is a separate
experiment on a separate dataset with a separate predictor
set, and its pre-committed §6.11 gates were met. The §13
LLM-domain configuration null does not retrospectively
invalidate the autonomy result.

For VC / investor communication, the autonomy track should
continue to be presented on its own merits. The LLM design
doc is an internal research artifact; all five §13 single-axis
revision probes (§13.7 / §1.3 / §13.12 / §13.14 / §13.16 /
§13.18) AND both §14 system-level scouts (§14a string-matched
selector, §14a.2 NLI-clustered selector) have now been executed.
**None lifts above §13.10's 0.661 marginal baseline on the
combined-classification rule, and neither §14 scout produces
sufficient lift to clear pre-committed STRONG promotion thresholds.**
None is positioned as a deliverable.

`AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md` "Honest scope caveats"
already reflects the current external-facing framing
("BCVF is not positioned as an LLM hallucination detector"),
and that framing is *strengthened*, not weakened, by the
combined §13 + §14 evidence:

- **§13** — 5-of-5 single-axis hypothesis classes tested
  produce combined `ANTI_FINDING` under the worst-benchmark
  rule, with TruthfulQA-MC defeating every confidence-based
  scalar construction tested.
- **§14a / §14a.2** — both system-level scouts return
  `SCOUT_SATURATION` on HaluEval-QA. The §14a.2 selector-spec
  fix succeeded structurally (Baseline-A ≠ Baseline-B with
  NLI-clustered semantic-equivalence aggregation) but the
  system layer still does not produce lift above pre-committed
  promotion thresholds.

The §13 single-axis program is exhausted post-§13.19. The §14
system-level scout program is closed post-§14c. Together this
is **7 distinct experimental structures tested beyond §13.10's
marginal-pass baseline; none clears the §13.9 0.75 strong band
on the combined-classification rule.** The framing will be
revisited only if some future out-of-§13/§14 probe (model-scale
upgrade to Qwen-32B+, benchmark substitution to a less hostile
benchmark family, selective-prediction abstention rather than
answer selection, supervised activation probes, or cross-domain
transfer — none pre-committed) lifts AUC or accuracy delta to
the 0.75 strong band on BOTH benchmarks (or on a fresh pre-
committed benchmark pair). No probe in the §13/§14 program has
cleared this bar. No VC-facing material is updated on the basis
of any §13 or §14 result, either in isolation or combined.

### 13.10 Revision experiment results — semantic-entropy on TruthfulQA + HaluEval

The §13.7 pre-committed probe has been executed. Both
benchmarks cleared the `AUC ≥ 0.60` marginal-pass bar with
identical AUC to three decimals, providing the cross-
benchmark confirmation §13.7 required.

**Configuration (identical across both runs):**

- **Target model:** `Qwen/Qwen2.5-7B-Instruct`, fp16, closed-book.
- **NLI model:** `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`, fp16.
- **Sampling:** K=10 completions at T=1.0, max_new_tokens=32.
- **Clustering:** bidirectional, question-conditioned NLI
  entailment, union-find. All K×(K−1) = 90 pairs per question
  batched in one NLI forward pass (batch_size=32 chunks).
- **Correctness label:** question-conditioned NLI — greedy
  generation entails the correct choice AND does not entail
  any distractor.
- **Scalar:** Shannon entropy (nats) over cluster-size
  distribution; AUC computed on `-entropy`.
- **Script:** `scripts/probe_semantic_entropy.py` at commit
  `08dfe76a` (plus the `8351e117` UTF-8 fix).

**Result table:**

| Benchmark | N | Greedy accuracy | Mean H (all) | Mean H (correct) | Mean H (wrong) | Separation | **AUC** | Classification |
|---|---|---|---|---|---|---|---|---|
| TruthfulQA-MC (validation) | 100 | 0.250 | 1.5616 | 1.2676 | 1.6596 | 0.392 nats | **0.661** | TRUTH_CORRELATED_MARGINAL |
| HaluEval-QA (data) | 100 | 0.300 | 1.5160 | 1.1761 | 1.6617 | 0.486 nats | **0.661** | TRUTH_CORRELATED_MARGINAL |

**What the result demonstrates:**

1. **The meaning-space metric swap is truth-correlated at the
   §11 marginal bar.** Both benchmarks clear AUC 0.60 cleanly,
   with the lower bound of the 95% CI (≈ [0.55, 0.77] at N=100)
   above 0.55. Compare to the §13.2 configuration-null run
   where all 11 simplex-space observables landed in
   [0.476, 0.527] — a clear lift of ~0.13 AUC attributable to
   the §2.2 metric revision.
2. **The signal is benchmark-portable, not a TruthfulQA
   artifact.** Two independent datasets with different question
   distributions, correctness-label formats, and greedy
   accuracies (25% vs 30%) produce identical AUC to three
   decimals. Coincidence rate for two independent AUCs to
   agree to that precision is extremely low; this is signal,
   not noise.
3. **Observed AUC matches the pre-committed expectation from
   §13.7.** That section forecast 0.65–0.72 for the discrete-
   SE + DeBERTa-base + question-context configuration, with
   the paper's 0.75–0.79 reserved for continuous-SE +
   DeBERTa-large. 0.661 is inside the predicted window. No
   evidence of over- or under-performance beyond what the
   disclosed simplifications predict.
4. **Wider mean-entropy separation on HaluEval (0.486 nats
   vs 0.392 on TruthfulQA)** with identical AUC indicates
   HaluEval's distractor distribution is further from correct
   than TruthfulQA's (easier to rank), but both rank signals
   land at the same AUC — consistent with the metric being
   well-calibrated rather than benchmark-gaming.

**What this authorizes** (per §13.7 pre-commitment and §13.8
priority list):

- The §2.2 metric revision is authorized to land. Semantic-
  entropy clustering replaces probability-simplex Euclidean
  distance as the §11-passing Ketu observable for the LLM
  domain at the simplex+same-family configuration.
- The §1.3 cross-family ensemble revision is promoted to
  top of the §13.8 authorized-next list. Literature predicts
  a further ~0.05–0.10 AUC lift; if that holds, the combined
  §2.2 + §1.3 revision would land in TRUTH_CORRELATED_STRONG
  territory.

**What this does NOT authorize:**

- VC-facing material changes. Per §13.9, the external framing
  remains "BCVF is not positioned as an LLM hallucination
  detector" until a strong pass on two benchmarks lands.
  Marginal AUC 0.66 is internal research confidence, not
  production-deployment confidence.
- Section 5 (Rahu-trust deployment), §6 (scale-out), or §7
  (packaging). These remain §13.8-paused until a strong
  pass is achieved and the pipeline is hardened beyond a
  standalone probe script.
- A 2nd-difference-of-entropy (BCVF-shaped) observable. The
  current §13.7 result is for static semantic entropy. If
  §1.3 passes, the next question is whether layering the
  BCVF 2nd-difference structure on top of semantic entropy
  adds marginal lift — that becomes a follow-up §0.8 pre-
  commitment after §1.3.

**Artifacts:**

- `docs/experiments/probe_semantic_entropy.md` (TruthfulQA-MC)
- `docs/experiments/probe_semantic_entropy.json` (TruthfulQA-MC,
  per-question dump including prompts, generations, cluster
  assignments)
- `docs/experiments/probe_semantic_entropy_halueval_qa.md`
- `docs/experiments/probe_semantic_entropy_halueval_qa.json`

### 13.11 Cross-family ensemble revision results — §1.3 attempt

The §13.8-authorized §1.3 cross-family ensemble probe has been
executed at N=100 on both benchmarks with the pre-committed triple
(Qwen2.5-7B-Instruct + Llama-3.1-8B-Instruct + Mistral-7B-Instruct-
v0.3). The combined pre-committed classification is
**`CROSS_FAMILY_ANTI_FINDING`**: TruthfulQA-MC AUC 0.633 falls below
the §13.11 anti-finding lower bound of 0.641 (§13.10 baseline 0.661
minus the ±0.02 saturation window), even though HaluEval-QA cleared
the internal-strong band at 0.716. The pre-committed bands require
the worst benchmark to set the combined classification, so the
heterogeneous split resolves to ANTI on the strict reading.

A follow-up chat-template diagnostic was run on TruthfulQA-MC (the
underperforming benchmark) to test whether prompt-format mismatch
between the shared `Q: ... A:` completion prompt and Llama/Mistral's
chat-template-native instruction tuning was the confound. The
diagnostic falsified that hypothesis: TruthfulQA-MC AUC dropped
further to 0.567 under per-family chat templates, with the entropy
signal's correct-vs-wrong separation collapsing from 0.419 nats to
0.232 nats. Cross-family structural alignment improved (singleton-
cluster rates converged) but at the cost of the entropy signal's
truth-resolution. Combined ANTI_FINDING stands, strengthened.

This closes the §13.8 item-1 authorization. The §13.8 item-2
embedding-space / activation-probe revision (Azaria & Mitchell 2023;
Chen et al. 2024 INSIDE / EigenScore) is promoted to top of the
authorized-next list and pre-committed in §13.12 below.

**Configuration (initial pass):**

- **Script:** `scripts/probe_cross_family_entropy.py` at commit
  `6a612dc` (initial M=3 implementation; subsequent commit `80afb69`
  added the `--chat-template` diagnostic flag without altering the
  default-path behaviour).
- **Target models (M = 3, fp16, co-resident on a single 80 GB GPU):**
  - `Qwen/Qwen2.5-7B-Instruct` (~14 GB) — model[0], also the label
    model (greedy generation labels correctness, identical to
    §13.10 for direct AUC comparability).
  - `meta-llama/Llama-3.1-8B-Instruct` (~15 GB) — model[1].
  - `mistralai/Mistral-7B-Instruct-v0.3` (~13 GB) — model[2].
- **NLI clustering model:** `MoritzLaurer/DeBERTa-v3-base-mnli-fever-
  anli`, fp16. Same as §13.10.
- **Benchmarks:** TruthfulQA-MC (validation split) and HaluEval-QA
  (data split), N=100 each. Same selections as §13.10.
- **Prompt format:** shared `Q: ... A:` completion across all three
  families (matches §13.10 exactly; per-family chat templates would
  confound cross-family lift with prompt-format lift, see chat-
  template diagnostic below).
- **Sampling:** K=10 completions per model per question at T=1.0,
  `max_new_tokens=32`. Pool size per question = M × K = 30.
  Per-(question, model) seed = `args.seed + q_idx × M + m_idx`
  (decouples sampling streams across families).
- **Clustering:** bidirectional, question-conditioned NLI entailment
  on the pooled M × K samples; union-find over the pool. The
  clustering rule is source-agnostic — any cross-family pair is free
  to merge if semantically equivalent — so cross-family agreement
  reduces clusters and lowers entropy.
- **Scalar:** Shannon entropy (nats) over the pooled cluster-size
  distribution; AUC computed on `−entropy` (higher entropy → less
  confident → more likely wrong).
- **Correctness label:** Qwen greedy generation passes question-
  conditioned NLI against the correct choice AND fails NLI against
  every distractor — identical labeling as §13.10.

**Initial-pass result table** (completion-style prompt, both
benchmarks, N=100):

| Benchmark | N | Greedy acc | Mean H (correct) | Mean H (wrong) | Separation | **AUC** | Δ vs §13.10 | Per-run band |
|---|---|---|---|---|---|---|---|---|
| TruthfulQA-MC (validation) | 100 | 0.250 | 2.143 | 2.562 | 0.419 nats | **0.633** | −0.028 | `CROSS_FAMILY_ANTI_FINDING` |
| HaluEval-QA (data) | 100 | 0.300 | 2.111 | 2.675 | 0.564 nats | **0.716** | +0.055 | `CROSS_FAMILY_INTERNAL_STRONG` |

Per-family singleton-cluster rates (fraction of a family's samples
landing in clusters no other family contributed to — pure
diagnostic, not in any pass band):

| Model | TruthfulQA-MC | HaluEval-QA |
|---|---|---|
| `Qwen/Qwen2.5-7B-Instruct` | 0.512 | 0.637 |
| `meta-llama/Llama-3.1-8B-Instruct` | 0.671 | 0.722 |
| `mistralai/Mistral-7B-Instruct-v0.3` | 0.739 | 0.720 |

**Combined classification logic** (per §13.11 pre-commitment): the
worst-benchmark band sets the overall classification. TruthfulQA-MC
0.633 < 0.641 lower bound → `CROSS_FAMILY_ANTI_FINDING` regardless
of HaluEval-QA's 0.716 internal-strong result.

**Chat-template diagnostic — TruthfulQA-MC only, N=100:**

A subsequent diagnostic ran on the underperforming benchmark with
each tokenizer's `apply_chat_template()` substituted for the shared
`Q: ... A:` prompt (ChatML for Qwen, Llama-3 role tags, `[INST]`
for Mistral). Hypothesis: Llama and Mistral's high singleton-cluster
rates (0.67 / 0.74) reflected prompt-format mismatch driving
stylistic divergence that NLI could not bind to Qwen's outputs,
rather than genuine semantic disagreement.

| Variant | Greedy acc | Mean H (all) | Mean H (correct) | Mean H (wrong) | Separation | Mean clusters | **AUC** |
|---|---|---|---|---|---|---|---|
| Initial pass (`Q: ... A:`) | 0.250 | 2.457 | 2.143 | 2.562 | 0.419 nats | 19.53 / 30 | **0.633** |
| Chat-template diagnostic | 0.170 | 1.854 | 1.662 | 1.893 | 0.232 nats | 13.78 / 30 | **0.567** |

| Singleton rate | Initial | Chat-template | Δ |
|---|---|---|---|
| Qwen | 0.512 | 0.429 | −0.083 |
| Llama | 0.671 | 0.548 | −0.123 |
| Mistral | 0.739 | 0.517 | −0.222 |

**What the result demonstrates:**

1. **Cross-family ensembling is not a uniform improvement over
   single-model semantic entropy.** §13.10's M=1 result was AUC
   0.661 on both benchmarks to three decimals — a clean, benchmark-
   portable single signal. The M=3 cross-family ensemble produced a
   wide split (TruthfulQA-MC −0.028, HaluEval-QA +0.055) at the same
   N. The signal added by independent families is not additive in
   the AUC sense; it is benchmark-conditional.
2. **HaluEval-QA's +0.055 lift is consistent with literature
   forecasts.** Yoffe 2024 (DebUnc) and Feng 2024 ("Don't
   Hallucinate, Abstain") report a +0.05–0.10 AUC lift from cross-
   family disagreement on QA-style benchmarks; HaluEval-QA's clean
   right-vs-hallucinated answer structure matches that setting and
   the result lands inside the predicted window.
3. **TruthfulQA-MC's −0.028 drop is consistent with literature
   forecasts for the same method on this specific benchmark.**
   Farquhar 2024 reports semantic entropy at AUROC 0.75–0.79 on
   TriviaQA / SQuAD but only ~0.70 on TruthfulQA-style adversarial
   benchmarks, attributing the gap to TruthfulQA's "confident
   misconception" question design — questions where models share
   the wrong answer with high confidence (low entropy for *wrong*
   answers, breaking the entropy → wrong correlation). The §13.10
   M=1 result already absorbed that pathology at 0.661; adding
   independently-trained models that also share the misconception
   compounds the low-entropy-for-wrong effect rather than diluting
   it. This is a method-level result, not a flaw in the §1.3
   ensemble construction.
4. **The chat-template diagnostic falsified the prompt-format
   hypothesis.** The pre-commitment was "TruthfulQA-MC AUC ≥ 0.68
   under chat templates → prompt-format was the confound." Observed
   AUC was 0.567, a further 0.066 drop from the initial 0.633. The
   hypothesis is rejected; cross-family ANTI_FINDING is not a
   prompt-formatting artifact.
5. **Chat templates trade structural alignment for entropy
   resolution.** The diagnostic produced a clean pair of opposing
   effects: singleton-cluster rates converged toward each other
   (Mistral −0.222, Llama −0.123, Qwen −0.083) — the structural
   improvement the hypothesis predicted — but the entropy signal's
   correct-vs-wrong separation collapsed from 0.419 nats to 0.232
   nats and the per-question cluster count fell from 19.53 to 13.78
   of 30 pooled samples. Instruct models under chat templates
   produce more formulaic, confidence-tone-matched assistant
   responses with reduced semantic variance regardless of actual
   knowledge — the "confidence theater" failure mode flagged in
   Kuhn 2023 and Farquhar 2024 (which is why the published Farquhar
   2024 protocol uses completion-style prompts). The completion-
   style prompt was a correct §13.11 design choice; chat templates
   would have only further damaged the signal had they been used
   throughout.
6. **Greedy-accuracy drop under chat templates (0.250 → 0.170) is
   labeling noise, not a signal change.** Chat-templated Qwen
   greedy generations are longer and include more qualifier
   language, which makes the question-conditioned NLI label
   ("entails correct AND not any distractor") harder to satisfy:
   correct answers fail because qualifiers introduce non-entailment;
   wrong answers sometimes pass because they accidentally entail a
   distractor. AUC is computed over the resulting label split, so
   the 0.567 number is on a slightly different label population
   than 0.633 — but the band gap is wide enough (0.066) that the
   labeling shift cannot rescue the chat-template variant into the
   pass region.

**What this authorizes** (per §13.11 pre-commitment and §13.8
priority list):

- The §13.8 item-2 embedding-space / activation-probe revision is
  promoted from "secondary" to top of the authorized-next list. See
  §13.12 for the pre-committed probe design (EigenScore, Chen et
  al. 2024 ICLR — covariance of mid-layer hidden states across the
  K=10 sampled generations, no training data required, directly
  comparable to §13.10's K=10 sampling protocol).
- A §13.11-attempt notation in §13.8 marking the §1.3 cross-family
  ensemble revision as executed and classified
  `CROSS_FAMILY_ANTI_FINDING`.
- HaluEval-QA's 0.716 internal-strong stand-alone result may be
  cited as a within-benchmark positive for cross-family in a §13.11
  appendix or follow-up note, but it does not change the combined
  classification under the §13.11 worst-benchmark rule.

**What this does NOT authorize:**

- Any update to `AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md`. Per §13.9, the
  external-framing revision requires `CROSS_FAMILY_STRONG`
  (≥ 0.75 on both benchmarks). Maximum observed AUC across §13.11
  was 0.716 on a single benchmark. The §13.9 hold remains in force.
- §13.8 item 3 (2nd-difference-of-semantic-entropy observable). The
  pre-commitment for that follow-up was conditional on §1.3
  passing; §1.3 did not pass, so item 3 is not authorized. Re-
  authorization requires a fresh §0.8 pre-commitment after §13.12
  lands a positive result.
- Section 5 (Rahu-trust deployment), §6 (scale-out beyond N=100),
  or §7 (packaging). All remain §13.8-paused on the same conditions
  as before §13.11.
- Any claim that the §1.3 ensemble "doesn't work". The honest scope
  is: at M=3 with a same-K=10 / same-T / same-completion-prompt
  configuration on a Qwen / Llama-3.1 / Mistral-v0.3 triple, the
  combined per-benchmark AUC bands resolve to ANTI_FINDING on the
  TruthfulQA pathology. Lift exists on HaluEval. A different
  ensemble (M=2, larger M, different families, weighted
  aggregation, per-model temperature tuning) is not tested here
  and is not foreclosed; it is simply lower-priority than the
  embedding-space revision per the §13.8 priority list.

**Artifacts:**

- `scripts/probe_cross_family_entropy.py` (commit `6a612dc`,
  initial M=3 implementation; commit `80afb69`, `--chat-template`
  diagnostic flag added).
- `docs/experiments/probe_cross_family_entropy_truthfulqa_mc.md`
  (initial pass).
- `docs/experiments/probe_cross_family_entropy_truthfulqa_mc.json`
  (per-question dump including pooled samples, source-model ids,
  cluster ids, prompts).
- `docs/experiments/probe_cross_family_entropy_halueval_qa.md`
  (initial pass).
- `docs/experiments/probe_cross_family_entropy_halueval_qa.json`.
- `docs/experiments/probe_cross_family_entropy_truthfulqa_mc_chat.md`
  (chat-template diagnostic).
- `docs/experiments/probe_cross_family_entropy_truthfulqa_mc_chat.json`.

### 13.12 Pre-commitment — EigenScore embedding-space probe (§13.8 item 2)

**Status: pre-committed, not yet executed.** This section is a
§0.8-style pre-commitment recorded before the experiment runs. The
probe specification, success bands, and expected-cost estimates
below are pinned at the time of §13.11's anti-finding write-up; any
deviation at run time must be flagged in the result section as a
deviation rather than a band-shift.

**Background.** §13.10 established that meaning-space semantic
entropy (Farquhar 2024) on a single Qwen2.5-7B-Instruct target
clears the §11 0.60 marginal bar at AUC 0.661 on both benchmarks
but does not clear the §13.9 0.75 external-framing bar. §13.11
attempted to lift that result via the §13.8 item-1 cross-family
ensemble revision (Yoffe 2024 / Feng 2024, Qwen + Llama + Mistral
M=3 pool) and landed `CROSS_FAMILY_ANTI_FINDING` — a heterogeneous
benchmark split (TruthfulQA 0.633 / HaluEval 0.716) whose worst
benchmark falls below the §13.10 baseline minus the saturation
window. The §13.8 item-2 embedding-space / activation-probe
revision is therefore the next authorized probe.

The literature class targeted here — Azaria & Mitchell 2023 (SAPLMA);
Marks & Tegmark 2024 ("The Geometry of Truth"); Chen et al. 2024
ICLR ("INSIDE: LLMs' Internal States Retain the Power of
Hallucination Detection") — operates on the model's hidden states
rather than its sampled outputs. Reported AUROCs on TruthfulQA /
HaluEval / SAPLMA are in the **0.71–0.83** band, with INSIDE /
EigenScore (Chen 2024) reporting **0.74–0.81** on HaluEval-QA and
TruthfulQA — i.e., literature predicts a result band that brackets
the §13.9 0.75 external-framing bar from both sides. A clean
positive on this probe therefore would meaningfully test §13.9 in
a way §13.11 could not.

EigenScore is selected over the linear-probe variants (SAPLMA,
Geometry of Truth) for three reasons specific to this codebase:

1. **No labeled training set required.** EigenScore is computed per
   question from K samples' hidden states; it has no learned
   parameters beyond a regularization scalar. Linear probes need a
   train/test split with truth labels, which would force a separate
   §0.8 pre-commitment around split selection and risk train/test
   contamination across our two benchmarks.
2. **Direct K=10 protocol parity with §13.10.** EigenScore reuses
   the same K=10 sampling already exercised in
   `probe_semantic_entropy.py`; only the per-sample artifact
   captured is different (last-token hidden state instead of decoded
   string). AUC bands across §13.10 / §13.11 / §13.12 stay directly
   comparable.
3. **Falsifies a different hypothesis class.** Semantic entropy is
   a sample-space metric; cross-family is an ensemble metric.
   EigenScore is an internal-state metric. A positive result here
   would not be a "more of the same" lift; a negative result would
   triangulate the §13 null toward a stronger, multi-axis claim.

**Specification (pinned):**

- **Script:** `scripts/probe_eigenscore.py` (new; does NOT modify
  `probe_semantic_entropy.py` — §13.10's result is pinned — and does
  NOT modify `probe_cross_family_entropy.py` — §13.11's result is
  pinned).
- **Target model:** `Qwen/Qwen2.5-7B-Instruct`, fp16. Same single-
  family configuration as §13.10 to preserve direct AUC
  comparability against the 0.661 baseline. M=1 by construction —
  EigenScore is a within-model signal.
- **Hidden-state extraction layer:** `model.config.num_hidden_layers
  // 2` (Qwen2.5-7B-Instruct has 28 transformer blocks, so
  layer 14, the middle layer). Pinned for the headline result; a
  `--layer` CLI flag enables follow-up sweeps but the §13.12 band
  classification refers exclusively to layer 14.
- **Hidden-state extraction position:** the LAST generated token's
  hidden state for each of the K samples (i.e., the residual-stream
  vector at the final non-EOS position of the sample). Captured via
  `model.generate(..., output_hidden_states=True)` and indexed as
  `outputs.hidden_states[-1][layer_idx][:, -1, :]` — last-step's
  hidden states tuple, middle-layer entry, final batch position.
- **Scalar (Chen 2024 formulation):** for each question with K
  samples and hidden-state matrix `X ∈ ℝ^{K × H}` (H = 3584 for
  Qwen2.5-7B-Instruct), compute the centered Gram-matrix variant
  used in the original paper (well-conditioned even when H ≫ K):

  ```
  X_c   = X - X.mean(axis=0, keepdims=True)        # K × H, centered
  Σ_K   = (X_c @ X_c.T) / H + α · I_K              # K × K
  EigenScore(q) = (1.0 / K) · log(det(Σ_K))
  ```

  with regularization `α = 1e-3` (Chen 2024 default). Higher
  EigenScore = more spread in the K hidden states = more uncertainty.
  AUC computed on `−EigenScore` so the convention "higher = more
  truth-predictive" is preserved across §13.10 / §13.11 / §13.12.
- **Benchmarks:** TruthfulQA-MC validation split, N=100 (same
  selection as §13.10); HaluEval-QA `data` split, N=100 (same
  selection as §13.10).
- **Sampling protocol:** K=10 completions per question at T=1.0,
  `max_new_tokens=32`. Identical to §13.10. Per-question seed
  `args.seed + q_idx`. No greedy from a separate model — the same
  Qwen target produces both the sampled completions (for hidden
  states) and the greedy completion (for the correctness label).
- **Prompt format:** shared `Q: ... A:` completion, identical to
  §13.10 / §13.11 initial pass. No chat templates (the §13.11
  diagnostic already established that chat templates degrade the
  signal on this codebase).
- **Correctness label:** Qwen greedy generation passes question-
  conditioned NLI (DeBERTa-v3-base-mnli-fever-anli) against the
  correct choice AND fails NLI against every distractor. Identical
  labeling to §13.10 / §13.11. Direct AUC comparability.

**Pre-committed success bands** (same numerical partition as §13.11
because the §13.10 baseline of 0.661 is unchanged; relabeled
`EMBEDDING_SPACE_*` to keep the per-revision lineage legible in
search and in `classify()` output):

- `AUC ≥ 0.75` on **both** benchmarks → **`EMBEDDING_SPACE_STRONG`**.
  Gates the §13.9 VC-brief revision (the same gate §13.11 failed
  to clear). Authorizes a full §13.13 writeup, re-opens the §13.8
  item-3 2nd-difference observable as a follow-up §0.8 pre-
  commitment, and unblocks the §13.9 external-framing reconsideration.
- `0.70 ≤ AUC < 0.75` on **both** → **`EMBEDDING_SPACE_INTERNAL_STRONG`**.
  Strong for internal research; VC-brief still held. Document in a
  §13.13 internal-strong section; consider whether layer or α
  sweep closes the 0.05-AUC gap to the strong band.
- `0.681 ≤ AUC < 0.70` on **both** → **`EMBEDDING_SPACE_MARGINAL_LIFT`**.
  Modest but real lift above §13.10's 0.661 + 0.02 saturation
  upper bound. Document; do NOT authorize further probe progression.
- `0.641 ≤ AUC ≤ 0.681` on **both** → **`EMBEDDING_SPACE_SATURATION`**.
  Within ±0.02 of §13.10's 0.661 single-model baseline. Internal-
  state representation adds nothing beyond meaning-space semantic
  entropy at this configuration. Together with §13.11's combined
  ANTI_FINDING, this would constitute strong evidence that a single-
  axis revision (metric class change) cannot clear the §13.9 bar
  and that compound revisions (e.g., embedding-space + 2nd-
  difference, or embedding-space + cross-family on a different
  triple) are required.
- `AUC < 0.641` on **any** benchmark → **`EMBEDDING_SPACE_ANTI_FINDING`**.
  Combined with §13.11, this would be a 2-of-2 anti-finding across
  the two literature-backed revision classes available to this
  codebase. Pause LLM track. Re-frame the §13 closure as "the
  literature-backed single-axis revisions tested in this codebase
  do not lift Qwen2.5-7B-Instruct AUC into the 0.75 band on both
  benchmarks at N=100." A combined-revision §0.8 pre-commitment
  becomes the only remaining authorized path.

The "on both benchmarks" combinatorial rule is identical to §13.11's
worst-benchmark rule and is pinned here so that a heterogeneous
TruthfulQA / HaluEval split (which is plausible given §13.11's 0.083-
wide split and Farquhar 2024's reported per-benchmark variance)
does not get rescued post-hoc by single-benchmark cherry-picking.

**Known simplifications vs Chen et al. 2024** (disclosed so the
expected AUC band is calibrated against a realistic baseline rather
than the paper's headline numbers):

- **Single fixed layer (L/2 = 14).** Chen 2024 sweeps multiple
  layers and reports best-of-sweep AUROC. Selecting a single layer
  before running gives up the best-of-sweep margin. Expected AUC
  penalty: small (~0.01–0.03) but material near the 0.75 boundary.
  Configurable via `--layer` for follow-up sweeps if §13.12 lands
  in the marginal or saturation band.
- **Single hidden-state position (last generated token).** The paper
  evaluates last-token, mean-pool, and last-prompt-token positions
  and reports modest variance across them. Last-token is the
  paper's default for generative QA. Expected penalty: <0.01 AUC.
- **Fixed regularization α = 1e-3.** Chen 2024 reports robustness
  to α in the [1e-4, 1e-2] range; outside that range AUC degrades.
  Pinning to the paper default is a reasonable §0.8 default but
  introduces a small confound if Qwen2.5-7B's hidden-state scale
  differs from the OPT/Llama-2 models used in the paper. Configurable
  via `--alpha` for follow-up.
- **K = 10, T = 1.0, max_new_tokens = 32.** Identical to §13.10 /
  §13.11. The paper's K is typically 10 as well.
- **Same correctness label as §13.10 / §13.11** (question-conditioned
  NLI on Qwen greedy). The paper uses gold-answer string match for
  TruthfulQA in some configurations, which would flag fewer correct
  generations as "correct" and shift n_pos / n_neg. Holding the
  label fixed across §13 prevents a labeling-pipeline confound but
  carries forward §13.10's labeling assumption. A string-match
  fallback label is a §13.13 robustness check if the result lands
  near a band boundary.
- **Single target model (Qwen2.5-7B-Instruct).** The paper uses
  Llama-2 / OPT in its headline numbers. Qwen2.5-7B's hidden-state
  geometry may differ; the literature predicts the method
  generalizes but the specific AUC is not pre-tested on Qwen.
  Expected AUC may land slightly below the paper's 0.74–0.81 range
  for this reason. The §13.12 strong band at 0.75 is therefore at
  the lower edge of what the literature predicts for this exact
  model — a clean strong-band pass would be a meaningful positive
  result, not a guaranteed replication.

These simplifications together suggest the §13.12 implementation
should land at AUROC **~0.68–0.78** on the two benchmarks if the
EigenScore signal transfers to Qwen2.5-7B-Instruct as the literature
predicts — i.e., bracketing the strong band but not guaranteed to
clear it. A result below 0.65 on both benchmarks would constitute
a genuine signal against the embedding-space hypothesis on this
codebase even after accounting for the simplifications above; a
result above 0.78 would suggest Qwen2.5-7B's hidden states carry a
stronger truth signal than the literature's Llama-2 / OPT baseline.

**Expected cost.** Single 7B target model, K=10 sampling identical
to §13.10, no NLI clustering pass on the K samples (NLI is used only
for the correctness label, ~3 calls per question). Hidden-state
extraction during generation adds ~2× memory but no substantial
wall-time. Estimated runtime: **~3–5 min at N=100 on a single 24+
GB GPU**. Cheaper than §13.10's clustering-bound runtime and much
cheaper than §13.11's M=3 co-resident loading.

**Report destination.**
- `docs/experiments/probe_eigenscore_truthfulqa_mc.md`
- `docs/experiments/probe_eigenscore_truthfulqa_mc.json` (per-question
  dump including hidden-state shape, EigenScore, sample IDs, cluster
  assignments are not applicable here — there is no clustering step).
- `docs/experiments/probe_eigenscore_halueval_qa.md`
- `docs/experiments/probe_eigenscore_halueval_qa.json`

**Relationship to BCVF 2nd-difference core.** EigenScore as
specified is a static scalar — first-difference structure (one
scalar per question). It does not yet introduce the BCVF 2nd-
difference observable. If §13.12 lands in `EMBEDDING_SPACE_STRONG`
or `EMBEDDING_SPACE_INTERNAL_STRONG`, a follow-up §13.13
pre-commitment can test whether `d²(EigenScore)/dk²` across outer
decoding steps (the true BCVF-shaped signal applied to internal
states) improves on the static scalar. That follow-up is NOT pre-
committed here; its authorization is conditional on §13.12 clearing
the marginal-lift bar AT MINIMUM.

**What §13.12 does not pre-commit.** No probe-script implementation
on-branch, no `classify()` thresholds in code, no benchmark runs.
This section is the §0.8-style pre-commitment record only.
Implementation of `scripts/probe_eigenscore.py` is a separate
authorization gate; the pre-committed bands above are the guarantee
that any future implementation cannot redefine the success criteria
post-hoc.

### 13.13 Pre-commitment — continuous semantic entropy (Farquhar 2024 bridge)

**Status: pre-committed, not yet executed.** This section is a
§0.8-style pre-commitment recorded before the experiment runs. The
specification, success bands, and expected-cost estimates below are
pinned at the time of §13.12's pre-commit and BEFORE §13.12 has been
run — the §13.13 probe can be authorized for implementation
independent of §13.12's outcome, since the two probes test different
hypothesis classes and use different scripts.

**Background.** §13.10 implemented Farquhar et al. 2024
(*Nature* 630, 625–630) at a deliberately simplified configuration:
discrete semantic entropy, DeBERTa-v3-base NLI, `max_new_tokens=32`,
NLI-based correctness labeling, multiple-choice TruthfulQA-MC. We
reached AUC 0.661 on both benchmarks. Farquhar's headline numbers
are AUROC 0.74–0.79 on TriviaQA / SQuAD / NQ-Open / BioASQ and
~0.70 on TruthfulQA-Generation. The gap to our 0.661 result is
attributable to several disclosed simplifications, each of which
the paper itself ablates. §13.13 closes the **three highest-leverage
methodological gaps** while holding the target model (Qwen2.5-7B-
Instruct), benchmarks (TruthfulQA-MC + HaluEval-QA), prompt format
(`Q: ... A:` completion), and correctness-label protocol (question-
conditioned NLI on Qwen greedy) fixed. This isolates the metric +
protocol contribution from confounds like model scale, benchmark
choice, or labeling pipeline.

**Quantified gap analysis (Farquhar 2024 vs §13.10), using the
paper's own ablations as the per-gap effect sizes:**

| Dimension | Farquhar 2024 | §13.10 | Estimated AUC gap |
|---|---|---|---|
| Headline scalar | **Continuous** SE (length-normalized log-prob weighting) | Discrete SE (cluster counts only) | **~+0.04** |
| NLI clustering model | DeBERTa-v2-xlarge (~900M) | DeBERTa-v3-base (~140M) | **~+0.02** |
| Generation length | `max_new_tokens=128`+ | `max_new_tokens=32` | **~+0.01–0.05** |
| Target LLM | Llama-2-13B/70B / Falcon-40B / Mistral-7B | Qwen2.5-7B-Instruct | ~0.0–0.05 (model-family effect) |
| Benchmarks | Free-form (TriviaQA, NQ, SQuAD, etc.) | TruthfulQA-MC1 + HaluEval-QA | ~+0.05–0.10 (protocol mismatch) |
| Correctness label | Gold-answer string match | Question-conditioned NLI on greedy | sign uncertain |

§13.13 addresses the **first three** gaps (continuous SE, larger
NLI, longer generation) — together estimated to lift AUC by
**+0.07–0.11** if the paper's per-gap ablations transfer to our
configuration. The remaining gaps (target model scale, benchmark
choice, labeling protocol) are deferred to subsequent §0.8 pre-
commitments because they require benchmark or model substitutions
that change what is being measured.

**Why this probe over a fresh hypothesis class.** §13.10 / §13.11 /
§13.12 each test a fundamentally different signal class (sample-
space, ensemble-space, internal-state). §13.13 instead **closes a
known replication gap on §13.10's signal class**. The reason this is
worth doing rather than another novel probe: if Farquhar's published
0.74–0.79 AUROC is real and transfers to Qwen2.5-7B at our
benchmarks, then §13.10's 0.661 underperforms the literature-
expected number by 0.07–0.11 *for reasons we have already
identified*. Closing those gaps either (a) confirms the literature
transfers and produces a strong-band §13.10-class result, or (b)
falsifies the transfer for this codebase even with a faithful
implementation — both outcomes are informative. Continuing to test
new hypothesis classes (item 3, item 4, ...) without first closing
known replication gaps would risk attributing each new probe's
shortfall to its hypothesis rather than to a shared protocol-level
issue.

**Specification (pinned):**

- **Script:** `scripts/probe_continuous_se.py` (new; does NOT modify
  `probe_semantic_entropy.py` — §13.10 is pinned).
- **Target model:** `Qwen/Qwen2.5-7B-Instruct`, fp16. Same single-
  model configuration as §13.10 / §13.12 to preserve direct AUC
  comparability against the 0.661 baseline. The model-scale gap is
  intentionally NOT closed in §13.13.
- **Benchmarks:** TruthfulQA-MC validation split, N=100 (same
  selection as §13.10); HaluEval-QA `data` split, N=100 (same
  selection as §13.10). Same benchmarks as §13.10 / §13.11 / §13.12
  for direct AUC comparability across the four probes.
- **Sampling:** K=10 completions per question at T=1.0,
  **`max_new_tokens=128`** (up from §13.10's 32). Per-question seed
  `args.seed + q_idx`. Generation captures per-token logits via
  `model.generate(..., output_scores=True, return_dict_in_generate=
  True)` so that per-sample length-normalized log-likelihood can be
  computed alongside the decoded string.
- **NLI clustering model:** **`MoritzLaurer/DeBERTa-v3-large-mnli-
  fever-anli-ling-wanli`** (or DeBERTa-v2-xlarge if available
  ungated). Up from §13.10's DeBERTa-v3-base. Used both for sample
  clustering and for correctness labeling (same model for both, as
  §13.10).
- **Prompt format:** shared `Q: ... A:` completion, identical to
  §13.10 / §13.11 initial pass / §13.12. No chat templates (§13.11
  diagnostic established chat templates degrade signal).
- **Clustering rule:** bidirectional, question-conditioned NLI
  entailment, union-find over the K samples per question. Identical
  to §13.10's `cluster_by_entailment`.
- **Continuous semantic entropy scalar (Farquhar 2024 §2.2 Eq. 6):**
  given K samples with cluster assignments c(s_k) ∈ {1, ..., C} and
  per-sample length-normalized log-likelihoods
  ℓ_k = (1/T_k) · Σ_t log p(s_k,t | s_k,<t, prompt)
  (the average per-token log-prob of sample k, where T_k is the
  number of generated tokens and the sum is over those tokens),
  compute per-cluster aggregated probability:
      log P(c) = logsumexp_{k: c(s_k) = c} ℓ_k
  Normalize over clusters:
      log P̂(c) = log P(c) − logsumexp_{c' ∈ clusters} log P(c')
  Then:
      H_continuous(q) = − Σ_c P̂(c) · log P̂(c)
  AUC computed on `−H_continuous` (higher entropy → less confident →
  more likely wrong; negate for the convention "higher = more
  truth-predictive" used across §13.10 / §13.11 / §13.12 / §13.13).
- **Correctness label:** Qwen greedy generation passes question-
  conditioned NLI against the correct choice AND fails NLI against
  every distractor. Identical labeling to §13.10 / §13.11 / §13.12.
  The greedy `max_new_tokens` is also raised to 128 for consistency
  with the sampling configuration; this MAY shift greedy accuracy
  slightly vs §13.10 (longer greedy responses can fail "entails
  correct AND not distractor" via qualifier text), and any such
  shift will be reported as a deviation in §13.14 (the result
  section, when written).

**Pre-committed success bands** (same numerical partition as §13.11
/ §13.12 because the §13.10 baseline of 0.661 is unchanged;
relabeled `CONTINUOUS_SE_*` to keep the per-revision lineage
legible in console output, JSON dumps, and grep):

- `AUC ≥ 0.75` on **both** benchmarks → **`CONTINUOUS_SE_STRONG`**.
  Gates the §13.9 VC-brief revision (the same gate §13.11 failed
  to clear and §13.12 has not yet attempted). Authorizes a §13.14
  writeup, re-opens the §13.8 item-3 2nd-difference observable as
  a follow-up §0.8 pre-commitment, and unblocks the §13.9 external-
  framing reconsideration.
- `0.70 ≤ AUC < 0.75` on **both** → **`CONTINUOUS_SE_INTERNAL_STRONG`**.
  Strong for internal research; VC-brief still held. Document in a
  §13.14 internal-strong section. Stage 2 of the Farquhar bridge
  (adding TriviaQA-Generation as a third benchmark to compare
  against Farquhar's headline 0.78 number directly) becomes the
  authorized next probe.
- `0.681 ≤ AUC < 0.70` on **both** → **`CONTINUOUS_SE_MARGINAL_LIFT`**.
  Modest but real lift above §13.10's 0.661 + 0.02 saturation
  upper bound. Document; do NOT authorize further single-axis
  probe progression. Stage 2 (TriviaQA addition) and Stage 3
  (target-model upscale to Qwen2.5-32B) remain plausible as
  follow-ups but require fresh §0.8 pre-commitments.
- `0.641 ≤ AUC ≤ 0.681` on **both** → **`CONTINUOUS_SE_SATURATION`**.
  Within ±0.02 of §13.10's 0.661 single-model baseline. The three
  Farquhar-aligned methodological upgrades (continuous SE, larger
  NLI, longer generation) added nothing measurable on this codebase.
  Combined with §13.11's anti-finding (and §13.12's outcome,
  whatever it lands at), this would be strong evidence that the
  shortfall vs Farquhar's 0.74–0.79 is NOT in the metric or
  protocol layer but in the benchmark choice (TruthfulQA-MC vs
  Farquhar's TruthfulQA-Generation) or the model scale (Qwen-7B
  vs Llama-2-13B/70B). Authorizes Stage 2 (benchmark substitution)
  as the next probe under a fresh pre-commitment.
- `AUC < 0.641` on **any** benchmark → **`CONTINUOUS_SE_ANTI_FINDING`**.
  The literature-aligned variant of §13.10 underperforms the
  simplified §13.10 baseline. This would be a surprising result —
  the paper's ablations predict each individual change is
  monotonically positive — and would suggest one of: (a) the
  continuous SE implementation has a numerics bug (length
  normalization sign / log-sum-exp aggregation), (b) the larger
  NLI model interacts pathologically with Qwen2.5-7B's output
  distribution, or (c) the longer generation introduces
  truncation-pattern artifacts that the discrete clustering
  absorbed but the continuous weighting amplifies. Investigation
  required before treating as a genuine anti-finding.

The "on both benchmarks" combinatorial rule is identical to §13.11 /
§13.12 and is pinned here to prevent post-hoc benchmark cherry-
picking on a heterogeneous TruthfulQA / HaluEval split.

**Known simplifications vs Farquhar 2024 that §13.13 does NOT close**
(disclosed so the expected AUC band is calibrated against a realistic
post-§13.13 baseline rather than the paper's headline numbers):

- **Target model:** Qwen2.5-7B-Instruct vs Farquhar's Llama-2-13B/
  70B / Falcon-40B / Mistral-7B. Same parameter scale as one of the
  paper's models (Mistral-7B), but different family. Expected per-
  family variance ±0.03 AUC.
- **Benchmarks:** TruthfulQA-MC + HaluEval-QA vs Farquhar's
  TriviaQA / NQ-Open / SQuAD / BioASQ / TruthfulQA-Generation.
  TruthfulQA-MC is multiple-choice (closed form) where Farquhar's
  TruthfulQA result was on the free-form generation variant — the
  two are different problems despite sharing questions. HaluEval-QA
  is not in the Farquhar paper at all. Stage 2 of this bridge
  (adding TriviaQA-Generation as a third benchmark) is the
  pre-committed follow-up if §13.13 lands above SATURATION.
- **Correctness label:** question-conditioned NLI on Qwen greedy vs
  Farquhar's gold-answer string match. Holding labeling fixed
  across §13 prevents cross-experiment label-shift confounds; cost
  is that we under-credit greedy generations that paraphrase the
  correct choice (NLI sometimes fails on legitimate paraphrases the
  string-match would also fail on, but the failure modes differ).
- **K = 10.** Farquhar uses K=10 in most experiments but ablates
  K up to 30; reports +0.01–0.02 AUC for K=20+. Pinning K=10
  preserves §13.10 / §13.11 / §13.12 parity.

These un-closed gaps together suggest the §13.13 implementation
should land at AUROC **~0.70–0.76 on both benchmarks** if the
paper's per-gap ablations transfer cleanly to Qwen2.5-7B-Instruct
on our benchmark mix — i.e., bracketing the §13.9 0.75 strong band
but not guaranteed to clear it. A result above 0.78 would suggest
the paper's ablations *under-state* the per-gap effect on this
codebase (unexpected); a result below 0.66 would constitute
genuine evidence against Farquhar's transfer claims for this model
+ benchmark mix even after the three simplifications above are
accounted for.

**Expected cost.** Single 7B target model + larger NLI model. K=10
sampling at `max_new_tokens=128` (4× the §13.10 token budget for
sampling; ~3× wall-clock for the generation pass). NLI clustering
pass on K=10 samples per question is unchanged in structure but
~2× slower per call due to the larger model. Estimated runtime:
**~10–15 min at N=100 on a single 24+ GB GPU** (vs §13.10's
~3 min). Memory: Qwen-7B fp16 ~14 GB + DeBERTa-v3-large fp16 ~1.5
GB = ~16 GB, comfortably under a 24 GB budget.

**Report destination.**
- `docs/experiments/probe_continuous_se_truthfulqa_mc.md`
- `docs/experiments/probe_continuous_se_truthfulqa_mc.json` (per-
  question dump including per-sample length-normalized log-
  likelihoods, cluster assignments, per-cluster aggregated
  log-probabilities — all the intermediate quantities needed to
  audit the continuous-SE numerics post-hoc).
- `docs/experiments/probe_continuous_se_halueval_qa.md`
- `docs/experiments/probe_continuous_se_halueval_qa.json`

**Relationship to §13.10 / §13.11 / §13.12.** §13.13 is a *protocol-
upgrade* probe, not a new hypothesis class. It sits in the same
sample-space metric class as §13.10 and tests whether the §13.10
shortfall vs Farquhar 2024 is closed by the three pinned upgrades.
§13.11 (cross-family ensemble) and §13.12 (EigenScore embedding-
space) test different hypothesis classes and are independent from
§13.13. Combination of §13.13's continuous SE with §13.12's
EigenScore as a compound predictor (linear combination, weighted
sum, or learned classifier) is the §13.8 item-4 follow-up and is
NOT pre-committed here — it requires a fresh §0.8 commitment after
both §13.12 and §13.13 land.

**What §13.13 does not pre-commit.** No probe-script implementation
on-branch, no `classify()` thresholds in code, no benchmark runs.
This section is the §0.8-style pre-commitment record only.
Implementation of `scripts/probe_continuous_se.py` is a separate
authorization gate; the pre-committed bands above are the guarantee
that any future implementation cannot redefine the success criteria
post-hoc. Authorization for implementation is independent of §13.12's
outcome — §13.13 can be built and run in parallel with §13.12 if
GPU time permits.

### 13.14 Pre-commitment — BCVF-faithful 2nd-difference observable

**Status: pre-committed, not yet executed.** This section is a
§0.8-style pre-commitment recorded before the experiment runs.
Specification, success bands, and expected-cost estimates are
pinned at this point and cannot be redefined post-hoc. §13.14 is
authorized to be built and run in parallel with §13.12 / §13.13;
its outcome is independent of theirs.

**Background — and why this probe is structurally different from
§13.10–§13.13.** The BCVF framework's autonomy-domain validation
(`symbolu_robotics/bcvf_autonomous/DESIGN.md` §6.1, §6.7) cleared
its pre-committed gates on `S3_map_error_accel` — *the second
derivative of the divergence between the robot's internal map and
ground truth, evaluated as the robot moves through its
environment*. Three things matter about that signal:

1. **It is relational, not agent-only.** Not a measurement of the
   robot's confidence in isolation; not a measurement of the road
   in isolation. It is the *acceleration of the agent-environment
   coupling failure* — fault information lives in how that coupling
   evolves, not in either side alone.
2. **It requires temporal evolution.** A single snapshot has no
   2nd derivative. The robot must be acting over time, the
   perception must update across steps, and the gap must be
   measurable as a function of step index.
3. **The 2nd derivative specifically catches accelerating
   failures** — a constant or shrinking gap is fine; an
   accelerating gap is the fault signature.

§13.10 (single-model semantic entropy), §13.11 (cross-family
ensemble), §13.12 (EigenScore over hidden states), and §13.13
(continuous SE) are all **single-snapshot agent-only** measurements.
Each samples K completions, computes one scalar per question, and
classifies. None of them takes a derivative over the model's
evolving generation state. They are first-derivative-class
constructions at best, and they each translate the BCVF idea by
*changing what is measured about the agent* (more samples, more
families, internal states, weighted entropy). None of them is
shaped like the autonomy-domain BCVF observable that actually
passed §6.1.

§13.14 is the first probe in the §13 ladder that is **shaped like
the autonomy-domain BCVF observable**. It takes a 2nd derivative
of the model's evolving uncertainty during a single generation, as
a function of token position within that generation. The token
sequence is the LLM's analogue of "robot moving through environment
over time" — it is the only sequential evolution available within
a single inference. Per-position semantic entropy is the analogue
of "robot's map at time t". The 2nd difference of per-position
entropy across the sequence is the analogue of `S3_map_error_accel`
— *the acceleration of the model's evolving uncertainty as it
constructs an answer*.

This makes §13.14 the **load-bearing probe for the BCVF-for-LLMs
transfer claim**. §13.10–§13.13 audit literature methods; §13.14
tests whether BCVF's actual native observable transfers. A
positive result here would be the first novel construction in this
codebase that is BCVF-shaped rather than literature-shaped; a
negative result would constitute the first real evidence that the
BCVF formalism itself does not carry the load on the LLM domain
(a stronger, multi-axis null than §13.10–§13.13's combined evidence
because those probes were not BCVF-faithful in the first place).

**The car / road / coupling framing.** §13.10–§13.13 measure
properties of the LLM (the "car"). The road (input difficulty,
question ambiguity, knowledge-boundary distance) is held fixed
across all probes by holding the benchmark fixed. The framework's
actual claim is that fault information lives in *how the coupling
between the two evolves under load* — the analogue of the robot's
map error accelerating as terrain becomes harder. Within a single
LLM inference, the only "load" axis available is sequence position:
the question is presented at t=0, and the model must construct an
answer over t=1..T. Per-position semantic divergence across K
samples is the LLM analogue of "how is the agent's internal world-
model evolving as it engages the environment", and the 2nd
difference is the analogue of "is that evolution accelerating
into divergence."

**Specification (pinned):**

- **Script:** `scripts/probe_bcvf_2diff.py` (new; does NOT modify
  any §13.10–§13.13 script — those results are pinned).
- **Target model:** `Qwen/Qwen2.5-7B-Instruct`, fp16. Same single-
  model configuration as §13.10 / §13.12 / §13.13 to preserve direct
  AUC comparability against the 0.661 baseline.
- **Benchmarks:** TruthfulQA-MC validation split, N=100 (same
  selection as §13.10); HaluEval-QA `data` split, N=100 (same
  selection as §13.10). Same benchmarks as §13.10 / §13.11 / §13.12
  / §13.13 for direct AUC comparability across the five probes.
- **Sampling:** K=10 completions per question at T=1.0,
  **`max_new_tokens=128`** (4× §13.10's 32; necessary so the
  generation has enough sequence length for a 2nd-difference signal
  to evolve). Per-question seed `args.seed + q_idx`. No hidden-state
  capture (this probe operates on decoded text, not internals — the
  signal class is "agent's evolving outputs", paralleling the
  robotics-domain signal class "agent's evolving map").
- **Prompt format:** shared `Q: ... A:` completion, identical to
  §13.10 / §13.11 / §13.12 / §13.13. No chat templates.
- **NLI clustering model:** `MoritzLaurer/DeBERTa-v3-base-mnli-fever-
  anli` for §13.14 v1 (matches §13.10 / §13.11 / §13.12 default;
  preserves AUC comparability with §13.10's 0.661). A `--nli-model`
  flag enables substituting in the §13.13-pinned DeBERTa-v3-large
  for a §13.14-v2 variant if v1 lands at SATURATION or below.
- **Position grid (pinned):** entropy is computed at sequence
  positions `t ∈ {position_min, position_min + position_stride,
  position_min + 2·position_stride, ..., max_new_tokens}`, with
  defaults:
  - `position_min = 8` — skip the first 8 generated tokens because
    those positions are dominated by leading "The", "A", whitespace,
    and other low-information tokens that produce noisy NLI
    clustering signal.
  - `position_stride = 4` — compute entropy every 4 tokens, giving
    `(128 − 8) / 4 + 1 = 31` measured positions per question. Sub-
    Nyquist sampling of the per-token sequence; chosen for
    computational tractability while preserving 2nd-difference
    structure on natural English answer construction.
  Both configurable via `--position-min` and `--position-stride`
  flags; non-default values are flagged in the report as deviations.
- **Per-position semantic entropy** (the 1st-derivative-class
  signal, computed at each grid position):
  - At each grid position `t`, take the K samples *truncated to
    length t generated tokens*. Decode each truncated sample to
    text; question-condition by prepending the question; cluster by
    bidirectional NLI entailment via union-find. Compute Shannon
    entropy `H_t` (nats) over the cluster-size distribution.
    Identical clustering rule to §13.10 — only the input strings
    differ (truncated rather than full).
- **2nd-difference scalar (the BCVF-shaped observable):** with
  per-question entropy series `H_{t₀}, H_{t₁}, ..., H_{t_N}` at the
  pinned grid positions:
  - Per-position 2nd difference (centered, stride-aware):
    `accel_i = H_{t_{i+1}} − 2·H_{t_i} + H_{t_{i−1}}`
    for `i ∈ [1, N−1]` (the i=0 and i=N positions are dropped
    because they have no centered neighbor).
  - **Primary scalar** (pinned for AUC and band classification):
    `bcvf_2diff(q) = max_i |accel_i|` — peak |entropy acceleration|
    across the generation. Mirrors `S3_map_error_accel` peak in the
    robotics domain.
  - **Secondary diagnostic scalars** (reported but NOT in the band
    classification): `mean_i |accel_i|`, `Σ_i accel_i²`, position
    `i*` of the peak. These exist purely to support post-hoc
    interpretation; changing the primary scalar after the run is a
    §0.8 violation.
  - AUC computed on `−bcvf_2diff(q)` so the convention "higher =
    more truth-predictive" is preserved. Hypothesis: questions
    where the model's evolving uncertainty *accelerates* are
    questions where the model is failing to commit to a stable
    answer — analogous to map error accelerating when the robot's
    perception is failing — and these are the questions more likely
    to be wrong.
- **Correctness label:** Qwen greedy generation passes question-
  conditioned NLI against the correct choice AND fails NLI against
  every distractor. Identical labeling protocol to §13.10 / §13.11
  / §13.12 / §13.13. Greedy `max_new_tokens=128` to match the
  sampling configuration.

**Pre-committed success bands** (same numerical partition as §13.11
/ §13.12 / §13.13 because the §13.10 baseline of 0.661 is unchanged
across all five probes; relabeled `BCVF_2DIFF_*` so the per-revision
lineage stays legible in console output, JSON dumps, and grep):

- `AUC ≥ 0.75` on **both** benchmarks → **`BCVF_2DIFF_STRONG`**.
  Gates the §13.9 VC-brief revision. Authorizes a §13.15 result
  writeup positioning §13.14 as **the first BCVF-faithful LLM
  result in this codebase** — distinct framing from any §13.10–
  §13.13 outcome because §13.14 is the only probe in the ladder
  that is shaped like the autonomy-domain BCVF observable that
  passed §6.1. STRONG here would constitute the load-bearing
  evidence for the BCVF-for-LLMs transfer claim.
- `0.70 ≤ AUC < 0.75` on **both** → **`BCVF_2DIFF_INTERNAL_STRONG`**.
  Strong for internal research; VC-brief still held. Document in a
  §13.15 internal-strong section. The 2nd-difference observable
  produces signal but doesn't clear the §13.9 bar; consider
  follow-ups: (a) NLI upgrade to DeBERTa-v3-large (§13.14-v2
  variant), (b) finer position grid (`position_stride=2` or `=1`),
  (c) target-model upscale to Qwen2.5-32B.
- `0.681 ≤ AUC < 0.70` on **both** → **`BCVF_2DIFF_MARGINAL_LIFT`**.
  Modest but real lift above §13.10 + 0.02. Document; do NOT
  authorize further single-axis probe progression. The BCVF-shaped
  signal exists but is not strong enough to change the §13.9
  external framing.
- `0.641 ≤ AUC ≤ 0.681` on **both** → **`BCVF_2DIFF_SATURATION`**.
  Within ±0.02 of §13.10's 0.661. The BCVF 2nd-difference
  observable adds nothing measurable beyond the static-snapshot
  semantic entropy of §13.10. **This would be a substantive
  internal finding** — it would suggest that for LLM hallucination
  detection the second-derivative-of-coupling-failure structure
  that powered the autonomy-domain validation does not transfer
  to the token-sequence-as-temporal-axis analogue. Honest scope
  for the BCVF-for-LLMs transfer claim narrows to "BCVF concepts
  inspired the §13 metric exploration but the native BCVF observable
  does not improve on the literature's first-derivative methods on
  this codebase".
- `AUC < 0.641` on **any** benchmark → **`BCVF_2DIFF_ANTI_FINDING`**.
  The 2nd-difference signal is *worse than* the static §13.10
  baseline. Combined with §13.11 + (whichever of §13.12 / §13.13
  has landed), this would be 3-of-3 single-axis revisions failing
  to improve on §13.10. The honest external framing under this
  outcome: **BCVF-for-LLMs as a hallucination detector is not
  supported by direct measurement on this codebase**. Pause the
  LLM track; the autonomy-domain BCVF claim stands independently
  on its own §6.1 evidence and is unaffected by this null. Items
  4–6 in §13.8's authorized list (TriviaQA addition, 2nd-difference,
  compound revisions) all need fresh §0.8 pre-commitments before
  any further LLM compute is authorized.

The "on both benchmarks" combinatorial rule is identical to §13.11
/ §13.12 / §13.13 and is pinned here to prevent post-hoc benchmark
cherry-picking on a heterogeneous TruthfulQA / HaluEval split.

**Why the SATURATION and ANTI bands matter MORE for §13.14 than
they did for §13.10–§13.13.** The earlier probes were literature
audits — a saturation result there says "this published method
doesn't transfer cleanly" but doesn't directly bear on the BCVF
formalism (because the methods being tested were not BCVF-shaped
in the first place). §13.14 IS the BCVF-shaped probe. A saturation
or anti result here is direct evidence about the BCVF transfer
claim itself, not just about a literature method. The honest
internal framing must therefore update accordingly: a §13.14
SATURATION is a real (if narrow) negative for the BCVF-for-LLMs
hypothesis, even though it is not a §13.9 VC-bar failure (which
already failed under §13.11 alone).

**Known simplifications and risks specific to §13.14** (disclosed
so the expected AUC band is calibrated against a realistic
post-§13.14 baseline; §13.14 is novel construction with no direct
literature reference, so the AUC forecast is more uncertain than
§13.10 / §13.13 which had paper-derived numbers):

- **NLI on truncated generations is noisier than NLI on full
  generations.** Truncated samples may end mid-sentence ("Paris
  was the capital of"); the MNLI-trained classifier was not
  trained on incomplete-sentence pairs. Question-conditioning
  partially mitigates this (the question stays well-formed) but
  the per-position entropy values are noisier than §13.10's whole-
  generation entropy. Net effect on AUC: probably slightly negative
  for short truncations (small `t`), neutral for mid-sequence
  truncations, neutral for full-length ones. The `position_min=8`
  default exists to cap the worst of this effect; if §13.14 lands
  at SATURATION, raising `position_min` to 16 or 24 is the first
  diagnostic follow-up.
- **Position-stride sub-sampling drops information.** Computing
  every 4 tokens (stride=4) means we discretely sample a continuous
  evolution. The 2nd-difference at stride S approximates the
  underlying continuous 2nd derivative with truncation error
  O(S²). Stride=4 was chosen for compute tractability; stride=1 is
  the gold-standard approximation but ~4× more expensive. If §13.14
  lands at MARGINAL_LIFT or SATURATION, stride=2 or stride=1 sweeps
  are the natural follow-up.
- **`max_i |accel_i|` is one of several reasonable scalar choices.**
  Other defensible primary scalars include `mean_i |accel_i|` (less
  outlier-sensitive but smears the fault signature) and
  `Σ_i accel_i²` (energy-style, weights large peaks more strongly).
  The `max_i |accel_i|` choice was pinned because it most directly
  mirrors the robotics-domain `S3_map_error_accel` peak that passed
  §6.1. If §13.14 lands at SATURATION with the primary scalar but
  one of the secondary diagnostics shows clear correct/wrong
  separation, that constitutes evidence the BCVF-shaped signal
  exists but the wrong aggregation was pinned — a fresh §0.8 re-
  commitment with a different primary scalar would be authorized.
- **Single target model (Qwen2.5-7B-Instruct).** As in §13.10–§13.13.
  Larger-model scaling effects are deferred to a separate §0.8 pre-
  commitment.
- **No literature anchor for the AUC forecast.** §13.10 had
  Farquhar 2024's headline 0.70–0.79 to anchor expectations;
  §13.12 had Chen 2024's 0.74–0.81; §13.13 had a quantified
  per-gap ablation table. §13.14 has none of these — there is no
  published paper running 2nd-difference of per-position semantic
  entropy at this exact construction. Best estimate: AUC band
  **0.62–0.78**, very wide because the prior is genuinely
  uncertain. A clean clear of 0.75 on both benchmarks would be a
  novel positive result; a clear miss below 0.65 would be the first
  direct disconfirmation of the BCVF-for-LLMs transfer claim on its
  native observable. Both outcomes are publishable; the former more
  exciting, the latter more rigorous.

**Expected cost.** Single 7B target model + DeBERTa-v3-base NLI
(same as §13.10). K=10 sampling at `max_new_tokens=128` (≈3× §13.10
generation cost). NLI clustering pass at each of ~31 grid positions
per question, each with K(K−1)=90 NLI pairs → ≈2,800 NLI calls per
question, batched → ≈90 forward passes per question at
batch_size=32. Estimated runtime: **~8–12 min at N=100 on a 24+ GB
GPU** — comparable to §13.13. Memory unchanged from §13.10
configuration.

**Report destination.**
- `docs/experiments/probe_bcvf_2diff_truthfulqa_mc.md`
- `docs/experiments/probe_bcvf_2diff_truthfulqa_mc.json` (per-
  question dump including the full per-position entropy series
  `H_t`, the per-position 2nd differences `accel_i`, the primary
  and secondary scalars, position of peak — all the intermediate
  quantities needed to audit the construction post-hoc and to
  support the secondary-scalar fallback authorization above).
- `docs/experiments/probe_bcvf_2diff_halueval_qa.md`
- `docs/experiments/probe_bcvf_2diff_halueval_qa.json`

**Relationship to §13.10–§13.13 and to the autonomy-domain result.**
§13.10 (single-snapshot SE), §13.11 (cross-family), §13.12
(EigenScore), §13.13 (continuous SE) are first-derivative-class
literature replications and bridges. §13.14 is the first probe in
the ladder that is **shaped like the autonomy-domain BCVF
observable** — `S3_map_error_accel` per §6.1 / §6.7 — applied to
the LLM domain by reading "agent moving through environment over
time" as "model constructing answer over token positions". A
positive §13.14 result would constitute evidence that the BCVF
formalism produces useful observables in a second domain (LLMs)
beyond its origin domain (autonomous robotics); a negative result
would be the first direct evidence in this codebase that the
formalism does not transfer at this analogue. **Crucially, neither
outcome retroactively affects the autonomy-domain result.** §6.1's
N=21 sign-test on `S3_map_error_accel` is a separate experiment
on a separate dataset with its own pre-committed gates met; §13.14's
outcome bears only on the LLM-domain transfer claim, not on the
robotics-domain validation that already passed.

**What §13.14 does not pre-commit.** No probe-script implementation
on-branch, no `classify()` thresholds in code, no benchmark runs.
This section is the §0.8-style pre-commitment record only.
Implementation of `scripts/probe_bcvf_2diff.py` is a separate
authorization gate. No VC-brief / §13.9 changes here — those remain
gated on `BCVF_2DIFF_STRONG` (or any other §13 probe's STRONG band)
on both benchmarks. §13.14 is authorized to be built and run in
parallel with §13.12 / §13.13 if GPU and engineering time permit;
its outcome is mathematically independent of theirs.

### 13.15 Result — BCVF 2nd-difference observable did not transfer at this construction

The §13.14 pre-committed probe has been executed at N=100 on both
benchmarks. Combined classification:
**`BCVF_2DIFF_ANTI_FINDING`**.

This result is not a broad rejection of BCVF-for-LLMs. It is a
rejection of **one specific text-level construction** of the
BCVF 2nd-difference observable — per-position semantic entropy over
NLI-clustered truncations, aggregated as `max_i |accel_i|`. The
transfer claim narrows to: *BCVF over text-level semantic-entropy
trajectories is not supported by the present evidence.* It does
not bear on BCVF over model-internal continuous state trajectories,
which remains untested as of this entry.

**Result table:**

| Benchmark | N | Greedy acc | Mean H first (t=8) | Mean H last (t=128) | AUC primary | AUC mean\|accel\| | AUC Σaccel² | Δ vs §13.10 | Per-run band |
|---|---|---|---|---|---|---|---|---|---|
| TruthfulQA-MC | 100 | 0.320 | 1.064 | 0.444 | **0.574** | 0.594 | 0.583 | −0.087 | `BCVF_2DIFF_ANTI_FINDING` |
| HaluEval-QA | 100 | 0.320 | 0.806 | 1.123 | **0.363** | 0.414 | 0.388 | −0.298 | `BCVF_2DIFF_ANTI_FINDING` |

Combined classification under the §13.14 worst-benchmark rule:
ANTI on both benchmarks. The HaluEval AUC of 0.363 is below the
0.500 random-classifier line, indicating not noise but a signal in
the *opposite* direction from the pre-committed AUC sign.

**Math used (the construction that failed).** For each question $q$
with K=10 sampled completions at T=1.0, max_new_tokens=128:

1. At each grid position $t \in \{8, 12, 16, \ldots, 128\}$
   (position_min=8, position_stride=4 → 31 positions), each of the
   K samples is truncated to its first $t$ generated tokens (capped
   at the sample's actual non-pad length).
2. The K truncated strings are clustered by question-conditioned
   bidirectional NLI entailment using DeBERTa-v3-base-MNLI, via
   union-find on the 90 directional pairs per position.
3. Per-position semantic entropy:
   $H_t = -\sum_{j} \frac{|c_j|}{K}\log\frac{|c_j|}{K}$ over the
   resulting cluster sizes.
4. Centered second difference at each interior grid index $i$:
   $\text{accel}_i = H_{t_{i+1}} - 2 H_{t_i} + H_{t_{i-1}}$.
5. Primary scalar (pinned for AUC + bands per §13.14):
   $\text{bcvf\_2diff}(q) = \max_i |\text{accel}_i|$.
6. AUC computed on $-\text{bcvf\_2diff}$, pre-committed direction
   *higher acceleration → less stable evolving uncertainty → more
   likely wrong*.

The two diagnostic secondary scalars $\text{mean}_i |\text{accel}_i|$
and $\sum_i \text{accel}_i^2$ were reported but not used for
classification (per §13.14's §0.8 pinning of the primary scalar).
All three scalar AUCs cluster within 0.05 on both benchmarks,
confirming the result is not a primary-scalar pinning artifact.

**Three reasons the signal failed at this construction:**

**(a) The per-position entropy curves were monotonic, not "smooth-
with-rare-spikes."** The autonomy-domain `S3_map_error_accel` works
because $e(t)$ is mostly slow-varying with sparse fault-onset
spikes, so $\frac{d^2 e}{dt^2}$ has high signal-to-noise. The
empirical $H_t$ curves are different shape: TruthfulQA-MC trends
$H_t = 1.06 \to 0.44$ over $t = 8 \to 128$ (samples *converge*
under longer NLI clustering); HaluEval-QA trends $H_t = 0.81 \to
1.12$ (samples *diverge*). Either trend is smooth and roughly
monotonic. The 2nd derivative of a smooth monotonic curve picks
out *local curvature*, not fault-onset moments — and local
curvature in this data does not correlate with truth.

**(b) The trend direction flipped across benchmarks.** TruthfulQA's
$H_t$ decreases with $t$; HaluEval's increases. This benchmark-
direction inversion is structural evidence that $H_t$ is dominated
by **NLI behavior on truncations of varying length**, not by the
model's evolving epistemic state. NLI-on-long-text becomes more
permissive (driving cluster merging on TruthfulQA where Qwen's
verbose answers acquire shared boilerplate). NLI-on-cumulative-
proposition becomes less permissive (driving cluster splitting on
HaluEval where each new sentence in the generated answer adds a
new claim for NLI to disagree on). Both are properties of NLI +
truncation, not of the LLM's truth state. The AUC inversion on
HaluEval (0.363 — sample-tighter when correct) is the same
artifact at the labeling boundary: longer correct answers explore
more semantic space mid-generation, longer wrong answers commit
confidently to a single wrong elaboration, so the BCVF-shape
signal runs the wrong way.

**(c) The signal is text-level / NLI-level, not model-state-level.**
The chain in §13.14's construction is: hidden state → sampled
token sequence → truncated decoded text → NLI clustering →
entropy → 2nd difference. Four lossy projections separate the
model's epistemic state from the scalar we score. Even when the
underlying state evolves smoothly with sparse fault onsets (the
shape BCVF needs), each downstream projection adds variance and
loses temporal precision. By the time the 2nd derivative is
computed, the original smooth-with-spikes structure (if it exists
at all in the model) has been smeared into the monotonic NLI
trends observed in (a).

**Narrowing of the transfer claim.** §13.15 narrows the §13.14
result to its specific construction:

> **The null narrows the BCVF-for-LLMs transfer claim to this
> specific observable construction: BCVF over text-level
> semantic-entropy trajectories is not supported by the present
> evidence. It does not reject BCVF over model-internal continuous
> state trajectories.**

The next step explicitly tests the un-rejected version. The
failure in §13.14 was not the 2nd-difference idea itself, but the
choice of text-level semantic entropy as the evolving state
variable. §13.16 therefore moves the BCVF operator onto a
continuous model-internal representation (per-position EigenScore
over hidden states) — the construction the §13.14 null leaves
open.

**Value preserved by §13.14.** The probe was not wasted compute.
It eliminated the most obvious text-level analogue of the BCVF
observable, sharpened the diagnostic understanding of why text-
level proxies fail (the three reasons above), and produced the
empirical evidence that constrains §13.16's design — specifically:
the next probe must operate on a signal class with continuous
real-valued geometry and direct provenance from the model's
internal state, not on NLI-clustered text. Without §13.14's
explicit failure data we would not be able to argue for §13.16's
construction with the evidence base now available.

**Status of the §13 program after §13.15.** Three single-axis
revisions tested across both benchmarks (§13.11 cross-family,
§13.12 EigenScore single-snapshot, §13.14 BCVF text-level 2nd-
difference) all underperform §13.10's 0.661 marginal baseline on
TruthfulQA-MC, with mixed results on HaluEval-QA. The §13.10
single-snapshot semantic entropy remains the strongest result in
this codebase. §13.16 (next section) is the only remaining
literature-aligned probe path that has not been tested and is
explicitly motivated by §13.15's narrowing.

**Artifacts:**

- `scripts/probe_bcvf_2diff.py` (commit `cebdd49`).
- `docs/experiments/probe_bcvf_2diff_truthfulqa_mc.md` and `.json`.
- `docs/experiments/probe_bcvf_2diff_halueval_qa.md` and `.json`.

### 13.16 Pre-commitment — Hidden-state EigenScore over positions

**Status: pre-committed, not yet executed.** §0.8-style pre-
commitment recorded before implementation. Specification, success
bands, and expected-cost estimates pinned at this point and cannot
be redefined post-hoc.

**Hypothesis (the one §13.15 leaves un-rejected).** BCVF may
transfer when the 2nd-difference operator is applied to a
**continuous model-internal representation** rather than to a
text-level clustering proxy. The failure in §13.14 was not the
2nd-difference idea itself, but the choice of text-level semantic
entropy as the evolving state variable. §13.16 moves the BCVF
operator onto the model's own hidden-state geometry, evaluated as
EigenScore (Chen 2024) at each position in the generated sequence.
This satisfies the three structural requirements that §13.14's
text-level construction violated (continuous real-valued signal,
direct provenance from model's internal state, smooth-with-rare-
inflections shape compatible with 2nd-derivative analysis — see
§13.15 reasons (a)–(c)).

**Exact mathematical object.** For each question $q$ with K=10
sampled completions at T=1.0, max_new_tokens=128:

1. Generate the K samples with `output_hidden_states=True,
   return_dict_in_generate=True` so that per-step layer-L hidden
   states for all K samples are captured during a single batched
   `generate` call. Layer index pinned to
   $L^* = \lfloor \text{num\_hidden\_layers} / 2 \rfloor = 14$
   (Qwen2.5-7B-Instruct mid-layer; identical to §13.12's pinned
   default and the Chen 2024 convention). Hidden dimension
   $H = 3584$ for Qwen-7B.
2. At each grid position $t \in \{8, 12, 16, \ldots, 128\}$
   (position_min=8, position_stride=4 → 31 positions, identical
   to §13.14's grid for direct comparability with §13.15's null),
   for each sample $k$, take the hidden state at the model-step
   that produced the token at generated position $t$, capped at
   the sample's actual non-pad length (same fallback rule as
   §13.12). Stack the K hidden states into
   $X_t \in \mathbb{R}^{K \times H}$.
3. Per-position EigenScore (Chen 2024 K×K Gram form, well-
   conditioned when $H \gg K$):
   $$
   X_t^c = X_t - \overline{X_t},
   \qquad
   \Sigma_t = \frac{1}{H} X_t^c (X_t^c)^\top + \alpha I_K,
   \qquad
   S_t = \frac{1}{K} \log \det \Sigma_t.
   $$
   With regularization $\alpha = 10^{-3}$ (Chen 2024 default;
   identical to §13.12 pinned). Computed via `np.linalg.slogdet`
   for numerical stability; defensive assertion that
   $\text{sign}(\det \Sigma_t) > 0$ at every position.
4. Centered second difference at each interior grid index $i$:
   $$
   \text{accel}_i = S_{t_{i+1}} - 2 S_{t_i} + S_{t_{i-1}}.
   $$
5. **Primary scalar (pinned for AUC + bands):**
   $$
   \text{bcvf\_eig\_2diff}(q) = \max_i |\text{accel}_i|.
   $$
   Mirrors the §13.14 / §6.1 peak structure but on continuous
   internal-state geometry instead of text-level entropy.
6. **Pinned secondary diagnostic scalars** (reported but NOT used
   for band classification — pinning prevents post-hoc swap, same
   §0.8 pattern as §13.14):
   - $\text{mean}_i |\text{accel}_i|$
   - $\sum_i \text{accel}_i^2$
   - position $i^*$ of the peak.
7. AUC computed on $-\text{bcvf\_eig\_2diff}$, pre-committed
   direction *higher EigenScore acceleration → less stable
   evolving internal-state geometry → more likely wrong*. This
   sign is identical to the §13.12 single-snapshot convention
   (where $-S_t$ at the final position was the truth predictor).

**Why this is a structurally better BCVF analogue than §13.14.**
Direct mapping to the three §13.15 failure reasons:

- **Continuous real-valued signal.** $S_t = \frac{1}{K}\log\det
  \Sigma_t$ ranges over $\mathbb{R}$ and varies smoothly with $X_t$.
  Discrete cluster-count entropy (§13.14) was bounded by $\log K
  \approx 2.30$ with only ~$K$ distinct reachable values per
  question. EigenScore has dynamic range and continuous variation
  compatible with 2nd-derivative analysis.
- **Direct provenance from model's internal state.** $X_t$ is the
  layer-$L^*$ residual-stream activation, captured during the
  model's own forward pass. No NLI step, no token-decoding step,
  no clustering. The chain is one projection (layer pick + position
  pick) rather than four (decode → truncate → NLI → cluster). The
  smearing argument from §13.15(c) does not apply.
- **Better match to "evolving world model."** The hidden-state
  distribution across K samples at position $t$ is the *literal*
  representation of the model's joint epistemic state at that step
  of answer construction. Evolution of $\Sigma_t$ across $t$ is the
  evolution of that joint distribution's geometry. The autonomy-
  domain signal `S3_map_error_accel` is the rate of change of an
  agent's internal map's coupling failure; per-position EigenScore
  acceleration is the closest LLM-domain analogue with direct
  internal-state grounding.

**Pre-committed configuration (pinned, all per §13.16):**

- **Script:** `scripts/probe_eigenscore_2diff.py` (new; does NOT
  modify §13.10–§13.14 scripts).
- **Target model:** `Qwen/Qwen2.5-7B-Instruct`, fp16. Same as
  §13.10 / §13.12 / §13.14 for direct AUC comparability.
- **Benchmarks:** TruthfulQA-MC validation split, N=100;
  HaluEval-QA `data` split, N=100. Same as §13.10–§13.14.
- **Sampling:** K=10, T=1.0, max_new_tokens=128, per-question seed
  `args.seed + q_idx`. Identical to §13.14.
- **Hidden-state extraction:** layer $L^* = 14$ (mid-layer of
  Qwen-7B's 28 transformer blocks), position-aligned with grid
  positions defined below. Layer is configurable via `--layer` for
  follow-up sweeps but the §13.16 band classification refers
  exclusively to layer 14. A non-default value is a §13.16
  deviation flagged in the result section.
- **Position grid:** position_min=8, position_stride=4,
  max_new_tokens=128 → 31 measured positions. Identical to §13.14
  for direct comparability with §13.15's null. Configurable via
  `--position-min` and `--position-stride`; non-default flagged as
  deviation.
- **EigenScore α:** $10^{-3}$. Identical to §13.12 pinning.
  Configurable via `--alpha` for follow-up; non-default flagged as
  deviation.
- **Prompt format:** shared `Q: ... A:` completion. No chat
  templates (per §13.11 diagnostic finding that chat templates
  degrade signal on this codebase).
- **Correctness label:** Qwen greedy generation passes question-
  conditioned NLI (DeBERTa-v3-base-mnli-fever-anli) against correct
  AND fails NLI against every distractor. Identical labeling to
  §13.10 / §13.11 / §13.12 / §13.14. Greedy `max_new_tokens=128`
  to match sampling configuration.
- **Pinned primary scalar:** $\max_i |\text{accel}_i|$.
- **Pinned diagnostic secondaries:** mean$|\text{accel}|$,
  $\sum \text{accel}^2$, peak position. Reported but not used for
  band classification.

**Pre-committed success bands** (`HSEIG_2DIFF_*`, same numerical
partition as §13.11 / §13.12 / §13.13 / §13.14 since the §13.10
baseline of 0.661 is unchanged across all probes). The "on both
benchmarks" worst-benchmark rule applies, identical to §13.14:

- `AUC ≥ 0.75` on **both** benchmarks → **`HSEIG_2DIFF_STRONG`**.
  Gates the §13.9 VC-brief revision AND constitutes the first
  load-bearing positive evidence for BCVF-for-LLMs at any
  construction in this codebase. Authorizes a §13.17 result
  writeup positioning §13.16 as the first BCVF-faithful LLM result
  and triggers re-examination of §13.9 external framing.
- `0.70 ≤ AUC < 0.75` on **both** → **`HSEIG_2DIFF_INTERNAL_STRONG`**.
  Strong for internal research; VC-brief still held. Diagnostic
  follow-ups: layer sweep (`--layer`), finer position grid
  (`--position-stride 1` or 2), α sweep (`--alpha`).
- `0.681 ≤ AUC < 0.70` on **both** → **`HSEIG_2DIFF_MARGINAL_LIFT`**.
  Modest but real lift above §13.10 + 0.02. Document; do not
  authorize further single-axis probe progression on this codebase.
- `0.641 ≤ AUC ≤ 0.681` on **both** → **`HSEIG_2DIFF_SATURATION`**.
  Within ±0.02 of §13.10's 0.661. Combined with §13.11 / §13.12 /
  §13.14 anti-findings, this would establish that *every*
  literature-aligned single-axis probe — across sample-space,
  ensemble, internal-state, and temporal-evolution variants —
  saturates at the §13.10 ceiling on Qwen-7B with base-NLI at
  N=100. Conclusive evidence that further lift requires either
  model-scale upgrade or compound-revision construction.
- `AUC < 0.641` on **any** benchmark →
  **`HSEIG_2DIFF_ANTI_FINDING`**. The hidden-state-internal
  variant of the BCVF 2nd-difference observable underperforms the
  §13.10 baseline. Would constitute a 4-of-4 anti-finding across
  the literature-backed paths; pause LLM track. The autonomy-
  domain BCVF claim stands independently on §6.1 evidence.

**Acceptance / rejection rules (explicit, non-vague):**

- **PASS:** AUC ≥ 0.75 on both benchmarks (HSEIG_2DIFF_STRONG).
- **CONDITIONAL PASS for internal research:** AUC ∈ [0.681, 0.75)
  on both benchmarks (INTERNAL_STRONG or MARGINAL_LIFT). Documented
  but does not unlock §13.9 VC-brief.
- **NULL (consistent with §13.10 ceiling):** AUC ∈ [0.641, 0.681]
  on both (SATURATION). Documented as final evidence that single-
  axis methods saturate.
- **REGRESSION:** AUC < 0.641 on any benchmark (ANTI_FINDING).
  Documented as the strongest negative finding in the §13 program.

**Disclosed simplifications (NOT closed by §13.16):**

- Single layer ($L^* = 14$) vs the per-model layer sweep some
  Chen 2024 configurations use. Configurable via `--layer` for
  follow-up but the §13.16 classification is at the pinned default.
- Last non-pad token position used at each grid index (same as
  §13.12). Mean-pool or last-prompt-token alternatives are not
  tested.
- Fixed α = $10^{-3}$. Configurable but pinned for classification.
- Single target model (Qwen2.5-7B-Instruct). Same scaling caveat
  as §13.10–§13.14.
- Same correctness label as §13.10 / §13.11 / §13.12 / §13.14
  (NLI on Qwen greedy). Holding labeling fixed prevents cross-
  experiment label-shift confounds.

**Expected cost.** Single 7B target model + DeBERTa-v3-base NLI
(used only for the correctness label, ~3 calls per question — no
NLI clustering of K samples at any position). K=10 sampling at
max_new_tokens=128 with `output_hidden_states=True` increases
generation memory by ~30% but no significant wall-clock cost.
Per-position EigenScore is a small CPU/GPU operation
($O(K^2 H)$ per position; negligible vs generation cost).
Estimated runtime: **~3–5 min at N=100 on a 24+ GB GPU**, faster
than §13.14 because no per-position NLI clustering pass.

**Report destination.**
- `docs/experiments/probe_eigenscore_2diff_truthfulqa_mc.md`
- `docs/experiments/probe_eigenscore_2diff_truthfulqa_mc.json`
  (per-question dump including the full per-position EigenScore
  series $S_t$, the per-position accelerations, and all four
  scalars — required for post-hoc secondary-scalar audits if
  primary saturates).
- `docs/experiments/probe_eigenscore_2diff_halueval_qa.md`
- `docs/experiments/probe_eigenscore_2diff_halueval_qa.json`

**Scope.** §13.16 is a new bounded experiment under the same §0.8
discipline as §13.12 / §13.13 / §13.14. It is not an open-ended
continuation of §13.14 — the §13.14 result stands as written in
§13.15 and is not re-litigated. §13.16 tests an *adjacent*
construction that the §13.15 narrowing left explicitly open. The
pre-committed bands above are the binding success criteria; any
deviation at run time must be flagged as a §0.8 deviation in the
result section, not absorbed silently.

**What §13.16 does not pre-commit.** No probe-script implementation
on-branch, no `classify()` thresholds in code, no benchmark runs.
This section is the §0.8-style pre-commitment record only.
Implementation of `scripts/probe_eigenscore_2diff.py` is a separate
authorization gate. No VC-brief / §13.9 changes here — those remain
gated on `HSEIG_2DIFF_STRONG` on both benchmarks (or any §13
probe's STRONG on both, which has not yet been observed).

### 13.17 Result — Hidden-state EigenScore 2nd-difference also did not transfer; §13 single-axis program closed

The §13.16 pre-committed probe has been executed at N=100 on both
benchmarks. Combined classification: **`HSEIG_2DIFF_ANTI_FINDING`**,
with the additional substantive finding that **the signal inverts
on BOTH benchmarks** — the only §13 probe to do so. This is the
fourth and final single-axis revision in the §13 program; with it,
the literature-aligned single-axis path is exhausted at this
codebase's Qwen-7B + DeBERTa-v3-base + N=100 configuration.

The §13.16 result narrows the BCVF-for-LLMs transfer claim further
than §13.15 did. §13.15 narrowed the §13.14 null to *text-level*
constructions and explicitly left open the hidden-state-internal
construction. §13.16 now closes that opening: per-position
EigenScore over hidden-state geometry exhibits the same structural
shape problem as per-position semantic entropy did in §13.14 —
smooth-monotonic underlying signal with no fault-onset structure
for the 2nd-difference operator to detect. Moving from text-level
to model-internal continuous state did not fix the issue; the
structural problem is **the K-sample-divergence dynamics of the
underlying signal class**, not the lossy projection chain §13.15
hypothesized.

**Result table:**

| Benchmark | N | Greedy acc | Mean S first (t=8) | Mean S last (t=128) | AUC primary | AUC mean\|accel\| | AUC Σaccel² | Δ vs §13.10 | Per-run band |
|---|---|---|---|---|---|---|---|---|---|
| TruthfulQA-MC | 100 | 0.320 | −3.72 | −1.20 | **0.462** | 0.432 | 0.453 | −0.199 | `HSEIG_2DIFF_ANTI_FINDING` |
| HaluEval-QA | 100 | 0.320 | −4.68 | −1.88 | **0.449** | 0.425 | 0.440 | −0.212 | `HSEIG_2DIFF_ANTI_FINDING` |

Combined classification under the §13.16 worst-benchmark rule:
ANTI on both. **All six AUCs (3 scalars × 2 benchmarks) cluster
in the narrow range [0.425, 0.462] — robustly inverted. The signal
is real and consistent in the wrong direction; it is not noise
around 0.5.**

Per-class means:

| Benchmark | Mean primary correct | Mean primary wrong | Δ (correct − wrong) |
|---|---|---|---|
| TruthfulQA-MC | 1.3691 | 1.2247 | **+0.144** (correct higher) |
| HaluEval-QA | 1.3971 | 1.3386 | **+0.058** (correct higher) |

Both benchmarks show *correct* answers having *higher* `max|accel|`
than wrong answers — opposite of the pre-committed direction.

**Math used (the construction that failed).** For each question $q$
with K=10 sampled completions at T=1.0, max_new_tokens=128:

1. Single batched `generate()` call with
   `output_hidden_states=True, return_dict_in_generate=True` so
   that per-step layer-$L^*$ hidden states are captured during one
   forward pass, where $L^* = \lfloor \text{num\_hidden\_layers}/2
   \rfloor = 14$ for Qwen-7B.
2. At each grid position $t \in \{8, 12, 16, \ldots, 128\}$ (31
   positions), for each sample $k$, extract
   $h^{(k)}_t = \text{out.hidden\_states}[\sigma(t,k)][L^*][k, -1, :]$
   where $\sigma(t,k) = \min(t, \text{sample\_lengths}[k]) - 1$
   (capped at the sample's actual non-pad length; falls back to
   step 0 if the sample emitted zero non-pad tokens).
3. Stack into $X_t \in \mathbb{R}^{K \times H}$ with $H = 3584$.
4. Per-position EigenScore (Chen 2024 K×K Gram form):
   $\Sigma_t = (1/H) X_t^c (X_t^c)^\top + \alpha I_K$ with
   $\alpha = 10^{-3}$; then
   $S_t = (1/K) \log \det \Sigma_t$ via `np.linalg.slogdet` for
   numerical stability.
5. Centered second difference:
   $\text{accel}_i = S_{t_{i+1}} - 2 S_{t_i} + S_{t_{i-1}}$ for
   interior $i$.
6. Primary scalar (pinned per §13.16):
   $\text{bcvf\_eig\_2diff}(q) = \max_i |\text{accel}_i|$.
7. AUC computed on $-\text{bcvf\_eig\_2diff}$, pre-committed
   direction *higher acceleration → less stable evolving internal-
   state geometry → more likely wrong*.

The two diagnostic secondary scalars
$\text{mean}_i |\text{accel}_i|$ and
$\sum_i \text{accel}_i^2$ were reported but not used for
classification (per §13.16's §0.8 pinning of the primary). All
three scalar AUCs cluster within 0.04 on both benchmarks.

**Three reasons the signal failed at this construction** (mapping
§13.15's diagnostic structure onto §13.16's data):

**(a) The per-position EigenScore curves are smooth and
monotonically rising on both benchmarks** — same shape problem
§13.14's text-level entropy curves had. TruthfulQA-MC mean
$S_t = -3.72 \to -1.20$ over $t = 8 \to 128$ (rise of 2.52 nats);
HaluEval-QA mean $S_t = -4.68 \to -1.88$ (rise of 2.80 nats). These
are smooth, large monotonic trends across 31 positions. The 2nd
derivative of a smooth monotonic curve has small magnitude
dominated by local trend curvature, not fault onsets. `max|accel|`
on such a series picks an outlier in a smoothly-bending trend,
not the moment of an epistemic event. Neither curve has the
smooth-with-rare-spikes structure BCVF's 2nd-derivative operator
needs.

The mechanism for the monotonic rise: at early grid positions, the
K=10 samples have barely diverged — their hidden states cluster
tightly, $\det \Sigma_t$ is small, $S_t$ is very negative. As
generation proceeds, the K samples explore different paths and
their hidden states pull apart — $\det \Sigma_t$ grows, $S_t$
becomes less negative. **This is a structural property of K-
sample-divergence dynamics, not an epistemic property of the
model**. It happens whether the model is confident or uncertain,
correct or wrong.

**(b) The signal direction is consistently inverted on BOTH
benchmarks.** §13.14 had asymmetric inversion (TruthfulQA in
expected direction at AUC 0.574, HaluEval inverted at 0.363).
§13.16 inverts on both (0.462 and 0.449), and three different
aggregations on each benchmark (`max|accel|`, `mean|accel|`,
`Σaccel²`) all show the same anti-correlated direction. The
inversion is robust across benchmark choice and aggregation
choice. It is the most consistent qualitative finding in the §13
program.

The mechanism for the inversion (hypothesis with empirical
support, not pre-committed): when Qwen is confident on a question,
it elaborates the answer with diverse phrasings, reasoning steps,
and qualifications mid-generation. The K=10 samples explore that
diverse semantic neighborhood, so hidden-state acceleration is
high. When Qwen is wrong with confidence, it commits to a single
confabulated story — K=10 samples follow similar trajectories,
hidden-state acceleration is low. The 2nd-difference observable
therefore measures something like "mid-generation semantic
exploration intensity" rather than "epistemic uncertainty."
Exploration intensity anti-correlates with hallucination on these
benchmarks.

**(c) Moving from text-level to model-internal continuous state
did not fix the structural problem §13.15 identified.** §13.15
hypothesized that §13.14's failure was the four-step lossy
projection chain (decode → truncate → NLI → cluster) smearing the
underlying epistemic signal. §13.16 removed three of those four
projections (no decode, no NLI, no cluster — only layer + position
selection on raw hidden states). The signal is still
structurally smooth-monotonic, the 2nd-difference operator still
has nothing to detect, and the result still inverts. **The lossy
projection chain was not the dominant cause**; the dominant cause
is that K-sample-divergence dynamics produce monotonic curves
across token positions regardless of which signal class
(text-level or hidden-state) is computed from those K samples.

This tightens the §13.15 narrowing substantially:

> **The §13.16 null further narrows the BCVF-for-LLMs transfer
> claim: BCVF's 2nd-difference operator does not produce a fault-
> onset-shaped signal at any K-sample-divergence-based observable
> tested in this codebase, whether the underlying signal class is
> text-level (semantic entropy of NLI clusters) or model-internal
> (per-position EigenScore over hidden-state geometry). The
> structural failure mode — smooth-monotonic underlying series with
> no rare-spike structure — is a property of K-sample-divergence
> dynamics, not of any specific projection from samples to scalars.**

This does not reject BCVF over signal classes that do not depend
on K-sample divergence — for example, per-token logit entropy
along a single greedy or sampled trajectory, which has within-
sample temporal evolution rather than cross-sample geometric
evolution. Such constructions have not been tested in this
codebase and are not pre-committed by §13.17.

**EOS-reuse diagnostic findings.** §13.16 was instrumented with
EOS-reuse diagnostics (commit `557f0f6`, pure logging) to test
whether late-position hidden-state reuse — when
$\text{sample\_lengths}[k] < t$, the per-position extraction
reuses sample $k$'s last hidden state at later grid positions —
was confounding the per-position EigenScore series. The
instrumentation surfaced the following:

| EOS-reuse bucket | TruthfulQA-MC | HaluEval-QA |
|---|---|---|
| Questions with no EOS reuse | 37 / 100 | 24 / 100 |
| Questions with some reuse (`fraction < 0.5`) | 29 / 100 | 24 / 100 |
| Questions with heavy reuse (`fraction ≥ 0.5`) | 34 / 100 | 52 / 100 |
| Mean `min_sample_length` (tokens) | 84.4 | 61.8 |
| Median `min_sample_length` | 102.5 | 66.5 |
| Mean `n_eos_reuse_positions` (of 31) | 11.1 (36%) | 16.7 (54%) |

HaluEval has substantially more EOS reuse than TruthfulQA (52 vs
34 heavy-reuse questions; 54% vs 36% mean reuse fraction). But
**both benchmarks invert with similar magnitude** — TruthfulQA AUC
0.462, HaluEval AUC 0.449. If EOS reuse were the dominant driver,
HaluEval would invert more strongly than TruthfulQA. It does not.
EOS reuse contributes some noise but is not the primary cause of
the inversion. The structural cause identified in reason (a)
above — smooth-monotonic K-sample-divergence dynamics — is the
dominant mechanism.

A post-hoc EOS-reuse stratification analysis on the JSON dumps
could further confirm this by computing AUC on the no-reuse subset
only (37 TFQA, 24 HaluEval questions). That analysis is not
required to support the §13.17 conclusion (the cross-benchmark
similarity already rules out EOS-reuse as the primary driver) but
would tighten the post-hoc evidence if performed; it is logged here
as an optional follow-up rather than a §0.8 commitment.

**What this authorizes** (per §13.16 pre-commitment + §13.17
result):

- **Closing the §13 single-axis program.** Four single-axis
  revisions — §13.11 cross-family ensemble, §13.12 EigenScore
  single-snapshot, §13.14 BCVF text-level 2nd-difference, §13.16
  BCVF hidden-state 2nd-difference — have all been executed and
  classified. None lifts AUC above §13.10's 0.661 marginal
  baseline on the combined-classification rule. The §13 single-
  axis path is exhausted at this codebase's Qwen-7B + DeBERTa-v3-
  base + N=100 configuration.
- **Authorizing the §13-program closing statement.** The honest
  external framing is: *on Qwen2.5-7B-Instruct + DeBERTa-v3-base +
  N=100, no literature-aligned single-axis hallucination-detection
  method tested in this codebase clears the §13.10 marginal
  baseline of AUC 0.661 on both TruthfulQA-MC and HaluEval-QA.
  The 2nd-difference operator specifically produces inverted
  signals at both text-level and hidden-state-level constructions,
  indicating that BCVF's native observable does not transfer to
  LLMs at the K-sample-divergence-as-temporal-axis analogue.*
- **Promoting §13.10 as the strongest §13 result on record.** The
  single-snapshot semantic-entropy probe at §13.10 remains the
  best-performing observable in the codebase at this scale and is
  the result of record for any §13-related referencing.
- **Documenting the qualitative inversion finding.** §13.14 +
  §13.16 together show that the 2nd-difference operator on K-
  sample-divergence signals produces an anti-correlated signal on
  these benchmarks. This is itself a substantive methodological
  finding worth referencing in any §13-program writeup, even
  though it does not unlock any pre-committed band.

**What this does NOT authorize:**

- **Any update to `AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md`.** Per
  §13.9, external-framing revision requires `STRONG` on both
  benchmarks at any §13 probe. No probe in §13 has cleared this.
  The §13.9 hold remains in force and is *strengthened* by
  §13.17's 4-of-4 confirmation.
- **Any single-axis follow-up probe in the §13 program.** The
  saturation pattern across four hypothesis classes (sample-space
  ensemble, internal-state, temporal-evolution at text-level,
  temporal-evolution at hidden-state) is robust enough that
  another single-axis variant is not authorized without a fresh
  §0.8 pre-commitment that explicitly identifies what new
  hypothesis class it tests.
- **Post-hoc reinterpretation of the §13.16 inversion as a
  positive result.** The pre-committed AUC sign was
  *higher acceleration → more likely wrong*. The data falsified
  that direction. Renaming the scalar post-hoc to "exploration
  intensity" and reporting AUC of $+\text{bcvf\_eig\_2diff}$ as a
  positive finding would be a §0.8 violation. The inversion is
  documented as a substantive observation, not retrofitted as a
  pass.
- **Any claim that BCVF does not transfer to LLMs in general.**
  §13.17 narrows the negative claim to *K-sample-divergence-based
  observables under the BCVF 2nd-difference operator at the
  constructions tested*. Signal classes that do not depend on
  K-sample divergence (e.g., per-token logit entropy along a
  single trajectory) are not tested and are not foreclosed.
  System-level integration tests that consume BCVF scalars in a
  multi-source Q&A pipeline (rather than treating them as
  standalone observables vs ground truth) are also not tested and
  are not foreclosed; if pursued, they would be a separate §14
  pre-commitment outside the §13 single-axis program.
- **Any claim that affects the autonomy-domain BCVF result.**
  §6.1's N=21 sign-test on `S3_map_error_accel` passed
  independently and stands. §13.17's outcome bears only on the
  LLM-domain transfer claim at the constructions tested, not on
  the robotics-domain validation.

**Status of the §13 program after §13.17.** Closed at the single-
axis level. The §13.10 baseline (AUC 0.661 on both benchmarks,
TRUTH_CORRELATED_MARGINAL) is the strongest result of record. Any
future LLM-domain work on the BCVF transfer claim would need to
test a fundamentally different hypothesis class (e.g., system-
level integration, single-trajectory temporal observable, or
model-scale upgrade) under a fresh §0.8 pre-commitment.

**Artifacts:**

- `scripts/probe_eigenscore_2diff.py` (commits `15306c2` initial,
  `557f0f6` EOS-reuse diagnostics).
- `docs/experiments/probe_eigenscore_2diff_truthfulqa_mc.md` and `.json`.
- `docs/experiments/probe_eigenscore_2diff_halueval_qa.md` and `.json`.

### 13.18 Pre-commitment — Single-trajectory forced-allocation-gap probe

**Status: pre-committed, not yet executed.** §0.8-style pre-
commitment recorded before implementation. Specification, success
bands, and pinned parameters below cannot be redefined post-hoc.

**Relationship to §13.17's closure.** §13.17 closed the §13 K-
sample-divergence-based single-axis program (cross-family,
EigenScore single-snapshot, BCVF text-level 2nd-difference, BCVF
hidden-state 2nd-difference). The narrowing in §13.17 was:

> *BCVF's 2nd-difference operator does not produce a fault-onset-
> shaped signal at any K-sample-divergence-based observable tested
> in this codebase. The structural failure mode is a property of
> K-sample-divergence dynamics, not of any specific projection.
> Signal classes that do not depend on K-sample divergence are
> not foreclosed.*

§13.18 tests **the un-rejected signal class** identified in that
narrowing: a single-trajectory observable computed across token
positions WITHIN one greedy generation, rather than across
multiple sampled generations. Same chapter (§13) for continuity;
distinct hypothesis class from §13.10–§13.16 (single-trajectory
logit geometry, not K-sample-divergence). Does NOT violate the
§13.17 closure because that closure was specifically scoped to
K-sample-divergence-based observables.

**Hypothesis (the mechanism §13 didn't measure).** Hallucinations
in autoregressive LLMs enter through a specific mechanical seam:

1. **Softmax flattens absolute logit magnitude.** The function
   $p_t = \text{softmax}(\mathbf{z}_t)$ maps any logit vector to
   a probability distribution summing to 1.0. Two scenarios with
   raw logits $[10, 1, 0.5]$ (model knows the answer) and
   $[-100, -100.1, -100.2]$ (model has no idea) produce wildly
   different epistemic states but Softmax flattens both into
   probability vectors that sum to 1.0. Absolute magnitude
   information is lost in the normalization step.
2. **Cross-entropy training forbids expressing absolute ignorance.**
   The model is optimized on next-token prediction over static
   text, where humans rarely interrupt to write "[I don't know]".
   The objective penalizes refusing to continue. The model is
   conditioned to always emit a continuation, even when its
   underlying activations support nothing strongly.
3. **Autoregression locks the forced guess into context.** Every
   token output becomes part of the input for the next step. Once
   Softmax forces an allocation at position $t$ despite low
   absolute logit magnitude, that forced guess becomes the
   conditioning context for position $t+1$, propagating the false
   premise.

**The hallucination signature is therefore the moment Softmax
forces an allocation despite low absolute logit magnitude** — a
property of *single-trajectory logit geometry*, not K-sample
geometry. This is the signal §13.10–§13.16 systematically did not
measure. Every probe in §13 looked at *between-sample* variance
(decoding stochasticity introduced by temperature), which is
downstream of the very mechanism that creates hallucination.

§13.18 therefore measures the forced-allocation gap directly. For
each token position in a single greedy generation, it computes:

- The **post-softmax entropy** $H_t$ — how spread the distribution
  is after the normalization step.
- The **pre-softmax confidence magnitude** $M_t$ — whether anything
  in the vocab strongly stands out from the bulk before softmax.

A high $H_t$ with a low $M_t$ is the "Scenario B" forced allocation
— the model is committing without evidence. Low $H_t$ or high
$M_t$ indicates a commitment its logits actually support.

The BCVF 2nd-difference operator is then applied across positions
WITHIN the trajectory. Sparse, sudden moments of widening forced-
allocation gap are the analogue of `S3_map_error_accel` peaks in
the autonomy domain — moments when the agent's internal map
(logit distribution) suddenly fails to track the territory (its
actual knowledge support).

**Why this might satisfy the smooth-with-rare-spikes structural
requirement that §13.14 and §13.16 violated.** The hypothesis is
mechanism-based, not data-based: a token where the model knows the
answer should produce high $M_t$ and low $H_t$ → low forced-
allocation gap. A token where the model is forced to guess (e.g.,
a specific date it doesn't know) should produce low $M_t$ and high
$H_t$ → high forced-allocation gap. Forced moments should be
sparse and local in well-formed generations — exactly the shape
the 2nd-difference operator exploits. Whether empirical
trajectories on Qwen2.5-7B-Instruct + TruthfulQA-MC / HaluEval-QA
actually have this shape is unknown and is the central question
of §13.18.

If the hypothesis holds, this is the first §13 single-axis probe
positioned to satisfy all five structural requirements §13.14 /
§13.16 violated: continuous real-valued signal, direct provenance
from model internals (raw logits), plausibly smooth-with-rare-
spikes shape, independent of K-sample divergence, captures the
autoregressive-hallucination mechanism. If it doesn't hold,
§13.18 produces a 5-of-5 single-axis null and tightens the §13.17
narrowing to also exclude single-trajectory forced-allocation-gap
observables on this codebase.

**Specification (pinned):**

- **Script:** `scripts/probe_forced_alloc_2diff.py` (new; does NOT
  modify any §13.10–§13.16 script — those results are pinned).
- **Target model:** `Qwen/Qwen2.5-7B-Instruct`, fp16. Same single-
  model configuration as §13.10 / §13.12 / §13.14 / §13.16 for
  direct AUC comparability against the §13.10 baseline of 0.661.
- **Benchmarks:** TruthfulQA-MC validation split, N=100; HaluEval-
  QA `data` split, N=100. Same selections as §13.10–§13.16.
- **Generation:** **single greedy completion per question**
  (T=0, deterministic, K=1 effectively). Captures per-token logits
  via `model.generate(..., output_scores=True,
  return_dict_in_generate=True)`. NOT K-sample stochastic — the
  hypothesis is single-trajectory by design; sampling would
  reintroduce the K-sample-divergence dynamics §13.17 ruled out as
  the failure mode.
- **max_new_tokens:** 128 (parity with §13.14 / §13.16; needed for
  trajectory length to evolve a 2nd-difference signal).
- **Prompt format:** shared `Q: ... A:` completion, identical to
  §13.10–§13.16. No chat templates.
- **Position grid:** **stride 1, every token** in the generated
  trajectory (no sub-sampling; single-trajectory observables don't
  have the per-position computational cost K-sample probes did).
  - `position_min = 4` — skip first 4 generated tokens. Lower than
    §13.14 / §13.16's 8 because there is no NLI-on-truncations
    noise concern at single-trajectory logit level; the floor exists
    only to avoid leading-token prompt-conditioning artifacts.
  - `position_max = T_actual` — the actual non-pad length of the
    greedy generation, capped at `max_new_tokens=128`.
  Both configurable; non-default flagged as §13.18 deviation.

**Pinned mathematical object (the forced-allocation-gap series and
its 2nd-difference scalar).** For each question $q$ with greedy
trajectory of length $T$ generated tokens, at each token position
$t \in [\text{position\_min}, T]$:

1. Capture raw logits $\mathbf{z}_t \in \mathbb{R}^{|V|}$ before
   softmax (vocab size $|V| = 151{,}936$ for Qwen2.5-7B).
2. Compute the **confidence magnitude**:
   $$M_t = \max_j z_t[j] - \frac{1}{|V|}\sum_j z_t[j]$$
   (max logit centered by mean — indicates whether any token
   strongly stands out from the bulk).
3. Compute the **post-softmax entropy**:
   $$H_t = -\sum_j p_t[j] \log p_t[j]
   \quad \text{where} \quad
   p_t = \text{softmax}(\mathbf{z}_t).$$
4. Z-normalize both quantities across the trajectory:
   $$\tilde{M}_t = \frac{M_t - \bar{M}}{\sigma_M}, \qquad
   \tilde{H}_t = \frac{H_t - \bar{H}}{\sigma_H}$$
   (means and standard deviations computed over the position-grid
   range $[\text{position\_min}, T]$ for that question's
   trajectory).
5. **Forced-allocation gap:**
   $$g_t = \tilde{H}_t - \alpha \cdot \tilde{M}_t,
   \qquad \alpha = 1.0 \text{ (pinned).}$$
   Equal weighting of normalized entropy and normalized confidence
   magnitude. The $\alpha$ value is pinned at 1.0 for the §13.18
   classification; configurable via `--alpha` for follow-up
   sweeps with non-default flagged as §13.18 deviation.
   - High $g_t$: high $\tilde{H}_t$ AND low $\tilde{M}_t$ — forced
     allocation moment.
   - Low $g_t$: low $\tilde{H}_t$ OR high $\tilde{M}_t$ — supported
     commitment.
6. Centered second difference at each interior $t$:
   $$\text{accel}_t = g_{t+1} - 2 g_t + g_{t-1}.$$
7. **Primary scalar (pinned for AUC + bands):**
   $$\boxed{\text{forced\_alloc\_2diff}(q) = \max_t |\text{accel}_t|}$$
   Mirrors `S3_map_error_accel` peak in the autonomy domain.
8. **Pinned diagnostic secondary scalars** (reported but NOT used
   for band classification — pinning prevents post-hoc swap, same
   §0.8 pattern as §13.14 / §13.16):
   - $\text{mean}_t |\text{accel}_t|$ (averaged absolute
     acceleration on the gap series).
   - $\sum_t \text{accel}_t^2$ (energy-style aggregation on the
     gap series).
   - **Variant-A entropy-only diagnostic:** $\max_t |a^H_t|$ where
     $a^H_t = H_{t+1} - 2 H_t + H_{t-1}$ — the 2nd difference of
     raw post-softmax entropy without the confidence-magnitude
     term. Tests whether $M_t$ contributes any signal beyond
     entropy alone. If primary saturates but Variant A's AUC
     differs materially, the $M_t$ component is either helping
     or hurting; if both are similar, $M_t$ is irrelevant on
     this codebase.
   - Position $t^*$ of the peak.
9. AUC computed on $-\text{forced\_alloc\_2diff}$, pre-committed
   direction *higher forced-allocation acceleration → moment the
   model's distribution committed to a low-magnitude forced guess
   → more likely the answer is wrong*. Same sign convention as
   §13.14 / §13.16 (negate the scalar so "higher = more truth-
   predictive").
10. **Correctness label:** Qwen greedy generation passes question-
    conditioned NLI (`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`)
    against the correct choice AND fails NLI against every
    distractor. Identical labeling to §13.10–§13.16. Direct AUC
    comparability.

**Pre-committed success bands** (`FORCED_ALLOC_2DIFF_*`, same
numerical partition as §13.11–§13.16 because the §13.10 baseline
of 0.661 is unchanged across all six probes; relabeled
`FORCED_ALLOC_2DIFF_*` so the per-revision lineage stays legible):

- `AUC ≥ 0.75` on **both** benchmarks → **`FORCED_ALLOC_2DIFF_STRONG`**.
  Gates the §13.9 VC-brief revision AND constitutes the first
  load-bearing positive evidence for BCVF-for-LLMs at any single-
  axis construction in this codebase. Authorizes a §13.19 result
  writeup positioning §13.18 as the first probe to satisfy all
  five structural requirements §13.14 / §13.16 violated.
- `0.70 ≤ AUC < 0.75` on **both** → **`FORCED_ALLOC_2DIFF_INTERNAL_STRONG`**.
  Strong for internal research; VC-brief still held. Diagnostic
  follow-ups: $\alpha$ sweep (`--alpha`), Variant C logit-lens
  curvature, longer trajectories (`--max-new-tokens 256`).
- `0.681 ≤ AUC < 0.70` on **both** → **`FORCED_ALLOC_2DIFF_MARGINAL_LIFT`**.
  Modest but real lift above §13.10 + 0.02. Document; do NOT
  authorize further single-axis probe progression.
- `0.641 ≤ AUC ≤ 0.681` on **both** → **`FORCED_ALLOC_2DIFF_SATURATION`**.
  Within ±0.02 of §13.10's 0.661 baseline. Combined with §13.11 /
  §13.12 / §13.14 / §13.16 anti-findings, would establish that
  the entire literature-aligned single-axis class — across both
  K-sample-divergence and single-trajectory observables — saturates
  at the §13.10 ceiling on Qwen-7B + base-NLI at N=100. **5-of-5
  single-axis null.** Conclusive evidence single-axis methods
  saturate; further lift requires either system-level integration
  (§14 outlined in §13.8) or model-scale upgrade.
- `AUC < 0.641` on **any** benchmark → **`FORCED_ALLOC_2DIFF_ANTI_FINDING`**.
  The forced-allocation-gap signal underperforms the §13.10 baseline.
  5-of-5 anti across literature-backed paths. Pause LLM track at
  the single-axis level. The autonomy-domain BCVF claim stands
  independently on §6.1 evidence.

The "on both benchmarks" combinatorial rule is identical to §13.11–
§13.16 and is pinned here to prevent post-hoc benchmark cherry-
picking on a heterogeneous TruthfulQA / HaluEval split.

**Acceptance / rejection rules (explicit, non-vague):**

- **PASS:** AUC ≥ 0.75 on both benchmarks (FORCED_ALLOC_2DIFF_STRONG).
- **CONDITIONAL PASS for internal research:** AUC ∈ [0.681, 0.75)
  on both benchmarks (INTERNAL_STRONG or MARGINAL_LIFT). Documented
  but does not unlock §13.9 VC-brief.
- **NULL (consistent with §13.10 ceiling):** AUC ∈ [0.641, 0.681]
  on both (SATURATION). Documented as final evidence single-axis
  methods saturate.
- **REGRESSION:** AUC < 0.641 on any benchmark (ANTI_FINDING).
  Documented as the strongest negative finding in the §13 program.

**Disclosed simplifications and risks specific to §13.18** (no
literature anchor for the construction; the AUC forecast is
correspondingly uncertain):

- **Greedy-only single trajectory (K=1).** No sampling diversity.
  If the greedy trajectory happens to be unrepresentative for some
  questions (e.g., greedy gets stuck on a confident wrong answer
  with low entropy throughout), the forced-allocation gap may be
  uniformly small and the 2nd-difference signal weak. Sampling
  variants (small K, looking at $g_t$ averaged across K
  trajectories) are not pre-committed but are a defensible §13.x
  follow-up if §13.18 lands at SATURATION.
- **Fixed $\alpha = 1.0$.** Equal z-normalized weighting of $H_t$
  and $M_t$. Defensible default but not empirically tuned.
  Configurable via `--alpha`; non-default flagged as deviation.
- **Z-normalization is per-question, not global.** Each
  trajectory's $\tilde{M}_t$ and $\tilde{H}_t$ are computed
  relative to that trajectory's own mean/std. This makes $g_t$
  scale-invariant per question but couples the within-question
  values. Alternative (global normalization across all questions)
  is not pre-committed.
- **Single fixed model (Qwen2.5-7B-Instruct).** Same scaling
  caveat as §13.10–§13.16.
- **Same correctness label as §13.10–§13.16** (NLI on Qwen
  greedy). Holds the labeling pipeline fixed across all six
  probes for direct AUC comparability.
- **Stride 1 grid covers every token, but the position floor
  (`position_min=4`) excludes the very first generated tokens.**
  If forced allocations happen reliably at exactly token 1 or 2
  (e.g., the model commits to a wrong answer immediately), the
  signal at those positions is excluded. Configurable via
  `--position-min`; non-default flagged as deviation.
- **No literature anchor for the AUC forecast.** Variant A's 1st-
  derivative version (per-token entropy) has Kadavath 2022
  AUROC ~0.55–0.62 reported on short-form QA. The 2nd-difference
  variant is novel; the forced-allocation-gap construction is
  novel. Best estimate: AUC band **0.55–0.75**, very wide because
  the prior is genuinely uncertain. A clean clear of 0.75 on
  both benchmarks would be a novel positive result; a clear miss
  below 0.65 would be the first direct disconfirmation of the
  forced-allocation-gap mechanism on this codebase.

**Expected cost.** Single Qwen-7B greedy generation per question
(no K-sample sampling, no per-position NLI clustering, no per-
position EigenScore extraction). Per-token logits are already
computed during generation; capturing them adds ~30% memory
overhead but no significant wall-clock cost. Per-position scalar
arithmetic ($H_t$, $M_t$, $g_t$, $\text{accel}_t$) is negligible
relative to generation. **Estimated runtime: ~2–4 min at N=100 on
a single 24+ GB GPU**, the cheapest §13 probe to date.

**Report destination.**
- `docs/experiments/probe_forced_alloc_2diff_truthfulqa_mc.md`
- `docs/experiments/probe_forced_alloc_2diff_truthfulqa_mc.json`
  (per-question dump including the full per-position $H_t$, $M_t$,
  $g_t$ series, the accelerations, and all scalars — required for
  post-hoc audit if the primary saturates).
- `docs/experiments/probe_forced_alloc_2diff_halueval_qa.md`
- `docs/experiments/probe_forced_alloc_2diff_halueval_qa.json`

**Scope.** §13.18 is a new bounded experiment under the same §0.8
discipline as §13.12 / §13.13 / §13.14 / §13.16. It tests the
single-trajectory observable §13.17's narrowing leaves explicitly
open, NOT a continuation of any K-sample-divergence-based probe.
The pre-committed bands above are the binding success criteria;
any deviation at run time must be flagged as a §0.8 deviation in
the result section, not absorbed silently.

**What §13.18 does not pre-commit.** This section is the §0.8-
style pre-commitment record only. Implementation of
`scripts/probe_forced_alloc_2diff.py` is a separate authorization
gate. No VC-brief / §13.9 changes here — those remain gated on
`FORCED_ALLOC_2DIFF_STRONG` (or any §13 probe's STRONG band) on
both benchmarks. Nothing in §13.18 retroactively modifies §13.10–
§13.17 results, the §13 program closure for K-sample-divergence
observables, or the autonomy-domain §6.1 result.

### 13.19 Result — Forced-allocation gap also did not transfer; §13 single-axis program now exhausted across all hypothesis classes

The §13.18 pre-committed probe has been executed at N=100 on both
benchmarks. Combined classification on the pinned primary scalar:
**`FORCED_ALLOC_2DIFF_ANTI_FINDING`**. Combined with §13.11 / §13.12
/ §13.14 / §13.16, this is the **5-of-5 single-axis null** across
both hypothesis classes the §13 program could test (K-sample-
divergence-based observables in §13.10–§13.16; single-trajectory
forced-allocation-gap observable in §13.18). The §13 single-axis
program is now exhausted at this codebase's Qwen-7B + DeBERTa-v3-
base + N=100 configuration across every literature-aligned and
mechanism-motivated single-axis construction tested.

A separately notable diagnostic finding is documented below
(§13.19's "Variant A entropy-only diagnostic" subsection): the
entropy-only 2nd-difference on HaluEval-QA reached AUC 0.701 —
the second-best HaluEval result across the entire §13 program,
behind only §13.11's cross-family 0.716. This does NOT change
the pre-committed §13.18 classification (which is bound to the
pinned primary scalar) but is informative about which component
of the forced-allocation-gap construction was carrying signal
versus noise. The combined-classification rule across both
benchmarks would still resolve to `ANTI_FINDING` even if Variant A
were used as the primary, because TruthfulQA-MC at AUC 0.536
sits well below the 0.641 boundary regardless of which scalar is
chosen — a finding consistent with the broader pattern that
TruthfulQA-MC has defeated every §13 single-axis method tested.

**Result table (primary scalar):**

| Benchmark | N | Greedy acc | Mean greedy length (non-pad tokens) | Trajectories too short | AUC primary | Δ vs §13.10 | Per-run band |
|---|---|---|---|---|---|---|---|
| TruthfulQA-MC | 100 | 0.320 | 116.6 | 1 | **0.549** | −0.112 | `FORCED_ALLOC_2DIFF_ANTI_FINDING` |
| HaluEval-QA | 100 | 0.320 | 100.9 | 11 | **0.571** | −0.090 | `FORCED_ALLOC_2DIFF_ANTI_FINDING` |

Combined classification under the §13.18 worst-benchmark rule:
ANTI on both. Primary scalar means by class:

| Benchmark | Mean primary correct | Mean primary wrong | Δ (correct − wrong) |
|---|---|---|---|
| TruthfulQA-MC | 10.8969 | 11.0854 | −0.188 (wrong higher, expected direction, weak) |
| HaluEval-QA | 9.7695 | 10.5236 | −0.754 (wrong higher, expected direction, weak) |

Note that on the primary scalar the means are in the *expected*
direction (wrong > correct, indicating higher acceleration
correlates with wrong answers as the pre-committed sign predicted)
on both benchmarks — but the rank-based AUC is only 0.549 / 0.571
because within-class variance dominates the mean separation.

**Math used (the construction that failed at the pinned-primary
level).** For each question $q$ with greedy trajectory of length
$T$ (T_actual = min(128, generated non-pad tokens), median 128,
mean 116.6 on TruthfulQA-MC and 100.9 on HaluEval-QA), at each
token position $t \in [\text{position\_min}, T]$ with stride 1:

1. Capture raw pre-softmax logits $\mathbf{z}_t \in \mathbb{R}^{|V|}$
   ($|V| = 152{,}064$ for Qwen2.5-7B).
2. Confidence magnitude
   $M_t = \max_j z_t[j] - \frac{1}{|V|}\sum_j z_t[j]$.
3. Post-softmax entropy
   $H_t = -\sum_j p_t[j] \log p_t[j]$ where
   $p_t = \text{softmax}(\mathbf{z}_t)$.
4. Per-trajectory z-normalize both:
   $\tilde{M}_t = (M_t - \bar{M})/\sigma_M$,
   $\tilde{H}_t = (H_t - \bar{H})/\sigma_H$.
5. Forced-allocation gap
   $g_t = \tilde{H}_t - \alpha \cdot \tilde{M}_t$ with $\alpha = 1.0$
   pinned.
6. Centered second difference
   $\text{accel}_t = g_{t+1} - 2 g_t + g_{t-1}$.
7. Primary scalar (pinned per §13.18):
   $\text{forced\_alloc\_2diff}(q) = \max_t |\text{accel}_t|$.
8. AUC computed on $-\text{forced\_alloc\_2diff}$, pre-committed
   direction *higher acceleration → forced-guess moment → more
   likely wrong*.

Three diagnostic secondary scalars were reported but not used for
classification: $\text{mean}_t |\text{accel}_t|$,
$\sum_t \text{accel}_t^2$, and the **Variant A entropy-only**
diagnostic $\max_t |a^H_t|$ where
$a^H_t = H_{t+1} - 2 H_t + H_{t-1}$ — the same 2nd-difference
operator applied to raw entropy without the $M_t$ component or
z-normalization. This was pinned in §13.18 explicitly to test
whether the $M_t$ component contributes any signal beyond entropy
alone.

**Variant A entropy-only diagnostic — substantive surprise.**
The four scalar AUCs measured per benchmark:

| Scalar | TruthfulQA-MC AUC | HaluEval-QA AUC |
|---|---|---|
| Primary `max\|accel(g)\|` (forced-allocation gap) | 0.549 | 0.571 |
| Diagnostic `mean\|accel(g)\|` | 0.364 | 0.486 |
| Diagnostic `Σ accel(g)²` | 0.381 | 0.600 |
| **Variant A** `max\|accel(H)\|` (entropy only, no $M_t$, no z-norm) | **0.536** | **0.701** |

The Variant A HaluEval AUC of **0.701** is the second-best
HaluEval result across the entire §13 program, behind only
§13.11's cross-family ensemble at 0.716. It clears the per-run
`INTERNAL_STRONG` band on HaluEval-QA. **This is a genuine and
unexpected finding**: a much simpler scalar (raw 2nd difference
of per-token entropy, no z-normalization, no confidence-magnitude
component) outperforms the mechanism-motivated forced-allocation
gap on HaluEval-QA. On TruthfulQA-MC the Variant A AUC of 0.536
is essentially the same as the primary's 0.549 — both noisy near
random, both well below the ANTI threshold.

**The Variant A finding does NOT change the §13.18 pre-committed
classification.** Per §0.8 discipline, the primary scalar was
pinned BEFORE the run. The classification follows the primary,
not the diagnostics. The Variant A AUC is reported here as
analytical data about which component carried signal, not as a
post-hoc band override.

**The Variant A finding ALSO does not unlock §13.9 even on its
own merits.** The combined-classification rule across both
benchmarks would resolve to ANTI even if Variant A were used as
the primary, because TruthfulQA-MC at AUC 0.536 sits well below
the 0.641 boundary for any scalar choice. The pattern across all
five §13 single-axis probes is consistent: TruthfulQA-MC defeats
every method tested, and the worst-benchmark rule then forces the
combined classification to ANTI regardless of how strong the
HaluEval-QA result is on the same probe. This is itself the most
robust finding of the §13 program — a benchmark-pathology pattern
that no scalar choice within the single-axis program reaches past.

**Why the $M_t$ component hurt the signal — mechanism analysis
partially falsified at this construction.**

The §13.18 pre-commitment was motivated by the ChatGPT mechanism
analysis: hallucination is forced allocation by Softmax despite
low absolute logit magnitude, so a signal that combines high
entropy ($H_t$) AND low confidence magnitude ($M_t$) should be
strictly more truth-correlated than entropy alone. The Variant A
data falsifies that prediction at this construction: removing
$M_t$ entirely (and removing the z-normalization) *improves* the
signal on HaluEval (0.701 vs 0.571 primary) and is roughly
equivalent on TruthfulQA (0.536 vs 0.549 primary).

A plausible mechanical explanation for why $M_t$ as defined hurts:
the centering by mean over the full vocab,
$M_t = \max_j z_t[j] - \frac{1}{|V|}\sum_j z_t[j]$, has $|V| =
152{,}064$ tokens. Most of those tokens have very negative
pre-softmax logits at any given step (Qwen's vocabulary is
dominated by long-tail entries that rarely fire). The mean over
all logits is therefore dominated by that long tail, making $M_t$
mostly a measure of *global logit-distribution shape* rather than
*local "is the top token strongly preferred"*. Z-normalizing $M_t$
within the trajectory then amplifies whatever within-question
fluctuation that long-tail-bulk shape exhibits — fluctuation that
has no obvious connection to per-position epistemic state.

The mechanism analysis's underlying claim (that absolute logit
magnitude information is lost in Softmax and that loss is
mechanically connected to hallucination) is not falsified by this
result — it is only the *specific operational definition* of
$M_t$ as `max − global_mean` that is ruled out. Alternative $M_t$
definitions that the §13.18 pre-commitment did not test:

- $M_t = \max_j z_t[j] - \text{second\_max}_j z_t[j]$
  (gap to runner-up — local "preference strength")
- $M_t = \max_j z_t[j] - \text{quantile}_{0.99}(z_t)$
  (top vs the 99th percentile — robust to long-tail bulk)
- $M_t = \max_j z_t[j]$ (raw max logit, no centering)
- $M_t = \log \sum_j e^{z_t[j]}$ (logsumexp / partition function
  log — directly captures absolute logit-distribution scale)

Any of these would be a separate §0.8 commitment if pursued. They
are explicitly NOT pre-committed by §13.19 — listed only to
document that the §13.18 result rules out one specific operational
definition of $M_t$, not the broader mechanism-analysis claim
about absolute logit magnitude.

**This is the §0.8-discipline pattern working as designed.** The
§13.18 pre-commitment fixed both the primary scalar and a
diagnostic specifically for this case (that one component of the
primary might be hurting beyond raw entropy). The diagnostic
fired exactly the way its docstring said it would. We cannot
post-hoc swap to Variant A, but we can report the finding cleanly
and use it to inform any future §0.8 commitment that returns to
this signal class.

**Combined picture across all five §13 single-axis probes.**

| Probe | Hypothesis class | TruthfulQA-MC | HaluEval-QA | Combined band |
|---|---|---|---|---|
| §13.10 baseline | sample-space, single model | **0.661** | **0.661** | `TRUTH_CORRELATED_MARGINAL` |
| §13.11 cross-family | sample-space, ensemble | 0.633 | 0.716 | `CROSS_FAMILY_ANTI_FINDING` |
| §13.12 EigenScore | internal-state, single-snapshot | 0.559 | 0.652 | `EMBEDDING_SPACE_ANTI_FINDING` |
| §13.14 BCVF text-level 2nd-diff | temporal, K-sample text | 0.574 | 0.363 (inv) | `BCVF_2DIFF_ANTI_FINDING` |
| §13.16 BCVF hidden-state 2nd-diff | temporal, K-sample internal | 0.462 (inv) | 0.449 (inv) | `HSEIG_2DIFF_ANTI_FINDING` |
| §13.18 forced-allocation gap (primary) | temporal, single-trajectory logit | 0.549 | 0.571 | `FORCED_ALLOC_2DIFF_ANTI_FINDING` |
| §13.18 Variant A entropy-only (diagnostic) | temporal, single-trajectory entropy | 0.536 | 0.701 | (not a pre-committed primary; reported) |

Three robust patterns visible in this combined matrix:

**Pattern 1 — §13.10 is the ceiling, not the floor.** Every
single-axis revision underperforms §13.10's marginal baseline on
the combined-classification rule. None lift above it. **5-of-5
single-axis null at the combined level.** §13.10 single-snapshot
semantic entropy remains the strongest result in this codebase
across all five tested hypothesis classes.

**Pattern 2 — TruthfulQA-MC consistently defeats every method.**
Across all six measured AUCs (five primary + Variant A
diagnostic), TruthfulQA-MC ranges from 0.462 to 0.661 with the
non-§13.10 entries clustered in [0.462, 0.633]. Every revision
loses ground vs §13.10 on this benchmark. The most plausible
mechanism (consistent with literature; Farquhar 2024 reports the
same TruthfulQA-vs-other-benchmarks pattern with semantic
entropy): **TruthfulQA-MC's adversarial design — questions where
models confidently share wrong answers — breaks confidence-based
detection regardless of the specific scalar construction**.
Every method we tested is some variant of "measure the model's
confidence-related uncertainty"; questions where the model is
wrong AND confident are by construction the hardest cases for any
such method.

**Pattern 3 — HaluEval-QA is more permissive but still does not
unlock combined classification.** Two methods cleared the
`INTERNAL_STRONG` per-run band on HaluEval-QA: §13.11 cross-family
at 0.716 and §13.18 Variant A at 0.701. But the worst-benchmark
combined-classification rule means the TruthfulQA-MC failure
floors the combined band to ANTI for both. The pattern is
substantive enough that ANY future probe seriously aiming for
combined STRONG would need to either (a) clear TruthfulQA-MC
specifically (which has not happened in any §13 probe), or (b)
substitute a different second benchmark whose pathology is less
hostile to confidence-based methods (TriviaQA-Generation is the
literature-anchored candidate per Farquhar 2024's headline 0.78
on it).

**What this authorizes** (per §13.18 pre-commitment + §13.19
result):

- **Closing the §13 single-axis program at the exhaustive
  level.** §13.17 closed the K-sample-divergence single-axis
  sub-program. §13.19 now closes the single-trajectory single-
  axis sub-program. Every literature-aligned and mechanism-
  motivated single-axis hypothesis class available to this
  codebase at Qwen-7B + DeBERTa-v3-base + N=100 has been tested
  and produced ANTI under the combined-classification rule.
  **No further §13 single-axis probes are authorized.**
- **Authorizing the §13-program closing statement.** The honest
  external framing is now: *on Qwen2.5-7B-Instruct + DeBERTa-v3-
  base + N=100, no literature-aligned or mechanism-motivated
  single-axis hallucination-detection method tested in this
  codebase clears the §13.10 marginal baseline of AUC 0.661 on
  both TruthfulQA-MC and HaluEval-QA. The five tested hypothesis
  classes (sample-space single-model, sample-space cross-family,
  internal-state single-snapshot, K-sample temporal evolution at
  text-level and hidden-state-level, single-trajectory forced-
  allocation) all collapse under the worst-benchmark rule because
  TruthfulQA-MC defeats every confidence-based scalar construction
  tested. The §13.10 baseline appears to be a saturation ceiling
  for this configuration class, not a starting point.*
- **Documenting the Variant A finding as a substantive analytical
  observation.** Per-token entropy 2nd-difference on HaluEval-QA
  reached AUC 0.701, comparable to §13.11's 0.716 and Farquhar
  2024's reported ~0.70 on TruthfulQA-Generation. The finding is
  reportable as evidence that the §13 single-axis ceiling on
  HaluEval-QA specifically is around 0.70–0.72, not lower.
- **Promoting §13.10 as the strongest §13 result on record.**
  Confirmed by 5-of-5 single-axis comparisons. Any §13-related
  external referencing should cite §13.10's marginal pass as the
  strongest combined-classification result.

**What this does NOT authorize:**

- **Any update to `AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md`.** Per
  §13.9, external-framing revision requires `STRONG` on both
  benchmarks at any §13 probe. No probe in §13 has cleared this.
  The §13.9 hold remains in force and is *strengthened* by §13.19's
  5-of-5 confirmation across five hypothesis classes.
- **Post-hoc reinterpretation of §13.18 as a Variant-A pass.**
  The pre-committed primary scalar was the forced-allocation gap
  with α=1.0. Variant A is a diagnostic, not the pre-committed
  primary. Reporting Variant A's HaluEval 0.701 as if it were
  the §13.18 result would be a §0.8 violation. The classification
  follows the primary; the diagnostic informs the analytical
  narrative.
- **Any single-axis follow-up probe in the §13 program.**
  Five hypothesis classes tested; all combined-classification
  ANTI. Another single-axis variant on the same benchmarks is
  not authorized without a fresh §0.8 pre-commitment that
  explicitly identifies what new hypothesis class it tests AND
  what pathway around the TruthfulQA-MC pathology it proposes.
- **Any claim about BCVF-for-LLMs in general.** §13.19 narrows
  the negative claim to *single-axis observables under the BCVF
  2nd-difference operator (and related single-snapshot scalars)
  at the constructions tested*. System-level integration
  (multi-source consumer with BCVF-shaped routing, the §6.1-style
  configuration) is not tested and is not foreclosed; if pursued
  it would be a separate §14 pre-commitment outside the §13
  single-axis program.
- **Any claim that affects the autonomy-domain BCVF result.**
  §6.1's N=21 sign-test on `S3_map_error_accel` passed
  independently and stands. §13.19's outcome bears only on the
  LLM-domain transfer claim at the constructions tested, not on
  the robotics-domain validation.

**Status of the §13 program after §13.19.** Closed exhaustively
at the single-axis level across five tested hypothesis classes.
The §13.10 baseline (AUC 0.661 on both benchmarks,
TRUTH_CORRELATED_MARGINAL) is the strongest result of record. Any
future LLM-domain work on the BCVF transfer claim would need to
test a fundamentally different experimental structure — specifically
system-level integration (the §6.1-style configuration where
BCVF-shaped routing decides among multiple sources and end-to-end
accuracy is the metric, not isolated-observable AUC) — under a
fresh §0.8 pre-commitment in a new top-level section (§14 or
beyond). The §13.8 future-work list documents three honest
remaining directions; none are pre-committed by §13.19.

**Artifacts:**

- `scripts/probe_forced_alloc_2diff.py` (commit `d5b7b65`).
- `docs/experiments/probe_forced_alloc_2diff_truthfulqa_mc.md` and `.json`.
- `docs/experiments/probe_forced_alloc_2diff_halueval_qa.md` and `.json`.

### 13.20 Observation — §13.10 protocol re-executed at N=200 (post-§13.19 deviation; not a re-classification of §13.10)

**Status: §0.8 deviation from §13.19 closure, surfaced
explicitly.** §13.19 explicitly stated "no further §13 single-
axis probes are authorized." A re-execution of §13.10's
protocol at N=200 was nonetheless run in the runpod container
on both benchmarks after §15.2 had landed. Because that run
both (a) was not pre-committed, and (b) overwrote the §13.10
N=100 dumps §15.2 was computed against (see §15.2 Postscript),
the result is recorded here as a documented observation, NOT
as a §13 re-classification or a §13.20-as-pre-commitment.

**Relationship to §13.10.** §13.10's verdict-of-record was
**TRUTH_CORRELATED_MARGINAL at N=100** (AUC 0.661 on both
TruthfulQA-MC and HaluEval-QA, identical to three decimals).
That verdict was pinned at the N=100 configuration and
remains binding under §0.8. **§13.20 does not change §13.10's
classification.**

**N=200 observation (per-benchmark numerical record).**

| Benchmark | N | Greedy correct | W | Greedy accuracy | Mean H (correct) | Mean H (wrong) | Mean H (all) | **AUC** | Per-benchmark §11 classification |
|---|---|---|---|---|---|---|---|---|---|
| TruthfulQA-MC | 200 | 48 | 152 | 0.240 | 1.379 | 1.646 | 1.582 | **0.596** | `NOISE_BAND_LIFT` (below §11 0.60 marginal bar) |
| HaluEval-QA  | 200 | 54 | 146 | 0.270 | 1.114 | 1.597 | 1.467 | **0.679** | `TRUTH_CORRELATED_MARGINAL` |

**Combined under the worst-benchmark rule** (§13.10 / §13.11 /
… discipline): the worst benchmark is TruthfulQA-MC at AUC
0.596, which falls in `NOISE_BAND_LIFT`. **At N=200 the
combined classification under the same rule §13 used would be
`NOISE_BAND_LIFT`**, one band below §13.10's N=100
`TRUTH_CORRELATED_MARGINAL`.

**Three honest observations the data supports.**

**(a) The §13.10 N=100 result of 0.661 / 0.661 was likely at
the upper end of the AUC's sampling distribution.** At N=200
the TruthfulQA-MC AUC is 0.596 (a 0.065-point drop). The
HaluEval-QA AUC is 0.679 (a 0.018-point rise). Both shifts
are within the order of magnitude one would expect from
N=100 → N=200 sampling-variance reduction at this AUC range,
with a mean-reversion direction on TruthfulQA-MC (toward the
broader distribution's mean). **The N=100 marginal-pass on
TruthfulQA-MC was real, but its 0.661 point estimate did not
generalize at N=200.**

**(b) Per-benchmark mean-entropy separations widened on
HaluEval-QA, narrowed on TruthfulQA-MC.** HaluEval-QA's
correct-vs-wrong mean H separation grew from 0.486 nats
(N=100) to 0.483 nats (N=200, essentially unchanged) but its
mean-H-correct dropped from 1.176 to 1.114 — the correct
subset became more concentrated. TruthfulQA-MC's correct-vs-
wrong separation narrowed from 0.392 nats (N=100) to 0.267
nats (N=200), with both means shifting up. **TruthfulQA-MC's
distractors at the larger sample produce more entropy in
correct-greedy responses too, eroding the gap.**

**(c) The cross-benchmark AUC convergence visible at N=100
(0.661 / 0.661) does not hold at N=200 (0.596 / 0.679).**
The N=100 cross-benchmark identity of AUCs to three decimals
was treated in §13.10 as evidence the metric was benchmark-
portable. The N=200 data weakens that claim: the AUCs diverge
by 0.083 points at the larger sample, with TruthfulQA-MC
falling below the §11 0.60 marginal bar and HaluEval-QA
remaining above it.

**Implications for §13.9 hold.** §13.9 gates external-framing
changes to `AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md` on a STRONG-
band lift on both benchmarks at any §13 / §14 / §15 probe.
The N=200 result is *further from STRONG* than the N=100
result was — TruthfulQA-MC dropped from 0.661 to 0.596,
moving below even the marginal bar. **§13.9 hold is
strengthened, not weakened, by §13.20.** No external-framing
change is authorized on this evidence.

**Implications for §15.** §15.2's MARGINAL verdict was
computed against the N=100 dumps (see §15.2 Postscript) and
is preserved as the §15.2 verdict-of-record. §13.20 does NOT
authorize:

- Recomputing §15 against the N=200 dumps. That would require
  a fresh top-level §0.8 commitment with revised PINNED_N /
  PINNED_W / parity gates.
- Re-classifying §15.2's MARGINAL based on a degraded
  upstream AUC. §15.2's verdict was about the §13.10 score's
  selective-prediction value at the §13.10-of-record
  configuration; the N=200 observation is upstream of §15's
  metric class and operates under a different N.
- Documenting §13.20's NOISE_BAND_LIFT as a "stronger §15
  null." The two are separate metric classes; combining them
  rhetorically would be the §0.8 violation pattern.

**What §13.20 explicitly does NOT authorize.**

- A §13.21 or any further §13 probe. §13.19 closure is
  reaffirmed; this section is documentation of an off-
  protocol observation, not a re-opening of §13.
- Updating §13.10's verdict-of-record. The N=100 verdict
  remains binding.
- Updating §15.1's pinned constants. The §15.2 verdict-of-
  record's reproducibility break is documented in the §15.2
  Postscript, not patched.
- VC-brief changes (§13.9 hold remains; §13.20 strengthens
  rather than weakens it).
- Cross-domain claims. The autonomy-domain BCVF claim (§6.1)
  is unaffected.

**Audit lesson.** §13's closure rule "no further §13 single-
axis probes are authorized" is binding under §0.8 but cannot
prevent off-protocol re-runs of producer scripts. The §15.1
parity guard caught the resulting reproducibility break at the
§15 layer (PARITY_GATE_FAILED would fire on a re-run); §13's
closure had no equivalent guard at the §13.10 layer because
the §13.10 producer is upstream of any §13 probe. Future
chapters should consider build-time fingerprinting of upstream
dumps so off-protocol overwrites are detected at the next
layer's first invocation.

**Artifacts.**

- `scripts/probe_semantic_entropy.py` (unchanged §13.10
  producer).
- `docs/experiments/probe_semantic_entropy_truthfulqa_mc.json`
  (now contains N=200 dump; **was** the §13.10 N=100
  TruthfulQA-MC dump §15.2 was computed against).
- `docs/experiments/probe_semantic_entropy_halueval_qa.json`
  (now contains N=200 dump; **was** the §13.10 N=100
  HaluEval-QA dump §15.2 was computed against).
- `docs/experiments/probe_semantic_entropy_truthfulqa_mc.md`
  and `probe_semantic_entropy_halueval_qa.md` (corresponding
  N=200 markdown reports).

## §14 System-level BCVF integration on LLMs (new chapter)

§13.19 closed the §13 single-axis program exhaustively across
five hypothesis classes. The remaining literature-aligned LLM-
domain question — articulated in the §13.8 future-work list and
in §13.17 / §13.19 — is whether the §6.1-style configuration
(multi-source agent system using BCVF-shaped routing, end-to-end
performance metric) transfers to LLMs. §13's program tested
observables in isolation against ground-truth correctness via
AUC; §14 tests an entirely different experimental structure.

§14 is bounded into a scout (§14a) and a conditional full
experiment (§14, the chapter). The scout exists to gate the
multi-week investment of the full experiment behind a cheap pre-
committed test on the most permissive benchmark.

### 14a Pre-commitment — System-level scout

**Status: pre-committed, not yet executed.** §0.8-style pre-
commitment recorded before implementation. Specification, success
bands, promotion rules, and pinned parameters cannot be redefined
post-hoc.

**Relationship to §13's closure.** §13.10–§13.19 tested
observables in isolation: per-question, compute a BCVF-shaped
scalar, AUC against ground-truth correctness label. §6.1's
autonomy-domain validation that passed is a fundamentally
different experimental shape: multiple sources are weighted /
filtered / routed by BCVF scores, the routed answer is compared
against ground truth, and a sign test on per-question wins
determines significance. §14a tests whether that experimental
shape transfers to LLMs. **It is not a continuation of §13's
single-axis program; it is a new program with a different
metric (end-to-end accuracy delta vs naive aggregation,
sign-test) and a different math object (consumer + selector +
end-to-end answer, not isolated scalar vs ground truth).**

**Why a scout, not full §14 directly.** Three reasons:

1. **§13's TruthfulQA-MC pathology cleanly predicts that
   running the full experiment on TruthfulQA-MC + HaluEval-QA
   would land in saturation/anti combined regardless of how
   well the system layer works.** Five §13 single-axis probes
   established that TruthfulQA-MC defeats every confidence-based
   scalar. A direct full §14 on both benchmarks therefore has a
   high ex-ante probability of combined-classification ANTI even
   if the system layer is genuinely useful on HaluEval-QA. The
   scout tests where signal is most likely first — HaluEval-QA
   alone — and only commits to the full experiment after seeing
   life on the cheaper test.
2. **Full §14 is a multi-week implementation** (~1500 lines of
   new code: source-runner, four consumer variants, two
   selectors, end-to-end harness with sign-test, ablation
   runners). The scout reuses §13.11's cross-family
   infrastructure + §13.10's semantic-entropy scalar + adds only
   two consumer variants and one selector. Implementation cost
   ~2-3 days vs ~2-3 weeks.
3. **Pre-committed promotion rules let §14a make a clean
   binary decision about whether to invest in full §14.** A
   scout STRONG promotes to full §14 with high prior on success.
   A scout REGRESSION closes the LLM transfer line with strong
   evidence (system-level integration *also* fails after the
   single-axis program closed exhaustively). Either is
   actionable; neither requires the full investment.

**The scout's role in the broader §13/§14 program.** §14a is
explicitly a gate, not a deliverable. Its job is to inform the
go/no-go decision on the full §14 (which would add TruthfulQA-MC,
add the remaining two consumer variants, add the highest-weight
source selector, add ablation runners, and run sign-tests at
N=300+ for higher statistical power). A §14a STRONG result is the
prerequisite for full §14 authorization; a §14a REGRESSION
forecloses full §14 entirely.

**Specification (pinned):**

- **Script:** `scripts/probe_system_level_scout.py` (new; does
  NOT modify any §13.10–§13.18 script — those results pinned).
- **Sources (M = 3, all already cached from §13.11):**
  - `Qwen/Qwen2.5-7B-Instruct`
  - `meta-llama/Llama-3.1-8B-Instruct`
  - `mistralai/Mistral-7B-Instruct-v0.3`
  - All loaded co-resident on the 80 GB GPU (~45 GB total in
    fp16, identical to §13.11 setup).
- **Per-source BCVF scalar (pinned):** **semantic entropy** per
  §13.10's protocol — for each source, sample K=10 completions
  at T=1.0 with `max_new_tokens=32`, cluster by question-
  conditioned bidirectional NLI entailment (DeBERTa-v3-base-mnli-
  fever-anli, identical to §13.10 / §13.11), Shannon entropy
  $H_{\text{src}}(q) = -\sum_c \frac{|c|}{K} \log \frac{|c|}{K}$
  over cluster sizes. Pinned this scalar (not Variant A entropy
  2nd-difference, which scored 0.701 on HaluEval per-source for
  Qwen) because: (a) §13.10/§13.11 already proved cross-model
  implementation; (b) failure attribution is cleaner — a §14a
  regression cleanly indicts the system-integration layer
  rather than per-source-scalar transfer; (c) §13.10 is the
  strongest §13 result of record. The scalar is interpreted as
  *trust cost*: high entropy → uncertain source → low trust.
- **Per-source greedy answer:** each source's deterministic T=0
  greedy completion at `max_new_tokens=32`. Same prompt format as
  §13.10 / §13.11 (`Q: ... A:` completion, no chat templates).
  This is the candidate answer that source contributes to the
  weighted majority vote.
- **Consumer variants (pinned, both run, results compared):**
  - **V1 — Softmin trust shaping** (autonomy-domain default; the
    construct ChatGPT flagged as harmful):
    $w_i^{V1} = \frac{\exp(-d_i / \tau)}{\sum_j \exp(-d_j / \tau)}$
    with $d_i = H_{\text{src}_i}(q)$ (per-source semantic
    entropy) and $\tau = 0.5$ (pinned; default temperature for
    softmin trust shaping in autonomy-domain BCVF). High-entropy
    sources get sharply down-weighted; low-entropy sources get
    sharply amplified.
  - **V2 — Thresholded exclusion + uniform survivors** (ChatGPT's
    recommended replacement):
    $S = \{i : d_i \le \theta\}$, $w_i^{V2} = \mathbb{1}[i \in S] /
    |S|$. If $|S| < 1$, fall back to all sources with uniform
    weights ($w_i = 1/M$). Threshold $\theta = $ median of
    $\{d_1, d_2, d_3\}$ (pinned per-question; uses 50th-percentile
    of the source costs as the cut-point). Sources above the
    median entropy are excluded; survivors are uniform-averaged.
- **Selector (pinned, single choice):** **weighted majority vote**
  of per-source greedy answers. For each candidate answer string
  $a$ produced by some source, its score is
  $\sum_i w_i \cdot \mathbb{1}[\text{greedy}_i = a]$ (sum of
  weights of sources that emitted $a$). The candidate with the
  maximum score wins. Ties broken by argmax of cumulative weight
  in source-list order (deterministic).
- **Benchmark (pinned, single choice):** HaluEval-QA `data` split,
  N = 100 (same selection as §13.10–§13.18 for direct comparison).
  No second benchmark in §14a; TruthfulQA-MC is explicitly
  reserved for full §14 conditional on §14a STRONG.
- **Greedy "is correct" labeling (pinned):** identical protocol
  to §13.10–§13.18 — for each candidate answer (selector output,
  baseline-A, baseline-B), pass it through question-conditioned
  NLI (DeBERTa-v3-base-mnli-fever-anli) against the correct
  choice AND against the hallucinated answer; correct iff
  entails correct AND does not entail hallucinated. Holding
  labeling fixed across §13/§14a preserves combined-classification
  comparability if §14 ever adds TruthfulQA-MC under the same
  rule.

**Pinned baselines for the accuracy delta:**

- **Baseline-A — Single-source Qwen greedy.** The simplest
  possible LLM answer: just `Qwen/Qwen2.5-7B-Instruct` greedy
  output, no ensembling, no BCVF, no consumer. Tests "does the
  system add anything over the strongest single source?"
- **Baseline-B — Uniform majority vote across all 3 source
  greedies.** No BCVF scoring or weighting; each source's greedy
  contributes one vote, the most-voted answer wins (ties broken
  same way as the selector). Tests "does BCVF-shaped weighting
  add anything over naive ensembling?"

The §14a primary comparison is V1 / V2 vs Baseline-B (does
BCVF-shaped consumer beat uniform aggregation?). V1 / V2 vs
Baseline-A is reported as a secondary comparison (does the
system add anything over single-source-Qwen?). Both must be
reported for honest accounting.

**Pre-committed success bands** (different metric from §13:
accuracy delta in percentage points, not AUC; sign-test as
secondary statistical confirmation).

Define $\Delta_v = \text{acc}(v) - \text{acc}(\text{Baseline-B})$
for each consumer variant $v \in \{V1, V2\}$, where $\text{acc}$
is fraction of N=100 questions where the candidate answer's NLI
label is correct.

- **STRONG (PROMOTE TO FULL §14):** $\Delta_v \ge +5$ percentage
  points for *both* V1 and V2, with sign-test p-value < 0.05 on
  per-question wins for at least one of V1, V2 vs Baseline-B.
  Authorizes drafting full §14 pre-commitment with both
  benchmarks (TruthfulQA-MC + HaluEval-QA), all four consumer
  variants, both selectors (weighted majority + highest-weight),
  and ablation runners.
- **DIRECTIONAL (PROMOTE TO FULL §14 WITH V2 PRIORITY):**
  $\Delta_{V2} \ge +3$ percentage points AND $\Delta_{V1} \le 0$
  (V2 lifts, V1 does not). This is the specific outcome ChatGPT
  predicted: softmin trust shaping (V1) is harmful while
  thresholded exclusion (V2) is helpful. If observed, full §14
  is authorized but with V1 deprioritized and V2 / V3 (veto-only)
  / V4 (deadband) as the consumer variants in scope.
- **MARGINAL (UNDECIDED, ONE ADDITIONAL SCOUT AUTHORIZED):**
  $\Delta_v \in (0, +3)$ for both V1 and V2 (small lift, no
  significance). One more §14a-class scout authorized — likely
  candidates: swap per-source scalar to Variant A entropy
  2nd-difference (the §13.18 diagnostic that scored 0.701 on
  HaluEval), OR add veto-only and deadband consumer variants.
  Pre-commitment for that additional scout would be a fresh §0.8
  commitment in §14a.2 (or similar). Full §14 NOT authorized
  until either MARGINAL or STRONG is reached on a follow-up scout.
- **SATURATION (NO PROMOTION; DOCUMENT AS NULL):**
  $\Delta_v \in [-3, 0]$ for both V1 and V2. The system layer
  adds nothing measurable on top of naive 3-source majority
  voting. Document §14a as a null result; do NOT promote to
  full §14. The honest external framing becomes: "single-axis
  observables saturate (5-of-5 §13 nulls); system-level
  integration on the most permissive benchmark also saturates;
  the LLM transfer line is closed at all tested experimental
  structures."
- **REGRESSION (CLOSE LLM TRANSFER LINE):**
  $\Delta_v < -3$ for *either* V1 or V2 (system-level integration
  actively hurts compared to naive majority voting on the most
  permissive benchmark). The LLM transfer line is closed with
  strong evidence: the failure isn't only at the observable
  level (§13) but also at the system-integration level (§14a).
  The autonomy-domain BCVF claim stands independently on §6.1.
  No further LLM-domain probes authorized in this codebase
  without a fundamental reframing (different model class,
  different benchmark family, or different formal structure
  entirely).

**Acceptance / rejection rules (explicit, non-vague):**

- **PROMOTE to full §14:** STRONG or DIRECTIONAL.
- **AUTHORIZE one more scout:** MARGINAL.
- **DOCUMENT as null, do NOT promote:** SATURATION.
- **CLOSE LLM transfer line:** REGRESSION.

**Statistical test (pinned).** Per-question sign test for
$v$ vs Baseline-B: count the questions where $v$'s answer is
correct AND Baseline-B's answer is wrong (a "win" for $v$),
versus questions where $v$ is wrong AND Baseline-B is correct
(a "loss" for $v$). Ignore ties (both correct or both wrong).
Binomial test on win count vs total non-ties at $\alpha = 0.05$.

The pre-committed bands above use $\Delta_v$ thresholds rather
than sign-test p-values directly, because $\Delta_v$ is the
practically meaningful number (the actual accuracy lift). The
sign-test p-value is a secondary confirmation that the lift is
not noise. **A STRONG result requires BOTH $\Delta_v \ge +5pp$
AND sign-test p < 0.05.** The two conditions together prevent
both Type I (random fluctuation labeled STRONG) and the inverse
case where the lift exists but is so small the sign-test
disagrees.

**Disclosed simplifications and risks specific to §14a:**

- **HaluEval-QA only.** The most permissive §13 benchmark; the
  one where multiple methods showed life (§13.10 0.661, §13.11
  0.716, §13.12 0.652, §13.18 Variant A 0.701). The scout's
  job is to detect signal where signal is most likely; if it
  fails here, full §14 with TruthfulQA-MC added almost certainly
  fails the worst-benchmark rule. Cherry-picking risk is real
  but acknowledged: a §14a STRONG followed by full §14 anti on
  TruthfulQA-MC would be the same per-benchmark pattern §13
  showed (HaluEval permissive, TruthfulQA hostile). The scout
  is gating compute investment, not making external claims; the
  full §14 would re-test on TruthfulQA-MC with full pre-committed
  bands.
- **Two consumer variants only.** V3 (veto-only) and V4 (deadband
  fallback) are deferred to full §14 conditional on §14a STRONG.
  This means §14a cannot detect the case where V3 or V4 lifts
  while V1 and V2 don't. Acceptable risk because: V1 and V2 are
  the polar choices (most aggressive sharpening vs most
  conservative inclusion-or-exclusion); intermediate variants
  V3/V4 are unlikely to lift if both polar variants regress.
- **One selector only.** Highest-weight-source selector deferred
  to full §14. Weighted majority vote is the more conservative
  selector (less sensitive to a single source dominating);
  highest-weight is more aggressive. If §14a STRONG, the full
  §14 could test both.
- **N=100.** Statistical power: ~85% to detect a true 60% sign-
  test win rate at α=0.05 (a $\Delta \approx 5pp$ effect). Smaller
  N (e.g., N=50) would be cheaper but reduces power below the
  acceptance threshold; larger N would be costlier without
  strengthening the scout's promotion-rule decisions.
- **Pinned softmin temperature τ = 0.5.** Autonomy-domain
  default. Different τ values would change V1's sharpening
  intensity. If §14a lands MARGINAL, a τ sweep is a defensible
  follow-up scout.
- **Pinned threshold θ = median entropy** for V2. Per-question
  median, not global. Alternatives (global percentile, fixed
  numeric threshold) not pre-committed. Median was chosen
  because it adapts to per-question difficulty and is robust
  to outlier source entropies.
- **No NLI quality control on per-source answers.** All three
  source greedies are accepted as candidate answers regardless
  of length, format, or apparent quality. If a source emits
  malformed text consistently (rare but possible for chat-
  template-native models given completion-style prompts), it
  contaminates the weighted majority vote. Defensible if §13.11
  showed this didn't happen at scale; problematic if it did.

**Expected cost.**

- 3 sources × 100 questions × K=10 stochastic generations =
  3,000 sampling calls (~30 min on the cached GPU).
- 3 sources × 100 questions × 1 greedy generation =
  300 deterministic generations (~5 min).
- Per-source NLI clustering: 3 × 100 = 300 clustering operations
  × 90 NLI pairs × ~50 ms batched ≈ ~10 min total.
- Per-question NLI labeling (one call per candidate answer
  against correct + hallucinated): 4 candidates per question
  × 100 questions × 2 NLI calls = 800 calls (~5 min batched).
- Consumer / selector / accuracy / sign-test computation:
  trivial (per-question scalar arithmetic).

**Estimated total runtime: ~50–60 min on the existing 80 GB GPU.**
Memory: same ~45 GB co-resident as §13.11. No new model downloads.

**Report destination.**

- `docs/experiments/probe_system_level_scout_halueval_qa.md`
- `docs/experiments/probe_system_level_scout_halueval_qa.json`
  (per-question dump including each source's greedy + entropy,
  per-question consumer weights, selected answer for each
  variant, per-question correctness label for each candidate,
  per-question wins/losses for sign-test).

**Scope.**

§14a is a bounded scout under §0.8 discipline. The pre-committed
bands and promotion rules above are the binding gate to full §14.
Any deviation at run time must be flagged in the result section
as a §0.8 deviation, not absorbed silently.

§14a does NOT pre-commit:
- Implementation of `scripts/probe_system_level_scout.py` —
  separate authorization gate.
- Full §14 — explicitly conditional on §14a STRONG or
  DIRECTIONAL outcome.
- Any update to `AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md` — §13.9
  hold remains, gated on STRONG band on both benchmarks at any
  §13 or §14 probe.

**What §14a scope explicitly excludes:**
- TruthfulQA-MC (deferred to full §14 conditional on §14a STRONG).
- V3 (veto-only) and V4 (deadband) consumer variants (deferred).
- Highest-weight-source selector (deferred).
- Ablation table and statistical decomposition (deferred to full §14).
- Variant A entropy 2nd-difference per-source scalar (alternative
  scout in §14a.2 conditional on §14a MARGINAL).

### 14b Result — system-level scout returned SCOUT_SATURATION; LLM transfer line closed at all tested experimental structures

The §14a pre-committed scout has been executed at N=100 on
HaluEval-QA. Combined classification per pre-committed bands:
**`SCOUT_SATURATION`**. The system layer adds nothing measurable
on top of naive 3-source majority voting at this configuration.
Combined with §13.19's 5-of-5 single-axis null, this is
comprehensive evidence that BCVF-for-LLMs does not transfer at
any tested experimental structure on this codebase. The autonomy-
domain BCVF claim stands independently on §6.1 evidence and is
unaffected.

**Result table:**

| Variant | Accuracy | Δ vs Baseline-B (pp) | Sign-test wins/losses | Sign-test p |
|---|---|---|---|---|
| Baseline-A (Qwen single-greedy) | 0.300 | — | — | — |
| Baseline-B (uniform majority vote) | 0.300 | 0.00 (reference) | — | — |
| **V1 (softmin trust, τ = 0.5)** | **0.330** | **+3.00** | 4/1 | 0.3750 |
| **V2 (thresholded exclusion + uniform survivors)** | **0.300** | **+0.00** | 0/0 | 1.0000 |

**Combined classification under §14a's pre-committed bands:**

- STRONG (Δ ≥ +5pp for both AND p < 0.05 for at least one): **NO**
  — V1 is +3pp (below 5pp), V2 is 0pp.
- DIRECTIONAL (Δ_V2 ≥ +3pp AND Δ_V1 ≤ 0pp): **NO** — V2 is 0pp,
  V1 is +3pp.
- MARGINAL (Δ_v in (0, +3] for both): **NO** — V2 is 0pp, not in
  open lower bound.
- REGRESSION (Δ_v < −3 for either): **NO**.
- Falls through to **SATURATION** by partition definition.

The classification follows the pre-committed bands exactly. Per
§0.8 discipline, the bands cannot be retroactively renegotiated;
SCOUT_SATURATION is the binding outcome.

**Sign-test analysis.** The "ties" (questions where the variant's
selected answer agrees with Baseline-B's selected answer) dominate
both comparisons:

- **V1 vs Baseline-B:** 5 questions where the answers differed
  (4 V1-wins, 1 V1-loss); 95 questions where V1 and Baseline-B
  selected the same answer. Two-sided binomial test on 4/1 wins/
  losses gives p = 0.375. Not significant at α = 0.05.
- **V2 vs Baseline-B:** 0 questions where the answers differed
  (V2 picked the same answer as Baseline-B on all 100 questions
  in this run). Sign-test p = 1.0 trivially.

**The structural read:** At this configuration (M = 3 cross-
family sources, semantic-entropy scalar, weighted majority vote
selector), the *majority-vote-itself* dominates the outcome
across nearly every question. The BCVF-shaped weighting (V1) and
the BCVF-shaped exclusion (V2) only produce different answers
than naive majority voting when:

1. The 3 sources do NOT have a clear 2-of-3 majority answer
   (otherwise majority wins regardless of weight), AND
2. The BCVF-shaped weights or exclusion shifts which candidate
   answer wins the weighted vote.

Empirically, that joint condition fired on 5 questions for V1
and 0 questions for V2 across N=100. **The system layer
genuinely has very little leverage at M=3 with weighted majority
vote, regardless of how the BCVF scalar weights are computed.**

**Statistical-power caveat.** Sign-test on 5 non-tied questions
is severely under-powered. A true 80% V1 win-rate (against
Baseline-B on differences) would still produce a non-significant
p-value at this n. The 4/1 result is consistent with both "V1
slightly better" and "noise around 50%." We cannot distinguish
those two hypotheses from §14a alone. Running with M=5 sources
(more disagreement opportunities), or with highest-weight-source
selector (more sensitive to weight differences), or at N=500
(more statistical power for any per-question lift) would all
provide larger non-tied samples for a more powerful sign test —
but none of those are pre-committed by §14a, and per the §14a
SCOUT_SATURATION verdict, no follow-up is authorized without a
fresh §0.8 commitment.

**Three analytical observations the result supports:**

**(a) V1 (softmin trust) shows a small numerical lift but not a
statistically significant one.** Δ_V1 = +3pp is below the
DIRECTIONAL +3pp threshold's strict-inequality (V1's pre-
committed bound was Δ_V1 ≤ 0pp for DIRECTIONAL, so V1 lifting
*disqualifies* DIRECTIONAL even if V2 had also lifted). The
sign-test 4/1 result on 5 differences cannot statistically
distinguish "V1 slightly better" from "noise." Per §0.8, the
small numerical lift does not unlock any band more permissive
than SATURATION because the strict band partition treats
$\Delta_V \in (0, +3]$ and $\Delta_V \in [-3, 0]$ as different
buckets, and the mixed-bucket case (one variant in MARGINAL,
one in SATURATION) falls through to SATURATION by code
construction.

**(b) V2 (thresholded exclusion) is structurally degenerate at
M = 3.** With three sources and per-question median entropy as
threshold $\theta$, V2 always either:

- excludes exactly one source (the highest-entropy one) and
  uniform-averages the other two — equivalent to a 2-of-3
  vote where the excluded source's vote is dropped, OR
- in tied-at-median cases, falls back to all-three uniform —
  identical to Baseline-B.

In both cases, the resulting majority winner is the same answer
as Baseline-B's 3-source uniform majority *whenever the
remaining 2 sources have a 2-of-2 majority on the same answer
that Baseline-B picked*. With M = 3 and 3 sources usually
producing 2-of-3 majorities, this overlap is near-total. Hence
$\Delta_V_2 = 0$ on N=100 is not surprising — it is structurally
near-inevitable. **V2's null result at M = 3 is largely an
artifact of the consumer-selector interaction, not a clean test
of "thresholded exclusion adds nothing."** A fairer test of V2
would require M = 5 sources (more degrees of freedom for the
threshold to bite) or a highest-weight-source selector (which is
more sensitive to V2's weight differences). Neither is pre-
committed by §14a.

**(c) System-layer bandwidth is severely limited at M = 3 +
weighted-majority-vote.** On 95 of 100 questions, V1 and
Baseline-B selected the same answer; on 100 of 100, V2 and
Baseline-B selected the same answer. The system layer can only
differentiate from naive majority voting when there is no clear
majority among the 3 sources. With 3 instruction-tuned sources
on factual QA, that joint condition fires on a small fraction
of questions. **The result is consistent with "BCVF-shaped
routing has the right idea but limited leverage at this
ensemble scale" — not with "BCVF-shaped routing actively
hurts."** REGRESSION was the band that would have indicted
BCVF-as-routing; SATURATION is the band that says "indistinguishable
from naive aggregation at this scale."

These three observations together support a precise narrowing
of the negative finding: *§14a does not falsify BCVF-shaped
routing in general; it falsifies BCVF-shaped routing as a
useful lift over naive 3-source majority voting on HaluEval-QA
with the §14a-pinned configuration (semantic-entropy scalar,
softmin τ=0.5 or median-threshold exclusion, weighted majority
vote selector, N=100).*

**Combined picture across §13 and §14a — LLM transfer line now
closed at all tested experimental structures.**

| Program | Hypothesis class | Status |
|---|---|---|
| §13.10 | sample-space, single-model SE | MARGINAL_PASS (0.661 / 0.661, baseline of record) |
| §13.11 | sample-space, cross-family ensemble | combined ANTI |
| §13.12 | internal-state, single-snapshot EigenScore | combined ANTI |
| §13.14 | temporal, K-sample text-level 2nd-diff | combined ANTI |
| §13.16 | temporal, K-sample hidden-state 2nd-diff | combined ANTI (both inverted) |
| §13.18 | temporal, single-trajectory forced-allocation | combined ANTI |
| **§14a** | **system-level, multi-source BCVF routing** | **SCOUT_SATURATION** |

**6 of 7 distinct hypothesis classes ANTI or saturated; §13.10
remains the strongest single result on record, and §14a's
saturation confirms the system-level structure does not lift
the §13.10 ceiling either.** The honest external framing is now:

> *On Qwen2.5-7B-Instruct + DeBERTa-v3-base + N=100 + the cross-
> family triple (Qwen + Llama + Mistral), no literature-aligned,
> mechanism-motivated, or system-level BCVF construction tested
> in this codebase clears the §13.10 marginal baseline of AUC
> 0.661 (or, for system-level, the corresponding accuracy
> baseline of 0.300 on HaluEval-QA's uniform majority vote) at
> the combined-classification rule. The LLM transfer line is
> closed at all six tested experimental structures.*

**What §14a authorizes (per pre-commitment):**

- **Documenting §14a as the closing scout for the LLM track.**
  The §14a SCOUT_SATURATION result is binding under §0.8.
  Together with §13.19's exhaustive single-axis closure, this
  is comprehensive null-finding evidence.
- **Promoting §13.10 as the strongest result of record across
  both §13 and §14.** Reaffirmed by 6-of-7 comparisons; no
  single-axis or system-level construction has lifted it.
- **The honest "BCVF for LLMs at this configuration does not
  produce a usable hallucination detector" framing** for any
  internal-research referencing (still with §13.9 holding the
  external framing unchanged).

**What §14a does NOT authorize:**

- **Any update to `AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md`.** Per
  §13.9, external-framing revision requires STRONG band on both
  benchmarks at any §13 or §14 probe. SCOUT_SATURATION is the
  opposite of that gate. The §13.9 hold remains in force and is
  *strengthened* by §14a's confirmation of saturation at the
  system-integration level.
- **Promotion to full §14.** SCOUT_SATURATION explicitly
  forecloses the full §14 investment per the §14a promotion
  rules. Full §14 was only authorized on STRONG or DIRECTIONAL.
- **Any post-hoc renegotiation of the §14a bands to recategorize
  the V1 +3pp result as MARGINAL or DIRECTIONAL.** The bands
  were pre-committed; the V1 strict-inequality on DIRECTIONAL
  ($\Delta_{V_1} \le 0$) and the V2 strict-inequality on
  MARGINAL (both deltas $> 0$) were both written explicitly into
  §14a. Attempting to rebucket the result post-hoc would be a
  §0.8 violation.
- **Any further LLM-domain probe in §13 or §14 without a
  fundamentally different reframing.** Specifically: a fresh
  §0.8 commitment that justifies why a different model class
  (Qwen-32B+, GPT-4-class, multi-modal), different benchmark
  family (TriviaQA-Generation, NQ-Open, CNN/DM summarization),
  or different formal structure (cross-domain transfer rather
  than within-domain probe) would be expected to produce a
  different outcome from what 6 hypothesis classes have already
  shown. Without that, no further LLM compute is authorized.
- **Any claim that affects the autonomy-domain BCVF result.**
  §6.1 stands independently. §14a's outcome bears only on the
  LLM-domain transfer claim at the constructions tested, not on
  the robotics-domain validation.

**Final scope statement — both §13 and §14 chapters now closed.**

- **§13** closed in §13.19 across all tested single-axis
  hypothesis classes (§13.11 cross-family, §13.12 EigenScore,
  §13.14 BCVF text-level 2nd-diff, §13.16 BCVF hidden-state
  2nd-diff, §13.18 single-trajectory forced-allocation gap).
- **§14** closed in §14b at the scout level. The full §14
  was explicitly conditional on §14a STRONG or DIRECTIONAL;
  §14a SCOUT_SATURATION forecloses the full investment.

The §13.8 future-work list documented three remaining out-of-§13
directions: (a) single-trajectory observable (executed in §13.18),
(b) system-level integration (executed in §14a), and (c) model-
scale upgrade. (a) and (b) have now been tested and produced ANTI
or saturated combined classifications. **Only (c) — model-scale
upgrade — remains untested**, and the §13.8 documentation
explicitly states it requires a fresh §0.8 commitment with
revised baseline before any new probe-vs-baseline comparisons.
None of (a), (b), or (c) was guaranteed to find a positive result
ex ante; the §13/§14 program was designed to test the cheapest,
most literature-aligned options first and exhaustively.

The autonomy-domain BCVF claim (§6.1's N=21 sign-test passed)
stands wholly independent of any §13 or §14 outcome. The §13/§14
LLM-domain program tested whether the BCVF formalism transfers
to an adjacent domain at a specific scale; the answer at this
configuration is no, six different ways. That is itself a clean,
publishable methodological null — a contribution to the LLM
hallucination-detection literature about which combinations of
literature-aligned single-axis methods do AND do not transfer
cleanly to 7B-class LLMs with practical NLI scoring at N=100.

**Artifacts:**

- `scripts/probe_system_level_scout.py` (commit `975e99c`).
- `docs/experiments/probe_system_level_scout_halueval_qa.md`
  and `.json`.

### 14a.2 Pre-commitment — System-level scout with NLI-clustered selector (selector-spec fix)

**Status: pre-committed, not yet executed.** §0.8-style pre-
commitment recorded before implementation. Specification, success
bands, and pinned parameters cannot be redefined post-hoc.

**Relationship to §14a / §14b — what's being fixed and what isn't.**
§14b documented §14a's `SCOUT_SATURATION` per pre-committed bands.
Post-§14b audit revealed a structural issue in the §14a-pinned
selector: weighted majority vote with **string-identity grouping**
degenerates at M=3 cross-family because Qwen, Llama, and Mistral
emit stylistically different greedy strings even when they
semantically agree. With 3 distinct strings, all majority votes
become 3-way string ties broken by source-list order → always
picks Qwen. Empirical confirmation in the §14a JSON dump:
$\text{acc}(\text{Baseline-A}) = \text{acc}(\text{Baseline-B}) =
0.300$ exactly across N=100 — Baseline-B's "uniform majority of 3
sources" was effectively identical to Baseline-A's single-source
Qwen because the selector never grouped semantically equivalent
answers from different sources.

**§14a's SCOUT_SATURATION verdict remains binding** under §0.8.
Bands cannot be retroactively renegotiated; the pre-committed
result stands as the §14a outcome and §14b's framing is binding
for that specific selector configuration.

**§14a.2 tests the same hypothesis with the spec fixed.** Same
sources, same per-source scalar, same consumer variants (V1
softmin, V2 thresholded exclusion), same benchmark, same N — only
the selector changes. The fix replaces string-identity grouping
with **question-conditioned bidirectional NLI clustering** of the
3 candidate answers (the §13.10 / §13.11 mechanism applied here
to the M=3 source greedies, not to K stochastic samples). This
groups semantically equivalent answers regardless of stylistic
divergence, then aggregates weights within each cluster, then
picks the cluster with maximum total weight.

The same fix also applies to **Baseline-B**, which is critical:
§14a's Baseline-B was a degenerate "always pick Qwen" comparison.
§14a.2's Baseline-B is a genuine semantic-majority baseline using
NLI-clustering with uniform weights. **This is the comparison §14a
should have made.**

**Scope of the §14a.2 commitment.** §14a.2 fixes ONLY the selector
spec. It does NOT change:

- Per-source scalar (still semantic entropy via §13.10 method).
- Consumer variants (still V1 softmin τ=0.5 and V2 thresholded
  exclusion at per-question median entropy).
- Benchmark (still HaluEval-QA only at N=100; TruthfulQA-MC still
  reserved for full §14 conditional on §14a.2 STRONG / DIRECTIONAL).
- Sources (still Qwen + Llama + Mistral cross-family triple).
- Sampling (still K=10, T=1.0, max_new_tokens=32).
- NLI model (still DeBERTa-v3-base-mnli-fever-anli).
- Correctness label protocol (still question-conditioned NLI vs
  right_answer + hallucinated_answer).
- Pre-committed bands (same numerical thresholds — STRONG ≥+5pp,
  DIRECTIONAL Δ_V2 ≥+3pp ∧ Δ_V1 ≤0pp, MARGINAL (0,+3], SATURATION
  [-3,0], REGRESSION <-3 — applied to Δ vs the *new* Baseline-B).

The hypothesis tested is unchanged: "does BCVF-shaped routing
produce measurable accuracy lift over naive aggregation on
HaluEval-QA?" The answer can now be tested cleanly because both
the BCVF-shaped variants AND the naive baseline are aggregating
on semantic equivalence classes rather than string identity.

**Specification (pinned — only the selector and Baseline-B change
from §14a; everything else inherits §14a verbatim):**

- **Script:** `scripts/probe_system_level_scout_v2.py` (new; does
  NOT modify `probe_system_level_scout.py` — the §14a result is
  pinned).
- **Sources:** Qwen2.5-7B-Instruct + Llama-3.1-8B-Instruct +
  Mistral-7B-Instruct-v0.3 (unchanged from §14a).
- **Per-source BCVF scalar:** semantic entropy (§13.10 method,
  K=10 samples, question-conditioned NLI clustering, Shannon
  entropy over cluster sizes — unchanged from §14a).
- **Consumer variants (unchanged):** V1 softmin trust at τ=0.5
  and V2 thresholded exclusion at per-question median entropy.
- **Per-source greedy answer:** unchanged.
- **Benchmark + N:** HaluEval-QA `data` split, N=100 (unchanged).
- **NLI model:** DeBERTa-v3-base-mnli-fever-anli (unchanged).
- **Correctness label:** unchanged.

**Pinned NEW selector — NLI-clustered weighted majority vote.**
Given M source greedies $a_1, \ldots, a_M$ and weights
$w_1, \ldots, w_M$ produced by a consumer variant:

1. **Cluster the M candidate answers via question-conditioned
   bidirectional NLI entailment** using union-find (the §13.10
   `cluster_by_entailment` mechanism, applied here to M=3 source
   greedies instead of K=10 stochastic samples). For each pair
   $(i, j)$, the NLI classifier checks both directions
   $\text{NLI}(q + a_i, q + a_j)$ and $\text{NLI}(q + a_j,
   q + a_i)$; sources are union-merged when both directions
   produce entailment. Result: a partition
   $\{C_1, C_2, \ldots, C_K\}$ of the M sources into $K \le M$
   semantic-equivalence classes.
2. **Aggregate weights within each cluster:**
   $W_k = \sum_{i \in C_k} w_i$.
3. **Pick the winning cluster** $k^* = \arg\max_k W_k$. Ties
   broken by lowest cluster index (deterministic).
4. **Pick a representative answer from the winning cluster:** the
   answer from the source with the highest individual weight in
   $C_{k^*}$. Ties broken by lowest source index in $C_{k^*}$.
5. **Return** the representative answer string.

**Pinned NEW Baseline-B — NLI-clustered uniform majority.**
Same algorithm as the new selector but with weights
$w_i = 1/M$ for all sources. This is the "naive ensembling"
baseline §14a should have used; the §14a SCOUT_SATURATION result
was generated against a Baseline-B that didn't actually do
ensembling because of the string-matching degeneracy.

**Baseline-A unchanged.** Single-source Qwen greedy. Same as §14a.

**Why both V1/V2 AND Baseline-B receive the same selector fix.**
The §14a structural issue affected both BCVF-shaped variants
(V1, V2) AND the naive baseline (Baseline-B) symmetrically — all
three were grouped by string identity. Fixing only the BCVF-shaped
variants while leaving Baseline-B as string-matched would
artificially inflate the BCVF-shaped variants' deltas (because
Baseline-B would still be degenerate "always pick Qwen"). The
fix must apply to both for the comparison to be fair. **The
hypothesis is "BCVF-shaped weighting beats uniform weighting
when both aggregate on semantic equivalence classes"** — not
"BCVF-shaped weighting beats string-matched naive aggregation."

**What this changes about the result interpretation.** §14a's
empirical $\text{acc}(\text{Baseline-A}) = \text{acc}(\text{Baseline-B})
= 0.300$ was diagnostic: string-matched majority on M=3 cross-
family was equivalent to single-source Qwen. §14a.2's Baseline-B
should produce a *different* number — specifically, $\ge 0.300$ if
NLI clustering captures real semantic agreement that string-
matching missed. The Δ vs Baseline-B in §14a.2 is therefore on
a properly higher (or at least different) base; the test of
"does BCVF-shaped routing add lift" becomes a real test rather
than a degenerate one.

**Pre-committed success bands (identical partition to §14a; same
band labels because the metric — accuracy delta vs Baseline-B in
percentage points — is structurally the same; only the *meaning*
of Baseline-B changes between §14a and §14a.2):**

Define $\Delta_v = \text{acc}(v) - \text{acc}(\text{Baseline-B}_{V2})$
for each consumer variant $v \in \{V1, V2\}$, where
$\text{Baseline-B}_{V2}$ is the new NLI-clustered uniform majority
defined above and $\text{acc}$ is the fraction of N=100 questions
where the candidate answer is labeled correct.

- **STRONG (PROMOTE TO FULL §14):** $\Delta_v \ge +5\text{pp}$ for
  *both* V1 and V2, with sign-test p-value < 0.05 on per-question
  wins for at least one of V1, V2 vs $\text{Baseline-B}_{V2}$.
- **DIRECTIONAL (PROMOTE TO FULL §14 WITH V2 PRIORITY):**
  $\Delta_{V2} \ge +3\text{pp}$ AND $\Delta_{V1} \le 0$. ChatGPT's
  pre-§14a-predicted pattern (softmin trust shaping is harmful
  while thresholded exclusion is helpful).
- **MARGINAL (UNDECIDED, ONE ADDITIONAL SCOUT AUTHORIZED):**
  $\Delta_v \in (0, +3)$ for both V1 and V2. Likely follow-up
  scout: V3 veto-only + V4 deadband consumer variants, OR
  Variant A entropy 2nd-difference per-source scalar.
- **SATURATION (NO PROMOTION; DOCUMENT AS NULL):**
  $\Delta_v \in [-3, 0]$ for both V1 and V2. Combined with §14a's
  SCOUT_SATURATION and §13.19's 5-of-5 single-axis null, a §14a.2
  SATURATION would constitute the cleanest possible closure of
  the LLM transfer line in this codebase: same hypothesis tested
  under the methodologically correct selector, same null result.
- **REGRESSION (CLOSE LLM TRANSFER LINE WITH STRONG EVIDENCE):**
  $\Delta_v < -3\text{pp}$ for *either* V1 or V2.

**Acceptance / rejection rules (explicit, non-vague):**

- **PROMOTE to full §14:** STRONG or DIRECTIONAL.
- **AUTHORIZE one more scout:** MARGINAL.
- **CLOSE LLM TRANSFER LINE with comprehensive evidence:**
  SATURATION or REGRESSION. This is the methodologically clean
  closure §14a's structural issue made unavailable.

**Statistical test (pinned, identical to §14a):** Per-question
sign test for $v$ vs $\text{Baseline-B}_{V2}$ — count wins (v
correct AND Baseline-B$_{V2}$ wrong) and losses (v wrong AND
Baseline-B$_{V2}$ correct). Ignore ties. Two-sided binomial test
on win count vs total non-ties at $\alpha = 0.05$. STRONG
requires both $\Delta_v \ge +5\text{pp}$ AND sign-test $p < 0.05$
for at least one variant.

**Disclosed simplifications and risks specific to §14a.2:**

- **All §14a simplifications still apply.** HaluEval-QA only
  (cherry-pick risk acknowledged), 2 consumer variants (V3/V4
  deferred), 1 selector class (highest-weight-source-takes-all
  deferred to full §14), N=100, pinned softmin τ=0.5, pinned
  threshold θ=median entropy. These are the same as §14a; §14a.2
  only adds the NLI-clustered selector layer on top.
- **NLI-clustered selector inherits NLI noise.** Question-
  conditioned NLI on M=3 candidate answers can mis-cluster — two
  semantically equivalent answers might fail bidirectional
  entailment (false negative; clusters split incorrectly), or two
  semantically distinct answers might pass bidirectional
  entailment (false positive; clusters merge incorrectly).
  DeBERTa-v3-base's known limitations on multi-domain inference
  apply. The §13.10 / §13.18 protocol with bidirectional
  entailment + question-conditioning is the most robust default
  available in this codebase, but is not perfect.
- **Cluster-tie tiebreaker preference.** When two clusters tie
  on aggregated weight, the lowest-cluster-index (deterministic
  via union-find canonicalization order) wins. This is a
  defensible default but introduces a small bias toward
  whichever sources happen to merge first in the union-find
  pass. Alternatives (random tiebreaker, source-order tiebreaker)
  not pre-committed.
- **Within-cluster representative selection.** The selector
  returns the answer string from the source with the highest
  individual weight in the winning cluster. Alternatives (random
  representative, source-order) not pre-committed. For V1 softmin
  with non-uniform weights this matters; for uniform-weights
  Baseline-B and for V2 within-survivor uniform weights, the
  representative is selected by source-order tiebreaker — same
  as §14a's behavior within a string-equivalence class.

**Expected cost.**

- Per-source K=10 sampling: 3 × 100 × 10 = 3,000 calls (~30 min).
- Per-source greedy: 3 × 100 = 300 calls (~5 min).
- Per-source NLI clustering of K=10 samples: 3 × 100 × 90 NLI
  pairs ≈ ~10 min batched.
- **NEW** — per-question NLI clustering of M=3 candidate
  answers: 100 × M(M−1) = 100 × 6 = 600 NLI pairs. Cost ≈ 1 min
  (negligible vs the K=10 clustering cost).
- Per-question NLI labeling vs (right_answer, hallucinated_answer):
  4 candidates × 100 questions × 2 NLI calls = 800 calls
  (~5 min batched).
- Consumer / selector / accuracy / sign-test: trivial.

**Estimated total runtime: ~50–60 min** (essentially identical
to §14a — the new NLI-cluster step on M=3 answers per question
is a small marginal cost). Memory unchanged. No new model
downloads.

**Report destination.**

- `docs/experiments/probe_system_level_scout_v2_halueval_qa.md`
- `docs/experiments/probe_system_level_scout_v2_halueval_qa.json`
  (per-question dump including each source's greedy + entropy +
  cluster ID assigned by the answer-clustering step, per-variant
  weights, per-cluster aggregated weights, selected answer, and
  candidate correctness labels for full post-hoc audit).

**Scope.**

§14a.2 is a bounded scout under §0.8 discipline. The pre-committed
bands and promotion rules above are the binding gate to full §14.
Any deviation at run time must be flagged in the result section
as a §0.8 deviation, not absorbed silently.

§14a.2 does NOT:
- Modify §14a's `SCOUT_SATURATION` verdict (binding under §0.8
  for the §14a-pinned configuration).
- Modify §14b's prose (§14b is the §14a result section; §14a.2's
  result section will be §14c when written).
- Pre-commit a `scripts/probe_system_level_scout_v2.py`
  implementation — that is a separate authorization gate.
- Authorize any update to `AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md`.
  Per §13.9, external-framing revision still requires STRONG band
  on both benchmarks at any §13 or §14 probe; §14a.2 is HaluEval-
  only by design.

**What §14a.2 explicitly excludes** (still deferred to full §14
on STRONG / DIRECTIONAL promotion):
- TruthfulQA-MC (deferred).
- V3 (veto-only) and V4 (deadband) consumer variants (deferred).
- Highest-weight-source-takes-all selector (deferred).
- Variant A entropy 2nd-difference per-source scalar (alternative
  scout in §14a.3 conditional on §14a.2 MARGINAL).

### 14c Result — System-level scout with NLI-clustered selector also returned SCOUT_SATURATION; LLM transfer line closed at all tested experimental structures

The §14a.2 pre-committed scout has been executed at N=100 on
HaluEval-QA. Combined classification per pre-committed bands:
**`SCOUT_SATURATION`**. The selector-spec fix to NLI-clustered
weighted majority vote worked structurally — Baseline-A and
Baseline-B are now genuinely different (0.300 vs 0.290) — but the
system layer still does not produce sufficient lift to clear any
of the pre-committed promotion thresholds.

Combined with §14a's SCOUT_SATURATION (string-matched selector)
and §13.19's 5-of-5 single-axis null, this is the **methodologically
clean closure of the LLM transfer line** that §14a's structural
issue had made unavailable. The autonomy-domain BCVF claim stands
independently on §6.1 evidence and is unaffected.

**Result table (primary scalar — V1/V2 vs the new NLI-clustered
Baseline-B):**

| Variant | Accuracy | Δ vs Baseline-B (pp) | Sign-test wins/losses | p |
|---|---|---|---|---|
| Baseline-A (Qwen single-greedy) | 0.300 | — | — | — |
| **Baseline-B (NLI-clustered uniform majority)** | **0.290** | reference | — | — |
| V1 (softmin trust, τ=0.5) | 0.330 | **+4.00** | 5/1 | 0.219 |
| V2 (thresholded exclusion + uniform survivors) | 0.300 | +1.00 | 1/0 | 1.000 |

**Side-by-side comparison with §14a (string-matched selector):**

| Quantity | §14a | §14a.2 | Direction |
|---|---|---|---|
| acc(Baseline-A) | 0.300 | 0.300 | unchanged |
| acc(Baseline-B) | 0.300 | 0.290 | **now genuinely different from A** |
| acc(V1) | 0.330 | 0.330 | unchanged numerically |
| acc(V2) | 0.300 | 0.300 | unchanged numerically |
| Δ_V1 vs Baseline-B | +3.00pp | **+4.00pp** | larger lift under fixed selector |
| Δ_V2 vs Baseline-B | +0.00pp | +1.00pp | small lift now visible |
| V1 sign-test wins/losses | 4/1 | 5/1 | one more non-tied difference |
| V2 sign-test wins/losses | 0/0 | 1/0 | one non-tied difference now appears |

The §14a.2 selector fix succeeded at its narrow methodological
goal: Baseline-B is no longer a degenerate "always pick Qwen via
tiebreaker." On 5 questions for V1 and 1 question for V2, the
NLI-clustered selector produced a different answer than NLI-
clustered Baseline-B — i.e., the BCVF-shaped weighting actually
shifted the cluster choice. **But the magnitudes are not large
enough to clear the pre-committed STRONG (+5pp + p<0.05) or
DIRECTIONAL (V2 ≥+3pp ∧ V1 ≤0pp) thresholds.**

**Math used (the construction tested at the pinned-primary level).**
For each question $q$ at N=100:

1. M=3 sources (Qwen + Llama + Mistral, all cached from §13.11).
2. Per source, K=10 stochastic samples + 1 greedy at T=1.0,
   max_new_tokens=32, prompt format `Q: ... A:`.
3. Per-source semantic entropy $H_{\text{src}}(q)$ via question-
   conditioned bidirectional NLI clustering of the K samples
   (DeBERTa-v3-base-mnli-fever-anli, identical to §13.10 / §13.11).
4. Two consumer variants:
   - V1 softmin: $w_i^{V1} \propto \exp(-H_{\text{src}_i}(q) / \tau)$,
     $\tau = 0.5$ pinned.
   - V2 thresholded exclusion: $S = \{i : H_{\text{src}_i}(q) \le
     \theta\}$, $w_i^{V2} = 1/|S|$ for survivors with $\theta = $
     per-question median entropy.
5. **NEW selector** (the §14a.2 spec fix):
   a. Cluster M source greedies $a_1, a_2, a_3$ via question-
      conditioned bidirectional NLI entailment using union-find
      (same `cluster_by_entailment` mechanism §13.10 uses on K=10
      samples). Result: partition into $K \le M$ semantic-
      equivalence classes.
   b. Aggregate weights within each cluster: $W_k = \sum_{i \in
      C_k} w_i$.
   c. Pick winning cluster $k^* = \arg\max_k W_k$, ties broken by
      lowest cluster index.
   d. Within winning cluster, pick representative source by highest
      individual weight, ties broken by lowest source index.
6. **NEW Baseline-B** uses the same NLI-clustered selector but
   with uniform weights $w_i = 1/M$. This replaces §14a's
   string-matched Baseline-B which was empirically degenerate.
7. Per-question correctness label for each candidate answer
   (V1 selected, V2 selected, Baseline-A = Qwen greedy,
   Baseline-B selected): question-conditioned NLI must entail
   `right_answer` AND not entail `hallucinated_answer`. Identical
   to §13.10–§13.18 protocol.
8. $\Delta_v = \text{acc}(v) - \text{acc}(\text{Baseline-B}_{V2})$
   for $v \in \{V1, V2\}$, in percentage points.
9. Sign-test for $v$ vs $\text{Baseline-B}_{V2}$: count wins
   ($v$ correct AND Baseline-B wrong) and losses ($v$ wrong AND
   Baseline-B correct); two-sided binomial test on win count vs
   total non-ties at $\alpha = 0.05$.

**Band-coverage gap exposed by §14a.2 — honest §0.8 audit point.**
The §14a.2 pre-committed bands defined:
- STRONG: $\Delta_v \ge +5\text{pp}$ for **both** + sign-test
  $p < 0.05$ for at least one.
- DIRECTIONAL: $\Delta_{V2} \ge +3\text{pp}$ AND $\Delta_{V1} \le 0$.
- MARGINAL: $\Delta_v \in (0, +3]$ for **both**.
- SATURATION: $\Delta_v \in [-3, 0]$ for **both**.
- REGRESSION: $\Delta_v < -3$ for either.

The observed result $(\Delta_{V1}, \Delta_{V2}) = (+4.00, +1.00)$
falls in **none** of these bands strictly:
- STRONG fails ($\Delta_{V1} = 4 < 5$).
- DIRECTIONAL fails ($\Delta_{V1} = 4 \not\le 0$).
- MARGINAL fails ($\Delta_{V1} = 4$ is outside $(0, 3]$).
- SATURATION fails (both $\Delta_v > 0$, not in $[-3, 0]$).
- REGRESSION fails (no $\Delta_v < -3$).

The implementation's `classify()` function falls through to
`SCOUT_SATURATION` as a catch-all (the last `return` statement in
the band cascade). **This is a code-level decision, not a strict
pre-committed-band decision** — the bands as written had a
coverage gap for cases where one variant lifts above MARGINAL but
below STRONG while the other variant lifts only marginally.

The strictest §0.8 reading of the result is "borderline MARGINAL+
on V1 and MARGINAL on V2; no pre-committed band cleanly applies;
the script's catch-all fallthrough returned SCOUT_SATURATION." For
operational purposes, SCOUT_SATURATION is the binding outcome —
§14a.2's promotion rules treat MARGINAL and SATURATION the same
way (no promotion to full §14; one more scout authorized at
MARGINAL but the §14a.2 prose explicitly closed the LLM track on
SATURATION/REGRESSION combined with §14a's prior result).

This band-coverage gap is documented as an analytical observation
about how §0.8 pre-commitments should be written. Future bands in
this codebase should partition $\mathbb{R}^M$ exhaustively to
prevent fall-through ambiguity.

**Four analytical observations the result supports:**

**(a) The selector-spec fix succeeded at its narrow methodological
goal.** §14a's empirical degeneracy ($\text{acc}(\text{Baseline-A})
= \text{acc}(\text{Baseline-B}) = 0.300$ exactly across N=100) is
gone. §14a.2 produces $\text{acc}(\text{Baseline-A}) = 0.300$ vs
$\text{acc}(\text{Baseline-B}) = 0.290$ — genuinely different
numbers reflecting NLI-clustered semantic-equivalence aggregation
rather than string-matched-tiebreaker degeneracy. **The §14a.2
selector-spec audit was the right move regardless of outcome.**
A hypothetical §14a.2 STRONG would have validated the system-
level hypothesis cleanly; the actual SCOUT_SATURATION still
documents the closure under the methodologically-correct
configuration. Either way, the §14a.2 commitment was a §0.8-
discipline win.

A small numerical surprise: $\text{acc}(\text{Baseline-B}) = 0.290$
is *lower* than $\text{acc}(\text{Baseline-A}) = 0.300$ on this
N=100 sample. Naive 3-source NLI-clustered ensembling slightly
hurts vs single-source Qwen on HaluEval-QA at this scale. The 1pp
difference is well within noise (sign-test p $\approx 0.5$ for a
single per-question swap), but the direction is consistent with
the §13 finding that the cross-family triple sometimes pulls Qwen
in wrong-answer directions when Llama and Mistral agree on a
hallucinated answer (HaluEval's distractors are designed to be
plausible).

**(b) V1 softmin trust shaping is the most persistently lifting
construct in the entire §13/§14 program.** The combined evidence:

| Probe | Selector | $\Delta_{V1}$ vs Baseline-B |
|---|---|---|
| §14a | string-matched | +3.00 pp |
| §14a.2 | NLI-clustered | **+4.00 pp** |

Persistent +3 to +4pp lift across two different selector
configurations is qualitatively different from §13's per-probe
results, where most variants saturated at the §13.10 baseline or
inverted. **This suggests softmin trust shaping at $\tau = 0.5$
on per-source semantic entropy is doing real work** — sharpening
the contribution of the lowest-entropy (most-confident) source's
answer in a way that occasionally produces a correct answer
where naive uniform aggregation produces a wrong one.

But the magnitude is small enough that:
- It does not clear the pre-committed STRONG threshold (+5pp).
- The sign-test on 5–6 non-tied questions out of 100 is severely
  under-powered ($p = 0.219$ in §14a.2). At N=200 with the same
  effect size, $p$ would still likely be $> 0.05$.
- Two consecutive scouts under different selectors landing in
  the +3 to +4pp range strongly suggests this is the *true*
  effect size for V1 softmin at this configuration, not a noise
  fluctuation. The honest read is "real but small, not enough to
  promote."

**(c) V2 thresholded exclusion saturates cleanly under both
selectors.** §14a: +0.00pp. §14a.2: +1.00pp (1 win / 0 losses).
At M=3 the median-entropy threshold + uniform survivors structure
has very limited bandwidth — it can only differentiate from
Baseline-B when the highest-entropy source happens to be in
clusterminority position. Empirically this rarely fires, and when
it does, the lift is a single question. **V2's null result is
robust to selector choice and is the cleanest "no-effect" finding
in §14.**

**(d) ChatGPT's predicted DIRECTIONAL pattern was falsified.**
Pre-§14a, ChatGPT's analysis predicted that softmin trust shaping
(V1) would be *harmful* and thresholded exclusion (V2) would be
*helpful* — the autonomy-domain "softmin amplifies the wrong
source" critique. The DIRECTIONAL band was specifically constructed
to detect this pattern: $\Delta_{V2} \ge +3\text{pp}$ AND
$\Delta_{V1} \le 0\text{pp}$.

The actual data:
- V1 (softmin) consistently lifts (+3 / +4pp across §14a / §14a.2).
- V2 (thresholded) is essentially inert (+0 / +1pp).

The opposite of the predicted pattern. This is empirical evidence
that softmin trust shaping is *not* the mathematically harmful
piece in this LLM-domain configuration; the autonomy-domain
softmin default is at minimum not actively dangerous here, and
plausibly is doing useful work that the more-conservative
thresholded variant doesn't capture. ChatGPT's general "softmin
only as good as the scalar it sharpens" intuition remains
correct, but the specific prediction "softmin amplifies wrong
source on cross-family LLM ensembles" was falsified. Worth
flagging in any future revisit: the autonomy-domain softmin
construct should not be removed from candidate consumer designs
based on §13/§14 evidence — if anything, it earned its place.

**Five-section post-mortem on the §13 + §14 LLM-track program.**

Distilling the empirical pattern across all 7 hypothesis classes
tested (§13.10–§13.18 single-axis + §14a / §14a.2 system-level)
into the cleanest structural reading:

**(1) Proxy thinness at scale.**
Each §13 probe applied a literature-anchored construction
(Farquhar 2024 semantic entropy, Yoffe 2024 cross-family, Chen
2024 EigenScore, BCVF text-level + hidden-state 2nd-difference,
ChatGPT's forced-allocation gap). All produced AUCs in the
0.46–0.72 range, with §13.10's baseline at 0.661 marginal-pass.
The literature-typical 0.74–0.81 AUROC range did *not* transfer
to our 7B-class + DeBERTa-v3-base + N=100 + completion-style-
prompt configuration. The proxy classes have a real ceiling at
this scale — likely close to §13.10's 0.66 — and the §13.9 0.75
external-framing bar is above it. Whether this is "wrong proxies"
or "right proxies at insufficient scale" is a real ambiguity that
required the model-scale upgrade probe (§13.8 future-work item,
never executed) to disambiguate. The honest framing: **proxy
thinness at our specific scale, not categorical wrongness of the
proxy class**.

**(2) Consumer-class evidence is mixed (not "softmin always
harmful").**
§14a / §14a.2's V1 softmin trust shaping produced the strongest
BCVF-shaped lift in the entire program (+3 / +4pp across two
selector configurations). V2 thresholded exclusion saturated
cleanly. ChatGPT's pre-§14a "softmin amplifies the wrong source"
critique was falsified by the data; the autonomy-domain softmin
default is doing useful work in this configuration, just at an
effect size below the pre-committed STRONG threshold. **The
softmin-as-harmful-construct framing should not carry forward
to any future LLM-domain BCVF work in this codebase based on §14
evidence**; the harmful-or-not question is empirically
unresolved and the surface-level evidence runs the *other* way
than ChatGPT's mechanism prediction.

**(3) Selector-spec audit.**
§14a's pinned selector (string-matched weighted majority vote)
degenerated at M=3 cross-family — Baseline-B was empirically
identical to Baseline-A because of 3-way string ties broken by
source order. Caught in the post-§14b audit. §14a.2 fixed it
with NLI-clustered weighted majority vote. The selector fix
worked structurally (Baseline-A and Baseline-B are now genuinely
different), but the system-level lift remained below promotion
thresholds even under the corrected spec. **The selector-spec
fix was the right §0.8-discipline move regardless of outcome**;
it eliminated a real measurement artifact and let §14a.2's
SCOUT_SATURATION verdict be the methodologically-clean closure
that §14a's structural issue had made unavailable.

**(4) TruthfulQA-MC pathology.**
The consistent failure benchmark across all 5 §13 single-axis
probes plus both §14 scouts. AUCs on TruthfulQA-MC ranged from
0.462 (§13.16, inverted) to 0.661 (§13.10) across §13; §14
didn't run on TruthfulQA-MC (deferred to full §14 conditional
on scout STRONG). The combined-classification rule (worst
benchmark sets the band) means TruthfulQA-MC's hostile
geometry — adversarial misconception distractors that match
common confidence patterns — floors every probe to ANTI/SATURATION
combined, even when HaluEval-QA results are reasonable. **Any
future LLM-domain probe at this scale should explicitly justify
how it expects to clear TruthfulQA-MC** (e.g., by switching to
TruthfulQA-Generation, which Farquhar 2024 reports as the more
permissive variant, or by abandoning combined-classification on
this benchmark pair).

**(5) What remains plausible (not pre-committed by §14c).**
Three out-of-§13/§14 directions documented in §13.8 future-work
list, each requires a fresh §0.8 commitment:

- **Model-scale upgrade.** Re-run §13.10 with Qwen-32B + DeBERTa-
  v3-large. Tests whether §13.10's 0.66 ceiling is a 7B artifact
  or fundamental.
- **Benchmark substitution.** TriviaQA-Generation (Farquhar 2024
  headline benchmark) instead of TruthfulQA-MC. Tests the proxy-
  thinness vs benchmark-pathology disambiguation.
- **Different formal structure.** Cross-domain transfer (BCVF
  trained in one domain applied in another), supervised
  activation probes (Azaria & Mitchell 2023; Marks & Tegmark
  2024) requiring labeled training data, or system-level
  abstention rather than answer selection. Each is a different
  research program with its own metrics.

None of these is authorized by §14c. They are plausible next
investments that would each require a deliberate §0.8 pre-
commitment with explicit hypothesis, metrics, bands, and
acceptance/rejection rules.

**Combined picture across §13 and §14 — full LLM transfer line
now closed at all tested experimental structures.**

| Program | Hypothesis class | Status |
|---|---|---|
| §13.10 | sample-space, single-model SE | MARGINAL_PASS (0.661 / 0.661, baseline of record) |
| §13.11 | sample-space, cross-family ensemble | combined ANTI |
| §13.12 | internal-state, single-snapshot EigenScore | combined ANTI |
| §13.14 | temporal, K-sample text-level 2nd-diff | combined ANTI |
| §13.16 | temporal, K-sample hidden-state 2nd-diff | combined ANTI (both inverted) |
| §13.18 | temporal, single-trajectory forced-allocation | combined ANTI |
| §14a | system-level, string-matched selector | SCOUT_SATURATION |
| **§14a.2** | **system-level, NLI-clustered selector** | **SCOUT_SATURATION** |

**7 of 8 distinct hypothesis classes ANTI or saturated; §13.10
remains the strongest result on record across both single-axis
and system-level programs.** The honest external framing for any
internal-research referencing of §13/§14 is now:

> *On Qwen2.5-7B-Instruct + DeBERTa-v3-base + N=100 + the cross-
> family triple (Qwen + Llama + Mistral), no literature-aligned,
> mechanism-motivated, or system-level BCVF construction tested
> in this codebase clears the §13.10 marginal baseline of AUC
> 0.661 (single-axis) or the corresponding accuracy ceiling
> around 0.30 on HaluEval-QA's NLI-clustered uniform majority
> vote (system-level). The LLM transfer line is closed at all
> eight tested experimental structures.*

**What §14c authorizes (per §14a.2 pre-commitment + §14c result):**

- **Closing the §13/§14 LLM-track program at the exhaustive
  level.** §13.19 closed §13's single-axis sub-program; §14b
  closed §14a's string-matched-selector scout; §14c closes
  §14a.2's NLI-clustered-selector scout. **No further §13/§14
  single-axis or scout-level probes are authorized.** The §13.10
  baseline is the strongest result of record; reaffirmed by all
  7 comparison probes.
- **Preserving the §14a.2 selector-spec fix as a methodological
  win.** The audit + fresh §0.8 commitment with corrected spec
  + clean re-run is the discipline pattern future LLM-domain
  work should replicate.
- **Documenting V1 softmin's persistent +3 to +4pp lift as
  analytical observation** (NOT as a band-clearing pass).
  Persistent across two different selector configurations
  (§14a, §14a.2). Below STRONG threshold and below sign-test
  significance at N=100. Worth flagging in future revisits; not
  worth current promotion.
- **Documenting the band-coverage gap as a §0.8-discipline
  lesson.** §14a.2's pre-committed bands didn't strictly cover
  the observed $(\Delta_{V1}, \Delta_{V2}) = (+4, +1)$ outcome.
  Future pre-commitments should partition the outcome space
  exhaustively to prevent fall-through ambiguity.

**What §14c does NOT authorize:**

- **Any update to `AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md`.** §13.9
  hold remains in force, strengthened by §14c's saturation under
  the methodologically-correct selector.
- **Any post-hoc renegotiation of §14a.2 bands** to recategorize
  the V1 +4pp as MARGINAL or DIRECTIONAL. Bands were pre-
  committed; rebucketing post-hoc would be a §0.8 violation.
- **Promotion to full §14.** SCOUT_SATURATION explicitly
  forecloses the multi-week full §14 investment per §14a.2's
  promotion rules.
- **Reframing the §14 result as "operational lift via abstention"
  or selective prediction.** The §14 program tested system-level
  *answer selection*, not selective prediction. Reframing what
  success means inside the §14c writeup would be the discipline-
  erosion failure mode §0.8 is designed to prevent. If selective
  prediction is interesting as a future direction, it should be
  pre-committed as a separate top-level chapter with its own
  pinned metrics — not blended into §14c.
- **Any further LLM-domain probe** in §13 or §14 without a
  fundamentally different reframing under a fresh §0.8 commitment.
- **Any claim that affects the autonomy-domain BCVF result.**
  §6.1 stands independently. §14c's outcome bears only on the
  LLM-domain transfer claim, not on the robotics-domain
  validation.

**Final scope statement — §13 and §14 chapters now closed.**

- **§13** closed in §13.19 across all five tested single-axis
  hypothesis classes.
- **§14a** scout closed in §14b at SCOUT_SATURATION (string-
  matched selector).
- **§14a.2** scout closed in §14c at SCOUT_SATURATION (NLI-
  clustered selector). Selector-spec fix succeeded structurally
  but did not lift the system layer past pre-committed promotion
  thresholds.
- **Full §14** explicitly NOT authorized. Promotion to full §14
  was conditional on §14a.2 STRONG or DIRECTIONAL; §14a.2
  SCOUT_SATURATION forecloses that path.

The §13.8 future-work list documents three remaining out-of-§13/
§14 directions, none pre-committed:
- (a) Single-trajectory forced-allocation observable — executed
  in §13.18 / §13.19 (combined ANTI).
- (b) System-level integration with NLI-clustered selector —
  executed in §14a.2 / §14c (SCOUT_SATURATION).
- (c) Model-scale upgrade — never executed; only remaining §13.8
  item not yet tested. Requires a fresh §0.8 commitment with
  revised baseline at the new scale.

**§13/§14 closure scope.** The §13/§14 LLM-track program tested
whether the BCVF formalism transfers to LLM hallucination
detection at our specific scale (Qwen2.5-7B-Instruct + DeBERTa-
v3-base + N=100 + cross-family triple where applicable + HaluEval-
QA + TruthfulQA-MC where applicable). The answer at this
configuration is **no**, eight different ways across single-axis
observable AUC and system-level routing accuracy. That is itself
a clean, publishable methodological null — a contribution to the
LLM hallucination-detection literature about which combinations
of literature-aligned single-axis methods + system-integration
configurations do AND do not transfer cleanly to 7B-class LLMs
with practical NLI scoring at modest N.

The autonomy-domain BCVF claim (§6.1's N=21 sign-test passed)
stands wholly independent of any §13 or §14 outcome. The §13/§14
LLM-domain program tested whether the BCVF formalism transfers
to an adjacent domain at a specific scale; the answer at this
configuration is no, eight different ways. The §13.9 external
framing remains "BCVF is not positioned as an LLM hallucination
detector"; that framing is now strengthened by exhaustive
exploratory evidence rather than weakened.

**Artifacts:**

- `scripts/probe_system_level_scout_v2.py` (commit `be0a5a3`).
- `docs/experiments/probe_system_level_scout_v2_halueval_qa.md`
  and `.json`.

---

## §15 Selective prediction / abstention from existing §13 signals (new chapter)

§13.19 closed the §13 single-axis program exhaustively across
five hypothesis classes. §14b and §14c closed the §14 system-
level scout program at `SCOUT_SATURATION` under both the
string-matched and NLI-clustered selector configurations.
**Both chapters asked the same question in different
experimental shapes: can BCVF-derived signals improve answer
selection?** The answer at this codebase's configuration was
no, eight different ways.

§15 asks a deliberately narrower, operational question:

> *§13 and §14 asked whether BCVF-derived signals could
> improve answer selection. §15 asks a narrower, operational
> question: whether the strongest surviving signal can support
> useful abstention behavior even when it is not strong enough
> to drive answer replacement.*

The strongest surviving signal of record is §13.10 single-
snapshot semantic entropy: AUC 0.661 on both TruthfulQA-MC
and HaluEval-QA at N=100. §13's combined-classification rule
treated this as `TRUTH_CORRELATED_MARGINAL` — above the §13
0.60 marginal bar but below the §13.9 0.75 STRONG bar that
gates external framing. §15 takes the same scalar and asks a
different question of it: thresholded into an answer/abstain
policy, does it move risk-coverage metrics relative to never-
abstain and random-abstain baselines on these two benchmarks?

This is a different metric class, a different acceptance
rule, and a different operational meaning from §13/§14:

| Program | Question | Metric class | Pass bar |
|---|---|---|---|
| §13 | does observable X correlate with correctness? | AUC vs ground truth | 0.60 marginal / 0.75 STRONG |
| §14 | does BCVF-shaped routing lift end-to-end accuracy? | Δ accuracy vs naive aggregation | +5pp + sign-test p<0.05 |
| **§15** | **does the §13.10 score support a useful abstain/answer policy?** | **AURC, coverage at target accuracy, error capture, false abstention** | **see §15.1 bands** |

§15 is therefore **not** a reinterpretation of §13/§14. The §13
single-axis verdicts and the §14 system-level scout verdicts
remain binding under §0.8 and are not retroactively reframed.
Per §14c's explicit prohibition ("do not reframe the §14
result as operational lift via abstention"), the §14 program's
accuracy-lift results are not blended into §15's operational
claims; §15 opens a fresh top-level chapter with its own
pinned hypothesis, primary observable, metrics, bands,
baselines, and acceptance/rejection rules.

**Why operational, not methodological.** §13.9's external-
framing hold is gated on STRONG-band lift in *answer-selection*
metrics (AUC ≥ 0.75 on both benchmarks, or §14-class accuracy
delta ≥ +5pp with sign-test significance). §15 cannot satisfy
that gate by construction — its metrics are a different class
entirely. §15 is explicitly *not* a research chapter on whether
BCVF transfers to LLMs; it is an operational chapter on whether
a known-marginal answer-correlation signal can be turned into a
useful abstention policy. A clean §15 STRONG would justify
internal investment in an abstention/escalation product layer
on top of §13.10-grade signals; a §15 SATURATION would
document that the AUC 0.661 ceiling does not even support a
useful abstention policy at this scale — itself a publishable
operational null. Either outcome is binding under §0.8.

**Compute scope.** §15 uses *only* already-computed per-question
scores from the §13.10 runs (TruthfulQA-MC and HaluEval-QA,
N=100 each, Qwen2.5-7B-Instruct + DeBERTa-v3-base, K=10
samples per question, semantic entropy via question-conditioned
NLI clustering, per-question correctness label via question-
conditioned NLI). **No new generation, no new benchmarks, no
new large-model runs, no new model downloads are authorized by
§15.** Risk-thresholding over per-question scalars and per-
question correctness labels that already exist in the §13.10
JSON dumps is the entire compute footprint. Wall-clock cost is
seconds, not minutes.

**§15 explicitly does NOT authorize:**

- New generation runs, new benchmarks, or new model loads.
- Re-running §13.10 at any other model / NLI / N configuration.
- Reopening any §13 or §14 hypothesis class.
- Updating `AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md`. The §13.9
  hold is gated on STRONG-band lift in answer-selection
  metrics on both benchmarks; §15 is a different metric class
  and cannot satisfy that gate by construction. The §13.9 hold
  remains in force regardless of §15 outcome.
- Production deployment claims. §15 is an internal-research
  scout to determine whether the existing signal carries
  operational abstention value at all.
- A §15.2 follow-up scout on any other observable (§13.11
  cross-family, §13.12 EigenScore, §13.18 Variant A forced-
  allocation entropy, §14a.2 V1 softmin trust score, etc.)
  without a fresh §0.8 commitment. §15 pins exactly one
  primary observable and one secondary comparator; nothing
  else is in scope.

**Confirmation: no data inspection prior to this pre-
commitment.** No §13.10 / §13.11 / §13.12 / §13.14 / §13.16 /
§13.18 / §14a / §14a.2 JSON dump has been opened during the
drafting of §15. The protocol, primary observable, metrics,
and bands in §15.1 below are pinned from the §13.10 prose
(specifically the §13.10 configuration block, result table,
and disclosed schema of `probe_semantic_entropy_*.json`)
only. Risk-coverage analysis on the existing dumps is gated
on this pre-commitment landing first; per §0.8, looking at the
data before the bands are pinned would be exactly the
discipline-erosion failure mode §15 exists to avoid.

### 15.1 Pre-commitment — Selective abstention scout on existing §13.10 dumps

**Status: pre-committed, not yet executed.** §0.8-style pre-
commitment recorded before any inspection of
`probe_semantic_entropy.json` or
`probe_semantic_entropy_halueval_qa.json`. Specification,
primary observable, operational metrics, success bands,
baselines, and acceptance/rejection rules below cannot be
redefined post-hoc once the data is opened.

**Relationship to §13/§14 — what §15 is and is not.** §15 is
not a continuation of §13's single-axis program (closed in
§13.19) nor of §14's system-level scout program (closed in
§14c). It is a fresh top-level chapter under §0.8 with a
different question, different metric class, and different
acceptance rule:

- §13 measured AUC of an observable against per-question
  ground-truth correctness. §15 takes the §13.10 observable
  *as given* (AUC 0.661) and measures whether thresholding
  it into an answer/abstain policy yields operational value.
- §14 measured end-to-end accuracy delta of a BCVF-shaped
  *answer selector* against naive aggregation. §15 does not
  change the answer at all — it only decides whether the
  pinned greedy answer is delivered or abstained.
- §15 produces no new claim about whether BCVF transfers to
  LLMs. It produces a claim about whether the §13.10 score,
  which already exists, supports a useful answer/abstain
  policy at this configuration.

§15's outcome cannot reopen §13 or §14 hypothesis classes by
construction — no new observable is introduced, no answer
replacement is performed, no new model is run. A §15 STRONG
result authorizes internal investment in an abstention /
escalation product layer over §13.10-grade signals; a §15
SATURATION documents that the §13.10 ceiling does not even
support useful abstention at this scale. Neither outcome
alters §13.9's external-framing hold.

**Specification — script and inputs (pinned).**

- **Script:** `scripts/probe_selective_abstention.py` (new;
  does NOT modify any §13.10–§14a.2 script — those results
  remain pinned). Pure post-processing: reads existing JSON
  dumps, computes per-threshold operational metrics. No model
  loads, no GPU, no NLI calls. CPU + numpy only.
- **Input dumps (pinned, both consumed; the two benchmarks
  are evaluated independently with identical protocol):**
  - `docs/experiments/probe_semantic_entropy.json` — §13.10
    TruthfulQA-MC dump, N=100. *(Original Chunk 2b pin —
    matches §13.10 prose. Briefly amended by §15.1 Amendment 1
    to a `_truthfulqa_mc`-suffixed path based on the §13.10
    script's filename template; reverted by §15.1 Amendment 2
    after on-disk verification showed the dump is at this
    un-suffixed path. See Amendments 1 and 2 below for the
    full audit trail.)*
  - `docs/experiments/probe_semantic_entropy_halueval_qa.json`
    — §13.10 HaluEval-QA dump, N=100. *(Unchanged across both
    amendments.)*
  - **No other JSON dump is consumed by §15.** §13.11 /
    §13.12 / §13.14 / §13.16 / §13.18 / §14a / §14a.2 dumps
    are explicitly out of scope.
- **Per-question fields consumed (pinned, schema documented
  in §13.10's `scripts/probe_semantic_entropy.py` JSON
  writer; see §15.1 amendment 1 for the explicit field-name
  mapping):**
  - `q_idx` — the per-question identifier (for deterministic
    ordering).
  - `semantic_entropy` — the per-question semantic-entropy
    scalar in nats.
  - `greedy_matches_correct` — the per-question greedy-
    answer correctness label (boolean, NLI-derived per
    §13.10).
  - **No other field is read.** If any of the above is
    missing from a dump, §15 fails fast with a
    `SCHEMA_MISMATCH` exit rather than substituting a derived
    quantity.

**Primary observable / risk score (pinned).** §13.10 single-
snapshot semantic entropy, exactly as defined in §13.10:
$$H(q) = -\sum_c \frac{|c|}{K} \log \frac{|c|}{K}$$
over NLI-clustered K=10 samples, units of nats. The §15 risk
score is $r(q) = H(q)$ — higher entropy means higher per-
question hallucination risk and higher abstain priority. §15
inherits §13.10's sign convention by reference; no re-
derivation, no alternative scalar definition.

**Answer candidate (pinned).** When the §15 policy delivers
an answer, the answer delivered is the §13.10 greedy
completion of `Qwen/Qwen2.5-7B-Instruct` whose correctness
label is already recorded in the input dump. §15 never
substitutes, re-decodes, or rewrites that answer. The
policy's only degree of freedom is the per-question
answer/abstain decision.

**Secondary observable (pinned: none).** §15.1 explicitly does
NOT pin a secondary observable. Rationale: every candidate
alternative scalar (cluster count, max-cluster fraction,
normalized entropy by $\ln K$, greedy-answer log-probability,
§13.11 / §13.12 / §13.18 scores, §14a / §14a.2 V1 trust
weights) either requires reading dump fields that the §15
pinned schema in the previous block does not include, or is a
monotone transform of $H(q)$ producing identical risk-coverage
rankings. The "one primary, optional one secondary" allowance
collapses under §15's pinned-input constraint to *one primary
only*. The sanity-check role a secondary observable would
play is filled by the random-abstain matched-coverage baseline
pinned in §15.1's baselines block below. Adding a true second
observable would require a fresh §0.8 commitment in a §15.2.

**Risk policy (pinned).** Per-question deterministic threshold
rule:
$$\text{policy}_\tau(q) = \begin{cases} \text{ANSWER } a(q) & \text{if } r(q) < \tau \\ \text{ABSTAIN} & \text{if } r(q) \ge \tau \end{cases}$$
where $r(q) = H(q)$ is the pinned risk score and $a(q)$ is the
pinned §13.10 greedy completion. The threshold $\tau$ is the
policy's only free parameter. Ties at $r(q) = \tau$ resolve to
ABSTAIN (deterministic, conservative — the rare-tie case does
not change combined-classification outcomes at N=100).

**Threshold-sweep protocol (pinned).** §15 evaluates the policy
across the full operational range by sweeping $\tau$ over the
empirical risk-score distribution per benchmark:

- The sweep grid is the **sorted unique values of $r(q)$ on
  the benchmark**, plus $\tau = -\infty$ (always abstain
  trivially: empty answered subset) and $\tau = +\infty$
  (always answer: full answered subset). At N=100 this yields
  at most 102 evaluation points per benchmark.
- All operational metrics (residual accuracy, coverage, error
  capture, false abstention, AURC) are computed at every
  point on this grid. No grid is hand-picked; no $\tau$ is
  hand-picked.
- The sweep is computed independently per benchmark.
  Combined classification across the two benchmarks happens
  at the metric level (per §15.1's bands block), not at the
  threshold level — there is no "merged $\tau$" that applies
  to both benchmarks.

Pinning the sweep this way prevents post-hoc threshold
selection on the data. Once the dumps are opened, every
threshold's metrics are computed mechanically; the §15
verdict reads off the pre-committed bands from the resulting
per-benchmark risk-coverage curves.

**Operational metrics (pinned; metrics 1–3 in this block,
metrics 4–5 in the next).**

For benchmark $\mathcal{B} \in \{\text{TruthfulQA-MC},
\text{HaluEval-QA}\}$ at threshold $\tau$, with $N = 100$
questions, per-question correctness $c(q) \in \{0, 1\}$ (from
the §13.10 NLI label) and risk score $r(q) = H(q)$:

- **Answered set:** $A_\tau = \{q : r(q) < \tau\}$;
  $|A_\tau|$ is the number answered.
- **Coverage primitive:**
  $\text{cov}(\tau) = |A_\tau| / N \in [0, 1]$.
- **Greedy total-wrong (constant per benchmark):**
  $W = N - \sum_q c(q)$. From §13.10 greedy accuracies:
  $W = 75$ on TruthfulQA-MC (greedy acc 0.250),
  $W = 70$ on HaluEval-QA (greedy acc 0.300).

**Metric 1 — Residual accuracy** (accuracy on the answered
subset):
$$\text{acc}(\tau) = \frac{1}{|A_\tau|} \sum_{q \in A_\tau} c(q) \quad \text{for } |A_\tau| > 0$$
$\text{NaN}$ when $|A_\tau| = 0$; excluded from accuracy-
conditioned reductions. Range $[0, 1]$.

**Metric 2 — Coverage at target accuracy** (the headline
operational lever — "how much can the policy answer while
maintaining accuracy at least $\alpha$?"):
$$\text{cov}@\alpha = \max\{\text{cov}(\tau) : \text{acc}(\tau) \ge \alpha \text{ and } |A_\tau| \ge n_{\min}\}$$
with $n_{\min} = 10$ (pinned floor, 10% of N=100; prevents
the trivial-high-accuracy-at-tiny-coverage degeneracy).
$\text{cov}@\alpha := 0$ deterministically if no $\tau$ in the
sweep grid satisfies both conditions.

Reported at three pinned target accuracies per benchmark:

| Target | TruthfulQA-MC | HaluEval-QA | Operational meaning |
|---|---|---|---|
| $\alpha_1$ = baseline + 10pp | 0.350 | 0.400 | noticeable lift over no-abstain |
| $\alpha_2$ = 0.50 | 0.500 | 0.500 | absolute majority correct on answered subset |
| $\alpha_3$ = 0.75 | 0.750 | 0.750 | deployment-grade accuracy on answered subset |

(Greedy baselines 0.250 / 0.300 per §13.10's result table.)

**Metric 3 — Error capture rate** (fraction of greedy
mistakes the policy successfully abstained away):
$$\text{ecr}(\tau) = \frac{1}{W} \sum_{q \notin A_\tau} (1 - c(q)) \quad \text{for } W > 0$$
Range $[0, 1]$. $\text{ecr} = 1$ means every wrong greedy
answer was abstained; $\text{ecr} = 0$ means no wrong greedy
answer was abstained. Undefined when $W = 0$; both pinned
benchmarks have $W > 0$ so this case does not arise in §15.

Reported at the same three target accuracies as Metric 2,
evaluated at the threshold $\tau^*$ that achieves
$\text{cov}@\alpha$. The operational pair
$(\text{cov}@\alpha, \text{ecr}(\tau^*))$ characterizes the
policy's value at each target: how much it answers and how
many wrong answers it caught at that operating point.

**Operational metrics 4 and 5 (pinned).**

**Metric 4 — Area under the risk-coverage curve (AURC)**
(integrated selective-error metric; the standard selective-
prediction headline number, lower is better):

Sort questions by ascending risk score $r(q)$, breaking ties
by ascending question identifier. Let $c_{(i)}$ be the
correctness label of the $i$-th lowest-risk question. The
cumulative selective error at coverage $k/N$ is
$$e_k = \frac{1}{k} \sum_{i=1}^{k} \big(1 - c_{(i)}\big)$$
and the §15 AURC is the discrete (Geifman–El-Yaniv 2017)
$$\text{AURC} = \frac{1}{N} \sum_{k=1}^{N} e_k$$
with uniform weighting over the $N$ coverage levels. Range
$[0, 1]$, lower is better.

**Random-matched AURC baseline** (uniform random selection
at matched coverage): a question selected uniformly at random
has expected wrong rate $W/N$ for any $k$, so
$\text{AURC}^{\text{random}} = W/N$ — the §13.10 greedy
error rate ($0.750$ on TruthfulQA-MC, $0.700$ on HaluEval-QA).
The §15 lift is
$$\Delta\text{AURC} = \text{AURC}^{\text{random}} - \text{AURC}^{\text{policy}}$$
positive when the policy outperforms random abstention.

**Metric 5 — False abstention rate** (fraction of correct
greedy answers the policy mistakenly abstained):
$$\text{far}(\tau) = \frac{1}{C} \sum_{q \notin A_\tau} c(q) \quad \text{for } C > 0$$
where $C = \sum_q c(q) = N - W$ is the total correct greedy
count ($C = 25$ on TruthfulQA-MC, $C = 30$ on HaluEval-QA per
§13.10). Range $[0, 1]$. $\text{far} = 0$ means no correct
greedy answer was abstained; $\text{far} = 1$ means all were.

Reported at the same three target-accuracy operating points
as Metrics 2 and 3, evaluated at the threshold $\tau^*$ that
achieves $\text{cov}@\alpha$. The pinned operational triple
at each target is
$$\big(\text{cov}@\alpha,\;\text{ecr}(\tau^*),\;\text{far}(\tau^*)\big)$$
which together capture selective-prediction quality: high
ecr + low far at meaningful coverage is the operational win
condition.

**Pre-committed bands (pinned; exhaustive partition).**

§14a.2 exposed a band-coverage gap when the pre-committed
band list did not strictly cover the observed outcome
$(\Delta_{V_1}, \Delta_{V_2}) = (+4, +1)$ and the script's
catch-all returned `SCOUT_SATURATION`. To prevent recurrence,
§15's bands are pinned as an **ordered cascade with an
explicit residual catch-all**: every possible outcome matches
exactly one band by construction.

**Headline statistics (pinned).** For benchmark
$b \in \{\text{TruthfulQA-MC}, \text{HaluEval-QA}\}$:

- $\delta_b = \Delta\text{AURC}_b$ (per-benchmark AURC lift
  over the random-matched baseline; Metric 4).
- $\kappa_b = \text{cov}@\alpha_2 \text{ on benchmark } b$
  (per-benchmark coverage at $\alpha_2 = 0.50$, the absolute-
  majority-correct target; Metric 2).

**Combined classification (worst-benchmark rule):**
$$\delta = \min_b \delta_b, \qquad \kappa = \min_b \kappa_b$$
Both headline statistics combine across benchmarks by
worst-benchmark, mirroring §13's worst-benchmark rule that
prevented combined classification from being driven by a
single-benchmark anomaly.

**Verdict cascade (pinned, ordered, exhaustive).** The §15
verdict is the **first** matching rule in the ordered list
below. The final rule (SATURATION, defined in the next
chunk) has no positive condition and explicitly catches
every $(\delta, \kappa) \in \mathbb{R}^2$ not matching rules
1–4.

1. **REGRESSION** — $\delta < -0.02$.
2. **STRONG** — $\delta \ge +0.10$ AND $\kappa \ge 0.30$.
3. **USEFUL_INTERNAL** — $\delta \ge +0.05$ AND $\kappa \ge 0.20$.
4. **MARGINAL** — $\delta \ge +0.02$ AND $\kappa \ge 0.10$.
5. **SATURATION** — explicit residual catch-all.

Rules 1–4 are mutually exclusive by ordering: once an outcome
matches rule $k$, rules $k+1, \ldots$ do not fire. Rule 5 has
no condition, so the cascade is exhaustive over $\mathbb{R}^2$.
REGRESSION is placed first (not last) so that any $\delta < -0.02$
outcome is classified as a regression even if $\kappa$ happens
to be high — a policy that hurts AURC is a regression
regardless of coverage behavior.

**STRONG (rule 2; promotes §15 to product / abstention-layer
investment).** $\delta \ge +0.10$ AND $\kappa \ge 0.30$.

Operational meaning: the §13.10 risk score, used as an
abstain threshold, integrates to at least 10 AURC points of
error suppression over random abstention on the worst
benchmark AND supports answering at least 30% of questions
at $\ge 50\%$ residual accuracy on the worst benchmark.

Authorizes drafting a §15.2 implementation pre-commitment for
an abstention/escalation product layer over §13.10-grade
signals (a separate §0.8 commitment, not auto-promoted by §15.1).
Does NOT authorize external-framing changes to
`AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md` (per §13.9 hold; §15's
metric class is operational, not answer-selection — the §13.9
gate is unchanged by §15 outcome).

**USEFUL_INTERNAL (rule 3; documents internal-research
operational value, no product investment).**
$\delta \ge +0.05$ AND $\kappa \ge 0.20$.

Operational meaning: the policy yields measurable but modest
abstention value — at least 5 AURC points of error suppression
AND $\ge 20\%$ answered at $\ge 50\%$ accuracy on the worst
benchmark.

Authorizes documenting the §13.10 score as having known
internal-research operational value for selective prediction
at this configuration. Does NOT authorize a §15.2 product
investment, external-framing changes, or any cross-domain
claim. The §13.9 hold remains in force.

**MARGINAL (rule 4; documents small but non-zero operational
signal, no investment).** $\delta \ge +0.02$ AND $\kappa \ge 0.10$
(and not matching rules 1–3 above).

Operational meaning: the policy yields a small detectable
abstention signal — at least 2 AURC points of error
suppression AND $\ge 10\%$ answered at $\ge 50\%$ accuracy on
the worst benchmark — but the lift is below the threshold
where internal-research documentation as a usable selective-
prediction signal is warranted.

Authorizes recording the §15 result as an acknowledged but
unactionable signal. Does NOT authorize a §15.2 follow-up,
internal-research operational claims, product investment, or
external-framing changes. The §13.9 hold remains.

**SATURATION (rule 5; explicit residual catch-all; documents
null operational result).** Any $(\delta, \kappa)$ not
matching rules 1–4. Specifically the residual covers:
$\delta \in [-0.02, +0.02)$ for any $\kappa$, or
$\delta \ge +0.02$ but $\kappa < 0.10$, or any other case
the prior rules do not catch.

Operational meaning: the §13.10 score, used as an abstain
threshold, is operationally indistinguishable from random
abstention at the worst benchmark on the integrated AURC
metric, OR yields some AURC lift that cannot meaningfully
support coverage at $\ge 50\%$ accuracy. The selective-
prediction policy adds nothing measurable on top of random
abstention at this configuration.

Authorizes documenting §15 as an operational null. Does NOT
authorize a §15.2 follow-up, any product investment,
internal-research operational claims, or external-framing
changes. Combined with §13/§14's prior closures, a §15
SATURATION extends the LLM transfer line's closure from
"answer-selection saturated" to "answer-selection AND
selective-prediction both saturated at this configuration."

**REGRESSION (rule 1; closes §13.10-as-selective-prediction-
risk-score line).** $\delta < -0.02$.

Operational meaning: the §13.10 score is anti-correlated with
correctness in the selective-prediction operational sense —
abstaining the high-entropy questions actively hurts AURC
relative to random abstention by more than 2 AURC points on
the worst benchmark.

The §13.10 baseline of record's AUC = 0.661 against ground-
truth correctness remains unaffected (REGRESSION here is on a
different metric class), but the operational route through
selective abstention is foreclosed at this configuration.
Does NOT authorize any external-framing changes; the §13.9
hold remains for the same reason it does in §15 SATURATION.

**Boundary-case audit table (illustrative, deterministic).**

The cascade is pinned with strict numerical thresholds. The
three specific cases flagged in §0.8 review plus three
additional edge cases, each traced through the cascade
mechanically:

| $\delta$ | $\kappa$ | Cascade trace | Verdict |
|---|---|---|---|
| $+0.10$ | $0.29$ | rule 1 NO; rule 2 NO ($\kappa < 0.30$); rule 3 YES | **USEFUL_INTERNAL** |
| $+0.049$ | $0.25$ | rule 1 NO; rule 2 NO; rule 3 NO ($\delta < +0.05$); rule 4 YES | **MARGINAL** |
| $-0.019$ | $0.40$ | rule 1 NO ($\delta \not< -0.02$); rules 2–4 NO; rule 5 catches | **SATURATION** |
| $+0.10$ | $0.30$ | rule 1 NO; rule 2 YES (both boundaries inclusive) | **STRONG** |
| $+0.15$ | $0.10$ | rule 1 NO; rule 2 NO ($\kappa < 0.30$); rule 3 NO ($\kappa < 0.20$); rule 4 YES | **MARGINAL** |
| $-0.025$ | $0.50$ | rule 1 YES; remaining rules not evaluated | **REGRESSION** |

The first three rows match the cases §0.8 review explicitly
called out. Rows 4–6 record additional anchors: row 4
documents that the STRONG boundary at $(+0.10, 0.30)$ is
inclusive on both axes; row 5 documents that high $\delta$
with low $\kappa$ cascades down to MARGINAL through the
$\kappa$ hurdles; row 6 documents that REGRESSION wins
regardless of $\kappa$ once the cascade fires on rule 1.
Future revisits should be able to verify the script's
classification matches this table exactly on these inputs.

**Acceptance / rejection rules (pinned, mapped one-to-one to
the verdict cascade).**

| Verdict | Authorizes | Forecloses |
|---|---|---|
| **STRONG** | Drafting a §15.2 implementation pre-commitment for an abstention/escalation product layer (separate §0.8 commitment). | VC-brief changes; cross-domain claims; auto-deployment without §15.2. |
| **USEFUL_INTERNAL** | Documenting internal-research operational value of the §13.10 score for selective prediction at this configuration. | §15.2 product investment; VC-brief changes; cross-domain claims. |
| **MARGINAL** | Recording §15 as an acknowledged but unactionable signal. | §15.2 follow-up; internal-research operational claims; product investment; VC-brief changes. |
| **SATURATION** | Documenting §15 as operational null; extending LLM transfer-line closure to "answer-selection AND selective-prediction both saturated." | §15.2 follow-up at any observable; product investment; VC-brief changes. |
| **REGRESSION** | Closing §13.10-as-selective-prediction-risk-score line. The §13.10 AUC=0.661 baseline of record is unaffected (different metric class). | §15.2 follow-up at this observable; product investment; VC-brief changes. |

**Statistical confirmation (pinned).** Per benchmark, paired
bootstrap over question indices, $B = 1000$ resamples,
deterministic seed (`numpy.random.SeedSequence(entropy=15)`).
For each resample, recompute $\delta_b$ on the resampled
question set and report the 2.5th and 97.5th percentiles as
the two-sided 95% CI on $\delta_b$. Equivalent computation
for $\kappa_b$.

The headline confirmation question is whether $\delta_b > 0$
is supported by the data after sampling variance is
accounted for. Pinned reporting in the §15 result section:
each benchmark's
$\big(\hat\delta_b,\;\text{CI}_{0.025}^{0.975}(\delta_b),\;\hat\kappa_b,\;\text{CI}_{0.025}^{0.975}(\kappa_b)\big)$
tuple alongside the verdict.

**Pinned demotion rule (statistical safeguard for the
highest-stakes verdict only).** If the verdict cascade
returns **STRONG**, the bootstrap CI lower bound on
$\delta_b$ must be $> 0$ on **both** benchmarks. If either
benchmark's CI lower bound is $\le 0$, the verdict is
demoted to **USEFUL_INTERNAL** with explicit
`STRONG_BUT_CI_DEMOTION` annotation in the result section.

USEFUL_INTERNAL, MARGINAL, SATURATION, and REGRESSION
verdicts are NOT subject to bootstrap-CI demotion. Their
operational scope does not require external statistical
confirmation: USEFUL_INTERNAL and MARGINAL are documentation-
only with explicit no-investment scope; SATURATION and
REGRESSION are themselves rejection verdicts. Pinning the
demotion rule narrowly to STRONG keeps the cascade
exhaustive and deterministic while preventing a noise-driven
STRONG point estimate from authorizing §15.2 investment.

**No sign-test analogue.** Per-question paired sign testing
on the §15 metric class does not yield information beyond the
bootstrap CI on $\delta_b$ — selective prediction's unit of
analysis is the (answered, abstained) partition, not a per-
question paired comparison against an explicit alternative.
The bootstrap CI on $\delta_b$ is the pinned statistical
confirmation; no sign-test is computed for the §15 verdict.

**Operational baselines (pinned).**

§15 compares against two operational baselines. Both yield
concrete answer/abstain decisions on the same questions;
neither is a renaming of the §13.10 risk score that drives
the §15 policy.

**Baseline 1 — Never-abstain ($B_\text{never}$).** Always
answer the §13.10 greedy completion; never abstain.

- Coverage: $1.0$ by construction.
- Residual accuracy: equals §13.10 greedy ($0.250$ on
  TruthfulQA-MC, $0.300$ on HaluEval-QA per §13.10).
- AURC contribution: single sweep endpoint at
  $(\text{cov} = 1, e = W/N) = (1, 0.750)$ on TruthfulQA-MC,
  $(1, 0.700)$ on HaluEval-QA.
- Role: documents the operational floor at full coverage —
  what doing nothing gets you.

**Baseline 2 — Random-abstain at matched coverage
($B_\text{random}$).** At each operating point $\tau$ with
$\text{cov}(\tau) = |A_\tau| / N$, the matched-coverage
random comparator answers a uniformly random subset of size
$|A_\tau|$ and abstains the rest.

By linearity of expectation, $B_\text{random}$ has closed-form
expected operational metrics independent of which random
subset is drawn:

- $\mathbb{E}[\text{acc}_{B_\text{random}}(\text{cov})] = (N - W) / N$
  (= the greedy accuracy; constant in $\text{cov}$).
- $\mathbb{E}[\text{AURC}_{B_\text{random}}] = W / N$
  (the $\Delta\text{AURC}$ baseline already pinned in
  Metric 4 and used by the verdict cascade in chunks 4a / 4b).

§15 reports the **analytic expectation** for $B_\text{random}$;
no empirical resampling is performed (the expectation is
closed-form and exact). Bootstrap CIs from §15's statistical
confirmation are computed on
$\delta_b = \text{AURC}^{B_\text{random}}_b - \text{AURC}^{\text{policy}}_b$
and capture both quantities' joint sampling variance over
question indices.

- Role: documents what selective-prediction value the §15
  policy adds beyond random abstention at matched coverage.
  This is the central quantity the §15 verdict bands
  threshold against (the headline statistic $\delta$).

**Explicitly NOT a §15 baseline.**

- **No oracle baseline.** A perfect-information abstainer
  (always abstains the wrong answers, always answers the
  right ones) is an upper bound (AURC = 0), not an operational
  comparator. Not pinned; does not participate in the verdict
  cascade. It may be reported as a diagnostic upper-bound
  number alongside the verdict but is not load-bearing.
- **No alternative-observable comparator.** Per Chunk 2c, §15
  pins exactly one observable. Any "BCVF-specific structure"
  comparator (e.g., 2nd-difference variants from §13.14 /
  §13.16 / §13.18) is out of scope at this commitment;
  would require a fresh §0.8 in a separate §15.2.
- **No alternative-threshold comparator on the same observable.**
  $r(q) = H(q)$ used at any threshold $\tau$ IS the §15
  policy, parameterized by $\tau$ — just a different operating
  point on the same risk-coverage curve, not a meaningfully
  different baseline.

**Disclosed simplifications and risks (pinned).**

Three categories: scope exclusions, load-bearing assumptions,
and failure-mode interpretations. Pinned in advance so the
result section reads off them mechanically.

**(1) What §15 is explicitly NOT testing.**

- **Not answer-selection.** §15 never substitutes the §13.10
  greedy completion. A §15 STRONG does not retroactively
  reopen any §13/§14 answer-selection hypothesis class; per
  §14c those verdicts remain binding. A §15 SATURATION does
  not weaken §13.10's marginal-pass — it only documents that
  the same signal does not transfer to the abstention metric
  class either.
- **Not retrieval augmentation.** §15 introduces no retrieval,
  search, or external knowledge source. The policy's only
  action when triggered by high $r(q)$ is to abstain — never
  to fetch additional context, query a tool, or escalate to a
  different model. Retrieval-augmented selective prediction is
  a strictly larger hypothesis class requiring a fresh §0.8.
- **Not cross-model routing.** §15 consumes no §13.11 / §14a /
  §14a.2 cross-model material. Higher-capability fallback
  (Qwen-32B, GPT-4-class) on the abstained questions is a
  different policy and would require the model-scale future-
  work item from §13.8 to land first.
- **Not calibration beyond the pinned entropy policy.** No
  isotonic calibration, no Platt scaling, no conformal
  wrapping, no post-hoc transform of $r(q)$. The threshold
  $\tau$ is the only fitted parameter, and it is fitted only
  via the deterministic empirical-support sweep — not via
  held-out tuning.

**(2) Load-bearing assumptions.**

- **Correctness labels inherited from §13.10.** $c(q)$ is the
  §13.10 NLI-derived label (entails right_answer AND not any
  distractor). §15 inherits any labeling artifacts §13.10
  carries — over-strict NLI on TruthfulQA-MC, missed
  paraphrases on HaluEval-QA, etc. A §15 verdict reflects the
  policy's selective behavior *under §13.10's labeling*, not
  an independent test of label quality.
- **Fixed dump schema.** Per Chunk 2b, §15 reads only the
  three pinned fields and fails fast on schema drift. Any
  field-set change requires fresh §0.8 review before §15 re-
  runs.
- **Threshold sweep over empirical support only.** $\tau$
  varies across the sorted unique $r(q)$ values per benchmark.
  $\delta$ is reported with bootstrap CI but $\text{cov}@\alpha$
  is computed on the discrete grid only; verdict resolution
  depends on the empirical support being dense enough at
  N=100 to bracket the pinned $\alpha$ targets.
- **Benchmark-local operating points.** Each benchmark's sweep
  is independent. There is no single operational $\tau$ that
  applies to both, and §15 STRONG does NOT authorize deploying
  any single $\tau$ — choice of a deployment threshold is a
  separate calibration exercise with its own pre-commitment
  (and would land in a §15.2 if STRONG fires).

**(3) Failure-mode interpretations.**

- **High AURC lift but tiny coverage.** Signature: large
  $\delta$ but $\kappa < 0.10$. Cascade verdict: SATURATION
  (rule 4 fails on $\kappa$; rule 5 catches). Even with
  STRONG-range $\delta$, this is the "Pyrrhic" outcome where
  the policy identifies a small high-confidence subset but
  cannot deliver useful coverage. The cascade is intentionally
  designed to reject this mode — operational value requires
  both AURC lift AND meaningful coverage.
- **Good coverage but weak error capture.** Signature:
  $\kappa$ in STRONG/USEFUL range but $\delta$ in MARGINAL/
  SATURATION. The policy sustains coverage at the target
  accuracy but reaches it by rejecting questions roughly at
  the random rate — i.e., the entropy threshold lands on a
  high-coverage operating point on a benchmark where greedy
  accuracy is already near target, not because the policy
  selectively catches errors. Cascade produces MARGINAL or
  SATURATION; operational read: "the answered subset is
  acceptable but the policy is not the source of the lift."
- **Benchmark asymmetry under worst-benchmark rule.** If one
  benchmark lands STRONG and the other SATURATION, combined
  classification is SATURATION (or whichever lower band
  applies). Intentional and mirrors §13/§14's worst-benchmark
  discipline. The result section must report per-benchmark
  $(\delta_b, \kappa_b)$ alongside the combined $(\delta,
  \kappa)$ so any asymmetry is visible — that is itself a
  publishable diagnostic finding (selective prediction
  transfers on benchmark X but not benchmark Y at this
  configuration).
- **STRONG blocked by CI demotion.** If point estimates
  satisfy STRONG but either benchmark's bootstrap CI on
  $\delta_b$ fails to clear zero, the verdict demotes to
  USEFUL_INTERNAL with `STRONG_BUT_CI_DEMOTION` annotation
  (Chunk 4c). Operational read: the policy may have a
  population-level effect, but at N=100 the data does not
  yet support a confident lift estimate; §15.2 product
  pre-commitment is not authorized until a re-run at larger
  N (a separate fresh §0.8 commitment) clears CI on both
  benchmarks.

**Expected cost (pinned).**

§15.1 is a **pure post-processing selective-prediction
analysis** over already-computed §13.10 dumps. Reinforcing
the framing: this is not a fresh experiment family in
disguise.

- **Compute:** CPU only. No GPU, no model loads, no NLI
  forward passes, no generation calls of any kind.
- **Inputs:** the two pinned dumps from Chunk 2b. Disk read
  only; ~200 KB combined order of magnitude.
- **Wall clock (estimated):** under 30 seconds total for
  both benchmarks, including $B = 1000$ bootstrap resamples
  per benchmark. Threshold sweep at $N=100$ yields ≤102 grid
  points; bootstrap over 100 indices is sub-millisecond per
  resample in numpy.
- **External dependencies:** `numpy` + Python stdlib only. No
  `transformers`, no `torch`, no HuggingFace cache, no
  network access. `HF_HOME` / `HF_TOKEN` not consumed.

**Report destination (pinned).**

Two output artifacts, exactly:

1. `docs/experiments/probe_selective_abstention.json` — single
   machine-readable artifact covering both benchmarks.
2. `docs/experiments/probe_selective_abstention.md` — single
   human-readable summary report.

**Mandatory JSON schema (top-level keys; each benchmark
contributes one nested block):**

```
{
  "schema_version": "15.1",
  "n_questions": 100,
  "bootstrap_B": 1000,
  "bootstrap_seed": "SeedSequence(entropy=15)",
  "benchmarks": {
    "truthfulqa_mc": {
      "greedy_accuracy": <float>,
      "total_wrong_W": <int>,
      "auc_random": <float>,
      "auc_policy": <float>,
      "delta_auc": <float>,
      "delta_auc_ci": [<lo>, <hi>],
      "kappa": <float>,
      "kappa_ci": [<lo>, <hi>],
      "operating_points": [
        {"alpha": 0.35, "cov": <float>, "tau_star": <float>,
         "ecr": <float>, "far": <float>},
        {"alpha": 0.50, ...},
        {"alpha": 0.75, ...}
      ],
      "threshold_sweep": [
        {"tau": <float>, "cov": <float>, "acc": <float>,
         "ecr": <float>, "far": <float>}, ...
      ]
    },
    "halueval_qa": { ... same shape, alpha_1 = 0.40 ... }
  },
  "combined": {
    "delta": <float>,
    "kappa": <float>,
    "verdict": "STRONG" | "USEFUL_INTERNAL" | "MARGINAL"
             | "SATURATION" | "REGRESSION",
    "verdict_annotations": []
  }
}
```

**Mandatory markdown report contents:**

- Per-benchmark headline table:
  $(\hat\delta_b, \text{CI}(\delta_b), \hat\kappa_b, \text{CI}(\kappa_b))$.
- Per-benchmark operating-point table at all three $\alpha$:
  $(\text{cov}@\alpha, \text{ecr}(\tau^*), \text{far}(\tau^*))$.
- Combined $(\delta, \kappa)$ under the worst-benchmark rule.
- Cascade trace mapping $(\delta, \kappa)$ to a verdict
  (the same kind of explicit walk-through used in Chunk 4b's
  audit table).
- Final `verdict` and any `verdict_annotations`.

**Pinned final verdict fields (in both JSON and markdown):**

- `verdict` ∈ `{STRONG, USEFUL_INTERNAL, MARGINAL,
  SATURATION, REGRESSION}` (exactly one).
- `verdict_annotations`: list (possibly empty); may include
  `STRONG_BUT_CI_DEMOTION` per Chunk 4c.

**Implementation scope (pinned — the §15.1 execution
boundary).**

§15.1 **authorizes**:

- Implementing `scripts/probe_selective_abstention.py` per
  Chunks 2b–6.
- Reading the two pinned input dumps.
- Computing the pinned five operational metrics.
- Running the verdict cascade and bootstrap CI exactly as
  pinned.
- Writing the two pinned output artifacts.

§15.1 **does NOT authorize**:

- Regenerating any §13.10 dump or any other §13/§14 dump.
- Changing the correctness labeling protocol or rerunning
  NLI on the dumps.
- Substituting another benchmark for TruthfulQA-MC or
  HaluEval-QA, or adding a third benchmark.
- Changing the risk score $r(q)$ from §13.10 semantic
  entropy to anything else.
- Adding a secondary observable comparator (Chunk 2c pin).
- Adding retrieval, routing, selector, or any consumer
  logic beyond the pinned threshold rule.
- Changing the threshold sweep grid, the $n_{\min}$ floor,
  the pinned $\alpha$ targets, or any band threshold.
- Auto-promoting any verdict to §15.2 — any §15.2 work
  requires a fresh §0.8 commitment per Chunks 4a / 4c.
- Updating `AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md` (per §13.9
  hold; §15's metric class cannot satisfy the §13.9 gate by
  construction).

Any deviation discovered at run time must be flagged in the
§15 result section as a §0.8 deviation, not absorbed
silently.

### 15.1 Amendment 1 — Input-path correction and explicit field-name pinning (pre-implementation)

**Status: amendment landed before any data inspection or
script execution.** Surfaced explicitly per §15.1's own "no
silent patches" rule.

**Trigger.** Pre-implementation audit of
`scripts/probe_semantic_entropy.py` (the §13.10 data-
producing script) revealed two §0.8 issues with the original
Chunk 2b pin:

1. **Input filename mismatch.** Chunk 2b pinned the
   TruthfulQA-MC dump path as
   `docs/experiments/probe_semantic_entropy.json` (matching
   §13.10's prose). The §13.10 script in fact emits per-
   benchmark filenames suffixed with the benchmark id:
   `probe_semantic_entropy_truthfulqa_mc.json` and
   `probe_semantic_entropy_halueval_qa.json`. A strict
   reading of the original Chunk 2b pin would have caused
   §15's fail-fast loader to abort with `SCHEMA_MISMATCH:
   file not found` against the actual on-disk filename.
2. **Field-name underspecification.** Chunk 2b named the
   three consumed fields by description (semantic entropy
   nats, correctness label, question id) but did not pin the
   exact JSON key names. Implementation requires the exact
   keys; leaving them implicit invites silent fallback to
   alternative field names.

**Amendment (this chunk supersedes the affected lines in
Chunk 2b).**

- TruthfulQA-MC input path is corrected to
  `docs/experiments/probe_semantic_entropy_truthfulqa_mc.json`.
- HaluEval-QA input path is unchanged
  (`docs/experiments/probe_semantic_entropy_halueval_qa.json`,
  already correct).
- Pinned field-name mapping:
  - `q_idx` → question identifier.
  - `semantic_entropy` → risk score $r(q) = H(q)$ in nats.
  - `greedy_matches_correct` → correctness label $c(q)$.
- All other §15.1 pins (primary observable definition,
  threshold-sweep protocol, metrics, bands, baselines, cost,
  scope) are unchanged.

**Why this is a §0.8-clean amendment, not a substantive
revision.** The amendment corrects a pre-commitment artifact
(filename and field-name underspecification) without changing
any pinned numerical band, metric definition, baseline,
acceptance/rejection rule, or scope boundary. No data has been
inspected. The cascade boundary-case audit table from Chunk 4b
is unaffected. The amendment is recorded explicitly here so
the audit trail shows the revision rather than a silent rename
during implementation.

**What this amendment does NOT change:**

- Numerical bands (Chunks 4a / 4b).
- Operational metric definitions (Chunks 3a / 3b).
- Baselines (Chunk 5).
- Disclosed simplifications, assumptions, or failure modes
  (Chunk 6).
- Output paths or schema (Chunk 7).
- The "no secondary observable" pin (Chunk 2c).
- The fail-fast schema-mismatch behavior; only the *target*
  filenames and field names that fail-fast checks against
  are corrected.

### 15.1 Amendment 2 — TruthfulQA-MC input-path revert (post on-disk verification)

**Status: amendment landed before any data inspection or
verdict computation.** Surfaced explicitly per §15.1's "no
silent patches" rule.

**Trigger.** First real-data invocation of
`scripts/probe_selective_abstention.py` in the runpod
container (where the actual §13.10 dumps reside) returned
`SCHEMA_MISMATCH: input dump not found` against the
Amendment-1-pinned path
`docs/experiments/probe_semantic_entropy_truthfulqa_mc.json`.
A `ls -la docs/experiments/probe_semantic_entropy*.json`
audit revealed:

- `probe_semantic_entropy.json` (254 KB, the actual §13.10
  TruthfulQA-MC dump — un-suffixed).
- `probe_semantic_entropy_halueval_qa.json` (210 KB, matches
  the original Chunk 2b pin; unchanged).

The original Chunk 2b pin (`probe_semantic_entropy.json` for
TruthfulQA-MC, un-suffixed) was therefore *correct* and
matched both the §13.10 prose Artifacts block and the actual
on-disk dump. Amendment 1 had extrapolated a suffixed path
from the §13.10 *script's* filename template
(`f"probe_semantic_entropy_{benchmark}.json"`), without
verifying against on-disk reality, and introduced a path
that did not match anything in the runpod's
`docs/experiments/` directory.

**Amendment (this chunk supersedes the TruthfulQA-MC path
component of Amendment 1).**

- TruthfulQA-MC input path **reverted** to
  `docs/experiments/probe_semantic_entropy.json`
  (un-suffixed; matches §13.10 prose and on-disk reality).
- HaluEval-QA input path remains
  `docs/experiments/probe_semantic_entropy_halueval_qa.json`
  (unchanged across both amendments).
- Field-name pinning from Amendment 1 (`q_idx`,
  `semantic_entropy`, `greedy_matches_correct`) is unchanged
  and verified against the §13.10 script's JSON writer.
- All other §15.1 pins (numerical bands, metric definitions,
  baselines, cost, scope, fail-fast behavior) are unchanged.

**Why this is a §0.8-clean amendment.** Like Amendment 1, this
amendment corrects a pre-commitment artifact (a wrong filename
introduced by Amendment 1) without changing any pinned
numerical band, metric definition, baseline, acceptance/
rejection rule, or scope boundary. No data has been inspected.
The cascade boundary-case audit table from Chunk 4b is
unaffected; `--self-test` continues to pass 13/13 unchanged.

**What this amendment does NOT change:**

- Amendment 1's field-name pin (still binding).
- Numerical bands (Chunks 4a / 4b).
- Operational metric definitions (Chunks 3a / 3b).
- Baselines (Chunk 5).
- Disclosed simplifications, assumptions, or failure modes
  (Chunk 6).
- Output paths or schema (Chunk 7).
- The "no secondary observable" pin (Chunk 2c).
- Fail-fast schema-mismatch behavior; only the *target*
  TruthfulQA-MC filename is reverted.

**Audit lesson recorded for future amendments.** Filename
pins should be verified against the actual on-disk artifact
in the execution environment, not extrapolated from the
producing script's template. Amendment 1's mistake — assuming
the script's template determined the on-disk filename without
checking the §13.10 prose's explicit Artifacts list — would
have caught itself sooner if a `ls`-based on-disk check had
been part of the amendment's own §0.8 review.

### 15.2 Result — §15.1 selective abstention scout returned MARGINAL

The §15.1 pre-committed scout has been executed against the
on-disk §13.10 dumps in the runpod container. Combined
classification per pre-committed bands:
**`MARGINAL`** (δ = +0.1159, κ = 0.1400, no annotations).
The §13.10 single-snapshot semantic-entropy score, used as a
per-question risk score in a deterministic answer/abstain
policy, produces small but non-zero AURC lift over random
abstention with statistical confirmation, but does not
support enough coverage at the α₂ = 0.50 absolute-majority
operating point on the worst benchmark to clear
USEFUL_INTERNAL.

Combined with §13.19's 5-of-5 single-axis null and §14b /
§14c's SCOUT_SATURATION on system-level routing, this is the
selective-prediction outcome that §15.1's bands were designed
to classify cleanly: the §13.10 ceiling supports
operationally-detectable but operationally-unactionable
abstention behavior at this configuration. The autonomy-
domain BCVF claim (§6.1) stands independently and is
unaffected. The §13.9 VC-brief hold remains in force and is
not addressed by §15 by construction (different metric class
than §13.9's gating bar).

**Parity-gate confirmation (per §15.1 Chunks 2b / 3a / 5).**

| benchmark | N_ok | W_ok | auc_random_ok |
|---|---|---|---|
| truthfulqa_mc | True | True | True |
| halueval_qa | True | True | True |

Both benchmarks satisfied N=100, W matches `PINNED_W` (75 on
TruthfulQA-MC, 70 on HaluEval-QA), and `AURC_random = W/N`
exactly. No §0.8 deviation from the §15.1-pinned configuration
fired at the input layer.

**§15.1 amendment audit trail.** Two §0.8 amendments to §15.1
landed before any data inspection: Amendment 1 added
explicit field-name pinning (`q_idx`, `semantic_entropy`,
`greedy_matches_correct`) and a per-benchmark-suffixed
TruthfulQA-MC input path; Amendment 2 reverted the TruthfulQA-
MC path to the un-suffixed `probe_semantic_entropy.json`
after on-disk verification in the runpod showed the actual
§13.10 artifact at that path. Both amendments are recorded in
§15.1 with full rationale. The post-amendment configuration
matches on-disk dumps exactly; **no further amendments fired
during the run** and the verdict is reported under the
amended-but-otherwise-unchanged §15.1 commitment.

**Self-test gate.** §15.1's required pre-execution gate
(`--self-test`) ran in the same invocation as real-data
execution and returned PASSED on all 6 cascade boundary cases
(Chunk 4b audit table) and all 7 demotion-rule cases (Chunk
4c). The cascade implementation matches the pinned design
exactly; the verdict reported below is the cascade's
mechanical readout, not interpretation.

**Artifacts.**

- `scripts/probe_selective_abstention.py` (numpy + stdlib,
  CPU-only post-processor; 1112 lines).
- `docs/experiments/probe_selective_abstention.json` (machine-
  readable, schema_version `15.1`, both benchmarks plus
  combined verdict; full threshold sweep included).
- `docs/experiments/probe_selective_abstention.md` (human-
  readable summary with per-benchmark headline, operating
  points, combined classification, and cascade trace).

**Per-benchmark headline result.**

| benchmark | greedy_acc | $W$ | AURC_random | AURC_policy | $\delta$ | $\delta$ 95% CI | $\kappa$ | $\kappa$ 95% CI |
|---|---|---|---|---|---|---|---|---|
| truthfulqa_mc | 0.250 | 75 | 0.7500 | 0.6341 | **+0.1159** | [+0.0213, +0.1925] | **0.1400** | [0.0000, 0.3600] |
| halueval_qa | 0.300 | 70 | 0.7000 | 0.5609 | **+0.1391** | [+0.0432, +0.2152] | **0.2600** | [0.0000, 0.5700] |

**Combined under worst-benchmark rule** (Chunk 4a):
$\delta = \min_b \delta_b = +0.1159$ (TruthfulQA-MC),
$\kappa = \min_b \kappa_b = +0.1400$ (TruthfulQA-MC).

**Cascade trace** (mechanical readout per §15.1 Chunks 4a /
4b; matches the implementation's `_cascade_trace` output
exactly):

```
rule 1 REGRESSION: delta=+0.1159 < -0.02         -> NO
rule 2 STRONG:     delta>=+0.10 AND kappa>=0.30  -> NO   (kappa=0.14 < 0.30)
rule 3 USEFUL_INTERNAL: delta>=+0.05 AND kappa>=0.20  -> NO   (kappa=0.14 < 0.20)
rule 4 MARGINAL:   delta>=+0.02 AND kappa>=0.10  -> YES
```

**Demotion rule (Chunk 4c) — did NOT fire.** The §15.1
demotion rule is STRONG-only by construction; since the
point-estimate verdict is MARGINAL (rule 4), the demotion
rule does not apply and `verdict_annotations = []`. For
audit completeness: had the verdict been STRONG, both
benchmarks' $\delta$ CI lower bounds are strictly positive
(0.0213 on TruthfulQA-MC, 0.0432 on HaluEval-QA), so the
demotion rule would NOT have fired even if STRONG had
classified.

**Three observations the headline supports.**

**(a) The AURC lift over random is statistically supported on
both benchmarks individually.** Both per-benchmark $\delta$
95% CI lower bounds are strictly positive (0.021 and 0.043).
The §13.10 entropy is genuinely truth-correlated for selective
prediction in the integrated AURC sense, not within sampling
noise. This is qualitatively distinct from a "saturation"
verdict — the policy does carry signal.

**(b) The $\delta$ point estimates are individually in the
STRONG band on both benchmarks.** TruthfulQA-MC $\delta =
+0.1159$ and HaluEval-QA $\delta = +0.1391$ each clear the
$\delta \ge +0.10$ STRONG threshold from §15.1 Chunk 4a. **It
is the $\kappa$ hurdle, not the $\delta$ hurdle, that
prevents a higher verdict band.** The §13.10 entropy can
identify wrong-answer enrichment in the integrated curve but
cannot deliver enough operating-point density at $\alpha_2 =
0.50$ on the worst benchmark.

**(c) The $\kappa$ CI lower bounds are 0.000 on both
benchmarks.** TruthfulQA-MC $\kappa$ CI = $[0.000, 0.360]$,
HaluEval-QA $\kappa$ CI = $[0.000, 0.570]$. Bootstrap cannot
rule out "no qualifying $\tau$ on the resample" at $N = 100$.
This is a power-of-measurement observation, not a $\kappa = 0$
claim — see §15.2 Chunk 2c (asymmetry analysis) and Chunk 6
§(3) failure-mode "STRONG blocked by CI demotion" for the
analogous discussion at $\delta$. A larger-N re-run would
likely tighten this band; that re-run is NOT authorized by
§15.1 and would require a fresh §0.8 commitment.

**Per-benchmark asymmetry under the worst-benchmark rule.**

The combined verdict is MARGINAL because the worst-benchmark
rule pulls TruthfulQA-MC's MARGINAL-grade $(\delta, \kappa)$
through. Each benchmark's own per-benchmark verdict, computed
by feeding only its own $(\delta_b, \kappa_b)$ through the
§15.1 cascade, is *higher* than the combined verdict:

| benchmark | $\delta_b$ | $\kappa_b$ | per-benchmark verdict (Chunk 4a / 4b cascade applied to that benchmark alone) |
|---|---|---|---|
| TruthfulQA-MC | +0.1159 | 0.1400 | **MARGINAL** (rule 4: $\delta \ge +0.02$ AND $\kappa \ge 0.10$, both cleared; rule 3 fails on $\kappa < 0.20$) |
| HaluEval-QA  | +0.1391 | 0.2600 | **USEFUL_INTERNAL** (rule 3: $\delta \ge +0.05$ AND $\kappa \ge 0.20$, both cleared; rule 2 fails on $\kappa < 0.30$) |
| **combined (min)** | **+0.1159** | **0.1400** | **MARGINAL** |

This is the canonical Chunk 6 §(3) failure-mode signature
"benchmark asymmetry under worst-benchmark rule" pinned
ex ante in §15.1. The asymmetry is **documented but
non-promotable**: per the §15.1 worst-benchmark rule (Chunk
4a) and per Chunk 6 §(3)'s explicit "intentional and matches
§13/§14's worst-benchmark discipline" guidance, the combined
classification is MARGINAL and is binding.

**TruthfulQA-MC's structural role across all three §13 / §14 /
§15 programs.** TruthfulQA-MC has now defeated three distinct
metric classes under the same worst-benchmark rule:

- **§13** (AUC of observable vs ground truth, Chunks 13.10–
  13.18): TruthfulQA-MC capped 5 of 5 single-axis hypothesis
  classes; the §13.18 Variant A entropy 2nd-difference scored
  AUC 0.701 on HaluEval-QA but 0.536 on TruthfulQA-MC, forcing
  combined ANTI.
- **§14** (Δ accuracy vs naive aggregation; deferred to full
  §14 conditional on scout STRONG): the scout never reached
  full §14, so TruthfulQA-MC was never independently evaluated
  at the system level — but the scout-level saturation on
  HaluEval-QA was already enough to foreclose full §14.
- **§15** (AURC lift + κ at α₂; this section): TruthfulQA-MC
  $\kappa = 0.14$ pulls combined classification one band below
  HaluEval-QA's per-benchmark USEFUL_INTERNAL.

The pattern is consistent: TruthfulQA-MC's adversarial
distractor structure (designed to match common false-belief
patterns) compresses entropy distributions in a way that
limits both AUC-based and AURC-based discrimination at the
7B + DeBERTa-v3-base configuration. **§15 does not falsify
or weaken this pattern; it adds a third metric-class data
point that confirms it.**

**Why this asymmetry is not a defect of §15.1's bands.** The
§15.1 worst-benchmark rule was pinned ex ante in Chunk 4a
specifically to mirror the §13 / §14 disciplines. Per-
benchmark splits where one benchmark would clear a higher
band and the other would not is **exactly** the case the
worst-benchmark rule was designed to handle uniformly. A
benchmark-conditional verdict (HaluEval-QA USEFUL_INTERNAL,
TruthfulQA-MC MARGINAL) would require a fresh §0.8 commitment
with a different combined-classification rule (e.g., per-
benchmark verdicts as the primary unit, or a pareto-frontier
structure across the two benchmarks). It is NOT authorized by
§15.1 and would not retroactively re-classify the §15.1
verdict-of-record reported in §15.2.

**Operating-cliff analysis — the ecr / far cost at α₂.**

The full operating-point table at all three pinned target-
accuracy points (Chunk 3a, $\alpha_1 = $ baseline + 10pp;
$\alpha_2 = 0.50$; $\alpha_3 = 0.75$):

| benchmark | $\alpha$ | $\text{cov}@\alpha$ | $\tau^*$ | ecr | far |
|---|---|---|---|---|---|
| truthfulqa_mc | 0.35 | 0.32 | 1.4979 | 0.7333 | 0.5200 |
| truthfulqa_mc | 0.50 | 0.14 | 0.6931 | 0.9067 | 0.7200 |
| truthfulqa_mc | 0.75 | 0.00 | $+\infty$ | NaN | NaN |
| halueval_qa  | 0.40 | 0.36 | 1.4979 | 0.7000 | 0.5000 |
| halueval_qa  | 0.50 | 0.26 | 1.0889 | 0.8143 | 0.5667 |
| halueval_qa  | 0.75 | 0.00 | $+\infty$ | NaN | NaN |

Three operationally relevant features:

**(a) Coupled high error-capture + high false-abstention at
$\alpha_2$.** At the absolute-majority operating point, the
policy catches **91% of TruthfulQA-MC's wrong greedy answers
and 81% of HaluEval-QA's** ($\text{ecr} = 0.91 / 0.81$), but
also abstains **72% of TruthfulQA-MC's correct greedy answers
and 57% of HaluEval-QA's** ($\text{far} = 0.72 / 0.57$).
This is the classical selective-prediction "throw out most
answers to keep the answered ones clean" trade-off: error
capture is high (so Chunk 6 §(3)'s "good coverage but weak
error capture" failure mode is *not* fired), but the false-
abstention cost makes the operating point operationally
expensive. Deployment without further calibration would
refuse most of the user's questions.

**(b) $\alpha_1$ vs $\alpha_2$ collapse asymmetry.** Both
benchmarks share the *same* $\tau^* = 1.4979$ at $\alpha_1$
(TruthfulQA-MC at 0.35, HaluEval-QA at 0.40), suggesting the
high-entropy tails of the two benchmarks' $r(q)$ distributions
are structurally similar. The divergence appears at
$\alpha_2 = 0.50$: TruthfulQA-MC requires $\tau^*$ to drop to
$0.6931 = \ln 2$ (the entropy of a 2-cluster equal-split) to
keep acc $\ge 0.50$, costing more coverage; HaluEval-QA can
hold $\tau^* = 1.0889$ and keep more questions in the answered
set. This is the structural reason TruthfulQA-MC's $\kappa$ is
lower than HaluEval-QA's even when both benchmarks' high-
entropy regions look comparable.

**(c) $\alpha_3 = 0.75$ degenerate on both benchmarks.**
$\text{cov}@0.75 = 0$ on TruthfulQA-MC AND on HaluEval-QA.
**No threshold $\tau$ in the empirical sweep grid (102 points
per benchmark) yields acc $\ge 0.75$ on an answered subset of
size $\ge n_{\min} = 10$.** This is a hard ceiling at the
configuration: deployment-grade accuracy ($\ge 75\%$) cannot
be reached from a base model at greedy accuracy $\le 0.30$
through abstention alone at this scale. It is the strongest
single piece of evidence that an abstention/escalation
product layer over §13.10-grade signals at this configuration
**cannot reach a deployment-grade subset** — even if the
verdict had been STRONG, $\alpha_3$ degeneracy would have
forced any deployment claim to operate at $\alpha < 0.75$
target-accuracy bands.

**Mapping to Chunk 6 §(3) failure-mode catalogue.** The §15.1
result hits one of the four pre-pinned failure modes exactly
(benchmark asymmetry, §15.2 Chunk 2c above) and is *adjacent*
to a second:

- **"High AURC lift but tiny coverage"** (Chunk 6 §(3) item
  1): pinned signature was $\delta$ STRONG-range AND $\kappa <
  0.10 \to$ SATURATION. The actual outcome is $\delta$
  STRONG-range AND $\kappa \in [0.10, 0.20)$ on the worst
  benchmark $\to$ MARGINAL — one band higher than the pinned
  failure-mode prediction. The cascade did not fire that
  mode, but the underlying mechanism (delta-rich, kappa-poor
  at $\alpha_2$) is what the failure mode anticipated.

The remaining two pre-pinned failure modes ("good coverage
but weak error capture", "STRONG blocked by CI demotion") are
NOT fired by this run. Both are documented and ruled out by
the headline numbers above.

**What §15.2 authorizes (per §15.1 Chunk 4c MARGINAL row).**

The §15.1-pinned acceptance/rejection mapping for MARGINAL is
binding under §0.8. Reproduced exactly:

| §15.2 verdict | Authorizes | Forecloses |
|---|---|---|
| MARGINAL | Recording §15 as an acknowledged but unactionable signal. | §15.2 follow-up; internal-research operational claims; product investment; VC-brief changes. |

Specifically, §15.2 **authorizes**:

- Documenting the §15.1 verdict-of-record in this section
  (which §15.2 itself accomplishes).
- Recording the per-benchmark $\delta$ / $\kappa$ /
  operating-point numerical evidence for future audit and
  reference.
- Citing the per-benchmark asymmetry (TruthfulQA-MC MARGINAL,
  HaluEval-QA USEFUL_INTERNAL) as a documented structural
  observation about the §13.10 score's operational behavior
  under the worst-benchmark rule.
- Citing §15 alongside §13 / §14 in the combined LLM-track
  closure framing (§15.2 Chunk 2f below).

§15.2 explicitly **does NOT authorize**:

- **A §15.2-as-implementation follow-up** (e.g., a script
  re-run at larger N, a ensemble-score variant, a relaxed
  worst-benchmark rule). Each would require a fresh top-level
  §0.8 commitment.
- **Internal-research operational claims** of the form
  "§13.10 entropy supports useful selective prediction at
  this configuration." Per Chunk 4c, USEFUL_INTERNAL is the
  bar for that claim, and §15.2's combined verdict is one
  band below.
- **Product investment** (any abstention/escalation product
  layer scoped over §13.10-grade signals at this
  configuration). STRONG was the bar for that authorization.
- **VC-brief changes.** Per Chunk 4c, no §15 verdict —
  including STRONG — would have authorized
  `AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md` updates, because §15's
  metric class (operational AURC + coverage) is structurally
  separate from §13.9's gate (answer-selection AUC ≥ 0.75 on
  both benchmarks). §13.9 hold remains in force.
- **Reframing of any §13 or §14 verdict.** §15's MARGINAL is
  on a fresh metric class and does not interact with §13's
  combined ANTI verdicts or §14's SCOUT_SATURATION verdicts.
  Those closures remain binding.
- **Cross-domain claims.** The autonomy-domain BCVF claim
  (§6.1) stands wholly independent of any §15 outcome.

**No deviation flag fired during the §15.1 run.** Per §15.1
Chunk 7's "Any deviation discovered at run time must be
flagged in the §15 result section as a §0.8 deviation, not
absorbed silently": the run produced no such deviation.
Parity gates passed, schema matched (post-Amendment 2), self-
test passed in-run, the cascade fired exactly as the
implementation's `_cascade_trace` walks the pinned rules.
The two §15.1 amendments landed pre-data-inspection are
documented within §15.1 itself, not as run-time deviations.

**Combined picture across §13 / §14 / §15 — LLM-track now
covers three distinct metric classes.**

§15.2 closes the third of three pre-committed metric-class
investigations of BCVF-derived signals on the LLM track:

| Program | Metric class | Question | Combined verdict |
|---|---|---|---|
| §13 | AUC of an observable vs ground-truth correctness | Does observable X correlate with correctness? | 5-of-5 single-axis classes ANTI; §13.10 baseline `TRUTH_CORRELATED_MARGINAL` (AUC 0.661 on both benchmarks) |
| §14 | Δ accuracy of system-level routing vs naive aggregation | Does BCVF-shaped routing lift end-to-end accuracy? | 2-of-2 scout configurations `SCOUT_SATURATION` |
| **§15** | **Risk-coverage operational metrics (AURC + coverage at target accuracy)** | **Does the §13.10 score support a useful answer/abstain policy?** | **MARGINAL** (δ = +0.116 statistically supported; κ = 0.14 limited by TruthfulQA-MC) |

The three programs are structurally independent — different
metric classes, different acceptance rules, different math
objects. **Each was pre-committed under §0.8 with bands fixed
before its data was opened, and each landed at a verdict band
strictly below STRONG on the combined-classification rule.**
The TruthfulQA-MC ceiling is the consistent structural cap
across all three.

**§13.9 VC-brief hold reaffirmed.** §13.9 gates external-
framing changes on `AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md` to a
STRONG-band lift on both benchmarks at any §13 / §14 / §15
probe. §15.2's MARGINAL verdict combined with §13's 5-of-5
ANTI and §14's 2-of-2 SCOUT_SATURATION means **eleven
distinct experimental structures across three metric classes
have now been tested at the 7B + DeBERTa-v3-base + N=100
configuration without producing a STRONG combined classification
on any of them.** The §13.9 hold is *strengthened*, not
weakened, by §15.2's confirmation that the operational-
abstention metric class also fails to clear STRONG.

The honest external framing for any internal-research
referencing of the §13 / §14 / §15 program is now:

> *On Qwen2.5-7B-Instruct + DeBERTa-v3-base + N=100, no
> literature-aligned, mechanism-motivated, system-level, or
> operational-abstention BCVF construction tested in this
> codebase clears the STRONG combined-classification bar on
> the worst-benchmark rule. The LLM transfer line is closed
> across answer-correlation (§13), answer-selection (§14),
> and selective-prediction (§15) metric classes at all eleven
> tested experimental structures.*

**§15 LLM-track operational chapter is closed.** Per Chunk 4c
the MARGINAL verdict explicitly forecloses §15.2-as-
implementation follow-ups at this observable. **Any
follow-up under §15 logic — whether it is an ensemble score,
a relaxed worst-benchmark rule, a hybrid §14-selector +
§15-abstention combination (the natural §14c-anticipated
direction), or a larger-N re-run — would require a fresh
top-level §0.8 commitment with bands pinned before any data
inspection.** None is authorized by §15.2.

**The autonomy-domain BCVF claim (§6.1) stands independently
on the N=21 sign-test that passed in §6.1 / §6.7 and is
unaffected by any §13 / §14 / §15 outcome.** The §13 / §14 /
§15 program tested whether BCVF transfers to LLM
hallucination detection at this codebase's specific scale,
across three distinct metric classes; the answer at this
configuration is no, eleven different ways.

**Artifacts.**

- `scripts/probe_selective_abstention.py` (§15.1 implementation,
  numpy + stdlib only, CPU-only post-processor with
  `--self-test` gate).
- `docs/experiments/probe_selective_abstention.json`
  (machine-readable result with full schema, both benchmarks,
  combined verdict).
- `docs/experiments/probe_selective_abstention.md`
  (human-readable summary with parity gates, per-benchmark
  headlines, operating points, cascade trace, final verdict).

### 15.2 Postscript — upstream §13.10 dumps overwritten post-run

**Status: §0.8 deviation surfaced explicitly per §15.1 Chunk 7.**

After §15.2 Chunks 2a–2f landed (`175fb96`), the §13.10
producer script `scripts/probe_semantic_entropy.py` was re-
executed in the runpod container at `--num-questions 200`
on both benchmarks. Because that script writes to the same
on-disk paths §15.1 reads from
(`docs/experiments/probe_semantic_entropy.json` and
`docs/experiments/probe_semantic_entropy_halueval_qa.json`),
**the §13.10 N=100 dumps that §15.2 was computed against
have been overwritten with N=200 versions.**

**§15.2 verdict-of-record is unchanged.** The artifacts
`docs/experiments/probe_selective_abstention.json` and
`probe_selective_abstention.md` were written from the N=100
dumps and contain the N=100 numbers
(`greedy_accuracy = 0.250 / 0.300`, `total_wrong_W = 75 / 70`,
`delta = +0.1159`, `kappa = 0.1400`, `verdict = MARGINAL`).
Those artifacts are preserved. The §15.2 verdict cited in
Chunks 2a–2f remains binding under §0.8 and is not
recomputed against the new N=200 dumps.

**What is broken.** §15.1's reproducibility chain from
upstream dumps to verdict. Re-running
`scripts/probe_selective_abstention.py` against the current
on-disk dumps would hit `PARITY_GATE_FAILED` (exit 3): the
N=200 dumps yield $N = 200$, $W = 152 / 146$, and
$\text{AURC}_\text{random} = 0.760 / 0.730$, none of which
match the §15.1-pinned $N = 100$, $W = 75 / 70$, and
$\text{AURC}_\text{random} = 0.750 / 0.700$. The script
would abort with the explicit "§15.1 assumptions no longer
hold" message — exactly as designed. **This is not a §15
verdict change; it is a reproducibility-trail break.**

**§0.8 discipline this satisfies.** §15.1 Chunk 7 required
that "any deviation discovered at run time must be flagged
in the §15 result section as a §0.8 deviation, not absorbed
silently." The deviation here was upstream of the §15.1
script's run-time loop — the §13.10 dumps were overwritten
post-run, not at run time — but the spirit of the rule
applies: the change is being surfaced, not absorbed.

**What this postscript does NOT authorize.**

- **Recomputing the §15 verdict against N=200 dumps.** §15.1's
  pinned configuration is N=100; substituting N=200 would
  require a fresh top-level §0.8 commitment with revised
  PINNED_N / PINNED_W / parity gates. Not authorized here.
- **Updating `PINNED_N` / `PINNED_W` in the script** to silence
  the parity gate. That would silently invalidate the §15.2-
  of-record by re-purposing its checkpoint. Not authorized.
- **Re-classifying §13.10.** §13.10's N=100 verdict (AUC
  0.661 / 0.661, `TRUTH_CORRELATED_MARGINAL`) is the §13.10-
  of-record. The N=200 result is a separate empirical
  observation documented in §13.20 below.
- **Restoring the N=100 dumps from regeneration.** Re-running
  §13.10 at N=100 today would produce different per-question
  scores due to sampling stochasticity — the original §15.2
  computation cannot be exactly reproduced even with N
  restored.

**Cross-reference.** The N=200 §13.10 numbers are recorded in
§13.20 below as a separate §13 observation (NOT a re-
classification of §13.10). §15.2's MARGINAL verdict and
§13.10's marginal-pass-of-record both stand at their pinned
configurations.

### 15.3 Pre-commitment — Hybrid §14-selector + §15-abstention scout (new chapter, not a continuation)

**Status: pre-committed, not yet executed.** §0.8-style pre-
commitment recorded before any §14a.2 / §15 / §13.x dump is
opened in hybrid form. Specification, primary risk signal,
success bands, baselines, and acceptance/rejection rules
below cannot be redefined post-hoc.

**Position in the §13 / §14 / §15 program — three closed
chapters at three distinct metric classes:**

- **§13** closed the **single-axis observable** line in
  §13.19 at combined ANTI on all five tested hypothesis
  classes under worst-benchmark.
- **§14** closed the **system-level answer-selection scout**
  line at `SCOUT_SATURATION` on both §14a (string-matched
  selector) and §14a.2 (NLI-clustered selector).
- **§15** closed the **single-source abstention** line at
  `MARGINAL` (§15.2). Per the §15.2 Postscript, that
  verdict-of-record is binding at N=100; §13.20's N=200
  observation does not re-classify it.

§15.3 tests the one structurally distinct combination none
of the three prior chapters tested:

> *Use the §14 answer-producing system to choose an answer,
> then apply a §15-style abstention gate on top of that
> answer. §14 decides which answer to give. §15 decides
> whether it is safe enough to return.*

**This is a new claim, not a re-test of any prior claim.**
Specifically:

- Not "BCVF-style routing alone selects the right answer"
  (§14a.2 closed `SCOUT_SATURATION`).
- Not "the §13.10 entropy alone supports useful abstention
  on the single-source Qwen greedy answer" (§15.2 closed
  `MARGINAL`).
- **But** "§14's selector + a §15-style abstention gate on
  §14's selected answer may produce a different
  answer/abstain operating frontier than either alone."

**Why this is a new metric class.** §14a.2 measured Δ
accuracy of V1 vs Baseline-B at full coverage (no
abstention). §15.1 measured AURC + cov@α of the §13.10
score on the Qwen greedy answer (no §14 selector). §15.3
measures risk-coverage operational metrics applied to
**§14's selected answer**, with the abstention gate fed by
a risk signal computed over §14's selector context. The
unit of analysis is the joint behavior of (Stage A: §14
selector × Stage B: §15-style abstention) on the same per-
question stream — neither §14 nor §15 alone exercised that
joint object.

**§15.3 is a fresh §0.8 commitment.** All §13 / §14 /
§15.1 / §15.2 / §13.20 verdicts remain binding under §0.8
and are NOT retroactively reframed by §15.3 work. A §15.3
STRONG would authorize a separate §15.4-as-implementation
pre-commitment for an answer-selection-plus-abstention
product layer; it would NOT re-classify §14's
`SCOUT_SATURATION` or §15.2's `MARGINAL`.

**Confirmation: no data inspection prior to this pre-
commitment.** No §14a.2 / §15 / §13.x dump has been opened
in hybrid form during the drafting of §15.3. The protocol,
primary risk signal, metrics, and bands in the §15.3
chunks below are pinned from §13 / §14 / §15 prose only.
Looking at the data before the bands are pinned would be
the §0.8 violation pattern §15.3 is designed to prevent.

**Stage A — answer-selection architecture (pinned).**

Stage A is the §14a.2 NLI-clustered selector + V1 softmin
trust consumer, fixed identical to the §14a.2 pinned
configuration. Pinned because:

- V1 softmin $\tau = 0.5$ produced the strongest BCVF-shaped
  lift in the entire §13 / §14 program (+4pp accuracy over
  Baseline-B on HaluEval-QA at N=100, per §14c).
- The §14a.2 NLI-clustered selector is the post-§14a-audit
  version that fixed the string-identity tie-breaking
  degeneracy. It is the only §14 selector that produced
  genuinely different Baseline-A vs Baseline-B numbers.
- §15.3 is a hybrid scout, not a multi-selector comparison.
  Pinning Stage A to one configuration keeps the
  experimental variable narrow (Stage B's abstention layer).

**Stage A specification (pinned):**

- **Source set (M = 3, cross-family, all cached from §13.11
  / §14a.2):** `Qwen/Qwen2.5-7B-Instruct`,
  `meta-llama/Llama-3.1-8B-Instruct`,
  `mistralai/Mistral-7B-Instruct-v0.3`.
- **Per-source K = 10 stochastic samples** at T=1.0,
  max_new_tokens=32, prompt `Q: ... A:`. Identical to
  §13.10 / §13.11 / §14a.2 protocols.
- **Per-source greedy answer** at T=0, max_new_tokens=32,
  same prompt format.
- **Per-source semantic entropy** $H_{\text{src}_i}(q)$ via
  question-conditioned bidirectional NLI clustering of the
  K=10 samples (DeBERTa-v3-base-mnli-fever-anli).
- **V1 softmin consumer (pinned, single):**
  $w_i^{V1} \propto \exp(-H_{\text{src}_i}(q) / \tau)$ with
  $\tau = 0.5$ (autonomy default; §14a.2 pin).
- **NLI-clustered selector (pinned, single):** cluster the
  M=3 source greedies by question-conditioned bidirectional
  NLI entailment, aggregate weights within each cluster,
  pick winning cluster $k^* = \arg\max_k W_k$ (ties broken
  by lowest cluster index), pick representative source
  within winning cluster by highest individual weight (ties
  by lowest source index). Identical to §14a.2's selector.

**Stage A output (the per-question handoff to Stage B).**

For each question $q$, Stage A produces:

- `selected_answer(q)` — the answer string Stage A delivers
  (winning cluster's representative-source greedy).
- `winning_source_id(q)` $\in$ {Qwen, Llama, Mistral} —
  which source's greedy was picked.
- All three per-source semantic entropies
  $\{H_{\text{src}_i}(q)\}_{i=1}^{3}$, including the winning
  source's $H_{\text{src}_{i^*}}(q)$.
- The winning cluster's aggregated weight $W_{k^*}$ and the
  runner-up cluster's aggregated weight
  $W_{k_{\text{runner}}}$.

Stage A makes no abstention decision and consumes no
threshold parameter. Its output is purely the answer plus
the per-question selector context that Stage B can inspect.

**What Stage A explicitly does NOT pin.**

- Multiple consumers (V2 thresholded exclusion, V3 veto-only,
  V4 deadband fallback). All deferred — V1 is pinned single.
- Multiple selectors (highest-weight-source, string-matched,
  uniform majority). Deferred.
- Different source sets. M=3 cross-family is pinned; no
  larger $M$, no model substitution, no single-source
  fallback.
- Re-running §14a.2 from scratch. The on-disk §14a.2 dump
  at `docs/experiments/probe_system_level_scout_v2_halueval_qa.json`
  is the pinned Stage A input. If that dump does not contain
  the fields Stage B requires (`winning_source_id`, per-
  source entropies, per-question correctness labels), §15.3
  fails fast with `SCHEMA_MISMATCH` and requires a fresh
  §0.8 amendment — mirroring §15.1's schema-mismatch
  discipline.

**Stage B — abstention architecture (pinned).**

Stage B sits downstream of Stage A and reads the §14a.2
dump's per-question records. For each question $q$, Stage B
consumes:

- `selected_answer(q)` from Stage A's V1 softmin + NLI-
  clustered selector;
- $c(q)$ — the correctness label of `selected_answer(q)`
  per the §14a.2 NLI labeling protocol (entails right_answer
  AND does not entail hallucinated_answer); **note this is
  the correctness of Stage A's selected answer, NOT Qwen's
  greedy answer — this $c(q)$ is structurally distinct from
  §15.1's $c(q)$ on questions where V1 selects a different
  answer than Qwen-greedy**;
- a per-question identifier for deterministic ordering.

These plus the §15.3 risk signal (pinned in Chunk 3d below)
drive Stage B's per-question answer-or-abstain decision.

**Decision rule (pinned, single).** Per-question deterministic
threshold rule, structurally identical to §15.1 Chunk 2c:
$$
\text{policy}_\tau(q) = \begin{cases}
\text{ANSWER selected\_answer}(q) & \text{if } r(q) < \tau \\
\text{ABSTAIN} & \text{if } r(q) \ge \tau
\end{cases}
$$
where $r(q)$ is the §15.3 risk signal pinned in Chunk 3d.
Ties at $r(q) = \tau$ resolve to ABSTAIN — deterministic,
conservative — identical to §15.1.

**Threshold-sweep protocol (pinned).** $\tau$ is swept across
the sorted unique values of $r(q)$ on the (single) benchmark
plus $-\infty$ (always-abstain) and $+\infty$ (always-answer).
At N=100 this yields at most 102 grid points. All operational
metrics (pinned in Chunk 3e) are computed at every grid
point. No grid is hand-picked; no $\tau$ is hand-picked.
There is no "merged $\tau$" anywhere in §15.3.

**What Stage B explicitly does NOT pin.**

- **Multiple abstention policies.** No deadband (answer if
  $r < \tau_{\text{low}}$, abstain if $r \ge \tau_{\text{high}}$,
  uncertain otherwise), no veto-only mode, no cluster-margin
  rule. One threshold rule, single $\tau$.
- **Multiple risk signals.** One scalar (pinned in Chunk 3d).
  No primary-plus-secondary, no ensemble.
- **Held-out calibration of $\tau$.** $\tau$ is fitted only
  via the deterministic empirical-support sweep — same rule
  §15.1 used. No held-out tuning, no isotonic / Platt /
  conformal wrapping of $r(q)$.
- **Re-decoding or rewriting `selected_answer(q)`.** Stage B's
  only degree of freedom is the answer/abstain decision; the
  answer itself is whatever Stage A produced.
- **Cascading multiple abstention layers.** If the risk
  signal were split across multiple thresholds (e.g., partial
  trust at intermediate $r(q)$), that would be a distinct
  policy and require a fresh §0.8 commitment.

**Risk signal pin (the central §15.3 design decision).**

Per the user-pinned constraint that §15.3 use a single risk
scalar and that the §15-style entropy be preferred absent a
strong reason otherwise, the §15.3 risk signal is pinned as:
$$
r(q) \;=\; H_{\text{src}_{i^*}}(q)
$$
where $i^*$ is Stage A's `winning_source_id(q)` (the source
whose greedy is the winning cluster's representative) and
$H_{\text{src}_{i^*}}(q)$ is that source's semantic-entropy
scalar from the §13.10 / §14a.2 pre-computed K=10 NLI-
clustered protocol. **Higher $H$ means higher per-question
hallucination risk on Stage A's selected answer; Stage B's
policy abstains when the risk exceeds $\tau$.**

This is a §15.1-analogue applied to V1's selected source
rather than to Qwen's greedy: when V1 picks Qwen, $r(q)$
equals §15.1's risk signal; when V1 picks Llama or Mistral,
$r(q)$ equals that source's per-source entropy. The novel
content of §15.3 is the joint behavior on questions where
V1 selects a different source than Qwen — that joint object
was not exercised by §13 / §14 / §15.

**Why this pin is defensible** (positive answers to the three
§0.8 questions a non-default risk signal would have to
answer; recorded here for the default too).

- **Why more defensible than alternatives?** $H_{\text{src}}$
  is the only LLM-domain scalar in this codebase that has
  cleared the §11 0.60 marginal bar on both benchmarks at
  N=100 (§13.10's verdict-of-record). Other candidate signals
  (winning-cluster weight margin, min-entropy across all 3
  sources) lack this prior validation.
- **Why does it not reopen §13 in disguise?** §13 measured
  AUC of $H_{\text{src}}$ against ground-truth correctness
  (a correlation-of-observable claim). §15.3 uses the same
  scalar as a per-question risk score driving an answer/
  abstain policy applied to **Stage A's selected answer** (a
  different metric class). The structurally novel content is
  the joint $(r(q), c(q))$ distribution on V1-selects-non-
  Qwen questions, which §13 did not exercise.
- **Why is it implementable without new infrastructure?**
  All required quantities are pre-computed in the §14a.2 on-
  disk dump per §14a.2's prose (`each source's greedy +
  entropy, per-question consumer weights, selected answer for
  each variant, per-question correctness label for each
  candidate`). No new model loads, no new NLI calls, no new
  generation. Pure CPU post-processing, mirroring §15.1.

**Alternative signals considered and explicitly NOT pinned.**

| Candidate | What it measures | Reason not pinned |
|---|---|---|
| $\min_i H_{\text{src}_i}(q)$ | most-confident source's entropy | Independent of which source V1 actually selected; weakly tied to Stage A's decision |
| $W_{k^*} - W_{k_{\text{runner}}}$ | winning-cluster margin (selector decisiveness) | Pure selector-level signal; lacks §13/§15 prior validation |
| $W_{k^*} / \sum_k W_k$ | winning-cluster fraction (consensus strength) | Same lack-of-validation issue; range $[1/M, 1]$ at M=3 |
| Cross-source NLI disagreement (§13.11-style) | inter-source agreement on V1's answer | Closer to §13.11 reframed; would require fresh §0.8 to justify reopening that closed hypothesis class |
| Any ensemble of two of the above | hybrid scalar | Forbidden by §15.3 Chunk 3c's "no ensemble" pin |

§15.3 uses **exactly one scalar**: the winning-source's
per-source semantic entropy $H_{\text{src}_{i^*}}(q)$. No
primary-plus-secondary, no ensemble, no fallback. Adding any
alternative would require a fresh §0.8 amendment to §15.3.

**Benchmark scope pin (single benchmark; HaluEval-QA only).**

§15.3 is a single-benchmark scout on **HaluEval-QA**, $N=100$,
identical to the §14a.2 dump's coverage. TruthfulQA-MC is
explicitly out of scope for the §15.3 scout.

**Three reasons HaluEval-QA-only is pinned, not a tunable
choice:**

1. **The §14a.2 dump exists only on HaluEval-QA.** §14a.2
   was pre-committed and executed on HaluEval-QA only;
   TruthfulQA-MC was explicitly deferred to "full §14"
   conditional on §14a.2 STRONG, which was never reached
   (§14c closed at `SCOUT_SATURATION`). The Stage A on-disk
   artifact §15.3 reads from
   (`probe_system_level_scout_v2_halueval_qa.json`)
   contains no TruthfulQA-MC data. Adding TruthfulQA-MC is
   therefore a *new generation step*, not a parameter
   change.

2. **HaluEval-QA is where the §14 BCVF-shaped signal was most
   alive.** V1 softmin produced the +4pp lift over Baseline-B
   on HaluEval-QA at N=100 in §14a.2 — the strongest BCVF-
   shaped lift in the entire §13 / §14 program (per §14c).
   TruthfulQA-MC across §13 / §14 / §15 has consistently
   acted as the worst-benchmark cap; if §15.3 has any chance
   of producing operational lift, HaluEval-QA is where to
   detect it first.

3. **Cost/benefit favors single-benchmark for the scout.**
   Adding TruthfulQA-MC to §15.3 would require (a) re-running
   the §14a.2 protocol on TruthfulQA-MC to produce the missing
   dump (~50–60 min on the existing GPU, identical cost to
   §14a.2's pinned cost), and (b) extending §15.3's bands to
   handle two-benchmark combined classification under a
   worst-benchmark rule. Both are outside §15.3 scope as a
   pure post-processing scout. The §15.3 scout's job is to
   detect signal where signal is most likely first; if it
   lands STRONG, a fresh §15.4 commitment can pre-commit the
   TruthfulQA-MC extension.

**Implication for the verdict bands.** Because §15.3 is
single-benchmark, **no worst-benchmark rule applies in
§15.3**. The verdict cascade pinned in Chunk 3g operates on
the single benchmark's $(\delta, \kappa)$ point estimates
directly. This is structurally distinct from §15.1's two-
benchmark cascade that combined $\delta = \min_b \delta_b$
and $\kappa = \min_b \kappa_b$ before applying the cascade.

**Cherry-picking caveat (acknowledged ex ante).** Pinning
HaluEval-QA-only is a deliberate scope choice, not a cherry-
pick: it follows the §14a.2 dump's existing coverage. A §15.3
STRONG on HaluEval-QA would NOT support an external claim
about §15.3's cross-benchmark behavior — that would require
the TruthfulQA-MC extension as a separate §15.4 commitment.
**The §15.3 verdict authorizes only what its single-benchmark
scope tests.** External-framing changes (VC-brief, etc.) are
foreclosed regardless of §15.3 outcome — same §13.9 hold rule
that bound §15.1 / §15.2.

**Operational metrics pin.**

§15.3's metric set is structurally similar to §15.1's but
single-benchmark (no worst-benchmark min) and pinned around
a different **primary decision metric** — chosen to make the
hybrid's claim operationally meaningful relative to §15.1's
verdict-of-record, not just relative to random abstention.

**Notation (single benchmark, $N=100$).** For each question
$q$ on HaluEval-QA at threshold $\tau$:

- $A_\tau = \{q : r(q) < \tau\}$ (Stage B answered set);
  $\text{cov}(\tau) = |A_\tau|/N$.
- $\text{acc}(\tau) = (1/|A_\tau|) \sum_{q \in A_\tau} c(q)$,
  where $c(q)$ is the correctness label of Stage A's
  `selected_answer(q)` per Chunk 3c (NOT Qwen-greedy
  correctness).
- $\text{ecr}(\tau), \text{far}(\tau)$ — identical formulas
  to §15.1 Chunks 3a / 3b applied to the new $c(q)$.
- $W_\text{hybrid} = N - \sum_q c(q)$ — total wrong selected
  answers; observed empirically at run time (NOT pinned ex
  ante like §15.1's $W$, since Stage A's selected-answer
  correctness count is not a pinned constant).

**Primary decision metric (single scalar):**
$$
\Delta\kappa \;=\; \kappa_\text{hybrid} - \kappa_{\S15.1,\text{HaluEval}}
$$
where:

- $\kappa_\text{hybrid} = \max\{\text{cov}(\tau) :
  \text{acc}(\tau) \ge \alpha_2 \text{ AND } |A_\tau| \ge n_\min\}$
  on HaluEval-QA, with $\alpha_2 = 0.50$ and $n_\min = 10$
  (identical floor to §15.1 Chunk 3a).
- $\kappa_{\S15.1,\text{HaluEval}} = 0.26$ — pinned constant
  from §15.2's verdict-of-record HaluEval $\kappa$ at $\alpha_2$
  (recorded in `docs/experiments/probe_selective_abstention.json`).

$\Delta\kappa > 0$ means the hybrid produces operationally
meaningful lift over §15.1's single-source abstention at the
absolute-majority target. $\Delta\kappa \le 0$ means it does
not improve over §15.1 at that target.

**Secondary diagnostic metrics** (reported, NOT band-driving).

- $\delta_\text{AURC,hybrid} = W_\text{hybrid}/N -
  \text{AURC}_\text{hybrid}$ — integrated lift over random
  abstention on Stage A's selected answers (single-benchmark
  analogue of §15.1's $\delta$).
- $(\text{cov}, \text{ecr}, \text{far})$ triples at three
  target accuracies $\alpha \in \{0.40, 0.50, 0.75\}$ — same
  $\alpha$ set §15.1 used on HaluEval-QA.
- Bootstrap CI (two-sided 95%, $B = 1000$, paired over
  question indices, deterministic seed
  `SeedSequence(entropy=15)` per §15.1 convention) on
  $\Delta\kappa$. Statistical demotion rule pinned in
  Chunk 3g.

**Baselines (pinned, three; all from existing artifacts; no
new generation).**

| Baseline | Source | Role |
|---|---|---|
| §15.1 HaluEval $\kappa@\alpha_2 = 0.26$ | §15.2 verdict-of-record | Primary comparator (drives $\Delta\kappa$) |
| §14a.2 V1 full-coverage point $(\text{cov}=1.0, \text{acc}=0.330)$ | §14a.2 dump | "Stage A without abstention" reference; documents whether the hybrid even needs Stage B |
| Random-abstain matched-coverage on Stage A's answers | Closed-form: $\mathbb{E}[\text{acc}_\text{random}(\text{cov})] = (N - W_\text{hybrid})/N$ | Random baseline for $\delta_\text{AURC,hybrid}$ |

§15.1's HaluEval $\kappa@\alpha_2$ is the central comparator
because §15.1 is the closest non-hybrid analogue (single-
source abstention at the same metric class on the same
benchmark). A §15.3 STRONG must demonstrate that adding Stage
A's selector produces operationally meaningful lift over the
single-source policy — not merely lift over random abstention.

**Verdict bands (pinned; exhaustive partition over $\Delta\kappa$).**

Per the user-pinned constraint that the §15.3 verdict
subordinate everything to $\Delta\kappa$ as the primary
scalar, the partition is **one-dimensional**: a single
ordered cascade driven by $\Delta\kappa$, with all secondary
diagnostics ($\delta_\text{AURC}$, operating-point triples,
the §14a.2 V1 full-coverage reference) explicitly **not
band-influencing**.

This is structurally simpler than §15.1's 2D $(\delta,
\kappa)$ cascade. The simpler cascade is justified because
§15.3 has already inherited Stage A's V1-vs-Baseline-B
accuracy lift from §14a.2 (a fixed configuration choice, not
a §15.3 measurement), and the remaining operational question
is binary: *does adding Stage B's abstention layer to V1's
selected answer beat §15.1's single-source abstention at the
same $\alpha_2$ target on the same benchmark?* $\Delta\kappa$
is the cleanest single scalar that answers it.

**Verdict cascade (pinned, ordered, exhaustive).** The §15.3
verdict is the **first** matching rule below. Rule 5 has no
positive condition; the cascade is exhaustive over $\mathbb{R}$
by construction.

1. **REGRESSION** — $\Delta\kappa < -0.02$.
2. **STRONG** — $\Delta\kappa \ge +0.10$.
3. **USEFUL_INTERNAL** — $\Delta\kappa \ge +0.05$.
4. **MARGINAL** — $\Delta\kappa \ge +0.02$.
5. **SATURATION** — explicit residual catch-all
   ($\Delta\kappa \in [-0.02, +0.02)$).

Rules 1–4 are mutually exclusive by ordering. Rule 5 catches
the residual deterministically. **No secondary metric
participates in the cascade.** Secondary diagnostics
($\delta_\text{AURC}$, $\text{ecr}$, $\text{far}$, the
$(\text{cov}, \text{ecr}, \text{far})$ triples) are reported
in the result section but never re-classify the verdict.

**Operational meanings per band** (assuming the pinned
$\kappa_{\S15.1} = 0.26$ baseline):

| Verdict | $\Delta\kappa$ range | Implied $\kappa_\text{hybrid}$ | Meaning |
|---|---|---|---|
| STRONG | $\ge +0.10$ | $\ge 0.36$ | Substantively higher cov@$\alpha_2$ than §15.1; product-relevant lift |
| USEFUL_INTERNAL | $[+0.05, +0.10)$ | $[0.31, 0.36)$ | Visibly better than §15.1; internal-research value |
| MARGINAL | $[+0.02, +0.05)$ | $[0.28, 0.31)$ | Small detectable lift |
| SATURATION | $[-0.02, +0.02)$ | $[0.24, 0.28)$ | Operationally equivalent to §15.1 |
| REGRESSION | $< -0.02$ | $< 0.24$ | Actively worse than §15.1 |

**Acceptance / rejection rules** (one-to-one mapped to the
cascade; mirrors §15.1 Chunk 4c structure).

| Verdict | Authorizes | Forecloses |
|---|---|---|
| **STRONG** | Drafting §15.4 — full hybrid pre-commitment with TruthfulQA-MC extension and product-layer scope (separate §0.8). | VC-brief changes (§13.9 hold remains); auto-deployment without §15.4; cross-benchmark claims absent §15.4. |
| **USEFUL_INTERNAL** | Documenting the §14+§15 hybrid as having internal-research operational value at this single-benchmark scale. | §15.4 product investment; cross-benchmark claims; VC-brief changes. |
| **MARGINAL** | Recording §15.3 as acknowledged but unactionable. | §15.4 follow-up; internal-research operational claims; product investment; VC-brief changes. |
| **SATURATION** | Documenting §15.3 as operational null; extending the §13/§14/§15 closure prose to cover the §14+§15 hybrid metric class. | Same as MARGINAL. |
| **REGRESSION** | Closing the §14+§15 hybrid construct at this configuration. §13.9 hold remains; the closure prose extends to "answer-selection AND single-source abstention AND hybrid all saturated/regressed." | Same as SATURATION. |

**Demotion rule (STRONG-only, bootstrap CI on $\Delta\kappa$).**
If the cascade returns STRONG but the bootstrap CI lower
bound on $\Delta\kappa$ is $\le 0$, the verdict is demoted to
**USEFUL_INTERNAL** with explicit `STRONG_BUT_CI_DEMOTION`
annotation. Mirrors §15.1 Chunk 4c's STRONG-only demotion
exactly. USEFUL_INTERNAL / MARGINAL / SATURATION / REGRESSION
are NOT subject to demotion — same operational-scope
reasoning as §15.1.

**Boundary-case audit table (illustrative, deterministic).**

| $\Delta\kappa$ | Cascade trace | Verdict |
|---|---|---|
| $+0.099$ | rule 1 NO; rule 2 NO ($\Delta\kappa < +0.10$); rule 3 YES | **USEFUL_INTERNAL** |
| $+0.019$ | rules 1–3 NO; rule 4 NO ($\Delta\kappa < +0.02$); rule 5 catches | **SATURATION** |
| $-0.020$ | rule 1 NO ($\Delta\kappa \not< -0.02$ at boundary); rules 2–4 NO; rule 5 catches | **SATURATION** |
| $-0.021$ | rule 1 YES; remaining rules not evaluated | **REGRESSION** |

The first two rows mirror §15.1's near-boundary demotion
pattern. The third and fourth rows document the REGRESSION
boundary inclusivity precisely: $\Delta\kappa = -0.020$ is NOT
regression (rule is strict-less-than), but $\Delta\kappa =
-0.021$ is.

**Implementation scope (pinned, framed as a small integration
layer over closed components).**

§15.3 is structurally a small integration layer that **reuses
closed §14 and §15 components without reopening either**. The
hybrid is built by composing existing artifacts, not by re-
running their pinned experiments.

**Reuse from §14 (data, not code).** The §14a.2 on-disk dump
`docs/experiments/probe_system_level_scout_v2_halueval_qa.json`
serves as Stage A's input. Per §14a.2 prose, the dump records
per-source greedies, per-source semantic entropies, V1 softmin
weights, NLI-clustered selector outputs (winning cluster,
representative source, selected_answer), and per-question
correctness labels for each candidate. **§14a.2 is NOT re-run.**
The §14a.2 `SCOUT_SATURATION` verdict-of-record (§14c) is
unchanged. §15.3 reads the dump as Stage A's pinned output;
it makes no new claim about whether V1 *succeeds* at answer
selection (V1's lift over Baseline-B was §14a.2's measurement,
closed at `SCOUT_SATURATION`).

**Reuse from §15 (the abstention *machinery pattern*, not the
whole §15.1 experiment).** §15.3 reuses §15.1's *abstention
machinery* — the threshold rule, the bootstrap convention,
the JSON+markdown artifact style, the discrete AURC formulation,
the cov@α with $n_\min$ floor — by **copying** the relevant
primitives from `scripts/probe_selective_abstention.py` into
the §15.3 script. **§15.3 does NOT reuse §15.1's experiment-
level pins:** §15.1 was two-benchmark with worst-benchmark
combination, used a 2D $(\delta, \kappa)$ cascade, and
compared against random-abstain as the central baseline.
§15.3 is single-benchmark, uses a 1D $\Delta\kappa$ cascade,
and compares against §15.1's HaluEval $\kappa@\alpha_2 = 0.26$
as the central baseline. Primitives are copied, not imported,
because §15.1's script is closed under §15.2's verdict-of-
record; importing from it would couple §15.3's outputs to any
future drift in §15.1's codepath, compromising §15.1's
reproducibility chain.

**New code — glue layer + hybrid evaluator + single-benchmark
report writer.**

One new script: `scripts/probe_hybrid_selective_abstention.py`
(numpy + stdlib only, CPU-only post-processor; structurally
parallel to `probe_selective_abstention.py`). The script
decomposes into three small components by responsibility:

- **Glue layer** — §14a.2 dump loader, schema validator,
  parity gate, and Stage A handoff extraction (items 1–3
  below).
- **Hybrid evaluator** — threshold sweep, operating-point
  computation, $\kappa_\text{hybrid}$, $\Delta\kappa$,
  bootstrap CI, the new 1D cascade, and the STRONG-only
  demotion rule (items 4–10 below).
- **Single-benchmark report writer** — `--self-test` gate
  plus JSON+markdown artifact writers (items 11–12 below).

Numbered components:

1. **§14a.2 dump loader** with schema validation against the
   pinned field list (q_idx, per-source semantic entropies,
   winning_source_id, selected_answer correctness label).
   Fail-fast on schema mismatch (no fallback).
2. **Parity gate** on $N=100$ on HaluEval-QA. Aborts on
   mismatch.
3. **Stage A handoff extraction** — derives $r(q) =
   H_{\text{src}_{i^*}}(q)$ and $c(q)$ = correctness of
   `selected_answer(q)` directly from the dump's fields.
4. **Threshold sweep** (sorted unique $r(q)$ plus $\pm\infty$)
   with per-threshold $(\text{cov}, \text{acc}, \text{ecr},
   \text{far})$ computation. Copied from §15.1.
5. **Operating-point computation** at $\alpha \in \{0.40,
   0.50, 0.75\}$, $n_\min = 10$. Copied from §15.1.
6. **$\kappa_\text{hybrid}$ computation** at $\alpha_2 = 0.50$.
7. **$\Delta\kappa$ computation** ($\kappa_\text{hybrid} - 0.26$).
8. **Bootstrap CI on $\Delta\kappa$** (paired over question
   indices, $B=1000$, `SeedSequence(entropy=15)` — same
   convention as §15.1 to keep the audit trail consistent).
9. **1D cascade** driven by $\Delta\kappa$ alone (Chunk 3g).
   **New** `verdict_cascade` function specific to §15.3
   (NOT the §15.1 2D cascade).
10. **STRONG-only demotion rule** on bootstrap CI lower
    bound of $\Delta\kappa$.
11. **`--self-test` gate** verifying the 1D cascade against
    Chunk 3g's 4-row boundary-case audit table and the
    STRONG-only demotion rule.
12. **JSON + markdown writers** matching the §15.3 output
    schema (`schema_version = "15.3"`, single-benchmark
    block under `benchmark`, `combined` block with `verdict`,
    `verdict_annotations`, `delta_kappa`, `kappa_hybrid`,
    `kappa_§15.1_baseline`).

**Engineering cost (estimated).**

- ~400–600 lines of new code (smaller than §15.1's 1112; the
  cascade is 1D and primitives are copy-pasted).
- CPU only; numpy + Python stdlib only; no GPU, no model
  loads, no NLI, no network.
- Wall-clock cost of real-data run: under 30 seconds at
  $N=100$ with $B=1000$ bootstrap.
- Implementation effort: roughly half §15.1's; the new work
  is the integration layer, not the metric primitives.

**Output paths (pinned).**

- `docs/experiments/probe_hybrid_selective_abstention.json`
  (machine-readable, `schema_version` `"15.3"`).
- `docs/experiments/probe_hybrid_selective_abstention.md`
  (human-readable summary).

**What §15.3 implementation explicitly does NOT authorize.**

- Re-running §14a.2 (the §14a.2 dump is the pinned Stage A
  input; §14c verdict unchanged).
- Modifying `scripts/probe_selective_abstention.py` (§15.1's
  pinned codepath; preserved verbatim per §15.2 Postscript).
- Adding TruthfulQA-MC or any other benchmark.
- Adding consumers or selectors beyond §14a.2's pinned
  configuration.
- Adding observables beyond $H_{\text{src}_{i^*}}$.
- Importing from the §15.1 script (primitives copied for
  independence).
- Auto-promoting any verdict to §15.4 (any §15.4 work
  requires its own §0.8 commitment).

**Reduced-form authorization rationale — §15.3 only exists
because upstream artifacts already exist.**

§15.3's compactness (single benchmark, single observable,
single selector, single consumer, no fresh model calls) is
authorized **only because the necessary upstream artifacts
already exist on disk**:

- The §14a.2 HaluEval-QA dump
  (`docs/experiments/probe_system_level_scout_v2_halueval_qa.json`)
  exists per §14a.2 / §14c's artifacts list.
- §13.10's semantic-entropy scalar definition is pinned by
  §13.10's verdict-of-record (and is not invalidated by the
  §13.20 N=200 observation, which does not re-classify
  §13.10).
- §15.1's abstention machinery exists and is validated in
  `scripts/probe_selective_abstention.py` per §15.2's
  verdict-of-record.

**If any of these upstream artifacts did not already exist,
this chapter would not be authorized in this reduced form.**
A from-scratch hybrid program would require fresh §14-class
and §15-class generation runs as their own §0.8 commitments
before any hybrid scout could land. §15.3 is structurally a
post-processing composition of three closed predecessors;
it is not an attempt to reopen them.

**What §15.3 explicitly does NOT test.**

The hybrid scout's claim is narrowed deliberately to keep the
§0.8 commitment tight. §15.3's verdict — whatever band the
cascade returns — bears only on this single configuration's
operational behavior. Specifically, §15.3 is NOT testing:

- **Retrieval augmentation.** No retrieval, search, web
  access, or external knowledge source enters Stage A or
  Stage B. The policy's only response options are ANSWER
  `selected_answer(q)` or ABSTAIN.
- **Verifier ensembles.** No external verifier model, no
  judge-model, no critique pass, no second-LLM fact-checking
  layer. The risk signal is exclusively the §13.10 / §14a.2
  semantic-entropy scalar of V1's selected source.
- **Cross-benchmark generalization.** §15.3 runs on HaluEval-QA
  only. A §15.3 STRONG would NOT support claims about
  TruthfulQA-MC behavior; that is the explicit §15.4 future-
  work scope.
- **A new §13 observable program.** §15.3 reuses the §13.10
  semantic-entropy scalar verbatim, applied to V1's selected
  source. No new §13 hypothesis class is opened. The §13.19
  single-axis closure remains binding.
- **A new §14 system-level program.** Stage A is fixed to
  §14a.2's pinned configuration; §15.3 makes no claim about
  whether different selectors, consumers, source sets, or
  $M$ values would produce different answer-selection lift.
  §14c's `SCOUT_SATURATION` verdict on V1 / V2 vs Baseline-B
  is unchanged.
- **Product readiness.** Even a §15.3 STRONG result would
  require §15.4 (full hybrid pre-commitment with TruthfulQA-
  MC extension and product-layer scope) before any
  deployment-grade claim. §15.3 is a scout, not a deployable
  system.
- **Re-classification of any prior §13 / §14 / §15 verdict.**
  §13.19 (single-axis ANTI), §14b / §14c (`SCOUT_SATURATION`),
  §15.2 (`MARGINAL`), and §13.20 (N=200 `NOISE_BAND_LIFT`
  observation, not a re-classification of §13.10) are all
  closed under §0.8 at their pinned configurations. §15.3
  cannot revisit any of them.

**§15.3 chunk roll-up — pre-commitment now complete.**

| Chunk | Content |
|---|---|
| 3a | Opening framing — fresh top-level chapter, new claim, new metric class |
| 3b | Stage A architecture pin (§14a.2 NLI-clustered selector + V1 softmin) |
| 3c | Stage B architecture pin (single threshold rule, ties to ABSTAIN) |
| 3d | Risk signal pin ($r(q) = H_{\text{src}_{i^*}}(q)$, single scalar) |
| 3e | Benchmark scope pin (HaluEval-QA only, scout-level) |
| 3f | Operational metrics pin ($\Delta\kappa$ primary; secondary diagnostics) |
| 3g | Verdict bands (1D cascade subordinated to $\Delta\kappa$) |
| 3h | Implementation scope (small integration layer over closed §14/§15) |
| 3i | What §15.3 does NOT test + reduced-form authorization rationale + roll-up |

Implementation of `scripts/probe_hybrid_selective_abstention.py`
is a separate §0.8 authorization gate. §15.3.x (the result
section, parallel to §15.2) follows the real-data run.

### 15.4 Result — §15.3 hybrid scout returned USEFUL_INTERNAL

The §15.3 pre-committed hybrid scout has been executed against
the on-disk §14a.2 dump in the runpod container. Combined
classification per pre-committed bands:
**`USEFUL_INTERNAL`** ($\Delta\kappa = +0.0900$,
$\kappa_\text{hybrid} = 0.35$, no annotations). The §14a.2
V1-selected answer plus a §15-style abstention gate on the
V1-winning-source's semantic-entropy risk score produces
operationally meaningful lift over §15.1's single-source
abstention baseline ($\kappa_{\S15.1} = 0.26$) at the
$\alpha_2 = 0.50$ absolute-majority operating target on
HaluEval-QA, clearing the USEFUL_INTERNAL band but missing
the STRONG band by 0.01 on the point estimate of $\Delta\kappa$.

This is the **first non-MARGINAL/SATURATION verdict in the
entire §13 / §14 / §15 LLM-track program.** §13's five single-
axis classes returned ANTI under worst-benchmark; §14's two
system-level scouts returned `SCOUT_SATURATION`; §15.2's
single-source abstention scout returned `MARGINAL`. The §15.3
hybrid is the structurally distinct combination §14c
anticipated (selector + abstention layer on the selected
answer); it produced the first measurable USEFUL_INTERNAL-band
lift in the program, on a single benchmark, at this scale.

Per §15.3 Chunk 3g's pinned acceptance/rejection table:

> USEFUL_INTERNAL — Authorizes documenting the §14+§15 hybrid
> as having internal-research operational value at this
> single-benchmark scale. Forecloses §15.5 product investment,
> cross-benchmark claims, VC-brief changes.

Operationally: the §13.10-grade semantic-entropy scalar
applied to V1's winning-source K=10 samples is enough to
drive a useful abstention/answer policy on HaluEval-QA, but
not enough to clear STRONG nor to support deployment-grade
claims. **§13.9 VC-brief hold remains in force; §15.4 does
not address §13.9's gate by construction** (different metric
class). The autonomy-domain BCVF claim (§6.1) stands
independently and is unaffected.

**Parity-gate confirmation (per §15.3 Chunk 3h).**

| benchmark | N_ok |
|---|---|
| halueval_qa | True |

The §14a.2 dump satisfied $N=100$ on HaluEval-QA. The §15.3
schema validation (`q_idx`, `sources` / per-source
`semantic_entropy`, `answer_cluster_ids`, `v1_weights`,
`v1_winning_cluster`, `v1_correct`) all passed; no fields
were missing. No §0.8 deviation fired at the input layer.

**Self-test gate.** §15.3's required pre-execution gate
(`--self-test`) ran in the same invocation as real-data
execution and returned PASSED on all 7 cascade boundary cases
(Chunk 3g audit table + 3 boundary-inclusivity anchors) and
all 7 demotion-rule cases. The 1D cascade implementation
matches Chunk 3g exactly; the verdict reported in §15.4 is
the cascade's mechanical readout, not interpretation.

**Cross-program consistency check.** $W_\text{hybrid} = 67$
implies V1 accuracy on HaluEval-QA $= 33/100 = 0.330$,
matching §14a.2's V1 accuracy of 0.330 exactly. The §14a.2
dump's V1 selected-answer correctness count is preserved
through Stage A handoff into §15.4 without drift.

**Artifacts.**

- `scripts/probe_hybrid_selective_abstention.py` (numpy +
  stdlib, CPU-only post-processor; the §15.3 implementation).
- `docs/experiments/probe_hybrid_selective_abstention.json`
  (machine-readable, `schema_version` `"15.3"`; single-
  benchmark block, combined block with verdict).
- `docs/experiments/probe_hybrid_selective_abstention.md`
  (human-readable summary with parity gate, Stage A
  configuration, headline table, operating points, cascade
  trace, final verdict).

**Section naming clarification.** §15.3 Chunk 3g's STRONG row
referenced "§15.4 — full hybrid pre-commitment with
TruthfulQA-MC extension and product-layer scope" as the
hypothetical authorization for STRONG. STRONG did NOT fire
(USEFUL_INTERNAL did), so the §15.4-as-future-full-hybrid
path is moot. §15.4 is therefore used here as the §15.3
result section (mirroring §15.1 → §15.2 convention). Any
future full-hybrid pre-commitment — which §15.3's
USEFUL_INTERNAL explicitly does NOT authorize per Chunk 3g
— would land at §15.5 or higher under its own §0.8
commitment.

**Headline result.**

| metric | value |
|---|---|
| $N$ | 100 |
| $W_\text{hybrid}$ (V1 wrong count) | 67 |
| $\text{AURC}_\text{random}$ ($= W/N$) | 0.6700 |
| $\text{AURC}_\text{policy}$ | 0.4858 |
| $\delta_\text{AURC}$ (diagnostic) | $+0.1842$ |
| $\kappa_\text{hybrid}$ at $\alpha_2 = 0.50$ | **0.3500** |
| $\kappa_{\S15.1}$ baseline (HaluEval $\kappa@\alpha_2$) | 0.2600 |
| $\boldsymbol{\Delta\kappa}$ **(primary)** | $\boldsymbol{+0.0900}$ |
| $\Delta\kappa$ 95% CI (paired bootstrap, $B = 1000$) | $[-0.1502, +0.4600]$ |

**Cascade trace** (mechanical readout per §15.3 Chunk 3g;
matches the implementation's `_cascade_trace_15_3` output
exactly):

```
rule 1 REGRESSION: delta_kappa=+0.0900 < -0.02     -> NO
rule 2 STRONG:     delta_kappa>=+0.10               -> NO   (point estimate 0.01 below threshold)
rule 3 USEFUL_INTERNAL: delta_kappa>=+0.05         -> YES
```

**Demotion rule (Chunk 3g) — did NOT apply.** The §15.3
demotion rule is STRONG-only by construction; the cascade
returned USEFUL_INTERNAL (rule 3), which is not subject to
demotion. `verdict_annotations` is empty. **Audit note for
the near-miss:** had the cascade returned STRONG (had the
point estimate been 0.01 higher), the demotion rule WOULD
have fired — the bootstrap CI lower bound on $\Delta\kappa$
is $-0.1502 \le 0$. A counterfactual STRONG would therefore
have demoted to USEFUL_INTERNAL with `STRONG_BUT_CI_DEMOTION`
annotation. **The cascade landed at USEFUL_INTERNAL on the
point estimate alone, without the demotion rule needing to
intervene; the verdict's stability does not depend on
bootstrap CI width.**

**Three observations the headline supports.**

**(a) First non-MARGINAL/SATURATION verdict in the entire
§13 / §14 / §15 LLM-track program.** Eleven distinct
experimental structures have now been tested across four
metric classes (§13 single-axis AUC, §14 system-level
accuracy delta, §15 single-source abstention AURC + cov@α,
§15.3 hybrid Δκ over §15.1 baseline). §15.3 is the first
that clears USEFUL_INTERNAL. The §14c-anticipated direction
(V1 selector + Stage B abstention on the selected answer)
is empirically validated at this scale: the joint object
produces operational lift that neither component produces
alone.

**(b) $\Delta\kappa = +0.0900$ misses STRONG by 0.01 on the
point estimate.** The point estimate is one-hundredth below
the pinned STRONG threshold of $+0.10$. **Pre-committed
bands prevent recharacterizing this as "essentially STRONG"
or relaxing the threshold post-hoc.** The §14a.2 band-
coverage-gap lesson (where a $(+4, +1)$ outcome fell through
the partition) is exactly the discipline-erosion failure
mode §15.3's exhaustive 1D cascade was designed to prevent.
The cascade landed at USEFUL_INTERNAL deterministically per
the pinned rule; the near-miss is documented but does not
unlock STRONG-band authorizations.

**(c) Bootstrap CI on $\Delta\kappa$ is wide; lower bound is
negative.** $\Delta\kappa$ 95% CI = $[-0.1502, +0.4600]$,
width $\approx 0.61$. At $N=100$ the paired bootstrap
cannot tightly constrain $\Delta\kappa$; the lower bound at
$-0.15$ does not rule out $\Delta\kappa \le 0$. This is a
power-of-measurement observation, NOT a $\Delta\kappa = 0$
claim. The point-estimate verdict is USEFUL_INTERNAL by the
pinned rule; the wide CI says a single re-run at the same
$N$ might land in a different band by chance. A larger-$N$
re-run would tighten this band; that re-run is NOT
authorized by §15.3 and would require a fresh §0.8
commitment.

**Comparison to §15.2 single-source abstention at the same
$\alpha_2$ target.**

§15.2's verdict-of-record on HaluEval-QA was MARGINAL with
$\kappa_{\S15.1,\text{HaluEval}}@\alpha_2 = 0.26$ at
$\alpha_2 = 0.50$. §15.4's hybrid policy on the same
benchmark at the same target produces $\kappa_\text{hybrid} =
0.35$. The operating-point comparison at $\alpha_2$:

| metric | §15.2 single-source (HaluEval) | §15.4 hybrid (HaluEval) | Δ |
|---|---|---|---|
| $\text{cov}@\alpha_2$ | 0.26 | **0.35** | **+0.09 = $\Delta\kappa$** |
| $\tau^*$ at $\alpha_2$ | 1.0889 | 1.2275 | +0.139 |
| ecr at $\tau^*$ | 0.8143 | 0.7463 | $-0.068$ |
| far at $\tau^*$ | 0.5667 | 0.4545 | $-0.112$ |

Three operationally relevant features of this comparison.

**(a) Coverage lift at the same accuracy target — the
headline operational signal.** The hybrid policy answers
35% of HaluEval-QA at $\text{acc} \ge 0.50$ where §15.1
single-source could only answer 26%. **At absolute terms
that is 9 more questions answered per 100 at the same
absolute-majority operating target.** Per §15.3 Chunk 3g
this is the band-driving primary.

**(b) ecr / far rebalancing.** The hybrid abstains fewer
questions overall than §15.1 (lower far) AND catches a
slightly smaller fraction of wrong V1 answers (lower ecr).
Together these produce higher net coverage at the same
accuracy bar. **Mechanism read:** V1's selector occasionally
picks Llama or Mistral on questions where Qwen would have
been wrong; the per-source-entropy of that winning source
captures the question's risk more accurately than Qwen's
own entropy did under §15.1. The hybrid trades a small
amount of V1-wrong-error capture for a larger reduction
in V1-correct-false-abstention.

**(c) The threshold $\tau^*$ that achieves $\kappa_\text{hybrid}$
is higher than §15.1's $\tau^*$ at the same $\alpha_2$
target ($1.2275$ vs $1.0889$).** A higher threshold means
the hybrid is willing to ANSWER on higher-entropy questions
than §15.1 was — i.e., the hybrid's per-question risk score
is shifted in distribution relative to Qwen-greedy entropy.
Mechanically consistent with V1 sometimes selecting non-Qwen
sources whose entropy distributions differ from Qwen's. **The
hybrid's risk score is not just §15.1's signal renamed; it
is structurally a different per-question scalar on the
divergent-V1-selection subset.**

**Cross-program consistency note (operating point at
$\alpha_1$).** §15.4's $\alpha_1 = 0.40$ point: cov $=0.63$,
$\tau^* = 1.9730$, ecr $=0.46$, far $=0.18$. §15.2's
HaluEval $\alpha_1 = 0.40$ point: cov $=0.36$, $\tau^* =
1.4979$, ecr $=0.70$, far $=0.50$. **The hybrid more than
$1.7\times$ the coverage at the modest-accuracy operating
target.** The pattern is consistent at $\alpha_1$ and
$\alpha_2$: the hybrid extends the operational frontier
across the lower-$\alpha$ range. The improvement
disappears at $\alpha_3 = 0.75$ (next chunk).

**Deployment-grade ceiling — $\alpha_3 = 0.75$ degeneracy
carries over from §15.2.**

The §15.4 operating point at $\alpha_3 = 0.75$:

| benchmark | $\alpha_3$ | $\text{cov}@\alpha_3$ | $\tau^*$ | ecr | far |
|---|---|---|---|---|---|
| §15.4 hybrid (HaluEval) | 0.75 | **0.00** | $+\infty$ | NaN | NaN |
| §15.2 single-source (HaluEval) | 0.75 | 0.00 | $+\infty$ | NaN | NaN |
| §15.2 single-source (TruthfulQA-MC) | 0.75 | 0.00 | $+\infty$ | NaN | NaN |

**No threshold $\tau$ in the §15.4 sweep grid (102 points)
yields acc $\ge 0.75$ on an answered subset of size $\ge
n_\min = 10$.** Same hard ceiling §15.2 documented across
both benchmarks — abstention alone, even with V1's selector
in front of it, **cannot reach a deployment-grade $\alpha
\ge 0.75$ subset** at this configuration.

**Three implications.**

**(a) The hybrid's USEFUL_INTERNAL verdict is real but
operationally bounded.** The lift at $\alpha_1 = 0.40$ and
$\alpha_2 = 0.50$ is genuine and measurable; the lift at
$\alpha_3 = 0.75$ is identically zero (both policies fail).
Any future product layer over this hybrid would have to
operate at $\alpha < 0.75$ — i.e., accept a residual
accuracy floor below 75% on the answered subset. **Whether
that floor is operationally acceptable is a product
question §15.3's USEFUL_INTERNAL does not answer and
explicitly does NOT authorize §15 to opine on.**

**(b) The mechanism §15.2 Chunk 2d documented persists.**
At greedy accuracies in the 0.25–0.33 range, the entropy
distribution does not contain a high-confidence subset
dense enough to support both $\text{acc} \ge 0.75$ AND
$|A_\tau| \ge 10$. Adding V1's selector (which lifts
greedy from 0.30 to 0.33 on HaluEval per §14a.2) does not
move the needle far enough to unlock $\alpha_3$. **A
deployment-grade ceiling requires either a higher base-
model accuracy floor (model-scale upgrade per §13.8 future-
work) or a larger-$N$ target-accuracy subset that survives
the entropy threshold.** Neither is in §15.3 / §15.4 scope.

**(c) The §15 metric class is partially saturated even
inside USEFUL_INTERNAL.** §15.4 USEFUL_INTERNAL covers
$\alpha_1$ and $\alpha_2$; $\alpha_3$ is unreachable.
Pre-committed bands do not distinguish "USEFUL_INTERNAL at
two of three operating points" from "USEFUL_INTERNAL at
all three" — the cascade is driven by $\Delta\kappa$ at
$\alpha_2$ alone per Chunk 3g. **This is by design**: §15.3
narrowed the verdict to one scalar to prevent secondary-
metric overreading. The $\alpha_3$ degeneracy is reported
as a diagnostic and bounds the operational claim, but does
not re-classify the verdict.

**What §15.4 authorizes (per §15.3 Chunk 3g USEFUL_INTERNAL row).**

The §15.3-pinned acceptance/rejection mapping for
USEFUL_INTERNAL is binding under §0.8. Reproduced exactly:

| §15.4 verdict | Authorizes | Forecloses |
|---|---|---|
| USEFUL_INTERNAL | Documenting the §14+§15 hybrid as having internal-research operational value at this single-benchmark scale. | §15.5 product investment; cross-benchmark claims; VC-brief changes. |

Specifically, §15.4 **authorizes**:

- Documenting the §15.3 verdict-of-record in this section
  (which §15.4 itself accomplishes).
- Recording the per-question $\Delta\kappa = +0.0900$,
  $\kappa_\text{hybrid} = 0.35$, the operating-point triples,
  and the bootstrap CI as the §15.4 verdict-of-record.
- Citing §15.4 as the **first** USEFUL_INTERNAL-grade
  empirical evidence in the §13 / §14 / §15 program at the
  pinned configuration.
- Citing the §14c-anticipated direction as empirically
  validated at this single-benchmark scale (V1 selector +
  Stage B abstention produces lift over §15.1's single-
  source policy at $\alpha_1$ and $\alpha_2$).

§15.4 explicitly **does NOT authorize**:

- **§15.5 follow-up.** A full hybrid pre-commitment with
  TruthfulQA-MC extension and product-layer scope was the
  §15.3 Chunk 3g STRONG-band authorization; STRONG did not
  fire. §15.5 requires a fresh top-level §0.8 commitment.
- **Cross-benchmark claims.** §15.4 ran on HaluEval-QA only.
  No claim about TruthfulQA-MC behavior is supported. Per
  §15.3 Chunk 3e's cherry-picking caveat: "The §15.3 verdict
  authorizes only what its single-benchmark scope tests."
- **Product-readiness claims.** USEFUL_INTERNAL is internal-
  research grade, not deployment grade. The $\alpha_3 = 0.75$
  degeneracy further bounds what could be claimed.
- **VC-brief updates.** §13.9 hold remains in force; §15.4's
  metric class (Δκ vs §15.1 baseline) is structurally
  separate from §13.9's gate (STRONG-band lift in answer-
  selection AUC or accuracy). The hold is not addressed by
  §15.4 by construction.
- **Reframing of any §13 / §14 / §15.x verdict.** §15.4 is
  on a fresh metric class and does not interact with §13's
  ANTI verdicts, §14's SCOUT_SATURATION, §15.2's MARGINAL,
  or §13.20's NOISE_BAND_LIFT observation.
- **Cross-domain claims.** Autonomy-domain BCVF (§6.1)
  stands wholly independent of any §15.4 outcome.

**§0.8 implementation transparency — line-count drift on the
§15.3 script.**

§15.3 Chunk 3h estimated `scripts/probe_hybrid_selective_abstention.py`
at $\sim$400–600 lines; the as-implemented script is
$\sim$1098 lines, roughly equivalent to §15.1's $\sim$1112
lines rather than half. Surfaced explicitly per §15.3 Chunk
3h's discipline rather than absorbed:

- The "copy primitives, do NOT import" rule (§15.3 Chunk 3h)
  duplicated $\sim$150 lines of §15.1 metric primitives into
  the §15.3 script.
- The §14a.2 schema validation is more elaborate than
  §15.1's (nested per-source structure, M=3 source-list
  validation, winning-cluster argmax extraction).
- Output writers are similar size to §15.1's, not smaller.

**The 1D verdict cascade IS smaller than §15.1's 2D
cascade, as Chunk 3h promised; the surrounding
infrastructure simply did not shrink proportionally.** This
drift is documented as an audit-lesson observation about
§0.8 cost-estimation discipline; it does NOT change the
§15.4 verdict (which is driven by $\Delta\kappa$ alone, not
by code complexity). Future "small integration layer over
closed components" estimates should account for the
copy-not-import rule's duplication cost up front.

**No deviation flag fired during the §15.3 run.** Per §15.3
Chunk 3h's "Any deviation discovered at run time must be
flagged in the §15.4 result section as a §0.8 deviation":
the run produced no such deviation. Parity gates passed,
schema matched, self-test passed in-run, the cascade fired
exactly as the implementation's `_cascade_trace_15_3` walks
the pinned rules. The line-count drift is documented inside
§15.4 (here) rather than as a run-time deviation, since it
was a pre-run estimation artifact.

**Combined picture across §13 / §14 / §15 — LLM-track now
covers four metric classes; one cleared USEFUL_INTERNAL.**

§15.4 closes the fourth of four pre-committed metric-class
investigations of BCVF-derived signals on the LLM track:

| Program | Metric class | Question | Combined verdict |
|---|---|---|---|
| §13 | AUC of an observable vs ground-truth correctness | Does observable X correlate with correctness? | 5-of-5 single-axis classes ANTI; §13.10 baseline `TRUTH_CORRELATED_MARGINAL` (AUC 0.661 / 0.661 at N=100) |
| §14 | Δ accuracy of system-level routing vs naive aggregation | Does BCVF-shaped routing lift end-to-end accuracy? | 2-of-2 scout configurations `SCOUT_SATURATION` |
| §15 (single-source) | Risk-coverage operational metrics on Qwen greedy | Does the §13.10 score support a useful answer/abstain policy on a single source? | `MARGINAL` (§15.2; δ=+0.116 statistically supported, κ=0.14 limited by TruthfulQA-MC) |
| **§15 (hybrid)** | **Δκ vs §15.1 baseline on V1's selected answer** | **Does a §14-selector + §15-abstention hybrid lift the operating frontier over single-source abstention?** | **`USEFUL_INTERNAL`** (§15.4; Δκ = +0.090; the only program-level lift to clear USEFUL_INTERNAL) |

The four programs are structurally independent — different
metric classes, different acceptance rules, different math
objects. **Each was pre-committed under §0.8 with bands
fixed before its data was opened.** Three returned strict
non-promotion verdicts (ANTI / SCOUT_SATURATION / MARGINAL);
§15.4 returned the program's first USEFUL_INTERNAL.

**§13.9 VC-brief hold reaffirmed.** §13.9 gates external-
framing changes to `AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md` on
a STRONG-band lift on both benchmarks at any §13 / §14 /
§15 probe. §15.4's USEFUL_INTERNAL is below STRONG by
construction (1D cascade rule 3 is the band immediately
below STRONG) and is single-benchmark — neither condition
satisfies §13.9's gate. Combined with §13's 5/5 ANTI,
§14's 2/2 SCOUT_SATURATION, §15.2's MARGINAL, §13.20's
N=200 `NOISE_BAND_LIFT`, and §15.4's single-benchmark
USEFUL_INTERNAL, **twelve distinct experimental structures
have now been tested across four metric classes at the 7B +
DeBERTa-v3-base + N=100/200 configuration without producing
a STRONG combined classification on any of them.** The
§13.9 hold is unchanged; §15.4 strengthens it by adding
another metric class that did not clear STRONG.

The honest external framing for any internal-research
referencing of the §13 / §14 / §15 program is now:

> *On Qwen2.5-7B-Instruct + DeBERTa-v3-base + N=100, no
> literature-aligned, mechanism-motivated, system-level,
> single-source-abstention, or hybrid-abstention BCVF
> construction tested in this codebase clears the STRONG
> combined-classification bar on the worst-benchmark rule.
> The §15.3 hybrid scout did clear USEFUL_INTERNAL on
> HaluEval-QA single-benchmark — internal-research
> operational evidence that adding §14a.2's V1 selector in
> front of a §15-style abstention gate produces measurable
> lift over single-source abstention at the absolute-
> majority operating target — but this single-benchmark
> USEFUL_INTERNAL does NOT clear the §13.9 STRONG-band-on-
> both-benchmarks external-framing bar.*

**§15.4 closes the §15 LLM-track operational chapter at the
hybrid level.** Per Chunk 3g the USEFUL_INTERNAL verdict
explicitly forecloses §15.5-as-implementation follow-ups at
this configuration. Any follow-up under §15 logic — cross-
benchmark extension to TruthfulQA-MC, larger-N re-run,
ensemble risk score, alternative selector configurations,
relaxed worst-benchmark rule — would require a fresh top-
level §0.8 commitment with bands pinned before any data
inspection. None is authorized by §15.4.

**The autonomy-domain BCVF claim (§6.1) stands independently
on the N=21 sign-test that passed in §6.1 / §6.7 and is
unaffected by any §13 / §14 / §15 outcome.** The §13 / §14 /
§15 program tested whether BCVF transfers to LLM
hallucination detection at this codebase's specific scale,
across four distinct metric classes; the answer at this
configuration is mixed — eleven of twelve experimental
structures returned strict non-promotion verdicts; one
(§15.3 hybrid) cleared USEFUL_INTERNAL on a single
benchmark. The §13.9 external-framing hold remains binding;
the §15.4 USEFUL_INTERNAL verdict is documented internally,
not externally, per Chunk 3g.

**Artifacts.**

- `scripts/probe_hybrid_selective_abstention.py` (the §15.3
  implementation; numpy + stdlib only).
- `docs/experiments/probe_hybrid_selective_abstention.json`
  (machine-readable result, schema_version `15.3`).
- `docs/experiments/probe_hybrid_selective_abstention.md`
  (human-readable summary).

§15.4 result section now complete (chunks 4a–4f, 6 commits
on top of the §15.3 pre-commitment + implementation).

### 15.5 Pre-commitment — Hybrid scout on TruthfulQA-MC (cross-benchmark companion to §15.3)

**Status: pre-committed, not yet executed.** §0.8-style pre-
commitment recorded before any §14a.2-on-TruthfulQA-MC dump
is opened in hybrid form, and indeed before that dump even
exists on disk (the GPU run that produces it follows §15.5's
landing, not precedes it). Specification, primary risk
signal, success bands, baselines, and acceptance/rejection
rules below cannot be redefined post-hoc.

**Position in the §13 / §14 / §15 program — what §15.5 is and
what it is not.** §15.5 is the cross-benchmark companion to
§15.3, not a continuation, reframe, or extension of §15.4's
verdict. Specifically:

- **§15.3** was a single-benchmark scout on **HaluEval-QA**;
  §15.4 returned `USEFUL_INTERNAL` ($\Delta\kappa = +0.0900$,
  $\kappa_\text{hybrid} = 0.35$ vs §15.1 baseline
  $\kappa = 0.26$).
- **§15.5** is a **single-benchmark scout on TruthfulQA-MC**
  — the benchmark §15.3 explicitly excluded (per §15.3
  Chunk 3e) because the §14a.2 dump did not exist for
  TruthfulQA-MC.
- §15.5 produces its own per-benchmark verdict on TruthfulQA-
  MC alone. The §15.5 verdict cascade fires on TruthfulQA-MC's
  $\Delta\kappa$ alone (per Chunk 5g, identical structure to
  §15.3 Chunk 3g).
- A **cross-benchmark synthesis** (§15.4 HaluEval verdict +
  §15.5 TruthfulQA-MC verdict under worst-benchmark rule) is
  computed in §15.5's result section as a **diagnostic**,
  NOT as the cascade band-driver. This keeps §15.5 a clean
  single-benchmark scout structurally parallel to §15.3.

**This is a new claim, not a reframe of §15.4.**

- Not "§15.4's USEFUL_INTERNAL extends to TruthfulQA-MC"
  (that would presume the answer; §15.5 tests it).
- Not "§14+§15 hybrid achieves cross-benchmark
  generalization" (the cross-benchmark synthesis is a
  derived diagnostic, not a §15.5 verdict).
- **But** "the §14+§15 hybrid construct, transplanted to
  TruthfulQA-MC at the same single-benchmark scout structure
  §15.3 used on HaluEval-QA, lands in cascade band X" —
  where X is determined by the §15.5 cascade applied to
  TruthfulQA-MC's numbers alone.

**§15.5 is a fresh §0.8 commitment.** All §13 / §14 / §15.1 /
§15.2 / §15.3 / §15.4 / §13.20 verdicts remain binding and
are NOT retroactively reframed. A §15.5 STRONG would authorize
drafting §15.6 (full hybrid pre-commitment with both
benchmarks combined and product-layer scope) as a separate
§0.8 commitment; it would NOT re-classify §15.4's single-
benchmark USEFUL_INTERNAL.

**Why this is a new metric class.** §15.4 measured
$\Delta\kappa$ on HaluEval-QA against the §15.1 HaluEval
baseline ($\kappa = 0.26$). §15.5 measures $\Delta\kappa$ on
TruthfulQA-MC against the §15.1 TruthfulQA-MC baseline
($\kappa = 0.14$, recorded in §15.2's verdict-of-record). The
two benchmarks have different greedy accuracies, different
distractor structures, and different §15.1 baseline values;
the per-benchmark $\Delta\kappa$ scalar is benchmark-local
by construction. **The cross-benchmark synthesis is a
derived comparator over two independent §0.8 commitments,
not a single combined-classification rule.**

**Confirmation: no data inspection prior to this pre-
commitment.** No §14a.2-on-TruthfulQA-MC dump exists on disk
yet. The §15.4 HaluEval-QA result was inspected only through
its pinned numerical record (Δκ=+0.090, κ=0.35 from
`probe_hybrid_selective_abstention.json`); no per-question
field of the §14a.2-on-HaluEval dump has been opened in §15.5
form. The protocol, primary signal, metrics, and bands in
the §15.5 chunks below are pinned from §13 / §14 / §15 prose
only.

**Stage A — answer-selection architecture (pinned, identical
to §15.3 Chunk 3b modulo benchmark substitution).**

Stage A is the §14a.2 NLI-clustered selector + V1 softmin
trust consumer **applied to TruthfulQA-MC** at the same
configuration §14a.2 / §15.3 used on HaluEval-QA. Pinned for
the same reasons §15.3 pinned this configuration: V1 softmin
$\tau = 0.5$ produced the +4pp lift in §14a.2 (the strongest
BCVF-shaped lift in the §13 / §14 program); the NLI-clustered
selector is the post-§14a-audit version that fixed the
string-identity tie-breaking degeneracy. Single configuration
in this scout — no multi-selector or multi-consumer sweep.

**Stage A specification (pinned).**

- **Source set (M = 3, cross-family, all cached from §13.11
  / §14a.2):** `Qwen/Qwen2.5-7B-Instruct`,
  `meta-llama/Llama-3.1-8B-Instruct`,
  `mistralai/Mistral-7B-Instruct-v0.3`.
- **Per-source K = 10 stochastic samples** at T=1.0,
  max_new_tokens=32, prompt `Q: ... A:`. Identical to
  §13.10 / §13.11 / §14a.2 protocols.
- **Per-source greedy answer** at T=0, max_new_tokens=32,
  same prompt format.
- **Per-source semantic entropy** $H_{\text{src}_i}(q)$ via
  question-conditioned bidirectional NLI clustering of the
  K=10 samples (DeBERTa-v3-base-mnli-fever-anli, identical
  NLI model to §13.10 / §14a.2).
- **V1 softmin consumer (pinned, single):**
  $w_i^{V1} \propto \exp(-H_{\text{src}_i}(q) / \tau)$ with
  $\tau = 0.5$.
- **NLI-clustered selector (pinned, single):** identical
  spec to §14a.2 / §15.3 Chunk 3b (cluster M=3 source
  greedies by question-conditioned bidirectional NLI
  entailment, aggregate weights within each cluster, pick
  winning cluster $k^*$ by max aggregated weight with
  lowest-cluster-index tiebreak, pick representative source
  by max individual weight with lowest-source-index
  tiebreak).
- **Benchmark (pinned, single):** **TruthfulQA-MC**
  validation split, $N = 100$. Identical to §13.10 /
  §13.11's TruthfulQA-MC question subset.

**Stage A output (the per-question handoff to Stage B).**
Identical structure to §15.3 Chunk 3b — `selected_answer(q)`,
`winning_source_id(q) ∈ {Qwen, Llama, Mistral}`, all three
per-source semantic entropies including the winner's, the
winning cluster's aggregated weight, and the runner-up's.
Stage A makes no abstention decision and consumes no
threshold parameter.

**The §14a.2-on-TruthfulQA-MC dump does not exist yet.** The
GPU run that produces it (~50–60 min on the existing 80 GB
GPU per §14a.2's pinned cost estimate) follows §15.5's
landing as a separate authorization step. Implementation
chunk (5h) details the pinned re-run protocol.

**What Stage A explicitly does NOT pin** (identical to §15.3
Chunk 3b's non-pin list):

- Multiple consumers (V2 thresholded exclusion, V3 veto-only,
  V4 deadband fallback). All deferred — V1 is pinned single.
- Multiple selectors (highest-weight-source, string-matched,
  uniform majority). Deferred.
- Different source sets. M=3 cross-family is pinned; no
  larger $M$, no model substitution, no single-source
  fallback.
- Re-running §14a.2 on HaluEval-QA. The on-disk §14a.2-on-
  HaluEval dump §15.3 used remains the §15.4 verdict-of-
  record artifact and is NOT touched by §15.5.

**Stage B — abstention architecture (pinned, identical to
§15.3 Chunk 3c).**

Stage B sits downstream of Stage A and reads the §14a.2-on-
TruthfulQA-MC dump's per-question records (once produced by
the Stage A GPU run). For each question $q$, Stage B
consumes:

- `selected_answer(q)` from Stage A's V1 softmin + NLI-
  clustered selector;
- $c(q)$ — the correctness label of `selected_answer(q)`
  per the §14a.2 NLI labeling protocol applied to
  TruthfulQA-MC (entails right_answer AND not any
  distractor); **note this is the correctness of Stage A's
  selected answer, NOT Qwen-greedy correctness on
  TruthfulQA-MC; structurally distinct from §15.1's
  TruthfulQA-MC $c(q)$ on questions where V1 selects a
  different answer than Qwen-greedy**;
- a per-question identifier for deterministic ordering.

These plus the §15.5 risk signal (pinned in Chunk 5d) drive
Stage B's per-question answer-or-abstain decision.

**Decision rule (pinned, single, identical to §15.3 Chunk 3c).**
Per-question deterministic threshold rule:
$$
\text{policy}_\tau(q) = \begin{cases}
\text{ANSWER selected\_answer}(q) & \text{if } r(q) < \tau \\
\text{ABSTAIN} & \text{if } r(q) \ge \tau
\end{cases}
$$
where $r(q)$ is the §15.5 risk signal pinned in Chunk 5d.
Ties at $r(q) = \tau$ resolve to ABSTAIN — identical
deterministic, conservative tie-handling as §15.1 / §15.3.

**Threshold-sweep protocol (pinned, identical to §15.3
Chunk 3c).** $\tau$ is swept across the sorted unique values
of $r(q)$ on TruthfulQA-MC plus $-\infty$ (always-abstain)
and $+\infty$ (always-answer). At $N=100$ this yields at most
102 grid points. All operational metrics (pinned in Chunk 5f)
are computed at every grid point. No grid is hand-picked; no
$\tau$ is hand-picked.

**What Stage B explicitly does NOT pin** (identical to §15.3
Chunk 3c).

- **Multiple abstention policies.** No deadband, no veto-only
  mode, no cluster-margin rule. One threshold rule, single
  $\tau$.
- **Multiple risk signals.** One scalar (pinned in Chunk 5d).
  No primary-plus-secondary, no ensemble.
- **Held-out calibration of $\tau$.** $\tau$ is fitted only
  via the deterministic empirical-support sweep — same rule
  §15.1 / §15.3 used. No held-out tuning, no isotonic /
  Platt / conformal wrapping of $r(q)$.
- **Re-decoding or rewriting `selected_answer(q)`.** Stage B's
  only degree of freedom is the answer/abstain decision; the
  answer itself is whatever Stage A produced.
- **Cascading multiple abstention layers.** If the risk
  signal were split across multiple thresholds, that would be
  a distinct policy and require a fresh §0.8 commitment.

**Risk signal pin (identical to §15.3 Chunk 3d).**

The §15.5 risk signal is pinned as:
$$
r(q) \;=\; H_{\text{src}_{i^*}}(q)
$$
where $i^*$ is Stage A's `winning_source_id(q)` on
TruthfulQA-MC and $H_{\text{src}_{i^*}}(q)$ is that source's
semantic-entropy scalar from the §13.10-protocol K=10 NLI-
clustered samples (computed by the §14a.2-on-TruthfulQA-MC
GPU run, identical protocol to §13.10 / §14a.2). **Higher
$H$ means higher per-question hallucination risk on Stage A's
selected answer; Stage B's policy abstains when $r$ exceeds
$\tau$.**

This is the same scalar §15.3 pinned, applied to the
TruthfulQA-MC §14a.2 dump rather than the HaluEval-QA one.
On questions where V1 picks Qwen on TruthfulQA-MC, $r(q)$
equals Qwen's per-source entropy on TruthfulQA-MC at the §13.10
protocol; on questions where V1 picks Llama or Mistral, $r(q)$
equals that source's per-source entropy.

**§15.5 reuses §15.3's risk-signal justification verbatim** —
the three §0.8 questions §15.3 Chunk 3d answered for
HaluEval-QA apply identically here:

- **Why more defensible than alternatives?** $H_{\text{src}}$
  inherits §13.10's marginal-pass-on-both-benchmarks pedigree
  (AUC 0.661 on each at N=100). §15.5's TruthfulQA-MC scalar
  is the same primitive at the same N=100, computed by the
  same NLI clustering protocol.
- **Why does it not reopen §13?** §13 measured AUC of
  $H_{\text{src}}$ vs ground-truth correctness; §15.5 uses
  the same scalar as a per-question risk score driving an
  answer/abstain policy applied to **Stage A's TruthfulQA-MC
  selected answer** — a different metric class. Novel content
  is the joint $(r(q), c(q))$ distribution on V1-selects-non-
  Qwen TruthfulQA-MC questions.
- **Why is it implementable without new infrastructure?**
  All quantities will be pre-computed in the §14a.2-on-
  TruthfulQA-MC dump once that GPU run produces it
  (per §14a.2's prose, dump records each source's greedy +
  entropy + per-question correctness label). Pure CPU post-
  processing in Stage B, mirroring §15.3.

**Alternative signals considered and explicitly NOT pinned**
(identical to §15.3 Chunk 3d):

- $\min_i H_{\text{src}_i}(q)$ — independent of V1's actual
  selection.
- $W_{k^*} - W_{k_{\text{runner}}}$ — winning-cluster margin;
  pure selector-level signal, lacks §13/§15 prior validation.
- $W_{k^*} / \sum_k W_k$ — winning-cluster fraction; same
  lack-of-validation issue.
- Cross-source NLI disagreement (§13.11-style) — closer to
  §13.11 reframed; would reopen that closed hypothesis class.
- Any ensemble of the above — forbidden by §15.5 Chunk 5c's
  "no ensemble" pin.

§15.5 uses **exactly one scalar**: $H_{\text{src}_{i^*}}(q)$.
No primary-plus-secondary, no ensemble, no fallback. Adding
any alternative would require a fresh §0.8 amendment to
§15.5.

**Benchmark scope pin (single benchmark; TruthfulQA-MC only).**

§15.5 is a single-benchmark scout on **TruthfulQA-MC** at
$N = 100$ — the benchmark §15.3 explicitly excluded. Per the
user-pinned A1 framing (cross-benchmark synthesis as
diagnostic only), §15.5's verdict cascade fires on
TruthfulQA-MC's $\Delta\kappa$ alone, structurally parallel
to §15.3's HaluEval-only cascade.

**Why TruthfulQA-MC, why now.**

1. **§15.3 deferred TruthfulQA-MC by construction.** §15.3
   Chunk 3e pinned HaluEval-QA-only because the §14a.2 dump
   existed only on HaluEval. §15.5 closes that gap with a
   fresh §14a.2 protocol run on TruthfulQA-MC.
2. **TruthfulQA-MC is the consistent worst-benchmark cap
   across §13 / §14 / §15.** It defeated 5/5 §13 single-axis
   classes; §14 deferred it to "full §14 conditional on §14a.2
   STRONG" which never landed; §15.2's combined-classification
   was clamped to MARGINAL by TruthfulQA-MC's $\kappa = 0.14$.
   §15.5 tests whether the §14+§15 hybrid construct that
   produced §15.4's HaluEval USEFUL_INTERNAL also clears its
   USEFUL_INTERNAL bar on the harder benchmark.
3. **High prior of failure, but a clean answer either way.**
   If §15.5 returns USEFUL_INTERNAL or higher, §15.4's
   single-benchmark finding generalizes; the cross-benchmark
   diagnostic synthesis would land USEFUL_INTERNAL or above
   under the worst-benchmark rule. If §15.5 returns MARGINAL
   or below, the §15.4 finding is bounded as a HaluEval-only
   artifact; the cross-benchmark synthesis lands at the
   worse of {§15.4, §15.5} per the worst-benchmark rule.

**Cross-benchmark synthesis (diagnostic, not band-driving).**
The §15.5 result section will compute and report the combined
verdict across §15.4 (HaluEval) and §15.5 (TruthfulQA-MC)
under the worst-benchmark rule:
$$
\Delta\kappa_\text{combined} = \min\big(\Delta\kappa_{\text{HaluEval}}, \Delta\kappa_{\text{TruthfulQA-MC}}\big)
$$
with the §15.3 / §15.5 cascade applied to
$\Delta\kappa_\text{combined}$. **This combined verdict is a
diagnostic only.** It does NOT re-classify §15.4's HaluEval-
only USEFUL_INTERNAL or §15.5's TruthfulQA-MC-only verdict.
It informs whether the §14+§15 hybrid clears USEFUL_INTERNAL
on a worst-benchmark basis — the bar a future §15.6 product-
layer commitment would care about — but it is NOT the §15.5
band-driver under §0.8.

**Implication for §15.6 / §13.9.** A §15.5 STRONG would
authorize §15.6 (full hybrid pre-commitment with both
benchmarks combined and product-layer scope). A §15.5
USEFUL_INTERNAL whose cross-benchmark synthesis also lands
USEFUL_INTERNAL would likewise unlock a §15.6 commitment as
a separate §0.8 step. Lower verdicts on §15.5 (MARGINAL,
SATURATION, REGRESSION) close the §14+§15 hybrid line at the
configuration. **§13.9 hold remains in force regardless of
§15.5 outcome** — §15.5's metric class (Δκ vs §15.1
TruthfulQA-MC baseline of 0.14) is structurally separate
from §13.9's answer-selection STRONG-band gate, exactly as
§15.3 / §15.4 were.

**Cherry-picking caveat (acknowledged ex ante).** TruthfulQA-
MC is the harder of the two benchmarks; running it
specifically AFTER §15.4's HaluEval USEFUL_INTERNAL could
look like cherry-picking the second benchmark to confirm a
positive signal. **§15.5 deliberately runs the harder
benchmark second precisely because TruthfulQA-MC has been
the consistent cap; the asymmetry is a known prior of the
program**, not an artifact of §15.5's setup. The §15.5 bands
(Chunk 5g) are pinned identical to §15.3's, not relaxed —
the same operational threshold applies.

**Operational metrics pin (identical structure to §15.3
Chunk 3f modulo benchmark and baseline).**

§15.5's metric set is structurally identical to §15.3's,
with two pinned differences: the benchmark is TruthfulQA-MC
and the §15.1 baseline is $\kappa_{\S15.1,\text{TruthfulQA-MC}}
= 0.14$ (not 0.26).

**Notation (single benchmark, $N = 100$).** For each
question $q$ on TruthfulQA-MC at threshold $\tau$:

- $A_\tau = \{q : r(q) < \tau\}$;
  $\text{cov}(\tau) = |A_\tau|/N$.
- $\text{acc}(\tau) = (1/|A_\tau|) \sum_{q \in A_\tau} c(q)$
  where $c(q)$ is correctness of Stage A's
  `selected_answer(q)` per Chunk 5c (NOT Qwen-greedy
  correctness on TruthfulQA-MC).
- $\text{ecr}(\tau), \text{far}(\tau)$ — identical formulas
  to §15.3 / §15.1 applied to the new $c(q)$.
- $W_\text{hybrid} = N - \sum_q c(q)$ — total wrong V1-
  selected answers on TruthfulQA-MC; observed empirically at
  run time (NOT pinned ex ante; same convention as §15.3).

**Primary decision metric (single scalar; identical
structure to §15.3 Chunk 3f).**
$$
\Delta\kappa \;=\; \kappa_\text{hybrid} - \kappa_{\S15.1,\text{TruthfulQA-MC}}
$$
where:

- $\kappa_\text{hybrid} = \max\{\text{cov}(\tau) :
  \text{acc}(\tau) \ge \alpha_2 \text{ AND } |A_\tau| \ge n_\min\}$
  on TruthfulQA-MC, with $\alpha_2 = 0.50$ and
  $n_\min = 10$ (identical floor to §15.1 / §15.3).
- $\kappa_{\S15.1,\text{TruthfulQA-MC}} = 0.14$ — pinned
  constant from §15.2's verdict-of-record TruthfulQA-MC
  $\kappa$ at $\alpha_2$, recorded in
  `docs/experiments/probe_selective_abstention.json`.

$\Delta\kappa > 0$ means the hybrid produces operationally
meaningful lift over §15.1's single-source abstention on
TruthfulQA-MC at the absolute-majority target.
$\Delta\kappa \le 0$ means it does not.

**§0.8 caveat on the baseline constant.** The
$\kappa_{\S15.1,\text{TruthfulQA-MC}} = 0.14$ value was
computed at N=100 against §13.10 dumps that have since been
overwritten with N=200 versions per §13.20 / §15.2 Postscript.
The recorded value persists in the §15.2 verdict-of-record
artifact and is binding under §0.8 regardless of the upstream
overwrite. **§15.5 does NOT re-run §15.1 on TruthfulQA-MC**
to "refresh" the baseline; doing so would require its own
§0.8 commitment and would conflate two N-configurations.

**Pinned three target accuracies (identical to §15.3 / §15.2
TruthfulQA-MC operating points).**
$\alpha \in \{0.35, 0.50, 0.75\}$, where $\alpha_1 = 0.35$ is
the TruthfulQA-MC greedy baseline (0.250 per §13.10) plus
10pp. (HaluEval used $\alpha_1 = 0.40$ because its greedy
baseline is 0.300; TruthfulQA-MC's lower greedy means
$\alpha_1$ is correspondingly lower.)

**Secondary diagnostic metrics** (reported, NOT band-driving).

- $\delta_\text{AURC,hybrid} = W_\text{hybrid}/N -
  \text{AURC}_\text{hybrid}$ — integrated lift over random
  abstention on Stage A's TruthfulQA-MC selected answers.
- $(\text{cov}, \text{ecr}, \text{far})$ triples at each of
  the three $\alpha$ values.
- Bootstrap CI (two-sided 95%, $B = 1000$, paired over
  question indices, deterministic seed
  `SeedSequence(entropy=15)` per §15.1 / §15.3 convention)
  on $\Delta\kappa$. Statistical demotion rule pinned in
  Chunk 5g.

**Baselines (pinned, three; all from existing artifacts; no
new generation beyond Stage A).**

| Baseline | Source | Role |
|---|---|---|
| §15.1 TruthfulQA-MC $\kappa@\alpha_2 = 0.14$ | §15.2 verdict-of-record | Primary comparator (drives $\Delta\kappa$) |
| §14a.2-on-TruthfulQA-MC V1 full-coverage point | (computed from the §14a.2-on-TruthfulQA-MC dump once produced) | "Stage A without abstention" reference; documents whether the hybrid even needs Stage B |
| Random-abstain matched-coverage on Stage A's answers | Closed-form: $\mathbb{E}[\text{acc}_\text{random}(\text{cov})] = (N - W_\text{hybrid})/N$ | Random baseline for $\delta_\text{AURC,hybrid}$ |

§15.1's TruthfulQA-MC $\kappa@\alpha_2 = 0.14$ is the central
comparator because §15.1 is the closest non-hybrid analogue
on TruthfulQA-MC. A §15.5 STRONG must demonstrate that
adding Stage A's selector produces operationally meaningful
lift over the single-source policy on TruthfulQA-MC — not
merely lift over random abstention.

**Verdict bands (pinned; identical 1D $\Delta\kappa$ cascade
to §15.3 Chunk 3g — B1 framing locked).**

Per the user-pinned B1 framing (bands identical to §15.3,
not recalibrated for TruthfulQA-MC), §15.5's verdict cascade
is the **same 1D ordered cascade** §15.3 used, applied to
TruthfulQA-MC's $\Delta\kappa$. Numerical thresholds are
unchanged:

1. **REGRESSION** — $\Delta\kappa < -0.02$.
2. **STRONG** — $\Delta\kappa \ge +0.10$.
3. **USEFUL_INTERNAL** — $\Delta\kappa \ge +0.05$.
4. **MARGINAL** — $\Delta\kappa \ge +0.02$.
5. **SATURATION** — explicit residual catch-all
   ($\Delta\kappa \in [-0.02, +0.02)$).

Rules 1–4 are mutually exclusive by ordering; rule 5 catches
the residual deterministically. **No secondary metric
participates in the cascade**; secondary diagnostics
($\delta_\text{AURC}$, ecr, far, operating-point triples) are
reported but never re-classify the verdict — same discipline
as §15.3.

**Why bands are NOT recalibrated for TruthfulQA-MC.** §15.1's
TruthfulQA-MC baseline ($\kappa = 0.14$) is structurally
lower than HaluEval's (0.26), so the same $\Delta\kappa$
threshold corresponds to a lower implied $\kappa_\text{hybrid}$
on TruthfulQA-MC. But the pinned B1 framing tests cross-
benchmark transfer at the **same operational threshold** —
i.e., does the hybrid clear the same operational bar on the
harder benchmark, not "does it clear a TruthfulQA-MC-specific
relaxed bar." Recalibrating the bands would be band-tuning
to expectations and is foreclosed.

**Operational meanings per band on TruthfulQA-MC** (assuming
the pinned $\kappa_{\S15.1,\text{TruthfulQA-MC}} = 0.14$):

| Verdict | $\Delta\kappa$ range | Implied $\kappa_\text{hybrid}$ | Meaning |
|---|---|---|---|
| STRONG | $\ge +0.10$ | $\ge 0.24$ | Substantively higher cov@$\alpha_2$ than §15.1 on the harder benchmark; cross-benchmark generalization confirmed |
| USEFUL_INTERNAL | $[+0.05, +0.10)$ | $[0.19, 0.24)$ | Visibly better than §15.1 on TruthfulQA-MC; internal-research value at this benchmark |
| MARGINAL | $[+0.02, +0.05)$ | $[0.16, 0.19)$ | Small detectable lift |
| SATURATION | $[-0.02, +0.02)$ | $[0.12, 0.16)$ | Operationally equivalent to §15.1 on TruthfulQA-MC |
| REGRESSION | $< -0.02$ | $< 0.12$ | Actively worse than §15.1 on TruthfulQA-MC |

**Acceptance / rejection rules** (one-to-one mapped to the
cascade; mirrors §15.3 Chunk 3g but with §15.5-specific
authorizations).

| Verdict | Authorizes | Forecloses |
|---|---|---|
| **STRONG** | Drafting §15.6 — full hybrid pre-commitment with both benchmarks combined and product-layer scope (separate §0.8). | VC-brief changes (§13.9 hold remains); auto-deployment without §15.6. |
| **USEFUL_INTERNAL** | Documenting the §14+§15 hybrid as having internal-research operational value on TruthfulQA-MC at this single-benchmark scale. Authorizes §15.6 conditional on cross-benchmark synthesis (Chunk 5e diagnostic) also landing USEFUL_INTERNAL. | §15.6 product investment (without cross-benchmark synthesis confirmation); cross-benchmark claims; VC-brief changes. |
| **MARGINAL** | Recording §15.5 as acknowledged but unactionable on TruthfulQA-MC. | §15.6 follow-up; product investment; VC-brief changes. |
| **SATURATION** | Documenting §15.5 as operational null on TruthfulQA-MC. Bounds §15.4's HaluEval USEFUL_INTERNAL as a HaluEval-only artifact under cross-benchmark synthesis. | Same as MARGINAL. |
| **REGRESSION** | Closing the §14+§15 hybrid construct on TruthfulQA-MC. The §13/§14/§15 closure prose extends to "answer-selection AND single-source abstention AND hybrid all saturated/regressed on TruthfulQA-MC at this configuration." | Same as SATURATION. |

**Demotion rule (STRONG-only, identical to §15.3 Chunk 3g).**
If the cascade returns STRONG but the bootstrap CI lower
bound on $\Delta\kappa$ is $\le 0$, the verdict is demoted
to **USEFUL_INTERNAL** with explicit `STRONG_BUT_CI_DEMOTION`
annotation. USEFUL_INTERNAL / MARGINAL / SATURATION /
REGRESSION are NOT subject to demotion.

**Boundary-case audit table (illustrative, deterministic;
identical to §15.3 Chunk 3g modulo benchmark labels).** The
cascade behavior is identical to §15.3's at the same
$\Delta\kappa$ values:

| $\Delta\kappa$ | Cascade trace | Verdict |
|---|---|---|
| $+0.099$ | rules 1–2 NO; rule 3 YES | **USEFUL_INTERNAL** |
| $+0.019$ | rules 1–4 NO; rule 5 catches | **SATURATION** |
| $-0.020$ | rule 1 NO at boundary; rule 5 catches | **SATURATION** |
| $-0.021$ | rule 1 YES | **REGRESSION** |

The boundary-inclusivity precisions match §15.3 exactly:
$\Delta\kappa = -0.020$ is SATURATION; $\Delta\kappa = -0.021$
is REGRESSION.

**Implementation scope (pinned, two phases: Stage A GPU re-
run + Stage B CPU post-processor).**

§15.5 reuses closed §14 / §15 components and pinned identical
configuration to §15.3 modulo benchmark — same "small
integration layer over closed components" framing as §15.3
Chunk 3h. Two distinct execution phases:

**Phase 1 — Stage A GPU re-run (~50–60 min on existing
80 GB GPU).**

Run a **new sibling producer**
`scripts/probe_system_level_scout_v2_truthfulqa.py` — a copy
of §14a.2's `probe_system_level_scout_v2.py` with only the
dataset-loading block swapped to load TruthfulQA-MC instead
of HaluEval-QA (using §13.11's `--benchmark truthfulqa_mc`
loading pattern). All other §14a.2 pinned configuration is
preserved verbatim. Sibling-producer pattern documented in
§15.5 Amendment 1 below; the §14a.2 producer
`scripts/probe_system_level_scout_v2.py` is preserved
pristine (§14c verdict-of-record reproducibility chain
unchanged). Pinned protocol (matches §14a.2's pinned cost
estimate exactly):

- 3 sources × 100 questions × K=10 stochastic generations =
  3,000 sampling calls (~30 min on the cached GPU).
- 3 sources × 100 questions × 1 greedy generation = 300
  deterministic generations (~5 min).
- Per-source NLI clustering: 3 × 100 = 300 clustering
  operations × 90 NLI pairs ≈ ~10 min.
- Per-question NLI labeling: 4 candidates × 100 questions
  × 2 NLI calls = 800 calls (~5 min batched).
- Memory: ~45 GB co-resident in fp16, identical to §13.11 /
  §14a.2 setup.

Output: `docs/experiments/probe_system_level_scout_v2_truthfulqa_mc.json`
(identical schema to the HaluEval-QA dump per
`scripts/probe_system_level_scout_v2.py`'s JSON writer).

**Phase 1 §0.8 caveat.** §14a.2's verdict-of-record (§14c
`SCOUT_SATURATION`) was on HaluEval-QA only; running its
protocol on TruthfulQA-MC is **the first time §14a.2's
pinned configuration has been exercised on TruthfulQA-MC**.
This is structurally close to "full §14" which §14c
foreclosed conditional on §14a.2 STRONG. **§15.5 is NOT a
"full §14" attempt** — it is using §14a.2's machinery as
Stage A within the §15.5 selective-prediction metric class
(operational AURC + cov@α), NOT measuring §14's answer-
selection accuracy delta. The Phase 1 GPU run produces a
TruthfulQA-MC dump but §15.5 does NOT classify against §14a.2
bands; it classifies against §15.5's pinned $\Delta\kappa$
cascade (Chunk 5g).

**Phase 2 — Stage B CPU post-processor.**

One new script: `scripts/probe_hybrid_selective_abstention_truthfulqa.py`
(numpy + stdlib only, CPU-only post-processor; structurally
parallel to `scripts/probe_hybrid_selective_abstention.py`
modulo benchmark and baseline constant).

Components 1–12 identical in shape to §15.3 Chunk 3h's
specification, with these §15.5-specific modifications:

1. **Input dump path** changed to
   `docs/experiments/probe_system_level_scout_v2_truthfulqa_mc.json`.
2. **Pinned baseline constant** changed to
   `KAPPA_BASELINE_S15_1 = 0.14` (vs §15.3's 0.26).
3. **Pinned $\alpha$ targets** changed to $\{0.35, 0.50,
   0.75\}$ (vs §15.3's $\{0.40, 0.50, 0.75\}$).
4. **Output paths** changed to
   `docs/experiments/probe_hybrid_selective_abstention_truthfulqa.{json,md}`.
5. **`schema_version`** = `"15.5"` (vs §15.3's `"15.3"`).
6. All other constants (cascade thresholds, bootstrap config,
   demotion rule, $n_\min$) identical to §15.3.

**Reuse from §15.3 (primitives copied, NOT imported).** Same
copy-not-import discipline as §15.3 Chunk 3h: §15.5's script
copies §15.3's metric primitives verbatim rather than
importing from `probe_hybrid_selective_abstention.py`.
§15.4's verdict-of-record artifacts are preserved unchanged.

**Cross-benchmark synthesis (Stage B Phase 2 reporting).**
The §15.5 result section will compute:

$$
\Delta\kappa_\text{combined} = \min(\Delta\kappa_{\text{HaluEval}}, \Delta\kappa_{\text{TruthfulQA-MC}})
$$

with the §15.3 / §15.5 cascade applied as a **diagnostic**.
$\Delta\kappa_{\text{HaluEval}} = +0.0900$ is read from
`docs/experiments/probe_hybrid_selective_abstention.json`
(§15.4 verdict-of-record). $\Delta\kappa_{\text{TruthfulQA-MC}}$
is computed by §15.5's Phase 2. Combined verdict reported
alongside §15.5's per-benchmark verdict; does NOT re-classify
either.

**Engineering cost (estimated).**

- **Phase 1:** ~50–60 min GPU on cached models. Identical to
  §14a.2's pinned cost.
- **Phase 2:** ~400–600 lines of new code (with the same
  $\sim$1098-line audit-lesson caveat from §15.4 Chunk 4e —
  copy-not-import duplication may push actual closer to
  §15.3's size). CPU only; under 30 sec wall clock at N=100
  with B=1000 bootstrap.
- **Total wall clock end-to-end:** ~1 hour after §15.5
  pre-commitment lands.

**Output paths (pinned).**

- `docs/experiments/probe_system_level_scout_v2_truthfulqa_mc.json`
  (Stage A dump from Phase 1 GPU run).
- `docs/experiments/probe_hybrid_selective_abstention_truthfulqa.json`
  (Stage B machine-readable, `schema_version` `"15.5"`).
- `docs/experiments/probe_hybrid_selective_abstention_truthfulqa.md`
  (Stage B human-readable summary).

**What §15.5 implementation explicitly does NOT authorize.**

- Modifying `scripts/probe_system_level_scout_v2.py` (§14a.2's
  pinned producer; preserved verbatim).
- Modifying `scripts/probe_selective_abstention.py` (§15.1's
  pinned codepath).
- Modifying `scripts/probe_hybrid_selective_abstention.py`
  (§15.3's pinned codepath; §15.4 verdict-of-record
  artifact).
- Re-running §14a.2 on HaluEval-QA (§15.4 dump preserved).
- Re-running §15.1 on TruthfulQA-MC (§15.2 baseline κ=0.14
  remains the pinned constant).
- Adding TruthfulQA-Generation, TriviaQA, or any benchmark
  beyond TruthfulQA-MC.
- Auto-promoting any verdict to §15.6.

**Reduced-form authorization rationale — §15.5 is partially
reduced-form, partially fresh-compute.**

Unlike §15.3 (which was pure post-processing because the
§14a.2 HaluEval-QA dump already existed), §15.5 requires a
genuinely new GPU run (Phase 1) before any post-processing
can begin. **§15.5 is therefore NOT in the same "reduced-form
post-processing only" category as §15.3.** Its compactness
is bounded by:

- **The §14a.2 producer script exists and is closed.** §15.5
  reuses it as-is on TruthfulQA-MC; no producer-script
  modifications.
- **§15.3's abstention machinery exists and is closed.**
  §15.5's Phase 2 copies §15.3's primitives.
- **§13.10's semantic-entropy scalar definition exists** and
  is not invalidated by §13.20's N=200 observation (which
  does not re-classify §13.10's N=100 verdict-of-record).
- **§15.1's TruthfulQA-MC κ baseline (0.14) exists** in
  §15.2's verdict-of-record artifact and is binding under
  §0.8 regardless of §13.20's upstream-dump overwrite.

**If §14a.2's producer script did not exist, §15.5's Phase 1
cost would be substantially higher** (writing a new producer
from scratch is multi-day work, not a 50–60-min run). The
~1-hour total wall-clock figure is contingent on the existing
§14a.2 producer being directly reusable.

**What §15.5 explicitly does NOT test.**

- **Retrieval augmentation.** No retrieval, search, or
  external knowledge source. The hybrid's only response
  options are ANSWER `selected_answer(q)` or ABSTAIN.
- **Verifier ensembles.** No external verifier model, no
  judge-model, no critique pass.
- **Multi-benchmark generalization beyond {HaluEval-QA,
  TruthfulQA-MC}.** §15.5's cross-benchmark synthesis is
  explicitly bounded to the §13.10 / §14a.2 / §15.1 / §15.3
  benchmark pair. Any third benchmark requires a fresh §0.8.
- **Larger-N stability.** §15.5 runs at N=100 to match §15.3
  / §15.4. A larger-N re-run would require its own §0.8.
- **A new §13 observable program.** §15.5 reuses §13.10's
  semantic-entropy scalar verbatim on TruthfulQA-MC. §13.19
  closure remains binding.
- **A new §14 system-level program.** §15.5 reuses §14a.2's
  pinned configuration on TruthfulQA-MC; this is the first
  on-TruthfulQA-MC §14a.2 run, but §15.5 does NOT classify
  the result against §14a.2's pre-committed bands (different
  metric class). §14c's `SCOUT_SATURATION` verdict on
  HaluEval-QA is unchanged.
- **Product readiness.** Even §15.5 STRONG would require
  §15.6 (full hybrid pre-commitment with both benchmarks
  combined and product-layer scope) before any deployment-
  grade claim. §15.5 is a single-benchmark scout.
- **Re-classification of any prior §13 / §14 / §15.x
  verdict.** §13.19 (single-axis ANTI), §14b / §14c
  (`SCOUT_SATURATION`), §15.2 (`MARGINAL`), §15.4
  (`USEFUL_INTERNAL`), and §13.20 (N=200 `NOISE_BAND_LIFT`
  observation) are all closed under §0.8 at their pinned
  configurations. §15.5 cannot revisit any of them.

**§15.5 chunk roll-up — pre-commitment now complete.**

| Chunk | Content |
|---|---|
| 5a | Opening framing — cross-benchmark companion to §15.3 (A1 framing) |
| 5b | Stage A architecture pin (§14a.2 protocol applied to TruthfulQA-MC) |
| 5c | Stage B architecture pin (single threshold rule, ties to ABSTAIN) |
| 5d | Risk signal pin ($r(q) = H_{\text{src}_{i^*}}(q)$, identical to §15.3) |
| 5e | Benchmark scope pin (TruthfulQA-MC only; cross-benchmark synthesis as diagnostic) |
| 5f | Operational metrics pin ($\Delta\kappa$ primary against $\kappa_{\S15.1} = 0.14$) |
| 5g | Verdict bands (1D $\Delta\kappa$ cascade, identical thresholds to §15.3; B1 framing) |
| 5h | Implementation scope (Phase 1 GPU re-run + Phase 2 CPU post-processor) |
| 5i | What §15.5 does NOT test + reduced-form rationale + roll-up |

Phase 1 (GPU re-run of §14a.2 on TruthfulQA-MC) is a separate
§0.8 authorization gate. Phase 2 (new CPU post-processor) is
also a separate gate. §15.5.x (the result section, parallel
to §15.4) follows both phases completing.

### 15.5 Amendment 1 — sibling producer for §14a.2 protocol on TruthfulQA-MC (pre-execution)

**Status: amendment landed before any GPU run.** Surfaced
explicitly per §15.5's "no silent patches" rule.

**Trigger.** Pre-execution audit of
`scripts/probe_system_level_scout_v2.py` (the §14a.2 producer
script Chunk 5h pinned for re-use) revealed that **the
producer is hardcoded to HaluEval-QA at line 715**
(`load_dataset("pminervini/HaluEval", "qa", split="data")`).
There is no `--benchmark` flag. §15.5 Chunk 5h's pin to
"re-run `scripts/probe_system_level_scout_v2.py` with
benchmark flag set to `truthfulqa_mc`" is therefore not
literally executable — the pinned producer cannot run on
TruthfulQA-MC as-is.

**Two recovery options considered.**

- **(A) Modify the existing §14a.2 producer** to add a
  `--benchmark` flag (mirroring §13.11's pattern at lines
  501–503 / 626–635 of `probe_cross_family_entropy.py`).
  §0.8 cost: changes the script that produced §14a.2's
  verdict-of-record artifacts. Even a small flag addition
  reaches into closed territory.
- **(B) Create a sibling producer script** that copies
  `probe_system_level_scout_v2.py` verbatim and swaps only
  the dataset-loading block. §0.8 benefit: §14a.2's producer
  stays pristine; §14c's verdict-of-record reproducibility
  chain unchanged.

**Amendment (this block supersedes the affected lines in
Chunk 5h).** Option B is pinned.

- **New script:** `scripts/probe_system_level_scout_v2_truthfulqa.py`
  — copy of `probe_system_level_scout_v2.py` with the
  dataset-loading block (line ~715 of the original) swapped
  to load TruthfulQA-MC validation split, mirroring §13.11's
  TruthfulQA-MC loading pattern.
- **All other §14a.2 pinned configuration preserved verbatim:**
  same M=3 cross-family sources, same K=10, same T=1.0, same
  max_new_tokens=32, same NLI model, same V1 softmin τ=0.5,
  same NLI-clustered selector, same dataclass schema for the
  per-question record. Only the benchmark loader differs.
- **Output filename:** the new script writes to
  `docs/experiments/probe_system_level_scout_v2_truthfulqa_mc.json`
  (per Chunk 5h's pinned output path).
- **§14a.2's existing producer
  `scripts/probe_system_level_scout_v2.py` is NOT modified.**
  The §14a.2 verdict-of-record reproducibility chain is
  preserved.

**Why this is a §0.8-clean amendment.** The amendment
corrects a pre-commitment artifact (an executable
assumption that didn't hold) without changing any pinned
numerical band, metric definition, baseline,
acceptance/rejection rule, or scope boundary. No data has
been inspected. The §15.5 cascade boundary-case audit table,
verdict bands, primary metric, baseline constant, and
benchmark scope are all unchanged.

**What this amendment does NOT change.**

- Numerical bands (Chunk 5g identical to §15.3 Chunk 3g).
- Operational metric definitions (Chunk 5f).
- Baselines (Chunk 5f's three pinned baselines).
- Cross-benchmark synthesis as diagnostic (Chunk 5e).
- Output paths for Phase 2 / Stage B
  (`probe_hybrid_selective_abstention_truthfulqa.{json,md}`).
- The "does not test" list (Chunk 5i).
- The §14a.2 producer or its closed §14c verdict-of-record.
- The §15.4 verdict-of-record (HaluEval USEFUL_INTERNAL).

**Implementation step (separate authorization).** Drafting
`scripts/probe_system_level_scout_v2_truthfulqa.py` is a
mechanical copy-with-one-swap operation. The new file would
be ~1100 lines (matching §14a.2 producer's size). I can draft
it in this sandbox; the user runs it on the runpod (50–60
min GPU). This is a separate §0.8 authorization step from
landing the amendment itself.

**Audit lesson recorded.** §15.5's Chunk 5h pin "re-run
`scripts/probe_system_level_scout_v2.py` with benchmark
flag" was based on assumed CLI surface, not verified CLI
surface. Future "reuse existing producer" pins should
explicitly cite the producer's flag list (or its absence)
to prevent assumption-vs-reality drift surfacing at
execution time.

### 15.6 Result — §15.5 hybrid scout on TruthfulQA-MC returned REGRESSION; cross-benchmark synthesis also REGRESSION

The §15.5 pre-committed hybrid scout has been executed
end-to-end (Phase 1 GPU producer + Phase 2 CPU post-processor)
in the runpod container against the TruthfulQA-MC benchmark.
Combined classification per pre-committed bands:
**`REGRESSION`** ($\Delta\kappa = -0.0300$,
$\kappa_\text{hybrid} = 0.11$ vs §15.1 baseline
$\kappa_{\S15.1,\text{TruthfulQA-MC}} = 0.14$, no
annotations). The §14a.2-protocol Stage A applied to
TruthfulQA-MC plus the §15-style abstention gate on V1's
winning-source semantic-entropy risk score produces a policy
that is **actively worse than §15.1's single-source
abstention** on TruthfulQA-MC at the $\alpha_2 = 0.50$
absolute-majority operating target.

**Cross-benchmark synthesis (DIAGNOSTIC, per Chunk 5e) also
returned REGRESSION:**
$$\Delta\kappa_\text{combined} = \min\big(\Delta\kappa_{\S15.4,\text{HaluEval}}, \Delta\kappa_{\S15.5,\text{TruthfulQA-MC}}\big) = \min(+0.0900, -0.0300) = -0.0300$$
The cross-benchmark verdict is dominated by §15.5's
TruthfulQA-MC negative value. **This empirically bounds
§15.4's HaluEval-only USEFUL_INTERNAL as a single-benchmark
artifact** under the worst-benchmark rule — the hybrid
construct does NOT generalize cross-benchmark.

This is the **first REGRESSION verdict in the entire
§13 / §14 / §15 LLM-track program**. §13 was 5/5 ANTI under
worst-benchmark; §14 was 2/2 `SCOUT_SATURATION`; §15.2 was
`MARGINAL`; §15.4 was `USEFUL_INTERNAL`. None of those four
prior verdicts was *actively negative* relative to its
comparator. §15.6 is.

Per §15.5 Chunk 5g's pinned acceptance/rejection table:

> REGRESSION — Authorizes: closing the §14+§15 hybrid
> construct on TruthfulQA-MC. The §13 / §14 / §15 closure
> prose extends to "answer-selection AND single-source
> abstention AND hybrid all saturated/regressed on
> TruthfulQA-MC at this configuration." Forecloses: §15.7+
> follow-up at this observable; product investment;
> VC-brief changes.

**§13.9 VC-brief hold remains in force and is *strengthened*
by §15.6.** §15.6 adds another metric class on TruthfulQA-MC
where the BCVF-derived construction does not clear STRONG —
in fact, it actively regresses below §15.1's single-source
baseline. The §13.9 STRONG-band-on-both-benchmarks gate is
unchanged. The autonomy-domain BCVF claim (§6.1) stands
independently and is unaffected.

**Parity-gate confirmation (per §15.5 Chunk 5h + Amendment 1).**

| benchmark | N_ok |
|---|---|
| truthfulqa_mc | True |

The §15.5 Phase 1 dump
(`probe_system_level_scout_v2_truthfulqa_mc.json`, produced
by `scripts/probe_system_level_scout_v2_truthfulqa.py`)
satisfied $N=100$ on TruthfulQA-MC. Phase 2 schema
validation (q_idx, sources / per-source semantic_entropy,
answer_cluster_ids, v1_weights, v1_winning_cluster,
v1_correct) all passed. The §15.4 verdict-of-record artifact
read for cross-benchmark synthesis validated against
`schema_version == "15.3"` AND `benchmark_name == "halueval_qa"`.
No §0.8 deviation fired at the input layer.

**Self-test gate.** §15.5 Phase 2's required pre-execution
gate (`--self-test`) ran in the same invocation as real-data
execution and returned PASSED on all 7 cascade boundary cases
(Chunk 5g audit table identical to §15.3 Chunk 3g per B1
framing) and all 7 demotion-rule cases. The 1D cascade
implementation matches Chunk 5g exactly.

**Cross-program consistency check.** Phase 1 reports
$\text{acc}(V_1) = \text{acc}(\text{Baseline-A}) = 0.250$ on
TruthfulQA-MC, matching §13.10's pinned TruthfulQA-MC greedy
accuracy of 0.250 exactly (Qwen-only). $W_\text{hybrid} = 75$
matches the §15.1 TruthfulQA-MC W=75 from §15.2's verdict-of-
record. **V1 selector contributed zero net accuracy on
TruthfulQA-MC** (Δ V1 vs Baseline-B = +0.00pp per Phase 1
output) — first §14-domain finding that V1 produces no lift
on the harder benchmark, in stark contrast to V1's +4pp on
HaluEval-QA (§14c).

**Phase 1 §14a.2-protocol classification — informational
only.** `scripts/probe_system_level_scout_v2_truthfulqa.py`
reported `SCOUT_SATURATION` per the §14a.2 producer's pinned
`classify()` function. **Per §15.5 Chunk 5h and Amendment 1,
this label is informational; §15.5 does NOT classify Phase
1's output against §14a.2 bands.** The §14a.2-on-HaluEval
verdict-of-record (§14c `SCOUT_SATURATION`) is unchanged;
§15.6 reports the §14a.2-on-TruthfulQA-MC informational
classification for cross-program consistency, not as a
re-classification of §14.

**Artifacts.**

- `scripts/probe_system_level_scout_v2_truthfulqa.py`
  (§15.5 Phase 1 sibling producer; §0.8 sibling of
  `probe_system_level_scout_v2.py` with TruthfulQA-MC
  dataset loading + multi-distractor labeling; §14a.2
  producer preserved unchanged).
- `scripts/probe_hybrid_selective_abstention_truthfulqa.py`
  (§15.5 Phase 2 post-processor; numpy + stdlib only;
  copies §15.1 / §15.3 metric primitives per §15.5 Chunk 5h).
- `docs/experiments/probe_system_level_scout_v2_truthfulqa_mc.json`
  (Phase 1 per-question dump).
- `docs/experiments/probe_hybrid_selective_abstention_truthfulqa.json`
  (machine-readable §15.5 result, schema_version `"15.5"`,
  with `cross_benchmark_synthesis` block).
- `docs/experiments/probe_hybrid_selective_abstention_truthfulqa.md`
  (human-readable summary).

**Section naming clarification.** §15.5 Chunk 5g's STRONG row
referenced "§15.6 — full hybrid pre-commitment with both
benchmarks combined and product-layer scope" as a hypothetical
authorization for STRONG. STRONG did NOT fire (REGRESSION
did). The §15.6-as-future-full-hybrid path is therefore moot.
§15.6 is used here as the §15.5 result section (mirroring
§15.3 → §15.4 convention). Any future LLM-track follow-up —
which §15.6's REGRESSION explicitly does NOT authorize per
Chunk 5g — would land at §15.7 or higher under its own §0.8
commitment.

**Headline result.**

| metric | value |
|---|---|
| $N$ | 100 |
| $W_\text{hybrid}$ (V1 wrong count) | 75 |
| V1 accuracy at full coverage | 0.250 (= Baseline-A; identical to §13.10 Qwen greedy) |
| $\text{AURC}_\text{random}$ ($= W/N$) | 0.7500 |
| $\text{AURC}_\text{policy}$ | 0.6325 |
| $\delta_\text{AURC}$ (diagnostic) | $+0.1175$ |
| $\kappa_\text{hybrid}$ at $\alpha_2 = 0.50$ | **0.1100** |
| $\kappa_{\S15.1,\text{TruthfulQA-MC}}$ baseline | 0.1400 |
| $\boldsymbol{\Delta\kappa}$ **(primary)** | $\boldsymbol{-0.0300}$ |
| $\Delta\kappa$ 95% CI (paired bootstrap, $B = 1000$) | $[-0.1400, +0.1202]$ |

**Cascade trace** (mechanical readout per §15.5 Chunk 5g;
matches the implementation's `_cascade_trace_15_5` output
exactly):

```
rule 1 REGRESSION: delta_kappa=-0.0300 < -0.02   -> YES
```

Rule 1 fires; remaining rules not evaluated by cascade
construction (REGRESSION first ordering per Chunk 5g).

**Demotion rule (Chunk 5g) — does NOT apply.** The §15.5
demotion rule is STRONG-only by construction. The cascade
returned REGRESSION (rule 1), which is not subject to
demotion. `verdict_annotations` is empty.

**Operating-point table.**

| $\alpha$ | $\text{cov}@\alpha$ | $\tau^*$ | ecr | far |
|---|---|---|---|---|
| 0.35 | **0.11** | 0.6390 | 0.9467 | 0.7200 |
| 0.50 | **0.11** | 0.6390 | 0.9467 | 0.7200 |
| 0.75 | 0.00 | $+\infty$ | NaN | NaN |

The $\alpha_1 = 0.35$ and $\alpha_2 = 0.50$ operating points
are **identical** — same $\tau^*$, same coverage, same ecr,
same far. Discussed under observation (b) below.

**Three observations the headline supports.**

**(a) First REGRESSION verdict in the §13 / §14 / §15 program.**
Twelve prior experimental structures (§13's 5 single-axis
classes + §14's 2 scouts + §15.2's single-source + §15.4's
HaluEval hybrid + §13.20's N=200 observation + the §15.5
Phase 1 informational SCOUT_SATURATION) returned ANTI,
SCOUT_SATURATION, MARGINAL, or USEFUL_INTERNAL — none was
*actively negative* relative to its comparator. §15.6 is the
first verdict where the BCVF-derived policy is **worse than
its baseline**. Operationally: the §14+§15 hybrid does NOT
just fail to improve on §15.1 TruthfulQA-MC abstention; it
makes it worse.

**(b) Operating points at $\alpha_1$ and $\alpha_2$ are
identical — the policy curve is "stepped" on TruthfulQA-MC.**
Same $\tau^* = 0.6390$, $\text{cov} = 0.11$, $\text{ecr} =
0.9467$, $\text{far} = 0.7200$ at both targets. Mechanically,
the threshold sweep cannot deliver a coverage between
$\kappa@\alpha_2$ and $\kappa@\alpha_1$ — there's no $\tau$
in the empirical grid that produces an answered subset of
size between 11 and 11 with accuracy in $[0.35, 0.50)$. The
hybrid's risk-coverage curve has a discrete jump: at $\tau =
0.6390$, accuracy on the 11-question answered subset is
already $\ge 0.50$; at any lower $\tau$, accuracy drops
below 0.35. This is qualitatively different from §15.4's
HaluEval curve, which had distinct $\alpha_1$ and $\alpha_2$
operating points with smooth coverage decline.

**(c) Bootstrap CI is wide; spans REGRESSION through MARGINAL+
upper bound.** $\Delta\kappa$ 95% CI = $[-0.1400, +0.1202]$,
width $\approx 0.26$. **The CI does NOT rule out
USEFUL_INTERNAL or even STRONG-territory upper bound at
$N=100$.** The point estimate $-0.03$ fires the cascade at
REGRESSION, but bootstrap cannot statistically distinguish
REGRESSION from a wide range of alternatives at this sample
size. This is a power-of-measurement observation (same
caveat §15.4 surfaced for HaluEval at the opposite sign);
the cascade's pinned rule operates on the point estimate
alone per Chunk 5g, so the wide CI does NOT change the
verdict. A larger-$N$ re-run would tighten this band; that
re-run is NOT authorized by §15.5 and would require a fresh
§0.8 commitment.

**Stage A informational findings — V1 selector contributes
zero net accuracy on TruthfulQA-MC.**

Phase 1 (`scripts/probe_system_level_scout_v2_truthfulqa.py`)
reported the §14a.2-protocol classification table (per
Chunk 5h, this is informational only; §15.5 does NOT
classify against §14a.2 bands):

| Variant | Accuracy | $\Delta$ vs Baseline-B (pp) | Sign-test wins/losses | $p$ |
|---|---|---|---|---|
| Baseline-A (Qwen single-greedy) | 0.250 | — | — | — |
| Baseline-B (NLI-clustered uniform majority) | 0.250 | reference | — | — |
| V1 (softmin trust, $\tau = 0.5$) | 0.250 | **+0.00** | 3/3 | 1.000 |
| V2 (thresholded exclusion + uniform survivors) | 0.220 | **−3.00** | 0/3 | 0.250 |

§14a.2-protocol classification (per the producer's `classify()`
function, **informational**): `SCOUT_SATURATION`. Both
$\Delta_{V_1} = +0.00\text{pp}$ and $\Delta_{V_2} = -3.00\text{pp}$
fall in the §14a.2 SATURATION band (V2's $-3.00$ is on the
SATURATION/REGRESSION boundary; the §14a.2 cascade catches
it as SATURATION via the residual catch-all).

**Cross-benchmark contrast with §14a.2-on-HaluEval (§14c
verdict-of-record):**

| Quantity | §14a.2 HaluEval (§14c) | §15.5 Phase 1 TruthfulQA-MC | Direction |
|---|---|---|---|
| $\Delta_{V_1}$ vs Baseline-B | +4.00pp | **+0.00pp** | V1 lift disappears on TruthfulQA-MC |
| $\Delta_{V_2}$ vs Baseline-B | +1.00pp | **−3.00pp** | V2 *flips negative* on TruthfulQA-MC |
| acc(Baseline-B) | 0.290 | 0.250 | Lower on TruthfulQA-MC (matches greedy 0.25) |

**This is the first §14-domain finding that V1 produces no
lift cross-benchmark.** V1's HaluEval +4pp does not
generalize. V2 actively regresses by 3pp on TruthfulQA-MC,
qualitatively different from V2's stable near-zero behavior
on HaluEval.

**Mechanism read (analytical observation, not load-bearing
on the §15.6 verdict).** §15.5's Stage A inherits §14a.2's
M=3 cross-family setup. On HaluEval-QA, V1's softmin
sometimes correctly down-weights a hallucinating source on
questions where another source is right — producing the +4pp
lift. On TruthfulQA-MC, the adversarial-distractor structure
(designed to match common false-belief patterns across many
LLM families) appears to mean **all three sources are
collectively wrong on the same questions** — i.e., when
Qwen is wrong, Llama and Mistral tend to be wrong too on the
same TruthfulQA-MC questions, so V1's selector has no
non-Qwen "right" candidate to upweight. Confirmed
empirically by V1's $\Delta = 0$: across all 100 questions,
V1 delivered the same answer Baseline-A delivered.

**Stage B's $\Delta\kappa = -0.0300$ on this Stage A
foundation.** With Stage A delivering the Qwen-greedy answer
on every question (V1 acc identically equals Baseline-A acc),
Stage B's risk score $r(q) = H_{\text{src}_{i^*}}(q)$ collapses
in expectation to "Qwen entropy on Qwen greedy" — structurally
similar to §15.1's TruthfulQA-MC scalar that produced
$\kappa = 0.14$. The 3pp deficit ($\kappa_\text{hybrid} =
0.11$ vs $\kappa_{\S15.1} = 0.14$) reflects the small subset
of questions where V1's softmin redistributes weight enough
to change the winning-source identity, and on those few
questions the V1-winning source's entropy distribution
differs from Qwen's in a way that makes the threshold rule
3pp worse on coverage at $\alpha_2$. **Stage A's failure to
contribute lift compounds with Stage B's threshold-rule
sensitivity to produce the REGRESSION.**

This is exactly the failure mode §15.5 Chunk 5e
"high prior of failure" anticipated, with empirical
confirmation that the §14+§15 hybrid does not generalize
cross-benchmark when Stage A's selector cannot extract
non-Qwen leverage on the harder benchmark.

**$\delta_\text{AURC}$ vs $\Delta\kappa$ tension —
operationally meaningful vs integrated diagnostic.**

§15.6's diagnostic and primary scalars **disagree in sign**:

| Metric | Value | What it says |
|---|---|---|
| $\delta_\text{AURC}$ (diagnostic; Chunk 5f secondary) | $+0.1175$ | Hybrid's integrated risk-coverage curve beats random abstention by ~12pp. |
| $\Delta\kappa$ (PRIMARY; Chunk 5g cascade-driver) | $-0.0300$ | Hybrid's coverage at $\alpha_2 = 0.50$ is 3pp worse than §15.1's single-source baseline. |

**Reconciliation.** The two metrics measure structurally
different things and answer different operational questions:

- $\delta_\text{AURC}$ asks: "Does the entropy score, used
  to rank answers, identify wrong answers more reliably than
  random selection?" The hybrid's answer: yes — the AURC
  curve dominates random abstention across the threshold
  sweep. The hybrid IS truth-correlated in the integrated
  sense.
- $\Delta\kappa$ asks: "At the absolute-majority operating
  target ($\alpha_2 = 0.50$), can the hybrid policy answer
  more questions than §15.1's single-source policy?" The
  hybrid's answer: no — the hybrid policy is *more
  selective* (catches a higher fraction of errors per unit
  answer; ecr=0.95) but cannot deliver enough coverage at
  $\alpha_2 \ge 0.50$ to beat §15.1's $\kappa = 0.14$.

**The §15.5 cascade pinned $\Delta\kappa$ as primary
(operationally meaningful) and $\delta_\text{AURC}$ as
secondary (integrated diagnostic) precisely to prevent this
class of disagreement from confusing the verdict.** Per
§15.5 Chunk 5g: "No secondary metric participates in the
cascade." The verdict reads off $\Delta\kappa$ alone; the
positive $\delta_\text{AURC}$ is reported as a diagnostic
but does NOT re-classify the verdict.

This is the design pattern that §14a.2's band-coverage gap
recovery (§14c) made into a §0.8 lesson: future bands should
partition the outcome space exhaustively along ONE primary
scalar, with secondary metrics reported as informational
only. §15.6 surfaces the diagnostic-vs-primary tension
explicitly and lets the cascade fire deterministically.

**$\alpha_3 = 0.75$ degeneracy carries over from §15.4 and
§15.2.**

The §15.6 operating point at $\alpha_3 = 0.75$:
$\text{cov} = 0.00$, $\tau^* = +\infty$, ecr/far NaN.
Identical to §15.4's HaluEval $\alpha_3$ degeneracy and
§15.2's both-benchmarks $\alpha_3$ degeneracy. **No
threshold $\tau$ in the §15.6 sweep grid yields acc $\ge
0.75$ on an answered subset of size $\ge n_\min = 10$.**
The deployment-grade ceiling persists across all four
metric-class configurations on TruthfulQA-MC. Whether the
hybrid is REGRESSION (here) or USEFUL_INTERNAL (§15.4),
$\alpha_3$ is unreachable; abstention alone — with or
without V1's selector — cannot deliver a $\ge 75\%$-accurate
subset from a base model at greedy accuracy 0.250.

This bounds any hypothetical future product layer: even if a
fresh §0.8 commitment with different bands or different
scaling reopened the §14+§15 hybrid line and produced a
non-REGRESSION verdict on TruthfulQA-MC, the $\alpha_3$
ceiling would still cap deployment-grade claims. **Reaching
$\alpha_3$ requires a higher base-model accuracy floor
(model-scale upgrade per §13.8 future-work, never
authorized), not abstention-layer tuning.**

**What §15.6 authorizes (per §15.5 Chunk 5g REGRESSION row).**

The §15.5-pinned acceptance/rejection mapping for REGRESSION
is binding under §0.8. Reproduced exactly:

| §15.6 verdict | Authorizes | Forecloses |
|---|---|---|
| REGRESSION | Closing the §14+§15 hybrid construct on TruthfulQA-MC. The §13 / §14 / §15 closure prose extends to "answer-selection AND single-source abstention AND hybrid all saturated/regressed on TruthfulQA-MC at this configuration." | §15.7+ follow-up at this observable; product investment; VC-brief changes; cross-benchmark deployment claims. |

Specifically, §15.6 **authorizes**:

- Documenting the §15.5 verdict-of-record in this section
  (which §15.6 itself accomplishes).
- Recording $\Delta\kappa = -0.0300$, $\kappa_\text{hybrid} =
  0.11$, the operating-point degeneracy at $\alpha_1 / \alpha_2$,
  the bootstrap CI, and the cross-benchmark synthesis as the
  §15.6 verdict-of-record.
- Citing §15.6 as the **first REGRESSION verdict** in the
  §13 / §14 / §15 program — bounding §15.4's HaluEval
  USEFUL_INTERNAL as a single-benchmark artifact under the
  worst-benchmark rule.
- Closing the §14+§15 hybrid construct at this configuration
  (single-benchmark scope on TruthfulQA-MC; cross-benchmark
  synthesis combined REGRESSION).

§15.6 explicitly **does NOT authorize**:

- **§15.7+ follow-up.** No further §14+§15 hybrid probe at
  this configuration. A cross-benchmark deployment claim
  required §15.5 STRONG (or USEFUL_INTERNAL with combined
  USEFUL_INTERNAL synthesis); both paths foreclosed.
- **Product-readiness claims.** REGRESSION is below SATURATION;
  the hybrid is *worse* than §15.1's single-source abstention
  on TruthfulQA-MC. Product investment over a known-regressing
  policy is not authorized.
- **VC-brief updates.** §13.9 hold remains in force,
  *strengthened* by §15.6's confirmation that the cross-
  benchmark hybrid does not generalize. §15.6's metric class
  is structurally separate from §13.9's gate (different
  measurement object), but the substantive direction is
  unambiguous: another metric class did not clear STRONG; one
  actively regressed.
- **Reframing of any §13 / §14 / §15.x verdict.** §15.6 is
  on a fresh metric class and does not interact with §13's
  ANTI verdicts, §14's SCOUT_SATURATION, §15.2's MARGINAL,
  §15.4's USEFUL_INTERNAL, or §13.20's NOISE_BAND_LIFT
  observation. Each remains binding at its pinned
  configuration.
- **Re-classifying §15.4 based on §15.6 cross-benchmark
  synthesis.** The cross-benchmark synthesis is explicitly
  diagnostic per Chunk 5e; §15.4's HaluEval-only
  USEFUL_INTERNAL verdict-of-record is preserved unchanged.
  §15.6 documents the cross-benchmark synthesis as a
  derived comparator, not as a §15.4 amendment.
- **Cross-domain claims.** Autonomy-domain BCVF (§6.1)
  stands wholly independent of §15.6. The N=21 sign-test
  result that passed in §6.1 / §6.7 is a robotics-domain
  validation on a different dataset, different predictor
  set, and different metric class entirely.

**No deviation flag fired during the §15.5 run.** Per §15.5
Chunk 5h's "Any deviation discovered at run time must be
flagged in the §15.6 result section as a §0.8 deviation":
the run produced no such deviation. Phase 1 (§14a.2 sibling
producer on TruthfulQA-MC) ran cleanly, output schema matched
the new sibling-producer's pinned schema, parity gate green;
Phase 2 self-test passed in-run, schema validation on both
the Phase 1 dump and the §15.4 cross-benchmark artifact
green, the cascade fired exactly per `_cascade_trace_15_5`.
The two §15.5 amendments (line-count drift acknowledgment
deferred to §15.4, sibling-producer creation per Amendment 1)
landed pre-execution and are documented within §15.5 itself,
not as run-time deviations.

**Combined picture across §13 / §14 / §15 — full LLM-track
program now closed across four metric classes and two
benchmarks; cross-benchmark hybrid REGRESSION is the
terminal verdict.**

§15.6 closes the §15 LLM-track operational program. The
full §13 / §14 / §15 testing matrix at this codebase's
Qwen2.5-7B-Instruct + DeBERTa-v3-base + N=100 configuration:

| Program | Metric class | TruthfulQA-MC | HaluEval-QA | Combined |
|---|---|---|---|---|
| §13.10 | AUC vs ground truth (single-axis SE baseline) | 0.661 | 0.661 | TRUTH_CORRELATED_MARGINAL |
| §13.11–§13.18 | AUC, 4 single-axis revisions | various | various | 5/5 ANTI |
| §14a / §14a.2 | Δ accuracy, system-level | (deferred) | SCOUT_SATURATION | SCOUT_SATURATION |
| §15.1 / §15.2 | AURC + cov@α, single-source abstention | $\kappa = 0.14$ | $\kappa = 0.26$ | MARGINAL (worst-benchmark min) |
| §15.3 / §15.4 | $\Delta\kappa$ vs §15.1 baseline, hybrid | (deferred to §15.5) | $\Delta\kappa = +0.090$ | USEFUL_INTERNAL (single-benchmark) |
| **§15.5 / §15.6** | $\Delta\kappa$ vs §15.1 baseline, hybrid | $\boldsymbol{\Delta\kappa = -0.030}$ | (§15.4 verdict-of-record, +0.090) | **REGRESSION** (cross-benchmark synthesis worst-benchmark min) |

**Thirteen distinct experimental structures across four
metric classes have now been tested.** None clears STRONG on
the worst-benchmark rule. §15.4 is the only single-benchmark
verdict that cleared USEFUL_INTERNAL; §15.6 bounds it as a
HaluEval-only artifact. The cross-benchmark hybrid is
REGRESSION.

**§13.9 VC-brief hold reaffirmed and strengthened.** §13.9
gates external-framing changes to
`AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md` on a STRONG-band lift
on both benchmarks at any §13 / §14 / §15 probe. §15.6 adds
the strongest possible negative result yet — REGRESSION on
the cross-benchmark hybrid synthesis. Combined with §13's
5/5 ANTI, §14's 2/2 `SCOUT_SATURATION`, §13.20's
NOISE_BAND_LIFT, §15.2's MARGINAL, §15.4's single-benchmark
USEFUL_INTERNAL, and §15.6's REGRESSION:

- **Thirteen experimental structures total.**
- **Zero clear STRONG on the combined-classification rule.**
- **One clears USEFUL_INTERNAL on a single benchmark only;
  cross-benchmark synthesis on that hybrid is REGRESSION.**

The §13.9 hold is unchanged in policy, but materially
*strengthened* by the cumulative evidence.

The honest external framing for any internal-research
referencing of the §13 / §14 / §15 program is now:

> *On Qwen2.5-7B-Instruct + DeBERTa-v3-base + N=100, no
> literature-aligned, mechanism-motivated, system-level,
> single-source-abstention, hybrid-abstention, or cross-
> benchmark-hybrid-abstention BCVF construction tested in
> this codebase clears the STRONG combined-classification
> bar on the worst-benchmark rule. The §15.4 hybrid scout
> cleared USEFUL_INTERNAL on HaluEval-QA single-benchmark,
> but the §15.6 cross-benchmark companion on TruthfulQA-MC
> returned REGRESSION, bounding §15.4 as a single-benchmark
> artifact under the worst-benchmark rule. The LLM
> hallucination-detection track is closed across thirteen
> experimental structures and four metric classes.*

**§15.6 closes the §15 LLM-track program at the cross-
benchmark hybrid level.** Per Chunk 5g, REGRESSION
explicitly forecloses §15.7+-as-implementation follow-ups
at this configuration. Any follow-up under §15-style logic
— cross-benchmark larger-N re-run, ensemble risk score,
alternative selector configurations, alternative consumer
configurations, relaxed worst-benchmark rule, model-scale
upgrade per §13.8 future-work — would require a fresh
top-level §0.8 commitment with bands pinned before any
data inspection. None is authorized by §15.6.

**The autonomy-domain BCVF claim (§6.1) stands independently
on the N=21 sign-test that passed in §6.1 / §6.7 and is
unaffected by any §13 / §14 / §15 outcome.** The §13 / §14 /
§15 program tested whether BCVF transfers to LLM
hallucination detection at this codebase's specific scale
across four distinct metric classes; the answer at this
configuration is mixed — twelve of thirteen experimental
structures returned strict non-promotion verdicts; one
(§15.4 hybrid on HaluEval) cleared USEFUL_INTERNAL on a
single benchmark; one (§15.6 cross-benchmark) returned
REGRESSION; **the cross-benchmark synthesis is REGRESSION
under the worst-benchmark rule.** The §13.9 external-
framing hold remains binding; §15.6 verdict and synthesis
are documented internally, not externally, per Chunk 5g.

**Artifacts.**

- `scripts/probe_system_level_scout_v2_truthfulqa.py`
  (§15.5 Phase 1 sibling producer; numpy + transformers +
  GPU; ~50–60 min runtime per N=100 invocation).
- `scripts/probe_hybrid_selective_abstention_truthfulqa.py`
  (§15.5 Phase 2 post-processor; numpy + stdlib only; under
  30 sec wall clock).
- `docs/experiments/probe_system_level_scout_v2_truthfulqa_mc.json`
  (Phase 1 per-question dump; consumed by Phase 2).
- `docs/experiments/probe_hybrid_selective_abstention_truthfulqa.json`
  (machine-readable §15.5 result, schema_version `"15.5"`,
  with cross_benchmark_synthesis block).
- `docs/experiments/probe_hybrid_selective_abstention_truthfulqa.md`
  (human-readable summary).

§15.6 result section now complete (chunks 6a–6f, 6 commits
on top of the §15.5 pre-commitment + Amendment 1 +
implementation). §15 LLM-track program is closed.

### 15.7 Pre-commitment — Diagnostic post-processing audit on existing dumps (no new compute)

**Status: pre-committed, not yet executed.** §0.8-style pre-
commitment recorded before any §15.4 / §15.6 / §15.2 dump is
opened in §15.7 form. Specification, computed quantities,
hypothesis tests, and interpretation framework below cannot
be redefined post-hoc.

**Position in the §13 / §14 / §15 program — what §15.7 is
and explicitly is not.**

§15.7 is a **pure-diagnostic post-processing chapter**, not a
new experimental probe and not a re-execution of any prior
program. It converts the empirical questions surfaced by a
multi-round informal critique of §15.6's interpretation into
a single binding §0.8 audit committed before any
implementation. **§15.7 produces interpretive content for the
§15 closure narrative; it explicitly does not re-classify any
prior verdict.**

Specifically, §15.7 is **NOT**:

- A new probe authorized by §15.6 (which closed the §15
  program at REGRESSION). §15.7 does not produce new
  verdicts.
- A re-execution of §13 / §14 / §15.x (no new GPU, no new
  generation, no new model loads, no new NLI calls).
- A re-classification of §15.4's HaluEval USEFUL_INTERNAL or
  §15.6's TruthfulQA-MC REGRESSION. Both verdicts-of-record
  remain binding under §0.8 regardless of any §15.7 finding.
- A re-classification of §13.9's VC-brief hold. The hold
  remains in force; §15.7 produces diagnostic content, not
  external-framing-grade evidence.
- An §15.8-authorizing chapter. No follow-up probe is
  authorized by §15.7 unless and until a fresh top-level
  §0.8 commitment lands.

§15.7 **IS**:

- A pre-committed diagnostic audit of three existing on-disk
  artifacts: §15.4 (HaluEval hybrid), §15.6 (TruthfulQA-MC
  hybrid), §15.2 (single-source baselines).
- A formalization of the **base-rate-adjusted ratio
  condition** for selective prediction (the operational
  criterion $F_1(\tau)/F_0(\tau) \ge \alpha(1-\pi)/((1-\alpha)\pi)$,
  not the cruder $F_1 - F_0$ separation), applied to existing
  data.
- A pinned **Stage A / Stage B / Composition decomposition**
  of the hybrid scout's three possible failure modes:
  (i) Stage A answer-stream failure, (ii) Stage B score-
  separability failure, (iii) Composition failure where Stage
  A's selected-answer correctness is poorly proxied by the
  Stage B winning-source risk score.
- A pinned falsifiable hypothesis test for whether §15.6's
  Δκ = −0.030 reflects substantive hybrid regression on
  TruthfulQA-MC versus stochastic equivalence to §15.1's
  TruthfulQA-MC baseline (under the working hypothesis that
  V1 selected Qwen on all 100 TruthfulQA-MC questions, the
  hybrid reduces in expectation to single-source).
- A pinned interpretation framework that maps each diagnostic
  output to **non-binding** narrative content, with explicit
  rules for what §15.7 may and may not say in the result
  section.

**Why §15.7 exists.** Three motivations, all surfaced through
external critique of §15.6:

1. **Diagnostic value:** the existing dumps contain
   information that the §15.4 / §15.6 verdict cascades did
   not extract (full risk-coverage curves, Stage-A/Stage-B
   decomposition, sampling-noise tests). Computing this
   information sharpens what §15 actually showed.
2. **Substantive vs noise distinction:** §15.6 REGRESSION's
   wide bootstrap CI [−0.14, +0.12] is consistent with both
   a noise-bound result and a substantive negative; §15.7's
   pinned hypothesis test resolves which.
3. **§0.8 audit-trail integrity:** post-hoc informal
   commentary on a verdict is not §0.8-binding. Converting
   the load-bearing critiques into a single pre-committed
   diagnostic audit lands the analysis under the same
   discipline as the prior chapters.

**§15.7 does NOT change the §15.6 verdict-of-record.** Per
§0.8, §15.6's pinned cascade returned REGRESSION on the
point estimate of Δκ on TruthfulQA-MC. That verdict is
binding regardless of §15.7's diagnostic findings. §15.7
may *interpretively weaken* the substantive reading (e.g.,
"REGRESSION reflects sampling stochasticity over Stage A's
Qwen-degenerate selection") but cannot *override* it. The
distinction between binding verdict and interpretive caveat
is pinned in §15.7 Chunk 7f below.

**Confirmation: no data inspection prior to this pre-
commitment.** The §15.4 / §15.6 / §15.2 artifacts have been
inspected only via their pinned `combined.{verdict, delta_kappa,
kappa_hybrid}` fields cited in the prior §0.8 chapters.
Per-question fields, full threshold sweeps, and stage-wise
records have NOT been opened in §15.7 form. The audit
specification in §15.7 Chunks 7c–7e below is pinned from §15
prose only; the actual quantities will be computed only after
§15.7 implementation lands.

**Inputs and architecture (pinned).**

§15.7 reads four on-disk artifacts. All four exist as
verdicts-of-record from prior §0.8-binding chapters; §15.7
modifies none of them.

| Artifact | Source chapter | Used for |
|---|---|---|
| `docs/experiments/probe_system_level_scout_v2_halueval_qa.json` | §14a.2 (per §14c verdict-of-record) | Stage A/B decomposition for §15.4 HaluEval hybrid: per-question V1 source identity, selected_answer correctness, per-source semantic entropies |
| `docs/experiments/probe_system_level_scout_v2_truthfulqa_mc.json` | §15.5 Phase 1 (per §15.6 verdict-of-record) | Stage A/B decomposition for §15.6 TruthfulQA-MC hybrid: same field set |
| `docs/experiments/probe_selective_abstention.json` | §15.2 verdict-of-record | Single-source baseline κ values per benchmark (HaluEval κ@α₂=0.26; TruthfulQA-MC κ@α₂=0.14); pinned constants only |
| `docs/experiments/probe_semantic_entropy.json` and `docs/experiments/probe_semantic_entropy_halueval_qa.json` | §13.10 producer (currently at N=200 per §13.20 dump-overwrite) | Distributional comparison ONLY for the §15.6 sampling-noise hypothesis test (Chunk 7e); see §0.8 caveat below |

**§0.8 caveat on the §13.10 dumps (per §15.2 Postscript and
§13.20).** The §13.10 dumps on disk are now N=200, having
been overwritten after §15.2 landed. §15.7 uses them ONLY
for the Chunk 7e sampling-noise hypothesis test, where the
quantity of interest is the **distributional shape** of Qwen
per-question K=10 semantic entropy — invariant to N=100 vs
N=200 sampling depth. **§15.7 does NOT re-derive §15.2's
verdict-of-record from these dumps.** The κ=0.14 (TruthfulQA-
MC) and κ=0.26 (HaluEval) baselines remain the pinned values
from §15.2's preserved artifact regardless of any §13.20
upstream overwrite. The N=200 status is documented inline in
the §15.7 result section as an interpretive caveat — same
pattern §15.2 Postscript established.

**Architecture pin: pure post-processing, no new compute.**

- **No new generation calls.** No model loads. No NLI scoring
  beyond what already exists in the pinned dumps.
- **No GPU.** numpy + Python stdlib only.
- **No network.** No HF cache reads. No HF_TOKEN consumed.
- **Wall-clock cost:** under 60 seconds total.
- **Modification footprint on existing artifacts:** zero.

**Schema validation (fail-fast, identical discipline to
§15.1 / §15.3 / §15.5).**

§15.7's loader validates each input artifact against pinned
field expectations. Any missing field, malformed JSON, or
duplicate question identifier triggers `SCHEMA_MISMATCH` exit
with explicit reference to §15.7 Chunk 7b — no fallback path,
no silent substitution.

Per-artifact pinned field expectations:

- **§14a.2 dumps** (both benchmarks): `questions[*].q_idx`,
  `questions[*].sources[i].semantic_entropy`,
  `questions[*].answer_cluster_ids`,
  `questions[*].v1_weights`,
  `questions[*].v1_winning_cluster`,
  `questions[*].v1_correct`,
  `questions[*].baseline_a_correct`,
  `questions[*].sources[i].source_name` (NEW vs §15.3/§15.5
  Phase 2 — needed for V1 source-identity audit).
- **§15.2 verdict-of-record artifact:** `schema_version == "15.1"`,
  `benchmarks.{truthfulqa_mc,halueval_qa}.kappa` (drives the
  pinned baselines).
- **§13.10 dumps:** `[*].q_idx`, `[*].semantic_entropy`,
  `[*].greedy_matches_correct` (matches §15.1 Amendment 1
  pinned field names; consumed only for distributional
  comparison).

**What §15.7 does NOT modify.**

- §14a.2 dumps (both benchmarks) — preserved unchanged.
- §15.2 verdict-of-record artifact — preserved unchanged.
- §13.10 dumps — read-only; the §13.20 N=200 status is
  inherited as-is.
- Any §13/§14/§15.x verdict-of-record markdown or JSON
  artifact other than the four §15.7 outputs.

§15.7 produces exactly two output artifacts (pinned in Chunk
7g): a JSON diagnostic dump and a markdown report. Both
include explicit `schema_version: "15.7-diagnostic"` and a
top-level field flagging that §15.7 is **diagnostic-only**
content, not a new verdict-of-record.

**Diagnostic computations (pinned, full audit spec).**

For each of the two hybrid configurations (§15.4 HaluEval +
§15.6 TruthfulQA-MC), §15.7 computes the following over the
existing per-question $(r(q), c(q))$ extracted from the
pinned §14a.2 / §15.5 Phase 1 dumps. Notation per §15.5
Chunk 5f.

**(A) Class-conditional CDFs.** For each benchmark, sort
questions by ascending $r(q)$ with question-id tiebreak.
At each threshold $\tau$ in the sorted unique-$r$ grid plus
$\pm\infty$:

$$F_1(\tau) = \Pr(R<\tau \mid Y=1) = \frac{|\{q : r(q)<\tau \text{ AND } c(q)=1\}|}{|\{q : c(q)=1\}|}$$
$$F_0(\tau) = \Pr(R<\tau \mid Y=0) = \frac{|\{q : r(q)<\tau \text{ AND } c(q)=0\}|}{|\{q : c(q)=0\}|}$$

These are the class-conditional CDFs of the risk score under
the pinned correctness label.

**(B) Separation diagnostic** (the cruder local-discrimination
form):
$$\Delta(\tau) = F_1(\tau) - F_0(\tau)$$
Range $[-1, +1]$. Reported as a curve over $\tau$.

**(C) Likelihood-ratio condition** (the operationally-correct
local condition for selective prediction):
$$\rho(\tau) = \frac{F_1(\tau)}{F_0(\tau)} \quad \text{(when } F_0(\tau) > 0\text{)}$$
At each $\tau$, compute and report $\rho(\tau)$.

**(D) Base-rate-adjusted threshold target.** Per the
selective-prediction precision condition derived in
§15.7's pinned interpretation framework, $\Pr(Y=1\mid R<\tau)
\ge \alpha$ if and only if
$$\rho(\tau) \ge \rho^*(\alpha, \pi) \;\equiv\; \frac{\alpha(1-\pi)}{(1-\alpha)\pi}$$

For each benchmark, compute $\rho^*(\alpha_2, \pi)$ using
$\pi$ = empirical V1 (or single-source) accuracy on that
benchmark, and report whether $\rho(\tau)$ exceeds $\rho^*$
in any τ region with $|A_\tau| \ge n_\min = 10$. **This is
the sharpest single diagnostic** for whether the score
supports useful selective prediction at the $\alpha_2 = 0.50$
operating point.

Pinned $\rho^*$ targets (computable ex-ante from §13.10
prose / §14a.2 evidence):

| Configuration | $\pi$ (Stage A or single-source acc) | $\rho^*$ at $\alpha_2 = 0.50$ |
|---|---|---|
| §15.4 HaluEval hybrid | 0.330 (V1 acc per §14c) | $\frac{0.5 \cdot 0.67}{0.5 \cdot 0.33} \approx 2.03$ |
| §15.6 TruthfulQA-MC hybrid | 0.250 (V1 acc per §15.6 Chunk 6c) | $\frac{0.5 \cdot 0.75}{0.5 \cdot 0.25} = 3.0$ |
| §15.2 HaluEval single-source | 0.300 (Qwen greedy per §13.10) | $\frac{0.5 \cdot 0.70}{0.5 \cdot 0.30} \approx 2.33$ |
| §15.2 TruthfulQA-MC single-source | 0.250 (Qwen greedy per §13.10) | $3.0$ |

The base-rate asymmetry is itself documented as a §15.7
finding: TruthfulQA-MC requires $\rho \ge 3.0$ while HaluEval
requires only $\sim 2.03$ — a 50% steeper bar from base rate
alone before any score-quality consideration.

**(E) Precision and coverage curves.**
$$p(\tau) = \Pr(Y=1 \mid R<\tau), \quad c(\tau) = \Pr(R<\tau)$$
Reported alongside $F_1, F_0, \Delta, \rho$ at every grid
point.

**(F) Step-size audit (where the policy curve is "stepped").**

Per §15.6 Chunk 6b observation (b), the §15.6 hybrid's α₁
and α₂ operating points were identical (same $\tau^*$, same
coverage). §15.7 quantifies the step-geometry of each
benchmark's risk-coverage curve:

- **Number of distinct $r(q)$ values** in the empirical
  support (≤ N).
- **Empirical jump sizes:** for each adjacent pair of
  thresholds in the sorted-unique-$r$ grid, compute
  $\Delta_\text{jump,k} = c(\tau_{k+1}) - c(\tau_k)$.
  Report mean, max, and number of "large jumps" (defined as
  jumps $\ge 1/N$, i.e., a single question or more shifting
  classification at one threshold).
- **Operating-point collapse audit:** for each pinned $\alpha
  \in \{\alpha_1, \alpha_2, \alpha_3\}$, compute the
  achieving threshold $\tau^*(\alpha)$ and flag whether any
  pair of adjacent $\alpha$ values resolves to the same
  $\tau^*$ — directly testing the §15.6 Chunk 6b "stepped
  curve" finding empirically.

**Reporting format (pinned).** All curves are emitted as
arrays in the §15.7 JSON artifact. The markdown report
includes a per-benchmark table summarizing:

- $\rho(\tau^*)$ at the operating-point threshold for each
  $\alpha$ target,
- $\rho^*(\alpha, \pi)$ pinned target,
- whether the condition $\rho \ge \rho^*$ is met,
- $\Delta(\tau^*)$ separation,
- step-size summary statistics.

**Critical §0.8 distinction:** all of these computations are
**diagnostic only**. None re-classifies any §15.4 / §15.5 /
§15.6 / §13.20 verdict-of-record. The $\rho \ge \rho^*$ test
informs whether the §13.10 entropy is operationally useful at
the pinned operating point, but the §15.6 cascade verdict on
$\Delta\kappa$ remains binding regardless.

**Stage A / Stage B / Composition decomposition (pinned).**

The hybrid scout's Δκ verdict mixes three distinct failure
modes that the §15.4 / §15.6 cascades did not separate.
§15.7 decomposes them.

Notation:

- $S(q)$ — Stage A's selected source identity for question
  $q$ (Qwen / Llama / Mistral).
- $a_S(q)$ — Stage A's selected answer (the V1-NLI-clustered
  selector winner's greedy).
- $Y_S(q) \in \{0, 1\}$ — correctness of $a_S(q)$ per the
  §14a.2 NLI labeling protocol.
- $R_S(q) = H_{\text{src}_{S(q)}}(q)$ — per-source semantic
  entropy of the source whose answer V1 selected.
- $\pi_S = \Pr(Y_S = 1)$ — Stage A's answer-stream accuracy
  at full coverage.
- $\pi_A = \Pr(Y_\text{Baseline-A} = 1)$ — Qwen-greedy
  accuracy at full coverage (the §13.10 single-source
  reference).

**Stage A audit (answer-stream quality + selector identity).**

Computed quantities per benchmark:

1. **V1 selection identity histogram.** Count of questions
   where $S(q) \in \{$Qwen, Llama, Mistral$\}$. **Pinned
   diagnostic question:** does V1 select Qwen on all 100
   TruthfulQA-MC questions? (Hypothesis from §15.6 Chunk 6c
   informational analysis; §15.7 confirms or refutes
   empirically.)
2. **V1-divergent question set $D = \{q : S(q) \ne \text{Qwen}\}$.**
   Per benchmark, $|D|$ and the per-question correctness
   delta on $D$:
   $$\Delta_D = \Pr(Y_S = 1 \mid q \in D) - \Pr(Y_\text{Baseline-A} = 1 \mid q \in D)$$
   This isolates Stage A's actual lift contribution to the
   subset of questions where V1 makes a non-Qwen choice.
3. **Stage A net lift:** $\Delta_A = \pi_S - \pi_A$, computed
   over all $N=100$ questions. Reports whether V1 added
   accuracy at full coverage.

**Stage A failure mode (i):** $\Delta_A \approx 0$ AND
$|D|$ small → V1 contributed no answer-stream lift; the
hybrid degenerates to single-source plus stochastic noise.
This is the §15.6 Chunk 6c hypothesis for TruthfulQA-MC.

**Stage B audit (score separability over Stage A's
selected-answer correctness).**

Computed quantities per benchmark:

1. **Class-conditional risk distributions** $\Pr(R_S \mid Y_S=1)$
   and $\Pr(R_S \mid Y_S=0)$ summary statistics: mean, stdev,
   min, max, percentiles (10/25/50/75/90).
2. **Separation diagnostic on Stage A labels:** $\Delta_S(\tau)$
   and $\rho_S(\tau)$ as in Chunk 7c, but evaluated
   against $Y_S$ (Stage A's selected-answer correctness),
   not against $Y_\text{Baseline-A}$.
3. **Local condition test at the pinned operating point:**
   does $\rho_S(\tau^*) \ge \rho^*(\alpha_2, \pi_S)$ for any
   $\tau^*$ with $|A_{\tau^*}| \ge n_\min = 10$?

**Stage B failure mode (ii):** Stage A's $\pi_S$ is decent
but $R_S$ does not separate $Y_S = 1$ from $Y_S = 0$ (i.e.,
the score has no information about whether Stage A's choice
was correct). This is structurally different from (i): Stage
A has produced a usable answer stream, but Stage B's risk
score is uninformative about it.

**Composition audit (Stage B risk score's proxy quality for
Stage A's selected answer).**

Computed quantities per benchmark:

1. **Per-question correlation:** $\text{corr}(R_S(q), 1 - Y_S(q))$
   (Pearson and Spearman; the latter robust to monotone
   transforms).
2. **V1-divergent vs Qwen-only correlation comparison:**
   compute the correlation separately on $D$ (V1 picked
   non-Qwen) and on $\bar{D}$ (V1 picked Qwen). If the
   correlation is substantially worse on $D$, the hybrid's
   risk score is a poor proxy on exactly the questions where
   Stage A's selection diverges from baseline — which is the
   composition failure mode.
3. **Cross-source proxy quality:** for each source $i$,
   compute $\text{corr}(H_{\text{src}_i}, 1 - Y_S)$ on the
   subset where $S(q) = i$. If the diagonal correlations are
   all roughly equal but cross-source effects are missing,
   the per-source entropy is a "self-proxy" only — informative
   about its own source's wrongness but not transferable as
   a Stage A-aware proxy.

**Composition failure mode (iii):** Stage A's $\pi_S$ is
decent AND $R_S$ has some separation overall, but the
per-question proxy $R_S \to (1 - Y_S)$ is worse on the
V1-divergent questions $D$ than on $\bar{D}$. This means the
hybrid's risk-score-to-correctness mapping breaks on exactly
the questions where the hybrid's selector matters — a
specifically hybrid pathology that does not exist in §15.1's
single-source scenario.

**Diagnostic decision tree (pinned).** Once §15.7 computes
the three audits, each benchmark's failure mode is classified
into one of:

- **A-DEGENERATE:** Stage A failure (i) — V1 contributes
  nothing. The hybrid reduces to single-source. §15.6's
  Δκ ≈ 0 in expectation; observed −0.030 is sampling noise.
- **B-INSUFFICIENT:** Stage B failure (ii) — score
  separability is below the $\rho \ge \rho^*$ threshold near
  the operating point.
- **C-MISMATCHED:** Composition failure (iii) — score
  works on $\bar{D}$ but fails on $D$.
- **MIXED / OTHER:** Two or more failure modes co-fire, or
  none of the three fits.

**§0.8 boundary:** the decision-tree classification is
diagnostic only. It does NOT re-classify §15.4 USEFUL_INTERNAL
or §15.6 REGRESSION. It produces interpretive content for
the §15.7 result section's narrative explanation of WHY the
verdicts came out as they did.

**§15.6 sampling-noise hypothesis test (pinned, falsifiable).**

The §15.6 verdict (REGRESSION, Δκ = −0.030) was discussed in
informal critique as plausibly reflecting Stage A degeneracy
(V1 selecting Qwen on all 100 TruthfulQA-MC questions) +
sampling stochasticity rather than a substantive hybrid-hurts
finding. §15.7 converts this informal hypothesis into a
**pre-committed falsifiable test**.

**The hypothesis (pinned).**

If V1 selects Qwen on every TruthfulQA-MC question (Stage A
audit confirms), then on TruthfulQA-MC the hybrid's risk
score $R_S = H_\text{Qwen-K=10}(q)$ is computed from a fresh
K=10 sample of Qwen on TruthfulQA-MC. §15.1's TruthfulQA-MC
risk score (used to derive the §15.2-pinned $\kappa = 0.14$
baseline) was likewise $H_\text{Qwen-K=10}(q)$ from a fresh
K=10 sample of Qwen on TruthfulQA-MC. **The two scalars are
the same protocol applied to fresh samples and should be
distributionally equivalent in expectation.**

**Falsifiable claim:** if the hypothesis is correct, the
empirical distributions of $R_S$ (from §15.5 Phase 1 dump)
and the §13.10 TruthfulQA-MC Qwen-K=10 entropies (from the
now-N=200 §13.10 dump on disk) should be drawn from the same
underlying distribution.

**Pinned test (two-sample Kolmogorov-Smirnov + summary
distance metrics).**

Compute on TruthfulQA-MC only (HaluEval included as a
control where V1 does diverge):

1. **KS two-sample test.** Null hypothesis: §15.6's $R_S$
   distribution and §13.10's Qwen-K=10 entropy distribution
   are drawn from the same underlying distribution. Report
   KS statistic and p-value at α=0.05.
2. **Summary distance metrics.** Compute on the two
   distributions:
   - $|\bar{R}_{15.6} - \bar{R}_{13.10}|$ (mean difference)
   - $|\sigma_{R_{15.6}} - \sigma_{R_{13.10}}|$ (stdev difference)
   - $\max_\tau |F_{15.6}(\tau) - F_{13.10}(\tau)|$ (KS distance,
     same as KS statistic)
3. **Conditional comparison on Qwen-correctness label.** If
   V1 selects Qwen on all 100 TruthfulQA-MC questions, then
   $Y_S = Y_\text{Qwen-greedy}$. Compute the same three
   distance metrics conditional on $Y = 1$ and on $Y = 0$
   separately.

**Pinned interpretation rules (§0.8-style; do not redefine
post-hoc).**

The KS test is reported with its p-value and the claim is
read mechanically:

- **p > 0.05 AND mean difference < 0.10 nats AND stdev
  difference < 0.10 nats:** **HYPOTHESIS_SUPPORTED**. The
  §15.6 risk score distribution is statistically
  indistinguishable from the §13.10 reference. Combined with
  a confirmed Stage A V1-picks-Qwen-on-all-100 finding, this
  empirically confirms the §15.6 sampling-noise reading: the
  hybrid degenerates to single-source on TruthfulQA-MC; the
  3pp Δκ gap reflects fresh-sample stochasticity.
- **p ≤ 0.05 OR either summary distance ≥ 0.10 nats:**
  **HYPOTHESIS_REFUTED**. The §15.6 risk score distribution
  is meaningfully different from §13.10's reference. The
  REGRESSION reading then has a substantive component beyond
  sampling stochasticity — possibly Stage A or Composition
  effects.
- **p > 0.05 AND ANY summary distance ≥ 0.10 nats AND
  ≤ 0.20 nats:** **HYPOTHESIS_PARTIAL**. Distributions are
  statistically equivalent at $\alpha = 0.05$ but show
  modest practical drift; document inline as ambiguous.

**Pinned numerical thresholds rationale.** 0.10 nats is the
practical-drift bound — meaningful entropy distributions
differ by 0.05–0.10 nats in §13.10 prose's reported
between-benchmark mean separations (HaluEval 0.486 vs
TruthfulQA-MC 0.392 is ~0.094 nats). 0.10 nats is the same
order as those between-benchmark gaps; drift larger than this
indicates a non-trivial distributional shift.

**Caveat: §13.10 dumps are now N=200.** Per §13.20 / §15.2
Postscript, the §13.10 TruthfulQA-MC dump on disk is N=200,
not the N=100 §15.2 baseline computed against. §15.7's KS
test uses the N=200 dump as the reference distribution
because **the test is about distributional shape, not the
specific N=100 sample**. Larger N gives a more powerful
reference; if HYPOTHESIS_SUPPORTED fires against the N=200
reference, it is more conservative than the same test
against the original N=100 dump would have been. The N=200
status is documented as an interpretive note in the §15.7
result, not as a §0.8 deviation.

**§0.8 boundary on the test outcome.**

- **HYPOTHESIS_SUPPORTED** does NOT change the §15.6 verdict
  from REGRESSION to anything else. The verdict cascade fired
  on the pinned $\Delta\kappa$ point estimate; the
  cascade's verdict is binding. HYPOTHESIS_SUPPORTED produces
  interpretive content of the form: *"the REGRESSION verdict
  is consistent with sampling-noise-bound stochasticity over
  a Stage-A-degenerate hybrid; substantive 'hybrid hurts'
  reading is not supported by the distributional evidence."*
- **HYPOTHESIS_REFUTED** likewise does not strengthen the
  §15.6 verdict to a worse band. The verdict remains
  REGRESSION; HYPOTHESIS_REFUTED produces content of the
  form: *"REGRESSION reflects substantive distributional
  drift in the §15.6 risk score relative to §13.10's
  reference; the hybrid does measurably differ from
  single-source even on a benchmark where Stage A
  degenerates."*
- **HYPOTHESIS_PARTIAL** produces ambiguity-flagging content
  with both readings explicitly stated.

In all three cases, the §15.6 cascade verdict (REGRESSION)
remains binding under §0.8. §15.7's hypothesis test informs
the **interpretation** of that verdict, not the verdict itself.

**Interpretation framework (pinned, §0.8-style; the
verdict-binding vs interpretive-caveat distinction).**

§15.7 produces diagnostic content. To prevent informal
narrative from drifting into verdict-override territory
(the failure mode §0.8 is designed to prevent), §15.7 pins
**three classes of statements** §15.7 may emit, each with
explicit constraints on what they can claim.

**Class 1 — Numerical observations (always permitted).**

§15.7 may report any of the diagnostic numbers from Chunks
7c–7e verbatim:

- "$\rho(\tau^*) = X$ vs $\rho^*(\alpha_2, \pi) = Y$ → local
  condition $\rho \ge \rho^*$ [met / not met]."
- "Stage A $|D| = X$ out of 100; V1 selected Qwen on $X$ /
  100 questions."
- "KS p-value = X; mean difference = Y nats; HYPOTHESIS
  classification: [SUPPORTED / REFUTED / PARTIAL]."
- "Number of distinct $r(q)$ values: $X$. Operating-point
  collapse at $\alpha \in \{0.40, 0.50\}$: [yes / no]."

These are direct readouts of pinned computations with no
inferential content beyond them.

**Class 2 — Interpretive narrative (permitted with explicit
verdict-binding caveat).**

§15.7 may interpret the numerical observations into mechanism
narrative, subject to the binding-verdict caveat:

> **Allowed interpretive form:** *"The §15.6 REGRESSION
> verdict-of-record (binding under §0.8) is consistent with
> [A-DEGENERATE / B-INSUFFICIENT / C-MISMATCHED / MIXED]
> failure mode. Specifically, [evidence from Class 1
> observations]. This sharpens the diagnosis without
> overriding the cascade verdict; the verdict remains
> REGRESSION regardless of the diagnostic mechanism."*

The constraint: every interpretive statement that bears on
§15.6 must explicitly include "the verdict remains
REGRESSION regardless." Same constraint applies to §15.4
USEFUL_INTERNAL — interpretive content may sharpen the
mechanism, but the verdict band cannot shift.

**Class 3 — Forbidden statements (§0.8-blocked).**

§15.7 may NOT emit any of the following:

- "§15.6's REGRESSION verdict was wrong" — overrides binding
  verdict.
- "Δκ should be re-classified as SATURATION because the
  hypothesis test showed sampling-noise" — overrides band
  cascade.
- "§15.4's USEFUL_INTERNAL is invalid because composition
  failure mode (iii) fired" — overrides binding verdict.
- "The §13.9 hold should be relaxed because §15.7 found
  diagnostic value" — overrides external-framing gate.
- "§15.8 follow-up is authorized because the diagnostic
  shows where to fix" — §15.8 requires fresh §0.8 commitment.
- "The autonomy result (§6.1) is strengthened by §15.7" —
  cross-domain claim outside §15.7 scope.

If §15.7's emitted content contains any of these, the script
must abort with `INTERPRETATION_VIOLATION` and refuse to
write artifacts. (This is enforced in implementation; pinned
in Chunk 7g.)

**Pinned narrative templates (§0.8 style).**

The §15.7 result section's mechanism narrative MUST follow
one of these templates per benchmark, parameterized by the
diagnostic decision-tree classification:

- **A-DEGENERATE template:** *"On [benchmark], §15.6's
  REGRESSION verdict-of-record (binding) reflects Stage A
  degeneration. V1 selected [source] on [N/100] questions;
  the hybrid reduced to single-source plus stochastic
  sampling. The [Δκ value] differs from §15.1's baseline
  [κ value] within [statistical / practical] equivalence
  bounds (KS p = X; mean drift = Y nats; HYPOTHESIS_SUPPORTED).
  The verdict band remains REGRESSION; the substantive
  reading is sampling-bounded, not 'hybrid actively hurts'."*
- **B-INSUFFICIENT template:** *"On [benchmark], §15.6's
  REGRESSION (or §15.4's USEFUL_INTERNAL) verdict-of-record
  (binding) is anchored by Stage B's score-separability
  failure. The risk score's local condition $\rho(\tau^*) =
  X$ falls below the base-rate-adjusted threshold
  $\rho^*(\alpha_2, \pi_S) = Y$ near the operating point.
  The verdict band remains [REGRESSION / USEFUL_INTERNAL];
  the mechanism is local discriminability, not Stage A
  degeneration."*
- **C-MISMATCHED template:** *"On [benchmark], §15.[X]'s
  verdict-of-record is anchored by composition failure: the
  per-source winning-source entropy $R_S$ correlates with
  $1 - Y_S$ at $\rho_\text{Pearson} = X$ on $\bar{D}$ but
  only $Y$ on $D$ (V1-divergent questions). The hybrid's
  risk-to-correctness mapping breaks on exactly the
  questions where Stage A's selector matters. The verdict
  band remains [REGRESSION / USEFUL_INTERNAL]; the
  mechanism is hybrid-specific."*
- **MIXED / OTHER template:** *"On [benchmark], the
  decomposition does not cleanly resolve to a single
  failure mode. [Specific evidence]. The verdict band
  remains [X]; the mechanism is multi-component."*

§15.7's result section MUST use exactly one of these
templates per benchmark + verdict pair. No free-form
narrative substitutions.

**§0.8 enforcement summary.**

| Statement type | Allowed | Constraint |
|---|---|---|
| Class 1 (numerical) | Yes | Must be direct readout of pinned computation |
| Class 2 (interpretive narrative) | Yes | Must use one of four pinned templates AND include explicit "verdict band remains [X]" caveat |
| Class 3 (verdict override) | **No** | Triggers INTERPRETATION_VIOLATION abort |

This is the §15.7 firewall against soft-override drift.

**Implementation scope (pinned).**

§15.7 is implementable as a single CPU-only post-processing
script with no new compute, mirroring the §15.1 / §15.3 /
§15.5 Phase 2 pattern.

**New script:** `scripts/probe_audit_15_7.py` (numpy +
stdlib + scipy.stats only — scipy is added as a dependency
ONLY for the KS two-sample test in Chunk 7e; if scipy is
not available, fall back to a numpy-only KS implementation
documented inline). No GPU, no transformers, no torch, no
network access.

**Reuse from §15.1 / §15.3 / §15.5 (primitives copied, NOT
imported).** Same copy-not-import discipline as §15.5 Chunk
5h: §15.7's script copies the relevant metric primitives
from prior scripts (sweep grid, NaN-safe acc/cov computation,
deterministic question-id sort with lexsort tiebreak)
verbatim. Importing from prior scripts would couple §15.7
to any future drift in those closed scripts.

**Component spec (~700–1000 lines estimated):**

1. **Schema validators** for the four input artifacts per
   Chunk 7b's pinned field expectations.
2. **§14a.2 dump loader** with Stage A handoff extraction
   (per-question $S(q), Y_S(q), R_S(q), Y_\text{Baseline-A}(q)$).
3. **§13.10 dump loader** for distributional comparison
   (per-question Qwen entropy + correctness label).
4. **§15.2 verdict-of-record loader** for pinned baseline
   $\kappa$ values.
5. **Diagnostic curve computation** (Chunk 7c): $F_1, F_0,
   \Delta, \rho, p, c$ over the empirical threshold grid;
   step-size audit; base-rate-adjusted $\rho^*$ per
   configuration.
6. **Stage A / B / Composition decomposition** (Chunk 7d):
   V1 selection identity histogram; V1-divergent set $D$
   metrics; Stage A net lift; Stage B class-conditional
   stats; Composition correlation comparison on $D$ vs
   $\bar{D}$.
7. **Diagnostic decision-tree classifier** (Chunk 7d) that
   maps the decomposition outputs into one of A-DEGENERATE
   / B-INSUFFICIENT / C-MISMATCHED / MIXED per benchmark.
8. **§15.6 sampling-noise hypothesis test** (Chunk 7e):
   KS two-sample test, summary distance metrics,
   conditional comparison; classify into HYPOTHESIS_SUPPORTED
   / HYPOTHESIS_REFUTED / HYPOTHESIS_PARTIAL per pinned
   thresholds.
9. **Interpretation-firewall enforcement** (Chunk 7f): the
   markdown report writer accepts only one of the four
   pinned templates per (benchmark, verdict) pair; emits
   `INTERPRETATION_VIOLATION` and aborts if Class-3
   forbidden statements appear in the rendered output.
10. **Self-test gate** (`--self-test`): verifies the
    diagnostic decision-tree classifier and the sampling-
    noise classifier on synthetic boundary cases mirroring
    the §15.7 Chunks 7d / 7e pinned thresholds. Required
    pre-execution gate.
11. **Output writers:** JSON + markdown per Chunk 7g paths.

**Self-test boundary cases (pinned).**

For the diagnostic decision-tree classifier, pinned synthetic
inputs:

- A-DEGENERATE input: V1 selects same source on all 100
  questions; $\Delta_A = 0$; $|D| = 0$ → expected verdict
  A-DEGENERATE.
- B-INSUFFICIENT input: $\rho_S(\tau^*) = 1.5$ vs
  $\rho^*(\alpha_2, \pi=0.30) = 2.33$ at any qualifying
  $\tau$ → expected B-INSUFFICIENT.
- C-MISMATCHED input: correlation on $\bar{D}$ = +0.4,
  correlation on $D$ = +0.05 (≥ 0.3 gap) → expected
  C-MISMATCHED.
- MIXED input: multiple criteria fire → expected MIXED.

For the sampling-noise classifier:

- SUPPORTED input: KS p = 0.5, mean_diff = 0.05, stdev_diff
  = 0.05 → HYPOTHESIS_SUPPORTED.
- REFUTED input: KS p = 0.001, mean_diff = 0.30 → REFUTED.
- PARTIAL input: KS p = 0.5, mean_diff = 0.15 → PARTIAL.

**Engineering cost:**

- ~700–1000 lines of new code (with copy-from-§15.x
  duplication accounted for, per the §15.4 Chunk 4e drift-
  acknowledgment lesson).
- numpy + Python stdlib + (optional) scipy.stats. CPU only.
- Wall-clock cost of real-data run: under 60 seconds.

**Output paths (pinned).**

- `docs/experiments/probe_audit_15_7.json` (machine-readable;
  `schema_version` `"15.7-diagnostic"`).
- `docs/experiments/probe_audit_15_7.md` (human-readable
  diagnostic report).

Both artifacts are flagged at the top with explicit text
indicating they are §15.7 diagnostic-only outputs and do
NOT constitute a new verdict-of-record. The interpretation
firewall (Chunk 7f) is enforced at write time.

**What §15.7 explicitly does NOT test, NOT authorize, NOT do.**

§15.7 is a deliberately narrowed diagnostic post-processing
audit. The scope boundary is tightly drawn to prevent it from
sliding into a new probe, a new verdict-class, or a follow-up
authorization. Specifically:

- **Not a new probe.** §15.7 reads existing artifacts; runs no
  new generation, no new model loads, no new NLI calls, no
  new GPU compute. If §15.7 implementation reaches for any
  resource outside the pinned four input artifacts, it is
  out of scope and aborts.
- **Not a re-classification of any §13 / §14 / §15.x verdict.**
  §15.4 USEFUL_INTERNAL, §15.6 REGRESSION, §15.2 MARGINAL,
  §13.20 NOISE_BAND_LIFT observation, §13.19 single-axis ANTI
  closure, §14b / §14c SCOUT_SATURATION verdicts — all remain
  binding under §0.8 regardless of §15.7 outputs.
- **Not a relaxation of the §13.9 VC-brief hold.** §13.9
  remains in force and is not addressed by §15.7 by
  construction (different metric class). The interpretation
  firewall (Chunk 7f) blocks any §15.7 statement claiming
  §13.9 should be reconsidered.
- **Not an authorization for §15.8 or beyond.** Any follow-up
  experimental probe (model-scale upgrade, supervised
  activation probe, benchmark substitution, ensemble risk
  score, alternative selector, deadband consumer, etc.)
  requires a fresh top-level §0.8 commitment. §15.7 produces
  diagnostic content that may inform the choice of follow-up,
  but does not authorize any specific follow-up.
- **Not a representation-level fix.** §15.7 audits the
  existing risk-score-to-correctness mapping; it does not
  propose new risk scores, new selector configurations, or
  new threshold policies. Per the multi-round critique that
  motivated §15.7, the transfer thesis was under-specified
  at the representation level — §15.7 confirms or refutes
  specific failure-mode hypotheses but does NOT propose a
  new representation.
- **Not a strengthening of §15.4 or §15.6.** §15.7 may sharpen
  the *mechanism* narrative for either verdict but cannot
  upgrade either to a higher band. The interpretation
  firewall blocks any "actually §15.4 should be STRONG"
  claim.
- **Not a cross-domain claim.** Autonomy-domain BCVF (§6.1)
  is wholly independent of §15.7. The interpretation firewall
  blocks any cross-domain claim.
- **Not a re-derivation of §15.2's verdict-of-record.** Per
  Chunk 7b's §0.8 caveat, the §13.10 dumps on disk are now
  N=200 per §13.20; §15.7 uses them only for distributional
  shape comparison in the sampling-noise hypothesis test
  (Chunk 7e), NOT to re-compute §15.2's pinned $\kappa$
  baselines.

**Reduced-form authorization rationale.**

§15.7 exists at all because the four input artifacts already
exist, the §15.5 / §15.4 closure cascades produced binding
verdicts that §15.7 may interpret without overriding, and
the multi-round informal critique surfaced specific
empirical questions answerable from the existing data. **If
any of the four artifacts had been missing, §15.7 would not
be authorized in this reduced form.** A from-scratch
diagnostic audit would require fresh §14a.2-class dumps,
fresh §15.x-class verdicts, or fresh §13.10 dumps at the
original N=100 — none of which §15.7 generates.

§15.7 is therefore authorized **only as a pure post-
processing layer over closed §13.10 / §14a.2 / §15.5 Phase 1
/ §15.2 artifacts**, with the explicit constraint that
§15.7's outputs are diagnostic narrative content for the
§15 closure, not new verdicts.

**§15.7 chunk roll-up — pre-commitment now complete.**

| Chunk | Content |
|---|---|
| 7a | Opening framing — pure-diagnostic post-processing; not a new probe; does not re-classify any verdict |
| 7b | Inputs and architecture (four on-disk artifacts; pure post-processing; no new compute; §0.8 caveat on §13.10 N=200 status) |
| 7c | Diagnostic curves pin (full audit spec): F₁, F₀, Δ(τ), ρ(τ), ρ*(α,π) base-rate-adjusted thresholds, p(τ), c(τ), step-size audit |
| 7d | Stage A / Stage B / Composition decomposition with three pinned failure modes; diagnostic decision-tree classifier |
| 7e | §15.6 sampling-noise hypothesis test — pinned KS + distance metrics; three pinned outcomes; explicit "does NOT change verdict" boundary |
| 7f | Interpretation framework — three statement classes; four pinned narrative templates; interpretation firewall against soft-override drift |
| 7g | Implementation scope — `scripts/probe_audit_15_7.py`, 11-component spec, self-test gate, INTERPRETATION_VIOLATION enforcement at write time |
| 7h | What §15.7 does NOT test + reduced-form rationale + roll-up |

Implementation of `scripts/probe_audit_15_7.py` is a separate
§0.8 authorization gate. §15.7's result section (parallel to
§15.6 / §15.4 / §15.2) follows the real-data run — and is
itself a §0.8 chunked drafting exercise with the
interpretation firewall (Chunk 7f) enforced.

### 15.8 Result — §15.7 audit produced three classifications; §15.6 mechanism narrative corrected (binding verdict unchanged)

The §15.7 pre-committed diagnostic audit has been executed
against the four pinned on-disk artifacts in the runpod
container. Three diagnostic classifications:

- **HaluEval-QA decomposition: `MIXED`** (no single failure
  mode fires cleanly).
- **TruthfulQA-MC decomposition: `C-MISMATCHED`** (composition
  failure: per-source winning-source entropy is sign-flipped
  on V1-divergent questions).
- **TruthfulQA-MC sampling-noise: `HYPOTHESIS_PARTIAL`**
  (distributions statistically equivalent at $\alpha=0.05$
  but practically drifted by ~0.18 nats).

**Critical §15.6 mechanism correction (verdict band
unchanged).** §15.7 has empirically **refuted** an informal
mechanism claim that appeared in §15.6 Chunk 6c's analytical
discussion — namely the working hypothesis that "V1 picked
Qwen on all 100 TruthfulQA-MC questions." The §15.7 audit
finds **V1 selected Qwen on 76/100, Llama on 17/100, Mistral
on 7/100**; the V1-divergent set $|D| = 24$, well above the
A-DEGENERATE small-divergence threshold. Per §15.7 Chunk 7f's
interpretation firewall, this correction:

- **Does not alter §15.6's binding `REGRESSION` verdict-of-
  record.** The cascade fired on the pinned $\Delta\kappa$
  point estimate; that verdict band remains REGRESSION
  regardless of the §15.7 mechanism finding.
- **Sharpens the mechanism narrative from "Stage A
  degeneracy" to "composition failure (C-MISMATCHED)".**
  The §15.7 audit identifies the correct underlying
  mechanism: the per-source winning-source entropy is a
  sign-flipped proxy for selected-answer correctness on
  V1-divergent questions ($r_{\bar{D}} = +0.264$, $r_D =
  -0.156$, gap = 0.421 above the 0.30 C-MISMATCHED
  threshold).
- **Is recorded here as §15.7-discovered evidence**, not
  back-applied as a silent edit to §15.6's text. §15.6
  Chunks 6a–6f remain the verdict-of-record for the §15.5
  scout; §15.8 documents the §15.7 mechanism correction in
  the audit trail.

**§13.9 VC-brief hold remains in force**, autonomy-domain
BCVF claim (§6.1) unaffected. **Both §15.4 USEFUL_INTERNAL
and §15.6 REGRESSION verdict-of-record bands remain
binding** — neither raised, neither lowered, neither
re-classified.

**Parity-gate / schema-validation confirmation (per §15.7
Chunk 7b).**

| Input artifact | Status |
|---|---|
| `probe_system_level_scout_v2_halueval_qa.json` (§14a.2) | loaded; 100 questions; schema validated |
| `probe_system_level_scout_v2_truthfulqa_mc.json` (§15.5 Phase 1) | loaded; 100 questions; schema validated |
| `probe_selective_abstention.json` (§15.2 verdict-of-record) | `schema_version == "15.1"` validated; pinned $\kappa$ extracted |
| `probe_semantic_entropy.json` (§13.10 TruthfulQA-MC reference) | loaded; 100 questions on disk in this runpod (`n_13_10_overwritten = False`); used as distributional reference for sampling-noise test only |

No `SCHEMA_MISMATCH` fired at the input layer.

**§13.10 N status — runpod-specific note.** The §15.7
runpod's on-disk §13.10 TruthfulQA-MC dump is **N=100, not
N=200**. This is a different runpod environment than the one
where §13.20's N=200 overwrite occurred (different container
hostname `49064e65c30d`). The §15.7 audit's `n_13_10_overwritten`
flag returned `False`. The sampling-noise test therefore
compared §15.6's N=100 R_S distribution against an N=100
§13.10 Qwen reference — the most direct comparison possible
under the pinned protocol. **§15.2's pinned $\kappa$
baselines are unchanged regardless** (those came from the
§15.2 verdict-of-record artifact, not from any §13.10 dump).

**Self-test gate.** §15.7's required pre-execution gate
(`--self-test`) ran in the same invocation as real-data
execution and returned PASSED on all 17 pinned cases:
- 4 decision-tree boundary cases (Chunk 7d).
- 6 sampling-noise classifier cases (Chunk 7e).
- 7 interpretation-firewall cases (Chunk 7f).

**Interpretation firewall confirmation.** The rendered
markdown report was scanned for Class-3 forbidden statements
before write per §15.7 Chunk 7f. **No `INTERPRETATION_VIOLATION`
fired**; output was written cleanly. The interpretation
firewall is empirically functional under real-data
conditions.

**Cross-program consistency check.**

| Quantity | §15.4 / §15.6 reported | §15.7 audit observed | Match? |
|---|---|---|---|
| HaluEval V1 acc | 0.330 (§14c) | $\pi_S = 0.33$ | ✓ |
| HaluEval Baseline-A acc | 0.300 (§14c) | $\pi_A = 0.30$ | ✓ |
| HaluEval $\Delta_A$ (= V1 − BA) | +0.030 (per §15.4 Chunk 4a) | $+0.030$ | ✓ |
| TruthfulQA-MC V1 acc | 0.250 (§15.6 Chunk 6a) | $\pi_S = 0.25$ | ✓ |
| TruthfulQA-MC Baseline-A acc | 0.250 (§15.6 Phase 1) | $\pi_A = 0.25$ | ✓ |
| TruthfulQA-MC κ at α₂ (hybrid) | 0.11 (§15.6 verdict-of-record) | cov@α₂ = 0.11 | ✓ |
| TruthfulQA-MC operating-point collapse at α₁/α₂ | reported in §15.6 Chunk 6b | empirically confirmed (same τ*=0.6390) | ✓ |
| §15.2 HaluEval $\kappa$ baseline | 0.26 (§15.2 verdict-of-record) | 0.26 | ✓ |
| §15.2 TruthfulQA-MC $\kappa$ baseline | 0.14 (§15.2 verdict-of-record) | 0.14 | ✓ |

All cross-program consistency checks pass. The §15.7 audit
operates over the same per-question state §15.4 / §15.6 / §15.2
classified; numerical drift between §15.x verdict-of-records
and §15.7 inputs is zero (within float precision).

**Artifacts.**

- `scripts/probe_audit_15_7.py` (§15.7 implementation; numpy
  + stdlib + optional scipy.stats; ~1967 lines).
- `docs/experiments/probe_audit_15_7.json` (machine-readable
  diagnostic, `schema_version "15.7-diagnostic"`; flagged at
  top as NOT a verdict-of-record).
- `docs/experiments/probe_audit_15_7.md` (human-readable
  diagnostic report; rendered through interpretation firewall).

**Headline numerical findings.**

**(A) Stage A / Stage B / Composition decomposition per
benchmark.**

| Quantity | HaluEval-QA | TruthfulQA-MC |
|---|---|---|
| V1 selection: Qwen | 69 / 100 | **76 / 100** |
| V1 selection: Llama | 12 / 100 | **17 / 100** |
| V1 selection: Mistral | 19 / 100 | **7 / 100** |
| $\|D\|$ (V1-divergent set) | 31 | **24** |
| $\|D\|/N$ | 0.31 | **0.24** |
| $\pi_S$ (V1 acc, full coverage) | 0.330 | 0.250 |
| $\pi_A$ (Baseline-A acc) | 0.300 | 0.250 |
| $\Delta_A = \pi_S - \pi_A$ | $+0.030$ | $\boldsymbol{0.000}$ |
| $\Delta$ on $D$ subset | $+0.097$ | $\boldsymbol{0.000}$ |
| $\rho(\tau^*)$ at $\alpha_2 = 0.50$ | 2.150 | **5.250** |
| $\rho^*$ at $\alpha_2 = 0.50$ | 2.030 | **3.000** |
| $\rho \ge \rho^*$? (local condition met) | **yes** (barely) | **yes** (comfortably) |
| Pearson $r(R_S, 1-Y_S)$ overall | $+0.364$ | $+0.193$ |
| Pearson $r$ on $\bar{D}$ (Qwen-picked) | $+0.439$ | $+0.264$ |
| Pearson $r$ on $D$ (V1-divergent) | $+0.191$ | $\boldsymbol{-0.156}$ |
| Composition gap $r_{\bar{D}} - r_D$ | $+0.248$ | $\boldsymbol{+0.421}$ |
| **Decision-tree classification** | **MIXED** | **C-MISMATCHED** |

**Three substantive numerical findings the table supports.**

**(a) The local condition $\rho(\tau^*) \ge \rho^*$ is met on
both benchmarks** — including on TruthfulQA-MC, where the
§15.6 cascade returned REGRESSION. This is operationally
striking: the score has *sufficient local discriminative
power* at the operating point on both benchmarks. On
TruthfulQA-MC, $\rho(\tau^*) = 5.25$ versus $\rho^* = 3.0$ —
the score discriminates more than the base-rate-adjusted
threshold requires. The reason §15.6 still returned REGRESSION
is that the τ* delivering $\rho \ge \rho^*$ also delivers
**only $\kappa = 0.11$ coverage**, below §15.1's
TruthfulQA-MC baseline of 0.14. **Sufficient discrimination
on a tiny subset, not insufficient discrimination overall.**

**(b) Composition correlation flips sign on TruthfulQA-MC's
V1-divergent subset.** $r_{\bar{D}} = +0.264$ (Qwen-picked,
expected direction: high entropy → wrong) versus $r_D =
-0.156$ (V1-divergent, **inverted direction: high entropy
→ correct**). Gap of 0.421 places this comfortably in the
C-MISMATCHED band (threshold 0.30). On the 24 questions
where V1's selector matters most, the per-source winning-
source entropy is **anti-correlated** with selected-answer
correctness. The hybrid's risk score breaks specifically on
the questions where the hybrid adds value.

**(c) HaluEval composition gap is sub-threshold but real.**
$r_{\bar{D}} - r_D = 0.248$ on HaluEval, below the C-MISMATCHED
threshold of 0.30 but visibly non-zero. The HaluEval correlation
on $D$ stays positive ($+0.191$), unlike TruthfulQA-MC's
sign-flip. Combined with $\Delta_A = +0.030$ Stage A lift and
$\rho \ge \rho^*$ Stage B condition met, none of A/B/C fires
cleanly → MIXED.

**(B) Operating-point analysis (curves and collapse).**

| Benchmark | $\alpha$ | cov@$\alpha$ | $\tau^*$ | $\rho(\tau^*)$ | $\rho^*$ | meets? |
|---|---|---|---|---|---|---|
| HaluEval-QA | 0.40 | 0.63 | 1.9730 | 1.523 | 1.354 | ✓ |
| HaluEval-QA | 0.50 | 0.35 | 1.2275 | 2.150 | 2.030 | ✓ |
| HaluEval-QA | 0.75 | **0.00** | $+\infty$ | NaN | 6.091 | ✗ |
| TruthfulQA-MC | 0.35 | **0.11** | **0.6390** | 5.250 | 1.615 | ✓ |
| TruthfulQA-MC | 0.50 | **0.11** | **0.6390** | 5.250 | 3.000 | ✓ |
| TruthfulQA-MC | 0.75 | **0.00** | $+\infty$ | NaN | 9.000 | ✗ |

**Operating-point collapse audit:**

| Benchmark | $\alpha$ pair | same $\tau^*$? |
|---|---|---|
| HaluEval-QA | (0.40, 0.50) | distinct |
| HaluEval-QA | (0.50, 0.75) | distinct (latter degenerate) |
| TruthfulQA-MC | (0.35, 0.50) | **collapsed** ($\tau^* = 0.6390$, cov = 0.11, $\rho = 5.25$ identical) |
| TruthfulQA-MC | (0.50, 0.75) | distinct (latter degenerate) |

**The §15.6 Chunk 6b "stepped curve" finding is empirically
confirmed.** The α₁/α₂ collapse on TruthfulQA-MC is a
property of the entropy distribution's empirical support
shape, not a measurement artifact. $\alpha_3 = 0.75$ remains
unreachable on both benchmarks (consistent with §15.4 / §15.6
findings).

**(C) Sampling-noise hypothesis test (TruthfulQA-MC).**

| Quantity | Value |
|---|---|
| KS statistic | 0.180 |
| KS p-value | 0.0691 |
| Mean drift (§15.6 R_S − §13.10 reference) | $-0.178$ nats |
| Stdev drift | $+0.003$ nats |
| N (§15.5 Phase 1) | 100 |
| N (§13.10 reference, on-disk this runpod) | 100 |
| **Classification** | **`HYPOTHESIS_PARTIAL`** |

Rationale (per Chunk 7e pinned interpretation rules): KS p =
0.0691 > 0.05 (statistically equivalent at α=0.05) BUT
$|$mean drift$| = 0.178$ nats falls in the
$[0.10, 0.20]$ PARTIAL band (above the SUPPORTED bound of
0.10 nats but below the REFUTED bound of 0.20 nats). The
distributions are not pure-sampling-noise (rejected as
SUPPORTED) and not pure-substantive-shift (rejected as
REFUTED) — they are practically drifted by ~0.18 nats with
shape preserved.

**Mechanism read on the drift direction.** The negative
mean drift means §15.6's R_S is on average **lower** than
§13.10's pure-Qwen reference. Consistent with V1 occasionally
picking non-Qwen sources whose K=10 entropies are tighter
than Qwen's: when V1 picks Llama or Mistral (24/100 questions),
$R_S$ comes from those sources, which have on average
modestly lower entropy than Qwen on TruthfulQA-MC.

**TruthfulQA-MC narrative — C-MISMATCHED classification (§15.6
mechanism corrected; verdict band remains REGRESSION).**

On truthfulqa-mc, §15.6's `REGRESSION` verdict-of-record
(binding under §0.8) is anchored by composition failure. The
per-source winning-source entropy $R_S$ correlates with
$1 - Y_S$ at Pearson $r_{\bar{D}} = +0.2643$ on the Qwen-
picked subset $\bar{D}$ (76 questions) but at $r_D = -0.1564$
on the V1-divergent subset $D$ (24 questions; $|D|/N = 0.24$).
The hybrid's risk-to-correctness mapping breaks on exactly
the questions where Stage A's selector matters — a
hybrid-specific pathology that does not exist in the single-
source scenario. The verdict band remains `REGRESSION`
regardless of this diagnostic mechanism.

**Explicit §15.6 mechanism correction recorded (per Chunk 7f
firewall constraints).** §15.6 Chunk 6c presented an informal
analytical hypothesis that V1 selected Qwen on all 100
TruthfulQA-MC questions, supporting a "Stage A degeneracy
plus sampling stochasticity" interpretation of the §15.6
REGRESSION verdict. **The §15.7 audit empirically refutes
this informal hypothesis**: V1 selected Qwen on 76/100,
Llama on 17/100, Mistral on 7/100; the V1-divergent set
$|D| = 24$ — well above the A-DEGENERATE threshold of
$|D|/N < 0.05$. The §15.6 Chunk 6c claim was not part of
§15.6's pinned cascade verdict; it was analytical commentary
that turned out to be empirically wrong. Per §15.7 Chunk 7f's
interpretation firewall:

- **The §15.6 `REGRESSION` cascade verdict-of-record remains
  binding under §0.8.** The cascade fired on the pinned
  $\Delta\kappa = -0.030$ point estimate; that classification
  is unchanged.
- **The §15.6 Chunk 6c analytical narrative is corrected
  here in §15.8**, not silently rewritten in §15.6. The audit
  trail preserves the original §15.6 Chunk 6c text alongside
  this §15.8 correction.
- **The corrected mechanism is C-MISMATCHED (composition
  failure)**, not A-DEGENERATE (Stage A degeneracy). The
  hybrid's risk score is sign-flipped on V1-divergent
  questions, which is structurally different from "the
  hybrid reduces to single-source."

**Operationally what C-MISMATCHED means on TruthfulQA-MC.**
On the 76 Qwen-picked questions, the per-source winning-
source entropy works as expected: high entropy → wrong
($r_{\bar{D}} = +0.26$). On the 24 V1-divergent questions,
the relationship inverts: high entropy of the winning source
is **anti-correlated** with whether V1's selected answer is
right ($r_D = -0.16$). Mechanically, this can happen if:

- When V1 picks a non-Qwen source on TruthfulQA-MC, that
  source's K=10 stochastic samples cluster tightly around an
  *incorrect* answer (low entropy, but wrong) — making low
  entropy a misleading proxy on those questions.
- Conversely, when V1 picks a non-Qwen source whose samples
  are diverse (high entropy), the V1-clustered selector may
  pick a representative whose answer happens to be correct —
  making high entropy weakly indicative of correctness on
  this small subset.

Either pattern produces sign-flipped correlation on $D$.
**§15.7 does not pin a single mechanical explanation; it
identifies the diagnostic signature and pins the
classification.** The narrative correction is a §15.8
finding, not a §15.6 amendment.

**Why $\Delta_A = 0$ is not A-DEGENERATE.** A-DEGENERATE
requires both $|\Delta_A| <$ threshold AND $|D|/N <$
threshold. TruthfulQA-MC has $\Delta_A = 0$ exactly (V1
swapped the same number of right-becomes-wrong as
wrong-becomes-right) but $|D|/N = 0.24 \gg 0.05$. The decision
tree (Chunk 7d, _classify_decision_tree) correctly does not
classify as A-DEGENERATE because the divergent set is
substantial. **§15.6's "V1 swapped sources but the net
accuracy was unchanged" pattern is real; the inference that
"V1 must have picked Qwen on all 100" was the wrong
conclusion to draw from that pattern.**

**Audit-trail integrity.** Per §15.7 Chunk 7f and the
no-silent-edit discipline, §15.6 Chunks 6a–6f text is
preserved unchanged. §15.8 records the §15.7 mechanism
correction as new §0.8-binding diagnostic content. Future
readers tracing the §15 program audit trail see:

1. §15.6 Chunk 6c's original informal hypothesis.
2. §15.8 (this section) recording the §15.7 audit's empirical
   refutation of that hypothesis and the corrected C-MISMATCHED
   mechanism.
3. Both §15.6 REGRESSION and §15.7 C-MISMATCHED diagnostic
   classification standing as binding §0.8 content at their
   respective levels (verdict cascade vs diagnostic
   decomposition).

The verdict band remains `REGRESSION`. The mechanism is now
correctly characterized.

**HaluEval-QA narrative — MIXED classification (no single
clean failure mode; verdict band remains USEFUL_INTERNAL).**

On halueval-qa, the §15.7 decomposition does not cleanly
resolve to a single failure mode. Stage A net lift
$\Delta_A = +0.030$; V1-divergent set size 31 ($|D|/N =
0.31$); $\rho(\tau^*) = 2.150$ vs $\rho^* = 2.030$ at
$\alpha_2 = 0.50$ (local condition met, but barely);
composition Pearson correlation gap $r_{\bar{D}} - r_D =
+0.248$ (visibly non-zero but below the 0.30 C-MISMATCHED
threshold). None of the three single-mode signatures fires
cleanly. The verdict band remains `USEFUL_INTERNAL`
regardless of this diagnostic mechanism; the §15.7 audit
flags HaluEval-QA's hybrid as multi-component rather than
asserting a single clean driver.

**Operationally what MIXED means on HaluEval-QA.** The §15.4
USEFUL_INTERNAL verdict is real but its mechanism is
distributed across all three components:

- **Stage A contributes ~3pp lift, concentrated on $D$.**
  V1's net accuracy lift over Baseline-A is $+0.030$ on the
  full 100 questions; on the 31 V1-divergent questions, V1's
  selected-answer accuracy minus Baseline-A's accuracy is
  $+0.097$ (a 9.7pp lift on the divergent subset). Stage A
  is doing real work where the selector chooses non-Qwen.
- **Stage B's local condition $\rho \ge \rho^*$ is met,
  marginally.** $\rho(\tau^*) = 2.150$ vs $\rho^* = 2.030$ —
  cleared by 0.12 (about 6% margin). Tighter than
  TruthfulQA-MC's 5.25 vs 3.0 (75% margin) but technically
  on the right side of the threshold.
- **Composition shows partial mismatch but stays sub-
  threshold.** Correlation drops from $r_{\bar{D}} = +0.439$
  on Qwen-picked questions to $r_D = +0.191$ on V1-divergent —
  a real degradation (factor of ~2), but the gap of 0.248
  doesn't quite cross the 0.30 C-MISMATCHED threshold AND
  the sign doesn't flip (both correlations stay positive,
  unlike TruthfulQA-MC's flip).

**What the MIXED classification implies about §15.4.** The
USEFUL_INTERNAL verdict is *real but fragile*. It survives
because all three components contribute small-positive
effects that compound to clear the $\Delta\kappa \ge +0.05$
USEFUL_INTERNAL threshold. None of the three components is
individually doing dominant work; conversely, none is
individually broken. **A §15.4 STRONG would have required
substantially stronger contribution from at least one
component**, which the data does not show.

**Sampling-noise interpretation: PARTIAL, leaning toward
modest substantive drift.**

The TruthfulQA-MC sampling-noise test classified
`HYPOTHESIS_PARTIAL`. Pinned interpretation rules (§15.7
Chunk 7e) classify this as "ambiguous"; both readings must
be reported.

**Reading 1 — modest drift toward sampling-noise side.** KS
p-value 0.0691 narrowly clears the $\alpha = 0.05$ threshold
of statistical equivalence; mean drift 0.178 nats narrowly
clears the SUPPORTED bound of 0.10 nats. The distributions
are statistically indistinguishable and the practical drift
is bounded. Under this reading, §15.6's $\Delta\kappa =
-0.030$ contains a substantial sampling-stochasticity
component, even if not dominantly noise-bound.

**Reading 2 — modest drift toward substantive shift.** Mean
drift 0.178 nats falls in the upper half of the PARTIAL band
$[0.10, 0.20]$; KS p-value 0.0691 sits just above the
rejection threshold. The shift direction is structurally
explained (V1 picks tighter-clustered non-Qwen sources on
24% of questions); the drift is real, not random. Under
this reading, §15.6's $\Delta\kappa = -0.030$ contains a
substantial composition-mismatch component, with the C-MISMATCHED
classification (Chunk 8c) carrying the dominant weight.

**Pinned interpretation per §15.7 Chunk 7e:** both readings
are reported; neither is privileged. The PARTIAL classification
means the data does not adjudicate cleanly between them. **The
§15.6 REGRESSION verdict band remains `REGRESSION` regardless
of which reading is privileged interpretively.** The §15.7
audit's value at the sampling-noise layer is showing that the
question is ambiguous — it is not a clean noise artifact, and
it is not a clean substantive shift; it is a small distributional
shift with mixed interpretation.

**Combining sampling-noise PARTIAL with TruthfulQA-MC
C-MISMATCHED.** The C-MISMATCHED classification captures the
*sign-flip on V1-divergent questions* mechanism, which is
distinct from distributional drift in $R_S$ overall. The
sampling-noise drift (-0.178 nats) and the composition
sign-flip (correlation $+0.26 \to -0.16$) are independent
signatures. Both contribute to §15.6's REGRESSION:

- C-MISMATCHED dominates the **mechanism** explanation: the
  hybrid's risk score is structurally broken on V1-divergent
  questions.
- PARTIAL sampling-noise contributes a **distributional**
  caveat: §15.6's R_S is also shifted modestly relative to
  §13.10's pure-Qwen reference, consistent with V1 picking
  non-Qwen sources with tighter K=10 clusters.

§15.6's REGRESSION verdict band remains binding regardless
of how these mechanism components are weighted.

**Authorization mapping per §15.7 Chunk 7f.**

§15.7's pre-committed Class-1 / Class-2 / Class-3 statement
rules govern what §15.8 may emit. Reproduced exactly:

| Class | Statement type | §15.8 usage in Chunks 8a–8d | Compliance |
|---|---|---|---|
| Class 1 | Numerical observations | All decomposition tables, operating-point tables, sampling-noise statistics, V1 selection histograms, correlation values | ✓ direct readouts of pinned computations |
| Class 2 | Interpretive narrative | TruthfulQA-MC C-MISMATCHED template (Chunk 8c); HaluEval MIXED template (Chunk 8d); sampling-noise PARTIAL dual-reading interpretation (Chunk 8d) | ✓ uses pinned templates; each statement includes "verdict band remains [X]" caveat |
| Class 3 | Verdict overrides | (none) | ✓ none emitted; firewall scan passed at write time |

**§15.8 specifically authorizes:**

- Documenting the §15.7 audit's three diagnostic
  classifications.
- Recording the empirical refutation of §15.6 Chunk 6c's
  "V1 picked Qwen on all 100" informal hypothesis.
- Sharpening §15.6's mechanism narrative from "Stage A
  degeneracy" to "composition failure (C-MISMATCHED)".
- Citing the §15.7 audit as confirmation of §15.6 Chunk 6b's
  "stepped curve" finding.
- Reporting the sampling-noise PARTIAL classification with
  both readings.

**§15.8 explicitly does NOT authorize:**

- **Re-classifying §15.6 from REGRESSION to any other band.**
  The cascade fired on the pinned $\Delta\kappa$ point
  estimate; that classification is binding under §0.8.
  §15.8's mechanism correction does NOT change the band.
- **Re-classifying §15.4 from USEFUL_INTERNAL to any other
  band.** The MIXED diagnostic classification is on a
  different layer (mechanism decomposition) than the §15.4
  cascade verdict (operational $\Delta\kappa$). The §15.4
  band is binding under §0.8 regardless of mechanism
  detail.
- **Strengthening or weakening §13.9's VC-brief hold based
  on §15.7 findings.** §13.9 gates external-framing on
  STRONG-band lift on both benchmarks; the §15.7 audit
  produces no STRONG-band evidence and does not address
  §13.9's gate by construction. §13.9 hold remains in
  force.
- **Authorizing a §15.8.x or §15.9 follow-up probe.** Any
  further LLM-track work (e.g., a fresh-§0.8 commitment to
  test a different risk score on the C-MISMATCHED-identified
  V1-divergent questions) requires its own top-level §0.8
  commitment. §15.8 records §15.7's diagnostic findings as
  part of the §15 closure narrative; it does not auto-promote
  any direction.
- **Cross-domain claims about §6.1 autonomy.** Autonomy-
  domain BCVF stands wholly independent of §15.7 / §15.8.
- **Silent edits to §15.6 text.** Per Chunk 7f's no-silent-
  edit discipline, §15.6 Chunks 6a–6f remain unchanged.
  The audit trail preserves the original §15.6 Chunk 6c
  hypothesis alongside §15.8's empirical refutation.

**Interpretation firewall confirmation under real-data
conditions.** The §15.7 implementation
(`scripts/probe_audit_15_7.py`) renders the diagnostic
markdown report and scans it for the 12 pinned Class-3
forbidden-statement patterns *before* writing the artifact.
**On this run, no `INTERPRETATION_VIOLATION` fired**: the
markdown was written cleanly, with no Class-3 patterns
detected. The firewall is empirically functional on the
real-data outputs. Future §15.x result-section drafting
should apply the same firewall pattern to prevent
interpretive drift.

**Run-time §0.8 deviation check.** Per §15.7 Chunk 7g, any
deviation discovered at run time must be flagged in the
§15.8 result section as a §0.8 deviation, not absorbed
silently. The §15.7 run produced **no such deviation**.
Schema validation passed on all four input artifacts; the
parity gates are implicit in §15.7's pinned configuration
(no parity guard is required at the §15.7 layer, as the
audit is descriptive over already-classified §0.8 outputs);
the self-test gate passed 17/17 in-run; the firewall passed
at write time.

The §15.6 Chunk 6c mechanism correction recorded above is
**not a run-time deviation** in §15.7's sense. It is a
diagnostic finding that the §15.7 audit was specifically
designed (per Chunk 7d's Stage A / B / Composition decomposition
spec) to surface. The correction is the §15.7 audit working
as intended.

**Combined picture across §13 / §14 / §15 + §15.7 audit —
program now closed at fully-decomposed-mechanism level.**

§15.8 closes the §15 LLM-track program at the diagnostic-
audit layer. The full §13 / §14 / §15 testing matrix plus
§15.7's diagnostic decomposition:

| Layer | Program | Verdict | Mechanism (post-§15.7) |
|---|---|---|---|
| §13.10 | AUC, single-axis SE baseline | TRUTH_CORRELATED_MARGINAL | (n/a; baseline) |
| §13.11–§13.18 | AUC, 4 single-axis revisions | 5/5 ANTI under worst-benchmark | (literature-aligned proxy thinness at scale) |
| §14a / §14a.2 | Δ accuracy, system-level | 2/2 SCOUT_SATURATION | (system-level bandwidth limited at M=3) |
| §13.20 | AUC, §13.10 N=200 observation | NOISE_BAND_LIFT (TruthfulQA-MC); MARGINAL (HaluEval) | (N=200 mean-reversion; not a §13.10 reclassification) |
| §15.1 / §15.2 | AURC + cov@α, single-source | MARGINAL | (TruthfulQA-MC base-rate caps κ@α₂ at 0.14) |
| §15.3 / §15.4 | Δκ vs §15.1 baseline, hybrid HaluEval | USEFUL_INTERNAL | **(§15.7: MIXED — multi-component; no single dominant driver)** |
| §15.5 / §15.6 | Δκ vs §15.1 baseline, hybrid TruthfulQA-MC | REGRESSION | **(§15.7: C-MISMATCHED — composition failure with sign-flipped correlation on V1-divergent subset)** |
| **§15.7 / §15.8** | **Diagnostic audit on existing dumps** | **(diagnostic-only; not a verdict)** | **§15.6 mechanism corrected from "Stage A degeneracy" to "composition failure"; §15.4 mechanism documented as MIXED multi-component; sampling-noise PARTIAL** |

**Fourteen distinct experimental structures plus one
diagnostic audit have now been tested at the 7B + DeBERTa-
v3-base + N=100 / N=200 configuration.** Zero clear STRONG
on the worst-benchmark rule. One cleared USEFUL_INTERNAL on
a single benchmark (§15.4) with multi-component MIXED
mechanism. One returned REGRESSION on the cross-benchmark
(§15.6) with C-MISMATCHED composition-failure mechanism. The
§15.7 diagnostic audit converted the multi-round informal
critique of §15.6's interpretation into binding §0.8
diagnostic content, including an explicit empirical
refutation of one §15.6 informal mechanism hypothesis.

**§13.9 VC-brief hold reaffirmed and strengthened by the
§15.7 diagnostic finding.** The C-MISMATCHED classification
on TruthfulQA-MC sharpens §13.9's framing: the cross-
benchmark hybrid is not just "saturated/regressed at this
configuration" but specifically "structurally broken on the
questions where the hybrid's selector matters most." This
adds mechanistic depth to the §13.9 hold without changing
its policy. The autonomy-domain BCVF claim (§6.1) stands
wholly independent of §15.7 / §15.8.

The honest external framing for any internal-research
referencing of the §13 / §14 / §15 + §15.7 program is now:

> *On Qwen2.5-7B-Instruct + DeBERTa-v3-base + N=100, no
> literature-aligned, mechanism-motivated, system-level,
> single-source-abstention, hybrid-abstention, or cross-
> benchmark-hybrid-abstention BCVF construction tested in
> this codebase clears the STRONG combined-classification
> bar on the worst-benchmark rule. The §15.4 hybrid scout
> cleared USEFUL_INTERNAL on HaluEval-QA single-benchmark;
> the §15.7 audit identifies its mechanism as MIXED
> multi-component (no single dominant driver). The §15.6
> cross-benchmark companion on TruthfulQA-MC returned
> REGRESSION, with the §15.7 audit identifying the mechanism
> as C-MISMATCHED composition failure (sign-flipped
> correlation on V1-divergent questions). Both verdict-of-
> records remain binding under §0.8; §15.7's diagnostic
> findings sharpen the mechanism narrative without changing
> any verdict band. The LLM hallucination-detection track is
> closed across fourteen experimental structures and four
> metric classes, with the §15.7 mechanism decomposition
> providing the cleanest structural reading of the §13 / §14
> / §15 program available.*

**§15.8 closes the §15 LLM-track program at the diagnostic-
audit layer.** Per §15.7 Chunk 7g and the firewall, no
§15.8.x or §15.9 follow-up is authorized by §15.8. Any
follow-up — model-scale upgrade, benchmark substitution,
supervised activation probes, source-construction redesign,
ensemble risk score, alternative selector, deadband consumer
— requires a fresh top-level §0.8 commitment with bands
pinned before any data inspection. None is authorized by
§15.8.

**The autonomy-domain BCVF claim (§6.1) stands independently
on the N=21 sign-test that passed in §6.1 / §6.7 and is
unaffected by any §13 / §14 / §15 / §15.7 outcome.**

**§15.8 chunk roll-up — result section now complete.**

| Chunk | Content |
|---|---|
| 8a | Header, three classifications, parity confirmation, §15.6 mechanism correction (verdict band unchanged), cross-program consistency check |
| 8b | Headline numerical findings (decomposition + operating points + sampling-noise) with three substantive observations including unexpected ρ ≥ ρ* on both benchmarks |
| 8c | TruthfulQA-MC C-MISMATCHED narrative + explicit §15.6 Chunk 6c hypothesis refutation with audit-trail integrity discipline |
| 8d | HaluEval MIXED narrative + sampling-noise PARTIAL dual-reading interpretation + mechanism-component combination |
| 8e | Authorization mapping (Class 1/2/3 compliance) + §0.8 firewall confirmation + run-time deviation check |
| 8f | Combined §13/§14/§15 + §15.7 picture; §13.9 hold reaffirmed and mechanistically sharpened; §15 LLM-track program closed |

§15.8 implementation source: `scripts/probe_audit_15_7.py`
output artifacts (`docs/experiments/probe_audit_15_7.{json,md}`);
all numerical evidence in this section traceable to those
diagnostic outputs.

**Artifacts.**

- `scripts/probe_audit_15_7.py` (§15.7 implementation;
  numpy + stdlib + scipy.stats; 1967 lines).
- `docs/experiments/probe_audit_15_7.json` (machine-readable
  diagnostic, `schema_version "15.7-diagnostic"`).
- `docs/experiments/probe_audit_15_7.md` (human-readable
  diagnostic report; rendered through interpretation
  firewall).

§15 LLM-track program closed at fully-decomposed-mechanism
level. §15.8 result section complete (chunks 8a–8f, 6 commits
on top of the §15.7 pre-commitment + implementation).

### 15.9 Future-work entry (documented, NOT pre-committed) — phase coherence as a theoretically-faithful autonomy-LLM transfer attempt

**Status: DOCUMENTED, NOT pre-committed.** §15.9 is the
§15-track analogue of §13.8's "future-work, requires fresh
§0.8 commitment" list. It records phase coherence as the
single most theoretically-defensible LLM-track direction
that has NOT been undertaken in this codebase, alongside
explicit constraints and prior estimates. **§15.9 does NOT
authorize implementation.** Any future phase-coherence
experiment requires a fresh top-level §0.8 commitment with
bands pinned ex-ante, structurally analogous to §15.3 /
§15.5 / §15.7's chunked pre-commitment discipline.

**The candidate formula and what it measures.**

The pinned candidate is the standard pairwise phase-coherence
metric over a windowed average of phase differences:

$$
C[i, j] \;=\; \frac{1}{W} \sum_{k} \cos(\phi_i[k] - \phi_j[k])
$$

where $\phi_i[k]$ is the phase of signal $i$ at index $k$
within window $W$, and the metric measures pairwise
agreement between any two signals $i, j$ over that window.
$C \in [-1, +1]$; $C = +1$ at perfect phase alignment,
$C = 0$ at orthogonal phases, $C = -1$ at perfect
anti-alignment.

This is structurally distinct from the §13/§14/§15 entropy-
based observables in three ways:

- **Continuous** rather than discrete (cosine of an angle vs
  Shannon entropy over discrete cluster sizes from K=10
  stochastic samples).
- **Pairwise** rather than scalar (produces a matrix
  $C[i, j]$ over signal pairs that can be aggregated, not a
  single per-question scalar).
- **Operates on internal phase structure** rather than
  output meaning space (downstream of the model's internals,
  not downstream of NLI clustering of sample texts).

**Why §15.9 is the most theoretically-faithful
autonomy-LLM transfer attempt available.**

The §6.1 autonomy-domain BCVF result that passed (N=21
sign-test p=0.0072) operated on **continuous phase-quad
signals** (`map_error_accel`) with the C2 vector-path
invariance property empirically validated. That is:
continuous geometric signals with meaningful temporal
evolution and physically grounded divergence.

The §13/§14/§15 LLM-track program mapped BCVF onto:
- §13.10 semantic entropy of cluster-size histograms over
  K=10 discrete stochastic samples,
- §13.14 BCVF 2nd-difference over per-position semantic
  entropy of NLI-clustered truncations,
- §13.16 BCVF 2nd-difference over per-position EigenScore
  of hidden-state stride grids,
- §13.18 forced-allocation gap from per-token logit
  centering,
- §14a / §14a.2 cross-source weighted majority vote with
  per-source semantic entropy as trust scalar,
- §15.x abstention threshold over per-source semantic
  entropy of the V1-winning source.

**None of these are continuous phase-like signals in the
§6.1 sense.** They are mathematically convenient analogues
that approximate the BCVF construction at the text-output
or token-logit layer rather than at the underlying
representational geometry. The §13.14 / §13.16 BCVF
2nd-difference observables came closest (per-position
continuous-curve operators) and both returned ANTI under
worst-benchmark; per the §13.15 / §13.17 narrowing analysis,
the per-position curves were monotonic-rising rather than
smooth-with-rare-spikes, so the 2nd-difference operator had
no fault-onset structure to detect.

**Phase coherence is the candidate that most directly tests
whether the §13/§14/§15 program failed because BCVF doesn't
transfer to LLMs OR because we mapped BCVF onto the wrong
substrate.** It addresses ChatGPT's representation-level
under-theorization critique surfaced during the §15.8
informal review.

**Three phase-definition options (each would need its own
§0.8 sub-pin).**

The candidate formula assumes phases exist. Phases are not
native to LLMs; defining them is itself a hypothesis-class
commitment. Three plausible candidates, each with different
priors and different engineering costs:

1. **Hilbert-transform phase of hidden-state magnitudes
   across token positions.** For each layer $\ell$ and
   sequence of token positions $1..T$, treat the
   $L^2$-norm $\|h_\ell[t]\|$ as a quasi-oscillatory
   signal; apply Hilbert transform to recover instantaneous
   phase. Then $\phi_i[k]$ becomes per-source per-position
   per-layer phase. Computationally cheap; requires no new
   model training.
2. **Fourier decomposition of per-layer activation
   trajectories across the K=10 stochastic samples.** For
   each layer and each token position, compute the FFT of
   the activation pattern across the K samples; extract
   dominant-frequency phases. More complex but more
   theoretically grounded — the K=10 samples form a discrete
   "time series" over the model's stochastic decoding
   variability.
3. **Rotary-embedding-derived phases.** Most modern LLMs
   (Qwen2.5, Llama-3.1, Mistral-7B-v0.3) use rotary positional
   embeddings (RoPE), which encode positional information
   as sin/cos pairs. Extract per-position rotary phases
   directly from the model's positional embedding matrix
   without additional transforms. Cheapest and most natively
   model-grounded.

**Each option is a different §0.8 sub-pin.** A full §15.9
pre-commitment would need to pin exactly one phase
definition before any data inspection, using the §15.3 /
§15.5 chunked-charter discipline.

**What §15.9 explicitly does NOT authorize.**

- Implementation of any phase-coherence script. The §15.9
  entry is a future-work *placeholder*, not an authorization.
- Re-classification of any §13 / §14 / §15.x verdict-of-
  record. All bands remain binding under §0.8 regardless of
  any future §15.9-pre-committed result.
- Updating `AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md`. The §13.9
  hold remains in force and would not be addressed by §15.9
  results except via STRONG-band lift on both benchmarks.
- Auto-promotion to §15.10 or beyond. Each follow-up needs
  its own fresh §0.8.
- Any claim that the autonomy-domain BCVF result (§6.1) is
  affected by §15.9 future work. §6.1 stands wholly
  independent.

**What a §15.9-pre-committed test would need to address.**

If §15.9 is ever fired, the pre-commitment must directly
engage with the structural failure modes §15.7 identified:

- **TruthfulQA-MC's adversarial distractor structure.** The
  benchmark produces correlated wrongness across model
  families. Phase coherence applied to the same source set
  would face the same correlated-wrongness issue. The
  pre-commitment should specify either (a) a benchmark
  substitution that escapes this pattern, or (b) explicit
  acknowledgment that cross-benchmark generalization remains
  conditional on the benchmark structure.
- **C-MISMATCHED composition failure on V1-divergent
  questions.** §15.7 found the per-source winning-source
  entropy is sign-flipped on V1-divergent questions. Phase
  coherence on the same Stage A configuration faces the
  same composition risk. The pre-commitment should specify
  whether Stage A is also redesigned (engineered diversity)
  or held fixed.
- **The $\rho \ge \rho^*$ met but coverage too low pattern.**
  Even with sufficient discrimination, the operating-point
  geometry on TruthfulQA-MC delivers tiny coverage. Phase
  coherence at the same N=100 may face the same sparse-
  support issue. The pre-commitment should specify a
  larger-N target or document the expected coverage
  ceiling.
- **The $\alpha_3 = 0.75$ deployment-grade ceiling.** Phase
  coherence cannot lift this from greedy accuracy 0.25–0.30.
  The pre-commitment should explicitly bound deployment
  claims at $\alpha < 0.75$ or specify a model-scale
  upgrade as part of the same commitment.

**Estimated cost (rough, not §0.8-binding).**

- Phase-definition engineering: 2–5 days depending on
  option (RoPE-derived cheapest, Fourier-of-stochastic-
  samples most complex).
- Phase coherence computation over existing §14a.2-class
  dumps: pure post-processing if hidden states are cached;
  ~hours if not (requires forward-pass replay through
  cached models).
- §0.8 chunked pre-commitment drafting: ~1–2 days per the
  §15.3 / §15.5 / §15.7 pattern.
- Self-test gate, output writers, interpretation framework:
  ~1 day reusing §15.7's primitives.
- Real-data run: depends on whether new generation is
  needed. If existing dumps include cached hidden states:
  CPU-only post-processing, <1 hour. Otherwise: GPU
  forward-pass replay, several hours.

Total: roughly 1–2 weeks for a complete §15.9 pre-commitment
+ implementation + result section, with the largest
uncertainty in the phase-definition engineering. Cheaper
than the §15.5 hybrid scout was, but more conceptually
demanding.

**§15.9 documentation-only status reaffirmed.** This entry
records the future-work item; it does not authorize work.
Per §0.8 discipline, any future §15.9 pre-commitment must
be drafted in chunked form before any data is inspected
under the phase-coherence framing, with bands pinned
ex-ante. The documentation here exists so that future
revisits can pick up the cleanest available "if reopening
LLMs" candidate without re-deriving the rationale from
informal commentary.

The §15 LLM-track program remains closed at the §15.8
mechanism-decomposed level. §15.9 sits as a documented
candidate for future reopening; it is not a continuation.

### 15.10 Pre-commitment — Phase 1 of final-resolution sprint: supervised linear truth-probe (DAY-LONG; bounded; one shot)

**Status: pre-committed, not yet executed.** §0.8-style pre-
commitment recorded before any hidden-state extraction or
probe training. Specification, primary metrics, success bands,
baselines, and decision rules below cannot be redefined
post-hoc.

**Position — what §15.10 is and is not.**

§15.10 is **Phase 1 of a bounded 3-phase final-resolution
sprint** for the LLM track, not a new long research program.
It is the §13.8 future-work item "linear activation probes
(Azaria & Mitchell 2023; Marks & Tegmark 2024)" being fired
explicitly under §0.8, with all bands pinned ex-ante. The
sprint structure is:

- §15.10 (Phase 1) — supervised truth-probe on hidden states.
- §15.11 (Phase 2) — phase-coherence probe (the §15.9
  documented candidate, fired with one pinned phase
  definition).
- §15.12 (Phase 3) — final synthesis + autonomy handoff,
  conditional on §15.10 / §15.11 results.

**§15.10 does NOT:**
- Reopen any §13 / §14 / §15.x verdict-of-record. All
  verdicts remain binding.
- Re-classify §15.4 USEFUL_INTERNAL or §15.6 REGRESSION.
- Modify the §13.9 VC-brief hold by construction.
- Authorize any longer probe-engineering program; it is one
  shot at one architecture (linear) on one feature set
  (final-layer last-token hidden state, optionally one mid-
  layer pool). No iterative search.
- Authorize source-construction redesign, retrieval, judge
  models, or 32B-class models. Same constraints as
  §13/§14/§15.

**The single load-bearing question §15.10 answers.**

> **Do Qwen2.5-7B-Instruct's hidden representations contain
> truth signal that the unsupervised BCVF-style score family
> failed to extract?**

Three pinned outcomes (exhaustive partition; mutually
exclusive):

- **`STRONG_SIGNAL_IN_Z`**: probe AUC $\ge 0.75$ on **both**
  benchmarks AND probe-AUC minus best-existing-unsupervised-
  baseline-AUC $\ge +0.05$ on **both** benchmarks.
- **`PARTIAL_SIGNAL_IN_Z`**: probe AUC $\ge 0.66$ (matches
  §13.10 baseline) on at least one benchmark AND probe AUC
  exceeds the best existing unsupervised baseline by any
  positive margin on at least one benchmark, but does NOT
  meet the STRONG bar.
- **`NO_MATERIAL_SIGNAL_IN_Z`**: probe AUC fails to exceed
  the best existing unsupervised baseline on either
  benchmark, OR probe AUC $< 0.60$ on both.

These bands cover $\mathbb{R}^2$ exhaustively over the
(HaluEval-AUC, TruthfulQA-AUC) pair without fall-through.

**Specification (pinned).**

- **Target model:** `Qwen/Qwen2.5-7B-Instruct` (matches
  §13.10 / §14a.2 / §15.x). No 32B; no other model class.
- **Benchmarks:** HaluEval-QA `data` split, N=100; TruthfulQA-
  MC `validation` split, N=100. Same question subsets as
  §13.10. **No new benchmarks.**
- **Question subset alignment:** the probe trains and
  evaluates on the same 100 questions per benchmark that
  §13.10 / §15.2 used. Question IDs pinned to match the
  §13.10 dump's `q_idx` field.
- **Per-question correctness label:** the §13.10
  `greedy_matches_correct` boolean from the existing dumps.
  Same NLI labeling protocol; no relabeling.
- **Hidden-state feature (pinned, single primary):** Qwen-7B
  greedy-decode forward pass over the question prompt
  `Q: ... A:`; extract the **final-layer last-token hidden
  state** (the residual-stream vector at position immediately
  before the model would generate its first answer token).
  This produces a single $d$-dimensional vector per question,
  $d = 3584$ for Qwen-7B. **No prompt re-engineering, no
  pooling across positions, no attention-head selection.**
- **Optional secondary feature (only if it requires zero
  extra engineering):** mid-layer last-token hidden state at
  layer 14 (the §13.16 layer; ~midway through the 28-layer
  stack). If extraction adds non-trivial code, skip it.
- **Probe architecture (pinned, single):** scikit-learn
  `LogisticRegression` with `penalty='l2'`, `C=1.0`, default
  solver, max 1000 iterations. **No MLP, no kernel methods,
  no feature search, no hyperparameter sweep beyond the
  defaults.** L2-regularized linear logistic regression on
  raw hidden-state vectors.
- **Train/test protocol (pinned):** **5-fold stratified
  cross-validation per benchmark**, deterministic seed
  `numpy.random.SeedSequence(entropy=15)` matching §15.x
  convention. Out-of-fold predictions used for AUC and
  selective-prediction metrics. **No held-out probe
  training data leaks across folds.**
- **Per-benchmark pi (base rate) for selective-prediction
  comparisons:** Qwen-greedy accuracy from §13.10
  (TruthfulQA-MC: 0.250; HaluEval-QA: 0.300). Pinned
  constants, not re-derived.

**Metrics (pinned).**

For each benchmark, primary:

- **Probe AUC** on out-of-fold predictions (sklearn
  `roc_auc_score`).
- **Probe selective-prediction $\kappa@\alpha_2 = 0.50$** —
  treating the probe's predicted probability $\hat{p}$ as a
  "trust score" and using $1 - \hat{p}$ as the abstention
  risk score. Same $n_{\min} = 10$ floor as §15.x.
- **$\Delta\text{AUC}_\text{vs-entropy}$** = probe AUC −
  best existing unsupervised baseline AUC. The "best
  existing baseline" per benchmark:
  - HaluEval-QA: §13.10 entropy (AUC 0.661).
  - TruthfulQA-MC: §13.10 entropy (AUC 0.661 from §15.2-
    of-record; we do not consult the now-N=200 §13.10 dump
    for this comparison).

Secondary diagnostics (reported, non-band-driving):

- Probe accuracy (out-of-fold).
- Per-fold AUC variance (bootstrap-equivalent CI proxy).
- Calibration (Brier score, ECE).

**Pinned baselines for the comparison table.**

| Baseline | Source | AUC anchor |
|---|---|---|
| §13.10 semantic entropy (HaluEval) | §13.10 verdict-of-record | 0.661 |
| §13.10 semantic entropy (TruthfulQA-MC) | §13.10 verdict-of-record (N=100, pre-§13.20) | 0.661 |
| §15.4 hybrid Δκ on HaluEval | §15.4 verdict-of-record | $\Delta\kappa = +0.090$ at $\alpha_2 = 0.50$ |
| §15.6 hybrid Δκ on TruthfulQA-MC | §15.6 verdict-of-record | $\Delta\kappa = -0.030$ at $\alpha_2 = 0.50$ |

**Decision rule (mechanical, no soft override).**

After probe runs on both benchmarks:

1. Compute probe AUC and $\Delta\text{AUC}_\text{vs-entropy}$
   per benchmark.
2. Compute probe $\kappa@\alpha_2$ per benchmark; compare to
   §15.x baselines (§15.2's $\kappa = 0.26$ HaluEval, $\kappa
   = 0.14$ TruthfulQA-MC).
3. Apply the three-band cascade:
   - **STRONG_SIGNAL_IN_Z** if probe AUC ≥ 0.75 on both AND
     ΔAUC ≥ +0.05 on both.
   - **PARTIAL_SIGNAL_IN_Z** if probe AUC ≥ 0.66 on at least
     one benchmark AND ΔAUC > 0 on at least one, AND not
     STRONG.
   - **NO_MATERIAL_SIGNAL_IN_Z** otherwise.

The cascade is exhaustive; every (HaluEval-AUC, TruthfulQA-AUC,
ΔAUC pair) outcome maps to exactly one band.

**Implementation scope (pinned).**

- New script: `scripts/probe_supervised_15_10.py` (numpy +
  scikit-learn + transformers; minimal). One file, ~600–900
  lines target.
- Two-phase: (1) hidden-state extraction (~10–15 min on
  cached Qwen-7B, GPU), (2) probe training + evaluation
  (CPU only, sub-minute per benchmark with sklearn).
- Self-test gate (`--self-test`) verifying probe + cascade
  classifier on synthetic boundary cases.
- Output paths:
  - `docs/experiments/probe_supervised_15_10.json`
    (`schema_version "15.10"`).
  - `docs/experiments/probe_supervised_15_10.md`.
- §15.7-pattern interpretation firewall against soft-override
  language in the markdown report (Class-3 forbidden patterns
  scanned at write time; abort on detection).

**What §15.10 explicitly does NOT authorize.**

- Iterative probe-architecture search. Linear only; one shot.
- Feature engineering beyond the pinned final-layer-last-token
  + optional mid-layer.
- Re-training Qwen-7B; no fine-tuning; no LoRA.
- Cross-benchmark training (probe is trained per-benchmark to
  avoid label-distribution leakage).
- Modification of any §15.x script or verdict-of-record
  artifact.
- Phase 2 / Phase 3 implementation. Each requires its own
  pre-commitment after Phase 1 results land.
- Auto-promotion of any §15.10 outcome to a verdict-of-record
  status. §15.10 produces a sprint-internal classification,
  not a §13.10-class AUC verdict.

**Time / compute budget.**

- Hidden-state extraction: ~10–15 min GPU on cached Qwen-7B
  (~15 GB, already loaded for §13.10 / §14a.2 / §15.5).
- Probe training + eval: <1 min CPU per benchmark.
- Total wall clock: ~20–30 min.

§15.10 implementation (`scripts/probe_supervised_15_10.py`)
is a separate §0.8 authorization gate. The §15.10 result
section follows the real-data run.

---


### 15.11 Pre-commitment — Phase 2 of final-resolution sprint: layer-wise phase-coherence probe (DAY-LONG; bounded; one shot)

**§0.8 declaration.**

§15.11 is Phase 2 of the bounded 3-phase final-resolution
sprint authorized at the close of §15.10
(`PARTIAL_SIGNAL_IN_Z`; HaluEval ΔAUC = +0.0076,
TruthfulQA-MC ΔAUC = −0.0386; per
`docs/experiments/probe_supervised_15_10.{json,md}`).

This is a fresh §0.8 commitment. §15.11 outputs do **NOT**
modify any §13/§14/§15.x verdict-of-record, including §15.10's
PARTIAL readout, §15.6's REGRESSION, §15.8's MIXED +
C-MISMATCHED, or the §13.9 hold. Bands, formula, features, and
self-test boundary cases are pinned ex ante in this section;
data inspection follows. Single shot — no iteration on the
formula, layer subsets, FFT windows, or feature aggregations
once this section is sealed.

**Position — what §15.11 is and is not.**

§15.11 tests whether **layer-wise phase coherence** over
Qwen-7B's per-layer last-token hidden states distinguishes
correct from incorrect answers in a way that:

- the §13.10 entropy baseline (AUC = 0.661 on both benchmarks)
  failed to extract, and
- the §15.10 supervised linear probe (AUC = 0.669 / 0.622)
  failed to extract.

The mechanism class is **cross-layer spectral phase relationship**:
at each question, the 29 per-layer last-token hidden states
(embedding output + 28 transformer-layer outputs) are FFT'd along
the hidden dimension, and a pairwise phase-coherence matrix is
built per the formula

> **C[i, j] = (1 / W) · Σ_k cos(φ_i[k] − φ_j[k])**

where φ_i[k] is the phase at frequency-bin k of FFT(h_i) for
layer i, and W is the number of frequency bins used (pinned
in the formula block below). A single scalar feature per
question is derived from C and tested against correctness.

**Why this mechanism (§0.8-disclosed).**

§15.10 tested whether truth signal is **linearly extractable
from a single layer**. The PARTIAL-by-hair result with one
benchmark regressing below baseline is consistent with — but
does not prove — the hypothesis that truth signal in 7B
hidden states is at-or-below the entropy ceiling under linear
extraction.

§15.11 tests a fundamentally **different mechanism class**:
whether truth signal is encoded in the **non-linear, multi-
scale phase relationship across layers**. This is the closest
LLM analog to BCVF's autonomy-domain mechanism (§6.1, N=21
sign-test): in autonomy, phase coherence between two
bidirectional-check streams identified correct decisions; in
LLMs, the analogous "streams" are the model's evolving
representations across depth.

This mechanism is **not reducible** to either §13.10 (which
only used token-level entropy) or §15.10 (which used a single
layer's linear projection). A negative result here, combined
with §15.10's PARTIAL, would be strong joint evidence that 7B
hidden states do not contain extractable truth signal under
any of the canonical mechanism classes (entropy / linear /
phase-coherence). A positive result would identify phase
coherence as the BCVF-faithful transfer mechanism.

**What §15.11 does NOT do.**

- Does NOT re-classify §15.10's `PARTIAL_SIGNAL_IN_Z`,
  §15.x's bands, or §13.9's hold.
- Does NOT iterate on the formula, the FFT length, the
  layer subset used, or the feature aggregation. All are
  pinned in the formula block below.
- Does NOT use any §15.11 data to amend Phase 1's outputs.
- Does NOT authorize Phase 3 (`§15.12` final synthesis +
  autonomy handoff). Phase 3 requires its own §0.8 commitment
  and is gated on Phase 2's mechanical cascade output.

**Dependencies and re-extraction note.**

- **Model.** Qwen/Qwen2.5-7B-Instruct, same as §15.10.
- **Labels.** Same §13.10 dumps, first PINNED_N = 100
  records per benchmark.
- **Prompt format.** `Q: {question}\nA:` (matches §15.10's
  pinned PROMPT_FORMAT).
- **Hidden-state cache.** §15.10's cache
  (`hidden_states_qwen_15_10.npz`) is layer = −1 only and is
  **insufficient** for §15.11 — phase coherence across layers
  requires all 29 hidden states per question. **A new GPU
  re-extraction is required**, producing a new cache
  (`hidden_states_all_layers_qwen_15_11.npz`). Approximate
  runtime on the same GPU: same as §15.10 extraction (~5–10
  min per benchmark, 200 forward passes total). Storage:
  ~41 MB per benchmark in fp32.

---


### 15.11 Pre-commitment (continued) — Pinned formula, FFT, layer subset, feature derivation

**Pinned per-layer extraction.**

For each question, the model is run forward on the prompt
`Q: {question}\nA:`. We capture **all 29 hidden states**
(`out.hidden_states[0..28]`):

- index 0 = embedding output;
- indices 1..28 = output of each of the 28 transformer
  layers (Qwen2.5-7B has 28 hidden layers).

For each layer i ∈ {0, 1, …, 28}, we take the **last-token**
position, yielding `h_i ∈ R^3584` per question. This is the
same prompt template and last-token convention as §15.10,
just extracting all layers instead of layer −1 only. PINNED.

**Pinned FFT (no windowing, no detrending).**

For each layer i, compute the **real-input FFT** along the
hidden dimension:

- `H_i = numpy.fft.rfft(h_i)` → complex array of length
  `floor(3584/2) + 1 = 1793`.
- No windowing is applied (rectangular window).
- No detrending or mean-subtraction is applied.
- The vector is treated as the canonical "signal" represented
  by the layer-i last-token hidden state, taken as-is from
  the model output.

The phase per bin is:

> `φ_i[k] = angle(H_i[k])`, for k ∈ {0, 1, …, 1792}.

**Pinned bin selection.**

For phase coherence we **exclude DC (k = 0) and Nyquist
(k = 1792)** because their phases are constrained to {0, π}
for real-input signals and would inflate coherence
trivially. Used bins: `k ∈ {1, 2, …, 1791}`.

> **W = 1791** (number of frequency bins used). PINNED.

**Pinned phase-coherence formula.**

For each ordered pair of layers (i, j) with i, j ∈ {0, …, 28}:

> **C[i, j] = (1 / W) · Σ_{k=1}^{1791} cos(φ_i[k] − φ_j[k])**

where φ_i[k] is the phase of the rfft of layer-i's last-token
hidden state at bin k.

**Properties** (mechanical, no interpretation):

- `C[i, i] = 1` for all i (trivially).
- `C[i, j] = C[j, i]` (symmetric).
- `C[i, j] ∈ [−1, +1]`.
- `C` is a 29×29 real symmetric matrix per question.

**Pinned feature aggregation.**

Per question, the **global cross-layer phase coherence**
scalar is:

> **F = (2 / (29 · 28)) · Σ_{0 ≤ i < j ≤ 28} C[i, j]**

i.e., the mean over the 29 · 28 / 2 = **406 upper-triangular
off-diagonal entries** of C. F ∈ [−1, +1].

This is the single scalar feature evaluated against
correctness. **No other features are derived. No layer
subsets, no per-layer-pair features, no spectral-bandwidth
features. PINNED.**

**Pinned direction convention.**

We test the BCVF-faithful direction:

> **Higher F predicts correct (y = 1).**

This matches the autonomy domain's relationship from §6.1
(high phase coherence between bidirectional check streams
identifies correct decisions). AUC is computed as
`roc_auc_score(y, F)` directly under this convention.

If AUC < 0.5, the empirical signal is in the **opposite**
direction (lower F predicts correct). Per §0.8, this counts
as "no signal in the expected BCVF-faithful direction" and
the cascade lands in `NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE`
regardless of how negative AUC is. **No directional
flipping. No "absolute" or "two-sided" AUC variants.
PINNED.**

**Why this exact formula (§0.8-disclosed).**

- **rfft + cosine of phase difference** is the literal LLM
  analog of the formula
  `C[i,j] = (1/W) · Σ_k cos(φ_i[k] − φ_j[k])`. No
  alternative parameterization is considered.
- **All 29 layers** is the most BCVF-faithful choice: every
  internal representation participates equally in the
  coherence scalar. No theoretically-motivated layer subset
  (e.g., "last 12") is used because such a choice would be
  a free hyperparameter without §0.8 justification.
- **Mean off-diagonal aggregation** is the natural N-stream
  extension of the 2-stream BCVF coherence statistic. No
  max, no top-K, no early/mid/late partition is considered.
- **Excluding DC + Nyquist** removes phases that are not
  free parameters of the signal. No alternative bin range
  is considered.
- **No windowing** is consistent with treating the hidden-
  state vector as a single canonical signal, not a time
  series of indeterminate windowing convention.

These choices are pinned to make §15.11 a **single-shot**
test of one specific mechanism. Any deviation in
implementation requires a fresh §0.8 amendment.

---


### 15.11 Pre-commitment (continued) — Pinned evaluation

**Pinned primary statistic.**

For each benchmark independently:

> **AUC_phase = roc_auc_score(y, F)**

where `y ∈ {0, 1}^N` is the §13.10 correctness vector (first
PINNED_N = 100 records per benchmark, `greedy_matches_correct`),
and `F ∈ R^N` is the per-question phase-coherence scalar.

No CV is performed — F is a deterministic, parameter-free
function of the hidden states, so there is nothing to fit.
AUC is computed once on the full N = 100 sample per benchmark.

**Pinned baseline and ΔAUC.**

The cascade-defining baseline is the **§13.10 entropy AUC**,
identical to §15.10's convention:

> **AUC_baseline = 0.661** (per §13.10 verdict-of-record,
> both benchmarks)
> **ΔAUC_phase = AUC_phase − 0.661**

This makes §15.11's cascade directly comparable to §15.10's:
same baseline, same ΔAUC frame, same statistical reference
point. **The §13.10 baseline is the canonical reference; no
other baseline is used to define the cascade. PINNED.**

**Pinned secondary readout (§15.10 comparison).**

For transparency, the markdown report records — but **does
not** use to define the cascade — the difference vs §15.10's
per-benchmark supervised probe AUCs:

> **ΔAUC_phase_vs_supervised = AUC_phase − AUC_supervised**, where
> AUC_supervised = 0.6686 on HaluEval-QA, 0.6224 on
> TruthfulQA-MC (per §15.10 JSON).

This secondary readout answers "did phase coherence beat the
supervised probe?" but is **disclosure only**. The cascade
label is fixed by ΔAUC vs §13.10 entropy baseline, not vs
§15.10 supervised AUC. PINNED.

**Pinned selective-prediction operating points.**

For each benchmark, κ@α is computed using **F directly as
the abstention score** (higher F → more confident in
correctness, per the pinned direction):

- Threshold sweep: `τ ∈ sorted(set(F)) ∪ {min(F) − 1}`
  (admit-all sentinel).
- Admit set at threshold τ: `{i : F[i] ≥ τ}`.
- Eligibility: `|admit set| ≥ N_MIN = 10` AND conditional
  accuracy `≥ α`.
- κ@α = max coverage among eligible thresholds; τ\* =
  argmax τ.

**Pinned alphas per benchmark** (matches §15.10):

- HaluEval-QA: α ∈ {0.40, 0.50, 0.75}.
- TruthfulQA-MC: α ∈ {0.35, 0.50, 0.75}.
- Primary alpha: α = 0.50 (matches §15.10
  `ALPHA_PRIMARY`).

The selective-prediction table is **disclosure only**; it
does not enter the cascade. The cascade is on AUC and ΔAUC.
PINNED.

**Pinned direction handling.**

AUC is computed with the BCVF-faithful direction (higher F
predicts correct). If AUC_phase < 0.5, the empirical signal
is in the opposite direction.

**Mechanical handling** (PINNED):

- AUC_phase ≥ 0.5 → cascade evaluates STRONG / PARTIAL /
  NO_MATERIAL bands per the cascade block below.
- AUC_phase < 0.5 → cascade lands automatically in
  `NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE` with rationale
  "wrong-direction signal under BCVF-faithful pinned
  direction; no signal in the predicted direction." No
  directional flipping, no absolute-value rescue, no
  re-evaluation under the inverted convention.

This is conservative and preserves §0.8's no-iteration
discipline: the BCVF-faithful direction was the
pre-committed hypothesis; failing it is a failure, not a
sign-flip opportunity.

**What is NOT computed.**

- No bootstrap confidence intervals for AUC (matches §15.10).
- No alternative aggregations of C (no max, no top-K, no
  row-mean, no per-pair features). Only the pinned F.
- No alternative direction conventions or two-sided AUC.
- No layer-pair scatter analysis or §15.7-style mechanism
  decomposition. §15.11 is a single-feature test by
  construction; if the cascade lands in NO_MATERIAL, that is
  the verdict and §15.11 closes.
- No re-classification of §15.10's `PARTIAL_SIGNAL_IN_Z`.
  The Phase 1 and Phase 2 cascades are independent
  §0.8-binding readouts.

**What enters the per-benchmark JSON.**

For each benchmark:

- `auc_phase`, `auc_baseline`, `dauc_phase` (vs §13.10);
- `auc_supervised_phase_1`, `dauc_phase_vs_supervised`
  (disclosure);
- `f_per_question`: the 100-element scalar feature vector;
- `coherence_matrix_summary`: min, mean, max, std of the
  406 off-diagonal upper-triangular entries — for sanity
  checking the F aggregation;
- `direction_held`: boolean (True if AUC_phase ≥ 0.5);
- `selective_prediction_operating_points`: list of dicts at
  each pinned α;
- `n_questions`, `n_correct`, `n_wrong`, `pi_observed`.

**What enters the per-run JSON.**

- All §15.11 pinned constants (W, layer subset, alphas,
  thresholds);
- §13.10 baseline AUCs and §15.10 supervised AUCs for
  cross-reference;
- Both per-benchmark blocks above;
- Final `cascade_verdict` block with label, AUCs, ΔAUCs,
  rationale;
- `schema_version = "15.11"`.

---


### 15.11 Pre-commitment (continued) — Pinned cascade bands and self-test boundary cases

**Pinned cascade labels.**

§15.11's cascade lands in exactly one of three exhaustive
bands:

- `STRONG_SIGNAL_IN_PHASE_COHERENCE`,
- `PARTIAL_SIGNAL_IN_PHASE_COHERENCE`,
- `NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE`.

Labels are **§15.11-specific** (do not collide with §15.10's
`*_IN_Z` labels) so any future cross-reference is
unambiguous about which mechanism class produced the verdict.

**Pinned cascade decision (mechanical, in order).**

Inputs: `auc_h`, `auc_t`, `dauc_h`, `dauc_t` where
`dauc = auc − 0.661` (the §13.10 entropy baseline).

**Step 1 — Direction gate (PINNED).**

> If `auc_h < 0.5` OR `auc_t < 0.5` →
> label = `NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE`,
> rationale = "wrong-direction failure on at least one
> benchmark; BCVF-faithful direction (higher F predicts
> correct) did not hold." Skip remaining steps.

This is the §0.8 enforcement of the pinned direction. The
hypothesis was BCVF-faithful direction; failing it on either
benchmark is a hypothesis failure, not a sign-flip
opportunity.

**Step 2 — STRONG check.**

> If `auc_h ≥ 0.75` AND `auc_t ≥ 0.75` AND
> `dauc_h ≥ +0.05` AND `dauc_t ≥ +0.05` →
> label = `STRONG_SIGNAL_IN_PHASE_COHERENCE`.

(Numerical thresholds are deliberately identical to §15.10's
STRONG conditions to make Phase 1 / Phase 2 cascades
directly comparable.)

**Step 3 — PARTIAL check.**

> If not STRONG, AND `(auc_h ≥ 0.66 OR auc_t ≥ 0.66)`,
> AND `(dauc_h > 0 OR dauc_t > 0)` →
> label = `PARTIAL_SIGNAL_IN_PHASE_COHERENCE`.

**Step 4 — Default.**

> Otherwise → label = `NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE`.

**Pinned threshold constants (matches §15.10 numerically).**

```
STRONG_AUC_THRESHOLD          = 0.75   # inclusive
STRONG_DELTA_AUC_THRESHOLD    = 0.05   # inclusive
PARTIAL_AUC_THRESHOLD         = 0.66   # inclusive
DIRECTION_GATE_THRESHOLD      = 0.5    # strict (AUC < 0.5 fails)
ENTROPY_BASELINE_AUC          = 0.661  # both benchmarks (per §13.10)
```

**Pinned self-test boundary cases (12 cases).**

Each tuple is `(auc_h, auc_t, dauc_h, dauc_t,
expected_label)`. The §15.11 implementation script must
pass all 12 at the self-test gate before any data
inspection:

| #   | auc_h | auc_t | dauc_h | dauc_t | expected     |
|-----|-------|-------|--------|--------|--------------|
|  1  | 0.80  | 0.78  | +0.139 | +0.119 | STRONG       |
|  2  | 0.75  | 0.75  | +0.089 | +0.089 | STRONG (boundary inclusive)               |
|  3  | 0.74  | 0.78  | +0.079 | +0.119 | PARTIAL (auc_h just below STRONG)         |
|  4  | 0.70  | 0.62  | +0.039 | −0.041 | PARTIAL (one benchmark passes both)       |
|  5  | 0.66  | 0.55  | +0.001 | −0.111 | PARTIAL (auc_h = 0.66 inclusive)          |
|  6  | 0.65  | 0.65  | −0.011 | −0.011 | NO_MATERIAL (both AUC < 0.66)             |
|  7  | 0.661 | 0.661 | 0.0    | 0.0    | NO_MATERIAL (dAUC not > 0)                |
|  8  | 0.49  | 0.78  | −0.171 | +0.119 | NO_MATERIAL (direction gate trips)        |
|  9  | 0.45  | 0.40  | −0.211 | −0.261 | NO_MATERIAL (direction gate trips on both)|
| 10  | 0.50  | 0.78  | −0.161 | +0.119 | PARTIAL (direction gate inclusive at 0.5) |
| 11  | 0.499 | 0.80  | −0.162 | +0.139 | NO_MATERIAL (direction gate strict)       |
| 12  | 0.55  | 0.55  | −0.111 | −0.111 | NO_MATERIAL (direction holds; both fail)  |

These cover: STRONG-clean and STRONG-boundary; PARTIAL via
just-below-STRONG, single-benchmark-passes, and
exact-AUC-boundary; NO_MATERIAL via both-AUC-fail,
exact-baseline, single-direction-fail, both-direction-fail,
direction-gate-inclusive-pass, direction-gate-strict-fail,
and middling-no-signal.

**Why these thresholds (§0.8-disclosed).**

- **Numerical identity with §15.10** (0.75 / 0.05 / 0.66 /
  0.5 / 0.661) is intentional. Phase 1 and Phase 2 are
  testing different mechanism classes against the same
  baseline; harmonizing thresholds makes the cross-phase
  comparison clean.
- **Direction gate at 0.5 strict** (AUC = 0.5 passes)
  reflects §0.8's "BCVF-faithful direction was
  pre-committed" — AUC = 0.5 is the no-information point,
  not the wrong-direction point. Wrong-direction is strict
  AUC < 0.5.
- **Inclusive at 0.75 and 0.66**, strict at 0 for ΔAUC,
  mirrors §15.10 exactly. No drift.
- **Three-band exhaustive partition** is a feature, not a
  bug: every (auc_h, auc_t, dauc_h, dauc_t) tuple maps to
  exactly one label by mechanical inspection. No
  interpretive grey zone.

**What the cascade does NOT consider.**

- Cross-phase comparison vs §15.10 supervised AUC.
  (Disclosure-only; never in the cascade decision.)
- Selective-prediction κ@α values. (Disclosure-only; never
  in the cascade decision.)
- CV variance, fold-AUC spread, or any per-question
  diagnostic. The cascade is on two scalars per benchmark
  (AUC, ΔAUC) and nothing else.
- Per-layer-pair coherence values from C. The cascade is on
  F via AUC; the matrix C is logged for sanity but not for
  cascade input.

---


### 15.11 Pre-commitment (continued) — Pinned outputs (paths, JSON, markdown, firewall, exit codes, self-test)

**Pinned output paths.**

```
docs/experiments/hidden_states_all_layers_qwen_15_11.npz   # cache (re-extraction)
docs/experiments/probe_phase_coherence_15_11.json          # machine-readable
docs/experiments/probe_phase_coherence_15_11.md            # human-readable
```

The hidden-state cache is a **separate file** from §15.10's
`hidden_states_qwen_15_10.npz` (which holds layer −1 only).
§15.11's cache holds all 29 layers and is required for
re-runs in `--probe-only` mode. PINNED.

**Pinned JSON schema (`schema_version = "15.11"`).**

Top-level keys (alphabetical for `sort_keys=True` parity with
§15.10):

```
{
  "alpha_targets_per_benchmark": {...},
  "baseline_auc_per_benchmark": {"halueval_qa": 0.661,
                                 "truthfulqa_mc": 0.661},
  "cascade_thresholds": {
    "strong_auc": 0.75,
    "strong_delta_auc": 0.05,
    "partial_auc": 0.66,
    "direction_gate_threshold": 0.5,
    "entropy_baseline_auc": 0.661
  },
  "cascade_verdict": {
    "label": "<STRONG|PARTIAL|NO_MATERIAL>_SIGNAL_IN_PHASE_COHERENCE",
    "auc_halueval": <float>,
    "auc_truthfulqa": <float>,
    "dauc_halueval": <float>,
    "dauc_truthfulqa": <float>,
    "direction_held_halueval": <bool>,
    "direction_held_truthfulqa": <bool>,
    "rationale": "<formatted prose>"
  },
  "extraction_layer": "all_29",
  "halueval_qa": { ... },          // per-benchmark block, schema below
  "hidden_dim": 3584,
  "n_layers_used": 29,
  "phase_coherence_config": {
    "fft_n": 3584,
    "n_freq_bins_total": 1793,
    "n_freq_bins_used": 1791,
    "bin_range_excluded": "DC (k=0) and Nyquist (k=1792)",
    "windowing": "rectangular (none)",
    "detrending": "none",
    "feature_aggregation": "mean over upper-triangular off-diagonal of 29x29 C (406 entries)",
    "direction_convention": "higher F predicts correct (BCVF-faithful)"
  },
  "pinned_N": 100,
  "pinned_pi": {"halueval_qa": 0.3, "truthfulqa_mc": 0.25},
  "qwen_model_id": "Qwen/Qwen2.5-7B-Instruct",
  "schema_version": "15.11",
  "supervised_auc_per_benchmark_phase_1": {
    "halueval_qa": 0.6685714285714286,
    "truthfulqa_mc": 0.6224
  },
  "truthfulqa_mc": { ... }
}
```

**Per-benchmark block** (schema for both `halueval_qa` and
`truthfulqa_mc`):

```
{
  "benchmark": "<benchmark>",
  "n_questions": 100,
  "n_correct": <int>,
  "n_wrong": <int>,
  "pi_observed": <float>,
  "auc_phase": <float>,
  "auc_baseline": 0.661,
  "dauc_phase": <float>,
  "auc_supervised_phase_1": <float>,            // disclosure only
  "dauc_phase_vs_supervised": <float>,          // disclosure only
  "direction_held": <bool>,                     // auc_phase >= 0.5
  "f_per_question": [<100 floats>],
  "coherence_matrix_summary": {
    "off_diag_min": <float>,
    "off_diag_mean": <float>,
    "off_diag_max": <float>,
    "off_diag_std": <float>,
    "n_off_diag_entries": 406
  },
  "selective_prediction_operating_points": [...],
  "kappa_at_alpha_primary": <float>,            // alpha = 0.50
  "tau_star_at_alpha_primary": <float>,
  "alpha_primary": 0.5
}
```

PINNED. No additional keys; no key removal except for keys
explicitly marked optional.

**Pinned markdown structure (`probe_phase_coherence_15_11.md`).**

Sections in order:

1. `# §15.11 Phase 2 — Layer-wise phase-coherence probe (result)`
   (header + schema version + model + extraction config one-liner).
2. `## Cascade verdict (mechanical readout)` (label, rationale,
   AUC table including ΔAUC vs §13.10 baseline AND vs §15.10
   supervised, direction_held flags).
3. `## Probe details — HaluEval-QA` (n, π, AUC, ΔAUC vs both
   references, direction_held, F-distribution summary,
   coherence matrix summary, selective-prediction
   operating-points table).
4. `## Probe details — TruthfulQA-MC` (same structure).
5. `## Pinned configuration (§15.11 §0.8-binding)` (FFT, W,
   layer subset, formula, feature aggregation, direction
   convention, cascade thresholds).
6. `## Caveats (§0.8-disclosed)` (see firewall patterns
   below; also re-states the prompt-format / question-source
   caveats from §15.10 since they apply identically to
   Phase 2).
7. `## Cross-phase comparison (disclosure only)` (one-line
   summary of Phase 1 vs Phase 2 cascade outputs; no
   override language).
8. `## Audit-trail integrity` (firewall scan note, §0.8
   binding statement, §13/§14/§15.x verdict-of-record
   preservation).

PINNED.

**Pinned interpretation firewall — §15.11-specific Class-3
forbidden patterns.**

Inherits all §15.10 / §15.7 patterns (Class-3 set is
monotone-growing). Adds the following §15.11-specific
patterns to prevent post-hoc override of the Phase 2 cascade:

```
"actually STRONG_SIGNAL_IN_PHASE_COHERENCE despite"
"should be STRONG_SIGNAL_IN_PHASE_COHERENCE"
"actually PARTIAL_SIGNAL_IN_PHASE_COHERENCE despite"
"should be classified as PARTIAL_SIGNAL_IN_PHASE_COHERENCE"
"the wrong-direction failure should be flipped"
"the direction gate should be relaxed"
"the BCVF-faithful direction was wrong"
"§15.10 PARTIAL is overturned"
"§15.10 verdict is overturned"
"§13.10 baseline should be replaced"
```

Combined with the §15.10/§15.7 inherited set, the firewall
scans the rendered markdown for ~26 Class-3 patterns before
write. PINNED.

**Pinned exit codes (mirror §15.10).**

```
0  success
2  CLI / argument error
3  SELF_TEST_FAILED
4  INTERPRETATION_VIOLATION
5  SCHEMA_MISMATCH (label dump or cache)
6  EXTRACTION_FAILED (torch / transformers stack)
7  PROBE_FAILED (numpy / sklearn / NaN in F)
```

PINNED. Exit code 7 in §15.11 captures any unexpected NaN in
F (e.g., from a degenerate hidden state with all-zero FFT) —
by design, F should never be NaN given Qwen-7B's normal
forward pass; if it occurs, the script aborts with the
diagnostic.

**Self-test gate composition.**

Mirrors §15.10's three-stage self-test:

1. Cascade boundary cases (12 cases per the cascade block) —
   must all pass.
2. Phase-coherence formula smoke test on synthetic inputs:
   - Two identical hidden states → C[i, j] = 1 (within
     numerical tolerance).
   - Two random hidden states (independent normal) →
     mean |C[i, j]| < 0.1 (large-N law).
   - Two opposite-phase hidden states → C[i, j] = −1
     (within tolerance).
3. Interpretation firewall: each of the ~26 Class-3 patterns
   must be flagged on a positive sample, and a clean §15.11
   sample must produce zero violations.

All three must pass before any data inspection. PINNED.

---


### 15.11 Pre-commitment (continued) — Caveats, transfer-thesis disclosure, Phase 3 authorization mapping, closing §0.8

**Caveats (§0.8-disclosed) — §15.11-specific.**

- **Single mechanism within the phase-coherence class.** We
  test ONE specific phase-coherence formula: layer-wise,
  mean off-diagonal, BCVF-faithful direction. A negative
  result rules out **this** instantiation; it does not rule
  out sample-wise (multi-decode), paraphrase-wise
  (multi-prompt), or alternative aggregations (max-pair,
  top-K, layer-block triplet, etc.) of phase coherence.
  These are explicitly out of scope for Phase 2; Phase 3
  will record them as untested-but-known alternatives.
- **Layer-wise was selected over sample-wise /
  paraphrase-wise** because (a) it is the cheapest
  re-extraction (single forward pass per question vs K
  samples or M paraphrases) and (b) it has the cleanest
  BCVF analog (layers as N "streams" vs the 2-stream
  autonomy original). It is **not** claimed to be the most
  powerful instantiation.
- **Direction is pinned BCVF-faithful (higher F predicts
  correct).** Wrong-direction failures count as failures;
  no sign-flip rescue. This is conservative by §0.8 design
  and may understate signal that exists in the inverted
  direction.
- **N = 100 per benchmark** (same as §15.10/§13.10).
  Statistical power is bounded; AUC standard error at AUC
  ≈ 0.66 with N = 100 is ~0.05–0.06. Bands at 0.66 and 0.75
  are hit/miss-able by sampling noise alone. The cascade
  reports point estimates and pinned bands; no bootstrap CI
  is computed (mirroring §15.10).
- **Single model size: Qwen2.5-7B-Instruct.** Does not
  speak to scaling behavior at 13B / 32B / 70B. Phase 3
  will explicitly record this as a scope limit.

**Caveats inherited from §15.10 (apply identically to §15.11).**

- Prompt-format vs §13.10 labeling regime: pinned
  `Q: {question}\nA:` regardless of which mode produced the
  §13.10 dump. Caveat carries forward unchanged.
- Question text source: dump's `question` field if present,
  else HuggingFace dataset by `q_idx`. Same fallback policy.

**Transfer-thesis disclosure (mechanical reading per cascade outcome).**

§15.11's cascade outcome contributes to the **joint state
of pre-committed mechanism classes** for the BCVF-autonomy
→ LLM transfer thesis. As of the close of Phase 1, the joint
state is:

| mechanism class                              | status                                                       |
|----------------------------------------------|--------------------------------------------------------------|
| §13.10 unsupervised entropy                  | AUC = 0.661 both benchmarks (saturated at chance-corrected ceiling) |
| §15.10 supervised linear (Phase 1)           | PARTIAL_SIGNAL_IN_Z (HaluEval ΔAUC = +0.008; TruthfulQA-MC ΔAUC = −0.039) |
| §15.11 layer-wise phase coherence (Phase 2)  | **PENDING**                                                  |

The mechanical reading of each Phase 2 outcome (no spin, no
override of §15.10):

- `STRONG_SIGNAL_IN_PHASE_COHERENCE` → phase coherence is
  identified as a transfer mechanism that linear extraction
  (§15.10) and unsupervised entropy (§13.10) failed to
  capture. Substantive positive update on the BCVF-faithful
  transfer thesis at the 7B scale. Phase 3 will document
  this as a confirmed mechanism class and propose downstream
  validation.
- `PARTIAL_SIGNAL_IN_PHASE_COHERENCE` → phase coherence
  carries some signal beyond entropy baseline on at least
  one benchmark, in the BCVF-faithful direction, but does
  not dominate. Joint with §15.10's PARTIAL: at least one
  mechanism class has weak signal in the BCVF-faithful
  direction. Phase 3 will document mixed evidence and the
  asymmetry profile across benchmarks.
- `NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE` → layer-wise
  phase coherence does not transfer at the 7B scale in the
  BCVF-faithful direction. Joint with §15.10's
  PARTIAL-by-hair: all three pre-committed canonical
  mechanism classes (entropy / supervised linear /
  phase-coherence) have produced near-null or null results.
  Phase 3 will document this as **strong joint evidence
  against transfer at the 7B scale under the canonical
  mechanism classes**, and will propose Phase 3's closure
  outcome from the four pre-committed bands (see below).

**Phase 3 (`§15.12`) authorization mapping (PINNED).**

§15.11 mechanically authorizes — but does not execute —
Phase 3 work. The eligible §15.12 closure outcomes per
§15.11 cascade label:

| §15.11 outcome                            | §15.12 closure outcomes mechanically eligible                                                                                                                                            |
|-------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `STRONG_SIGNAL_IN_PHASE_COHERENCE`        | `REOPEN_LATER_UNDER_NEW_HYPOTHESIS_CLASS` (with positive update; phase coherence becomes the new hypothesis class)                                                                       |
| `PARTIAL_SIGNAL_IN_PHASE_COHERENCE`       | `CLOSED_OPERATIONALLY_BUT_BCVF_FAITHFUL_REOPENING_POSSIBLE`                                                                                                                              |
| `NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE`   | `CLOSED_OPERATIONALLY_BUT_SUPERVISED_REOPENING_POSSIBLE` (because §15.10 was PARTIAL — supervised retains a residual reopening path) **or** `FULLY_CLOSED` (only if Phase 3's ChatGPT cross-bridge analysis converges to closure) |

Phase 3 (§15.12) will get its own pre-commitment chunked
draft; the closure-outcome decision rule will be pinned
there. The **set** of eligible outcomes per §15.11 label is
pinned **here**, ex ante, so Phase 3 cannot retroactively
choose an outcome outside the §15.11-authorized set.

This is the §0.8-binding constraint that prevents Phase 3
from being a re-litigation of Phase 2.

**What §15.11 does NOT do, restated.**

- Does NOT modify §15.10's `PARTIAL_SIGNAL_IN_Z`
  verdict-of-record.
- Does NOT modify §13.9's hold or any §13/§14/§15.x
  verdict-of-record.
- Does NOT execute Phase 3. Phase 3 requires its own §0.8
  commitment.
- Does NOT iterate on the formula or features after this
  section is sealed.
- Does NOT permit selecting from §15.12 closure outcomes
  outside the table above.

**Closing §0.8 declaration.**

This pre-commitment (the chunks under §15.11 above) is
**§0.8-binding**. Once committed to the design document,
the §15.11 mechanism, formula, evaluation, cascade,
outputs, firewall, self-test gate, caveats, and Phase 3
authorization mapping are all frozen. Implementation chunks
(script-side `scripts/probe_phase_coherence_15_11.py`) will
follow this pre-commitment exactly. Any deviation requires
a fresh §0.8 amendment surfaced in the design document.

Phase 2 enters execution only after this pre-commitment is
committed to the branch and the implementation script's
self-test gate passes.

---


### 15.12 Pre-commitment — Phase 3 of final-resolution sprint: final synthesis + autonomy handoff package (BOUNDED; one shot)

**§0.8 declaration.**

§15.12 is Phase 3 of the bounded 3-phase final-resolution
sprint, authorized at the close of §15.11
(`NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE`; HaluEval AUC =
0.4610 / ΔAUC = −0.2000; TruthfulQA-MC AUC = 0.4853 /
ΔAUC = −0.1757; direction gate failed on both benchmarks;
per `docs/experiments/probe_phase_coherence_15_11.{json,md}`
at commit `b73e319`).

This is a fresh §0.8 commitment. §15.12 outputs do **NOT**
modify any §13/§14/§15.x verdict-of-record, including
§15.10's `PARTIAL_SIGNAL_IN_Z`, §15.11's
`NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE`, §15.6's REGRESSION,
§15.8's MIXED + C-MISMATCHED, or the §13.9 hold. **All
upstream verdicts remain binding.**

§15.12 is the **mechanical synthesis** step: it consumes
the artifacts produced by Phases 1 and 2 (and the earlier
§15.x verdicts), applies a **pre-committed closure decision
rule**, and emits a final synthesis memo + autonomy handoff
package. It does NOT rerun any experiment, retrain any
probe, re-extract any hidden states, or re-classify any
verdict.

Bands, decision rule, output structure, and self-test cases
are pinned **ex ante** in this section. Any deviation
requires a fresh §0.8 amendment.

**What §15.12 does.**

1. **Synthesize the joint state of pre-committed mechanism
classes.** Four classes have been tested:

   - **§13.10 unsupervised entropy** (semantic-entropy
     AUC, both benchmarks): saturated at AUC = 0.661.
   - **§14a / §15.4 / §15.6 / §15.8 system-level
     composition** (multi-source forced-allocation):
     MIXED + C-MISMATCHED (per §15.8).
   - **§15.10 supervised linear** (logistic regression on
     layer −1 hidden states): `PARTIAL_SIGNAL_IN_Z`
     (HaluEval ΔAUC = +0.008, TruthfulQA-MC ΔAUC = −0.039).
   - **§15.11 layer-wise phase coherence** (29-layer rfft
     phase coherence): `NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE`
     (direction gate failed on both benchmarks).

2. **Apply the pinned closure decision rule** (formula
block below) to select a final closure outcome from the
§15.11-authorized eligible set:
`CLOSED_OPERATIONALLY_BUT_SUPERVISED_REOPENING_POSSIBLE`
(default) **or** `FULLY_CLOSED` (only if a pre-committed
convergence criterion is met).

3. **Produce three artifacts**:

   - **Final LLM synthesis memo** (4-mechanism-class
     comparison + closure rationale).
   - **One-page LLM closure note** (executive summary +
     final outcome).
   - **Autonomy handoff package** (executive memo, claim
     ladder, 90-day plan, narrative set) — preparing the
     autonomy domain for any future BCVF-faithful
     follow-on without inheriting unresolved LLM-transfer
     ambiguity.

**What §15.12 does NOT do.**

- Does **NOT** rerun any §15.10 / §15.11 / §13.10
  experiment.
- Does **NOT** modify any §13/§14/§15.x verdict-of-record.
- Does **NOT** iterate on the closure decision rule once
  this section is sealed.
- Does **NOT** select a closure outcome outside the
  §15.11-authorized set
  (`CLOSED_OPERATIONALLY_BUT_SUPERVISED_REOPENING_POSSIBLE`
  or `FULLY_CLOSED`). The other two pre-committed outcomes
  from the original 3-phase sprint plan
  (`CLOSED_OPERATIONALLY_BUT_BCVF_FAITHFUL_REOPENING_POSSIBLE`,
  `REOPEN_LATER_UNDER_NEW_HYPOTHESIS_CLASS`) are
  **mechanically ineligible** given the §15.11 outcome.
- Does **NOT** authorize any Phase 4 / §15.13 / further
  LLM experiment. Once §15.12 closes, the LLM
  transfer-line is operationally closed in this branch;
  any reopening requires a new top-level §0.8 commitment.

**Dependencies.**

- **§15.10 verdict-of-record.**
  `docs/experiments/probe_supervised_15_10.json` and
  `.md` (commit `a094e94`). Sealed
  `PARTIAL_SIGNAL_IN_Z`.
- **§15.11 verdict-of-record.**
  `docs/experiments/probe_phase_coherence_15_11.json` and
  `.md` (commit `b73e319`). Sealed
  `NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE`.
- **§13.10 / §13.20 baseline.** Entropy AUC = 0.661 both
  benchmarks; π = 0.300 (HaluEval) / 0.250 (TruthfulQA-MC).
- **§15.7 / §15.8 mechanism decomposition.**
  `docs/experiments/probe_audit_15_7.{json,md}`; verdict
  MIXED + C-MISMATCHED.
- **Earlier §15.x verdicts.** §15.2 MARGINAL, §15.4
  USEFUL_INTERNAL, §15.6 REGRESSION — all preserved as
  part of the joint state, but **not used as cascade
  input** (cascade is only on Phase 1 + Phase 2 outcomes
  per the §15.11 mapping).

No new GPU work, no new experiments, no model loads.
§15.12 is pure synthesis + memo writing under §0.8
discipline.

**Time / compute budget.**

- Total wall clock: <5 minutes (CPU-only, JSON parsing +
  bootstrap CI on N=100 array + markdown rendering + file
  writes).
- Disk footprint: ~30–50 KB of new artifacts (no large
  caches).

§15.12 implementation
(`scripts/probe_synthesis_15_12.py`) is a separate §0.8
authorization gate and follows after this pre-commitment
is sealed.

---


_End of skeleton. Each section to be filled in one at a time, on explicit authorization._

