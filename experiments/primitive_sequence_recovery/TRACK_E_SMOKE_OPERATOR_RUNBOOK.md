# Track E Smoke Pilot — Operator Runbook (RunPod / local GPU)

**Claude did not run this pilot.** This runbook is for the **operator** to execute manually on a
GPU host. The build sandbox has no GPU and cannot reach model hosts, so the real scoring runs here,
on your pod. Nothing in this repo runs the models automatically.

**Invariants that must hold throughout:** `frozen/manifest.json` stays **NOT_READY**; the **base**
smoke manifest (`track_e_smoke_manifest.json`) stays **`run_enabled:false` / `NOT_APPROVED`**
(authorization comes from the *separate* `track_e_smoke_approved_run_config.json`); Stage A
untouched; four-sphere JSON **not integrated**; **Track B remains BLOCKED regardless of result**; no
`ONTOLOGICAL_SIGNAL`, no Sanskrit privilege. **The result is exploratory triage only, not
validation.**

Approved config: generator `Qwen/Qwen2.5-7B-Instruct`, scorer `mistralai/Mistral-7B-Instruct-v0.3`
(generator ≠ scorer), temp `0.0`, max tokens `256`, JSON-only, browsing off, no carryover. Note:
the 108 packets are pre-authored from the frozen bundle, so **only the scorer model is exercised**;
the generator id is recorded for protocol completeness.

---

## 0. Where things are

- Repo root on the pod: `/workspace/symbolu`
- Experiment dir: `/workspace/symbolu/experiments/primitive_sequence_recovery`
- Pure runner (no model calls): `track_e_smoke_runner.py`
- GPU scorer (this run): `run_track_e_smoke_runpod.py`
- Separate approved config: `track_e_smoke_approved_run_config.json`
- Expected output: `track_e_smoke_result.json` (+ `TRACK_E_SMOKE_RESULT.md`)

## 1. Confirm branch & commit

```bash
cd /workspace/symbolu
git rev-parse --show-toplevel
git branch --show-current          # expect: claude/symbolu-adversarial-eval-zevb4h
git rev-parse --short HEAD
```

## 2. Pull latest branch

```bash
cd /workspace/symbolu
git fetch origin && git pull origin claude/symbolu-adversarial-eval-zevb4h
```

## 3. Verify GPU / CUDA

```bash
nvidia-smi                          # confirm a GPU is present (e.g. RTX 6000 Ada, 48 GB)
python3 -c "import torch; print('cuda:', torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```
**ABORT if** no GPU is listed or `cuda: False` (see §9).

## 4. Install dependencies if needed

```bash
python3 -c "import torch, transformers, accelerate" 2>/dev/null \
  || pip install --upgrade "torch" "transformers>=4.44" "accelerate" "sentencepiece"
```
(Models download from Hugging Face on first use; ensure the pod has network + any HF token needed.)

## 5. Run unit tests (no models)

```bash
cd /workspace/symbolu/experiments/primitive_sequence_recovery
python3 test_track_e_harness.py
python3 test_track_e_smoke_runner.py
```
**ABORT if** either suite fails.

## 6. Dry-run packet preview + leak scan (no models)

```bash
cd /workspace/symbolu/experiments/primitive_sequence_recovery
python3 run_track_e_smoke_runpod.py --dry-check
```
Expect: `packets=108 leak=clean shuffled_ok=True model_calls=0` then `[dry-check] OK`.
Independent confirmation:
```bash
python3 -c "
import track_e_smoke_runner as R
rep,pk,hid=R.dry_run()
assert rep['n_packets']==108, rep
assert rep['leak_scan']=='clean' and rep['all_shuffled_differ_from_authored']
assert rep['model_calls']==0
assert sum(1 for p in pk if set(p)&{'true_arm','correct_candidate_id','opt_to_cand'})==0
assert not any('sphere' in ' '.join(R._scorer_facing_strings(p)).lower() for p in pk)
print('CONFIRMED: 108 packets, leak-clean, shuffled, hidden-key separate, no four-sphere')
"
```
**ABORT if** packet count ≠ 108 or leak scan is not clean (see §9).

## 7. Enable the approved run (separate config — base manifest stays false)

Authorization is the separate `track_e_smoke_approved_run_config.json` (already
`run_enabled:true` / `APPROVED`); the base smoke manifest is **not** edited. Arm the run with the
env token, and confirm the config is accepted while the base manifest stays gated:

```bash
export TRACK_E_SMOKE_RUN_APPROVED=I_APPROVE_TRACK_E_SMOKE
python3 track_e_smoke_runner.py \
  --approval-config track_e_smoke_approved_run_config.json    # prints "approval config accepted: PACKETS_EMITTED..."
python3 -c "import json;m=json.load(open('track_e_smoke_manifest.json'));print('base manifest:',m['run_enabled'],m['approval_status'])"
# expect: base manifest: False NOT_APPROVED
```

