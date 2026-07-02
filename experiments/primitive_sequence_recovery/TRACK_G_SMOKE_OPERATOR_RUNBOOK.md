# Track G Smoke Pilot — Operator Runbook (RunPod / local GPU)

**Claude did not run this pilot.** For manual operator execution on a GPU host. The build sandbox
has no GPU / model access; nothing runs a model automatically.

**Invariants:** `frozen/manifest.json` stays NOT_READY; the **base** smoke manifest
(`track_g_smoke_manifest.json`) stays `run_enabled:false` / `NOT_APPROVED` (authorization is the
*separate* `track_g_smoke_approved_run_config.json` + env token); Stage A untouched; four-sphere JSON
not integrated; **Track B remains BLOCKED**; no `ONTOLOGICAL_SIGNAL`, no Sanskrit privilege.
**Polarity is frozen before scoring — post-hoc edits invalidate a case (`INVALID_POSTHOC_POLARITY`).**
Result is exploratory triage only, not validation.

**A is varṇa-derived, not hand-authored.** The real polarity vector A is derived deterministically
by `track_g_derive.py` from `track_g_varna_polarity_table.json` (frozen per-varṇa signed axis
contributions) + each word's varṇa sequence; R = sign-flip(A); B = seeded-scramble(A). The varṇa
table is researcher-authored / high-DOF / unvalidated, so even a positive smoke is architecture-bound
utility only, never ontology.

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
python3 test_track_g_derive.py
python3 test_track_g_smoke_runner.py
```
ABORT if any fails. (`test_track_g_derive.py` proves A is varṇa-derived, not hand-authored, and
that R/B are transforms of the derived A.)

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

### 5a. Approval-config placeholder fields (inspection note — operator honesty required)

The shipped `track_g_smoke_approved_run_config.json` is a **template** with exactly **four**
`<fill…>` placeholder values you must replace before a real run:

| Field | Gate-relevant? | Notes |
|---|---|---|
| `scorer_model` | **Yes** | Must be a real, loadable model id/path (see below). |
| `approval_record.date` | **Yes** | e.g. `"2026-07-02"`. |
| `approval_record.signature` | **Yes** | Explicit approval text. |
| `approval_record.approver` | No (record-only) | Not checked by the gate, but **should be filled** for an honest record. |

- **Gate-relevant** = checked by `load_approval_config` in `track_g_smoke_runner.py`
  (`scorer_model`, `approval_record.date`, `approval_record.signature` must be non-empty; plus the
  already-correct `config_type` / `run_enabled:true` / `approval_status:"APPROVED"` /
  `four_sphere_integrated:false`).
- **Placeholders are non-empty strings, so they can PASS the gate** even though they are meaningless.
  The gate only checks presence, not validity — **operator honesty is required** to replace them
  with real values. A placeholder left in `date`/`signature` yields a dishonest record; a placeholder
  left in `scorer_model` will fail at model load (below).
- **`scorer_model` must be a real Hugging Face repo id** (e.g. `mistralai/Mistral-7B-Instruct-v0.3`)
  **or a local model path** — it is passed **directly** to
  `AutoModelForCausalLM.from_pretrained(model_id)` / `AutoTokenizer.from_pretrained(model_id)` in
  `run_track_g_smoke_mistral.py`. A `<fill…>` placeholder passes the gate but errors at load (no
  partial/fabricated output).
- **`--model-id` overrides the config value** (`model_id = args.model_id or cfg["scorer_model"] or
  DEFAULT_MODEL`); `--temperature` / `--max-new-tokens` likewise override the config.
- **No real scorer run is performed from this documentation task.** This section only records the
  inspection; running the scorer is a separate, explicitly-operator-driven step (§5–§7b) on a GPU host.

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

## 7b. Score the packets with the approved model (`run_track_g_smoke_mistral.py`) — GPU host only

This is the scorer step. It re-runs the dry-run first (0 model calls), then — only after the env
token + separate approved config pass — loads the approved model, scores the 90 packets JSON-only at
temp 0, ingests the scores into `track_g_harness`, and writes `track_g_smoke_outputs.json` +
`TRACK_G_SMOKE_RESULT.md` with one of the 8 allowed labels. Malformed scorer output is rejected; if
the malformed rate exceeds 0.15 the run aborts `INCONCLUSIVE`. It never fabricates scores and never
edits the base manifest.

```bash
cd /workspace/symbolu/experiments/primitive_sequence_recovery
export TRACK_G_SMOKE_RUN_APPROVED=I_APPROVE_TRACK_G_SMOKE
# dry-check first (no model, no writes):
python3 run_track_g_smoke_mistral.py --dry-check
# then the real scored run (loads the approved model AFTER gates pass):
python3 run_track_g_smoke_mistral.py \
  --approval-config track_g_smoke_approved_run_config.json \
  --judge-mode single
