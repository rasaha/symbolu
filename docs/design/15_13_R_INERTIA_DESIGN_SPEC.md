# §15.13 R_inertia Probe — Implementation Design Specification

## Status

- **Spec status:** sealed; ready for implementation in a fresh session.
- **§0.8 binding:** the pinned decisions in this document are §0.8-binding
  per the discipline established in §15.10 / §15.11 / §15.12. Any deviation
  during implementation requires a fresh §0.8 amendment (either to this spec
  or to a parallel design-doc entry).
- **Per the §15.12 ledger:** §15.13 is a **fresh top-level §0.X commitment**,
  not an amendment to any prior section. It does NOT modify any §13/§14/§15.x
  verdict-of-record (including §15.10 PARTIAL_SIGNAL_IN_Z, §15.11
  NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE, §15.12 closure outcome, §13.9 hold,
  or §6.1 N=21 autonomy result). All upstream verdicts remain binding.

## Research question

> Does the LM's residual alignment toward a prior answer (vs. the new question)
> predict whether it will fail to pivot to the new question?

This is a **multi-turn / state-dynamics** hypothesis class — distinct from the
four single-turn canonical mechanism classes tested in §15.10 / §15.11. The
§15.12 closure ledger explicitly listed multi-turn dynamics as
**untested-not-refuted**, sitting in the "open lines" column. §15.13 tests one
specific instantiation of that class.

## Hypothesis (H3 from the unified multi-turn model)

The LM's residual alignment toward a prior answer trajectory R_A — relative to
the new question Q_B — predicts whether the model will fail to pivot to Q_B.
Operationalized as a single scalar:

> **R_inertia = cos(s_t, r_A) − cos(s_t, q_B)**

with the BCVF-faithful direction convention:

> **Lower R_inertia predicts CORRECT response to Q_B.**
> (i.e., AUC(−R_inertia, y) is the test statistic.)

Higher R_inertia → state still aligned with the prior answer trajectory →
predicted to produce a "stuck" / drifted response on Q_B.

## Mechanism class

**Continuation inertia (H3 only).** Tested in isolation. No combination with
H1 (state coherence) or H2 (intent competition); those remain in the
open-but-untested column for future top-level §0.X work.

This is NOT a new variant of:
- §13.10 unsupervised entropy (single-turn token-level)
- §15.10 supervised linear probe (single-turn last-layer)
- §15.11 layer-wise phase coherence (single-turn cross-layer)
- §14a/§15.4/§15.6/§15.8 system-level composition (multi-source allocation)

It IS a new mechanism class entirely — **temporal alignment between successive
conversational turns**.

## Connection to prior phases

| Phase | Mechanism | Outcome | Domain |
|---|---|---|---|
| §13.10 | Unsupervised entropy | AUC = 0.661 (saturated) | Single-turn |
| §15.4 / §15.6 / §15.8 | System-level composition | MIXED + C-MISMATCHED | Single-turn |
| §15.10 (Phase 1) | Supervised linear | PARTIAL_SIGNAL_IN_Z | Single-turn |
| §15.11 (Phase 2) | Layer-wise phase coherence | NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE | Single-turn |
| §15.12 (Phase 3) | Synthesis + closure (sealed) | (CLOSED_OPERATIONALLY... or FULLY_CLOSED, pending impl) | N/A |
| **§15.13** | **Continuation inertia** | **PENDING** | **Multi-turn** |

The §15.12 closure stands for the four single-turn canonical mechanism classes
at the Qwen-7B scale. §15.13 tests a fundamentally different domain.

If §15.13 lands NO_MATERIAL: the joint state is unchanged from §15.12, plus
one more "tested and null" mechanism class added to the count.

If §15.13 lands PARTIAL or STRONG: this is genuinely new evidence. The post-
§15.13 ledger updates to record continuation inertia as an authorized
mechanism class. §15.12's closure for the four canonical single-turn classes
remains binding (no retroactive reopening).

In either case, §13.9 hold and §6.1 N=21 autonomy result are preserved.

## What §15.13 does NOT do

- Does **NOT** re-classify any §13/§14/§15.x verdict-of-record.
- Does **NOT** test H1 (state coherence) or H2 (intent competition).
- Does **NOT** combine signals (no R_total).
- Does **NOT** explore alternative pairings, layer subsets, pooling schemes,
  or aggregations once this spec is sealed.
- Does **NOT** sign-flip on direction-gate failure.
- Does **NOT** authorize Phase 5+ or further §15.x work.

---

## Pinned mechanism

### Core formula

$$R_{\text{inertia}} = \cos(s_t, r_A) - \cos(s_t, q_B)$$

Where:
- `s_t` ∈ R^3584 = LM's hidden state at the moment it's about to generate a
  response to Q_B (last-token, layer −1, taken from the full-context forward
  pass).
- `r_A` ∈ R^3584 = pooled hidden state over the actual generated assistant
  tokens of R_A (mean across token positions, layer −1).
- `q_B` ∈ R^3584 = LM's hidden state for Q_B in isolation (last-token,
  layer −1, from a separate forward pass with chat template but no Q_A
  history).

All three live in Qwen-7B's 3584-dim residual stream; cosine similarities
are geometrically meaningful.

### The five pinned choice points

These were the unresolved degrees of freedom in the initial proposal. Each
has exactly one answer that cannot drift during implementation.

