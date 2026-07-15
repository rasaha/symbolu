# B1.12 V2 — Independent-judge runner (RunPod)

Executes the **frozen** `VARNA_SYMBOLIC_RESONANCE_PREREG_V2.md` (SHA `831e48ec…`) + freeze record
`B1_12_V2_PREREG_FREEZE.md` on the fresh 20-word list `../b1_12_symbolic_resonance_wordlist_v2/`
(SHA `7a558008…`). `EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`.

## Design (Option A — reliability fix, single tightened DBR axis)
- **Two independent judges, NO crossover.** Qwen and Mistral each judge all 20 words on their own; neither model
  sees the other's evidence, relationship, score, or verdict.
- Each model, per occurrence, emits: `supporting_evidence`, `opposing_evidence`, `relationship`, `dbr_score`
  (+ a bare-word `profile`) in ONE blind judgment.
- Tightened DBR scale ("requires interpretation" → 25, not 50); no-supplementation firewall at scoring;
  **opposition/resolution are full-range, polarity-neutral** (frozen §1.4 correction). Prompts are frozen — do not
  edit during a run.
- Deterministic decoding (temp 0, top_p 1, top_k −1, fixed seed, bf16). No model-family substitution.
- Two hard gates first: `RUN_INVALID_INPUT_MISMATCH` (hash/word-list/prereg) and `BLOCKED_REQUIRED_MODEL_UNAVAILABLE`.

## Run (1×A100-80GB)
```bash
export HF_HUB_DISABLE_XET=1 HF_HUB_ENABLE_HF_TRANSFER=0 HF_HUB_CACHE=/workspace/hf_cache
cd experiments/primitive_sequence_recovery/b1_12_bsr_v2_runner
python -m pytest test_v2_runner.py -q            # 7 pass, no GPU
python run_v2_independent.py --qwen Qwen/Qwen3-32B \
    --mistral mistralai/Mistral-Small-3.1-24B-Instruct-2503 --seed 20260714
```
Two sequential model loads (Qwen judge; Mistral judge), one resident at a time; resume-safe (skips a judge whose
`_tmp/*_judge.json` already exists). Qwen defaults to non-thinking (`--qwen-thinking` to fix it on).

## Outputs → `../results/b1_12_symbolic_resonance_v2/`
`run_manifest.json`, `input_hashes.json`, `model_manifest.json`, `wordlist_manifest.json`,
`qwen_scores.json`, `mistral_scores.json`, `qwen_profiles.json`, `mistral_profiles.json`, `raw_all.jsonl`,
and the mechanical Phase-4 aggregates: `component_agreement.json`, `relationship_agreement.json`,
`word_verdict_agreement.json`, `score_distributions.json`, `disagreement_table.json`,
`strongest_disagreements.json`, `strongest_agreements.json`, `profile_agreement.json`, `summary_statistics.json`
(carries `model_identity_dependence`). Aggregation is mechanical — no interpretation in the runner.

## Discipline
No modification of the frozen prereg, freeze record, word list, parser, mappings, glosses, thresholds, verdict
bands, or the independent two-model design. Glosses are read only at scoring time. Retries fire only for structural
invalidity (never for an unfavorable score); every attempt + any relationship-typo coercion is logged in
`raw_all.jsonl`.