## 8. Run the real smoke pilot (scorer model runs here)

```bash
cd /workspace/symbolu
python3 experiments/primitive_sequence_recovery/run_track_e_smoke_runpod.py \
  --approval-config experiments/primitive_sequence_recovery/track_e_smoke_approved_run_config.json
```
This: re-runs the dry-run/leak scan, validates the approved config, emits the 108 packets, runs the
**scorer** model over them (JSON-only, temp 0), validates + ingests outputs, computes metrics via
the harness, and writes `track_e_smoke_result.json` + `TRACK_E_SMOKE_RESULT.md`. It self-aborts if
the malformed-JSON rate exceeds 15%.

## 9. Abort conditions (stop and do not report a result as valid)

| Condition | Check / action |
|---|---|
| dry-run leak scan fails | §6 prints leak ≠ clean → **stop**; do not run models |
| packet count ≠ 108 | §6 assertion fails → **stop** |
| GPU unavailable | §3 `cuda: False` / no `nvidia-smi` → **stop** |
| model download fails | §4/§8 raises on `from_pretrained` → **stop**, fix network/HF token, retry |
| malformed JSON rate too high | runner self-aborts (>15%); label recorded `INCONCLUSIVE` |
| output missing | §10 shows no `track_e_smoke_result.json` → **stop**; re-run |
| forbidden label as actual label | §10 check finds `ONTOLOGICAL_SIGNAL`/`SANSKRIT_PRIVILEGE`/`EXPERIENTIAL_WEATHER_SIGNAL` in `primary_label` → **stop**, do not commit, report the bug |
| scorer names Sanskrit/varṇa/root | runner flags contamination → label `LLM_SMOKE_CONTAMINATED` (never a positive) |

## 10. Collect / inspect results

```bash
cd /workspace/symbolu/experiments/primitive_sequence_recovery
ls -l track_e_smoke_result.json TRACK_E_SMOKE_RESULT.md      # confirm they exist
python3 -c "
import json
r=json.load(open('track_e_smoke_result.json'))
print('primary_label   :', r['primary_label'])
print('per_arm_means   :', r['per_arm_means'])
print('deltas          :', r['deltas'])
print('malformed_rate  :', r['malformed_rate'])
print('contamination   :', r['contamination_notes'])
print('abort_events    :', r['abort_events'])
print('full_pilot_just.:', r['full_pilot_justified'])
FORB={'ONTOLOGICAL_SIGNAL','SANSKRIT_PRIVILEGE','EXPERIENTIAL_WEATHER_SIGNAL'}
assert r['primary_label'] not in FORB, 'FORBIDDEN LABEL EMITTED — do not commit'
print('OK: no forbidden label')
"
```

## 11. Confirm guardrails after the run

```bash
cd /workspace/symbolu
python3 -c "import json;print('frozen:', json.load(open('experiments/primitive_sequence_recovery/frozen/manifest.json'))['status'])"   # NOT_READY
python3 -c "import json;m=json.load(open('experiments/primitive_sequence_recovery/track_e_smoke_manifest.json'));print('base smoke manifest:',m['run_enabled'],m['approval_status'])"  # False NOT_APPROVED
git diff --stat -- symbolu_neural/structural_v1        # empty = Stage A untouched
git status --porcelain                                 # expect only track_e_smoke_result.json + TRACK_E_SMOKE_RESULT.md new
```

## 12. Commit the result (only after inspecting it)

Only commit the **result report** (and only if §10 shows no forbidden label). Do **not** commit any
change to the base smoke manifest or `frozen/manifest.json`.

```bash
cd /workspace/symbolu
git add experiments/primitive_sequence_recovery/track_e_smoke_result.json \
        experiments/primitive_sequence_recovery/TRACK_E_SMOKE_RESULT.md
git commit -m "Track E smoke pilot result (exploratory triage only; not validation)"
git push -u origin claude/symbolu-adversarial-eval-zevb4h
```
Or paste the printed summary back to Claude and it will commit the result for you.

## Interpretation (hard limits)

Acceptable outcomes: `NO_SIGNAL`, `CONTEXT_ONLY_EXPLAINS`, `BARNUM_BOUNDARY`, `SCRAMBLE_EQUIVALENT`
(default expectation). Do **not** overclaim a positive: `BOUNDARY_CONSTRAINT_SIGNAL` at smoke size
is smoke-suggestive only and cannot validate the theory — any positive merely justifies a larger,
pre-registered pilot with bootstrap CIs, seed stability, and independent replication. The Track C /
D0 negatives are unchanged, and **Track B remains blocked** regardless of this result.

---

Track E smoke operator run package created. Claude did not run the pilot. User must execute commands manually on RunPod. Track B remains blocked. Structure, not validated meaning.
