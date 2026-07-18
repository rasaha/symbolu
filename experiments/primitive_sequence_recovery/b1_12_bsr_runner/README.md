# B1.12 Bare-Word Symbolic Resonance — multi-LLM crossover runner (RunPod)

Executes the B1.12 BSR two-LLM crossover under the controlling preregistration
`VARNA_SYMBOLIC_RESONANCE_PREREG_V1.md` + the pre-run freeze
`B1_12_BSR_VERDICT_AND_ROLE_STABILITY_FREEZE.md`, on the frozen 20-word list
(`../b1_12_symbolic_resonance_wordlist_v1/`, SHA `9779384d…`).

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`.

## Design
- **Run A:** Qwen 3 authors profile+evidence → Mistral Small scores.
- **Run B:** Mistral authors → Qwen scores (fresh, no Run-A context).
- Deterministic decoding (temperature 0, fixed seed, one fixed Qwen mode). No forced consensus; both judgments retained.
- Two hard gates first: `RUN_INVALID_INPUT_MISMATCH` (hashes/word-list) and `BLOCKED_REQUIRED_MODEL_UNAVAILABLE`
  (no family substitution). Verdicts and the role-dependence rule are frozen **before** any model call.

## RunPod setup
GPU with enough VRAM for a ~32B model (e.g. 1×A100 80GB or 2×48GB with `--tensor-parallel-size 2` in `backends.py`).
```bash
pip install "vllm>=0.6" transformers
# (models auto-download from HF; set HF_TOKEN if gated)
cd experiments/primitive_sequence_recovery/b1_12_bsr_runner
python -m pytest test_bsr_runner.py -q          # deterministic self-check (no GPU needed)
python run_crossover.py \
  --mode vllm \
  --qwen Qwen/Qwen3-32B \
  --mistral mistralai/Mistral-Small-3.1-24B-Instruct-2503 \
  --seed 20260714
```
Alternative (served vLLM OpenAI-compatible endpoints):
```bash
python run_crossover.py --mode openai \
  --qwen Qwen/Qwen3-32B --qwen-base-url http://127.0.0.1:8001/v1 \
  --mistral mistralai/... --mistral-base-url http://127.0.0.1:8002/v1 --seed 20260714
```
Qwen reasoning mode defaults to **non-thinking** (`enable_thinking=False`); pass `--qwen-thinking` to fix it ON
instead. Whatever is chosen is used consistently in both roles and recorded in `model_manifest.json`.

## Outputs → `../results/b1_12_symbolic_resonance_multillm_v1/`
`run_manifest.json`, `input_hashes.json`, `model_manifest.json`, `wordlist_manifest.json`,
`run_{a,b}_model_inputs.json`, `run_{a,b}_profiles.json`, `run_{a,b}_evidence.json`, `run_{a,b}_scores.json`,
`run_{a,b}_raw_outputs.jsonl`, `component_agreement.json`, `relationship_agreement.json`,
`word_verdict_agreement.json`, `role_dependence_summary.json`, and (author it after inspecting the numbers)
`B1_12_SYMBOLIC_RESONANCE_MULTILLM_REPORT.md`. Running here overwrites the earlier SETUP-blocked manifests with
real results.

## Discipline
No modification of the controlling prereg, the scope-update artifact, the frozen word list, the parser, the
mappings, the old 60-word scores, or any prior artifact. The runner reads frozen glosses **only** at scoring time
(never during word selection — that firewall is upstream). Retries fire only for structural invalidity
(malformed JSON, missing field/evidence, invalid score, invented relationship, modified gloss) — never because a
score is unfavorable — and every retry is logged in `run_{a,b}_raw_outputs.jsonl`.

**Relationship-token canonicalization.** The relationship type is a controlled vocabulary. Orthographic
typos of a taxonomy token (e.g. Mistral's deterministic `constituitive_property` → `constitutive_property`)
are canonicalized **only** when the intent is unambiguous — an exact match, case/separator normalization, or a
*unique* nearest taxonomy token within edit distance ≤ 2 (`bsr_rubric.canonicalize_relationship`). Semantically
distinct or ambiguous tokens (e.g. `causation`, `vibes`) are **not** coerced and still fail as
`invented_relationship`. This never touches scores, evidence, or which relationship the model chose; every
coercion (`from`/`to`/occurrence) is recorded in the per-attempt `coercions` field of the raw log.
