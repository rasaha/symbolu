# Track F Smoke Pilot — Operator Runbook (Mistral, RunPod / local GPU)

**Claude did not run this pilot.** The operator runs it manually on a GPU host; the build sandbox
has no GPU and cannot reach model hosts. Nothing runs the model automatically.

**Invariants:** `frozen/manifest.json` stays NOT_READY; the **base** smoke manifest
(`track_f_smoke_manifest.json`) stays `run_enabled:false` / `NOT_APPROVED` (authorization is the
*separate* `track_f_smoke_approved_run_config.json`); Stage A untouched; four-sphere JSON not
integrated; **Track B remains BLOCKED**; no `ONTOLOGICAL_SIGNAL`, no Sanskrit privilege. **Result is
exploratory triage only, not validation, and does not claim varṇa truth.**

Config: answer model `mistralai/Mistral-7B-Instruct-v0.3`, temp 0.0, max tokens 256, JSON-only, no
browsing, no carryover. **Judge separation:** no distinct judge model is supplied, so single-model
judging (Mistral judging its own anonymized outputs) is **exploratory / weaker** and reported as
such.

## 1. Branch + commit
```bash
cd /workspace/symbolu
git branch --show-current          # expect: claude/symbolu-adversarial-eval-zevb4h
git pull origin claude/symbolu-adversarial-eval-zevb4h
git rev-parse --short HEAD
```

## 2. GPU / CUDA
```bash
nvidia-smi
python3 -c "import torch; print('cuda:', torch.cuda.is_available())"
```
ABORT if no GPU / `cuda: False`.

## 3. Dependencies
```bash
python3 -c "import torch,transformers,accelerate" 2>/dev/null \
  || pip install --upgrade "torch" "transformers>=4.44" "accelerate" "sentencepiece"
```

## 4. Unit tests (no models)
```bash
cd /workspace/symbolu/experiments/primitive_sequence_recovery
python3 test_track_f_harness.py
```
ABORT if it fails.

## 5. Dry-run packet preview (no models)
```bash
cd /workspace/symbolu/experiments/primitive_sequence_recovery
python3 run_track_f_smoke_mistral.py --dry-check
```
Expect: `packets=72 leak=clean arm_randomized=True no_hidden_labels=True no_four_sphere=True model_calls=0` → `[dry-check] OK`. ABORT if leak ≠ clean or packet count ≠ 72.

## 6. Set approval env
```bash
export TRACK_F_SMOKE_RUN_APPROVED=I_APPROVE_TRACK_F_SMOKE
```

## 7. Run the Mistral smoke pilot
```bash
cd /workspace/symbolu
python3 experiments/primitive_sequence_recovery/run_track_f_smoke_mistral.py \
  --approval-config experiments/primitive_sequence_recovery/track_f_smoke_approved_run_config.json \
  --judge-mode single
```
This validates the approved config (base manifest untouched), emits the 72 packets, runs Mistral
(JSON-only, temp 0) over them, and — with `--judge-mode single` — runs the exploratory single-model
judge. It writes `track_f_smoke_outputs.json` + `TRACK_F_SMOKE_RESULT.md` and self-aborts if the
malformed-JSON rate exceeds 15%. (Omit `--judge-mode single` to collect answers only.)

## 8. Abort checks
| Condition | Action |
|---|---|
| dry-run leak ≠ clean or packets ≠ 72 | stop; do not load model |
| GPU unavailable / model download fails | stop; fix and retry |
| malformed-JSON rate > 15% | runner self-aborts → `INCONCLUSIVE` |
| forbidden label as actual label (`ONTOLOGICAL_SIGNAL` / `SANSKRIT_PRIVILEGE`) | stop; do not commit; report bug |
| scorer/judge names Sanskrit/varṇa/root | treat as contamination; label not a positive |

## 9. Collect / inspect
```bash
cd /workspace/symbolu/experiments/primitive_sequence_recovery
python3 -c "import json;o=json.load(open('track_f_smoke_outputs.json'));print(o['primary_label'], 'malformed', o['malformed_rate'], '| judge', o['judge_mode'], '|', o['judge_note'])"
python3 -c "import json;m=json.load(open('track_f_smoke_manifest.json'));print('base manifest:',m['run_enabled'],m['approval_status'])"   # -> False NOT_APPROVED
```

## 10. Commit the result (only after inspecting; no forbidden label)
```bash
cd /workspace/symbolu
git add experiments/primitive_sequence_recovery/track_f_smoke_outputs.json \
        experiments/primitive_sequence_recovery/TRACK_F_SMOKE_RESULT.md
git commit -m "Track F smoke pilot result (Mistral; exploratory triage only)"
git push -u origin claude/symbolu-adversarial-eval-zevb4h
```
Or paste the printed summary back to Claude to commit.

## Interpretation limits

Labels: `INFERENCE_STEERING_SIGNAL` (specific + useful + correctness-preserving), else
`PROMPT_PRIMING_ONLY` / `SCRAMBLE_EQUIVALENT` / `BARNUM_EQUIVALENT` / `CORRECTNESS_DEGRADED` /
`NO_EFFECT` / `INCONCLUSIVE`. A single-model-judged smoke cannot validate anything; even a positive
is engineering utility (and provisional without answer≠judge separation), never varṇa truth, and
would only justify a larger pre-registered pilot. Track B stays blocked regardless.

---

Track F Mistral smoke operator package. Claude did not run the pilot. Track B remains blocked. Structure, not validated meaning.