python3 -c "import json;m=json.load(open('track_g_smoke_manifest.json'));print('base manifest:',m['run_enabled'],m['approval_status'])"  # -> False NOT_APPROVED
```

### 7c. Diagnosing malformed scorer output (`--debug-dump`) — diagnostic only

If a run aborts `INCONCLUSIVE` with a high `malformed_rate` (the scorer's output failed JSON
parsing), add `--debug-dump` to capture the **raw text of the malformed generations** so the format
failure can be diagnosed:

```bash
python3 run_track_g_smoke_mistral.py \
  --approval-config track_g_smoke_approved_run_config.json \
  --judge-mode single --model-id mistralai/Mistral-7B-Instruct-v0.3 \
  --debug-dump                       # writes track_g_smoke_malformed_debug.jsonl
```

- The file `track_g_smoke_malformed_debug.jsonl` holds one JSON record per **malformed** packet:
  `packet_id`, `case_id`, `arm`, `n_opts`, `parser_error`, `contamination_detected`, `raw_text`.
- **It is diagnostic only — NOT a score artifact.** It contains no scores, no label, and does not
  feed back into `track_g_harness`; it exists solely to see what the model emitted. It is
  **gitignored and must never be committed** (it carries raw model text and the arm mapping).
- Capturing it **does not change** scores, the malformed count, the abort threshold, the 8 labels,
  packet assembly, or the frozen polarity — bare runs (no flag) behave identically. Diagnosis of the
  cause and any parser/prompt repair are a **separate, later, explicitly-approved** step.

**Parser accepts the positional-array shape (B2).** Diagnosis of the first real run showed Mistral
returns `"scores"` as a positional **array** (`[0.2, 0.1, ...]`), sometimes as quoted numbers, rather
than the required `{"opt_1": 0.2, ...}` object. `parse_scorer_json` now accepts EITHER a keyed object
OR a positional list of the **same length** — mapped in packet-option order to `opt_1..opt_N` — and
coerces quoted numbers to floats. It stays strict after normalization: every option present exactly
once, numeric/finite/in-range, `chosen` a valid option, and the contamination scan unchanged. This
reads only what the model already returned (never invents a score) and does **not** change the 8
labels, the label criteria, `A_vs_R`/`A_vs_X` co-primary status, the 0.15 abort threshold, packet
construction, or the frozen polarity. Arrays with the wrong length, non-numeric/opt-id values,
out-of-range/NaN scores, or `//`-comment / hybrid-syntax JSON are still rejected as malformed.

**Honest negative prior (record it, don't fish past it).** The varṇa polarity table was authored
from the frozen glosses **blind to the target poles**, so the derived A vectors mostly do **not**
match the pre-registered poles (e.g. *happy* derives toward contraction/fear/inertia). The expected
outcome is `RANDOM_POLARITY_EXPLAINS` / `CONTEXT_ONLY_EXPLAINS` / `NO_SIGNAL`. Report whatever comes
out once — do not retune the table to the answers (that would be `INVALID_POSTHOC_POLARITY` in
spirit) and do not reinterpret a null as a signal.

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
