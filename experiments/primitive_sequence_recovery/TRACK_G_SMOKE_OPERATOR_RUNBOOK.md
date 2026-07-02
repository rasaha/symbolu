# Track G Smoke Pilot — Operator Runbook (RunPod / local GPU)

**Claude did not run this pilot.** For manual operator execution on a GPU host. The build sandbox
has no GPU / model access; nothing runs a model automatically.

**Invariants:** `frozen/manifest.json` stays NOT_READY; the **base** smoke manifest
(`track_g_smoke_manifest.json`) stays `run_enabled:false` / `NOT_APPROVED` (authorization is the
*separate* `track_g_smoke_approved_run_config.json` + env token); Stage A untouched; four-sphere JSON
not integrated; **Track B remains BLOCKED**; no `ONTOLOGICAL_SIGNAL`, no Sanskrit privilege.
**Polarity is frozen before scoring — post-hoc edits invalidate a case (`INVALID_POSTHOC_POLARITY`).**
Result is exploratory triage only, not validation.

## 1. Branch + commit
```bash
cd /workspace/symbolu
git branch --show-current          # expect: claude/symbolu-adversarial-eval-zevb4h
git pull origin claude/symbolu-adversarial-eval-zevb4h
git rev-parse --short HEAD
```

## 2. GPU / deps
```bash
nvidia-smi
python3 -c "import torch; print('cuda:', torch.cuda.is_available())"
python3 -c "import torch,transformers,accelerate" 2>/dev/null \
  || pip install --upgrade "torch" "transformers>=4.44" "accelerate" "sentencepiece"
```
ABORT if no GPU / `cuda: False`.

## 3. Unit tests (no models)
```bash
cd /workspace/symbolu/experiments/primitive_sequence_recovery
python3 test_track_g_harness.py
python3 test_track_g_smoke_runner.py
```
ABORT if either fails.

## 4. Dry-run packet preview (no models)
```bash
cd /workspace/symbolu/experiments/primitive_sequence_recovery
python3 track_g_smoke_runner.py --dry-check
```
Expect: `packets=90 leak=clean shuffled_ok=True arm_randomized=True no_hidden_labels=True no_four_sphere=True model_calls=0` → `[dry-check] OK`. ABORT if leak ≠ clean or packet count ≠ 90.

## 5. Prepare the approved run config (before any run)
Edit `track_g_smoke_approved_run_config.json` and fill: `scorer_model`, `approval_record.approver`,
`approval_record.date`, `approval_record.signature`. Leave `run_enabled:true` / `approval_status:
"APPROVED"` (this is the *separate* config; the **base manifest stays gated**).

## 6. Set approval env
```bash
export TRACK_G_SMOKE_RUN_APPROVED=I_APPROVE_TRACK_G_SMOKE
```

## 7. Emit packets under the approved config (still no model call inside the runner)
```bash
cd /workspace/symbolu/experiments/primitive_sequence_recovery
python3 track_g_smoke_runner.py \
  --approval-config track_g_smoke_approved_run_config.json
python3 -c "import json;m=json.load(open('track_g_smoke_manifest.json'));print('base manifest:',m['run_enabled'],m['approval_status'])"   # -> False NOT_APPROVED
```
The runner emits the 90 anonymized packets for **external** scoring; it does **not** call a model.
(A model/judge step for Track G is a separate, later, explicitly-approved addition — this package
stops at dry-run/packet-emission readiness.)

## 8. Requirements for any real run
- separate approved config (`run_enabled:true`, `approval_status:"APPROVED"`, `scorer_model` filled),
- env `TRACK_G_SMOKE_RUN_APPROVED=I_APPROVE_TRACK_G_SMOKE`,
- a **leak-clean dry-run** (§4) with 90 packets,
- polarity assignments **frozen** (no post-hoc edits) and the **random-flip (R) arm present**.

## 9. Abort checks
| Condition | Action |
|---|---|
| dry-run leak ≠ clean or packets ≠ 90 | stop |
| GPU unavailable | stop |
| any polarity assignment edited after outputs seen | `INVALID_POSTHOC_POLARITY`; discard run |
| R (random-flip) arm missing | invalid bundle; stop |
| forbidden label as an actual label | stop; do not commit; report bug |
| scorer names Sanskrit/varṇa/root | contamination; not a positive |

## 10. Interpretation limits

Labels: `POLARITY_BOUNDARY_SIGNAL` (only if A beats R, X, B, I, D — `A_vs_R` and `A_vs_X` primary),
else `RANDOM_POLARITY_EXPLAINS` / `CONTEXT_ONLY_EXPLAINS` / `SCRAMBLE_EQUIVALENT` / `BARNUM_POLARITY`
/ `NO_SIGNAL` / `INCONCLUSIVE` / `INVALID_POSTHOC_POLARITY`. A smoke cannot validate anything; even a
positive is architecture-bound, English/LLM-mediated engineering utility, never varṇa truth, and
would need a larger pre-registered pilot. Track B stays blocked regardless.

---

Track G smoke operator package. Claude did not run the pilot. Track B remains blocked. Structure, not validated meaning.
