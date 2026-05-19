# Roadmap Exp 2 + Exp 4 — long-context + multi-model de-risking

Status: **no new code — existing flags.** Cheap quality-breadth runs on the
§20.4.3-validated config (protected-K 4%, static, V-INT4). Run while the
Exp-6 kernel work is being staffed.

Config under test (the §20.4.3 ship-shape config):
`--k-bits 4 --v-bits 4 --k-protect-fraction 0.04 --k-protect-static`.

Prerequisites: the pod already set up for the §20.4 runs (venv-hf, model
cache, branch at `555067bd` or later — both `--k-protect-fraction` and
`--k-protect-static` present). Same shell so `HF_HOME` / `TMPDIR` apply.

## Exp 2 — long context (does protected-K hold past 16k?)

The §20.4 sprint measured at 16 000 chars (~4–5k tokens). The value prop
is *long* context; the K-channel failure mechanism (softmax error
amplification, tighter key competition with more keys) could compound worse
at longer context. Test 32k / 64k chars (~9k / ~18k tokens).

```bash
cd /workspace/symbolu/CTM_plus/Bench
mkdir -p bench_out/exp2_longctx
python -m ctm_bench.scripts.track_e_long_context \
  --model Qwen/Qwen2.5-7B-Instruct --dtype float16 --device auto \
  --context-lengths 32000,64000 \
  --needle-depths 0.1,0.5,0.9 --needle-samples 8 --needle-decode-tokens 64 \
  --skip-perplexity \
  --k-bits 4 --v-bits 4 --k-protect-fraction 0.04 --k-protect-static \
  --output bench_out/exp2_longctx/protected_k_longctx.json
```

**GPU-memory note:** the harness runs an FP16 baseline alongside
protected-K. At 64 000 chars the FP16 KV cache is ~20 GB; with 14 GB
weights that fits a 40 GB A100 but is tight. **Only on an 80 GB GPU**,
append `,100000` to `--context-lengths` to push toward Qwen's 32 768-token
limit — on 40 GB it would OOM the baseline. The harness writes partial JSON
after every trial, so a crash loses nothing already measured.

Decision: protected-K within noise of the FP16 baseline at 32k/64k → the
long-context value prop holds. A drop that grows with context length → the
16k result does not generalize; retest at a higher protect fraction.

## Exp 4 — multi-model (does the outlier story replicate?)

Outlier channels are model-specific, but outlier *protection* should
generalize. If it doesn't replicate on Mistral, the claim is Qwen-specific.
Mistral-7B-v0.3 is already in the HF cache (used in §20.3); no download.

```bash
cd /workspace/symbolu/CTM_plus/Bench
mkdir -p bench_out/exp4_multimodel
python -m ctm_bench.scripts.track_e_long_context \
  --model mistralai/Mistral-7B-Instruct-v0.3 --dtype float16 --device auto \
  --context-lengths 16000 \
  --needle-depths 0.1,0.5,0.9 --needle-samples 8 --needle-decode-tokens 64 \
  --skip-perplexity \
  --k-bits 4 --v-bits 4 --k-protect-fraction 0.04 --k-protect-static \
  --output bench_out/exp4_multimodel/protected_k_mistral.json
```

Decision: protected-K within noise of the FP16 baseline on Mistral → the
outlier-protection approach generalizes. A material drop → it is
Qwen-specific and needs per-model tuning of the protect fraction.

## Reading the results

Each run prints a summary with an `int4 decode:` line. For the full table:

```bash
python - <<'PY'
import json, glob
for f in sorted(glob.glob('bench_out/exp*/*.json')):
    d = json.load(open(f))
    for k, b in d.get('deltas', {}).get('per_context_length', {}).items():
        print('%-34s' % f.split('/')[-1], k,
              'baseline=%3.0f%%' % ((b.get('baseline_needle_accuracy') or 0)*100),
              'protK=%3.0f%%' % ((b.get('int4_needle_accuracy') or 0)*100),
              'stutter=%s' % b.get('int4_first_stutter_earliest'))
PY
```

These are quality-breadth runs. They do **not** address throughput — that
is Experiment 6, the sole remaining gate.
