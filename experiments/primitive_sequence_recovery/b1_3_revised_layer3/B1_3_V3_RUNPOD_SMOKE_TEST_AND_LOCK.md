# B1.3 v3-Authoritative — RunPod Smoke Test, Locking, and Run

Operator commands for: (A) smoke test (no model), (B) locking mechanisms before the run, (C) the run itself.
**Nothing here is executed by the assistant.** No EVIDENCE_FREEZE declared, no scoring, no model call by the
assistant. Track B BLOCKED. **Structure, not validated meaning.**

> **Note on "generation":** for B1.3 v3 there is **no separate generation step** — the 371 stimuli are already
> generated and frozen (`b1_3_concrete_object_final_stimuli_draft_v3_authoritative.jsonl`). The "run" is the
> blinded **judge run + frozen B1.3 scorer**. Do **not** re-generate stimuli; regenerating would break the
> frozen hashes.

Judges: `meta-llama/Llama-3.1-8B-Instruct`, `meta-llama/Meta-Llama-3-8B-Instruct`, `google/gemma-2-9b-it`.

---

## A. Smoke test (mock — NO model, NO scoring)

```bash
cd symbolu/experiments/primitive_sequence_recovery

# 0. clean tree + correct commit
git fetch origin claude/symbolu-adversarial-eval-zevb4h
git checkout claude/symbolu-adversarial-eval-zevb4h && git pull
git merge-base --is-ancestor 9cec5b0 HEAD && echo "OK commit present" || echo "STOP: commit missing"
git status --porcelain | grep . && echo "STOP: dirty tree" || echo "OK clean tree"

# 1. mock unit tests (no model)
python3 test_run_b1_3_v3_with_b1_1_judges.py          # expect 9/9 PASS
python3 b1_3_revised_layer3/test_score_b1_3_concrete_object_llm.py   # expect 10/10 PASS

# 2. mock probe-only (plumbing + A/B parser; no model)
python3 run_b1_3_v3_with_b1_1_judges.py --mode probe-only            # 3 judges compliant on synthetic items

# 3. freeze-check (hashes / source / judges / scorer; no scoring)
python3 run_b1_3_v3_with_b1_1_judges.py --mode freeze-check          # expect ready=true
```
If any smoke step fails → **STOP**. Do not lock, do not run.

## B. Locking mechanisms (BEFORE the run) — do these in order

### B1. Record a hash lock of the 16 active artifacts (immutable evidence baseline)

```bash
cd b1_3_revised_layer3
sha256sum \
  b1_3_concrete_object_final_primary_wordlist.json \
  b1_3_concrete_object_deranged_source_map.json \
  b1_3_concrete_object_generation_template_spec.json \
  b1_3_concrete_object_arm_construction_spec.json \
  b1_3_concrete_object_semantic_baseline_spec.json \
  b1_3_concrete_object_deranged_stratification_spec.json \
  b1_3_concrete_object_llm_scoring_contract_v2.json \
  b1_3_concrete_object_llm_style_audit_protocol_draft.json \
  b1_3_concrete_object_llm_judge_spec.json \
  score_b1_3_concrete_object_llm.py \
  test_score_b1_3_concrete_object_llm.py \
  b1_3_concrete_object_llm_judge_model_config_v2.json \
  b1_3_authoritative_varna_bridge_pool.json \
  b1_3_concrete_object_final_stimuli_draft_v3_authoritative.jsonl \
  b1_3_concrete_object_style_audit_report_v3_authoritative.json \
  b1_3_v3_authoritative_source_audit.json \
  | tee b1_3_v3_LOCK.sha256
cd ..

# confirm the freeze manifest itself matches the value attested in the operator sequence:
python3 -c "import hashlib;print(hashlib.sha256(open('b1_3_revised_layer3/b1_3_concrete_object_llm_freeze_review_manifest_v3_authoritative.json','rb').read()).hexdigest())"
# must print: 1bfeee516488d093283153cbf13d372613a8c85e9ddc6d5840c331e1b7bbfaf9
```

### B2. Filesystem lock — make the active artifacts read-only (prevents accidental mutation during the run)

