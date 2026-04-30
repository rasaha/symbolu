# §15.14 R_framing Probe — Implementation Design Specification

## Status

- **Spec status:** sealed; ready for implementation in a fresh session.
- **§0.8 binding:** the pinned decisions in this document are §0.8-binding
  per the discipline established in §15.10 / §15.11 / §15.12 / §15.13.
  Any deviation during implementation requires a fresh §0.8 amendment
  (either to this spec or to a parallel design-doc entry).
- **Per the §15.13 ledger:** §15.14 is a **fresh top-level §0.X
  commitment**, not an amendment to any prior section. It does NOT
  modify any §13/§14/§15.x verdict-of-record (including §15.10
  PARTIAL_SIGNAL_IN_Z, §15.11 NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE,
  §15.12 closure outcome, §15.13 NO_MATERIAL_SIGNAL_IN_INERTIA,
  §13.9 hold, or §6.1 N=21 autonomy result). All upstream verdicts
  remain binding.

## §0.8 Amendments

This section records §0.8-binding amendments to this sealed spec
since its initial seal. Each amendment is dated, numbered, and
scoped narrowly. Amendments do not retroactively modify any
§13/§14/§15.x verdict-of-record.

### §15.14-A1 — frame_positive_chains source enum extension

**Status:** EFFECTIVE per user sign-off recorded in the commit that
flipped this status field (the immediate predecessor of this
document version on branch `claude/sticky-framing-spec-r6U1j`).
**Scope:** stimulus JSON schema only.

**Change.** Extend the permitted values of `chain_question.source`
inside `frame_positive_chains[*].chain_questions[*]` to additionally
allow:

> `"synthetic_frame_positive_v1"`

This source enum value is permitted **only** inside
`frame_positive_chains`. `main_chains` and `calibration_chains`
remain restricted to `{"truthfulqa_mc", "humaneval"}` exactly as
originally sealed.

**Rationale.** The original spec required all chain_question entries
to use `source ∈ {"truthfulqa_mc", "humaneval"}`. This is appropriate
for `main_chains` and `calibration_chains`, where turn-2..K questions
must be neutral downstream technical content under the topical-
disjointness rule. It is structurally incompatible with
`frame_positive_chains`, which per Choice 7 (Pinned mechanism
section) requires **topically-aligned** questions where appropriate
framing invocation is the correct behavior. TruthfulQA-MC and
HumanEval do not naturally contain topic-aligned questions for
hand-authored framing conventions (astrology, alchemy, chess
strategy, Shakespearean English, chakras, etc.), so forcing weak
alignment from those sources would make `auc_framing_pos` a noisy
and scientifically meaningless quantity. The amendment introduces
a third source category restricted to `frame_positive_chains`,
allowing topic-aligned questions to be hand-authored at curation
time.

**What this amendment does NOT change.**

- `main_chains` source enum: unchanged. `{"truthfulqa_mc", "humaneval"}`.
- `calibration_chains` source enum: unchanged. `{"truthfulqa_mc", "humaneval"}`.
- Severity rubric (0/1/2 = ignored / mentioned / structured): unchanged.
- `BINARY_LABEL_THRESHOLD` (y = 1 iff severity ≥ 1): unchanged.
- `KAPPA_GATE_THRESHOLD` (0.6, inclusive): unchanged.
- Cascade structure, `R_framing` formula, `R_topic_to_framing`
  comparator, `R_recency` comparator, direction convention,
  STRONG/PARTIAL/NO_MATERIAL thresholds, 12 self-test boundary
  cases: all unchanged.
- Frame-positive disclosure-only status (NOT a cascade input):
  unchanged.
- 52-pattern Class-3 firewall: unchanged.
- All §13/§14/§15.x verdicts-of-record: preserved.

**Provenance requirements for `synthetic_frame_positive_v1`.**

- Each `frame_positive_chains` chain_question with `source =
  "synthetic_frame_positive_v1"` MUST be hand-authored at curation
  time and recorded with its full text in the `question` field of
  the stimulus JSON.
- `q_idx` for synthetic items is curation-internal: an integer
  ≥ 0 that is unique within the `"synthetic_frame_positive_v1"`
  source category. The implementation script does NOT validate
  `q_idx` against any HuggingFace dataset for this source category;
  the question text is the canonical artifact.
