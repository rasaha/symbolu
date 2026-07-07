# B1.3 v3-Authoritative — RunPod Operator Sequence

Exact operator sequence for the B1.3 v3-authoritative run on a model-access (RunPod) host, using the committed
B1.1-judge runner. **Nothing here is executed by the assistant.** EVIDENCE_FREEZE is **not** declared; the
assistant does not create the freeze file, does not run score-frozen, does not score. Track B BLOCKED.
**Structure, not validated meaning.**

Judge panel (open-weight, cross-family, non-Claude): `meta-llama/Llama-3.1-8B-Instruct`,
`meta-llama/Meta-Llama-3-8B-Instruct`, `google/gemma-2-9b-it`.

---

## Step 1 — Pull latest repo and verify commit

```bash
git clone <repo-url> symbolu && cd symbolu
git fetch origin claude/symbolu-adversarial-eval-zevb4h
git checkout claude/symbolu-adversarial-eval-zevb4h
git pull origin claude/symbolu-adversarial-eval-zevb4h

# verify you are at (or ahead of) the runner commit:
git log --oneline -1
# expect the runner commit in history:
git merge-base --is-ancestor 30a0210 HEAD && echo "OK: 30a0210 present" || echo "STOP: runner commit missing"

cd experiments/primitive_sequence_recovery

# GPU + deps for REAL judging (not needed for mock/freeze-check):
nvidia-smi
python3 -c "import torch, transformers; print('torch', torch.__version__, 'transformers', transformers.__version__)"

# sanity: mock tests must be green before anything real
python3 test_run_b1_3_v3_with_b1_1_judges.py      # expect 9/9 PASS
```

## Step 2 — Real probe-only (synthetic prompts only; NO real B1.3 scoring)

```bash
python3 run_b1_3_v3_with_b1_1_judges.py --mode probe-only --real
```
- Runs each of the 3 judges on harmless **synthetic** `widget`/`gizmo` A/B prompts (never real B1.3 items).
- **Pass criterion:** every judge returns compliant `A`/`B` with a low invalid rate (target `invalid = 0`,
  hard cap 10%). A judge that refuses/malforms above cap must be **fixed or excluded before freeze** — do not
  coerce output.
- Produces **no** score and **no** judge-output artifact for the study.

## Step 3 — freeze-check (hashes / source / judges / scorer; NO scoring)

```bash
python3 run_b1_3_v3_with_b1_1_judges.py --mode freeze-check
```
Expect all true:
```
hashes_ok=true                    # 16 bound v3 artifacts match the freeze manifest
v3_source_audit_pass=true         # V3_AUTHORITATIVE_SOURCE_AUDIT_PASS
judge_ids_in_declared_panel=true  # the 3 judges are in the B1.1 declared panel
scorer_present=true               # frozen B1.3 scorer present
ready=true
```
If any is false → **STOP**, do not freeze; investigate (hash drift, missing scorer, panel mismatch).

## Step 4 — If Steps 2 and 3 both pass: EVIDENCE_FREEZE declaration file (OPERATOR CREATES THIS)

Create `experiments/primitive_sequence_recovery/b1_3_revised_layer3/b1_3_v3_EVIDENCE_FREEZE_DECLARED.json`
with exactly this content (fill the operator/date fields; the runner strictly requires
`evidence_freeze_declared: true`, the rest is the binding record):

```json
{
  "artifact": "b1_3_v3_EVIDENCE_FREEZE_DECLARED",
  "evidence_freeze_declared": true,
  "study": "B1.3 concrete-object LLM judged-modulation (v3-authoritative)",
  "declared_by": "<operator name/id>",
  "declared_at_utc": "<YYYY-MM-DDTHH:MM:SSZ>",
  "runner_commit": "30a0210",
  "stimuli": "b1_3_concrete_object_final_stimuli_draft_v3_authoritative.jsonl",
  "scorer": "score_b1_3_concrete_object_llm.py",
  "scoring_contract": "b1_3_concrete_object_llm_scoring_contract_v2.json",
  "freeze_manifest": "b1_3_concrete_object_llm_freeze_review_manifest_v3_authoritative.json",
  "freeze_manifest_sha256": "1bfeee516488d093283153cbf13d372613a8c85e9ddc6d5840c331e1b7bbfaf9",
  "pinned_judge_model_ids": [
    "meta-llama/Llama-3.1-8B-Instruct",
    "meta-llama/Meta-Llama-3-8B-Instruct",
    "google/gemma-2-9b-it"
  ],
  "probe_only_passed": true,
  "freeze_check_passed": true,
  "attestation": "I have verified real probe-only compliance and freeze-check; I authorize the frozen run. No artifact may change after this point except via a new versioned study.",
  "post_freeze_rule": "no changes to stimuli, thresholds, prompts, scorer, or judge IDs after freeze"
}
```
> Before creating it, re-confirm the manifest hash on the host matches the value above:
> ```bash
> python3 -c "import hashlib; print(hashlib.sha256(open('b1_3_revised_layer3/b1_3_concrete_object_llm_freeze_review_manifest_v3_authoritative.json','rb').read()).hexdigest())"
> # must print: 1bfeee516488d093283153cbf13d372613a8c85e9ddc6d5840c331e1b7bbfaf9
> ```
> If it differs, an active artifact changed → **STOP**, do not freeze.