```bash
cd b1_3_revised_layer3
chmod 0444 \
  b1_3_concrete_object_final_primary_wordlist.json \
  b1_3_concrete_object_deranged_source_map.json \
  b1_3_concrete_object_generation_template_spec.json \
  b1_3_concrete_object_arm_construction_spec.json \
  b1_3_concrete_object_semantic_baseline_spec.json \
  b1_3_concrete_object_deranged_stratification_spec.json \
  b1_3_concrete_object_llm_scoring_contract_v2.json \
  b1_3_concrete_object_llm_style_audit_protocol_draft.json \
  b1_3_concrete_object_llm_judge_spec.json \
  score_b1_3_concrete_object_llm.py \
  b1_3_concrete_object_llm_judge_model_config_v2.json \
  b1_3_authoritative_varna_bridge_pool.json \
  b1_3_concrete_object_final_stimuli_draft_v3_authoritative.jsonl \
  b1_3_concrete_object_style_audit_report_v3_authoritative.json \
  b1_3_v3_authoritative_source_audit.json
cd ..
```

### B3. Git lock — tag the exact commit (immutable pointer for the frozen run)

```bash
git tag -a b1_3_v3_evidence_freeze -m "B1.3 v3-authoritative EVIDENCE_FREEZE point"
git rev-parse b1_3_v3_evidence_freeze     # record this hash in the run log
# (optional) push the tag if the repo policy allows: git push origin b1_3_v3_evidence_freeze
```

### B4. EVIDENCE_FREEZE declaration (the logical lock — OPERATOR creates it)

Create `b1_3_revised_layer3/b1_3_v3_EVIDENCE_FREEZE_DECLARED.json` with the exact contents from
`B1_3_V3_RUNPOD_OPERATOR_SEQUENCE.md` §4 (must contain `"evidence_freeze_declared": true`,
`freeze_manifest_sha256: 1bfeee51…faf9`, the 3 pinned judge IDs, and your attestation). The runner **refuses**
`score-frozen` until this file exists.

### B5. Re-verify the lock immediately before the run

```bash
cd b1_3_revised_layer3 && sha256sum -c b1_3_v3_LOCK.sha256 && cd ..   # all OK
python3 run_b1_3_v3_with_b1_1_judges.py --mode freeze-check           # ready=true again
```
Any mismatch → **STOP**: an artifact changed after locking; do not run.

## C. The run (judge run + frozen scorer) — DO NOT RUN UNTIL B4 FILE EXISTS

```bash
# DO NOT RUN UNTIL b1_3_v3_EVIDENCE_FREEZE_DECLARED.json EXISTS (Step B4).
mkdir -p run_out

# judge run over the 371 comparisons with the real open-weight panel:
python3 run_b1_3_v3_with_b1_1_judges.py --mode score-frozen --real

# score with the FROZEN B1.3 scorer:
python3 b1_3_revised_layer3/score_b1_3_concrete_object_llm.py \
    --stimuli   b1_3_revised_layer3/b1_3_concrete_object_final_stimuli_draft_v3_authoritative.jsonl \
    --judge-outputs run_out/b1_3_v3_judge_outputs.jsonl \
    --style-audit b1_3_revised_layer3/b1_3_concrete_object_style_audit_report_v3_authoritative.json \
    --contract  b1_3_revised_layer3/b1_3_concrete_object_llm_scoring_contract_v2.json \
    --out-json  run_out/b1_3_v3_score_report.json \
    --out-md    run_out/b1_3_v3_score_report.md
```
(Post-run summary commands are in `B1_3_V3_RUNPOD_OPERATOR_SEQUENCE.md` §6.)

## Unlock / cleanup (only after the run + review)

```bash
# restore write bits if you need to iterate on a NEW versioned study (never edit frozen v3 in place):
cd b1_3_revised_layer3 && chmod 0644 b1_3_*.json *.py *.jsonl && cd ..
```

## Guardrails

Smoke test is mock-only (no model, no scoring). Locking is hash-lock + read-only + git tag + operator
declaration. `score-frozen` refuses without the declaration file. The assistant does not declare EVIDENCE_FREEZE,
create the declaration file, run score-frozen, score, re-generate stimuli, or edit thresholds/lexicon. No
ONTOLOGICAL_SIGNAL, no Sanskrit privilege. Track B stays BLOCKED until the frozen run is completed, scored, and
reviewed.

**B1.3 v3-authoritative is ready for operator smoke test and locking. No evidence freeze declared. Nothing run
or scored. Track B remains blocked. Structure, not validated meaning.**
