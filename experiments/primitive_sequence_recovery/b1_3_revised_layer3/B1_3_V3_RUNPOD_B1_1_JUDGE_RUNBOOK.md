# B1.3 v3-Authoritative — RunPod Runbook (B1.1 judge execution layer)

Runs the B1.3 v3-authoritative judged-modulation study on a **model-access host** (e.g. RunPod) using the
**B1.1 open-weight judge execution layer** with **B1.3 packets, B1.3 A/B parsing, and the frozen B1.3 scorer**.
Runner: `experiments/primitive_sequence_recovery/run_b1_3_v3_with_b1_1_judges.py`.

**EVIDENCE_FREEZE is NOT declared. `score-frozen` must NOT be run until the operator declares freeze.**
Track B BLOCKED. Structure, not validated meaning.

## Judges (open-weight, cross-family, non-Claude)

- `meta-llama/Llama-3.1-8B-Instruct` (Meta / Llama)
- `meta-llama/Meta-Llama-3-8B-Instruct` (Meta / Llama)
- `google/gemma-2-9b-it` (Google / Gemma)

## 0. Repo pull

```bash
git clone <repo-url> symbolu && cd symbolu
git checkout claude/symbolu-adversarial-eval-zevb4h
git pull origin claude/symbolu-adversarial-eval-zevb4h
cd experiments/primitive_sequence_recovery
```

## 1. Dependency check

```bash
python3 -c "import json, hashlib; print('stdlib ok')"
# real judging only (NOT needed for probe-mock / freeze-check / tests):
python3 -c "import torch, transformers; print('torch', torch.__version__, 'transformers', transformers.__version__)"
# GPU (real judging): nvidia-smi
```

## 2. Mock tests (no model, no scoring)

```bash
python3 test_run_b1_3_v3_with_b1_1_judges.py      # expect 9/9 PASS
```

## 3. probe-only (synthetic A/B compliance; no real B1.3 items)

```bash
# mock (no model) — verifies plumbing + A/B parser:
python3 run_b1_3_v3_with_b1_1_judges.py --mode probe-only
# real models on the pod — verifies each judge emits compliant A/B on synthetic 'widget' prompts:
python3 run_b1_3_v3_with_b1_1_judges.py --mode probe-only --real
```
If any judge's synthetic invalid rate is high, fix/exclude it **before** freeze (do not coerce output).

## 4. freeze-check (hashes / config; no scoring)

```bash
python3 run_b1_3_v3_with_b1_1_judges.py --mode freeze-check
# expect: hashes_ok=true, v3_source_audit_pass=true, judge_ids_in_declared_panel=true,
#         scorer_present=true, ready=true
```
This re-hashes the 16 bound v3 artifacts vs the freeze manifest, confirms the v3 source audit passed, confirms
the judge IDs are in the B1.1 declared panel, and confirms the frozen scorer is present. It does **not** score.

## 5. score-frozen — DO NOT RUN UNTIL EVIDENCE_FREEZE IS DECLARED

`score-frozen` **refuses** unless the operator has created
`b1_3_revised_layer3/b1_3_v3_EVIDENCE_FREEZE_DECLARED.json` (the runner never creates it). After a genuine
operator freeze (exact model IDs pinned, probe passed, hashes confirmed):

```bash
# (OPERATOR) create the declaration file with evidence_freeze_declared=true + attestation + manifest sha256.
# then, on the model host:
python3 run_b1_3_v3_with_b1_1_judges.py --mode score-frozen --real
# -> builds blinded A/B packets over the 371 comparisons, calls the 3 judges,
#    writes raw judge outputs, then invokes the FROZEN B1.3 scorer:
python3 b1_3_revised_layer3/score_b1_3_concrete_object_llm.py \
    --stimuli   b1_3_revised_layer3/b1_3_concrete_object_final_stimuli_draft_v3_authoritative.jsonl \
    --judge-outputs <OUT_DIR>/b1_3_v3_judge_outputs.jsonl \
    --style-audit b1_3_revised_layer3/b1_3_concrete_object_style_audit_report_v3_authoritative.json \
    --contract  b1_3_revised_layer3/b1_3_concrete_object_llm_scoring_contract_v2.json \
    --out-json  <OUT_DIR>/b1_3_v3_score_report.json \
    --out-md    <OUT_DIR>/b1_3_v3_score_report.md
```

## 6. Result summary

```bash
python3 -c "import json,sys; r=json.load(open(sys.argv[1])); print('terminal_label:', r['terminal_label']); \
print('primary:', r['primary_endpoint']['result']); print('reasons:', r['decision_reasons'])" \
    <OUT_DIR>/b1_3_v3_score_report.json
```

## Guardrails

Reuses **only** the B1.1 judge execution plumbing (adapters/panel/JSON-retry-refusal). Uses B1.3's own packets,
A/B prompt, parser, and the **frozen B1.3 scorer** (B1.1 scorer NOT reused). Does not declare EVIDENCE_FREEZE,
modify v3 stimuli, change scorer thresholds, edit the authoritative lexicon, or overwrite v2. `score-frozen`
refuses without an operator freeze declaration. Track B BLOCKED. Structure, not validated meaning.
