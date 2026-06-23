# Conscious Generation — Weak LLM-Judge Evaluation Harness

> **LLM-judge evaluation is an assisted weak-evaluation layer for screening and iteration. It is not human
> evaluation and cannot by itself validate Conscious Generation training.**
>
> **Strong validation requires human labels or at least a human-calibrated subset.**

## 1. Purpose
Score Conscious Generation / Mistral answers (arms A=base, B=base+C×R×S wrapper, C=C×R×S-LoRA,
D=C×R×S-LoRA+wrapper) with a **fixed-rubric LLM judge** (Llama / Qwen / Gemma) for fast **screening and
iteration**. It produces weak rubric labels, multi-judge agreement diagnostics, and a comparison against
the existing rule/Phase-3 audit scorer. It is a *screening tool*, layered on top of — never replacing — the
deterministic rubric and the human-label track.

This does **not** change the T1 conclusion: `CG_TRAINING_WRAPPER_STILL_BEST` stands; the inference-time
C×R×S wrapper remains the validated deployment path.

## 2. Why the LLM judge is weak, not human
- It is another language model, with its own biases; its labels correlate with surface fluency and with the
  judge's own training distribution.
- It cannot establish ground truth. It can only **screen** ("which answers look frame-broken / leaky / low
  signal") and **flag candidates** for human review.
- Therefore every label this harness emits is marked `source = llm_judge_weak_label` (single judge) or
  `source = llm_judge_ensemble_weak_label` (multi-judge consensus). The string `human_label` is **never**
  emitted (hard-asserted by `assert_no_human_labels`).

## 3. Supported labels (rubric v1)
Binary (also the agreement fields): `primary_frame_correct`, `rejected_domain_leak`,
`secondary_overpromotion`, `factuality_preserved`, `generic_low_signal`, `overconfident_or_overstated`,
`answer_acceptable`, `rewrite_needed`. Numeric: `must_include_recall_score` (0.0–1.0),
`clarity_usefulness_score` (1–5). Plus optional `short_reason`.

## 4. Rubric
A fixed prompt (`llm_judge_rubric.py`, `RUBRIC_VERSION="v1"`) provides the question, the **primary /
secondary / rejected** frames, and the **must-include** concepts, then requires **strict JSON only**. The
judge prompt:
1. hides arm/model identity (never includes arm, model, lora, metadata, split);
2. provides primary/secondary/rejected domains and must-include items;
3. instructs strict JSON only;
4. warns **not to reward fluency** that violates the semantic frame;
5. warns **not to punish concise** answers unless they omit required content;
6. states **rejected-domain leakage is a MAJOR failure**.
The parser (`parse_judge_json`) tolerates ```` ```json ```` fences, requires all rubric fields, coerces
booleans, and clamps numerics; anything unparseable or incomplete is counted as **invalid JSON**.

## 5. Input / output format
**Input** (`--input`, JSONL or JSON): answer records of the form
```json
{ "id": "ex_001", "arm": "C", "query": "...", "answer": "...", "primary_domain": "medicine_healing",
  "secondary_domains": ["authority_status"], "rejected_domains": ["finance","astrology"],
  "must_include": ["diagnose","treat","illness"], "metadata": {"model":"mistral_lora","split":"test"} }
```
Also accepted: a four-arm eval JSON (`{"per_example":[...]}`) — flattened to one record per arm
(answer text per arm required); and the Phase-3 audit JSONL (carries audit labels for §7 comparison).
Missing **required** fields (query/answer/primary_domain) fail loud; missing **optional** fields
(secondary/rejected/must_include) fail loud unless `--allow-missing-optional`.

**Output** (`--out-dir`):
- `llm_judge_labels.jsonl` — one row per judge per item: `{id, judge, source, labels, raw_response,
  valid_json, rubric_version}` (+ `arm` for analysis, never in the prompt) and ensemble consensus rows;
- `llm_judge_eval.json` — decision, agreement, audit comparison, notes;
- `llm_judge_eval.md` — human-readable summary.

## 6. Multi-judge agreement
With ≥2 judges (`--judges llama,qwen`): per binary field — **percent agreement** + **Cohen's κ**
(first pair) + **Fleiss' κ** (≥3 judges); per numeric field — **mean absolute difference** + Pearson +
Spearman. With one judge, agreement is **not computable** and the run states so. An overall
`avg_percent_agreement` drives the decision gate.

## 7. Audit comparison
When the input carries Phase-3 audit labels, the harness compares the (first) judge against them on the
overlapping notions (`primary_frame_correct`, `rejected_domain_leak`, `secondary_overpromotion`,
`answer_acceptable`, `rewrite_needed`) and reports `agreement_with_audit`,
`llm_judge_more_lenient_count`, `llm_judge_more_strict_count`, and disagreement examples. **The audit is
authoritative; the judge never overrides it** — this is a diagnostic only.

## 8. Risks
- **Judge bias** — the judge has its own priors; its "acceptable" is not ground truth.
- **Shared model-family bias** — judges from the same family (or a mock sharing one heuristic) inflate
  agreement; high κ between same-family judges is **not** evidence of correctness. (In the bundled mock,
  the two judges share a heuristic core and therefore agree ~100% on binary fields — illustrating exactly
  this artifact.)
- **Fluency bias** — LLM judges over-reward fluent prose; the rubric explicitly warns against this, but the
  bias is not eliminated.
- **Circularity** — if the **same** model both labels training data and judges the result, scores are
  self-confirming. Do not train Mistral on a judge's labels and then evaluate with that same judge without
  marking the circularity risk.

## 9. Allowed claims
- "Judge X flags N answers as frame-broken / rejected-domain-leaking / low-signal" (screening).
- "Judges agree at κ=… on rewrite_needed" (evaluator usability).
- "Judge agrees with the rule/audit scorer on M% of items; it is more lenient/strict on …" (calibration).
- "These weak labels prioritize K items for human review."

## 10. Forbidden claims
- Treating LLM-judge labels as human labels, or claiming human-quality validation.
- Claiming Conscious Generation training is validated from LLM-judge results alone.
- Using the LLM judge to override the Phase-3 audit in runtime.
- Wiring any judge result into the runtime, or modifying the C×R×S wrapper / Kosha / Guna / Vritti / Bhava
  paths from this harness.

## 11. Decision labels
`CG_LLM_JUDGE_EVAL_READY`, `CG_LLM_JUDGE_MOCK_ONLY`, `CG_LLM_JUDGE_WEAK_LABELS_GENERATED`,
`CG_LLM_JUDGE_AGREEMENT_LOW` (<0.60), `CG_LLM_JUDGE_AGREEMENT_ACCEPTABLE` (≥0.70),
`CG_LLM_JUDGE_AUDIT_DISAGREEMENT_HIGH` (flag when >40% rewrite_needed disagreement),
`CG_LLM_JUDGE_ENV_UNAVAILABLE`, `CG_LLM_JUDGE_INVALID_JSON_RATE_HIGH` (>0.10).
Precedence: mock_only → invalid-JSON-high → (≥2 judges) agreement band → single-judge weak-labels. These
labels describe **evaluator usability only**; none of them validates training.

## 12. CLI
```bash
# CPU-safe mock (deterministic; for tests / smoke):
python scripts/conscious_generation_training/llm_judge_eval.py \
  --input runs/cg_training/crs_eval/four_arm_eval.json \
  --out-dir runs/cg_training/llm_judge_eval --judges mock --mock

# Local Llama via Ollama (if the provider is available):
python scripts/conscious_generation_training/llm_judge_eval.py \
  --input runs/cg_training/crs_eval/four_arm_eval.json \
  --out-dir runs/cg_training/llm_judge_eval --judges llama --provider ollama --model llama3.1

# Multi-judge:
python scripts/conscious_generation_training/llm_judge_eval.py \
  --input runs/cg_training/crs_eval/four_arm_eval.json \
  --out-dir runs/cg_training/llm_judge_eval --judges llama,qwen --provider ollama
```
Real judges need a local Ollama / OpenAI-compatible server; with no provider configured the harness writes
`CG_LLM_JUDGE_ENV_UNAVAILABLE` and exits cleanly. Tests use `--mock` only (no GPU, no network).
