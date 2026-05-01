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

### §15.14-A4 — judge severity extraction: logit-based first-token argmax (replaces generation-and-parse)

**Status:** EFFECTIVE per user sign-off recorded in the commit that
flipped this status field (the immediate predecessor of this
document version on branch `claude/sticky-framing-spec-r6U1j`).

**Scope:** the judge severity-extraction code path in
`scripts/probe_framing_15_14.py`. Specifically:
`_judge_one_row` body (replaces `model.generate(...)` + parse with a
single-step forward pass to logits + argmax over three label-token
candidates), `_try_parse_judge_severity` (deleted under A4 — no parse
step exists), `JUDGE_PROMPT_TEMPLATE` (instruction-line text
preserved; the prompt is unchanged in content), `MAX_NEW_TOKENS_JUDGE`
(unused under A4 — no generation occurs; constant retained for
provenance / comparison only). Plus per-row audit fields in the
annotated cache + JSON output (a new `judge_logits` triple per row).

**Rationale.** §15.14 v2 closed as `ANNOTATION_FAILED` (this commit
cycle) at `json_parse_failure_rate = 0.8477` under §15.14-A3
(single-digit prompt + `MAX_NEW_TOKENS_JUDGE = 8`). Combined with v1
results (Qwen-7B/JSON @ 0.2692, Llama-8B/JSON @ 0.7077), the empirical
pattern is that 7-8B-class instruction-tuned judges fail the 5%
parse-failure gate across multiple output-format prompts. The binding
constraint at this hardware/parameter scale is **format-following
reliability**, not rubric understanding.

§15.14-A4 removes the format-following step entirely. Instead of
asking the judge to *generate* a label, we read the judge's
distribution over the three label tokens at the first decoder step
and take argmax. This is mechanically the simplest possible severity
extraction protocol that respects the rubric: the judge still scores
the rubric (it conditions on the full prompt including all severity
definitions); only the output-emission step is replaced.

**Change.** Three pinned implementation modifications. No threshold
changes.

1. **Severity extraction (replaces generation + parse).** For each
   evaluation row:
   - Render the full judge prompt (unchanged content, unchanged SHA-
     256 of the template text).
   - Encode the prompt with the active judge tokenizer.
   - Run a single forward pass over the encoded prompt; obtain the
     logits at the LAST input position (i.e. the logits over the
     vocabulary that would be used to sample the FIRST generated
     token).
   - Identify the token IDs corresponding to the three label
     characters: `"0"`, `"1"`, `"2"`. The token IDs are computed once
     at judge-load time via `tokenizer.encode(label, add_special_tokens=False)`
     and verified to be single-token under the active tokenizer; if
     any of the three labels does not encode to a single token under
     the active judge tokenizer, the script exits 9 ANNOTATION_FAILED
     with a diagnostic (this is the structural prerequisite for
     logit-based extraction).
   - `severity = argmax({logit_at_id_for_"0", logit_at_id_for_"1",
     logit_at_id_for_"2"})`.
   - `rationale = ""` (no rationale in A4; preserved as empty string
     for output-schema continuity, same as A3).

2. **Pinned `MAX_NEW_TOKENS_JUDGE`** is **retained but unused** under
   A4 (`= 8`, inherited from §15.14-A3). It is preserved as a constant
   in the annotated cache and in the markdown report for provenance
   so that the audit trail makes the A3 → A4 transition explicit.

3. **Per-row audit fields.** The annotated cache and the per-row JSON
   add a single field:
   ```
   "judge_logits": {"0": <float>, "1": <float>, "2": <float>}
   ```
   These are the raw logits at the three label-token positions (NOT
   softmaxed; the argmax is invariant under softmax, so the raw logits
   are the audit-minimal record). They are recorded in fp32. The
   existing `judge_severity` and `judge_rationale` fields are
   preserved; `judge_rationale` is the empty string under A4.

**Parser change.** `_try_parse_judge_severity(raw)` is **removed**
under A4. There is no string parsing step. The function and its
callers in `_judge_one_row` are deleted; the new `_judge_one_row`
body returns `(severity, "", logits_triple)` directly from the
forward pass.

**Failure surfaces under A4.**

- `json_parse_failure_rate` is structurally **zero** (no parsing
  occurs). The field name is **preserved** in the output schema for
  cross-version diff continuity (and reported as `0.0`); a future v3+
  rename to `judge_extraction_failure_rate` is deferred.
- The **single-token-encoding precondition** (each label must encode
  to a single token under the active tokenizer) is checked once at
  judge-load and a failure exits 9 ANNOTATION_FAILED with diagnostic
  `LABEL_TOKEN_ENCODING_AMBIGUOUS`.
- The **Pass D κ-gate** (Cohen's κ ≥ 0.6 inclusive between judge
  severity and human label severity, computed on the 50 calibration
  rows with `BINARY_LABEL_THRESHOLD: y = 1 iff severity ≥ 1`) is
  **unchanged and binding**. If κ < 0.6, the script exits 9
  ANNOTATION_FAILED before the cascade is computed.

**Output schema change (annotated cache + JSON).**

- New per-row field: `judge_logits` (object with keys `"0"`, `"1"`,
  `"2"`; values `float`). Required under A4.
- `judge_severity`: unchanged (int in `{0, 1, 2}`).
- `judge_rationale`: unchanged (empty string `""` under A4 and A3;
  preserved for cross-version schema continuity).
- `annotation_protocol.judge_prompt_sha256`: unchanged from A3 (the
  prompt text content is unchanged).
- New `annotation_protocol.judge_extraction_method`: string field with
  value `"logit_first_token_argmax"` under A4 (was `"generate_and_parse"`
  pre-A4, retroactively populated for cross-version comparison).

**What this amendment does NOT change.**

- `JUDGE_MODEL_ID_DEFAULT` (`Qwen/Qwen2.5-72B-Instruct`): unchanged.
- `JUDGE_MODEL_ID_FALLBACK` (`meta-llama/Llama-3.1-8B-Instruct`,
  effective under §15.14-A2): unchanged.
- `KAPPA_GATE_THRESHOLD = 0.6` (inclusive): unchanged.
- `ANNOTATION_FAILURE_RATE_THRESHOLD = 0.05`: unchanged (vacuous
  under A4 since parse failure is structurally zero, but retained).
- `BINARY_LABEL_THRESHOLD` (y = 1 iff severity ≥ 1): unchanged.
- `DIRECTION_GATE_THRESHOLD = 0.5` (strict): unchanged.
- `PARTIAL_AUC_THRESHOLD = 0.66` (inclusive): unchanged.
- `STRONG_AUC_THRESHOLD = 0.75` (inclusive): unchanged.
- `STRONG_DELTA_AUC_THRESHOLD = 0.05` (inclusive, vs chance, vs
  R_topic_to_framing, vs R_recency): unchanged.
- Severity rubric (0=IGNORED / 1=MENTIONED / 2=STRUCTURED): unchanged.
- Cascade structure (4-step direction-gate → STRONG → PARTIAL →
  NO_MATERIAL), 2-comparator strict-margin requirement: unchanged.
- 12 self-test cascade boundary cases: unchanged.
- 52-pattern Class-3 firewall: unchanged.
- `JUDGE_PROMPT_TEMPLATE` text content (and its SHA-256): unchanged.
  The prompt still says "Return EXACTLY ONE CHARACTER: 0, 1, or 2."
  even though we no longer generate. This preserves the rubric-
  conditioning context exactly as it was under A3.
- `framing_15_14_extractions.npz` cache: unchanged and reusable via
  `--force-annotate`.
- All `human_severity_rationale` values in the calibration labels
  artifact: unchanged.
- §15.14-A1 (synthetic_frame_positive_v1 source enum): unchanged.
- §15.14-A2 (Llama-3.1-8B fallback judge): unchanged.
- §15.14-A3 (single-digit prompt text + `MAX_NEW_TOKENS_JUDGE = 8`):
  remains EFFECTIVE in the spec; A4 supersedes only the *extraction
  mechanism*, not the prompt text. The empirical observation that
  A3's generation path fails the 5% gate is recorded in the v2
  outcome document (§0.8-binding) and stands.
- All §13/§14/§15.x verdicts-of-record (including §15.14 v1
  ANNOTATION_FAILED closure and §15.14 v2 ANNOTATION_FAILED closure):
  preserved.

**Cascade verdict reading discipline (post-A4).**

A §15.14 v3 cascade verdict produced under §15.14-A4 (logit-first-
token-argmax judge) is a §0.8-binding readout AT THE STATED JUDGE
CONFIGURATION. It is not directly comparable to a hypothetical
generation-based cascade verdict because the extraction mechanism
itself is a different empirical claim (the model's first-token logit
distribution may not equal the model's generation distribution after
sampling, even at temperature 0; the two coincide for argmax decoding
without preamble, but the latter is empirically not observed at this
parameter scale).

**What this amendment does NOT permit.**

- Lowering `KAPPA_GATE_THRESHOLD` below 0.6.
- Modifying any sealed AUC threshold, the cascade structure, the
  comparator rules, or the severity rubric.
- Modifying the topic-overlap firewall (52 patterns).
- Modifying `BINARY_LABEL_THRESHOLD`.
- Modifying `DIRECTION_GATE_THRESHOLD`.
- Quantizing any judge model.
- Sign-flip rescue on direction-gate failure.
- Skipping the κ self-test gate.
- Treating the v3 logit-first-token-argmax cascade verdict as
  equivalent to a hypothetical generation-based cascade verdict for
  cross-§ comparison.
- Modifying the human calibration labels artifact.
- Modifying any prior §13 / §14 / §15.x verdict-of-record.

**Pinned-table update (Chunk 6 Sealed §0.8-binding decisions).**

One new entry; one entry annotated:

| Decision | Pinned value (post-A4) |
|---|---|
| `JUDGE_EXTRACTION_METHOD` | `logit_first_token_argmax` (effective under §15.14-A4; was `generate_and_parse` pre-A4) |
| `MAX_NEW_TOKENS_JUDGE` | `8` (effective under §15.14-A3; **unused under §15.14-A4** — no generation occurs; retained for provenance) |

**Implementation surface.** Three contained changes to
`scripts/probe_framing_15_14.py`:

1. `_judge_one_row` body: replace `model.generate(...) → decode → parse`
   with `model(...) → logits[-1] → argmax over three label-token IDs`.
   Returns `(severity, "", logits_triple)`.
2. `_try_parse_judge_severity`: deleted (no callers).
3. Judge-load step: precompute the three label-token IDs and verify
   single-token encoding under the active tokenizer; exit 9 with
   `LABEL_TOKEN_ENCODING_AMBIGUOUS` if any label is multi-token.
4. JSON / annotated-cache / markdown writers: add per-row
   `judge_logits` triple; add `annotation_protocol.judge_extraction_method`
   top-level field.

No other source changes. The `_load_judge_model`, `run_pass_c_judge`,
`run_pass_d_kappa_gate`, `compute_features_per_row`,
`classify_cascade_framing`, the firewall, and the writers are
otherwise unchanged.

**Required reporting (per user authorization, this commit cycle).**

The v3 outcome document must list all four judge attempts side-by-
side (verbatim from the v2 OUTCOME document, plus the v3 row):

1. Qwen-7B JSON judge: parse failure 0.2692 → ANNOTATION_FAILED
2. Llama-8B JSON judge: parse failure 0.7077 → ANNOTATION_FAILED
3. Llama-8B single-digit 8-token judge / A3: parse failure 0.8477 → ANNOTATION_FAILED
4. Llama-8B logit-first-token judge / A4: parse failure structurally 0.0; κ-gate result TBD

If §15.14-A4 also fails the κ-gate, §15.14 closes as
ANNOTATION_FAILED across all accessible judges. If §15.14-A4 passes
the κ-gate, only then is the cascade verdict computed, without
changing any threshold.

**Provenance after a §15.14-A4 v3 run.**

A successful §15.14-A4 v3 cascade verdict (or κ-gate-failure exit 9)
will produce annotated-cache + JSON output with:

```
"annotation_protocol": {
  "judge_model_id": "<whichever judge loaded; unchanged from A2 logic>",
  "judge_fallback_used": <bool>,
  "judge_prompt_sha256": "<unchanged from A3>",
  "judge_extraction_method": "logit_first_token_argmax",
  "label_token_ids": {"0": <int>, "1": <int>, "2": <int>},
  ...
},
"per_row": [
  {"...": ..., "judge_logits": {"0": <float>, "1": <float>, "2": <float>}, ...},
  ...
]
```

The presence of `judge_extraction_method = "logit_first_token_argmax"`
and per-row `judge_logits` triples is the audit-trail signature that
§15.14-A4 is in effect.

**v3 readout discipline.** The §15.14 v1 closure (commit `2d88be1`)
and the §15.14 v2 closure (commit cycle of this amendment) are both
preserved. The §15.14-A4 v3 readout is a **separate** §0.8-binding
result. It does not retroactively give v1 or v2 a verdict; it
produces a fresh v3 verdict under a different judge extraction
mechanism.

---

### §15.14-A5 — judge prompt rendering: chat-template (H1-only; revised after empirical falsification of the single-token H2 surface-variant design)

**Status:** EFFECTIVE per user sign-off recorded in the commit that
flipped this status field (the immediate predecessor of this
document version on branch `claude/diagnose-framing-kappa-L6dmt`).
Sign-off correspondence used the literal phrase
`Sign off §15.14-A5. Push the EFFECTIVE follow-up.` and explicitly
bounded the EFFECTIVE scope to: H1-only;
`tokenizer.apply_chat_template(...)` for judge prompt rendering;
unchanged isolated-token logit argmax over `"0"`, `"1"`, `"2"`; no
H2 single-token surface-variant mechanism; no two-token marginal
scoring; no §15.14-A6; no 70B escalation; no modification of any
threshold, label, rubric, cascade, firewall, sign direction, or
prior verdict-of-record. The EFFECTIVE readout discipline:
κ ≥ 0.6 → cascade; κ < 0.6 → A5 ANNOTATION_FAILED with H1 ruled
out for the accessible 8B judge, with no reinterpretation of v1 /
v2 / v3 and no overwrite of A4 diagnostic findings.

**Revision provenance.** A prior version of this PROPOSED block
(committed in `6aa5a7e`) specified a 6-candidate logit argmax over
`{iso_0, iso_1, iso_2, sp_0, sp_1, sp_2}` plus a
`LABEL_TOKEN_ENCODING_AMBIGUOUS_SPACE_PREFIXED` precondition. That
H2 mechanism was empirically falsified before sign-off by
`scripts/diagnose_a4_kappa.py --tokenizer-only` (commit `ed47395`)
on the post-§15.14-A2 fallback judge tokenizer
(`meta-llama/Llama-3.1-8B-Instruct`):

| label | iso        | space-prefixed | newline-prefixed |
|-------|------------|----------------|-------------------|
| `'0'` | `[15]`     | `[220, 15]`    | `[198, 15]`       |
| `'1'` | `[16]`     | `[220, 16]`    | `[198, 16]`       |
| `'2'` | `[17]`     | `[220, 17]`    | `[198, 17]`       |

Token 220 is the literal-space token; token 198 is the
literal-newline token. Under Llama-3.1's tiktoken-style BPE, no
single token in the active vocabulary encodes the surface form
`" 0"`, `" 1"`, `" 2"`, `"\n0"`, `"\n1"`, or `"\n2"`. The
single-token-space-prefixed argmax candidate set required by the
prior A5 H2 mechanism therefore has **no valid token IDs to point
at on this tokenizer**, and the precondition
`LABEL_TOKEN_ENCODING_AMBIGUOUS_SPACE_PREFIXED` would correctly
fire at judge-load and exit 9 ANNOTATION_FAILED before Pass C ran.
The mechanism is structurally infeasible against the post-A2
fallback judge.

The current revision drops H2 from §15.14-A5 entirely and narrows
A5 to **H1-only**. A future §15.14-A6 may revisit H2 under a
different mechanism (e.g., two-token marginal log-probability:
compare `logit(15)` against `logit(220) + logit(15 | prev=220)`,
and parallels for 16/17), but that is **out of scope** for A5 and
is **not authorized** by this PROPOSED block.

**Scope (revised).** One surgical code change inside
`scripts/probe_framing_15_14.py`:

1. The `_judge_one_row` body — replace the raw-string tokenization
   step with a chat-template render of the existing rendered judge
   prompt as the single user message, with
   `add_generation_prompt=True`. The frozen `JUDGE_PROMPT_TEMPLATE`
   text and its SHA-256 are unchanged; the template is **wrapped**,
   not edited. The argmax candidate set remains the unchanged
   3-element isolated-form `{label_token_ids["0"],
   label_token_ids["1"], label_token_ids["2"]}` inherited from
   §15.14-A4.

`_load_judge_model` is **unchanged** under the revised A5 (no
space-prefixed precondition, no widened return). The annotated-
cache schema bumps from `15.14-A4-annotated` to
`15.14-A5-annotated` for cross-version diff continuity, but the
on-disk per-row layout is **structurally identical** to A4: a
`(n, 3)` `judge_logits` matrix in iso-form column order
`(0, 1, 2)`, no `judge_label_form_used` column. The single new
top-level provenance field is `annotation_protocol.judge_prompt_render`.

**No other source change.** `_load_judge_model` (other than the
unchanged §15.14-A4 isolated-form precondition), Pass A
(multi-turn extraction), Pass B (standalone Q_t extraction), Pass
C (other than the rendering change in `_judge_one_row`), Pass D
(κ-gate computation), the cascade comparator, the firewall, the
self-test gate, the writers (other than the schema-version string
and one new top-level provenance field), and the calibration
labels artifact are otherwise unchanged.

