# Step 1 qualification — RAW output (Qwen2.5-7B-Instruct)

**Objective:** qualify `bench_kv_format_quality.py` by reproducing the known production
INT4-protected result (holds quality at ~4% protection) on the discriminating model
(Qwen2.5-7B, where fp8 collapsed and int4-protected held).

## Provenance
- harness commit: `c26a5072` (production-config-matched: K per-channel affine over 32-token
  blocks + K-only protection; V per-32-channel group, no protection; per-head max-abs selector)
- model: `Qwen/Qwen2.5-7B-Instruct`
- corpus: wikitext-2-raw-v1 test, ctx=4096, PPL scored on tail 50% (teacher-forced NLL)
- date: 2026-07-18
- env: pod `/workspace/symbolu`, venv-vllm; torchaudio stubbed (cu124 vs torch cu121 mismatch,
  unused by this text-only bench — see `[env-fix]` banner in each run)
- exact command:
  ```bash
  for pf in 0.02 0.04 0.06 0.08; do
    echo "===== protect-frac=$pf ====="
    python CTM_plus/Bench/scripts/bench_kv_format_quality.py \
      --model Qwen/Qwen2.5-7B-Instruct --protect-frac $pf 2>&1
  done | tee /workspace/kvformat_qualify_qwen25.log
  ```

## Measured PPL (bf16 baseline = 5.1754, gate = within 1%)

| protect-frac | bf16 | fp8 | int4_protected | nvfp4 (plain) | nvfp4_protected |
|--:|--:|--:|--:|--:|--:|
| 2% | 5.1754 | 142.1014 | **5.1787 (+0.06%) HOLDS** | 3098.2488 | 13292.8652 (+256747%) |
| 4% | 5.1754 | 142.1014 | **5.1812 (+0.11%) HOLDS** | 3098.2488 | 135.0775 (+2510%) |
| 6% | 5.1754 | 142.1014 | 5.2378 (+1.21%) | 3098.2488 | 19.4090 (+275%) |
| 8% | 5.1754 | 142.1014 | 5.2441 (+1.33%) | 3098.2488 | 22.4032 (+333%) |

(fp8 and plain-nvfp4 are protect-frac-independent by construction — no protection — hence constant.)

## Verdict on the qualification gate

**QUALIFIED.** `int4_protected` reproduces the production result: at the production ~4% budget it
is bf16-identical (+0.11%), i.e. HOLDS. This closes the earlier harness defect (needed 16% where
production needs ~4%), whose root cause was quantizing K per-32-channel-group instead of per-channel
over 32-token blocks. With the per-channel K quantizer, protection is monotone-ish and holds at 4%.

## Two reproducible findings for Step 2/3 (NOT yet conclusions)

1. **NVFP4-protected @ 2% (13293) is ~4x WORSE than plain NVFP4 (3098).** Partial protection makes
   NVFP4 worse than no protection. Recovers as protection rises (2%→6%: 13293→19.4). Hypothesis:
   NVFP4's per-tensor global scale couples all 16-elem blocks; zeroing the top outliers drops a
   block's local amax while the global amax stays high (unprotected outliers remain) → that block's
   e4m3 scale underflows → block reconstructs ~0 → catastrophe. To be verified via saturation/clip-rate
   instrumentation + per-layer recon-error trace (Step 3). This is the anomaly the "chaotic noise"
   explanation was explicitly rejected for — it reproduces on the qualified harness, so it is a real
   integration-level property, not RNG.
2. **int4_protected is mildly non-monotone (4%→6%: +0.11%→+1.21%).** V is constant across the sweep,
   so this is purely a K-protection effect. Small (0.06 nats) but real; secondary Step-3 item.

## Preliminary strategic signal (hold until Steps 3–4 complete)

At matched budget on Qwen2.5, int4-protected massively out-holds NVFP4-protected (0.11% vs 2510% at
4%; 1.33% vs 333% even at 8%). This *suggests* the int4 format retains a large quality edge and the
protection mechanism does NOT transfer cleanly to NVFP4 as implemented — but the decisive test
(Step 4: freeze mask+budget, swap only the base quantizer) and the mechanism verification (Step 3)
must run before any TRANSFER_SUPPORTED / TRANSFER_NOT_SUPPORTED verdict.

## Raw console (verbatim)

```
===== protect-frac=0.02 =====
  [env-fix] torchaudio unusable (RuntimeError: Detected that PyTorch and TorchAudio were compiled with different CUDA versions. PyTorch has CUDA version 12.1 whereas TorchAudio has CUDA version 12.4. Please install the TorchAudio version that matches your PyTorch version.); stubbed it (unused by this bench) so the model can load.
KV-format quality — Qwen2.5-7B-Instruct ctx=4096 tail>=50% protect=2%  (NVFP4 EMULATED — quality only)
  bf16             PPL   5.1754
  fp8              PPL 142.1014
  int4_protected   PPL   5.1787
  nvfp4            PPL 3098.2488
  nvfp4_protected  PPL 13292.8652
-- verdict --
  bf16           PPL   5.1754  (baseline, gate = within 1%)
  fp8            PPL 142.1014  = +2645.71% vs bf16  [DEGRADED]
  int4_protected PPL   5.1787  =   +0.06% vs bf16  [HOLDS]
  nvfp4          PPL 3098.2488  = +59764.92% vs bf16  [DEGRADED]
  nvfp4_protected PPL 13292.8652  = +256747.11% vs bf16  [DEGRADED]

===== protect-frac=0.04 =====
KV-format quality — Qwen2.5-7B-Instruct ctx=4096 tail>=50% protect=4%  (NVFP4 EMULATED — quality only)
  bf16             PPL   5.1754
  fp8              PPL 142.1014
  int4_protected   PPL   5.1812
  nvfp4            PPL 3098.2488
  nvfp4_protected  PPL 135.0775
-- verdict --
  int4_protected PPL   5.1812  =   +0.11% vs bf16  [HOLDS]
  nvfp4_protected PPL 135.0775  = +2509.99% vs bf16  [DEGRADED]

===== protect-frac=0.06 =====
KV-format quality — Qwen2.5-7B-Instruct ctx=4096 tail>=50% protect=6%  (NVFP4 EMULATED — quality only)
  bf16             PPL   5.1754
  fp8              PPL 142.1014
  int4_protected   PPL   5.2378
  nvfp4            PPL 3098.2488
  nvfp4_protected  PPL  19.4090
-- verdict --
  int4_protected PPL   5.2378  =   +1.21% vs bf16  [DEGRADED]
  nvfp4_protected PPL  19.4090  = +275.02% vs bf16  [DEGRADED]

===== protect-frac=0.08 =====
KV-format quality — Qwen2.5-7B-Instruct ctx=4096 tail>=50% protect=8%  (NVFP4 EMULATED — quality only)
  bf16             PPL   5.1754
  fp8              PPL 142.1014
  int4_protected   PPL   5.2441
  nvfp4            PPL 3098.2488
  nvfp4_protected  PPL  22.4032
-- verdict --
  int4_protected PPL   5.2441  =   +1.33% vs bf16  [DEGRADED]
  nvfp4_protected PPL  22.4032  = +332.88% vs bf16  [DEGRADED]
```
