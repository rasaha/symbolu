# B1.3 v3-Authoritative Runner — Readiness Note

**Reuse decision:** `B1_1_JUDGE_LAYER_REUSABLE_B1_3_SCORER_REQUIRED` (commit 6168138).

- **B1.1 judge layer — reused** (execution only): `run_b1_llm_judge.py` `LlamaJudgeAdapter` / `MockJudgeAdapter`
  pattern, `validate_judge`, `DECLARED_JUDGES` (Llama-3.1-8B, Llama-3-8B, Gemma-2-9b), and the structured-JSON /
  retry / refusal plumbing. Cross-family, non-Claude (not generator-adjacent).
- **B1.3 scorer — required**: `score_b1_3_concrete_object_llm.py` (frozen; own arms/thresholds/labels).
- **B1.1 scorer — NOT reused**: different arms (A vs D/S/R_same/R_deranged/R_domain/C/X), thresholds,
  `RANDOM_OR_SCRAMBLED_MATCHES` verdict, and `tie→0.5` — all excluded. B1.3 uses forced A/B (tie→invalid).
- **B1.3 packets/prompt/parser — B1.3's own**: blinded A/B packets (arm identity, keys, source, metadata, and
  v2/v3 provenance hidden), forced-A/B parser that rejects B1.1 `output_1/output_2/tie/both_bad`.

**Artifacts added:** `run_b1_3_v3_with_b1_1_judges.py`, `test_run_b1_3_v3_with_b1_1_judges.py` (**10/10** mock
tests PASS), `b1_3_v3_b1_1_judge_runner_config.json`, `B1_3_V3_RUNPOD_B1_1_JUDGE_RUNBOOK.md`.

**3-model run implemented:** `score-frozen` (post-freeze) runs the full loop — for each of the **3 judges**
(Llama-3.1-8B, Llama-3-8B, Gemma-2-9b) over all **371** comparisons it builds a blinded A/B packet, calls the
judge, parses A/B, and appends one row per (item, comparison, model) → **1113 rows** in
`b1_3_v3_judge_outputs.jsonl` (resumable), then invokes the frozen B1.3 scorer. The mock test exercises the
entire loop (3 × 371 = 1113 rows) with **no model call, no freeze, into a temp dir**. Both hard gates
(operator EVIDENCE_FREEZE declaration file + artifact hash match) must pass before any real model call.

**Run state:** `freeze-check` → ready (16 artifacts hash-match; v3 source audit pass; judge IDs in declared
panel; scorer present). `probe-only` (mock) → all 3 judges compliant on synthetic items. `score-frozen` →
**refuses** (no operator EVIDENCE_FREEZE declaration; the runner never creates one).

**Pending:** the real run remains pending an explicit operator **EVIDENCE_FREEZE** declaration on a model-access
(RunPod) host where the open-weight judges are callable. No evidence freeze declared. Nothing run or scored.
Track B remains BLOCKED. Structure, not validated meaning.