## Step 5 — score-frozen — **DO NOT RUN UNTIL I CREATE THE EVIDENCE_FREEZE FILE**

```bash
# DO NOT RUN UNTIL b1_3_v3_EVIDENCE_FREEZE_DECLARED.json EXISTS (Step 4).
# The runner REFUSES if the declaration file is absent.
mkdir -p run_out
python3 run_b1_3_v3_with_b1_1_judges.py --mode score-frozen --real

# then score with the FROZEN B1.3 scorer over the raw judge outputs the runner wrote:
python3 b1_3_revised_layer3/score_b1_3_concrete_object_llm.py \
    --stimuli   b1_3_revised_layer3/b1_3_concrete_object_final_stimuli_draft_v3_authoritative.jsonl \
    --judge-outputs run_out/b1_3_v3_judge_outputs.jsonl \
    --style-audit b1_3_revised_layer3/b1_3_concrete_object_style_audit_report_v3_authoritative.json \
    --contract  b1_3_revised_layer3/b1_3_concrete_object_llm_scoring_contract_v2.json \
    --out-json  run_out/b1_3_v3_score_report.json \
    --out-md    run_out/b1_3_v3_score_report.md
```

## Step 6 — Post-run summary

```bash
R=run_out/b1_3_v3_score_report.json

# terminal label + decision reasons
python3 -c "import json;r=json.load(open('$R'));print('TERMINAL_LABEL:',r['terminal_label']);print('REASONS:',r['decision_reasons'])"

# primary endpoint + all comparison metrics (win rate, CI, Holm p)
python3 -c "import json;r=json.load(open('$R'));print('PRIMARY:',r['primary_endpoint']);[print(c,r['comparison_results'][c]) for c in r['comparison_results']]"

# near/mid/far gradient
python3 -c "import json;r=json.load(open('$R'));print('GRADIENT:',r['near_mid_far_gradient'])"

# per-judge / per-model-family + item-family summary
python3 -c "import json;r=json.load(open('$R'));print('MODEL_FAMILY:',r['model_family_breakdown']);print('SINGLE_FAMILY_DOMINATES:',r['single_model_family_dominates']);print('ITEM_FAMILY:',r['item_family_breakdown'])"

# malformed / refusal / invalid counts
python3 -c "import json;r=json.load(open('$R'));print('INVALID_SUMMARY:',r['invalid_summary'])"

# audit + threshold pass/fail
python3 -c "import json;r=json.load(open('$R'));print('AUDIT:',r['audit_summary']);print('THRESHOLDS:',r['threshold_summary'])"

# output files created
ls -la run_out/

# Track B status (remains BLOCKED until this frozen run is completed AND scored and reviewed)
echo "Track B: BLOCKED until frozen run completed + scored + reviewed"
```

## Interpretation guardrails (unchanged)

- Terminal label is whatever the frozen scorer emits: one of STRONG / CATEGORY_LIMITED / NULL /
  STYLE_CONFOUNDED / SEMANTIC_BASELINE_EXPLAINS / INVALID_RUN. **Report it as-is** — a NULL /
  SEMANTIC_BASELINE_EXPLAINS is the expected, acceptable outcome (semantic baseline still names object-function;
  prior is low).
- **No** ONTOLOGICAL_SIGNAL, **no** Sanskrit privilege, **no** semantic-truth claim regardless of label.
- Track B stays BLOCKED until the frozen run is completed, scored, and reviewed.
- No post-freeze edits to stimuli, thresholds, prompts, scorer, or judge IDs — any change spawns a new
  versioned study.

---

**B1.3 v3-authoritative is ready for operator real-probe and freeze-check. No evidence freeze declared. Nothing
scored. Track B remains blocked. Structure, not validated meaning.**