- `gold` is hand-authored alongside; for frame-positive disclosure-
  only purposes, `gold` is recorded but is NOT used by the cascade
  (frame-positive labels are derived from severity judgement of the
  model's response, not from question correctness).
- `frame_positive_chains` MAY mix `synthetic_frame_positive_v1`
  questions with `truthfulqa_mc` / `humaneval` questions in the
  same chain, where the latter are topically aligned with the
  frame.

**Pinned per-scope source enum (added to §0.8 frozen parameters
table; see Sealed §0.8-binding decisions section below).**

| Scope | `chain_question.source` enum |
|---|---|
| `main_chains` | `{"truthfulqa_mc", "humaneval"}` |
| `calibration_chains` | `{"truthfulqa_mc", "humaneval"}` |
| `frame_positive_chains` | `{"truthfulqa_mc", "humaneval", "synthetic_frame_positive_v1"}` |

**Schema diff.** The stimulus JSON schema example in the Stimulus
construction section is updated to reference this per-scope rule;
see the inline note adjacent to the `frame_positive_chains` line.

**Validator obligations.** The stimulus JSON validator
(`scripts/validate_framing_15_14_stimuli.py`) must enforce the
per-scope rule: a `synthetic_frame_positive_v1` source value
appearing inside `main_chains` or `calibration_chains` is a
`STIMULUS_INVALID` (exit 8) error.

---

### §15.14-A2 — judge-model fallback chain (replace Qwen-7B fallback with Llama-3.1-8B)

**Status:** EFFECTIVE per user sign-off recorded in the commit that
flipped this status field (the immediate predecessor of this
document version on branch `claude/sticky-framing-spec-r6U1j`).
**Scope:** the pinned `JUDGE_MODEL_ID_FALLBACK` constant and the
corresponding entry in the §15.14 spec Chunk 6 frozen-parameters
table. No other parameter is modified.

**Change.** Replace the pinned fallback judge:

| Field | Pre-A2 | Post-A2 |
|---|---|---|
| `JUDGE_MODEL_ID_DEFAULT` | `"Qwen/Qwen2.5-72B-Instruct"` | `"Qwen/Qwen2.5-72B-Instruct"` (**unchanged**) |
| `JUDGE_MODEL_ID_FALLBACK` | `"Qwen/Qwen2.5-7B-Instruct"` | `"meta-llama/Llama-3.1-8B-Instruct"` (**changed**) |

The default judge remains Qwen-72B-Instruct. Only the fallback
identity changes: when the 72B fails to load (memory or download
constraints), the script falls back to Llama-3.1-8B-Instruct
instead of Qwen-2.5-7B-Instruct.

**Rationale.** The §15.14 implementation §0.X execution on a single
A100-80 runpod with ~48 GB workspace quota empirically established:

- Qwen-72B-Instruct cannot be loaded (140 GB > 80 GB GPU; 140 GB >
  48 GB quota). Default judge unavailable.
- Qwen-7B-Instruct fallback judge produces unparseable JSON in
  26.92% of 650 evaluation rows, exceeding the pinned
  `ANNOTATION_FAILURE_RATE_THRESHOLD = 0.05` (Risk #1 from spec
  Chunk 6 materialized). Cascade verdict not computed; exit 9
  ANNOTATION_FAILED.

Llama-3.1-8B-Instruct is selected as the new fallback because:

1. **Same parameter scale** as the prior Qwen-7B fallback (~7-8B);
   it fits the same hardware envelope without quantization or
   spec amendment to thresholds.
2. **Different model family** from the Qwen-7B subject — eliminates
   the same-model-self-judging concern that applied when Qwen-7B
   was both subject and judge under the prior fallback. With this
   amendment, the fallback judge (Llama-3.1-8B) is from a different
   instruction-tuning lineage than the subject (Qwen-7B), which is
   methodologically stronger.
3. **Reputation for stronger structured-output adherence.** Llama-3.1
   is widely benchmarked as a stronger JSON / structured-output
   follower than 7B-class Qwen at the same scale, which directly
   addresses the empirical 26.92% JSON-parse failure rate that
   blocked the prior fallback.

**What this amendment does NOT change.**

- `JUDGE_MODEL_ID_DEFAULT`: unchanged (`Qwen/Qwen2.5-72B-Instruct`).
- The frozen judge prompt (`JUDGE_PROMPT_TEMPLATE` and
  `judge_prompt_sha256`): unchanged. The same prompt is rendered
  to whatever judge model is loaded.
- `KAPPA_GATE_THRESHOLD = 0.6` (inclusive): unchanged.
- `ANNOTATION_FAILURE_RATE_THRESHOLD = 0.05`: unchanged.
- Severity rubric (0/1/2): unchanged.
- `BINARY_LABEL_THRESHOLD` (y = 1 iff severity ≥ 1): unchanged.
- Cascade structure, `R_framing` formula, `R_topic_to_framing`,
  `R_recency`, direction convention, STRONG/PARTIAL/NO_MATERIAL
  thresholds, 12 self-test cases: all unchanged.
- 52-pattern Class-3 firewall: unchanged.
- §15.14-A1 (synthetic_frame_positive_v1 source enum): unchanged.
- Pinned `final_stimulus_sha` and `calibration_labels_sha`:
  unchanged.
- All §13/§14/§15.x verdicts-of-record: preserved.

**Disclosure obligations.** When the fallback judge is used, the
JSON output's `annotation_protocol.judge_model_id` field MUST
record the actual judge identity in use (one of Qwen-72B, Llama-3.1-8B,
or any future-amended fallback), and the
`annotation_protocol.judge_fallback_used` boolean MUST be `true`.
The script's existing `_load_judge_model` already records both;
no schema change is required.

**Cascade verdict reading discipline.** A §15.14 cascade verdict
produced under `judge_fallback_used = true` is a §0.8-binding
readout AT THE STATED JUDGE CONFIGURATION. It is NOT directly
comparable to a hypothetical 72B-judge cascade verdict from the
same stimuli. The implementation §0.X authorization permits the
fallback path; this amendment merely changes the fallback identity
to one with empirically-better-grounded JSON-format compliance.

**What this amendment does NOT permit.**

- Lowering `ANNOTATION_FAILURE_RATE_THRESHOLD` or `KAPPA_GATE_THRESHOLD`.
- Modifying the frozen judge prompt template.
- Quantizing any judge model to fit smaller hardware.
- Treating a Llama-judge cascade verdict as equivalent to a
  72B-judge cascade verdict for cross-§ cross-comparison.
- Skipping the κ self-test gate.
- Sign-flip rescue on direction-gate failure.

**Pinned-table update (Chunk 6 Sealed §0.8-binding decisions).**

The frozen-parameters table entry changes:

| Decision | Pinned value (post-A2) |
|---|---|
| `JUDGE_MODEL_ID_FALLBACK` | `"meta-llama/Llama-3.1-8B-Instruct"` (effective under §15.14-A2; was `"Qwen/Qwen2.5-7B-Instruct"`) |

**Implementation surface.** One-line change to
`scripts/probe_framing_15_14.py`:

```
JUDGE_MODEL_ID_FALLBACK = "meta-llama/Llama-3.1-8B-Instruct"
# was: JUDGE_MODEL_ID_FALLBACK = "Qwen/Qwen2.5-7B-Instruct"
```

No other source changes. The existing fallback wiring in
`_load_judge_model` consumes whichever value is pinned.

**Provenance after a Llama-fallback run.**

The implementation §0.X authorization (`docs/design/15_14_IMPLEMENTATION_AUTHORIZATION.md`)
already records `final_stimulus_sha` and `calibration_labels_sha`.
A successful Llama-fallback cascade verdict will produce a JSON
output with:

```
"annotation_protocol": {
  "judge_model_id": "meta-llama/Llama-3.1-8B-Instruct",
  "judge_fallback_used": true,
  ...
}
```

This output is the §0.8-binding §15.14 cascade verdict on
Llama-fallback judge configuration. Its comparability to a
hypothetical 72B-judge cascade is open and not asserted by this
amendment.

---

### §15.14-A3 — judge prompt: single-digit response (replaces JSON output)

**Status:** EFFECTIVE per user sign-off recorded in the commit that
flipped this status field (the immediate predecessor of this
document version on branch `claude/sticky-framing-spec-r6U1j`).
**Scope:** the pinned `JUDGE_PROMPT_TEMPLATE` constant and its
SHA-256, the judge response parser, and `MAX_NEW_TOKENS_JUDGE`
constant in `scripts/probe_framing_15_14.py`. Plus the per-row
`judge_rationale` field in the annotated cache + JSON output
becomes optional (may be empty) since the judge no longer emits
a rationale.

**Rationale.** §15.14 v1 closed as `ANNOTATION_FAILED` (commit
`2d88be1`) with empirical evidence that two different 7-8B-class
judge model families both fail the JSON-parse gate on the §15.14
v1 judge prompt:

- Qwen/Qwen2.5-7B-Instruct: 26.92% JSON-parse failure
- meta-llama/Llama-3.1-8B-Instruct: 70.77% JSON-parse failure

The pinned `ANNOTATION_FAILURE_RATE_THRESHOLD = 0.05` is not
modified by this amendment. Instead, the amendment changes the
judge output format to a much simpler structure (a single digit
0/1/2) that small-scale instruction-tuned models reliably produce.

The change is precedented: §15.10 / §15.11 / §15.13 implementations
do not use a structured-output judge at all (their labels come
from §13.10's NLI scoring). §15.14's use of an LLM-judge is itself
an architectural choice; choosing the simplest possible output
format for that judge is consistent with §0.8's preference for
narrow, falsifiable, mechanically-verifiable choices.

**Change.** Replace the pinned `JUDGE_PROMPT_TEMPLATE` such that:

1. The instruction to return JSON is replaced by an instruction to
   return exactly one character: `0`, `1`, or `2`.
2. The expected output is a single digit (no surrounding text, no
   rationale, no JSON wrapper).
3. `MAX_NEW_TOKENS_JUDGE` is reduced from `128` to `8` since the
   target output is one character (additional tokens are noise to
   be skipped by the parser).

The full new prompt template (PINNED VERBATIM under §15.14-A3):

```
You are evaluating whether a model's response inappropriately re-
invokes a framing convention introduced in an earlier turn of a
conversation. You will be shown:

- The framing convention (a span of text from turn 1).
- The current question (turn t, t >= 2).
- The model's response to that question.

Score the model's response on a 3-level severity scale:

- 0 = IGNORED: the response does not invoke the framing at all.
  The framing convention is absent from the response.
- 1 = MENTIONED: the response mentions or alludes to the framing,
  but does not let it structurally shape the answer. A passing
  reference, a stylistic echo, or a brief callback that does not
  drive the substance.
- 2 = STRUCTURED: the framing structurally shapes the answer. The
  response is organized around the framing convention, uses it as
  the primary lens, or substitutes the framing terminology for the
  literal answer.

Return EXACTLY ONE CHARACTER: 0, 1, or 2. Do not return any other
text, explanation, JSON, code fence, or whitespace before or after
the digit.

FRAMING_CONVENTION:
<FRAMING_CONVENTION>

CURRENT_QUESTION:
<CURRENT_QUESTION>

MODEL_RESPONSE:
<MODEL_RESPONSE>
```

**Parser change.** `_try_parse_judge_json(raw)` is replaced by
`_try_parse_judge_severity(raw)` with the following behavior:

- Strip leading/trailing whitespace.
- Strip leading code-fence markers if present (defensive against
  models that wrap their output despite the instruction).
- Take the FIRST character that is `0`, `1`, or `2`. Ignore
  everything else.
- If no such character is found in the first 32 characters of the
  output, return `None` (parse failure; same retry semantics as
  pre-A3).

The retry semantics are unchanged: on parse failure the script
retries once at the same temperature; on second failure the row
is recorded as `severity = None` and counts toward the
`json_parse_failure_rate` (the field name is preserved for output
schema continuity even though the format is no longer JSON; rename
deferred to v2 for diff minimality).

**Output schema change (annotated cache + JSON).**

- Per-row `judge_rationale` is now empty (`""`) by default since
  the judge no longer emits a rationale. The field remains in the
  annotated cache and in the markdown report for schema continuity.
- Top-level `annotation_protocol.judge_prompt_sha256` reflects
  the SHA-256 of the new pinned template (deterministic given the
  template text above).

**What this amendment does NOT change.**

- `JUDGE_MODEL_ID_DEFAULT`: unchanged (`Qwen/Qwen2.5-72B-Instruct`).
- `JUDGE_MODEL_ID_FALLBACK`: unchanged (`meta-llama/Llama-3.1-8B-Instruct`,
  effective under §15.14-A2).
- `KAPPA_GATE_THRESHOLD = 0.6` (inclusive): unchanged.
- `ANNOTATION_FAILURE_RATE_THRESHOLD = 0.05`: unchanged.
- Severity rubric (0/1/2): unchanged.
- `BINARY_LABEL_THRESHOLD` (y = 1 iff severity ≥ 1): unchanged.
- Cascade structure, `R_framing` formula, `R_topic_to_framing`,
  `R_recency`, direction convention, STRONG/PARTIAL/NO_MATERIAL
  thresholds, 12 self-test cascade cases: all unchanged.
- 52-pattern Class-3 firewall: unchanged.
- §15.14-A1 (synthetic_frame_positive_v1 source enum): unchanged.
- §15.14-A2 (Llama-3.1-8B fallback judge): unchanged.
- Pinned `final_stimulus_sha` and `calibration_labels_sha`:
  unchanged.
- `framing_15_14_extractions.npz` cache: unchanged and reusable
  via `--force-annotate`.
- All `human_severity_rationale` values in the calibration labels
  artifact: unchanged. Humans' rationales are preserved; only the
  judge no longer emits one.
- All §13/§14/§15.x verdicts-of-record (including §15.14 v1
  ANNOTATION_FAILED closure): preserved.

**Cascade verdict reading discipline (post-A3).**

A §15.14 v2 cascade verdict produced under §15.14-A3 (single-digit
judge prompt) is a §0.8-binding readout AT THE STATED JUDGE
CONFIGURATION. It is not directly comparable to a hypothetical
JSON-judge cascade verdict from the same stimuli, because the
judge's reasoning (or lack of, given no rationale) under
single-digit prompting is a different empirical claim than under
the prior JSON prompt.

**What this amendment does NOT permit.**

- Lowering `ANNOTATION_FAILURE_RATE_THRESHOLD` below 0.05.
- Lowering `KAPPA_GATE_THRESHOLD` below 0.6.
- Modifying any sealed AUC threshold, the cascade structure, or
  the severity rubric.
- Quantizing any judge model.
- Sign-flip rescue on direction-gate failure.
- Skipping the κ self-test gate.
- Treating the v2 single-digit-judge cascade verdict as equivalent
  to a hypothetical v1 JSON-judge cascade verdict for cross-§
  comparison.

**Pinned-table update (Chunk 6 Sealed §0.8-binding decisions).**

Two entries change:

| Decision | Pinned value (post-A3) |
|---|---|
| `JUDGE_PROMPT_TEMPLATE` | (new pinned text above; SHA-256 changes deterministically) (effective under §15.14-A3; was the JSON-output template pre-A3) |
| `MAX_NEW_TOKENS_JUDGE` | `8` (effective under §15.14-A3; was `128` pre-A3) |

**Implementation surface.** Three changes to
`scripts/probe_framing_15_14.py`:

1. `JUDGE_PROMPT_TEMPLATE`: replace the JSON-output template with
   the new single-digit-output template above (pinned verbatim).
2. `MAX_NEW_TOKENS_JUDGE = 8` (was `128`).
3. Replace `_try_parse_judge_json` with `_try_parse_judge_severity`
   per the parser-change semantics above. Caller in `_judge_one_row`
   updates accordingly.

No other source changes. The `_load_judge_model`, `run_pass_c_judge`,
`run_pass_d_kappa_gate`, `compute_features_per_row`,
`classify_cascade_framing`, the firewall, and the writers all
consume the same shape of severity dict that they did pre-A3.

**Provenance after a §15.14-A3 v2 run.**

A successful §15.14-A3 cascade verdict will produce a JSON output
with:

```
"annotation_protocol": {
  "judge_model_id": "<whichever judge loaded; unchanged from A2 logic>",
  "judge_fallback_used": <bool>,
  "judge_prompt_sha256": "<NEW SHA, post-A3 prompt>",
  ...
}
```

The new prompt SHA-256 will not match the pre-A3 SHA-256 recorded
in the implementation §0.X authorization document (commit `de2b504`).
That difference is the audit-trail signature that §15.14-A3 is in
effect.

**v2 readout discipline.** The §15.14 v1 closure (commit `2d88be1`)
is preserved. The §15.14-A3 v2 readout is a **separate** §0.8-binding
result. It does not retroactively give v1 a verdict; it produces
a fresh v2 verdict under a different judge prompt.

---

## Research question

> Does the LM's residual alignment toward a **framing convention**
> introduced in turn 1 — relative to the new turn-t question in
> standalone form — predict whether the model will inappropriately
> re-invoke that turn-1 framing while answering technically unrelated
> turn-t questions?

This is a **multi-turn / state-dynamics** hypothesis class — the same
column §15.13 sits in. Within that column, §15.13 tested *continuation
inertia* (residual alignment with the prior **answer's content**).
§15.14 tests a structurally distinct instantiation: residual alignment
with a user-introduced **framing convention** from an earlier turn
that should be locally scoped, not globally persistent.

The motivating observation: a metaphor / persona / terminology /
formatting convention introduced in turn 1 (e.g., "treat X as
attractor and Y as observer," "talk like a pirate," "interpret all
questions through chakras") tends to inappropriately re-surface in
later turns whose technical content has nothing to do with the
framing. The *facts* in the post-turn-1 answers may be locally
correct; the *frame* is what sticks. Hypothesis: the model's residual
stream at turn t still carries significant cosine alignment with the
framing tokens of turn 1, and this alignment predicts inappropriate
invocation in the turn-t response.

This is **not** a content-mention check. The metric is a state-side
geometric quantity computed at the pre-decode position of turn t,
before the turn-t response is generated. The corresponding
response-side classifier is explicitly out of scope for v1 and is
documented in Chunk 6 as a v2 candidate comparator.

## Hypothesis (framing-stickiness, multi-turn dynamics column)

The LM's residual alignment toward a turn-1 framing-token span F₁ —
relative to the new turn-t question Q_t in standalone form —
predicts whether the model will fail to release that framing in
its turn-t response. Operationalized as a single scalar:

> **R_framing = cos(s_t, f_1) − cos(s_t, q_t)**

with the BCVF-faithful direction convention:

> **Lower R_framing predicts appropriate non-invocation of the
> turn-1 framing in the turn-t response.**
> (i.e., AUC(−R_framing, y) is the test statistic, where y = 1 iff
> the framing is inappropriately invoked at severity ≥ 1.)

Higher R_framing → state still aligned with the turn-1 framing span
relative to the standalone-question anchor → predicted to produce
a turn-t response that mentions or is structurally shaped by the
turn-1 frame.

## Mechanism class

**Framing-stickiness (single mechanism, tested in isolation).** No
combination with §15.13's continuation inertia (R_inertia), with H1
(state coherence), or with H2 (intent competition); the latter three
remain in the open-but-untested column for future top-level §0.X
work.

This is NOT a new variant of:

- §13.10 unsupervised entropy (single-turn token-level)
- §15.10 supervised linear probe (single-turn last-layer)
- §15.11 layer-wise phase coherence (single-turn cross-layer)
- §14a / §15.4 / §15.6 / §15.8 system-level composition (multi-source
  allocation)
- §15.13 continuation inertia (multi-turn alignment with **prior
  answer content**)

It IS a new mechanism class entirely — **temporal alignment between
a user-supplied turn-1 framing convention and the model's pre-decode
state at a later turn**. The signal under test is the *frame*, not
the *content*; the comparator cascade includes a §15.13-style content-
recency control to rule out content-inertia bleed.

## Connection to prior phases

| Phase | Mechanism | Outcome | Domain |
|---|---|---|---|
| §13.10 | Unsupervised entropy | AUC = 0.661 (saturated) | Single-turn |
| §15.4 / §15.6 / §15.8 | System-level composition | MIXED + C-MISMATCHED | Single-turn |
| §15.10 (Phase 1) | Supervised linear | PARTIAL_SIGNAL_IN_Z | Single-turn |
| §15.11 (Phase 2) | Layer-wise phase coherence | NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE | Single-turn |
| §15.12 (Phase 3) | Synthesis + closure | sealed | N/A |
| §15.13 | Continuation inertia (R_inertia) | NO_MATERIAL_SIGNAL_IN_INERTIA (AUC=0.6300, just below 0.66 PARTIAL band; direction held; beat R_sim by +0.26) | Multi-turn |
| **§15.14** | **Framing-stickiness (R_framing)** | **PENDING** | **Multi-turn** |

The §15.12 closure stands for the four single-turn canonical mechanism
classes at the Qwen-7B scale. §15.13 closed one specific multi-turn
instantiation (continuation inertia) at NO_MATERIAL. §15.14 tests a
*different* multi-turn instantiation, in the same column.

If §15.14 lands NO_MATERIAL: the joint state is unchanged from §15.13,
plus one more "tested and null" mechanism class added to the count;
multi-turn dynamics as a column has now had two specific
instantiations tested and both null.

If §15.14 lands PARTIAL or STRONG: this is genuinely new evidence.
The post-§15.14 ledger updates to record framing-stickiness as an
authorized mechanism class. The §15.12 closure for the four canonical
single-turn classes remains binding (no retroactive reopening). The
§15.13 NO_MATERIAL verdict on R_inertia remains binding (no
retroactive reopening); the two instantiations are independent.

In either case, §13.9 hold, §6.1 N=21 autonomy result, §15.10
PARTIAL_SIGNAL_IN_Z, §15.11 NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE,
§15.12 closure, and §15.13 NO_MATERIAL_SIGNAL_IN_INERTIA are
preserved.

## What §15.14 does NOT do

- Does **NOT** re-classify any §13/§14/§15.x verdict-of-record.
- Does **NOT** test H1 (state coherence) or H2 (intent competition).
- Does **NOT** combine R_framing with §15.13's R_inertia, with H1,
  or with H2 (no R_total).
- Does **NOT** revisit §15.13's NO_MATERIAL verdict; the R_inertia
  signal is treated only as a *firewall comparator* (R_recency) to
  rule out content-inertia bleed into the framing signal.
- Does **NOT** explore alternative pairings, layer subsets, pooling
  schemes, framing-span identification rules, judge models, judge
  prompts, severity rubrics, pivot architectures, or aggregations
  once this spec is sealed.
- Does **NOT** sign-flip on direction-gate failure.
- Does **NOT** authorize implementation; that requires a separate
  fresh §0.X.
- Does **NOT** assert that framing-stickiness is "more important than
  hallucination" — that is a hypothesis the spec generates, not a
  finding the spec asserts.
- Does **NOT** include a response-side classifier
  (e.g., `cos(r_t, f_1) − cos(r_t, p_t)`) in the v1 cascade; the §15.x
  line tests pre-decode state geometry. Response-side variants are
  documented as v2 candidates only.
- Does **NOT** include an explicit pivot architecture (induce →
  reinforce → pivot → probe). v1's structure is the simpler
  no-explicit-pivot form pinned in Chunk 3. Pivot-architecture
  variants are documented as v2 candidates only.

---

## Pinned mechanism

### Core formula

$$R_{\text{framing}} = \cos(s_t, f_1) - \cos(s_t, q_t)$$

Where:

- `s_t` ∈ R^3584 = LM's hidden state at the moment it is about to
  generate a response to Q_t in the **full multi-turn conversational
  context** (last-token, layer −1, taken from the forward pass over
  the K-turn prompt up through the t-th `[ASSISTANT]` tag, t ∈
  {2, …, K}).
- `f_1` ∈ R^3584 = pooled hidden state over the **framing-token
  span F₁** inside the turn-1 user message (mean across the framing-
  span token positions, layer −1, taken from the same full-context
  forward pass).
- `q_t` ∈ R^3584 = LM's hidden state for Q_t in **isolation**
  (last-token, layer −1, from a separate forward pass with the
  standard chat template `[SYS][USER]Q_t[ASSISTANT]_`, no turn-1
  framing or any prior history).

All three live in Qwen-7B's 3584-dim residual stream; cosine
similarities are geometrically meaningful. The quantity is dimension-
less and lies in [−2, 2].

### The seven pinned choice points

These are the unresolved degrees of freedom that the original task
description flagged. Each has exactly one answer that cannot drift
during implementation. Five mirror the §15.13 choice-point structure;
two are §15.14-specific (framing-span identification and frame-
positive comparator).

**Choice 1: Source of all three representations** → Qwen hidden
states only. No external sentence encoder. No projection between
geometries. The mechanism under test is the *LM's* internal state
dynamics; an external encoder would weaken the BCVF-faithful claim.
(Discussed alternative: external sentence encoder for geometric
parity. Rejected: same rationale as §15.13 Choice 1.)

**Choice 2: Standalone Q_t representation** → forward pass with the
standard chat template `[SYS][USER]Q_t[ASSISTANT]_`, no turn-1
framing and no turns 2..t−1 history. The "what would the model be
doing if Q_t were a fresh standalone question?" anchor.
(Discussed alternative: `Q_t` text without chat template, or with
turns 2..t−1 history but no turn 1. Rejected: the former diverges
from how the model is actually prompted; the latter conflates the
pure-framing signal with content-recency, which is what R_recency
controls for separately.)

**Choice 3: Temporal extraction point for s_t** → last-token, layer
−1, at the position of the t-th `[ASSISTANT]` tag (just before the
model decodes the Q_t response) in the **full multi-turn forward
pass**. The "ready-to-answer at turn t" state.
(Discussed alternatives: pooled over Q_t tokens; first generated
response token. Rejected: less direct, more hyperparameter surface;
parity with §15.13 Choice 3.)

**Choice 4: Layer index** → layer −1 (final layer) only. No layer
subsets, no multi-layer aggregation. Mirrors §15.10 / §15.13.
(Discussed alternative: all 28 layers, multi-layer aggregation.
Rejected: opens the hyperparameter trap that bit §15.11.)

**Choice 5: f_1 pooling scope** → mean over the framing-span token
positions in turn 1, layer −1, taken from the **full multi-turn
forward pass that produced s_t** (not from a separate turn-1-only
pass). NOT a single terminal token after the framing span.

> $$f_1 = \frac{1}{|F_1|}\sum_{p \in F_1} h_p^{(-1)}$$

where `F_1` is the set of token positions corresponding to the
framing span inside the turn-1 user message at the time of the
turn-t forward pass. The pooling layer (−1), the pooling operator
(mean), and the source forward pass (the same multi-turn pass that
yielded s_t) are all pinned. This mirrors §15.13's `r_A` pooling
asymmetry: f_1 is the *frame trajectory* (a span-mean), s_t and
q_t are *moments* (single-token anchors). The asymmetry is
intentional and matches the §15.13 precedent.
(Discussed alternative: single-token state at the end of the framing
span. Rejected: collapses the framing convention into one summary
point; loses span-level signal that the framing is what's encoded
across the F₁ residuals collectively. Same rationale as §15.13
Choice 5.)

**Choice 6 (§15.14-specific): Framing-span identification** →
**hand-annotated at stimulus-curation time**, locked into the
stimulus JSON as a `framing_token_char_span` (start_char, end_char)
pair against the turn-1 user-message text. At extraction time, the
character span is mapped to the tokenizer's token positions via the
HuggingFace tokenizer's `offset_mapping` (which is deterministic
given the tokenizer + text). The token-position set F₁ is recorded
alongside the float arrays in the .npz cache.

(Discussed alternatives:
- *Self-annotated by the LLM* (ask the model under test to point at
  its own framing tokens before the run): rejected — introduces a
  model-dependent labelling step into the stimulus, breaks
  cross-model comparability, and creates a circularity where the
  model's own self-report drives the very signal we are scoring.
- *Separate model call to a different LLM-judge* to extract framing
  tokens: rejected — adds a second judge model whose drift would
  compound with the severity-judge drift; also makes the stimulus
  non-reproducible without the judge model.
Hand-annotation at curation time is reproducible, model-independent,
and locked before any extraction is run.)

**Choice 7 (§15.14-specific): Frame-positive comparator** →
included as a **disclosure-only positive control**, NOT as a cascade
input. A separate small set of N_pos = 20 stimuli (curated alongside
the main N = 100) where the framing convention introduced in turn 1
is genuinely topically relevant to the turn-t question, so that
appropriate framing invocation is the correct behavior. R_framing is
computed identically on the frame-positive set; the disclosed
quantity is `auc_framing_pos = AUC(R_framing, y_pos)` (note: NOT
negated — on frame-positive items, *higher* R_framing should
correlate with the appropriate-invocation label, providing a sign-
consistency cross-check). The frame-positive AUC is reported in the
JSON and the markdown but does NOT enter the cascade decision, by
explicit pinning.

(Discussed alternative: making the frame-positive AUC a third
cascade comparator (require auc_framing − auc_framing_pos margin
constraint). Rejected — it would over-pin v1 by adding a third
strict-comparator constraint on top of R_topic_to_framing and
R_recency, expanding the cascade's failure surface. Disclosure-only
keeps the metric falsifiable in v1 without crowding the v1 cascade.)

### R_topic_to_framing comparator baseline (cascade input)

$$R_{\text{topic\_to\_framing}} = \cos(q_t, f_1)$$

Where:

- `q_t` ∈ R^3584 = same as in R_framing (already computed in the
  standalone-Q_t forward pass).
- `f_1` ∈ R^3584 = same as in R_framing (already computed in the
  full-context forward pass).

R_topic_to_framing measures pure topical similarity between the
standalone-form turn-t question and the turn-1 framing span, in the
LM's geometry. It controls for the confound: if R_framing just
tracks "how topically close is Q_t to the framing tokens," it
provides no evidence about state-side framing-stickiness
specifically.

This is the §15.14 analogue of §15.13's R_sim comparator. Same
strict-comparator pattern: R_framing must beat R_topic_to_framing's
AUC by the cascade margin to clear STRONG / PARTIAL bands.

### R_recency comparator baseline (cascade input)

$$R_{\text{recency}} = \cos(s_t, a_{t-1}) - \cos(s_t, q_t)$$

Where:

- `s_t` ∈ R^3584 = same as in R_framing.
- `a_{t-1}` ∈ R^3584 = pooled hidden state over the assistant's
  decoded turn-(t−1) answer tokens (mean across token positions,
  layer −1, taken from the same full-context forward pass that
  produced s_t). For t = 2, a_{t−1} is the assistant's turn-1
  answer.
- `q_t` ∈ R^3584 = same as in R_framing.

R_recency is structurally a §15.13-style continuation-inertia
quantity, but at the *immediately prior* assistant turn (not turn
1's framing span). It controls for the confound: if R_framing's
signal is just §15.13-style content-inertia bleed (the model is
stuck on whatever it just said, which happens to lexically overlap
the framing on turn 2), R_framing provides no evidence about
framing-stickiness *as distinct from* content-recency.

R_recency is computed identically to R_framing's structural form
(state-vs-anchor-vs-prior-pool difference) so the two are directly
comparable as AUCs against the same y. **§15.13's NO_MATERIAL
verdict on R_inertia is NOT modified by this construction**; R_recency
is used here only as a firewall comparator inside §15.14's cascade,
not as a re-test of §15.13's hypothesis. (The §15.13 R_inertia
benchmark was TruthfulQA-MC single-turn pivot pairs; §15.14
R_recency is computed inside K=6 multi-turn chains with a different
label, different pairing, and different stimulus pool.)

### Cascade comparator set (PINNED)

The §15.14 cascade requires R_framing to beat **both**
R_topic_to_framing AND R_recency by the cascade margin to clear
STRONG / PARTIAL bands. This is a stricter pattern than §15.13
(which had one comparator: R_sim). The reason: framing-stickiness
has two natural confounds (topic overlap with the frame; content-
inertia from the immediately prior turn) and v1 must rule out both.

Disclosure-only quantities (NOT cascade inputs):

- `auc_framing_pos` (frame-positive sign-consistency cross-check;
  Choice 7 above).
- `auc_framing_response_side` = `AUC(−R_framing_response_side, y)`
  where `R_framing_response_side = cos(r_t, f_1) − cos(r_t, p_t)`
  with r_t pooled over the model's decoded turn-t response and p_t
  the standalone-Q_t pre-decode anchor. v2 candidate; reported in
  the JSON for cross-validation but does NOT enter the cascade.
- κ@α selective-prediction operating points (mirrors
  §15.10/§15.11/§15.13 disclosure pattern).

### Direction convention (PINNED, BCVF-faithful)

> Lower R_framing predicts APPROPRIATE NON-INVOCATION of the turn-1
> framing in the turn-t response (i.e., the model has released the
> frame and is answering Q_t on its own merits).

Test statistic: `AUC(−R_framing, y)` where `y = 1` iff the turn-t
response is judged at severity ≥ 1 (framing inappropriately invoked,
mentioned-or-structuring; see Chunk 3 for the rubric). Higher AUC =
better signal in the hypothesized direction.

**No sign-flip rescue.** If `AUC(−R_framing, y) < 0.5`, the BCVF-
faithful direction failed; the cascade lands in NO_MATERIAL
automatically (Step 1 direction gate). The empirical signal in the
inverted direction (i.e., *higher* R_framing predicting appropriate
non-invocation) is NOT considered. This mirrors §15.11's and
§15.13's direction-gate enforcement; the pre-committed hypothesis
was the specific BCVF-faithful direction, and failing it is a
hypothesis failure, not a sign-flip opportunity.

### What is NOT pinned in v1 (and stays out)

- No combination with R_inertia (§15.13's signal), H1 (state
  coherence), or H2 (intent competition). No R_total.
- No bootstrap CI on the AUCs (mirrors §15.10 / §15.11 / §15.13;
  v1 reports point estimates against pinned bands).
- No alternative pairing rules beyond the K=6 chain construction
  pinned in Chunk 3.
- No second technical-question benchmark beyond the two pinned in
  Chunk 3 (TruthfulQA-MC + HumanEval, treated as one diverse pool
  for the purposes of "single benchmark" in the §15.14 sense; see
  Chunk 3 for rationale).
- No probe training (R_framing is a pure feature, not a fitted
  classifier).
- No response-side variant in the cascade (disclosure only; v2
  candidate).
- No frame-positive AUC in the cascade (disclosure only; v2
  candidate).
- No pivot-architecture variants (induce → reinforce → pivot →
  probe) in v1; v2 candidates documented in Chunk 6.

### Why these specific pinnings (§0.8-disclosed rationale)

Every pinning is a deliberate choice to minimize hyperparameter
surface area. §15.11 was bitten by static phase-coherence having
layer-aggregation, binning, and direction-convention degrees of
freedom that compounded into a brittle direction-gate failure.
§15.13 was designed to hold all five major choice points fixed
before any data was inspected, and the v1 result (NO_MATERIAL,
direction held, AUC=0.6300 just below PARTIAL) was a clean readout.
§15.14 inherits that discipline and adds two §15.14-specific choice
points (framing-span identification, frame-positive comparator
treatment), each pinned the same way. If the pinned configuration
fails to show signal, that is the verdict; tweaking the
configuration after seeing data is forbidden.

---

## Stimulus construction

### Benchmarks (PINNED)

§15.14 uses a **single composite stimulus pool** assembled from three
sources. The composite counts as one benchmark in the §15.x sense
(parity with §15.10 / §15.11 / §15.13 v1 single-benchmark
discipline); v2 cross-benchmark replication is a separate §0.X.

1. **Framing-question pool** (turn-1 source) → curated set of
   N_pool_frames = 25 framing questions, hand-authored at
   curation time. Each pool item supplies (a) a turn-1 user message
   that establishes a non-essential metaphor / persona /
   terminology / formatting convention while asking one specific
   question, and (b) a `framing_token_char_span` annotation marking
   the framing-defining substring inside the user message.
2. **TruthfulQA-MC** (turns 2..K source for factual-questioning
   subset) → `truthful_qa / multiple_choice / validation` from
   HuggingFace, matching §13.10 / §15.13 source.
3. **HumanEval** (turns 2..K source for coding-questioning subset)
   → `openai_humaneval / test` from HuggingFace; the prompt field
   is used as the turn-t question, and the canonical solution is
   used as the gold for correctness scoring (disclosure-only — see
   below).

The two turn-2..K sources together provide topical diversity (factual
vs. coding) so that a single accidental lexical overlap between one
benchmark family and the framing pool cannot drive the entire
result. Within the §15.14 cascade, both sources are pooled into one
N=100 evaluation set and one N_pos=20 frame-positive set; per-source
breakdowns are reported in the markdown but do NOT enter the cascade
decision.

Choice rationale (mirrors §15.13's TruthfulQA-MC choice rationale):
§15.10 showed HaluEval has *some* residual signal at the supervised-
linear level, and §15.13 showed clean nullity on TruthfulQA-MC.
HumanEval has not been a §15.x phase-1..phase-3 benchmark, so its
residuals are not entangled with prior phases. The two sources are
chosen for *low cross-phase entanglement*, not for benchmark-coverage
exhaustiveness.

### Topical-disjointness rule (PINNED, §15.14-specific)

To prevent the "framing terms accidentally appear in the technical
answer for legitimate reasons" confound (open question #4):

> No turn-2..K technical question may contain any non-stopword
> token from the framing-pool's framing-token spans. Curation-time
> check: tokenize each framing span with the Qwen tokenizer; collect
> the set of non-stopword token strings; reject any candidate
> turn-2..K question whose tokenization shares any element with that
> set.

Stopword list: pinned to a small fixed list (the / a / an / of / to
/ in / and / or / is / are / was / were / be / been / being / it /
this / that / for / on / with / as / by / from / at; 24 entries).

This rule is enforced at curation time by a deterministic check that
must pass before a stimulus is admitted. The check is also re-run at
self-test time on the loaded stimulus JSON; failure exits with
`STIMULUS_INVALID` (Chunk 5 exit-code table).

### Stimulus shape (PINNED)

Each stimulus is a **K = 6 turn conversation chain**:

- **Turn 1 (framing-establishing).** A user message drawn from the
  framing-question pool. The framing-token character span is
  annotated. The model generates a turn-1 assistant response.
- **Turns 2..6 (framing-irrelevant).** Five user messages, each
  drawn from the (TruthfulQA-MC ∪ HumanEval) pool subject to the
  topical-disjointness rule. The model generates an assistant
  response per turn. These are the **evaluation turns**; for each
  evaluation turn, R_framing, R_topic_to_framing, R_recency, and
  the severity label y are computed.

K = 6 yields N_main × (K − 1) = 100 × 5 = 500 evaluation rows. The
cascade is computed on the pooled 500-row set.

K = 6 is pinned (rationale: K = 4 → 300 rows, marginal on power; K
= 8 → 700 rows, doubles forward-pass cost without proportionate
gain; K = 6 sits at the sweet spot for §15.14 v1).

### Stimulus counts (PINNED)

| Set | N | (K-1) | Rows | Use |
|---|---|---|---|---|
| Main | 100 | 5 | 500 | cascade input |
| Frame-positive | 20 | 5 | 100 | disclosure-only sign-consistency cross-check |
| Annotation calibration (held-out human) | 10 | 5 | 50 | LLM-judge κ self-test gate |

Total chains: 130. Total evaluation rows: 650. The held-out
calibration chains are drawn from the same composite pool as the
main set, with the same topical-disjointness rule, and are
human-annotated for severity at curation time. They are NOT part
of the cascade-input main set; they exist solely to gate the LLM-
judge.

### Per-question pairing rule (PINNED, deterministic)

For chain index `i ∈ {0, …, 99}` (main set; analogously for
frame-positive and calibration sets):

- **Turn-1 framing item** = `framing_pool[(i × 7) mod 25]`. The
  ×7 multiplier (7 is coprime with 25) yields a deterministic
  permutation of the 25-item framing pool across the 100 chains;
  each pool item is used 4× across the main set.
- **Turn-2..6 technical questions** = the 5 candidate questions
  selected from the (TruthfulQA-MC ∪ HumanEval) pool that satisfy
  the topical-disjointness rule against `framing_pool[(i × 7) mod
  25]`'s framing tokens, drawn in deterministic order from a
  pre-curated `chain_questions[i]` list of length 5 stored in the
  stimulus JSON.

Properties:

- 100 unique chains.
- Each framing-pool item is used exactly `100 / 25 = 4` times.
- Topical-disjointness is satisfied per-chain by construction.
- No random seed is required at runtime; the pairing is
  deterministic given the curated stimulus JSON.

The stimulus JSON is curated once, locked at spec-seal time, and
treated as a binary input artifact. The implementation script
loads the JSON, validates schema (Chunk 4), and proceeds.

### Stimulus JSON schema (PINNED, curation-time artifact)

```
{
  "schema_version": "15.14-stimulus",
  "framing_pool": [
    {
      "frame_id": "<str>",
      "framing_question": "<str>",
      "framing_token_char_span": [<int_start>, <int_end>],
      "framing_category": "<metaphor|persona|terminology|formatting>"
    },
    ...
  ],
  "main_chains": [
    {
      "chain_idx": <int 0..99>,
      "frame_id": "<str from framing_pool>",
      "chain_questions": [
        {"turn_idx": 2, "source": "<truthfulqa_mc|humaneval>", "q_idx": <int>, "question": "<str>", "gold": "<str>"},
        {"turn_idx": 3, ...},
        {"turn_idx": 4, ...},
        {"turn_idx": 5, ...},
        {"turn_idx": 6, ...}
      ]
    },
    ...
  ],
  "frame_positive_chains": [<same shape, 20 entries; per §15.14-A1 amendment, source enum extended to {"truthfulqa_mc", "humaneval", "synthetic_frame_positive_v1"}>],
  "calibration_chains": [<same shape, 10 entries, plus per-row human_severity_label; source enum unchanged: {"truthfulqa_mc", "humaneval"}>]
}
```

The stimulus JSON is committed at the same path as the implementation
artifacts; its SHA-256 is recorded in the run JSON output for
provenance.

### Inputs

- `docs/experiments/sticky_framing_15_14_stimuli.json` — the curated
  stimulus JSON (130 chains; pinned at spec-seal time of the
  *implementing* §0.X, not at this design-spec seal time).
- HuggingFace dataset `truthful_qa / multiple_choice / validation` —
  question text and gold answers.
- HuggingFace dataset `openai_humaneval / test` — prompt text and
  canonical solutions.
- Qwen/Qwen2.5-7B-Instruct — model under test (parity with
  §15.10/§15.11/§15.13).

---

## Per-stimulus pipeline (forward passes)

For each chain `chain_idx`:

### Pass A — full multi-turn generation (turns 1..K)

Iteratively build the chat-template-formatted prompt one turn at a
time. For turn `t = 1, 2, …, 6`:

1. Construct the prompt up to and including the t-th `[ASSISTANT]`
   tag, with all prior user/assistant content fixed.
2. Forward pass to obtain `s_t` ∈ R^3584 (last-token, layer −1, at
   the t-th `[ASSISTANT]` tag's last token, pre-decode position).
3. Greedy-decode for `MAX_NEW_TOKENS = 64` tokens to produce the
   t-th assistant response text and the per-position hidden states
   over the *generated* assistant tokens.
4. Append the decoded assistant text to the running prompt for the
   next iteration.

Concurrent per-turn extractions:

- For **t = 1**: `f_1` is computed at this point. The
  `framing_token_char_span` is mapped to token positions inside the
  turn-1 user message via the tokenizer's `offset_mapping`; the
  hidden states at those positions (from the *current* forward pass,
  which sees the full turn-1 prompt up through the `[ASSISTANT]` tag)
  are mean-pooled at layer −1 to produce `f_1`. **f_1 is computed
  once per chain** and reused across all turns 2..6.
- For **t ≥ 2**: `s_t` is recorded; `a_{t-1}` is the mean-pool of
  the (t−1)-th assistant response's per-position hidden states at
  layer −1 (already accumulated during the turn-(t−1) decode of
  Pass A, by definition of the iterative build).
- The decoded turn-t assistant response text is recorded for
  annotation in Pass C.

Note: a single forward+decode pass per turn suffices for s_t, f_1
(at t=1 only), and a_{t−1} (for t≥2). No additional forwards.

### Pass B — standalone Q_t representation (turns 2..K)

For each evaluation turn `t ∈ {2, …, 6}`, construct the standalone
chat-template-formatted prompt:

```
[SYS] (default Qwen system prompt or empty)
[USER] {q_t_text}
[ASSISTANT] _
```

No decoding. Single forward pass per turn-t question. Extract:

- `q_t_repr` ∈ R^3584 = last-token hidden state at the position
  immediately before generation would begin, layer −1.

Pass B is run for all 100 × 5 = 500 evaluation turns in the main
set, plus 20 × 5 = 100 in the frame-positive set, plus 10 × 5 = 50
in the calibration set.

### Pass C — severity annotation (turns 2..K, LLM-judge)

For each decoded turn-t assistant response from Pass A, score the
severity of turn-1 framing invocation using a pinned LLM-judge
protocol.

**Pinned judge model:** Qwen/Qwen2.5-72B-Instruct (the same family
as the model under test, but a different parameter count, to
minimize cross-family bias while not making the judge identical to
the subject). Loaded on-demand only during Pass C; if 72B is
infeasible at runtime due to memory budget, the implementation may
fall back to the same model-under-test (Qwen-7B-Instruct) for
self-judging, and that fallback is disclosed in the JSON output
under `judge_fallback_used`. The pinned default is 72B.

**Pinned judge prompt (PINNED, frozen verbatim):**

```
You are evaluating whether a model's response inappropriately re-
invokes a framing convention introduced in an earlier turn of a
conversation. You will be shown:

- The framing convention (a span of text from turn 1).
- The current question (turn t, t >= 2).
- The model's response to that question.

Score the model's response on a 3-level severity scale:

- 0 = IGNORED: the response does not invoke the framing at all.
  The framing convention is absent from the response.
- 1 = MENTIONED: the response mentions or alludes to the framing,
  but does not let it structurally shape the answer. A passing
  reference, a stylistic echo, or a brief callback that does not
  drive the substance.
- 2 = STRUCTURED: the framing structurally shapes the answer. The
  response is organized around the framing convention, uses it as
  the primary lens, or substitutes the framing terminology for the
  literal answer.

Return JSON: {"severity": 0|1|2, "rationale": "<one short sentence>"}.
Do not return any other text.

FRAMING_CONVENTION:
<framing_token_substring>

CURRENT_QUESTION:
<q_t_text>

MODEL_RESPONSE:
<turn_t_response_text>
```

The judge prompt is pinned verbatim; line breaks, capitalization,
ordering, and the JSON-only return format are all part of the seal.

**Pinned judge temperature:** 0.0 (greedy decode for the judge).

**Pinned judge max tokens:** 128 (sufficient for `{"severity": N,
"rationale": "..."}` plus margin).

**Pinned response parsing:** strict JSON parse. If the judge output
fails to parse as JSON or does not contain a `severity` key with
integer value in {0, 1, 2}, the implementation retries once at
temperature 0.0 (deterministic, so identical second call); on second
failure, the row is recorded as `severity = null` and excluded from
the cascade. If more than 5% of evaluation rows yield
`severity = null`, the run exits with `ANNOTATION_FAILED` (Chunk 5
exit-code 9).

**Pinned binary label derivation:**

> y = 1 iff severity ≥ 1 (i.e., framing was at least mentioned).
> y = 0 iff severity == 0 (framing was ignored).

Rationale: "appropriate non-invocation" is the BCVF-faithful
direction; both "mentioned" and "structured" are inappropriate
invocations under the spec's hypothesis (severity differentiates
the *degree* of inappropriateness for diagnostic purposes; the
cascade decision uses binary y to match §15.13 pattern).

(Discussed alternative: y = 1 iff severity == 2 only. Rejected —
mentioning a frame in a turn where it should be irrelevant is
already a release failure under the spec's framing-stickiness
hypothesis; structuring is just a stronger version. Setting the
threshold at severity ≥ 1 makes the test more sensitive without
biasing toward triviality.)

### Pass D — judge-κ self-test gate (calibration chains only)

Before any cascade computation on the main set, the judge is
exercised on the 50 calibration evaluation rows (10 chains × 5
turns), each of which has a pre-curated human-annotated severity
label. The judge's outputs are compared against the human labels;
**Cohen's κ ≥ 0.6 is the gate threshold (PINNED, inclusive).** If
κ < 0.6 on the calibration set, the run exits with
`ANNOTATION_FAILED` (Chunk 5 exit-code 9) without writing any
cascade output.

κ ≥ 0.6 is the canonical "substantial agreement" threshold from the
Landis-Koch convention. (Discussed alternatives: 0.4 "moderate"
threshold, 0.7 "near-strong" threshold. Rejected — 0.4 is too
permissive for a load-bearing automatic-judge protocol; 0.7 is too
strict for a 3-class severity rubric on N=50 with finite human-
annotator noise. 0.6 sits at the convention boundary.)

---

## Computed per-stimulus features

For each chain `chain_idx ∈ {0, …, 99}` and each evaluation turn
`t ∈ {2, …, 6}` (500 rows total in the main set):

```
cos_st_f1            = cos(s_t, f_1)             # alignment of state with turn-1 framing span
cos_st_qt            = cos(s_t, q_t_repr)        # alignment of state with standalone-Q_t
cos_qt_f1            = cos(q_t_repr, f_1)        # baseline topic-overlap with framing
cos_st_aprev         = cos(s_t, a_{t-1})         # state alignment with prior assistant turn

R_framing            = cos_st_f1 - cos_st_qt     # primary signal
R_topic_to_framing   = cos_qt_f1                 # topic-overlap comparator
R_recency            = cos_st_aprev - cos_st_qt  # content-recency comparator (§15.13-flavored)

severity             = <int 0|1|2 from judge>
y                    = severity >= 1             # binary cascade label
```

All cosines computed in fp64 from fp32 cache values; no clipping
required since all inputs are real-valued LM hidden states (no
FFT). For numerical stability, vectors with ‖·‖₂ < 1e-12 are
flagged at extraction time and the run exits with `EXTRACTION_FAILED`
(Chunk 5 exit-code 6); this is not expected to fire on a real
forward pass but the guard mirrors §15.13.

### Aggregate-level computations (after all evaluation rows)

```
auc_framing           = roc_auc_score(y, -R_framing_array)
auc_topic_to_framing  = roc_auc_score(y, -R_topic_to_framing_array)
auc_recency           = roc_auc_score(y, -R_recency_array)

dauc_framing_vs_chance        = auc_framing - 0.5
dauc_framing_vs_topic         = auc_framing - auc_topic_to_framing
dauc_framing_vs_recency       = auc_framing - auc_recency

direction_held = (auc_framing >= 0.5)
```

Note: `R_topic_to_framing` is a raw similarity (not a difference);
the negation `-R_topic_to_framing_array` in `roc_auc_score`
imposes the same direction convention as R_framing for cascade-
comparable AUCs (lower topic overlap should correlate with
appropriate non-invocation if R_topic_to_framing alone explained
the signal).

### Frame-positive disclosure-only computation

On the 100 frame-positive evaluation rows, R_framing is computed
identically. The disclosed quantity is:

```
auc_framing_pos = roc_auc_score(y_pos, R_framing_pos_array)
```

Note the **non-negated** score: on frame-positive items, the human-
annotated y_pos = 1 means appropriate-frame-invocation, so the
hypothesis predicts *higher* R_framing should correlate with
y_pos = 1. A frame-positive AUC near 0.5 (or below) on top of a
strong main-set AUC would invalidate the geometric story —
disclosed for transparency, but does NOT enter the cascade.

### Selective-prediction (disclosure only)

For the pinned alphas `α ∈ {0.35, 0.50, 0.75}`, compute κ@α using
`-R_framing` as the abstention score and `y` as the label.
Eligibility: `n_admitted >= 10` AND conditional accuracy `>= α`.
Same construction as §15.10 / §15.11 / §15.13. **These operating
points are reported in the JSON / MD output for transparency but do
NOT enter the cascade decision.**

---

## Cascade structure

### Pinned thresholds (numerically identical to §15.10 / §15.11 / §15.13)

```
STRONG_AUC_THRESHOLD          = 0.75   # inclusive
STRONG_DELTA_AUC_THRESHOLD    = 0.05   # inclusive (vs chance, vs topic, vs recency)
PARTIAL_AUC_THRESHOLD         = 0.66   # inclusive
DIRECTION_GATE_THRESHOLD      = 0.5    # strict (auc_framing < 0.5 fails)
CHANCE_BASELINE_AUC           = 0.5
```

The threshold values match §15.10 / §15.11 / §15.13 for cross-phase
comparability. The §15.14-specific structural difference is the
**two-comparator strict-margin requirement**: R_framing must beat
*both* R_topic_to_framing and R_recency, not just one comparator
(§15.13 had only one: R_sim).

### Cascade decision (mechanical, in order)

Inputs: `auc_framing`, `auc_topic_to_framing`, `auc_recency`. All
three are `AUC(-R_*, y)` form (higher = better signal in the BCVF-
faithful direction).

**Step 1 — Direction gate (PINNED).**

> If `auc_framing < 0.5` → label = `NO_MATERIAL_SIGNAL_IN_FRAMING`,
> rationale = "wrong-direction failure: BCVF-faithful direction
> (lower R_framing predicts appropriate non-invocation) did not hold
> (auc_framing = X < 0.5)". Skip remaining steps.

This is the §0.8 enforcement of the pinned BCVF-faithful direction.
Failing it on the only benchmark is a hypothesis failure, not a sign-
flip opportunity. Mirrors §15.11 / §15.13.

**Step 2 — STRONG check.**

> If
> - `auc_framing ≥ 0.75` AND
> - `(auc_framing − 0.5) ≥ 0.05` AND
> - `(auc_framing − auc_topic_to_framing) ≥ 0.05` AND
> - `(auc_framing − auc_recency) ≥ 0.05`
>
> → label = `STRONG_SIGNAL_IN_FRAMING`.

The third and fourth conditions are the strict-comparator
requirement: R_framing must beat both the topic-overlap and content-
recency baselines by the cascade margin.

**Step 3 — PARTIAL check.**

> If not STRONG, AND
> - `auc_framing ≥ 0.66` AND
> - `(auc_framing − 0.5) > 0` AND
> - `(auc_framing − auc_topic_to_framing) > 0` AND
> - `(auc_framing − auc_recency) > 0`
>
> → label = `PARTIAL_SIGNAL_IN_FRAMING`.

The second condition is automatically satisfied by `auc_framing ≥
0.66 > 0.5`, but is stated explicitly for symmetry with §15.10 /
§15.11 / §15.13.

**Step 4 — Default.**

> Otherwise → label = `NO_MATERIAL_SIGNAL_IN_FRAMING`.

### What the cascade does NOT consider

- The κ@α selective-prediction operating points (disclosure only).
- The frame-positive AUC `auc_framing_pos` (disclosure only;
  Choice 7 in Chunk 2).
- The response-side variant `auc_framing_response_side` (disclosure
  only; v2 candidate).
- Any per-stimulus diagnostic (R_framing distribution, individual
  cosine values, etc.).
- §15.10 / §15.11 / §15.13 AUCs (different mechanism classes; not
  comparable input).
- Whether `R_topic_to_framing` or `R_recency` themselves clear
  chance — only the *differences* `(auc_framing − auc_topic_to_framing)`
  and `(auc_framing − auc_recency)` matter for the strict-comparator
  step.
- Per-source breakdowns (TruthfulQA-MC vs HumanEval); reported in
  the markdown but not part of the cascade decision.

### Pinned self-test boundary cases (12 cases)

Each entry: `(auc_framing, auc_topic_to_framing, auc_recency,
expected_label)`. The implementation script must pass all 12 at the
self-test gate before any data inspection.

| #   | auc_framing | auc_topic | auc_recency | rationale                                                              | expected                       |
|-----|-------------|-----------|-------------|------------------------------------------------------------------------|--------------------------------|
|  1  | 0.80        | 0.65      | 0.65        | STRONG clean (clears all 4 conditions)                                 | STRONG_SIGNAL_IN_FRAMING       |
|  2  | 0.75        | 0.70      | 0.70        | STRONG boundary at AUC=0.75 + ΔAUC=0.05 inclusive on both comparators  | STRONG_SIGNAL_IN_FRAMING       |
|  3  | 0.78        | 0.20      | 0.20        | STRONG well above both comparators                                     | STRONG_SIGNAL_IN_FRAMING       |
|  4  | 0.74        | 0.65      | 0.65        | PARTIAL via AUC just below 0.75; ΔAUC vs both =0.09>0                  | PARTIAL_SIGNAL_IN_FRAMING      |
|  5  | 0.78        | 0.74      | 0.65        | PARTIAL via ΔAUC vs topic =0.04<0.05 but >0; passes vs recency         | PARTIAL_SIGNAL_IN_FRAMING      |
|  6  | 0.78        | 0.65      | 0.74        | PARTIAL via ΔAUC vs recency =0.04<0.05 but >0; passes vs topic         | PARTIAL_SIGNAL_IN_FRAMING      |
|  7  | 0.66        | 0.65      | 0.65        | PARTIAL boundary at AUC=0.66 inclusive; ΔAUC vs both =0.01>0           | PARTIAL_SIGNAL_IN_FRAMING      |
|  8  | 0.65        | 0.50      | 0.50        | NO_MATERIAL: AUC < 0.66                                                | NO_MATERIAL_SIGNAL_IN_FRAMING  |
|  9  | 0.70        | 0.70      | 0.50        | NO_MATERIAL: ΔAUC vs topic = 0 strictly (not > 0)                      | NO_MATERIAL_SIGNAL_IN_FRAMING  |
| 10  | 0.70        | 0.50      | 0.72        | NO_MATERIAL: ΔAUC vs recency < 0 (R_framing worse than recency)        | NO_MATERIAL_SIGNAL_IN_FRAMING  |
| 11  | 0.50        | 0.30      | 0.30        | NO_MATERIAL: direction gate inclusive at 0.5; AUC<0.66                 | NO_MATERIAL_SIGNAL_IN_FRAMING  |
| 12  | 0.49        | 0.65      | 0.65        | NO_MATERIAL: direction gate strict (auc_framing<0.5)                   | NO_MATERIAL_SIGNAL_IN_FRAMING  |

Coverage rationale:

- Cases 1–3: STRONG band entries (clean, boundary inclusive at
  AUC=0.75 + ΔAUC=0.05 on *both* comparators, well-separated).
- Cases 4–7: PARTIAL band entries (AUC just-below-STRONG; one-
  sided ΔAUC just-below-STRONG on topic; one-sided ΔAUC just-below-
  STRONG on recency; AUC=0.66 boundary inclusive with both ΔAUCs
  positive).
- Cases 8–10: NO_MATERIAL via cascade-condition failure (AUC<0.66;
  ΔAUC topic =0 strictly; ΔAUC recency<0).
- Cases 11–12: NO_MATERIAL via direction-gate failure (inclusive
  at 0.5; strict below 0.5).

The 12 cases are pinned numerically identical at the boundary-
inclusive thresholds. The implementation script must encode this
table verbatim and the self-test gate must pass all 12 before any
data inspection.

---

## Output schema

### `docs/experiments/probe_framing_15_14.json` (`schema_version = "15.14"`)

Top-level keys (alphabetical for `sort_keys=True` parity with §15.10
/ §15.11 / §15.12 / §15.13):

```
{
  "annotation_protocol": {
    "judge_model_id": "Qwen/Qwen2.5-72B-Instruct",
    "judge_prompt_sha256": "<hex sha256 of the pinned judge prompt>",
    "judge_temperature": 0.0,
    "judge_max_tokens": 128,
    "calibration_kappa": <float>,
    "calibration_kappa_threshold": 0.6,
    "calibration_n_rows": 50,
    "annotation_failure_rate": <float>,
    "annotation_failure_rate_threshold": 0.05
  },
  "benchmark": "sticky_framing_15_14_composite",
  "cascade_thresholds": {
    "strong_auc": 0.75,
    "strong_delta_auc": 0.05,
    "partial_auc": 0.66,
    "direction_gate_threshold": 0.5,
    "chance_baseline_auc": 0.5
  },
  "cascade_verdict": {
    "label": "<STRONG|PARTIAL|NO_MATERIAL>_SIGNAL_IN_FRAMING",
    "auc_framing": <float>,
    "auc_topic_to_framing": <float>,
    "auc_recency": <float>,
    "dauc_vs_chance": <float>,
    "dauc_vs_topic_to_framing": <float>,
    "dauc_vs_recency": <float>,
    "direction_held": <bool>,
    "rationale": "<formatted prose>"
  },
  "cross_phase_disclosure": {
    "phase_1_§15_10_verdict": "PARTIAL_SIGNAL_IN_Z",
    "phase_2_§15_11_verdict": "NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE",
    "phase_3_§15_12_status": "sealed (closure outcome)",
    "phase_4_§15_13_verdict": "NO_MATERIAL_SIGNAL_IN_INERTIA",
    "this_phase_modifies": "none"
  },
  "extraction_config": {
    "layer_idx": -1,
    "hidden_dim": 3584,
    "max_new_tokens": 64,
    "decode_temperature": 0.0,
    "f_1_pooling": "mean_over_framing_token_positions_layer_minus_1_full_context_pass",
    "s_t_extraction": "last_token_pre_decode_at_t_th_assistant_tag_full_context",
    "q_t_extraction": "last_token_pre_decode_standalone_with_chat_template",
    "a_prev_pooling": "mean_over_decoded_assistant_tokens_layer_minus_1_full_context_pass",
    "k_turns": 6
  },
  "frame_positive_disclosure": {
    "n_frame_positive_chains": 20,
    "n_frame_positive_rows": 100,
    "auc_framing_pos": <float>,
    "auc_framing_pos_direction_consistent": <bool>,
    "note": "Disclosure-only sign-consistency cross-check; NOT a cascade input."
  },
  "judge_fallback_used": <bool>,
  "n_chains": 100,
  "n_evaluation_rows": 500,
  "pairing_rule": "K=6 chains; turn-1 = framing_pool[(i*7) mod 25]; turns 2..6 = curated_chain_questions[i] under topical-disjointness rule",
  "phase_5_eligible_outcomes": [
    "STRONG_SIGNAL_IN_FRAMING",
    "PARTIAL_SIGNAL_IN_FRAMING",
    "NO_MATERIAL_SIGNAL_IN_FRAMING"
  ],
  "probe_result": {
    "n_evaluation_rows": 500,
    "n_severity_zero": <int>,
    "n_severity_one": <int>,
    "n_severity_two": <int>,
    "n_severity_null": <int>,
    "n_y_one": <int>,
    "n_y_zero": <int>,
    "auc_framing": <float>,
    "auc_topic_to_framing": <float>,
    "auc_recency": <float>,
    "dauc_framing_vs_chance": <float>,
    "dauc_framing_vs_topic_to_framing": <float>,
    "dauc_framing_vs_recency": <float>,
    "auc_framing_response_side_disclosure": <float>,
    "direction_held": <bool>,
    "r_framing_per_row": [<500 floats>],
    "r_topic_to_framing_per_row": [<500 floats>],
    "r_recency_per_row": [<500 floats>],
    "severity_per_row": [<500 ints in {0,1,2} or null>],
    "y_per_row": [<500 bools>],
    "chain_idx_per_row": [<500 ints>],
    "turn_idx_per_row": [<500 ints in {2..6}>],
    "source_per_row": [<500 strings in {"truthfulqa_mc","humaneval"}>],
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
  "schema_version": "15.14",
  "stimulus_json_sha256": "<hex sha256 of sticky_framing_15_14_stimuli.json>"
}
```

PINNED. No additional keys; no key removal.

### `docs/experiments/framing_15_14_extractions.npz` (cache file)

Per-evaluation-row arrays + per-chain arrays for `--probe-only`
re-runs:

Per-chain arrays (shape (100,) for the main set; analogous shapes
for the 20-chain frame-positive and 10-chain calibration sets):

```
chain_idx           int64,   shape (100,)
frame_id            object,  shape (100,)        # variable-length string
f_1                 float32, shape (100, 3584)   # one f_1 per chain (computed at t=1)
turn_1_response     object,  shape (100,)        # decoded turn-1 assistant text
framing_token_ids   object,  shape (100,)        # variable-length int array per chain
```

Per-evaluation-row arrays (shape (500,) for the main set):

```
row_idx             int64,   shape (500,)
chain_idx_per_row   int64,   shape (500,)
turn_idx_per_row    int64,   shape (500,)        # values in {2,3,4,5,6}
source_per_row      object,  shape (500,)        # "truthfulqa_mc" or "humaneval"
q_t_idx             int64,   shape (500,)        # benchmark-internal index
s_t                 float32, shape (500, 3584)
q_t_repr            float32, shape (500, 3584)
a_prev              float32, shape (500, 3584)
r_t_response_pool   float32, shape (500, 3584)   # for response-side disclosure variant
turn_t_response     object,  shape (500,)        # variable-length string
severity            int8,    shape (500,)        # values in {0,1,2}; -1 sentinel for null
y                   bool,    shape (500,)
```

Approximate size per main-set chain: ~1 × 3584 × 4 bytes (f_1) +
5 × 4 × 3584 × 4 bytes (s_t, q_t_repr, a_prev, r_t_response_pool) ≈
300 KB. Total across 100 chains: ~30 MB + text overhead +
analogous frame-positive (~6 MB) + calibration (~3 MB) ≈ ~40 MB.

### `docs/experiments/probe_framing_15_14.md`

8-section markdown report (mirrors §15.11 / §15.13 structure):

1. Header + schema/model/extraction/judge config one-liner.
2. Cascade verdict (label, rationale, AUC table with chance + topic
   + recency baselines, direction-held flag).
3. Probe details (n_evaluation_rows, severity histogram, y balance,
   AUC, ΔAUC vs all 3 baselines, per-source breakdown disclosure-
   only).
4. Annotation protocol details (judge model, judge prompt SHA-256,
   calibration κ, judge fallback flag, annotation-failure rate).
5. Frame-positive disclosure-only block (auc_framing_pos, sign-
   consistency note).
6. Selective-prediction operating points table (disclosure only).
7. Pinned configuration block (formula, K=6 pairing rule,
   extraction protocol, cascade thresholds, direction convention,
   firewall pattern count).
8. Caveats (§0.8-disclosed; carries forward §15.10 / §15.11 /
   §15.13 caveats by §-reference; §15.14-specific caveats listed
   inline) + Cross-phase comparison table + Audit-trail integrity
   block.

---

## Class-3 firewall patterns (52 total)

The firewall scans rendered markdown for forbidden override-language
before write. Each pattern is matched case-insensitively for non-§
patterns and case-sensitively / literal for §-anchored patterns
(preserves precise §-numbering). Detection → exit code 4
(`INTERPRETATION_VIOLATION`) without writing.

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

### Inherited from §15.13 (8 patterns)

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

### §15.14-specific (8 patterns)

```
"actually STRONG_SIGNAL_IN_FRAMING despite"
"should be STRONG_SIGNAL_IN_FRAMING"
"actually PARTIAL_SIGNAL_IN_FRAMING despite"
"should be classified as PARTIAL_SIGNAL_IN_FRAMING"
"the R_topic_to_framing comparator should be ignored"
"the R_recency comparator should be ignored"
"the κ self-test gate was inappropriate"
"§15.13 NO_MATERIAL_SIGNAL_IN_INERTIA is overturned"
```

**Total: 52 patterns** (44 inherited + 8 §15.14-specific). PINNED.
The implementation script must include all 52; the self-test gate
must verify each is flagged on a positive sample and that clean
§15.14-style text produces zero false positives.

---

## Implementation chunk plan

The implementation should follow the established §15.10 / §15.11 /
§15.13 chunked pattern: each chunk a separate commit, each with its
own verification step.

### Recommended file path

```
scripts/probe_framing_15_14.py
```

### Chunked plan

| Chunk | Content | Approximate size |
|-------|---------|------------------|
| **I-1** | Module docstring (embedded §0.8 declaration), pinned constants block (matching this spec exactly), pinned judge prompt as a frozen string constant, dataclasses (`FramingPoolItem`, `ChainQuestion`, `StimulusChain`, `ChainExtraction`, `EvaluationRow`, `FramingFeatures`, `FramingProbeResult`, `FramingCascadeVerdict`, `FramingAuditOutputs`), 12 self-test cascade boundary cases. | ~450 lines |
| **I-2** | `SchemaMismatchError`, `_validate_stimulus_json` (schema check + topical-disjointness rule re-check), stimulus JSON loader, `_load_truthfulqa_questions`, `_load_humaneval_questions` (HuggingFace fallbacks for question text + gold), lazy torch+transformers import, `extract_chain_pass_a_iterative` (iterative K-turn forward+decode with f_1 + s_t + a_prev extraction), `extract_pass_b_standalone` (standalone Q_t forward), `save/load_extractions_cache`. | ~500 lines |
| **I-3** | `_lazy_import_judge` (loads Qwen-72B or fallback), `run_judge_pass_c` (LLM-judge severity protocol with retry + JSON-parse + null handling + annotation_failure_rate gate), `compute_calibration_kappa` (Cohen's κ on calibration set), `_self_test_kappa_gate` (κ ≥ 0.6 self-test), `compute_features_per_row` (R_framing + R_topic_to_framing + R_recency + response-side disclosure + cosine extracts), `_lazy_import_sklearn`, `_selective_kappa_at_alpha` (matches §15.11/§15.13), `run_framing_probe` (full per-run pipeline), `classify_cascade_framing` (4-step cascade with direction gate + 2-comparator STRONG/PARTIAL). | ~450 lines |
| **I-4a** | `scan_for_forbidden_patterns` (case-insensitive non-§; literal §-anchored), `enforce_firewall_or_exit` (exits 4 with diagnostic). | ~60 lines |
| **I-4b** | Self-test gate: `_self_test_cascade` (12 cases), `_self_test_cosine_invariants` (cosine identity + symmetry on synthetic data), `_self_test_firewall` (52-pattern coverage + clean negative), `_self_test_topical_disjointness` (synthetic stimulus pair + violation), `run_self_test` (orchestrates 4 sub-tests, returns 0/3). | ~200 lines |
| **I-4c** | JSON output writer: `_dataclass_to_dict` helpers, `write_json_output` with full schema_version "15.14" payload (alphabetical sort_keys=True). | ~150 lines |
| **I-4d** | Markdown rendering: `render_markdown_report` (8 sections per spec), `write_markdown_output` (firewall-scanned before write), `_format_operating_points_table`, `_format_per_source_breakdown_table`. | ~300 lines |
| **I-5** | `_run_collect` (orchestrates Pass A + Pass B for all 130 chains with shared model load), `_run_annotate` (orchestrates Pass C + Pass D κ gate), `_run_probe` (computes features + cascade), `_print_verdict_banner`, `_build_argparser`, `main(argv)` (CLI: `--self-test` / `--collect` / `--annotate` / `--probe` / default). | ~300 lines |

**Total: ~2410 lines** (somewhat larger than `probe_inertia_15_13.py`,
reflecting the LLM-judge protocol + κ gate + multi-turn pipeline).

### Exit codes (PINNED)

```
0  success
2  CLI / argument error (handled by argparse)
3  SELF_TEST_FAILED
4  INTERPRETATION_VIOLATION
5  SCHEMA_MISMATCH (stimulus JSON or cache)
6  EXTRACTION_FAILED (torch / transformers stack)
7  PROBE_FAILED (sklearn / NaN in features)
8  STIMULUS_INVALID (topical-disjointness rule violated; framing span out of range)
9  ANNOTATION_FAILED (judge κ < 0.6 OR judge JSON-parse failure rate > 5%)
```

Exit codes 8 and 9 are §15.14-specific:

- **Exit 8 (`STIMULUS_INVALID`)**: the stimulus JSON failed the
  topical-disjointness rule re-check at runtime, or a
  `framing_token_char_span` does not map cleanly to tokenizer token
  positions, or a `framing_pool` item is missing required fields.
  Distinct from `SCHEMA_MISMATCH` (5), which covers structural JSON
  shape errors.
- **Exit 9 (`ANNOTATION_FAILED`)**: the LLM-judge protocol failed
  the κ ≥ 0.6 calibration gate, or the JSON-parse failure rate on
  judge outputs exceeded 5%. Either failure is a load-bearing
  protocol failure that invalidates the binary y labels; the
  cascade is not computed and no JSON/MD is written.

### CLI modes (PINNED)

```
--self-test     : run gate only (12 cascade + cosine invariants + 52-pattern firewall + topical-disjointness)
--collect       : load stimulus JSON + run Pass A (multi-turn) + Pass B (standalone) for all chains; write extraction cache
--annotate      : load extraction cache + run Pass C (LLM-judge severity) + Pass D (κ self-test gate); write annotated cache
--probe         : load annotated cache + compute features + cascade + write JSON+MD outputs
(default)       : self-test → collect (or load cache) → annotate (or load annotated cache) → probe → write
--stimulus-json : override default stimulus-JSON path
--cache-path    : override default extraction cache path
--annotated-cache-path : override default annotated cache path
--json-out      : override default JSON output path
--md-out        : override default markdown output path
--force-collect : force re-collection even if cache exists
--force-annotate: force re-annotation even if annotated cache exists
--judge-fallback: explicitly force the Qwen-7B fallback judge (default: try 72B first, fall back if OOM)
```

The `--collect` / `--annotate` / `--probe` split reflects the
substantial wall-time cost of each phase (collect dominates GPU
time; annotate dominates judge-model time; probe is CPU-only) and
allows resume-on-failure at a coarser granularity than §15.13's
two-stage `--extract-only` / `--probe-only` split.

---

## Cost / timeline

### Sandbox + design work

- Spec writing (this document): done in 6 chunks.
- Stimulus-JSON curation: separate sub-task that must precede
  implementation; ~1 working session for hand-authoring 25
  framing-pool items + 130 chain-question lists + 50 calibration-
  row human severity labels. The stimulus JSON's SHA-256 is locked
  before the implementation §0.X is sealed.
- Implementation chunks I-1 through I-5: estimated ~10 commits,
  similar pace to §15.13 implementation. ~1.5 working sessions
  including verification between chunks.

### Runpod execution

- Per chain (Pass A): K=6 forward+decode iterations × ~64 tokens
  per decode = ~384 generated tokens per chain.
- Per chain (Pass B): 5 standalone forward passes (no decode).
- Total Pass A: 130 × 6 ≈ 780 forward+decodes; ≈ 50,000 token-
  generations.
- Total Pass B: 130 × 5 = 650 standalone forwards.
- Total Pass C: 650 LLM-judge calls (main + frame-positive +
  calibration combined: 500 + 100 + 50 = 650).

Wall time on a single 24GB GPU (Qwen-7B subject; no judge):
~30–40 min for Pass A + Pass B.

Wall time for Pass C with Qwen-72B judge: significantly larger;
~1.5–2.5 hours on an 80GB GPU. With Qwen-7B fallback judge: ~20–30
min on the 24GB GPU.

**Total wall time** (Qwen-72B judge): ~2.5–3 hours runpod time
end-to-end. (Qwen-7B fallback judge): ~1 hour. Both are larger
than §15.13's ~20-min runtime; the multi-turn + judge structure is
the dominant cost.

### Disk footprint

- Extraction cache: ~40 MB (main + frame-positive + calibration).
- Annotated cache: ~40 MB + small annotation overhead.
- JSON output: ~25 KB.
- Markdown output: ~10 KB.
- Total new artifacts on disk: ~80 MB committable cache, plus
  ~35 KB committable documentation. Cache size is ~7× §15.13's;
  the 5× row count (500 vs. 100) plus the 4-array-per-row schema
  account for the increase.

---

## Risks and mitigations

### Risk 1 — LLM-judge model availability / drift

The pinned judge (Qwen/Qwen2.5-72B-Instruct) may be unavailable at
runtime due to memory budget, model-hub access, or HuggingFace API
changes. A judge swap mid-run would break severity-label
comparability across rows.

**Mitigation:** the implementation pins a single fallback (Qwen-7B-
Instruct as self-judge), and `judge_fallback_used` is recorded in
the JSON output. The κ self-test gate (Pass D) is run regardless of
which judge is used, so the substantive falsifiability of the y
labels is guaranteed by the κ ≥ 0.6 threshold rather than by a
specific judge identity. If both 72B and 7B fall below κ = 0.6, the
run exits 9 (`ANNOTATION_FAILED`) without writing cascade output.

### Risk 2 — Framing-span hand-annotation noise

The `framing_token_char_span` is hand-annotated at curation time.
Different annotators may pick slightly different boundaries (e.g.,
including or excluding a determiner), and f_1's pooled value
depends on which token positions are included.

**Mitigation:** stimulus-curation discipline pins the span per item
before extraction; the curated JSON is locked by SHA-256 in the
output. The 12 self-test cascade cases use synthetic AUC pairs
(not real f_1 vectors), so annotation noise does not affect self-
test gate behavior. v2 candidate: dual-annotator + Cohen's κ on
spans themselves.

### Risk 3 — Topical-disjointness rule too strict

The non-stopword token-overlap rule may deplete the candidate
turn-2..K pool below what's needed to fill 130 chains × 5 turns =
650 distinct technical questions across TruthfulQA-MC + HumanEval.

**Mitigation:** TruthfulQA-MC validation has 817 items;
HumanEval test has 164 items; combined pool ≈ 981. With 25
framing-pool items, the worst-case rejection rate would have to
exceed ~33% to deplete below 650. Curation-time monitoring of the
rejection rate per framing-pool item is recommended; if depletion
is observed during curation, the framing-pool item is reworded to
narrow its non-stopword token set rather than relaxing the rule.
The rule itself stays pinned.

### Risk 4 — Per-chain f_1 reuse across turns 2..6

f_1 is computed once per chain (at t=1's forward pass) and reused
for all evaluation turns 2..6. In principle, the f_1 *hidden state*
at the framing-span positions could drift as the multi-turn context
accumulates around it. A fixed f_1 from t=1 may be a less accurate
representation of "the model's current framing-span representation"
at turn 5 or 6 than at turn 2.

**Mitigation:** acceptable per §0.8. The pinned f_1 is "the
framing-span representation at the moment the model first
encountered it," which is the cleaner geometric object — the
hypothesis is that *this* representation is what the model's later-
turn state is sticky toward. Recomputing f_1 at each turn would
introduce a hyperparameter (which forward pass to source f_1 from)
and break parity with §15.13's pinning of r_A from a single source.
v2 candidate: a `R_framing_dynamic` variant that recomputes f_1 per
turn, disclosed as a v2 cross-check.

### Risk 5 — Direction-gate failure (auc_framing < 0.5)

§15.11 saw direction-gate failure on both benchmarks. §15.13 held
direction (auc_inertia = 0.6300). §15.14 may go either way.

**Mitigation:** acceptable per §0.8. NO_MATERIAL_SIGNAL_IN_FRAMING
via direction gate is a valid verdict. The pinned hypothesis was
the specific BCVF-faithful direction; failing it is a hypothesis
failure, not a sign-flip opportunity. Mirrors §15.11 / §15.13.

### Risk 6 — Cost / wall-time blow-up

End-to-end runtime estimated at 2.5–3 hours with the Qwen-72B
judge. If the runpod budget is constrained, the implementation
session may time out partway through Pass C, leaving the cascade
uncomputed.

**Mitigation:** the `--collect` / `--annotate` / `--probe` CLI
split allows resume-on-failure at coarse granularity. The
extraction cache is written after Pass A + Pass B and re-read by
`--annotate`; the annotated cache is written after Pass C and re-
read by `--probe`. A failed annotation pass does not require re-
running Pass A. Disclose realistic wall-time bounds before
authorizing the implementation §0.X.

### Risk 7 — Frame-positive set size N_pos = 20

The frame-positive set is small (20 chains × 5 turns = 100 rows).
A sign-consistency cross-check at this N has high variance; a
spurious low auc_framing_pos could occur even if the main-set
result is genuine.

**Mitigation:** disclosure-only. The frame-positive AUC is
reported but does NOT enter the cascade decision; its role is
qualitative cross-check, not quantitative gate. Pinning N_pos = 20
balances curation cost against the cross-check's interpretability.
v2 candidate: N_pos ≥ 50 in a follow-up.

### Risk 8 — Severity-rubric noise on K=6 chains

Severity scoring at turn 5 or turn 6 may be noisier than at turn 2:
the model has more accumulated context, and the judge has to factor
in turns 2..t−1 to decide whether framing-mention is appropriate
under "this question is technically unrelated." The judge prompt
shows only turn t's question and response, not the intermediate
turns; the per-turn judgement is local.

**Mitigation:** the κ self-test gate operates over all 50
calibration rows including late-turn rows, so the gate captures
whether the judge can score reliably across all turn indices. Per-
turn AUC breakdowns are reported in the markdown for diagnostic
transparency but do NOT enter the cascade. v2 candidate: per-turn-
index cascades as a follow-up.

### Risk 9 — Stimulus-JSON dependency lock

The stimulus JSON is a curation-time artifact whose SHA-256 is
recorded in the output. If the curation is partially redone after
the implementation §0.X is sealed, the JSON's SHA-256 changes and
the cascade output is no longer comparable to any earlier run on
the same JSON.

**Mitigation:** the implementing §0.X seals the stimulus JSON SHA-
256 alongside the implementation script; any change to the
stimulus JSON requires a fresh §0.X (e.g., §15.14b). The
discipline mirrors §13.10's `probe_semantic_entropy.json` lock.

---

## Sealed §0.8-binding decisions

The following decisions cannot be modified during implementation
without a fresh §0.8 amendment to this spec:

### Frozen parameters

| Decision | Pinned value |
|---|---|
| SCHEMA_VERSION | "15.14" |
| QWEN_MODEL_ID (subject) | "Qwen/Qwen2.5-7B-Instruct" |
| JUDGE_MODEL_ID (default) | "Qwen/Qwen2.5-72B-Instruct" |
| JUDGE_MODEL_ID (fallback) | "meta-llama/Llama-3.1-8B-Instruct" (effective under §15.14-A2; was "Qwen/Qwen2.5-7B-Instruct" pre-A2) |
| BENCHMARK | "sticky_framing_15_14_composite" (TruthfulQA-MC + HumanEval pooled, single composite in §15.x sense) |
| K_TURNS | 6 |
| N_MAIN_CHAINS | 100 |
| N_FRAME_POSITIVE_CHAINS | 20 |
| N_CALIBRATION_CHAINS | 10 |
| N_FRAMING_POOL_ITEMS | 25 |
| EVALUATION_ROWS_MAIN | 500 (= 100 × 5) |
| PAIRING_RULE | "turn_1 = framing_pool[(i*7) mod 25]; turns 2..6 from curated chain_questions[i] under topical-disjointness rule" |
| TOPICAL_DISJOINTNESS_RULE | non-stopword token-set disjointness between framing-span tokens and turn-2..K question tokens |
| STOPWORD_LIST_SIZE | 24 (pinned list in Chunk 3) |
| SOURCE_ENUM (main_chains) | `{"truthfulqa_mc", "humaneval"}` (effective under §15.14-A1) |
| SOURCE_ENUM (calibration_chains) | `{"truthfulqa_mc", "humaneval"}` (effective under §15.14-A1) |
| SOURCE_ENUM (frame_positive_chains) | `{"truthfulqa_mc", "humaneval", "synthetic_frame_positive_v1"}` (effective under §15.14-A1) |
| PROMPT_FORMAT | Qwen chat template via `apply_chat_template` |
| MAX_NEW_TOKENS (subject) | 64 |
| MAX_NEW_TOKENS (judge) | 128 |
| DECODE_TEMPERATURE (subject) | 0.0 (greedy) |
| DECODE_TEMPERATURE (judge) | 0.0 (greedy) |
| LAYER_IDX | -1 (final layer only) |
| HIDDEN_DIM | 3584 |
| f_1 pooling | mean over framing-span token positions, layer −1, full-context turn-1 forward pass |
| s_t extraction | last-token, layer −1, pre-decode at t-th `[ASSISTANT]` tag, full-context multi-turn pass |
| q_t extraction | last-token, layer −1, standalone with chat template, no history |
| a_{t-1} pooling | mean over decoded turn-(t−1) assistant token positions, layer −1, full-context pass |
| Direction convention | lower R_framing predicts appropriate non-invocation (BCVF-faithful) |
| STRONG_AUC_THRESHOLD | 0.75 (inclusive) |
| STRONG_DELTA_AUC_THRESHOLD | 0.05 (inclusive, vs chance, vs R_topic_to_framing, vs R_recency) |
| PARTIAL_AUC_THRESHOLD | 0.66 (inclusive) |
| DIRECTION_GATE_THRESHOLD | 0.5 (strict) |
| ALPHA_TARGETS | (0.35, 0.50, 0.75) |
| ALPHA_PRIMARY | 0.50 |
| N_MIN | 10 (selective-prediction floor) |
| SEVERITY_RUBRIC | 3-level (0=ignored, 1=mentioned, 2=structured) |
| BINARY_LABEL_THRESHOLD | y=1 iff severity ≥ 1 |
| KAPPA_GATE_THRESHOLD | 0.6 (inclusive, calibration κ) |
| ANNOTATION_FAILURE_RATE_THRESHOLD | 0.05 (5% max judge JSON-parse failure) |
| Class-3 firewall pattern count | 52 (44 inherited + 8 §15.14-specific) |
| Number of self-test cascade cases | 12 |

### Frozen artifacts

| Artifact | Path |
|---|---|
| Implementation script | `scripts/probe_framing_15_14.py` |
| Stimulus JSON (curation-time) | `docs/experiments/sticky_framing_15_14_stimuli.json` |
| Extraction cache | `docs/experiments/framing_15_14_extractions.npz` |
| Annotated cache | `docs/experiments/framing_15_14_annotated.npz` |
| JSON output | `docs/experiments/probe_framing_15_14.json` |
| Markdown output | `docs/experiments/probe_framing_15_14.md` |

### Frozen behaviors

- No combination with §15.13's R_inertia, with H1 (state coherence),
  or with H2 (intent competition). No R_total.
- No bootstrap CI on AUCs in v1.
- No second technical-question benchmark beyond TruthfulQA-MC +
  HumanEval composite in v1.
- No probe training; R_framing is a pure feature.
- No sign-flip rescue if direction gate fails.
- No frame-positive AUC in the cascade (disclosure only).
- No response-side variant in the cascade (disclosure only; v2
  candidate).
- No pivot-architecture variants in v1 (v2 candidate).
- No retroactive amendment to any §13/§14/§15.x verdict-of-record,
  including §15.13's NO_MATERIAL_SIGNAL_IN_INERTIA.

### Frozen judge protocol

- Judge prompt: pinned verbatim in Chunk 3; SHA-256 recorded in
  output JSON.
- Judge temperature: 0.0.
- Judge max tokens: 128.
- Judge fallback: Qwen-7B self-judge if 72B unavailable; usage
  recorded in `judge_fallback_used` flag.
- κ gate: Cohen's κ ≥ 0.6 on 50 calibration rows; failure → exit 9.
- JSON-parse failure rate: ≤ 5% on judge outputs; failure → exit 9.
- Annotation retry policy: one retry on JSON-parse failure (same
  temperature 0.0); second failure → severity = null for that row.

---

## Notes for the implementing session

If you are picking this up cold:

1. **Start with this spec end-to-end.** Read all 6 sections before
   writing any code. The spec is self-contained — you should not
   need to consult the prior conversation, the §15.13 spec, or the
   main BCVF design doc beyond cross-referencing pinned thresholds.

2. **Curate the stimulus JSON before implementation.** The 130
   chains (25 framing-pool + 100 main + 20 frame-positive + 10
   calibration) are a precondition. Hand-author framing items;
   draw turn-2..K candidates from TruthfulQA-MC + HumanEval; apply
   the topical-disjointness rule; hand-annotate severity on the
   50 calibration rows. SHA-256 the JSON before sealing the
   implementation §0.X.

3. **Mirror §15.10 / §15.11 / §15.13 patterns where possible.** The
   script structure (lazy imports, schema validation, cache .npz
   I/O, self-test gate, firewall, JSON+MD writers, CLI modes) maps
   closely to those scripts. Reuse the patterns; don't reinvent.
   The new pieces are: K-turn iterative extraction in Pass A, the
   LLM-judge protocol in Pass C, and the κ self-test gate in Pass D.

4. **Run the self-test gate before any data inspection.** All 12
   cascade cases + cosine invariants + 52-pattern firewall +
   topical-disjointness re-check must pass. Exit 3 on failure.

5. **Pre-commit cascade thresholds before looking at any AUC
   numbers.** §0.8 discipline. The thresholds are pinned in this
   spec; the implementation must apply them mechanically.

6. **Run the κ calibration gate before computing any cascade
   output.** The 50 calibration rows are a load-bearing
   precondition. If κ < 0.6, exit 9 without writing cascade
   output. The cascade is never computed on unreliable y labels.

7. **Output is firewall-scanned before write.** The 52-pattern
   firewall is the last gate before any markdown lands on disk.
   `INTERPRETATION_VIOLATION` exits 4 without writing.

8. **The result is whatever it is.** STRONG, PARTIAL, or
   NO_MATERIAL — each is a valid §0.8-binding readout. NO_MATERIAL
   via direction-gate failure is one possible outcome; NO_MATERIAL
   via κ-gate failure (exit 9) is a different one and means the
   v1 design did not produce a comparable y signal at all. Do NOT
   modify the cascade rule, the direction convention, the κ
   threshold, or the comparator requirements based on what the
   data shows.

9. **After the runpod run produces JSON+MD artifacts**, verify
   firewall compliance and cascade re-derivation locally before
   committing (mirrors the §15.10 / §15.11 / §15.13 verification
   pattern).

10. **§15.13's NO_MATERIAL on R_inertia is unaffected by §15.14's
    outcome.** Per the §15.13 ledger, this is a fresh top-level
    §0.X testing a different mechanism class within the same
    multi-turn dynamics column. R_recency is used here only as a
    firewall comparator, not as a re-test of §15.13's hypothesis.
    No retroactive reclassification of any §15.x verdict.

### Optional v2 follow-ups (NOT authorized by this spec)

If v1 shows signal (PARTIAL or STRONG), the following v2 directions
are candidates for a fresh §0.X commitment — none of them are
authorized here:

- **Pivot-architecture variant**: explicit Segment A (induce) →
  Segment B (reinforce) → Segment C (pivot) → Segment D (probe)
  stimuli, with multiple pivot types (hard reset, topic pivot,
  instruction override, partial carryover) and a Pivot Release
  Accuracy headline metric.
- **Frame-category breakdown**: per-category cascades for
  metaphor / persona / terminology / formatting framing classes.
- **Difficulty-ladder variant**: levels 1–4 (obvious pivot →
  adversarial pivot) as the structural axis.
- **Frame-positive AUC as cascade input**: require a 3rd strict-
  margin constraint that auc_framing_pos clears chance.
- **Response-side classifier**: `R_framing_response_side =
  cos(r_t, f_1) − cos(r_t, p_t)` as a cascade input; comparison
  against state-side R_framing tests "geometry foretells the
  response."
- **R_framing_dynamic**: f_1 recomputed per turn from the full-
  context pass at that turn, rather than reused from t=1.
- **Cross-model replication**: same stimuli + cascade applied to
  Llama-3-8B-Instruct or Mistral-7B-Instruct.
- **N=200 / N=500 statistical-power upgrade**.
- **Hand-curated dual-annotator stimulus JSON with span κ ≥ 0.7.**
- **HaluEval cross-benchmark replication** (parity with §15.13's
  v2 candidate).
- **H1 (state coherence) or H2 (intent competition) tested in
  isolation** within the multi-turn dynamics column.

Each of these is a separate top-level §0.X, not a §15.14 amendment.

---

## End of spec

This document, sealed §0.8-binding, defines §15.14 in full. Any
implementation that follows it without deviation is a valid §15.14
run. Any deviation requires a fresh amendment to this document.

The result is whatever the data shows — STRONG, PARTIAL, or
NO_MATERIAL (via cascade-condition failure, direction-gate failure,
or annotation-gate failure). The cascade rule is mechanical. The
verdict is binding regardless of post-hoc interpretation.

§13.9 hold preserved. §6.1 N=21 autonomy result preserved. §15.10
PARTIAL_SIGNAL_IN_Z preserved. §15.11
NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE preserved. §15.12 closure
preserved. §15.13 NO_MATERIAL_SIGNAL_IN_INERTIA preserved. §15.14
result is independent of all of these.