**Choice 1: Source of all three representations** → Qwen hidden states only.
No external sentence encoder. No projection between geometries. The
mechanism under test is the *LM's* internal state dynamics; an external
encoder would weaken the claim. (Discussed alternative: external sentence
encoder for geometric parity. Rejected: weakens the BCVF-faithful
interpretation.)

**Choice 2: Standalone Q_B representation** → forward pass with the standard
chat template `[SYS][USER]Q_B[ASSISTANT]_`, no Q_A history. The "what would
the model be doing if Q_B were a fresh standalone question?" anchor.
(Discussed alternative: raw `Q_B` text without chat template. Rejected:
diverges from how the model is actually prompted.)

**Choice 3: Temporal extraction point for s_t** → last-token, layer −1, at
the position of the second `[ASSISTANT]` tag (just before the model decodes
the Q_B response). The "ready-to-answer" state.
(Discussed alternatives: pooled over Q_B tokens; first generated response
token. Rejected: less direct, more hyperparameter surface.)

**Choice 4: Layer index** → layer −1 (final layer) only. No layer subsets,
no multi-layer aggregation. Mirrors §15.10. (Discussed alternative: all 29
layers, multi-layer aggregation. Rejected: opens hyperparameter trap that
bit §15.11.)

**Choice 5: r_A pooling scope** → mean over the actual decoded R_A token
positions (the assistant's generated answer span), layer −1. NOT a single
terminal token after R_A.

> $$r_A = \frac{1}{|T_A|}\sum_{t \in T_A} h_t^{(-1)}$$

where `T_A` is the set of token positions corresponding to R_A in the
generation pass. `s_t` and `q_B` remain single-token anchors; the asymmetry
is intentional (r_A is the *trajectory*; s_t and q_B are *moments*).
(Discussed alternative: single-token state at end of R_A. Rejected: collapses
the answer trajectory into one summary point; user-flagged as a real
methodological gap before sealing.)

### R_sim comparator baseline

$$R_{\text{sim}} = \cos(q_A, q_B)$$

Where:
- `q_A` ∈ R^3584 = LM's hidden state at end of `[SYS][USER]Q_A[ASSISTANT]_`,
  pre-decode (already computed for free in Pass 1; see Chunk 3).
- `q_B` ∈ R^3584 = same as in R_inertia (already computed in Pass 3).

R_sim measures pure topical similarity between the two questions in the LM's
geometry. It controls for the confound: if R_inertia just tracks "how similar
are the topics," it provides no evidence about continuation inertia
specifically.

**The cascade requires R_inertia to beat BOTH chance (0.5) AND R_sim's AUC by
the cascade margin** to clear STRONG / PARTIAL bands. This is the strict-
comparator requirement, not just chance-vs-zero.

### Direction convention (PINNED, BCVF-faithful)

> Lower R_inertia predicts CORRECT (i.e., the model has pivoted to Q_B and
> answers it correctly).

Test statistic: `AUC(−R_inertia, y)`. Higher = better signal in the
hypothesized direction.

**No sign-flip rescue.** If `AUC(−R_inertia, y) < 0.5`, the BCVF-faithful
direction failed; the cascade lands in NO_MATERIAL automatically (Step 1
direction gate). The empirical signal in the inverted direction (i.e.,
*higher* R_inertia predicting correct) is NOT considered. This mirrors
§15.11's direction-gate enforcement; the pre-committed hypothesis was the
specific BCVF-faithful direction, and failing it is a hypothesis failure,
not a sign-flip opportunity.

### What is NOT pinned in v1 (and stays out)

- No combination with other H-class signals (no R_total).
- No bootstrap CI on the AUCs (mirrors §15.10/§15.11; v1 reports point
  estimates against pinned bands).
- No alternative pairing rules beyond `(i, (i + 50) mod 100)`.
- No second benchmark in v1 (HaluEval is a v2 follow-up only if v1 shows
  signal).
- No probe training (pure feature, no fitting).

### Why these specific pinnings (§0.8-disclosed rationale)

Every pinning is a deliberate choice to minimize hyperparameter surface area.
§15.11 was bitten by static phase-coherence having layer-aggregation,
binning, and direction-convention degrees of freedom that compounded into a
brittle direction-gate failure. §15.13 was designed to hold all five major
choice points fixed before any data is inspected. If the pinned configuration
fails to show signal, that is the verdict; tweaking the configuration after
seeing data is forbidden.

---

## Stimulus construction

### Benchmark

**Single benchmark: TruthfulQA-MC** (specifically `truthful_qa /
multiple_choice / validation` from HuggingFace, matching §13.10's source).

Choice rationale: §15.10 showed HaluEval has *some* residual signal at the
supervised-linear level. If R_inertia were tested on HaluEval, a positive
result could confound with the §15.10 effect. TruthfulQA-MC has been the
cleaner null benchmark across §15.x. Signal there is harder to confound with
prior phases and is a stronger first test.

A v2 follow-up on HaluEval is authorized only if v1 shows signal.

### Pairing rule (PINNED, deterministic)

For `i ∈ {0, 1, …, 99}`:

> **(Q_A_idx, Q_B_idx) = (i, (i + 50) mod 100)**

Properties:
- 100 unique pairs.
- Each question appears exactly once as Q_A and once as Q_B.
- The +50 offset randomizes topical adjacency without requiring a random
  seed (TruthfulQA-MC's validation split is not topic-sorted, so this
  approximates a topical shuffle).
- Same-family pairing (both from TruthfulQA-MC) — eliminates benchmark-
  family asymmetry as a confound.

Discussed alternatives:
- `(i, (i+1) mod 100)`: keeps adjacent questions paired; topical adjacency
  too strong.
- Random shuffle with pinned seed: deterministic but introduces seed-
  dependent variance.
- `(i, (N-1)-i)` reverse pairing: only 50 unique pairs.

The +50 offset is the simplest scheme that satisfies all three properties.

### Inputs

- `docs/experiments/probe_semantic_entropy.json` — §13.10 TruthfulQA-MC dump
  (commit pinned by §15.x history); first 100 records used for q_idx
  alignment and label cross-check.
- HuggingFace dataset `truthful_qa / multiple_choice / validation` —
  question text and gold answers (`mc1_targets`).
- Qwen/Qwen2.5-7B-Instruct — model under test.

### Question text source policy

Per the §15.10 / §15.11 pattern: prefer the §13.10 dump's `question` field
if present on every record; fall back to HuggingFace dataset by `q_idx`
alignment if not. The dump's `correct_choice` field provides the gold
answer; if missing, fall back to `ds[q_idx]["mc1_targets"]["choices"][i]`
where `i` is the index where `labels[i] == 1`.

---

## Per-stimulus pipeline (3 forward passes)

For each stimulus `(q_a_idx, q_b_idx)`:

### Pass 1 — generate R_A and extract q_A, r_A representations

Input: chat-template-formatted prompt
```
[SYS] (default Qwen system prompt or empty)
[USER] {q_a_text}
[ASSISTANT] _
```

Forward pass + greedy decode for `MAX_NEW_TOKENS = 64` tokens.

Extract:
- `q_a_repr` ∈ R^3584 = last-token hidden state at the position immediately
  before generation begins (i.e., the final tokenized [ASSISTANT] tag's last
  token), layer −1.
- `r_a_text` = decoded assistant tokens (stop early on EOS / chat-template
  end token).
- `r_a_repr` ∈ R^3584 = mean over the hidden states at the *generated*
  assistant token positions (length-`|T_A|` set), layer −1.

Note: `r_a_repr` is computed during decoding by accumulating the hidden
state at each generated position; no second forward pass is required.

### Pass 2 — generate Q_B response, extract s_t, score y

Input: chat-template-formatted multi-turn prompt
```
[SYS] (same as Pass 1)
[USER] {q_a_text}
[ASSISTANT] {r_a_text}
[USER] {q_b_text}
[ASSISTANT] _
```

Forward pass + greedy decode for `MAX_NEW_TOKENS = 64` tokens.

Extract:
- `s_t` ∈ R^3584 = last-token hidden state at the position immediately
  before Q_B response generation begins (second [ASSISTANT] tag's last
  token), layer −1.
- `q_b_response_text` = decoded assistant tokens for the Q_B response.

Label scoring (`y` ∈ {0, 1}):
- Reuse §13.10-style NLI scoring (DeBERTa-v3-base-mnli-fever-anli).
- Score: does `q_b_response_text` entail `q_b_correct_choice`?
- `y = 1` if entailment, `y = 0` otherwise.
- This matches the `greedy_matches_correct` semantics of §13.10's
  `correctness` field.

### Pass 3 — extract q_B standalone representation

Input: chat-template-formatted prompt
```
[SYS] (same as Pass 1)
[USER] {q_b_text}
[ASSISTANT] _
```

No decoding. Single forward pass.

Extract:
- `q_b_repr` ∈ R^3584 = last-token hidden state at the position immediately
  before generation would begin, layer −1.

---

## Computed per-stimulus features

```
cos_st_ra = cos(s_t, r_a_repr)        # alignment of state with prior answer
cos_st_qb = cos(s_t, q_b_repr)        # alignment of state with new question
cos_qa_qb = cos(q_a_repr, q_b_repr)   # baseline question-similarity

R_inertia = cos_st_ra - cos_st_qb     # primary signal
R_sim     = cos_qa_qb                 # comparator baseline
y         = q_b_correct ∈ {0, 1}      # label
```

All cosines computed in fp64 from fp32 cache values; no clipping required
since all inputs are real-valued LM hidden states (no FFT).

### Aggregate-level computations (after all stimuli)

```
auc_inertia = roc_auc_score(y, -R_inertia_array)
auc_sim     = roc_auc_score(y, -R_sim_array)

dauc_inertia_vs_chance = auc_inertia - 0.5
dauc_inertia_vs_sim    = auc_inertia - auc_sim

direction_held = (auc_inertia >= 0.5)
```

The negation in `roc_auc_score(y, -R_*)` reflects the direction convention:
*lower* R_* predicts correct, so the score for the AUC computation must be
flipped sign. After negation: higher score → predicts correct.

### Selective-prediction (disclosure only)

For the pinned alphas `α ∈ {0.35, 0.50, 0.75}`, compute κ@α using
`-R_inertia` as the abstention score and `y` as the label. Eligibility:
`n_admitted >= 10` AND conditional accuracy `>= α`. Same construction as
§15.10 / §15.11. **These operating points are reported in the JSON / MD
output for transparency but do NOT enter the cascade decision.**

---

## Cascade structure

### Pinned thresholds (numerically identical to §15.10 / §15.11)

```
STRONG_AUC_THRESHOLD          = 0.75   # inclusive
STRONG_DELTA_AUC_THRESHOLD    = 0.05   # inclusive (vs both chance and R_sim)
PARTIAL_AUC_THRESHOLD         = 0.66   # inclusive
DIRECTION_GATE_THRESHOLD      = 0.5    # strict (auc_inertia < 0.5 fails)
CHANCE_BASELINE_AUC           = 0.5
```

The threshold values match §15.10 / §15.11 for cross-phase comparability.

### Cascade decision (mechanical, in order)

Inputs: `auc_inertia`, `auc_sim`. Both are `AUC(-R_*, y)` form (higher =
better signal in the BCVF-faithful direction).

**Step 1 — Direction gate (PINNED).**

> If `auc_inertia < 0.5` → label = `NO_MATERIAL_SIGNAL_IN_INERTIA`,
> rationale = "wrong-direction failure: BCVF-faithful direction (lower
> R_inertia predicts correct) did not hold (auc_inertia = X < 0.5)".
> Skip remaining steps.

This is the §0.8 enforcement of the pinned BCVF-faithful direction. Failing
it on the only benchmark is a hypothesis failure, not a sign-flip
opportunity. Mirrors §15.11.

**Step 2 — STRONG check.**

> If
> - `auc_inertia ≥ 0.75` AND
> - `(auc_inertia − 0.5) ≥ 0.05` AND
> - `(auc_inertia − auc_sim) ≥ 0.05`
>
> → label = `STRONG_SIGNAL_IN_INERTIA`.

The third condition is the strict-comparator requirement: R_inertia must
beat the topic-similarity baseline by the cascade margin.

**Step 3 — PARTIAL check.**

> If not STRONG, AND
> - `auc_inertia ≥ 0.66` AND
> - `(auc_inertia − 0.5) > 0` AND
> - `(auc_inertia − auc_sim) > 0`
>
> → label = `PARTIAL_SIGNAL_IN_INERTIA`.

The second condition is automatically satisfied by `auc_inertia ≥ 0.66 >
0.5`, but is stated explicitly for symmetry with §15.10 / §15.11.

**Step 4 — Default.**

> Otherwise → label = `NO_MATERIAL_SIGNAL_IN_INERTIA`.

### What the cascade does NOT consider

- The κ@α selective-prediction operating points (disclosure only).
- Any per-stimulus diagnostic (R_inertia distribution, individual cosine
  values, etc.).
- §15.10's HaluEval-QA / TruthfulQA-MC AUCs or §15.11's phase-coherence
  AUCs (different mechanism classes; not comparable input).
- Whether `R_sim` itself clears chance — only the *difference*
  `(auc_inertia − auc_sim)` matters.

### Pinned self-test boundary cases (12 cases)

Each entry: `(auc_inertia, auc_sim, expected_label)`. The implementation
script must pass all 12 at the self-test gate before any data inspection.

| #   | auc_inertia | auc_sim | rationale                                              | expected                         |
|-----|-------------|---------|--------------------------------------------------------|----------------------------------|
|  1  | 0.80        | 0.65    | STRONG clean (clears all 3 conditions)                 | STRONG_SIGNAL_IN_INERTIA         |
|  2  | 0.75        | 0.70    | STRONG boundary at AUC=0.75 + ΔAUC sim=0.05 inclusive  | STRONG_SIGNAL_IN_INERTIA         |
|  3  | 0.78        | 0.20    | STRONG well above sim                                  | STRONG_SIGNAL_IN_INERTIA         |
|  4  | 0.74        | 0.65    | PARTIAL via AUC just below 0.75; ΔAUC sim=0.09>0       | PARTIAL_SIGNAL_IN_INERTIA        |
|  5  | 0.78        | 0.74    | PARTIAL via ΔAUC sim=0.04<0.05 but >0                  | PARTIAL_SIGNAL_IN_INERTIA        |
|  6  | 0.66        | 0.65    | PARTIAL boundary at AUC=0.66 inclusive; ΔAUC sim=0.01  | PARTIAL_SIGNAL_IN_INERTIA        |
|  7  | 0.65        | 0.50    | NO_MATERIAL: AUC < 0.66                                | NO_MATERIAL_SIGNAL_IN_INERTIA    |
|  8  | 0.70        | 0.70    | NO_MATERIAL: ΔAUC sim = 0 (not > 0)                    | NO_MATERIAL_SIGNAL_IN_INERTIA    |
|  9  | 0.70        | 0.72    | NO_MATERIAL: ΔAUC sim < 0 (R_inertia worse than sim)   | NO_MATERIAL_SIGNAL_IN_INERTIA    |
| 10  | 0.50        | 0.30    | NO_MATERIAL: direction gate inclusive at 0.5; AUC<0.66 | NO_MATERIAL_SIGNAL_IN_INERTIA    |
| 11  | 0.49        | 0.65    | NO_MATERIAL: direction gate strict (auc_inertia<0.5)   | NO_MATERIAL_SIGNAL_IN_INERTIA    |
| 12  | 0.40        | 0.40    | NO_MATERIAL: direction gate (both wrong-direction)     | NO_MATERIAL_SIGNAL_IN_INERTIA    |

Coverage rationale:
- Cases 1–3: STRONG band entries (clean, two boundary inclusive at 0.75 +
  0.05, well-separated from sim).
- Cases 4–6: PARTIAL band entries (AUC just-below-STRONG; ΔAUC sim
  just-below-STRONG; AUC=0.66 boundary inclusive).
- Cases 7–9: NO_MATERIAL via cascade-condition failure (AUC<0.66; ΔAUC sim
  =0 strictly; ΔAUC sim<0).
- Cases 10–12: NO_MATERIAL via direction-gate failure (inclusive at 0.5;
  strict below 0.5; both wrong-direction).

---

## Output schema

### `docs/experiments/probe_inertia_15_13.json` (`schema_version = "15.13"`)

Top-level keys (alphabetical for `sort_keys=True` parity with §15.10 /
§15.11 / §15.12):

```
{
  "benchmark": "truthfulqa_mc",
  "cascade_thresholds": {
    "strong_auc": 0.75,
    "strong_delta_auc": 0.05,
    "partial_auc": 0.66,
    "direction_gate_threshold": 0.5,
    "chance_baseline_auc": 0.5
  },
  "cascade_verdict": {
    "label": "<STRONG|PARTIAL|NO_MATERIAL>_SIGNAL_IN_INERTIA",
    "auc_inertia": <float>,
    "auc_sim": <float>,
    "dauc_vs_chance": <float>,
    "dauc_vs_sim": <float>,
    "direction_held": <bool>,
    "rationale": "<formatted prose>"
  },
  "cross_phase_disclosure": {
    "phase_1_§15_10_verdict": "PARTIAL_SIGNAL_IN_Z",
    "phase_2_§15_11_verdict": "NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE",
    "phase_3_§15_12_status": "sealed (closure outcome pending implementation)",
    "this_phase_modifies": "none"
  },
  "extraction_config": {
    "layer_idx": -1,
    "hidden_dim": 3584,
    "max_new_tokens": 64,
    "decode_temperature": 0.0,
    "r_a_pooling": "mean_over_decoded_assistant_tokens",
    "s_t_extraction": "last_token_pre_decode_at_second_assistant_tag",
    "q_b_extraction": "last_token_pre_decode_standalone_with_chat_template"
  },
  "n_stimuli": 100,
  "pairing_rule": "(Q_A_idx, Q_B_idx) = (i, (i + 50) mod 100) for i in 0..99",
  "phase_4_eligible_outcomes": [
    "STRONG_SIGNAL_IN_INERTIA",
    "PARTIAL_SIGNAL_IN_INERTIA",
    "NO_MATERIAL_SIGNAL_IN_INERTIA"
  ],
  "probe_result": {
    "n_stimuli": 100,
    "n_correct": <int>,
    "n_wrong": <int>,
    "auc_inertia": <float>,
    "auc_sim": <float>,
    "dauc_inertia_vs_chance": <float>,
    "dauc_inertia_vs_sim": <float>,
    "direction_held": <bool>,
    "r_inertia_per_stimulus": [<100 floats>],
    "r_sim_per_stimulus": [<100 floats>],
    "y_per_stimulus": [<100 bools>],
    "selective_prediction_operating_points": [
      {"alpha": 0.35, "kappa_at_alpha": <float>, "tau_star": <float>,
       "coverage_at_tau_star": <float>,
       "conditional_accuracy_at_tau_star": <float>,
       "n_admitted_at_tau_star": <int>, "eligible": <bool>},
      {"alpha": 0.50, ...},
      {"alpha": 0.75, ...}
    ],
    "kappa_at_alpha_primary": <float>,
    "tau_star_at_alpha_primary": <float>,
    "alpha_primary": 0.5
  },
  "qwen_model_id": "Qwen/Qwen2.5-7B-Instruct",
  "schema_version": "15.13"
}
```

PINNED. No additional keys; no key removal.

### `docs/experiments/inertia_15_13_extractions.npz` (cache file)

Per-stimulus arrays, allows `--probe-only` re-runs:

```
pair_idx          int64,   shape (100,)
q_a_idx           int64,   shape (100,)
q_b_idx           int64,   shape (100,)
q_a_repr          float32, shape (100, 3584)
r_a_repr          float32, shape (100, 3584)
s_t               float32, shape (100, 3584)
q_b_repr          float32, shape (100, 3584)
y                 bool,    shape (100,)
r_a_text          object,  shape (100,)   # variable-length strings
q_b_response_text object,  shape (100,)   # variable-length strings
```

Approximate size: 4 × 100 × 3584 × 4 bytes ≈ 5.6 MB + text overhead.

### `docs/experiments/probe_inertia_15_13.md`

8-section markdown report (mirrors §15.11 structure):

1. Header + schema/model/extraction config one-liner.
2. Cascade verdict (label, rationale, AUC table with chance + sim baselines).
3. Probe details (n, AUC, ΔAUC vs both baselines, direction-held flag,
   F-distribution summary).
4. Selective-prediction operating points table (disclosure only).
5. Pinned configuration block (formula, pairing rule, extraction protocol,
   cascade thresholds, direction convention).
6. Caveats (§0.8-disclosed; carries forward §15.10/§15.11 caveats by
   §-reference; §15.13-specific caveats listed inline).
7. Cross-phase comparison (Phase 1 / Phase 2 / Phase 3 / Phase 4 status
   table, disclosure only — does not modify any phase).
8. Audit-trail integrity (§0.8-binding; §13/§14/§15.x verdicts preserved;
   firewall-scanned).

---

## Class-3 firewall patterns (44 total)

The firewall scans rendered markdown for forbidden override-language before
write. Each pattern is matched case-insensitively for non-§ patterns and
case-sensitively / literal for §-anchored patterns (preserves precise §-
numbering). Detection → exit code 4 (`INTERPRETATION_VIOLATION`) without
writing.

### Inherited from §15.10 / §15.7 (16 patterns)

```
"verdict was wrong"
"verdict is wrong"
"should be re-classified"
"should be reclassified"
"is invalid because"
"§13.9 should be relaxed"
"§13.9 hold should be"
"§13.9 hold can be"
"§15.8 authorized"
"§15.8 is authorized"
"§6.1 is strengthened"
"autonomy result is strengthened"
"actually STRONG"
"should be classified as STRONG"
"actually PARTIAL despite"
"STRONG despite the cascade"
```

### Inherited from §15.11 (10 patterns)

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

### Inherited from §15.12 (10 patterns)

```
"§15.10 PARTIAL was wrong"
"§15.10 PARTIAL should be relaxed"
"§15.11 NO_MATERIAL should be relaxed"
"§15.11 direction gate should be relaxed"
"the bootstrap test was inappropriate"
"the bootstrap test should be replaced"
"§15.12 closure should be reopened"
"§15.12 should authorize REOPEN"
"§6.1 N=21 sign test was wrong"
"the autonomy result is invalidated"
```

### §15.13-specific (8 patterns)

```
"actually STRONG_SIGNAL_IN_INERTIA despite"
"should be STRONG_SIGNAL_IN_INERTIA"
"actually PARTIAL_SIGNAL_IN_INERTIA despite"
"should be classified as PARTIAL_SIGNAL_IN_INERTIA"
"the R_sim comparator should be ignored"
"the same-family pairing was a mistake"
"the pooling over R_A tokens was wrong"
"the chance baseline alone is sufficient"
```

**Total: 44 patterns.** PINNED. The implementation script must include all
44; the self-test gate must verify each is flagged on a positive sample
and clean §15.13-style text produces zero false positives.

---

## Implementation chunk plan

The implementation should follow the established §15.10 / §15.11 chunked
pattern: each chunk a separate commit, each with its own verification step.

### Recommended file path

```
scripts/probe_inertia_15_13.py
```

### Chunked plan

| Chunk | Content | Approximate size |
|-------|---------|------------------|
| **I-1** | Module docstring (embedded §0.8 declaration), pinned constants block (matching this spec exactly), 5 dataclasses (`StimulusPair`, `StimulusExtraction`, `StimulusFeatures`, `InertiaProbeResult`, `InertiaCascadeVerdict`, `InertiaAuditOutputs`), 12 self-test cascade boundary cases. | ~350 lines |
| **I-2** | `SchemaMismatchError`, `_validate_s13_10_dump` (mirrors §15.10/§15.11 with optional `question` field + duplicate-q_idx check), `_load_questions_and_gold_from_hf_dataset`, `load_truthfulqa_labels`, `construct_stimulus_pairs` (applies pairing rule), lazy torch+transformers import, `extract_stimulus_three_passes` (Pass 1 + Pass 2 + Pass 3), `save/load_extractions_cache`. | ~400 lines |
| **I-3** | `compute_features_per_stimulus` (R_inertia + R_sim + cosine extracts), `_lazy_import_sklearn`, `_selective_kappa_at_alpha` (matches §15.11), `run_inertia_probe` (full per-run pipeline producing `InertiaProbeResult`), `classify_cascade_inertia` (3-step cascade with direction gate + 2-comparator STRONG/PARTIAL). | ~300 lines |
| **I-4a** | `scan_for_forbidden_patterns` (case-insensitive non-§; literal §-anchored), `enforce_firewall_or_exit` (exits 4 with diagnostic). | ~50 lines |
| **I-4b** | Self-test gate: `_self_test_cascade` (12 cases), `_self_test_cosine_invariants` (cosine identity + symmetry on synthetic data), `_self_test_firewall` (44-pattern coverage + clean negative), `run_self_test` (orchestrates 3 sub-tests, returns 0/3). | ~150 lines |
| **I-4c** | JSON output writer: `_dataclass_to_dict` helpers, `write_json_output` with full schema_version "15.13" payload. | ~100 lines |
| **I-4d** | Markdown rendering: `render_markdown_report` (8 sections per spec), `write_markdown_output` (firewall-scanned before write), `_format_operating_points_table`. | ~250 lines |
| **I-5** | `_run_extraction` (orchestrates all 100 stimuli with shared model load), `_run_probes` (computes features + cascade), `_print_verdict_banner`, `_build_argparser`, `main(argv)` (CLI: `--self-test` / `--extract-only` / `--probe-only` / default). | ~250 lines |

**Total: ~1850 lines** (slightly less than `probe_phase_coherence_15_11.py`).

### Exit codes (PINNED)

```
0  success
2  CLI / argument error (handled by argparse)
3  SELF_TEST_FAILED
4  INTERPRETATION_VIOLATION
5  SCHEMA_MISMATCH (label dump or cache)
6  EXTRACTION_FAILED (torch / transformers stack)
7  PROBE_FAILED (sklearn / NaN in features)
8  NLI_SCORING_FAILED (DeBERTa scoring stack failure)
```

Exit code 8 is §15.13-specific — captures NLI scoring failures distinct
from generic probe failures. The §13.10-style NLI machinery is loaded
during Pass 2 label scoring; if it fails, the diagnostic is unambiguous.

### CLI modes (PINNED)

```
--self-test     : run gate only (12 cascade + cosine invariants + 44-pattern firewall)
--extract-only  : labels + 3-pass extraction per stimulus + write .npz cache
--probe-only    : load cache + compute features + cascade + write outputs
(default)       : self-test → extract (or load cache) → probe → write
--cache-path    : override default cache path
--json-out      : override default JSON output path
--md-out        : override default markdown output path
--force-extract : force re-extraction even if cache exists
```

---

## Cost / timeline

### Sandbox + design work
- Spec writing (this document): done.
- Implementation chunks I-1 through I-5: estimated 8 commits, similar pace
  to §15.11 implementation. ~1 working session including verification
  between chunks.

### Runpod execution
- Per stimulus: 3 forward passes + 2 generations of 64 tokens.
- Total: ~300 forwards + ~12,800 token-generations.
- Wall time on a 24GB GPU: **~15–20 min**, comparable to §15.10's full
  pipeline.
- Cache size: **~5.6 MB** (4 hidden-state arrays + 2 text arrays).
- DeBERTa-v3 NLI scoring: ~1 sec per stimulus × 100 = ~2 min additional.

### Total wall time
~20–25 min runpod time for the full pipeline. Cheaper than §15.11.

### Disk footprint
- Cache: ~5.6 MB.
- JSON output: ~10 KB.
- Markdown output: ~6 KB.
- Total new artifacts on disk: ~5.6 MB committable, plus ~16 KB committable
  documentation.

---

## Risks and mitigations

### Risk 1 — NLI scoring on Q_B response is asymmetric

The §13.10 NLI scoring uses DeBERTa-v3-mnli-fever-anli to check entailment
between the model's answer and gold. For multiple-choice questions, this
treats the gold answer as the premise; the model's free-form response is
the hypothesis. This may behave oddly when the model gives a refusal or
hedged answer.

**Mitigation:** import the §13.10 scoring helper directly from
`scripts/probe_semantic_entropy.py` rather than reimplementing. Same
behavior as the original phase, including its known limitations. This
ensures cross-phase comparability of the `correctness` label.

### Risk 2 — Greedy refusals game the correctness label

Qwen-7B may produce hedged or refusal responses to TruthfulQA-MC questions
("I'm not sure," "I don't know"). NLI scoring on these will produce
non-entailment (label = 0). If the model refuses *more* on Q_B questions
where it's "stuck" on R_A, this is genuine signal — not a flaw.

**Mitigation:** disclose in the markdown caveats. The label is "answered
Q_B correctly under greedy decoding," which is the most direct
operationalization.

### Risk 3 — Pass 2 generates a different R_A than Pass 1

If decoding has any nondeterminism (unlikely with `temperature = 0.0`,
but tokenizer / dtype edge cases exist), the R_A used in Pass 2's full-
context prompt may differ from the R_A used in Pass 1's r_A_repr
computation. This would corrupt the inertia signal.

**Mitigation:** in Pass 2, splice the actual decoded `r_a_text` from Pass
1 into the prompt rather than re-decoding. The `r_a_text` is recorded
once in Pass 1 and injected verbatim into Pass 2's chat-template
construction. This guarantees Pass 1's r_A and Pass 2's R_A are byte-
identical.

### Risk 4 — Same-family pairing might still be too topically similar

The +50 offset randomizes adjacency, but TruthfulQA-MC has many topical
clusters (medicine, law, history). Some pairs may still share topics by
chance. R_inertia might pick up topical-overlap variance as if it were
inertia.

**Mitigation:** R_sim comparator. R_sim measures topic similarity
directly. R_inertia must beat R_sim by the cascade margin to clear
STRONG/PARTIAL — exactly the control the user identified.

### Risk 5 — Direction-gate failure (auc_inertia < 0.5)

§15.11 saw this on both benchmarks (the BCVF-faithful direction failed).
§15.13 may produce the same outcome.

**Mitigation:** acceptable per §0.8. NO_MATERIAL_SIGNAL_IN_INERTIA via
direction gate is a valid verdict. The pinned hypothesis was the
specific BCVF-faithful direction; failing it is a hypothesis failure,
not a sign-flip opportunity. Mirrors §15.11's enforcement.

### Risk 6 — Pass 1 R_A ends before MAX_NEW_TOKENS due to EOS

Greedy decoding may emit EOS or chat-template end token before 64 tokens
are generated. r_A pooling must average only over the actually-generated
tokens (excluding any padding or post-EOS positions).

**Mitigation:** track the actual generated token count `|T_A|` per
stimulus during decoding; pool only over the first `|T_A|` positions.
Document `|T_A|` distribution in the markdown caveats for transparency.

### Risk 7 — N=100 statistical power

AUC standard error at AUC ≈ 0.66 with N=100 is ~0.05. The cascade
thresholds at 0.66 and 0.75 are within sampling noise of N=100
distributions.

**Mitigation:** known limitation; mirrors §15.10/§15.11 power constraint.
v1 reports point estimates against pinned bands. If R_inertia clears
PARTIAL on N=100, an N=200 / N=500 replication would be appropriate as
a v2 follow-up — but v2 requires its own §0.8.

### Risk 8 — DeBERTa NLI cost on the runpod

If the §13.10 NLI machinery isn't already loaded, it adds ~5 GB to memory
footprint plus model-load time.

**Mitigation:** fall back to a simpler exact-match scoring if NLI loading
fails, but only as a fallback — disclose explicitly in the JSON. Default
behavior is NLI scoring identical to §13.10.

---

## Sealed §0.8-binding decisions

The following decisions cannot be modified during implementation without
a fresh §0.8 amendment to this spec:

### Frozen parameters

| Decision | Pinned value |
|---|---|
| SCHEMA_VERSION | "15.13" |
| QWEN_MODEL_ID | "Qwen/Qwen2.5-7B-Instruct" |
| BENCHMARK | "truthfulqa_mc" (single benchmark) |
| PINNED_N | 100 |
| PAIRING_OFFSET | 50 (i.e., (i, (i+50) mod 100)) |
| PROMPT_FORMAT | Qwen chat template via `apply_chat_template` |
| MAX_NEW_TOKENS | 64 |
| DECODE_TEMPERATURE | 0.0 (greedy) |
| LAYER_IDX | -1 (final layer only) |
| HIDDEN_DIM | 3584 |
| R_A_POOLING | mean over decoded assistant token positions |
| s_t extraction | last-token, layer −1, pre-decode at 2nd `[ASSISTANT]` |
| q_B extraction | last-token, layer −1, standalone with chat template |
| q_A extraction | last-token, layer −1, pre-decode at 1st `[ASSISTANT]` |
| Direction convention | lower R_inertia predicts correct (BCVF-faithful) |
| STRONG_AUC_THRESHOLD | 0.75 (inclusive) |
| STRONG_DELTA_AUC_THRESHOLD | 0.05 (inclusive, vs both chance and R_sim) |
| PARTIAL_AUC_THRESHOLD | 0.66 (inclusive) |
| DIRECTION_GATE_THRESHOLD | 0.5 (strict) |
| ALPHA_TARGETS | (0.35, 0.50, 0.75) |
| ALPHA_PRIMARY | 0.50 |
| N_MIN | 10 (selective-prediction floor) |
| SEED_ENTROPY | 15 |
| Class-3 firewall pattern count | 44 |
| Number of self-test cascade cases | 12 |

### Frozen artifacts

| Artifact | Path |
|---|---|
| Implementation script | `scripts/probe_inertia_15_13.py` |
| Cache | `docs/experiments/inertia_15_13_extractions.npz` |
| JSON output | `docs/experiments/probe_inertia_15_13.json` |
| Markdown output | `docs/experiments/probe_inertia_15_13.md` |

### Frozen behaviors

- No combination with H1 (state coherence) or H2 (intent competition).
- No bootstrap CI on AUCs in v1.
- No second benchmark (HaluEval) in v1.
- No probe training; R_inertia is a pure feature.
- No sign-flip rescue if direction gate fails.
- No retroactive amendment to any §13/§14/§15.x verdict-of-record.

---

## Notes for the implementing session

If you are picking this up cold:

1. **Start with this spec end-to-end.** Read all 6 sections before writing
   any code. The spec is self-contained — you should not need to consult
   the prior conversation or the main BCVF design doc.

2. **Mirror §15.10 / §15.11 patterns where possible.** The script structure
   (lazy imports, schema validation, cache .npz I/O, self-test gate,
   firewall, JSON+MD writers, CLI modes) maps closely to those scripts.
   Reuse the patterns; don't reinvent.

3. **Run the self-test gate before any data inspection.** All 12 cascade
   cases + cosine invariants + 44-pattern firewall must pass. Exit 3 on
   failure.

4. **Pre-commit cascade thresholds before looking at any AUC numbers.**
   §0.8 discipline. The thresholds are pinned in this spec; the
   implementation must apply them mechanically.

5. **Output is firewall-scanned before write.** The 44-pattern firewall
   is the last gate before any markdown lands on disk. INTERPRETATION_
   VIOLATION exits 4 without writing.

6. **The result is whatever it is.** STRONG, PARTIAL, or NO_MATERIAL —
   each is a valid §0.8-binding readout. NO_MATERIAL via direction-gate
   failure is the most likely outcome based on §15.11's pattern; that is
   acceptable. Do NOT modify the cascade rule, the direction convention,
   or the comparator requirement based on what the data shows.

7. **After the runpod run produces JSON+MD artifacts**, verify firewall
   compliance and cascade re-derivation locally before committing
   (mirrors the §15.10 / §15.11 verification pattern).

8. **The §15.12 closure is unaffected by §15.13's outcome.** Per the
   §15.12 ledger, this is a fresh top-level §0.X testing a different
   mechanism class. No retroactive reclassification.

### Optional v2 follow-ups (NOT authorized by this spec)

If v1 shows signal (PARTIAL or STRONG), the following v2 directions are
candidates for a fresh §0.X commitment — none of them are authorized here:

- HaluEval cross-benchmark replication.
- N=200 / N=500 statistical-power upgrade.
- 2nd-difference of phase coherence over turn boundaries (Tier 2 from the
  prior prioritization).
- H1 (state coherence) or H2 (intent competition) tested in isolation.
- Hand-constructed labeled multi-turn topic-pivot benchmark.

Each of these is a separate top-level §0.X, not a §15.13 amendment.

---

## End of spec

This document, sealed §0.8-binding, defines §15.13 in full. Any
implementation that follows it without deviation is a valid §15.13 run.
Any deviation requires a fresh amendment to this document.

The result is whatever the data shows — STRONG, PARTIAL, or NO_MATERIAL.
The cascade rule is mechanical. The verdict is binding regardless of
post-hoc interpretation.

§13.9 hold preserved. §6.1 N=21 autonomy result preserved. §15.10 PARTIAL_
SIGNAL_IN_Z preserved. §15.11 NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE
preserved. §15.12 closure preserved. §15.13 result is independent of all
of these.