**Rationale (revised).** §15.14 v3 closed as `ANNOTATION_FAILED`
(commit `257dd24`) at Cohen's κ = `−0.0776 < 0.6 inclusive` under
§15.14-A4 logit-first-token-argmax extraction. The format-
following confound is structurally removed under A4 (parse failure
= 0.0); the residual κ readout was approximately uncorrelated with
the human rubric.

The leading remaining mechanistic hypothesis on the A4 readout
that is operable as a ~5-line code change is:

- **H1 (rendering-protocol mismatch).** `_judge_one_row` calls
  `tokenizer(prompt, return_tensors="pt", return_attention_mask=True)`
  on the raw rendered judge prompt
  (`scripts/probe_framing_15_14.py:1750` post-`dc10d78`). The judge
  model is `meta-llama/Llama-3.1-8B-Instruct`, an instruction-tuned
  chat model whose first-token logit distribution is calibrated for
  the post-`<|end_header_id|>\n\n` position of the Llama-3.1 chat
  template — not for the raw text-tail position the script feeds
  it. Pass A and Pass B (subject side, `scripts/probe_framing_15_14.py:1263`
  and `scripts/probe_framing_15_14.py:1421`) both render their
  prompts via `tokenizer.apply_chat_template(...,
  add_generation_prompt=True)`. The judge side does not; the
  asymmetry is the §15.14-A5 H1 test.

H2 (label-token locus mismatch) was tested empirically before
sign-off via the tokenizer-form asymmetry probe (block 6 of
`scripts/diagnose_a4_kappa.py`). The probe confirmed that the
isolated-form `{15, 16, 17}` and the space-prefixed-form continue
to differ by exactly one prefix token (220 for space, 198 for
newline), and that no single-token space-prefixed variant exists
on the active tokenizer. H2's single-token mechanism is
falsified; H2's two-token-marginal mechanism remains a valid
hypothesis but is mechanistically more complex (an extra
forward pass per row, plus a joint-logprob argmax) and is deferred
to a future §15.14-A6 PROPOSED amendment.

H1 alone is a ~5-line code change in `_judge_one_row`, and it
produces a measurable κ delta without changing the prompt text,
the rubric, the calibration labels, the cascade structure, or any
sealed threshold. If A5 (H1-only) clears the κ-gate, the §15.14
v4 cascade verdict is computed without any threshold change. If
A5 also fails the κ-gate, then H1 is ruled out as the binding
constraint at 7-8B scale, and the residual diagnosis routes to:

  - §15.14-A6 PROPOSED (two-token-marginal H2; future cycle); or
  - H3 (global-mass diagnostic on GPU; partial diagnostic available
    via `scripts/diagnose_a4_kappa.py` block 5 once a
    `framing_15_14_annotated_A4_diagnostic.npz` cache exists); or
  - 70B+ judge escalation under separate authorization.

§15.14-A5 (revised) does NOT pre-judge the outcome: it reduces
exactly one specific mechanism candidate (H1) to a single binary
κ readout under the same sealed `KAPPA_GATE_THRESHOLD = 0.6
inclusive` gate that bound v1 / v2 / v3.

**Change (revised).** Two pinned implementation modifications. No
threshold changes.

1. **Judge prompt rendering (H1 fix; replaces raw-string
   tokenization).** Inside `_judge_one_row`, after rendering the
   frozen `JUDGE_PROMPT_TEMPLATE` via the unchanged `render_judge_prompt`
   function, encode the resulting text through the active
   tokenizer's chat template as a single user message:

   ```
   encoded = tokenizer.apply_chat_template(
       [{"role": "user", "content": prompt}],
       add_generation_prompt=True,
       return_tensors="pt",
       return_dict=True,
   )
   ```

   The final-position logits readout is unchanged (still
   `out.logits[0, -1, :]` at fp32 over the active vocabulary). The
   final position now corresponds to the immediate-next-token slot
   after the chat template's assistant-header generation prompt
   (i.e., immediately after `<|end_header_id|>\n\n` for Llama-3.1),
   which is the position the model's first-token distribution is
   calibrated for.

   The frozen `JUDGE_PROMPT_TEMPLATE` text content and its SHA-256
   are **unchanged**: the prompt is wrapped by the chat template,
   not edited. The recorded
   `annotation_protocol.judge_prompt_sha256` continues to refer to
   the unwrapped template content (preserved for cross-version
   diff continuity); the new
   `annotation_protocol.judge_prompt_render` field records the
   rendering protocol.

2. **Per-row audit fields (annotated cache + JSON; minimal
   delta).** The annotated cache schema bumps from
   `15.14-A4-annotated` to `15.14-A5-annotated`. The on-disk per-
   row layout is **structurally identical** to A4: a `(n, 3)`
   `judge_logits` matrix in iso-form column order `("0", "1", "2")`,
   plus the existing `severity`, `judge_rationale`, and provenance
   fields. The schema bump is for cross-version diff continuity
   only (so a downstream reader can tell whether the cache was
   produced by A4 raw-string or A5 chat-template rendering).

   Top-level provenance fields in JSON output and the annotated
   cache:
   - `annotation_protocol.judge_prompt_render`: new; value
     `"apply_chat_template_user_only(add_generation_prompt=True)"`
     under A5 (retroactively populated as `"raw_string"` for any
     pre-A5 cache loaded for diff comparison; pre-A5 caches are
     not recomputed).
   - `annotation_protocol.label_token_ids`: unchanged (isolated-
     form IDs `{0→15, 1→16, 2→17}` under Llama-3.1-8B-Instruct;
     preserved for cross-version diff).
   - `annotation_protocol.judge_extraction_method`: unchanged
     (`"logit_first_token_argmax"`; the mechanism is structurally
     the same — only the input position changes).

   No `judge_label_form_used` column. No
   `label_token_ids_space_prefixed` field. No 6-cell judge_logits
   object. These were specified in the prior PROPOSED block
   (`6aa5a7e`) and are removed in this revision.

**Failure surfaces under A5 (revised).**

- `json_parse_failure_rate` is structurally **zero** (no parsing
  step; A4 inheritance). The field name is **preserved** in the
  output schema for cross-version diff continuity.
- `LABEL_TOKEN_ENCODING_AMBIGUOUS` (isolated-form precondition,
  introduced under A4): unchanged.
- The Pass D **κ-gate at `KAPPA_GATE_THRESHOLD = 0.6` inclusive**
  remains **unchanged and binding**. If κ < 0.6 on the 50
  calibration rows under the A5 chat-template-rendered argmax,
  the script exits 9 ANNOTATION_FAILED before the cascade is
  computed, exactly as under A4.

**What this amendment does NOT change (revised).**

- `JUDGE_MODEL_ID_DEFAULT` (`Qwen/Qwen2.5-72B-Instruct`):
  unchanged.
- `JUDGE_MODEL_ID_FALLBACK` (`meta-llama/Llama-3.1-8B-Instruct`,
  effective under §15.14-A2): unchanged.
- `KAPPA_GATE_THRESHOLD = 0.6` (inclusive): unchanged.
- `ANNOTATION_FAILURE_RATE_THRESHOLD = 0.05`: unchanged (vacuous
  under A4 / A5 since parse failure is structurally zero, but
  retained).
- `BINARY_LABEL_THRESHOLD` (y = 1 iff severity ≥ 1): unchanged.
- `DIRECTION_GATE_THRESHOLD = 0.5` (strict): unchanged.
- `PARTIAL_AUC_THRESHOLD = 0.66` (inclusive): unchanged.
- `STRONG_AUC_THRESHOLD = 0.75` (inclusive): unchanged.
- `STRONG_DELTA_AUC_THRESHOLD = 0.05` (inclusive, vs chance, vs
  R_topic_to_framing, vs R_recency): unchanged.
- Severity rubric (0=IGNORED / 1=MENTIONED / 2=STRUCTURED):
  unchanged.
- Sign direction (BCVF-faithful: `R_framing` higher → more
  framing-stickiness): unchanged.
- Cascade structure (4-step direction-gate → STRONG → PARTIAL →
  NO_MATERIAL), 2-comparator strict-margin requirement: unchanged.
- 12 self-test cascade boundary cases: unchanged.
- 52-pattern Class-3 firewall: unchanged.
- `JUDGE_PROMPT_TEMPLATE` text content (and its SHA-256): unchanged.
  The prompt is wrapped by the chat template, not edited. The
  rubric-conditioning context that the judge reads is identical.
- `MAX_NEW_TOKENS_JUDGE = 8`: retained but unused (A4 inheritance).
- Argmax candidate set: **unchanged from A4**, `{label_token_ids["0"],
  label_token_ids["1"], label_token_ids["2"]}` (isolated-form,
  3-element). The prior PROPOSED widening to a 6-element set is
  withdrawn under this revision.
- `framing_15_14_extractions.npz` extraction cache: unchanged and
  reusable via `--force-annotate`.
- All `human_severity` / `human_severity_rationale` values in the
  calibration labels artifact: unchanged. The locked labels SHA
  (`e9776ff223ef913b2e404d2cf90203e9615c01640bc8fc5c42ffabf2d49b0d6c`,
  50/50 by `rasaha-2026-04-30`) is unchanged.
- Locked stimulus SHA
  (`e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7`):
  unchanged.
- Stimulus geometry (130 chains × 5 evaluation turns = 650 rows,
  100/20/10 main/frame_positive/calibration split): unchanged.
- §15.14-A1 (synthetic_frame_positive_v1 source enum): unchanged.
- §15.14-A2 (Llama-3.1-8B fallback judge): unchanged.
- §15.14-A3 (single-digit prompt text + `MAX_NEW_TOKENS_JUDGE = 8`):
  unchanged in the spec; A5 supersedes only the *prompt-render
  protocol*, not the prompt text content or any constant.
- §15.14-A4 (logit-first-token-argmax extraction mechanism):
  unchanged. A5 changes the input position (raw text-tail →
  chat-template assistant-header) but does NOT change the argmax
  surface (still 3 isolated-form candidates) or the extraction
  mechanism label (`"logit_first_token_argmax"`). The per-row
  `annotation_protocol.judge_prompt_render` field disambiguates
  A4 (`"raw_string"`) from A5 (`"apply_chat_template_user_only(add_generation_prompt=True)"`).
- All §13/§14/§15.x verdicts-of-record (including §15.14 v1
  ANNOTATION_FAILED closure, §15.14 v2 ANNOTATION_FAILED closure,
  and §15.14 v3 ANNOTATION_FAILED closure across all four tested
  judge configurations): preserved.

**What this amendment does NOT permit.**

- Lowering `KAPPA_GATE_THRESHOLD` below 0.6.
- Modifying any sealed AUC threshold, the cascade structure, the
  comparator rules, or the severity rubric.
- Modifying the topic-overlap firewall (52 patterns).
- Modifying `BINARY_LABEL_THRESHOLD`.
- Modifying `DIRECTION_GATE_THRESHOLD`.
- Modifying the sign convention (BCVF-faithful direction).
- Editing `JUDGE_PROMPT_TEMPLATE` text content (the prompt is
  wrapped, not edited).
- Re-collapsing the 3-class κ to a binary κ (binary-collapse κ may
  appear in diagnostic output as a side metric per
  `BINARY_LABEL_THRESHOLD_DESCRIPTION`, but the binding gate
  remains the 3-class Cohen's κ).
- Sign-flip rescue on direction-gate failure.
- Skipping the κ self-test gate.
- Treating the v4 cascade verdict as equivalent to a hypothetical
  generation-based or A4-extraction-surface cascade verdict for
  cross-§ comparison.
- Modifying the human calibration labels artifact.
- Modifying any prior §13 / §14 / §15.x verdict-of-record.
- Quantizing any judge model.
- Escalating the judge model identity (no 70B+ swap under A5;
  A5 is restricted to the post-A2 `meta-llama/Llama-3.1-8B-
  Instruct` fallback).
- Widening the argmax candidate set beyond the 3 isolated-form
  label-token IDs (the H2 single-token surface-variant widening
  was empirically falsified before sign-off and is withdrawn).
- Adding an extra forward pass per row, a two-token marginal
  log-probability computation, or any other H2 mechanism in
  this amendment cycle (deferred to a future §15.14-A6).

**Cascade verdict reading discipline (post-A5).**

A §15.14 v4 cascade verdict produced under §15.14-A5 (chat-
template-rendered prompt + unchanged 3-element iso-form argmax)
is a §0.8-binding readout AT THE STATED JUDGE CONFIGURATION. It
is not directly comparable to the §15.14-A4 v3 cascade verdict
(which was never computed; v3 closed at κ-gate failure) because
the input position is a different empirical claim about which
locus of the model's logit row encodes the rubric-conditioned
severity. The two readouts share the prompt text content, the
judge model identity, and the 3-element argmax surface.

**Pinned-table update (Chunk 6 Sealed §0.8-binding decisions; revised).**

One new pinned entry; no other entries added or modified by this
amendment:

| Decision | Pinned value (post-A5) |
|---|---|
| `JUDGE_PROMPT_RENDER` | `apply_chat_template_user_only(add_generation_prompt=True)` (effective under §15.14-A5; was implicit `raw_string` pre-A5) |

The prior PROPOSED block (`6aa5a7e`) added a second entry
`JUDGE_LABEL_TOKEN_CANDIDATE_SET` widening the candidate set to
6 elements. That entry is **withdrawn** under this revision; the
candidate set remains the 3-element isolated-form set inherited
from §15.14-A4 and is not separately pinned by A5.

**Implementation surface (revised; post-sign-off, EFFECTIVE follow-up).**

Three contained changes to `scripts/probe_framing_15_14.py`:

1. `_judge_one_row` body: replace `tokenizer(prompt, return_tensors=
   "pt", return_attention_mask=True)` with the chat-template
   render sketched above. The per-row return tuple is unchanged
   (`(severity, "", logits_triple)`).
2. `_save_annotated_cache` / `_load_annotated_cache`: bump the
   schema-version constant `_ANNOTATED_CACHE_SCHEMA_VERSION` from
   `"15.14-A4-annotated"` to `"15.14-A5-annotated"`. No layout
   change.
3. Top-level provenance write: add a single new field
   `annotation_protocol.judge_prompt_render` to the JSON writer
   and to the markdown writer's audit-trail block. Value:
   `"apply_chat_template_user_only(add_generation_prompt=True)"`.

`_load_judge_model` is **unchanged** under the revised A5.

No other source change. `_load_subject_model`, `extract_pass_a_iterative`,
`extract_pass_b_standalone`, `run_pass_c_judge` (other than
calling the revised `_judge_one_row`), `run_pass_d_kappa_gate`,
`compute_features_per_row`, `classify_cascade_framing`, the
firewall, and the self-test gate are unchanged.

**Required reporting (under v4 EFFECTIVE follow-up).**

The §15.14 v4 outcome document must list all five judge attempts
side-by-side (the four from v3 OUTCOME plus the v4 row):

1. Qwen-7B JSON judge: parse failure 0.2692 → ANNOTATION_FAILED
2. Llama-8B JSON judge: parse failure 0.7077 → ANNOTATION_FAILED
3. Llama-8B single-digit 8-token judge / A3: parse failure 0.8477 → ANNOTATION_FAILED
4. Llama-8B logit-first-token judge / A4 (raw-string render, 3 candidates): parse failure 0.0; κ = −0.0776 → ANNOTATION_FAILED
5. Llama-8B logit-first-token judge / A5 (chat-template render, 3 candidates): parse failure 0.0; κ = TBD

If §15.14-A5 also fails the κ-gate, §15.14 closes as
ANNOTATION_FAILED with H1 ruled out as the binding constraint;
the residual diagnosis routes to §15.14-A6 PROPOSED (two-token-
marginal H2; future cycle), and ultimately to a 70B+ judge
escalation under a separate authorization. If §15.14-A5 passes
the κ-gate, the v4 cascade verdict is computed without changing
any threshold.

**Provenance after a §15.14-A5 v4 run.**

A successful §15.14-A5 v4 cascade verdict (or κ-gate-failure
exit 9) will produce annotated-cache + JSON output with:

```
"annotation_protocol": {
  "judge_model_id": "<whichever judge loaded; unchanged from A2 logic>",
  "judge_fallback_used": <bool>,
  "judge_prompt_sha256": "<unchanged from A3>",
  "judge_prompt_render": "apply_chat_template_user_only(add_generation_prompt=True)",
  "judge_extraction_method": "logit_first_token_argmax",
  "label_token_ids":               {"0": <int>, "1": <int>, "2": <int>},
  ...
},
"per_row": [
  {
    "...": ...,
    "judge_logits": {"0": <float>, "1": <float>, "2": <float>},
    ...
  },
  ...
]
```

The per-row `judge_logits` object remains a 3-cell triple under
A5 (identical to A4). The presence of
`judge_prompt_render = "apply_chat_template_user_only(add_generation_prompt=True)"`
is the audit-trail signature that §15.14-A5 is in effect (the
on-disk per-row layout is otherwise indistinguishable from A4).

**v4 readout discipline.** The §15.14 v1 closure (commit `2d88be1`),
the §15.14 v2 closure (commit `198378e`), and the §15.14 v3
closure (commit `257dd24`) are all preserved. The §15.14-A5 v4
readout is a **separate** §0.8-binding result. It does not
retroactively give v1, v2, or v3 a verdict; it produces a fresh
v4 verdict under a different judge prompt-render protocol with
the unchanged A4 first-token candidate set.

**Empirical falsification record (single-token surface-variant H2).**

The §15.14-A5 PROPOSED block at commit `6aa5a7e` specified a
6-element argmax candidate set
`{iso_0, iso_1, iso_2, sp_0, sp_1, sp_2}` plus a
`LABEL_TOKEN_ENCODING_AMBIGUOUS_SPACE_PREFIXED` precondition that
required each of `" 0"`, `" 1"`, `" 2"` to encode to a single
token under the active tokenizer. That mechanism was tested
empirically before sign-off via
`scripts/diagnose_a4_kappa.py --tokenizer-only` (commit `ed47395`)
on `meta-llama/Llama-3.1-8B-Instruct`'s tokenizer, with the result
that no single-token space-prefixed variant exists on that
tokenizer (`" 0"` → `[220, 15]`, etc.). The single-token H2
mechanism is therefore structurally infeasible against the
post-A2 fallback judge; the precondition would correctly fire at
judge-load and exit 9 ANNOTATION_FAILED before Pass C.

This empirical falsification is recorded as a §0.8-binding
finding-of-record about the active tokenizer and is preserved in
this spec. It does not constitute a verdict-of-record on
§15.14's hypothesis class; it is a tokenizer-level structural
observation. Future amendments are free to revisit H2 under a
different mechanism (e.g., two-token marginal log-probability)
that does not require single-token encoding of surface
variants. Such mechanisms are deferred to a future §15.14-A6
PROPOSED amendment and are not authorized by this revised A5
PROPOSED block.

**Two-phase discipline (per A1–A4 precedent; explicit).**

1. **PROPOSED commit (revised)** (this commit cycle): the spec
   amendment block above is added with `Status: PROPOSED
   (revised)`. No code is touched in
   `scripts/probe_framing_15_14.py`. No status flip. No cache
   schema bump. No annotated-cache write. The prior PROPOSED
   block (`6aa5a7e`) is superseded by this revision; the prior
   block's H2 6-candidate mechanism is withdrawn; only the H1
   chat-template-render mechanism remains under PROPOSED.
2. **EFFECTIVE follow-up** (separate commit, only after the user
   replies with the literal phrase
   `Sign off §15.14-A5. Push the EFFECTIVE follow-up.`): flips
   this status field from `PROPOSED (revised)` to `EFFECTIVE`,
   applies the three-item implementation surface enumerated
   above (one `_judge_one_row` body change, one schema-version
   bump, one new top-level provenance field), and bumps the
   annotated-cache schema string. The runpod execution under
   the EFFECTIVE follow-up is a **separate** user authorization;
   it is not implied by the EFFECTIVE flip itself.

**No other source change.** `_load_subject_model`, Pass A
(multi-turn extraction), Pass B (standalone Q_t extraction), Pass D
(κ-gate computation), the cascade comparator, the firewall, the
self-test gate, the writers, and the calibration labels artifact
are otherwise unchanged.

**Rationale.** §15.14 v3 closed as `ANNOTATION_FAILED` (commit
`257dd24`) at Cohen's κ = `−0.0776 < 0.6 inclusive` under §15.14-A4
logit-first-token-argmax extraction. The format-following confound
is structurally removed under A4 (parse failure = 0.0); the residual
κ readout was approximately uncorrelated with the human rubric.
Two leading mechanistic hypotheses about the A4 readout are
diagnostically separable from the rubric-discrimination hypothesis
without changing any threshold or any verdict-of-record:

- **H1 (rendering-protocol mismatch).** `_judge_one_row` calls
  `tokenizer(prompt, return_tensors="pt", return_attention_mask=True)`
  on the raw rendered judge prompt
  (`scripts/probe_framing_15_14.py:1750` post-`dc10d78`). The judge
  model is `meta-llama/Llama-3.1-8B-Instruct`, an instruction-tuned
  chat model whose first-token logit distribution is calibrated for
  the post-`<|end_header_id|>\n\n` position of the Llama-3.1 chat
  template — not for the raw text-tail position the script feeds
  it. Pass A and Pass B (subject side, scripts/probe_framing_15_14.py:1263
  and scripts/probe_framing_15_14.py:1421) both render their prompts
  via `tokenizer.apply_chat_template(..., add_generation_prompt=True)`.
  The judge side does not; the asymmetry is the §15.14-A5 H1 test.
- **H2 (label-token locus mismatch).** Under §15.14-A4,
  `_load_judge_model` (`scripts/probe_framing_15_14.py:1695`) encodes
  label characters in **isolated form** (`tokenizer.encode("0",
  add_special_tokens=False) → [15]`, similarly `[16]`, `[17]`).
  After a chat template's assistant header, the natural continuation
  distribution lives over **space-prefixed** (or punctuation-
  prefixed) variants. Llama-3.1's tiktoken-style BPE merges `" 0"`,
  `" 1"`, `" 2"` into distinct token IDs from the isolated `15/16/17`,
  so the §15.14-A4 argmax-over-{15,16,17} samples the wrong three
  loci of the post-header logit row. Adding the space-prefixed
  variants to the candidate set restores parity with the model's
  natural first-token distribution.

Both hypotheses are ~5-line code changes in `_judge_one_row` and
`_load_judge_model`, and they jointly produce a measurable κ delta
without changing the prompt text, the rubric, the calibration
labels, the cascade structure, or any sealed threshold. If A5
clears the κ-gate, the §15.14 v4 cascade verdict is computed without
any threshold change. If A5 also fails the κ-gate, then H1 and H2
are ruled out as the binding constraints at 7-8B scale, and the
residual diagnosis routes to H3 (global-mass diagnostic on GPU) and
ultimately to a 70B+ judge escalation per the user's separate
authorization channel.

§15.14-A5 does NOT pre-judge the outcome: it reduces two specific
mechanism candidates to a single binary κ readout under the same
sealed `KAPPA_GATE_THRESHOLD = 0.6 inclusive` gate that bound v1 /
v2 / v3.

**Change.** Three pinned implementation modifications. No threshold
changes.

1. **Judge prompt rendering (H1 fix; replaces raw-string
   tokenization).** Inside `_judge_one_row`, after rendering the
   frozen `JUDGE_PROMPT_TEMPLATE` via the unchanged `render_judge_prompt`
   function, encode the resulting text through the active tokenizer's
   chat template as a single user message:

   ```
   encoded = tokenizer.apply_chat_template(
       [{"role": "user", "content": prompt}],
       add_generation_prompt=True,
       return_tensors="pt",
       return_dict=True,
   )
   ```

   The final-position logits readout is unchanged (still
   `out.logits[0, -1, :]` at fp32 over the active vocabulary). The
   final position now corresponds to the immediate-next-token slot
   after the chat template's assistant-header generation prompt
   (i.e., immediately after `<|end_header_id|>\n\n` for Llama-3.1),
   which is the position the model's first-token distribution is
   calibrated for.

   The frozen `JUDGE_PROMPT_TEMPLATE` text content and its SHA-256
   are **unchanged**: the prompt is wrapped by the chat template,
   not edited. The recorded
   `annotation_protocol.judge_prompt_sha256` continues to refer to
   the unwrapped template content (preserved for cross-version diff
   continuity); the new `annotation_protocol.judge_prompt_render`
   field records the rendering protocol.

2. **Label-token candidate set (H2 fix; widens the argmax surface).**
   Inside `_load_judge_model`, alongside the existing isolated-form
   `label_token_ids`, additionally compute the space-prefixed form:

   ```
   label_token_ids_space_prefixed: dict[str, int] = {}
   ambiguous_sp: list[str] = []
   for ch in LABEL_TOKEN_CHARS:
       ids_sp = tokenizer.encode(" " + ch, add_special_tokens=False)
       if len(ids_sp) != 1:
           ambiguous_sp.append(f"{(' ' + ch)!r}→{ids_sp!r}")
       else:
           label_token_ids_space_prefixed[ch] = int(ids_sp[0])
   if ambiguous_sp:
       sys.stderr.write(
           "ANNOTATION_FAILED: LABEL_TOKEN_ENCODING_AMBIGUOUS_SPACE_PREFIXED — "
           f"space-prefixed label character(s) did not encode to a "
           f"single token under tokenizer of {judge_id_used!r}: "
           f"{', '.join(ambiguous_sp)}. §15.14-A5 requires each of "
           f"' 0', ' 1', ' 2' to be single-token.\n"
       )
       sys.exit(EXIT_ANNOTATION_FAILED)
   ```

   Inside `_judge_one_row`, the argmax is taken over the **6-element
   candidate set**:

   ```
   candidates: list[tuple[str, str, int]] = [
       ("isolated",       "0", label_token_ids["0"]),
       ("isolated",       "1", label_token_ids["1"]),
       ("isolated",       "2", label_token_ids["2"]),
       ("space_prefixed", "0", label_token_ids_space_prefixed["0"]),
       ("space_prefixed", "1", label_token_ids_space_prefixed["1"]),
       ("space_prefixed", "2", label_token_ids_space_prefixed["2"]),
   ]
   logits_by_form: dict[str, dict[str, float]] = {
       "isolated":       {ch: 0.0 for ch in LABEL_TOKEN_CHARS},
       "space_prefixed": {ch: 0.0 for ch in LABEL_TOKEN_CHARS},
   }
   for form, ch, tok_id in candidates:
       logits_by_form[form][ch] = float(last_logits[tok_id].item())
   form_used, severity_char, _ = max(
       candidates, key=lambda t: logits_by_form[t[0]][t[1]],
   )
   ```

   The chosen severity is the digit (`{0, 1, 2}`) of the winning
   candidate; the form (`"isolated"` or `"space_prefixed"`) is
   recorded per row but does **not** participate in the severity
   value. This collapses the 6-candidate argmax back into a 3-class
   severity for downstream Pass D κ and feature computation
   exactly as under A4.

3. **Per-row audit fields (annotated cache + JSON).** The annotated
   cache schema bumps from `15.14-A4-annotated` to
   `15.14-A5-annotated`. Per-row fields:
   - `judge_logits` (renamed in serialized layout): now an object
     with two sub-objects keyed by form:
     ```
     "judge_logits": {
       "isolated":       {"0": <float>, "1": <float>, "2": <float>},
       "space_prefixed": {"0": <float>, "1": <float>, "2": <float>}
     }
     ```
     On disk in `.npz`, `judge_logits` becomes a `(n, 6)` float64
     matrix with column order pinned `(iso_0, iso_1, iso_2, sp_0,
     sp_1, sp_2)`.
   - `judge_label_form_used` (new): string in
     `{"isolated", "space_prefixed"}`. On disk in `.npz`, a
     `(n,)` object array.
   - `judge_severity`: unchanged (int in `{0, 1, 2}`).
   - `judge_rationale`: unchanged (empty string `""` under A5; same
     as A3 / A4).

   Top-level provenance fields in JSON output and the annotated
   cache:
   - `annotation_protocol.judge_prompt_render`: new; value
     `"apply_chat_template_user_only(add_generation_prompt=True)"`
     under A5 (retroactively populated as `"raw_string"` for any
     pre-A5 cache loaded for diff comparison; pre-A5 caches are
     not recomputed).
   - `annotation_protocol.label_token_ids`: unchanged (isolated-form
     IDs; preserved for cross-version diff).
   - `annotation_protocol.label_token_ids_space_prefixed`: new
     under A5 (single-token IDs for `" 0"`, `" 1"`, `" 2"` under
     the active tokenizer).
   - `annotation_protocol.judge_extraction_method`: unchanged
     (`"logit_first_token_argmax"`; the mechanism is structurally
     the same, only the input position and the candidate set
     change).

**Failure surfaces under A5.**

- `json_parse_failure_rate` is structurally **zero** (no parsing
  step; A4 inheritance). The field name is **preserved** in the
  output schema for cross-version diff continuity.
- `LABEL_TOKEN_ENCODING_AMBIGUOUS` (isolated-form precondition,
  introduced under A4): unchanged.
- `LABEL_TOKEN_ENCODING_AMBIGUOUS_SPACE_PREFIXED` (new under A5):
  fires iff any of `" 0"`, `" 1"`, `" 2"` does not encode to a
  single token under the active tokenizer. Under
  `meta-llama/Llama-3.1-8B-Instruct` (the post-A2 fallback),
  Llama's tiktoken-style BPE merges `" 0"`, `" 1"`, `" 2"` into
  single tokens; this precondition is expected to PASS at judge-
  load. If a future judge is wired in whose tokenizer does not
  share this property, the precondition correctly exits 9 with a
  diagnostic instead of silently mis-locating the candidate logits.
- The Pass D **κ-gate at `KAPPA_GATE_THRESHOLD = 0.6` inclusive**
  remains **unchanged and binding**. If κ < 0.6 on the 50
  calibration rows under the A5 candidate set, the script exits 9
  ANNOTATION_FAILED before the cascade is computed, exactly as
  under A4.

**What this amendment does NOT change.**

- `JUDGE_MODEL_ID_DEFAULT` (`Qwen/Qwen2.5-72B-Instruct`): unchanged.
- `JUDGE_MODEL_ID_FALLBACK` (`meta-llama/Llama-3.1-8B-Instruct`,
  effective under §15.14-A2): unchanged.
- `KAPPA_GATE_THRESHOLD = 0.6` (inclusive): unchanged.
- `ANNOTATION_FAILURE_RATE_THRESHOLD = 0.05`: unchanged (vacuous
  under A4 / A5 since parse failure is structurally zero, but
  retained).
- `BINARY_LABEL_THRESHOLD` (y = 1 iff severity ≥ 1): unchanged.
- `DIRECTION_GATE_THRESHOLD = 0.5` (strict): unchanged.
- `PARTIAL_AUC_THRESHOLD = 0.66` (inclusive): unchanged.
- `STRONG_AUC_THRESHOLD = 0.75` (inclusive): unchanged.
- `STRONG_DELTA_AUC_THRESHOLD = 0.05` (inclusive, vs chance, vs
  R_topic_to_framing, vs R_recency): unchanged.
- Severity rubric (0=IGNORED / 1=MENTIONED / 2=STRUCTURED):
  unchanged.
- Sign direction (BCVF-faithful: `R_framing` higher → more
  framing-stickiness): unchanged.
- Cascade structure (4-step direction-gate → STRONG → PARTIAL →
  NO_MATERIAL), 2-comparator strict-margin requirement: unchanged.
- 12 self-test cascade boundary cases: unchanged.
- 52-pattern Class-3 firewall: unchanged.
- `JUDGE_PROMPT_TEMPLATE` text content (and its SHA-256): unchanged.
  The prompt is wrapped by the chat template, not edited. The
  rubric-conditioning context that the judge reads is identical.
- `MAX_NEW_TOKENS_JUDGE = 8`: retained but unused (A4 inheritance).
- `framing_15_14_extractions.npz` extraction cache: unchanged and
  reusable via `--force-annotate`.
- All `human_severity` / `human_severity_rationale` values in the
  calibration labels artifact: unchanged. The locked labels SHA
  (`e9776ff223ef913b2e404d2cf90203e9615c01640bc8fc5c42ffabf2d49b0d6c`,
  50/50 by `rasaha-2026-04-30`) is unchanged.
- Locked stimulus SHA
  (`e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7`):
  unchanged.
- Stimulus geometry (130 chains × 5 evaluation turns = 650 rows,
  100/20/10 main/frame_positive/calibration split): unchanged.
- §15.14-A1 (synthetic_frame_positive_v1 source enum): unchanged.
- §15.14-A2 (Llama-3.1-8B fallback judge): unchanged.
- §15.14-A3 (single-digit prompt text + `MAX_NEW_TOKENS_JUDGE = 8`):
  unchanged in the spec; A5 supersedes only the *prompt-render
  protocol* and the *candidate set*, not the prompt text content
  or any constant.
- §15.14-A4 (logit-first-token-argmax extraction mechanism):
  unchanged. A5 generalizes A4's argmax surface from 3 candidates
  to 6 (3 isolated + 3 space-prefixed) and changes the input
  position from raw text-tail to chat-template assistant-header.
  The extraction method label `"logit_first_token_argmax"` covers
  both A4 and A5; the per-row `judge_label_form_used` field plus
  the `annotation_protocol.judge_prompt_render` field disambiguate.
- All §13/§14/§15.x verdicts-of-record (including §15.14 v1
  ANNOTATION_FAILED closure, §15.14 v2 ANNOTATION_FAILED closure,
  and §15.14 v3 ANNOTATION_FAILED closure across all four tested
  judge configurations): preserved.

**What this amendment does NOT permit.**

- Lowering `KAPPA_GATE_THRESHOLD` below 0.6.
- Modifying any sealed AUC threshold, the cascade structure, the
  comparator rules, or the severity rubric.
- Modifying the topic-overlap firewall (52 patterns).
- Modifying `BINARY_LABEL_THRESHOLD`.
- Modifying `DIRECTION_GATE_THRESHOLD`.
- Modifying the sign convention (BCVF-faithful direction).
- Editing `JUDGE_PROMPT_TEMPLATE` text content (the prompt is
  wrapped, not edited).
- Re-collapsing the 3-class κ to a binary κ (binary-collapse κ may
  appear in diagnostic output as a side metric per
  `BINARY_LABEL_THRESHOLD_DESCRIPTION`, but the binding gate
  remains the 3-class Cohen's κ).
- Sign-flip rescue on direction-gate failure.
- Skipping the κ self-test gate.
- Treating the v4 cascade verdict as equivalent to a hypothetical
  generation-based or A4-extraction-surface cascade verdict for
  cross-§ comparison.
- Modifying the human calibration labels artifact.
- Modifying any prior §13 / §14 / §15.x verdict-of-record.
- Quantizing any judge model.
- Escalating the judge model identity (no 70B+ swap under A5; A5
  is restricted to the post-A2 `meta-llama/Llama-3.1-8B-Instruct`
  fallback).

**Cascade verdict reading discipline (post-A5).**

A §15.14 v4 cascade verdict produced under §15.14-A5 (chat-
template-rendered prompt + 6-candidate argmax) is a §0.8-binding
readout AT THE STATED JUDGE CONFIGURATION. It is not directly
comparable to the §15.14-A4 v3 cascade verdict (which was never
computed; v3 closed at κ-gate failure) because the input position
and the candidate set are different empirical claims about which
locus of the model's logit row encodes the rubric-conditioned
severity. The two readouts share only the prompt text content and
the judge model identity.

**Pinned-table update (Chunk 6 Sealed §0.8-binding decisions).**

One new pinned entry; one entry annotated:

| Decision | Pinned value (post-A5) |
|---|---|
| `JUDGE_PROMPT_RENDER` | `apply_chat_template_user_only(add_generation_prompt=True)` (effective under §15.14-A5; was implicit `raw_string` pre-A5) |
| `JUDGE_LABEL_TOKEN_CANDIDATE_SET` | `{isolated_0, isolated_1, isolated_2, space_prefixed_0, space_prefixed_1, space_prefixed_2}` (effective under §15.14-A5; was `{isolated_0, isolated_1, isolated_2}` under §15.14-A4) |

**Implementation surface (post-sign-off, EFFECTIVE follow-up).**

Three contained changes to `scripts/probe_framing_15_14.py`:

1. `_judge_one_row` body: replace `tokenizer(prompt, return_tensors=
   "pt", return_attention_mask=True)` with the chat-template render
   sketched above; widen the per-row return tuple to carry the
   6-cell logit record and the chosen form.
2. `_load_judge_model`: add the parallel encoding + precondition
   check for the space-prefixed variant; widen the returned dict
   to include `label_token_ids_space_prefixed`.
3. `_save_annotated_cache` / `_load_annotated_cache`: schema bump
   `15.14-A4-annotated → 15.14-A5-annotated`; widen `judge_logits`
   matrix shape `(n, 3) → (n, 6)`; add `judge_label_form_used`
   column; add top-level `judge_prompt_render` and
   `label_token_ids_space_prefixed` fields.

Plus per-row block extension and one new provenance line in:

4. The JSON writer (`_save_probe_json` / equivalent): per-row
   `judge_logits` widened object; per-row `judge_label_form_used`;
   top-level `annotation_protocol.judge_prompt_render` and
   `annotation_protocol.label_token_ids_space_prefixed`.
5. The markdown writer (`_render_probe_markdown` / equivalent):
   one new line in the audit-trail section reporting
   `judge_prompt_render` and the per-form label token IDs; the
   per-row table is unchanged in shape (severity is still a single
   integer column).

No other source change. `_load_subject_model`, `extract_pass_a_iterative`,
`extract_pass_b_standalone`, `run_pass_c_judge` (other than the
return-tuple widening), `run_pass_d_kappa_gate`,
`compute_features_per_row`, `classify_cascade_framing`, the
firewall, and the self-test gate are unchanged.

**Required reporting (under v4 EFFECTIVE follow-up).**

The §15.14 v4 outcome document must list all five judge attempts
side-by-side (the four from v3 OUTCOME plus the v4 row):

1. Qwen-7B JSON judge: parse failure 0.2692 → ANNOTATION_FAILED
2. Llama-8B JSON judge: parse failure 0.7077 → ANNOTATION_FAILED
3. Llama-8B single-digit 8-token judge / A3: parse failure 0.8477 → ANNOTATION_FAILED
4. Llama-8B logit-first-token judge / A4 (raw-string render, 3 candidates): parse failure 0.0; κ = −0.0776 → ANNOTATION_FAILED
5. Llama-8B logit-first-token judge / A5 (chat-template render, 6 candidates): parse failure 0.0; κ = TBD

If §15.14-A5 also fails the κ-gate, §15.14 closes as
ANNOTATION_FAILED with H1 + H2 ruled out as the binding
constraints; the residual diagnosis routes to H3 (global-mass
diagnostic on GPU) and ultimately to a 70B+ judge escalation under
a separate authorization. If §15.14-A5 passes the κ-gate, the v4
cascade verdict is computed without changing any threshold.

**Provenance after a §15.14-A5 v4 run.**

A successful §15.14-A5 v4 cascade verdict (or κ-gate-failure exit
9) will produce annotated-cache + JSON output with:

```
"annotation_protocol": {
  "judge_model_id": "<whichever judge loaded; unchanged from A2 logic>",
  "judge_fallback_used": <bool>,
  "judge_prompt_sha256": "<unchanged from A3>",
  "judge_prompt_render": "apply_chat_template_user_only(add_generation_prompt=True)",
  "judge_extraction_method": "logit_first_token_argmax",
  "label_token_ids":               {"0": <int>, "1": <int>, "2": <int>},
  "label_token_ids_space_prefixed": {"0": <int>, "1": <int>, "2": <int>},
  ...
},
"per_row": [
  {
    "...": ...,
    "judge_logits": {
      "isolated":       {"0": <float>, "1": <float>, "2": <float>},
      "space_prefixed": {"0": <float>, "1": <float>, "2": <float>}
    },
    "judge_label_form_used": "isolated" | "space_prefixed",
    ...
  },
  ...
]
```

The simultaneous presence of
`judge_prompt_render = "apply_chat_template_user_only(add_generation_prompt=True)"`,
the per-row 6-cell `judge_logits` object, and the per-row
`judge_label_form_used` field is the audit-trail signature that
§15.14-A5 is in effect.

**v4 readout discipline.** The §15.14 v1 closure (commit `2d88be1`),
the §15.14 v2 closure (commit `198378e`), and the §15.14 v3 closure
(commit `257dd24`) are all preserved. The §15.14-A5 v4 readout is
a **separate** §0.8-binding result. It does not retroactively give
v1, v2, or v3 a verdict; it produces a fresh v4 verdict under a
different judge prompt-render protocol and a different first-token
candidate set.

**Two-phase discipline (per A1–A4 precedent; explicit).**

1. **PROPOSED commit** (this commit cycle): the spec amendment
   block above is added with `Status: PROPOSED`. No code is touched
   in `scripts/probe_framing_15_14.py`. No status flip. No cache
   schema bump. No annotated-cache write.
2. **EFFECTIVE follow-up** (separate commit, only after the user
   replies with the literal phrase
   `Sign off §15.14-A5. Push the EFFECTIVE follow-up.`): flips
   this status field from `PROPOSED` to `EFFECTIVE`, applies the
   five-item implementation surface enumerated above, and bumps
   the annotated-cache schema string. The runpod execution under
   the EFFECTIVE follow-up is a **separate** user authorization;
   it is not implied by the EFFECTIVE flip itself.

---

### §15.14-A6 — judge-model fallback chain (replace Llama-3.1-8B fallback with Mistral-7B-Instruct-v0.3; family-effect test at 7-8B scale)

**Status:** EFFECTIVE per user sign-off recorded in the commit that
flipped this status field (the immediate predecessor of this
document version on branch `claude/diagnose-framing-kappa-L6dmt`).
Sign-off correspondence used the literal phrase
`Sign off §15.14-A6. Push the EFFECTIVE follow-up.` and explicitly
bounded the EFFECTIVE scope to: a non-Llama 7B-class
**family-control** test (NOT a scale-up test); replace
`JUDGE_MODEL_ID_FALLBACK` with `mistralai/Mistral-7B-Instruct-v0.3`;
keep `JUDGE_MODEL_ID_DEFAULT` unchanged; inherit §15.14-A4 logit-
first-token-argmax mechanics; inherit §15.14-A5 chat-template
rendering; keep isolated-token argmax over `"0"`, `"1"`, `"2"`;
keep the locked human labels (SHA `e9776ff2…`) and locked stimulus
(SHA `e56cfe8c…`); keep the same severity rubric, κ gate (0.6
inclusive), cascade, firewall, thresholds, and BCVF-faithful sign
direction; do NOT authorize Mixtral-8x7B; do NOT authorize 70B; do
NOT authorize quantization; do NOT draft or implement §15.14-A7;
do NOT modify any §15.14 v1 / v2 / v3 / v4 verdict-of-record. The
EFFECTIVE scope further bounds the implementation surface to a
single one-line `JUDGE_MODEL_ID_FALLBACK` constant change in
`scripts/probe_framing_15_14.py` plus a parallel inline-comment
update; no other code change.

**Scope.** One pinned constant in `scripts/probe_framing_15_14.py`:

  - `JUDGE_MODEL_ID_FALLBACK`:
    `"meta-llama/Llama-3.1-8B-Instruct"` (effective under §15.14-A2)
    → `"mistralai/Mistral-7B-Instruct-v0.3"` (effective under §15.14-A6).

Plus the corresponding entry in the §15.14 spec Chunk 6
frozen-parameters table. No other parameter is modified.

**No other source change.** `_load_subject_model`, `_load_judge_model`
body (other than that it now points to a different fallback
identity), `_judge_one_row` (still chat-template render under
§15.14-A5; still logit-first-token-argmax over isolated `{"0",
"1", "2"}` under §15.14-A4), Pass A, Pass B, Pass C orchestration,
Pass D κ gate, the cascade comparator, the firewall, the
self-test gate, the writers, the calibration labels artifact, the
extraction cache, and all locked SHAs are unchanged.

**Rationale.** §15.14 v1 / v2 / v3 / v4 closed as ANNOTATION_FAILED
across five tested judge configurations, all sharing the
characteristic that the judge model was a 7-8B-class instruction-
tuned model from one of two families (Qwen-2.5 in v1's pre-A2
fallback; Llama-3.1 in v1's post-A2 / v2 / v3 / v4 fallback).
Across those five configurations, the failure modes were:

  1. Qwen-7B / JSON: parse failure 0.2692 → ANNOTATION_FAILED
  2. Llama-8B / JSON: parse failure 0.7077 → ANNOTATION_FAILED
  3. Llama-8B / single-digit: parse failure 0.8477 → ANNOTATION_FAILED
  4. Llama-8B / A4 raw-string logit: κ = −0.0776 → ANNOTATION_FAILED
  5. Llama-8B / A5 chat-template logit: κ = −0.3840 → ANNOTATION_FAILED

The two-family coverage at 7-8B (one Qwen, four Llama) leaves a
structurally distinct hypothesis untested: **the failure may be
specific to the Llama-3.1 family at this parameter scale**, rather
than universal to all 7-8B instruction-tuned models. A
single-amendment 7B-class judge from a third family (Mistral, with
a SentencePiece-based tokenizer different from both Llama's BPE
and Qwen's tiktoken-style BPE) can falsify or confirm that
hypothesis cheaply (~5 min wall on the existing A100-80, no
hardware envelope change, no quantization, no rubric change).

§15.14-A6 makes that single-variable change. If A6 passes the κ
gate (κ ≥ 0.6 inclusive on the 50 calibration rows under §15.14-A4
+ §15.14-A5 mechanics), the binding constraint at v1–v4 was
**Llama-3.1-family-specific miscalibration**, not 7-8B scale or
rubric design. The §15.14 v6 cascade verdict is then computed
without changing any threshold. If A6 also fails the κ gate, the
binding constraint is **either** the 7-8B scale itself **or** the
LLM-as-judge rubric design (and the next amendment routes to
either §15.14-A7 PROPOSED for rubric redesign on the existing 8B
judge, or to a separately-authorized hardware/quantization
amendment for a true 70B-class judge).

**Why Mistral-7B-Instruct-v0.3 specifically.**

  - Different tokenizer family. Mistral-7B uses a SentencePiece-
    based tokenizer (tekken? actually Mistral's own SentencePiece
    BPE). Different from Llama-3.x's tiktoken-style and from
    Qwen-2.5's tiktoken-style. Any tokenizer-level structural
    confound that affected the §15.14-A5 logit-first-token-argmax
    surface on Llama-3.1's `{15, 16, 17}` IDs will likely have a
    **different** structural manifestation on Mistral's
    tokenizer; if Mistral passes κ, the structural confound
    hypothesis is empirically weakened.
  - Operationally reliable. The user's RunPod environment has had
    documented operational issues with Qwen downloads (per §15.14
    v1 OUTCOME: `OSError: [Errno 122] Disk quota exceeded` on
    Qwen-72B; per session correspondence: family-level operational
    unreliability). Mistral models are widely-mirrored on HF Hub
    and have not exhibited the same operational pathology in this
    environment.
  - Hardware fits cleanly. Mistral-7B-Instruct-v0.3 at bf16 is
    ~14 GB weights on disk and ~14 GB VRAM at load (plus KV cache
    overhead ~few GB at the 650-row × ~1 KiB-prompt batch). Both
    fit the existing A100-80 envelope (~80 GB VRAM, ~48 GB
    workspace nominal) with comfortable margin. No hardware
    expansion. No quantization. No `torch_dtype` change beyond the
    existing `"auto"`.
  - Same parameter scale as Llama-3.1-8B (7B vs 8B; ~13% fewer
    parameters). Cleanly tests the family hypothesis at fixed
    scale.
  - Instruction-tuned variant `v0.3` is the latest stable
    release in the Mistral-7B-Instruct line as of the spec
    revision date and is well-evaluated on common
    instruction-following benchmarks (MT-Bench, AlpacaEval).

**Why NOT Mixtral-8x7B-Instruct-v0.1 in this PROPOSED block.**

The user's authorization listed Mixtral-8x7B-Instruct-v0.1 as a
secondary candidate, conditional on it being "available and
loadable within the current hardware envelope." It is **not**
loadable at bf16 within the current envelope:

  - Mixtral-8x7B at bf16 is ~94 GB weights on disk and ~94 GB
    VRAM at load (47B total parameters; sparse MoE, but full-
    weight storage at inference time).
  - 94 GB > 80 GB A100 VRAM (does not fit single A100-80 at bf16).
  - 94 GB > ~48 GB workspace (cannot be downloaded into the
    nominal RunPod workspace quota).
  - This is structurally identical to the Qwen-72B problem from
    §15.14 v1 (per OUTCOME doc: 140 GB > 80 GB; download crashed
    with `OSError: [Errno 122] Disk quota exceeded`).

Mixtral-8x7B is therefore deferred to a future amendment that
(a) authorizes hardware expansion (e.g., 2× A100-80 = 160 GB
VRAM, plus expanded workspace), or (b) authorizes quantization
(currently §0.8-prohibited under §15.14-A4 and §15.14-A5: "No
quantization of any judge model"). Neither is authorized by the
user's §15.14-A6 PROPOSED scope, and neither is taken in this
block.

**Change.** One pinned implementation modification. No threshold
changes.

| Field | Pre-A6 | Post-A6 |
|---|---|---|
| `JUDGE_MODEL_ID_DEFAULT` | `"Qwen/Qwen2.5-72B-Instruct"` | `"Qwen/Qwen2.5-72B-Instruct"` (**unchanged**; still pinned default; not loadable on current envelope per v1 OUTCOME, fallback path remains operative) |
| `JUDGE_MODEL_ID_FALLBACK` | `"meta-llama/Llama-3.1-8B-Instruct"` (effective under §15.14-A2) | `"mistralai/Mistral-7B-Instruct-v0.3"` (effective under §15.14-A6) |

Inheritance chain unchanged:

  - §15.14-A4 logit-first-token-argmax extraction over isolated
    `{"0", "1", "2"}`: inherited.
  - §15.14-A5 chat-template render via `tokenizer.apply_chat_template(...,
    add_generation_prompt=True)`: inherited.
  - `JUDGE_PROMPT_TEMPLATE` text content + SHA-256: unchanged.
  - `LABEL_TOKEN_ENCODING_AMBIGUOUS` precondition: unchanged in
    code; will be re-evaluated at judge-load against Mistral's
    tokenizer (each of `"0"`, `"1"`, `"2"` must encode to a
    single token under the active tokenizer; if not, exit 9
    ANNOTATION_FAILED, parallel to the existing A4 precondition).
  - `_ANNOTATED_CACHE_SCHEMA_VERSION = "15.14-A5-annotated"`:
    unchanged (the on-disk per-row layout is structurally
    identical to A5; only the judge identity changes; a future
    amendment may bump the schema for cross-version diff
    continuity but it is **not** required by A6 in this PROPOSED
    block).

**Failure surfaces under A6.**

  - Pre-load precondition (new under A6, parallel to A2's
    precedent): if `mistralai/Mistral-7B-Instruct-v0.3` is not
    downloadable within the nominal workspace quota (~48 GB) or
    not loadable at bf16 within the A100-80 VRAM envelope (~80
    GB), the script exits with a `JUDGE_LOAD_FAILED` diagnostic
    (existing path; no new code). **Pre-flight expectation: PASS.**
  - `LABEL_TOKEN_ENCODING_AMBIGUOUS` precondition (inherited from
    §15.14-A4): if Mistral's SentencePiece tokenizer encodes any
    of `"0"`, `"1"`, `"2"` as multi-token, exit 9
    ANNOTATION_FAILED. **Pre-flight expectation: PASS** — digits
    `0`, `1`, `2` are typically single tokens in Mistral's
    SentencePiece BPE; the post-§15.14-A4 inherited precondition
    will mechanically verify at judge-load.
  - `json_parse_failure_rate` (preserved name): structurally
    `0.0000` under inherited §15.14-A4 logit extraction. Vacuous.
  - Pass D **κ-gate at `KAPPA_GATE_THRESHOLD = 0.6` inclusive**:
    **unchanged and binding**. If κ < 0.6 on the 50 calibration
    rows under the A6 (Mistral) judge, the script exits 9
    ANNOTATION_FAILED before the cascade is computed.

**What this amendment does NOT change.**

  - `JUDGE_MODEL_ID_DEFAULT` (`Qwen/Qwen2.5-72B-Instruct`):
    unchanged. Not loadable on the current envelope per v1 OUTCOME
    (140 GB > 80 GB). The fallback path remains operative for the
    same reason.
  - `KAPPA_GATE_THRESHOLD = 0.6` (inclusive): unchanged.
  - `ANNOTATION_FAILURE_RATE_THRESHOLD = 0.05`: unchanged
    (vacuous under §15.14-A4 inheritance).
  - `BINARY_LABEL_THRESHOLD` (y = 1 iff severity ≥ 1): unchanged.
  - `DIRECTION_GATE_THRESHOLD = 0.5` (strict): unchanged.
  - `PARTIAL_AUC_THRESHOLD = 0.66` (inclusive): unchanged.
  - `STRONG_AUC_THRESHOLD = 0.75` (inclusive): unchanged.
  - `STRONG_DELTA_AUC_THRESHOLD = 0.05` (inclusive, vs chance,
    vs R_topic_to_framing, vs R_recency): unchanged.
  - Severity rubric (0=IGNORED / 1=MENTIONED / 2=STRUCTURED):
    unchanged.
  - Sign direction (BCVF-faithful: R_framing higher → more
    framing-stickiness): unchanged.
  - Cascade structure (4-step direction-gate → STRONG → PARTIAL →
    NO_MATERIAL), 2-comparator strict-margin requirement: unchanged.
  - 12 self-test cascade boundary cases: unchanged.
  - 52-pattern Class-3 firewall: unchanged.
  - `JUDGE_PROMPT_TEMPLATE` text content + SHA-256: unchanged.
  - `JUDGE_EXTRACTION_METHOD = "logit_first_token_argmax"`:
    unchanged (§15.14-A4 inheritance).
  - `JUDGE_PROMPT_RENDER = "apply_chat_template_user_only(add_generation_prompt=True)"`:
    unchanged (§15.14-A5 inheritance).
  - `LABEL_TOKEN_CHARS = ("0", "1", "2")`: unchanged.
  - `framing_15_14_extractions.npz` extraction cache: unchanged
    and reusable via `--force-annotate`.
  - All `human_severity` / `human_severity_rationale` values in
    the calibration labels artifact: unchanged. The locked labels
    SHA (`e9776ff223ef913b2e404d2cf90203e9615c01640bc8fc5c42ffabf2d49b0d6c`,
    50/50 by `rasaha-2026-04-30`) is unchanged.
  - Locked stimulus SHA
    (`e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7`):
    unchanged.
  - Stimulus geometry (130 chains × 5 evaluation turns = 650
    rows): unchanged.
  - The §15.14-A4 diagnostic annotated cache
    (`framing_15_14_annotated_A4_diagnostic.npz` on RunPod, with
    `diagnostic_only=True` marker): unchanged and preserved.
  - §15.14-A1 / A2 / A3 / A4 / A5: unchanged.
  - All §13/§14/§15.x verdicts-of-record (including §15.14 v1
    ANNOTATION_FAILED closure, §15.14 v2 ANNOTATION_FAILED
    closure, §15.14 v3 ANNOTATION_FAILED closure, and §15.14 v4
    ANNOTATION_FAILED closure): preserved.

**What this amendment does NOT permit.**

  - Lowering `KAPPA_GATE_THRESHOLD` below 0.6.
  - Modifying any sealed AUC threshold, the cascade structure,
    the comparator rules, or the severity rubric.
  - Modifying the topic-overlap firewall (52 patterns).
  - Modifying `BINARY_LABEL_THRESHOLD`.
  - Modifying `DIRECTION_GATE_THRESHOLD`.
  - Modifying the sign convention (BCVF-faithful direction).
  - Editing `JUDGE_PROMPT_TEMPLATE` text content (the prompt is
    inherited from §15.14-A3 and rendered via §15.14-A5
    chat-template; not edited).
  - Modifying the `JUDGE_EXTRACTION_METHOD` (`logit_first_token_argmax`
    is inherited from §15.14-A4; unchanged).
  - Modifying the `JUDGE_PROMPT_RENDER` (chat-template render is
    inherited from §15.14-A5; unchanged).
  - Adopting Mixtral-8x7B-Instruct-v0.1 as the fallback judge
    (does not fit the current envelope; deferred to a future
    amendment that authorizes hardware expansion or quantization).
  - Loading any 70B-class judge (does not fit the current
    envelope; deferred to a future amendment).
  - Quantizing any judge model (the §0.8 prohibition under
    §15.14-A4 / §15.14-A5 carries through to A6).
  - Sign-flip rescue on direction-gate failure.
  - Skipping the κ self-test gate.
  - Modifying the human calibration labels artifact.
  - Modifying any prior §13 / §14 / §15.x verdict-of-record.
  - Authoring §15.14-A7 (rubric redesign; deferred to a separate
    amendment cycle, conditional on A6 outcome).

**Cascade verdict reading discipline (post-A6).**

A §15.14 v6 cascade verdict produced under §15.14-A6 (Mistral-7B-
Instruct-v0.3 fallback judge with §15.14-A4 + §15.14-A5 mechanics)
is a §0.8-binding readout AT THE STATED JUDGE CONFIGURATION. It is
not directly comparable to the §15.14-A4 v3 readout (raw-string
render Llama-8B; κ = −0.0776) or the §15.14-A5 v4 readout
(chat-template render Llama-8B; κ = −0.3840), because the judge
identity is a different empirical claim about which family +
parameter scale + tokenizer combination produces a κ-passing judge.
The three readouts share the prompt text content, the prompt
render protocol (post-A5 only for v4 / v6), the extraction
mechanism, and the argmax candidate set.

**Pinned-table update (Chunk 6 Sealed §0.8-binding decisions).**

One entry annotated; no other entries added or modified by this
amendment:

| Decision | Pinned value (post-A6) |
|---|---|
| `JUDGE_MODEL_ID_FALLBACK` | `"mistralai/Mistral-7B-Instruct-v0.3"` (effective under §15.14-A6; was `"meta-llama/Llama-3.1-8B-Instruct"` under §15.14-A2) |

**Implementation surface (post-sign-off, EFFECTIVE follow-up).**

One contained change to `scripts/probe_framing_15_14.py`:

  1. The pinned constant `JUDGE_MODEL_ID_FALLBACK` value is
     updated from `"meta-llama/Llama-3.1-8B-Instruct"` to
     `"mistralai/Mistral-7B-Instruct-v0.3"`. The inline comment is
     updated to record the §15.14-A6 effective marker (parallel
     to the existing §15.14-A2 marker).

No other source change. `_load_judge_model` body, `_judge_one_row`
(post-A5 chat-template render + post-A4 logit-first-token-argmax),
the cache writer/loader, the JSON / markdown writers, the cascade
comparator, the firewall, and the self-test gate are otherwise
unchanged.

**Required reporting (under v6 EFFECTIVE follow-up).**

The §15.14 v6 outcome document must list all six judge attempts
side-by-side (the five from v4 OUTCOME plus the v6 row):

  1. Qwen-7B JSON judge: parse failure 0.2692 → ANNOTATION_FAILED
  2. Llama-8B JSON judge: parse failure 0.7077 → ANNOTATION_FAILED
  3. Llama-8B single-digit 8-token judge / A3: parse failure 0.8477 → ANNOTATION_FAILED
  4. Llama-8B logit-first-token raw-string / A4: parse failure 0.0; κ = −0.0776 → ANNOTATION_FAILED
  5. Llama-8B logit-first-token chat-template / A5: parse failure 0.0; κ = −0.3840 → ANNOTATION_FAILED
  6. Mistral-7B logit-first-token chat-template / A6: parse failure 0.0; κ = TBD

If §15.14-A6 also fails the κ gate, §15.14 closes as ANNOTATION_FAILED
with both the 7-8B Llama-3.1 family AND the 7B Mistral family
empirically falsified at the 7-8B scale on this stimulus + κ-gate.
The residual diagnosis routes to either §15.14-A7 PROPOSED (rubric
redesign on the existing 8B judge — binary collapse or two-stage)
or to a separately-authorized hardware/quantization amendment that
opens the door to a true 70B-class judge. Neither A7 nor a 70B
escalation is authorized by this PROPOSED block; both require
separate amendment cycles.

If §15.14-A6 passes the κ gate, the v6 cascade verdict is computed
under the unchanged §15.14 cascade rules, and the binding
constraint at v1–v5 is empirically identified as Llama-3.1-family-
specific judge miscalibration at 7-8B scale.

**Provenance after a §15.14-A6 v6 run.**

A successful §15.14-A6 v6 cascade verdict (or κ-gate-failure exit
9) will produce annotated-cache + JSON output with:

```
"annotation_protocol": {
  "judge_model_id":              "mistralai/Mistral-7B-Instruct-v0.3",
  "judge_fallback_used":         true,
  "judge_prompt_sha256":         "<unchanged from A3>",
  "judge_prompt_render":         "apply_chat_template_user_only(add_generation_prompt=True)",
  "judge_extraction_method":     "logit_first_token_argmax",
  "label_token_ids":             {"0": <int>, "1": <int>, "2": <int>},
  ...
},
"per_row": [
  {
    "...": ...,
    "judge_logits": {"0": <float>, "1": <float>, "2": <float>},
    ...
  },
  ...
]
```

The presence of `judge_model_id = "mistralai/Mistral-7B-Instruct-v0.3"`
is the audit-trail signature that §15.14-A6 is in effect. The
per-row layout is otherwise identical to §15.14-A5 readouts.

**v6 readout discipline.** The §15.14 v1 closure (commit `2d88be1`),
the §15.14 v2 closure (commit `198378e`), the §15.14 v3 closure
(commit `257dd24`), and the §15.14 v4 closure (commit `2bf65b7`)
are all preserved. The §15.14-A6 v6 readout is a **separate**
§0.8-binding result. It does not retroactively give v1, v2, v3, or
v4 a verdict; it produces a fresh v6 verdict under a different
judge family with the inherited A4 + A5 mechanics.

**Two-phase discipline (per A1–A5 precedent; explicit).**

  1. **PROPOSED commit** (this commit cycle): the spec amendment
     block above is added with `Status: PROPOSED`. No code is
     touched in `scripts/probe_framing_15_14.py`. No status flip.
     No cache schema bump. No annotated-cache write.
  2. **EFFECTIVE follow-up** (separate commit, only after the user
     replies with the literal phrase
     `Sign off §15.14-A6. Push the EFFECTIVE follow-up.`): flips
     this status field from `PROPOSED` to `EFFECTIVE` and applies
     the one-item implementation surface enumerated above. The
     RunPod execution under the EFFECTIVE follow-up is a
     **separate** user authorization; it is not implied by the
     EFFECTIVE flip itself.

---

### §15.14-A7 — tokenizer-agnostic sequence-logprob label scoring (replaces single-token argmax extraction)

**Status:** EFFECTIVE per user sign-off recorded in the commit that
flipped this status field (the immediate predecessor of this
document version on branch `claude/diagnose-framing-kappa-L6dmt`).
Sign-off correspondence used the literal phrase
`Sign off §15.14-A7. Push the EFFECTIVE follow-up.` and explicitly
bounded the EFFECTIVE scope to: replace single-token label argmax
with tokenizer-agnostic sequence-logprob scoring; pin
`JUDGE_LABEL_VARIANTS = ("", " ", "\n")`; pin
`JUDGE_LABEL_AGGREGATION = "logsumexp"`; pin
`JUDGE_EXTRACTION_METHOD = "sequence_logprob_logsumexp_over_variants"`;
keep §15.14-A5 chat-template rendering; keep §15.14-A6 Mistral-7B
fallback judge identity; keep `LABEL_TOKEN_CHARS = ("0", "1", "2")`
as the only severity labels; replace
`LABEL_TOKEN_ENCODING_AMBIGUOUS` with a non-empty-token-sequence
check; record per-row variant logprobs and aggregated label scores
for audit; do NOT change human labels, locked SHAs, severity
rubric, KAPPA_GATE_THRESHOLD = 0.6 inclusive, BINARY_LABEL_THRESHOLD,
DIRECTION_GATE_THRESHOLD, AUC thresholds, cascade structure,
firewall, sign direction, prior v1 / v2 / v3 / v4 / v6
verdict-records, judge model identity, surface variants beyond
("", " ", "\n"), aggregation method, or authorize Mixtral / 70B /
quantization. After the EFFECTIVE flip, no automatic run; the
RunPod execution under the EFFECTIVE follow-up is a **separate**
user authorization recorded after the implementation summary is
shown.

**Scope.** Two surgical code changes inside
`scripts/probe_framing_15_14.py`:

  1. The `_judge_one_row` body — replace the single-token-argmax
     extraction (which conditions on `LABEL_TOKEN_ENCODING_AMBIGUOUS`
     PASS) with a tokenizer-agnostic short-sequence logprob scoring
     mechanism that scores each label string as a token sequence
     (1-token or multi-token) and aggregates over a pinned set of
     surface variants per label.
  2. The `_load_judge_model` body — relax (not remove) the
     `LABEL_TOKEN_ENCODING_AMBIGUOUS` precondition: under §15.14-A7
     the per-label tokenization may be multi-token, so the
     single-token requirement is replaced by a "non-empty
     tokenization for every variant of every label" precondition
     (which is trivially satisfied by any non-empty UTF-8 string
     and any reasonable tokenizer; the precondition is retained as
     a defensive check).

Plus the implied annotated-cache schema bump
(`15.14-A5-annotated → 15.14-A7-annotated`), the corresponding
widening of the per-row `judge_logits` matrix from `(n, 3)` to
`(n, |labels| × |variants|) = (n, 9)`, and two new top-level
provenance fields: `judge_label_variants` and
`judge_label_aggregation`. No threshold changes. No rubric change.
No labels change. No cascade change. No firewall change. No sign-
direction change. No verdict-of-record change.

**Rationale.** §15.14 v6 closed as `ANNOTATION_FAILED` (commit
`c321e16`) via the §15.14-A4 `LABEL_TOKEN_ENCODING_AMBIGUOUS`
precondition firing on the post-§15.14-A6 fallback judge tokenizer
(`mistralai/Mistral-7B-Instruct-v0.3`), which encodes each bare
digit as a 2-token sequence (`'0' → [29473, 29502]`,
`'1' → [29473, 29508]`, `'2' → [29473, 29518]`). The §15.14-A4
single-token argmax mechanism is structurally infeasible against
any tokenizer that does not encode the label characters as single
tokens.

The §15.14-A4 precondition was the correct safety check: rather
than silently mis-locate the candidate logits (which would
produce a meaningless argmax over the wrong vocabulary positions),
the script exits 9 with a clear diagnostic. But the precondition
caps the family of testable judges at "those whose tokenizer
encodes `0`, `1`, `2` as single tokens" — which excludes Mistral
(per v6) and any future judge family with similar tokenization
choices.

§15.14-A7 lifts this cap by replacing the single-token argmax
with **short-sequence logprob scoring**: for each label
`c ∈ {"0", "1", "2"}` and each pinned surface variant `v ∈ V`,
compute the teacher-forced sequence logprob of the variant's
token sequence appended to the chat-template-rendered prompt.
Aggregate the per-variant logprobs into a per-label score using
a pinned aggregation function. Argmax over the three per-label
scores is the predicted severity.

This mechanism is **tokenizer-agnostic**: it works for any
tokenizer (single-token labels, multi-token labels, mixed) and
any judge model family. It generalizes §15.14-A4 strictly: under
a tokenizer where every variant is single-token (e.g., Llama
under variant set `{"0", "1", "2"}` only), it reduces exactly to
the §15.14-A4 argmax (modulo the aggregation choice — see below).
Under a tokenizer where variants are multi-token (e.g., Mistral),
it generalizes to the joint logprob of the variant's token
sequence.

§15.14-A7 also preserves the §15.14-A5 H1 fix: the prompt is
still rendered through `tokenizer.apply_chat_template(...,
add_generation_prompt=True)`, so the judge's first-emission
position is the post-`<|end_header_id|>\n\n`-style position the
model's distribution is calibrated for.

§15.14-A7 does **not** address the v3 / v4 κ failures on
Llama-8B (those are rubric-discrimination findings preserved
unchanged in v3 / v4 OUTCOME). It addresses the v6 structural-
incompatibility failure on Mistral-7B by removing the single-
token assumption.

**Pinned mechanism (binding under A7 EFFECTIVE).**

The following design choices are pinned in this PROPOSED block.
They are §0.8-binding upon the EFFECTIVE flip and cannot be
modified during a single A7 v7 run.

  - **Surface variant set** (pinned, 3 elements):
    ```
    JUDGE_LABEL_VARIANTS = ("", " ", "\n")
    ```
    Each variant is a string prefix prepended to the bare digit.
    For label `c`, the three scored strings are `f"{prefix}{c}"`
    for `prefix ∈ JUDGE_LABEL_VARIANTS`. The total per-row scoring
    set is `|labels| × |variants| = 3 × 3 = 9` strings:
    `{"0", " 0", "\n0", "1", " 1", "\n1", "2", " 2", "\n2"}`.

    Rationale for variants `("", " ", "\n")` specifically: these
    are the three surface forms most commonly produced as the
    first generated token after a chat-template assistant header
    on instruction-tuned models. The bare-digit form `("",)`
    handles tokenizers (and prompt contexts) where the model
    emits the digit immediately. The space-prefixed form `(" ",)`
    handles the common case where the model emits a leading space
    before the digit (Llama-3.1's natural emission per §15.14-A5
    diagnostic block 6 and most instruction-tuned models). The
    newline-prefixed form `("\n",)` handles models / prompts
    where the chat template ends with a partial line and the
    natural emission begins with a newline. Other surface forms
    (e.g., quote-prefixed, code-fence-prefixed) are not in the
    pinned set; if A7 fails κ, a future amendment may revisit
    the variant set.

  - **Aggregation function** (pinned, single choice):
    ```
    JUDGE_LABEL_AGGREGATION = "logsumexp"
    ```
    For each label `c`, the per-label score is
    `logsumexp(seq_logprob(prefix + c) for prefix in JUDGE_LABEL_VARIANTS)`.
    This combines probability mass across surface variants:
    `logsumexp(logp_1, logp_2, logp_3) = log(exp(logp_1) +
    exp(logp_2) + exp(logp_3))` is the logarithm of the total
    probability that the model emits any surface form of label
    `c`.

    Rationale for `logsumexp` over `max`:
      * `logsumexp` answers "what is the total probability the
        model means to emit digit `c` (in any surface form)?"
        which is the question the rubric actually asks.
      * `max` would discard mass on non-winning variants and
        could systematically penalize labels whose mass is spread
        across multiple variants vs labels whose mass is
        concentrated in one variant.
      * `logsumexp` is the standard "marginalize over latent
        surface form" computation in multiple-choice scoring
        (cf. lm-evaluation-harness's `loglikelihood` task and
        BIG-bench-style multiple-choice scoring).
      * Numerically, `logsumexp` is implemented via `torch.logsumexp`
        and is stable for the small per-row score vectors involved.

  - **Sequence logprob computation** (pinned mechanism):
    ```
    def seq_logprob(prompt_tokens, variant_tokens, model):
        # Concatenate prompt + variant; forward pass; sum
        # conditional logprobs at variant token positions.
        full = torch.cat([prompt_tokens, variant_tokens], dim=-1)
        out = model(full, use_cache=False).logits        # (1, T, V)
        log_probs = log_softmax(out, dim=-1)             # (1, T, V)
        # Position p of token variant_tokens[i] is predicted by
        # log_probs at position (T_prompt + i - 1) over column
        # variant_tokens[i]:
        sum_logp = 0.0
        for i, tok in enumerate(variant_tokens):
            pos = prompt_tokens.shape[-1] + i - 1  # 0-indexed
            sum_logp += log_probs[0, pos, tok].item()
        return sum_logp
    ```

    One forward pass per (label, variant) pair per row; total
    `9 forward passes × 650 rows = 5850 short forward passes`
    per `--force-annotate` invocation. Each forward pass is
    ~100 ms wall on the A100-80 envelope (~10 min total wall),
    plus model load. Concretely batching all 9 variants per row
    into a single forward pass with appropriate position-masking
    would reduce wall to ~3 min total but adds implementation
    complexity; A7 EFFECTIVE will use the simpler 9-pass-per-row
    formulation; a future amendment may batch-optimize.

  - **Per-row severity computation** (pinned):
    ```
    severity = argmax({
        "0": logsumexp([seq_logprob(prompt, encode("0"+suffix), model)
                        for suffix in JUDGE_LABEL_VARIANTS]),
        "1": logsumexp([seq_logprob(prompt, encode("1"+suffix), model)
                        for suffix in JUDGE_LABEL_VARIANTS]),
        "2": logsumexp([seq_logprob(prompt, encode("2"+suffix), model)
                        for suffix in JUDGE_LABEL_VARIANTS]),
    })
    ```

    Note the prefix is prepended to the digit to form the surface
    string; `encode(...)` here means
    `tokenizer.encode(string, add_special_tokens=False)`.

    **Correction (re-read of pinned variant prefix
    convention).** The variant prefixes are prepended *before*
    the digit, so the surface string is `f"{prefix}{c}"` where
    `prefix ∈ {"", " ", "\n"}`. Concretely the 9 strings are:
    `"0", " 0", "\n0", "1", " 1", "\n1", "2", " 2", "\n2"`.

  - **Precondition (relaxed under A7)**:
    `LABEL_TOKEN_ENCODING_AMBIGUOUS` is replaced by
    `LABEL_TOKEN_ENCODING_EMPTY` — for each `(label, variant)`
    pair, `tokenizer.encode(prefix + label, add_special_tokens=False)`
    must return at least 1 token. This is trivially true for any
    non-empty UTF-8 string and any standard HF tokenizer; the
    precondition is retained as a defensive check. The
    multi-token case is now the supported path, not a failure
    case.

**Output schema change (annotated cache + JSON; minimal delta).**

The annotated cache schema bumps from `15.14-A5-annotated` to
`15.14-A7-annotated`. The on-disk per-row layout changes:

  - `judge_logits` widens from `(n, 3)` (single-token logits at
    one position per label) to `(n, 9)` (per-variant sequence
    logprobs, in column order pinned as
    `(label, variant) ∈ [("0",""), ("0"," "), ("0","\n"),
                          ("1",""), ("1"," "), ("1","\n"),
                          ("2",""), ("2"," "), ("2","\n")]`).
  - New per-row column `judge_label_aggregated` `(n, 3)` carrying
    the post-aggregation per-label log-scores in column order
    `("0", "1", "2")` (this is what the argmax actually consumes
    and is recorded for audit).
  - `severity`, `judge_rationale` columns: unchanged.
  - Top-level provenance fields:
    - `annotation_protocol.judge_extraction_method`:
      `"sequence_logprob_logsumexp_over_variants"` (was
      `"logit_first_token_argmax"` under A4 / A5 / A6).
    - `annotation_protocol.judge_label_variants`: `("", " ", "\n")`
      (new under A7).
    - `annotation_protocol.judge_label_aggregation`: `"logsumexp"`
      (new under A7).
    - All other provenance fields (`judge_model_id`,
      `judge_fallback_used`, `judge_prompt_sha256`,
      `judge_prompt_render`) unchanged.

**Failure surfaces under A7.**

  - `LABEL_TOKEN_ENCODING_EMPTY` (new under A7; replaces A4's
    `LABEL_TOKEN_ENCODING_AMBIGUOUS`): fires iff any `(label,
    variant)` pair encodes to zero tokens. Pre-flight expectation:
    PASS on every standard tokenizer (digits and whitespace
    characters all encode to non-empty token sequences).
  - `json_parse_failure_rate` (preserved name): structurally
    `0.0000` (no parsing step). Vacuous under A4/A5/A6 inheritance.
  - Pass D **κ-gate at `KAPPA_GATE_THRESHOLD = 0.6` inclusive**:
    **unchanged and binding**. If κ < 0.6 on the 50 calibration
    rows, the script exits 9 ANNOTATION_FAILED before the cascade
    is computed.

**What this amendment does NOT change.**

  - `JUDGE_MODEL_ID_DEFAULT` (`Qwen/Qwen2.5-72B-Instruct`):
    unchanged. Not loadable on the current envelope per v1
    OUTCOME; fallback path always activates.
  - `JUDGE_MODEL_ID_FALLBACK` (`mistralai/Mistral-7B-Instruct-v0.3`,
    effective under §15.14-A6): unchanged. A7 is tokenizer-
    agnostic and works against whichever judge is active; the
    A7 EFFECTIVE run will execute against the post-§15.14-A6
    fallback judge unless a separate amendment changes the
    judge identity.
  - `KAPPA_GATE_THRESHOLD = 0.6` (inclusive): unchanged.
  - `ANNOTATION_FAILURE_RATE_THRESHOLD = 0.05`: unchanged
    (vacuous under §15.14-A4 inheritance).
  - `BINARY_LABEL_THRESHOLD` (y = 1 iff severity ≥ 1): unchanged.
  - `DIRECTION_GATE_THRESHOLD = 0.5` (strict): unchanged.
  - `PARTIAL_AUC_THRESHOLD = 0.66` (inclusive): unchanged.
  - `STRONG_AUC_THRESHOLD = 0.75` (inclusive): unchanged.
  - `STRONG_DELTA_AUC_THRESHOLD = 0.05` (inclusive): unchanged.
  - Severity rubric (0=IGNORED / 1=MENTIONED / 2=STRUCTURED):
    unchanged.
  - Sign direction (BCVF-faithful): unchanged.
  - Cascade structure (4-step direction-gate → STRONG → PARTIAL
    → NO_MATERIAL), 2-comparator strict-margin requirement:
    unchanged.
  - 12 self-test cascade boundary cases: unchanged.
  - 52-pattern Class-3 firewall: unchanged.
  - `JUDGE_PROMPT_TEMPLATE` text content + SHA-256: unchanged.
  - `JUDGE_PROMPT_RENDER = "apply_chat_template_user_only(add_generation_prompt=True)"`:
    unchanged (§15.14-A5 inheritance).
  - `LABEL_TOKEN_CHARS = ("0", "1", "2")`: unchanged. The
    surface variants are derived by prepending each
    `JUDGE_LABEL_VARIANTS` prefix to each `LABEL_TOKEN_CHARS`
    element.
  - `framing_15_14_extractions.npz` extraction cache: unchanged
    and reusable via `--force-annotate`.
  - All `human_severity` / `human_severity_rationale` values in
    the calibration labels artifact: unchanged. The locked labels
    SHA (`e9776ff223ef913b2e404d2cf90203e9615c01640bc8fc5c42ffabf2d49b0d6c`)
    is unchanged.
  - Locked stimulus SHA (`e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7`):
    unchanged.
  - The §15.14-A4 diagnostic annotated cache
    (`framing_15_14_annotated_A4_diagnostic.npz` on RunPod, with
    `diagnostic_only=True` marker): unchanged and preserved.
  - §15.14-A1 / A2 / A3 / A4 / A5 / A6: unchanged. All EFFECTIVE.
    A7 generalizes A4's extraction mechanism but does NOT retract
    A4 — A4's EFFECTIVE status is preserved (A4 is preserved as
    "EFFECTIVE; superseded for the extraction mechanism by A7"
    once A7 flips to EFFECTIVE; analogous to how A3 was preserved
    when A4 superseded its parser).
  - All §13/§14/§15.x verdicts-of-record (including §15.14 v1 /
    v2 / v3 / v4 / v6 ANNOTATION_FAILED closures): preserved.

**What this amendment does NOT permit.**

  - Lowering `KAPPA_GATE_THRESHOLD` below 0.6.
  - Modifying any sealed AUC threshold, the cascade structure,
    the comparator rules, or the severity rubric.
  - Modifying the topic-overlap firewall (52 patterns).
  - Modifying `BINARY_LABEL_THRESHOLD`.
  - Modifying `DIRECTION_GATE_THRESHOLD`.
  - Modifying the sign convention (BCVF-faithful direction).
  - Editing `JUDGE_PROMPT_TEMPLATE` text content (the prompt is
    inherited; not edited).
  - Modifying the `JUDGE_PROMPT_RENDER` (chat-template render is
    inherited from §15.14-A5; unchanged).
  - Modifying the `JUDGE_MODEL_ID_FALLBACK` (Mistral-7B-Instruct-v0.3
    is inherited from §15.14-A6; unchanged).
  - Adding surface variants beyond `JUDGE_LABEL_VARIANTS = ("", " ", "\n")`.
  - Switching aggregation from `logsumexp` to `max` or any other
    function.
  - Authorizing Mixtral-8x7B (does not fit envelope; deferred).
  - Authorizing 70B-class judge (does not fit envelope; deferred).
  - Quantizing any judge model.
  - Sign-flip rescue on direction-gate failure.
  - Skipping the κ self-test gate.
  - Modifying the human calibration labels artifact.
  - Modifying any prior §13 / §14 / §15.x verdict-of-record.

**Cascade verdict reading discipline (post-A7).**

A §15.14 v7 cascade verdict produced under §15.14-A7 (sequence-
logprob logsumexp-over-variants extraction with §15.14-A5
chat-template render and §15.14-A6 Mistral-7B fallback judge) is
a §0.8-binding readout AT THE STATED JUDGE CONFIGURATION. It is
not directly comparable to any prior §15.14 readout, because the
extraction mechanism is a different empirical claim about how to
read the judge's rubric-conditioned distribution.

**Pinned-table update (Chunk 6 Sealed §0.8-binding decisions).**

Three new pinned entries; one entry annotated:

| Decision | Pinned value (post-A7) |
|---|---|
| `JUDGE_EXTRACTION_METHOD` | `sequence_logprob_logsumexp_over_variants` (effective under §15.14-A7; was `logit_first_token_argmax` under §15.14-A4 / A5 / A6) |
| `JUDGE_LABEL_VARIANTS` | `("", " ", "\n")` (new under §15.14-A7) |
| `JUDGE_LABEL_AGGREGATION` | `"logsumexp"` (new under §15.14-A7) |

**Implementation surface (post-sign-off, EFFECTIVE follow-up).**

Three contained changes to `scripts/probe_framing_15_14.py`:

  1. New top-level constants:
     ```
     JUDGE_LABEL_VARIANTS = ("", " ", "\n")
     JUDGE_LABEL_AGGREGATION = "logsumexp"
     JUDGE_EXTRACTION_METHOD = "sequence_logprob_logsumexp_over_variants"
     ```
     The `JUDGE_EXTRACTION_METHOD` constant value changes from
     `"logit_first_token_argmax"` to the new value.

  2. `_judge_one_row` body: replace the single-token argmax with
     a per-variant teacher-forced sequence-logprob loop:
     ```
     def _judge_one_row(tokenizer, model, framing_substr, q, r, *, label_token_ids):
         prompt = render_judge_prompt(framing_substr, q, r)
         encoded = tokenizer.apply_chat_template(
             [{"role": "user", "content": prompt}],
             add_generation_prompt=True,
             return_tensors="pt", return_dict=True,
         )
         prompt_ids = encoded["input_ids"].to(target_device)
         T_prompt = prompt_ids.shape[-1]

         all_variant_logprobs = {ch: [] for ch in LABEL_TOKEN_CHARS}
         all_variant_columns = {}     # for cache: (label, variant) -> logprob
         for ch in LABEL_TOKEN_CHARS:
             for prefix in JUDGE_LABEL_VARIANTS:
                 surface = prefix + ch
                 v_ids = torch.tensor(
                     [tokenizer.encode(surface, add_special_tokens=False)],
                     device=target_device,
                 )
                 full = torch.cat([prompt_ids, v_ids], dim=-1)
                 with torch.no_grad():
                     out = model(full, use_cache=False)
                 logp = torch.log_softmax(out.logits[0].float(), dim=-1)
                 # Sum per-position logprobs over the variant tokens:
                 sum_logp = 0.0
                 for i, tok in enumerate(v_ids[0].tolist()):
                     pos = T_prompt + i - 1
                     sum_logp += float(logp[pos, tok].item())
                 all_variant_logprobs[ch].append(sum_logp)
                 all_variant_columns[(ch, prefix)] = sum_logp

         # logsumexp aggregation per label:
         per_label_score = {
             ch: float(torch.logsumexp(
                 torch.tensor(all_variant_logprobs[ch]), dim=0,
             ).item())
             for ch in LABEL_TOKEN_CHARS
         }
         severity_char = max(LABEL_TOKEN_CHARS, key=lambda c: per_label_score[c])
         return int(severity_char), "", all_variant_columns, per_label_score
     ```

  3. `_load_judge_model`: replace the
     `LABEL_TOKEN_ENCODING_AMBIGUOUS` exit with a relaxed check:
     ```
     # Replace the existing LABEL_TOKEN_ENCODING_AMBIGUOUS check
     # with a non-empty-tokenization check across all 9 variant
     # × label combinations:
     empty_variants = []
     for ch in LABEL_TOKEN_CHARS:
         for prefix in JUDGE_LABEL_VARIANTS:
             surface = prefix + ch
             ids = tokenizer.encode(surface, add_special_tokens=False)
             if len(ids) < 1:
                 empty_variants.append(repr(surface))
     if empty_variants:
         sys.stderr.write(
             "ANNOTATION_FAILED: LABEL_TOKEN_ENCODING_EMPTY — "
             f"variant string(s) encoded to zero tokens under tokenizer "
             f"of {judge_id_used!r}: {', '.join(empty_variants)}\n"
         )
         sys.exit(EXIT_ANNOTATION_FAILED)

     # Note: under A7, label_token_ids is NOT used by _judge_one_row
     # (which now does per-variant sequence scoring). The dict is
     # preserved in the return tuple for cache-schema continuity but
     # carries the isolated-form IDs only (or empty if the tokenizer
     # does not encode any label as single-token; cache writer
     # handles both cases).
     for ch in LABEL_TOKEN_CHARS:
         ids = tokenizer.encode(ch, add_special_tokens=False)
         if len(ids) == 1:
             label_token_ids[ch] = int(ids[0])
         # else: leave label_token_ids[ch] absent (multi-token);
         # the cache writer records None or omits the entry.
     ```

  4. `_save_annotated_cache` / `_load_annotated_cache`: schema
     bump `15.14-A5-annotated → 15.14-A7-annotated`; widen
     `judge_logits` matrix shape `(n, 3) → (n, 9)`; add
     `judge_label_aggregated` `(n, 3)` matrix; add top-level
     `judge_label_variants` and `judge_label_aggregation` fields.

  5. JSON / markdown writers: add per-row `judge_label_aggregated`
     entries; add top-level `annotation_protocol.judge_label_variants`
     and `annotation_protocol.judge_label_aggregation`; update
     `annotation_protocol.judge_extraction_method` value to
     `"sequence_logprob_logsumexp_over_variants"`.

`Pass C` orchestration (`run_pass_c_judge`) is unchanged in
shape (still iterates rows, still calls `_judge_one_row`, still
returns `severities_by_key`); the per-row dict structure adds
the `judge_label_aggregated` field. `Pass D` (κ-gate) is
unchanged. The cascade comparator, the firewall, the self-test
gate, the writers (apart from the schema additions above) are
otherwise unchanged.

**Required reporting (under v7 EFFECTIVE follow-up).**

The §15.14 v7 outcome document must list all seven judge attempts
side-by-side (the six from v6 OUTCOME plus the v7 row):

  1. Qwen-7B JSON: parse 0.2692 → ANNOTATION_FAILED
  2. Llama-8B JSON: parse 0.7077 → ANNOTATION_FAILED
  3. Llama-8B single-digit / A3: parse 0.8477 → ANNOTATION_FAILED
  4. Llama-8B / A4 raw-string single-token logit: parse 0.0; κ = −0.0776 → ANNOTATION_FAILED
  5. Llama-8B / A5 chat-template single-token logit: parse 0.0; κ = −0.3840 → ANNOTATION_FAILED
  6. Mistral-7B / A6 chat-template single-token logit: LABEL_TOKEN_ENCODING_AMBIGUOUS → ANNOTATION_FAILED
  7. Mistral-7B / A7 chat-template sequence-logprob logsumexp(`""`, `" "`, `"\n"`) over (`"0"`, `"1"`, `"2"`): parse 0.0; κ = TBD

If §15.14-A7 also fails the κ-gate, §15.14 closes as
ANNOTATION_FAILED with the extraction-mechanism degree-of-freedom
empirically exhausted on the post-§15.14-A6 fallback judge. The
residual diagnosis routes to either:

  - a future amendment that swaps the judge identity (Mistral-7B
    → another 7B-class family, or 22B / 32B / 70B-class judges
    under hardware/quantization amendments), or
  - a future amendment that redesigns the judge rubric (binary or
    two-stage), or
  - a future amendment that revisits the variant set or
    aggregation (A7-family successor amendments).

None of these are authorized by this PROPOSED block; each
requires a separate amendment cycle.

If §15.14-A7 passes the κ-gate, the v7 cascade verdict is
computed under unchanged §15.14 cascade rules, and the binding
constraint at v6 is empirically identified as the §15.14-A4
single-token extraction mechanism × Mistral SentencePiece
tokenizer combination (resolved by A7's tokenizer-agnostic
extraction).

**Provenance after a §15.14-A7 v7 run.**

A successful §15.14-A7 v7 cascade verdict (or κ-gate-failure
exit 9) will produce annotated-cache + JSON output with:

```
"annotation_protocol": {
  "judge_model_id":              "mistralai/Mistral-7B-Instruct-v0.3",
  "judge_fallback_used":         true,
  "judge_prompt_sha256":         "<unchanged from A3>",
  "judge_prompt_render":         "apply_chat_template_user_only(add_generation_prompt=True)",
  "judge_extraction_method":     "sequence_logprob_logsumexp_over_variants",
  "judge_label_variants":        ["", " ", "\n"],
  "judge_label_aggregation":     "logsumexp",
  "label_token_ids":             {"0": null, "1": null, "2": null},   # multi-token under Mistral
  ...
},
"per_row": [
  {
    "...": ...,
    "judge_logits": {
      "0": {"":  <float>, " ": <float>, "\n": <float>},
      "1": {"":  <float>, " ": <float>, "\n": <float>},
      "2": {"":  <float>, " ": <float>, "\n": <float>}
    },
    "judge_label_aggregated": {"0": <float>, "1": <float>, "2": <float>},
    ...
  },
  ...
]
```

The presence of
`judge_extraction_method = "sequence_logprob_logsumexp_over_variants"`
plus the per-row 9-cell `judge_logits` object (variants nested
under labels) plus the per-row 3-cell `judge_label_aggregated`
object is the audit-trail signature that §15.14-A7 is in effect.

**v7 readout discipline.** §15.14 v1 / v2 / v3 / v4 / v6 closures
preserved. §15.14-A7 v7 readout is a **separate** §0.8-binding
result. It does not retroactively give v1–v6 a verdict; it
produces a fresh v7 verdict under a different extraction
mechanism.

**Two-phase discipline (per A1–A6 precedent; explicit).**

  1. **PROPOSED commit** (this commit cycle): the spec amendment
     block above is added with `Status: PROPOSED`. No code is
     touched in `scripts/probe_framing_15_14.py`. No status flip.
     No cache schema bump. No annotated-cache write.
  2. **EFFECTIVE follow-up** (separate commit, only after the user
     replies with the literal phrase
     `Sign off §15.14-A7. Push the EFFECTIVE follow-up.`): flips
     this status field from `PROPOSED` to `EFFECTIVE` and applies
     the five-item implementation surface enumerated above. The
     RunPod execution under the EFFECTIVE follow-up is a
     **separate** user authorization; it is not implied by the
     EFFECTIVE flip itself.

---

### §15.14-A8 — rubric-redesign diagnostic: two-stage binary judging (replaces direct 3-class scoring)

**Status:** PROPOSED. The status field will flip to EFFECTIVE only
after the user replies with the literal phrase
`Sign off §15.14-A8. Push the EFFECTIVE follow-up.` and a separate
EFFECTIVE follow-up commit is pushed that flips this status field
and applies the implementation surface enumerated below. This
two-phase discipline mirrors §15.14-A1 / A2 / A3 / A4 / A5 / A6 /
A7.

**Frame.** §15.14-A8 is a **rubric-redesign diagnostic, NOT a
repair of §15.14-A7.** §15.14-A7 (tokenizer-agnostic
sequence-logprob logsumexp scoring) is preserved as EFFECTIVE
(κ-falsified by v7 at κ = −0.0976). A8 tests a structurally
distinct hypothesis: that the 7-8B-judge κ failures across v3 / v4
/ v7 are caused by the **direct 3-class rubric** — specifically
the unstable middle class `MENTIONED` — rather than by judge
parameter scale, judge family, or any property of the §15.14
stimulus or hidden-state hypothesis. If A8 passes the κ-gate,
rubric design is identified as the binding constraint at 7-8B
scale; if A8 fails the κ-gate, the accessible-small-judge path is
exhausted and the only remaining serious options are 70B-class
judge / hardware amendment or closing §15.14 as untestable under
accessible judges.

**Scope.** Multiple surgical code changes inside
`scripts/probe_framing_15_14.py` to support two-stage binary
judging while inheriting all §15.14-A4 / A5 / A6 / A7 mechanics
that survive the rubric redesign. Plus the implied annotated-
cache schema bump (`15.14-A7-annotated → 15.14-A8-annotated`),
two new pinned prompt templates with their own SHA-256s, and
new top-level provenance fields. No threshold change. No labels
change. No cascade structure change. No firewall change. No
sign-direction change. No verdict-of-record change. No
modification of `LABEL_TOKEN_CHARS`, `KAPPA_GATE_THRESHOLD`, or
`JUDGE_PROMPT_TEMPLATE` (the original 3-class template is
**preserved** as a constant for cross-version provenance, but is
no longer dispatched by `_judge_one_row` under A8).

**Rationale.** §15.14 v7 closed as `ANNOTATION_FAILED` (commit
`933459d`) with κ = `−0.0976` on Mistral-7B-Instruct-v0.3 +
§15.14-A7 sequence-logprob logsumexp extraction. The 7-8B-class
family-control hypothesis was empirically falsified across two
families × decisive κ readouts (Llama-8B / A4: κ = `−0.0776`;
Mistral-7B / A7: κ = `−0.0976`). Two natural mechanistic
interpretations remain post-v7 (recorded in v7 OUTCOME):

  1. **Scale is the binding constraint.** 7-8B is insufficient
     regardless of family or extraction protocol. A 70B-class
     judge under hardware/quantization amendment is indicated.
  2. **Rubric design is the binding constraint.** The 3-class
     IGNORED / MENTIONED / STRUCTURED rubric is mismatched to
     the bimodal human distribution (28/1/21 over the 50
     calibration rows). A binary or two-stage rubric on the
     existing 7-8B envelope is indicated.

§15.14-A8 tests interpretation (2) directly. Decisive evidence
from prior phases motivates the test:

  - **§15.14-A4 diagnostic block 1 (recorded on RunPod via
    `framing_15_14_annotated_A4_diagnostic.npz`)**: judge picked
    `MENTIONED` 34/50 calibration rows (68%) where humans picked
    `MENTIONED` 1/50 (2%). The judge over-uses the middle class
    by a factor of 34×.
  - **§15.14-A4 diagnostic block 4**: binary-collapse κ
    (`y = 1 iff severity ≥ 1`) was `+0.047` — also poor, but a
    different failure mode from the 3-class `−0.08`.
  - **Second-eyes review (correspondence record)**: the lone
    `MENTIONED` label in the 50-row human distribution is
    plausibly a clerical slip; the underlying human judgment is
    essentially binary IGNORED-vs-STRUCTURED.
  - **§15.14 v7 confirms**: replacing the family AND the
    extraction mechanism (Llama → Mistral, single-token argmax →
    sequence-logprob logsumexp) does not change the
    judge-distribution-vs-human-distribution mismatch on the
    middle class.

The two-stage rubric A8 introduces decomposes the 3-class
decision into two binary decisions that align with how humans
appear to think about this rubric:

  - **Stage 1 (binary):** "Is the framing present at all?"
    Answers: `N` (no framing) → severity 0; `Y` (some framing) →
    proceed to stage 2.
  - **Stage 2 (binary, conditional):** "Among responses where
    framing is present, is it structurally controlling?"
    Answers: `M` (mentioned only) → severity 1; `S` (structurally
    controlling) → severity 2.

Each stage is a separate sequence-logprob logsumexp scoring under
§15.14-A7 mechanics with §15.14-A5 chat-template render. The
mapping from `(stage1, stage2)` outcome to the canonical severity
in `{0, 1, 2}` is mechanical (pinned below). The κ-gate is
unchanged (computes 3-class κ between mapped severity and human
labels on the 50 calibration rows; threshold `0.6` inclusive).

A8 **does not modify the human labels or collapse them.** The
50 human labels remain the unchanged `(28 × 0, 1 × 1, 21 × 2)`
distribution. The mapping is on the **judge** side only: it
gives the judge a more tractable decision protocol; the human
labels are the unchanged ground truth against which 3-class κ is
computed.

**Pinned mechanism (binding under A8 EFFECTIVE).**

The following design choices are pinned in this PROPOSED block.
They are §0.8-binding upon the EFFECTIVE flip and cannot be
modified during a single A8 v8 run.

  - **Stage 1 prompt template** (pinned verbatim; new top-level
    constant `JUDGE_PROMPT_TEMPLATE_STAGE1`; SHA-256 sealed at
    EFFECTIVE flip):

    ```
    You are evaluating whether a model's response invokes a
    framing convention introduced in an earlier turn of a
    conversation. You will be shown:

    - The framing convention (a span of text from turn 1).
    - The current question (turn t, t >= 2).
    - The model's response to that question.

    Decide: does the model's response invoke or carry over the
    prior framing convention AT ALL?

    - N = NO framing present. The response does not invoke the
      framing in any way; the framing convention is absent from
      the response.
    - Y = SOME framing present. The response invokes the framing
      in some form — whether as a passing mention, a stylistic
      echo, a brief callback, or a structurally controlling lens.

    Return EXACTLY ONE CHARACTER: N or Y. Do not return any other
    text, explanation, JSON, code fence, or whitespace before or
    after the letter.

    FRAMING_CONVENTION:
    <FRAMING_CONVENTION>

    CURRENT_QUESTION:
    <CURRENT_QUESTION>

    MODEL_RESPONSE:
    <MODEL_RESPONSE>
    ```

  - **Stage 2 prompt template** (pinned verbatim; new top-level
    constant `JUDGE_PROMPT_TEMPLATE_STAGE2`; SHA-256 sealed at
    EFFECTIVE flip):

    ```
    You are evaluating whether a model's response is STRUCTURALLY
    CONTROLLED by a framing convention introduced in an earlier
    turn of a conversation. You have already determined that the
    framing is present in some form. You will be shown:

    - The framing convention (a span of text from turn 1).
    - The current question (turn t, t >= 2).
    - The model's response to that question.

    Decide: among responses where the framing is present, does
    the framing STRUCTURALLY control the response?

    - M = MENTIONED only. The framing appears as a passing
      reference, a stylistic echo, or a brief callback that does
      NOT drive the substance, the organization, or the
      terminology of the answer.
    - S = STRUCTURED. The framing structurally shapes the answer.
      The response is organized around the framing, uses it as
      the primary lens, or substitutes the framing terminology
      for the literal answer.

    Return EXACTLY ONE CHARACTER: M or S. Do not return any other
    text, explanation, JSON, code fence, or whitespace before or
    after the letter.

    FRAMING_CONVENTION:
    <FRAMING_CONVENTION>

    CURRENT_QUESTION:
    <CURRENT_QUESTION>

    MODEL_RESPONSE:
    <MODEL_RESPONSE>
    ```

    Both templates use the same three placeholders
    (`<FRAMING_CONVENTION>`, `<CURRENT_QUESTION>`,
    `<MODEL_RESPONSE>`) substituted by the existing
    `render_judge_prompt`-style mechanism. Each template's
    SHA-256 is recorded in the annotated cache + JSON output for
    provenance.

  - **Pinned per-stage label sets** (single-character labels;
    parallel to LABEL_TOKEN_CHARS but with semantically
    appropriate letters per stage):
    ```
    JUDGE_STAGE1_LABELS = ("N", "Y")
    JUDGE_STAGE2_LABELS = ("M", "S")
    ```

  - **Pinned mapping** from `(stage1, stage2)` outcome to the
    canonical severity in `LABEL_TOKEN_CHARS = ("0", "1", "2")`:
    ```
    def _map_two_stage(stage1: str, stage2: str | None) -> int:
        if stage1 == "N":
            return 0                       # severity 0 (IGNORED)
        if stage1 == "Y" and stage2 == "M":
            return 1                       # severity 1 (MENTIONED)
        if stage1 == "Y" and stage2 == "S":
            return 2                       # severity 2 (STRUCTURED)
        raise ValueError(
            f"unexpected stage outcomes: stage1={stage1!r}, "
            f"stage2={stage2!r}"
        )
    ```

  - **Pinned execution policy: conditional stage 2.** Stage 2 is
    run **only when stage 1 picks Y**. When stage 1 picks N, the
    severity is immediately set to 0; stage 2 is not run; the
    cache records `stage2_pick = None` (sentinel) and stage-2
    logprob columns receive a NaN sentinel. Rationale: stage 2's
    decision is logically void when stage 1 says no framing is
    present; saving the forward passes is operationally cleaner
    and avoids spurious stage-2 logprobs influencing any
    downstream metric.

  - **Pinned per-stage extraction.** Each stage uses the
    inherited §15.14-A7 mechanism (sequence-logprob logsumexp
    over `JUDGE_LABEL_VARIANTS = ("", " ", "\n")` per label),
    with the stage-appropriate label set. Per-row scoring:
    - Stage 1: `2 labels × 3 variants = 6 forward passes`,
      always run.
    - Stage 2: `2 labels × 3 variants = 6 forward passes`,
      conditional on stage 1 picking Y.

    Worst-case wall cost per `--force-annotate` invocation:
    `12 forward passes × 650 rows = 7800` short forward passes
    (~13 min on A100-80). Best case (all rows pick N):
    `6 × 650 = 3900` (~7 min). Expected, given the calibration
    distribution: ~9-11 passes per row average → ~6500-7150
    total (~11-12 min wall). This is comparable to A7's ~10 min.

  - **Per-stage precondition.** The §15.14-A7
    `LABEL_TOKEN_ENCODING_EMPTY` precondition is **extended** to
    cover both stages: each `(label, variant)` surface string
    across both `JUDGE_STAGE1_LABELS` and `JUDGE_STAGE2_LABELS`
    must encode to ≥1 token under the active tokenizer
    (`2 stages × 2 labels × 3 variants = 12` surface strings).
    Trivially satisfied by any non-empty UTF-8 string. Defensive
    check; does not gate any normal run.

**Output schema change (annotated cache + JSON).**

The annotated cache schema bumps from `15.14-A7-annotated` to
`15.14-A8-annotated`. The on-disk per-row layout changes:

  - `judge_logits` widens from `(n, 9)` (single 3-class × 3
    variants under A7) to `(n, 12)` under A8: 2 stages × 2
    labels × 3 variants. Pinned column order:
    ```
    [(1, "N", ""), (1, "N", " "), (1, "N", "\n"),
     (1, "Y", ""), (1, "Y", " "), (1, "Y", "\n"),
     (2, "M", ""), (2, "M", " "), (2, "M", "\n"),
     (2, "S", ""), (2, "S", " "), (2, "S", "\n")]
    ```
    Stage-2 cells (columns 6..11) carry `NaN` for rows where
    stage 1 picked N (stage 2 was not run).
  - `judge_label_aggregated` widens from `(n, 3)` (per-label
    A7 logsumexp over LABEL_TOKEN_CHARS) to `(n, 4)` under A8:
    `(stage1_N, stage1_Y, stage2_M, stage2_S)`. Stage-2 cells
    carry `NaN` when stage 1 picked N.
  - New per-row column `judge_stage1_pick` `(n,)` of strings
    `"N"` or `"Y"`.
  - New per-row column `judge_stage2_pick` `(n,)` of strings
    `"M"`, `"S"`, or `""` (empty-string sentinel for skipped
    stage 2).
  - `severity` column: unchanged shape, but values are now
    derived from `_map_two_stage(stage1_pick, stage2_pick)`.
  - `judge_rationale` column: unchanged (preserved as empty
    string for cross-version continuity).
  - Top-level provenance fields:
    - `annotation_protocol.judge_extraction_method`:
      `"two_stage_sequence_logprob_logsumexp"` (was
      `"sequence_logprob_logsumexp_over_variants"` under A7).
    - `annotation_protocol.judge_prompt_sha256`: REMOVED (the
      original 3-class template's SHA is no longer the active
      prompt; it is preserved as a const in the script for
      cross-version provenance only). Replaced by:
    - `annotation_protocol.judge_prompt_template_stage1_sha256`:
      new under A8. SHA-256 of `JUDGE_PROMPT_TEMPLATE_STAGE1`.
    - `annotation_protocol.judge_prompt_template_stage2_sha256`:
      new under A8. SHA-256 of `JUDGE_PROMPT_TEMPLATE_STAGE2`.
    - `annotation_protocol.judge_stage1_labels`: new under A8.
      Value: `["N", "Y"]`.
    - `annotation_protocol.judge_stage2_labels`: new under A8.
      Value: `["M", "S"]`.
    - All other provenance fields (`judge_model_id`,
      `judge_fallback_used`, `judge_prompt_render`,
      `judge_label_variants`, `judge_label_aggregation`,
      `label_token_chars`, `label_token_ids`) unchanged.

**Failure surfaces under A8.**

  - `LABEL_TOKEN_ENCODING_EMPTY` (extended under A8 to cover both
    stages): fires iff any of the 12 `(stage, label, variant)`
    surface strings encodes to zero tokens. Pre-flight
    expectation: PASS on Mistral-7B-Instruct-v0.3 and any
    standard HF tokenizer.
  - `json_parse_failure_rate` (preserved name): structurally
    `0.0000` (no parsing step). Vacuous. Carries through from
    A4 / A5 / A6 / A7.
  - Pass D **κ-gate at `KAPPA_GATE_THRESHOLD = 0.6` inclusive**:
    **unchanged and binding**. If 3-class κ < 0.6 on the 50
    calibration rows under the two-stage-mapped severities, the
    script exits 9 ANNOTATION_FAILED before the cascade is
    computed.

**What this amendment does NOT change.**

  - `JUDGE_MODEL_ID_DEFAULT` (`Qwen/Qwen2.5-72B-Instruct`):
    unchanged.
  - `JUDGE_MODEL_ID_FALLBACK`
    (`mistralai/Mistral-7B-Instruct-v0.3`, §15.14-A6 inherit):
    unchanged.
  - `JUDGE_PROMPT_RENDER`
    (`apply_chat_template_user_only(add_generation_prompt=True)`,
    §15.14-A5 inherit): unchanged.
  - `JUDGE_LABEL_VARIANTS = ("", " ", "\n")` (§15.14-A7
    inherit): unchanged. Used per-stage.
  - `JUDGE_LABEL_AGGREGATION = "logsumexp"` (§15.14-A7
    inherit): unchanged. Used per-stage.
  - `LABEL_TOKEN_CHARS = ("0", "1", "2")`: unchanged. The
    canonical severity output is still `0 / 1 / 2`; the
    two-stage decomposition is internal to the judge.
  - `KAPPA_GATE_THRESHOLD = 0.6` (inclusive): unchanged.
  - `ANNOTATION_FAILURE_RATE_THRESHOLD = 0.05`: unchanged
    (vacuous under §15.14-A4 / A7 inheritance).
  - `BINARY_LABEL_THRESHOLD` (y = 1 iff severity ≥ 1):
    unchanged.
  - `DIRECTION_GATE_THRESHOLD = 0.5` (strict): unchanged.
  - `PARTIAL_AUC_THRESHOLD = 0.66` (inclusive): unchanged.
  - `STRONG_AUC_THRESHOLD = 0.75` (inclusive): unchanged.
  - `STRONG_DELTA_AUC_THRESHOLD = 0.05` (inclusive): unchanged.
  - Severity rubric (0=IGNORED / 1=MENTIONED / 2=STRUCTURED) at
    the κ-evaluation surface: unchanged. The two-stage rubric
    is the **judge's** decision protocol; the canonical
    severity values that the κ-gate compares against the human
    labels are unchanged.
  - **Human calibration labels: unchanged.** The 50-row
    `(28, 1, 21)` distribution is the unchanged ground truth.
    A8 does NOT relabel, collapse, or otherwise modify the
    labels artifact. Locked SHA
    `e9776ff223ef913b2e404d2cf90203e9615c01640bc8fc5c42ffabf2d49b0d6c`
    preserved.
  - Locked stimulus SHA
    (`e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7`):
    unchanged.
  - Sign direction (BCVF-faithful: R_framing higher → more
    framing-stickiness): unchanged.
  - Cascade structure (4-step direction-gate → STRONG → PARTIAL
    → NO_MATERIAL), 2-comparator strict-margin requirement:
    unchanged.
  - 12 self-test cascade boundary cases: unchanged.
  - 52-pattern Class-3 firewall: unchanged.
  - Original `JUDGE_PROMPT_TEMPLATE` (3-class) text content +
    SHA-256: **preserved as a constant** in the script for
    cross-version provenance, but no longer dispatched by
    `_judge_one_row` under A8. Pre-A8 output JSON files reference
    its SHA via `annotation_protocol.judge_prompt_sha256`; A8's
    output JSON references the two new per-stage SHAs instead.
  - `framing_15_14_extractions.npz` extraction cache: unchanged
    and reusable via `--force-annotate`.
  - `framing_15_14_annotated_A4_diagnostic.npz` on RunPod
    (`diagnostic_only=True`): unchanged and preserved.
  - §15.14-A1 / A2 / A3 / A4 / A5 / A6 / A7: unchanged. All
    EFFECTIVE. A8 layers new per-stage prompt + per-stage
    scoring + severity-mapping logic on top of A7's mechanism;
    A4 / A5 / A6 / A7 mechanics are inherited where applicable
    and preserved as EFFECTIVE.
  - All §13/§14/§15.x verdicts-of-record (including §15.14 v1 /
    v2 / v3 / v4 / v6 / v7 ANNOTATION_FAILED closures):
    preserved.

**What this amendment does NOT permit.**

  - Lowering `KAPPA_GATE_THRESHOLD` below 0.6.
  - Modifying any sealed AUC threshold, the cascade structure,
    the comparator rules, or the canonical severity rubric
    (0/1/2 at the κ-evaluation surface).
  - Modifying the topic-overlap firewall (52 patterns).
  - Modifying `BINARY_LABEL_THRESHOLD`.
  - Modifying `DIRECTION_GATE_THRESHOLD`.
  - Modifying the sign convention.
  - Modifying the human calibration labels artifact.
  - Collapsing the 3-class human labels to a binary human label
    set. The κ-gate compares two-stage-mapped 3-class judge
    severity against the unchanged 3-class human severity.
  - Editing `JUDGE_PROMPT_TEMPLATE_STAGE1` or
    `JUDGE_PROMPT_TEMPLATE_STAGE2` text content during a single
    A8 EFFECTIVE run (both are pinned with sealed SHAs).
  - Modifying `JUDGE_STAGE1_LABELS` or `JUDGE_STAGE2_LABELS`.
  - Modifying the conditional stage-2 execution policy (stage 2
    runs iff stage 1 picks Y).
  - Modifying the `_map_two_stage` mapping function.
  - Modifying the inherited §15.14-A7 mechanics
    (`JUDGE_LABEL_VARIANTS`, `JUDGE_LABEL_AGGREGATION`).
  - Modifying the inherited §15.14-A5 chat-template render.
  - Modifying the inherited §15.14-A6 fallback judge identity
    (Mistral-7B-Instruct-v0.3).
  - Authorizing Mixtral-8x7B (does not fit envelope; deferred).
  - Authorizing 70B-class judge (does not fit envelope;
    deferred).
  - Quantizing any judge model (carries forward the §15.14-A4 /
    A5 / A6 / A7 prohibition).
  - Sign-flip rescue on direction-gate failure.
  - Skipping the κ self-test gate.
  - Modifying any prior §13 / §14 / §15.x verdict-of-record.
  - Reinterpreting §15.14 v1 / v2 / v3 / v4 / v6 / v7 outcomes.

**Cascade verdict reading discipline (post-A8).**

A §15.14 v8 cascade verdict produced under §15.14-A8 (two-stage
binary judging with §15.14-A4 / A5 / A6 / A7 mechanics inherited)
is a §0.8-binding readout AT THE STATED JUDGE CONFIGURATION. It
is not directly comparable to any prior §15.14 readout, because
the judge decision protocol is a different empirical claim about
how to extract rubric-conditioned severity from the active 7-8B
judge.

**Pinned-table updates (Chunk 6 Sealed §0.8-binding decisions).**

Six new pinned entries; one entry annotated:

| Decision | Pinned value (post-A8) |
|---|---|
| `JUDGE_EXTRACTION_METHOD` | `two_stage_sequence_logprob_logsumexp` (effective under §15.14-A8; was `sequence_logprob_logsumexp_over_variants` under §15.14-A7) |
| `JUDGE_PROMPT_TEMPLATE_STAGE1` | (the verbatim text above, pinned; SHA-256 sealed at EFFECTIVE flip) |
| `JUDGE_PROMPT_TEMPLATE_STAGE2` | (the verbatim text above, pinned; SHA-256 sealed at EFFECTIVE flip) |
| `JUDGE_STAGE1_LABELS` | `("N", "Y")` (new under §15.14-A8) |
| `JUDGE_STAGE2_LABELS` | `("M", "S")` (new under §15.14-A8) |
| `JUDGE_TWO_STAGE_MAPPING` | `(N→0, Y∧M→1, Y∧S→2)` (new under §15.14-A8) |
| `JUDGE_TWO_STAGE_EXECUTION_POLICY` | `conditional_stage_2_iff_stage_1_y` (new under §15.14-A8) |

The original `JUDGE_PROMPT_TEMPLATE` constant + its SHA-256 are
preserved in the script for cross-version provenance but are
**no longer dispatched** by `_judge_one_row` under A8.

**Implementation surface (post-sign-off, EFFECTIVE follow-up).**

Eight contained changes to `scripts/probe_framing_15_14.py`:

  1. Two new top-level constants:
     `JUDGE_PROMPT_TEMPLATE_STAGE1` and
     `JUDGE_PROMPT_TEMPLATE_STAGE2` (the verbatim texts above).
  2. Two new SHA helper functions:
     `judge_prompt_template_stage1_sha256()` and
     `judge_prompt_template_stage2_sha256()` (parallel to the
     existing `judge_prompt_sha256()`).
  3. Two new render functions:
     `render_judge_prompt_stage1(framing_substr, q, r)` and
     `render_judge_prompt_stage2(framing_substr, q, r)`
     (parallel to the existing `render_judge_prompt`).
  4. New top-level constants:
     `JUDGE_STAGE1_LABELS = ("N", "Y")`,
     `JUDGE_STAGE2_LABELS = ("M", "S")`. The existing
     `LABEL_TOKEN_CHARS = ("0", "1", "2")` is unchanged and
     remains the canonical severity-output enum.
  5. New helper `_map_two_stage(stage1, stage2) -> int` per the
     pinned mapping above.
  6. `_judge_one_row` body: rewritten for two-stage logic.
     Returns `(severity, "", per_stage_logprobs,
     per_stage_aggregated, stage1_pick, stage2_pick)` —
     widened from §15.14-A7's 4-tuple to a 6-tuple.
  7. `_load_judge_model`: extend the
     `LABEL_TOKEN_ENCODING_EMPTY` precondition to check all
     `2 × 2 × 3 = 12` surface strings (2 stages × 2 labels × 3
     variants).
  8. `_save_annotated_cache` / `_load_annotated_cache`: schema
     bump `15.14-A7-annotated → 15.14-A8-annotated`; widen
     `judge_logits` matrix `(n, 9) → (n, 12)`; widen
     `judge_label_aggregated` `(n, 3) → (n, 4)`; add
     `judge_stage1_pick` and `judge_stage2_pick` per-row
     columns; add top-level
     `judge_prompt_template_stage1_sha256` /
     `judge_prompt_template_stage2_sha256` /
     `judge_stage1_labels` / `judge_stage2_labels` provenance
     fields.

Plus per-row block extension in:

  9. `run_pass_c_judge` orchestrator: update the per-row dict to
     thread the new fields through.
  10. `FramingAuditOutputs` dataclass: add
      `judge_prompt_template_stage1_sha256`,
      `judge_prompt_template_stage2_sha256`,
      `judge_stage1_labels`, `judge_stage2_labels` fields.
      Drop or alias the existing `judge_prompt_sha256` field
      (preserved for cross-version diff continuity but no longer
      written under A8).
  11. JSON / markdown writers: add per-stage SHAs and
      per-stage labels to the audit-trail block; update
      `judge_extraction_method` value.

`Pass C` orchestration shape (still iterates rows, still calls
`_judge_one_row`) is unchanged. `Pass D` (κ-gate) is unchanged.
The cascade comparator, the firewall, the self-test gate, the
calibration labels artifact, the extraction cache, the locked
stimulus SHA, and the locked labels SHA are all unchanged.

**Required reporting (under v8 EFFECTIVE follow-up).**

The §15.14 v8 outcome document must list all eight judge attempts
side-by-side (the seven from v7 OUTCOME plus the v8 row):

  1. Qwen-7B JSON: parse 0.2692 → ANNOTATION_FAILED
  2. Llama-8B JSON: parse 0.7077 → ANNOTATION_FAILED
  3. Llama-8B single-digit / A3: parse 0.8477 → ANNOTATION_FAILED
  4. Llama-8B / A4 raw-string single-token: parse 0.0; κ = −0.0776 → ANNOTATION_FAILED
  5. Llama-8B / A5 chat-template single-token: parse 0.0; κ = −0.3840 → ANNOTATION_FAILED
  6. Mistral-7B / A6 chat-template single-token: LABEL_TOKEN_ENCODING_AMBIGUOUS → ANNOTATION_FAILED
  7. Mistral-7B / A7 chat-template seq-logprob: parse 0.0; κ = −0.0976 → ANNOTATION_FAILED
  8. Mistral-7B / A8 chat-template two-stage seq-logprob: parse 0.0; κ = TBD

If §15.14-A8 also fails the κ-gate, **§15.14 closes as
ANNOTATION_FAILED with the accessible-small-judge path
exhausted.** The only remaining serious options at that point
are:

  - a 70B-class judge / hardware amendment (separate
    authorization), or
  - closing §15.14 as untestable under accessible judges
    (separate authorization).

If §15.14-A8 passes the κ-gate, the v8 cascade verdict is
computed under unchanged §15.14 cascade rules, and the binding
constraint at v3 / v4 / v7 is empirically identified as
**rubric design** (specifically the unstable middle class
`MENTIONED` in the direct 3-class rubric). Scale-of-judge would
then be empirically identified as NOT the binding constraint,
and the §15.14 forward path would route to the cascade-verdict
output rather than to a 70B+ amendment.

**Provenance after a §15.14-A8 v8 run.**

A successful §15.14-A8 v8 cascade verdict (or κ-gate-failure
exit 9) will produce annotated-cache + JSON output with:

```
"annotation_protocol": {
  "judge_model_id":                          "mistralai/Mistral-7B-Instruct-v0.3",
  "judge_fallback_used":                     true,
  "judge_prompt_template_stage1_sha256":     "<sha256 of JUDGE_PROMPT_TEMPLATE_STAGE1>",
  "judge_prompt_template_stage2_sha256":     "<sha256 of JUDGE_PROMPT_TEMPLATE_STAGE2>",
  "judge_prompt_render":                     "apply_chat_template_user_only(add_generation_prompt=True)",
  "judge_extraction_method":                 "two_stage_sequence_logprob_logsumexp",
  "judge_label_variants":                    ["", " ", "\n"],
  "judge_label_aggregation":                 "logsumexp",
  "judge_stage1_labels":                     ["N", "Y"],
  "judge_stage2_labels":                     ["M", "S"],
  "label_token_chars":                       ["0", "1", "2"],
  "label_token_ids":                         {"0": -1, "1": -1, "2": -1},
  ...
},
"per_row": [
  {
    "...": ...,
    "judge_logits": {
      "stage1": {"N": {"":  <f>, " ": <f>, "\n": <f>},
                 "Y": {"":  <f>, " ": <f>, "\n": <f>}},
      "stage2": {"M": {"":  <f>, " ": <f>, "\n": <f>}|null,
                 "S": {"":  <f>, " ": <f>, "\n": <f>}|null}
    },
    "judge_label_aggregated": {
      "stage1": {"N": <f>, "Y": <f>},
      "stage2": {"M": <f>, "S": <f>} | null
    },
    "judge_stage1_pick": "N" | "Y",
    "judge_stage2_pick": "M" | "S" | null,
    ...
  },
  ...
]
```

The simultaneous presence of
`judge_extraction_method = "two_stage_sequence_logprob_logsumexp"`
plus the per-row two-stage `judge_logits` object plus the per-row
`judge_stage1_pick` / `judge_stage2_pick` fields is the
audit-trail signature that §15.14-A8 is in effect.

**v8 readout discipline.** §15.14 v1 / v2 / v3 / v4 / v6 / v7
closures preserved. §15.14-A8 v8 readout is a **separate**
§0.8-binding result. It does not retroactively give v1–v7 a
verdict; it produces a fresh v8 verdict under a different judge
decision protocol (two-stage binary instead of direct 3-class).

**Two-phase discipline (per A1–A7 precedent; explicit).**

  1. **PROPOSED commit** (this commit cycle): the spec amendment
     block above is added with `Status: PROPOSED`. No code is
     touched in `scripts/probe_framing_15_14.py`. No status flip.
     No cache schema bump. No annotated-cache write.
  2. **EFFECTIVE follow-up** (separate commit, only after the
     user replies with the literal phrase
     `Sign off §15.14-A8. Push the EFFECTIVE follow-up.`): flips
     this status field from `PROPOSED` to `EFFECTIVE` and
     applies the eleven-item implementation surface enumerated
     above. The RunPod execution under the EFFECTIVE follow-up
     is a **separate** user authorization; it is not implied by
     the EFFECTIVE flip itself.

---

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
