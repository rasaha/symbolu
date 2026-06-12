# NEXT POD SESSION — int4_protected GPU runs (deploy verify + headroom + APC payoff)

## TASK 1 ✅ MEASURED 2026-06-12 (A100-SXM4-80G, util 0.85, mml 32768, --quick)

- DENSITY: bf16 399,792 slots -> int4 799,584 = **2.00x raw pool**;
  sidecars **8.3 GiB measured outside the pool** -> **~1.75x net** at equal
  total VRAM. (Historical 1.83x was at a smaller pool — the sidecar
  fraction scales with pool size, so net is util-dependent: quote 1.75x
  at max-util, not 1.83x, for this config.)
- QUALITY: needle RETRIEVED at ctx=16384 (also gates the cu128-toolchain
  rebuild: eager B=1 int4 read path coherent).
- APC (quick: N=8, gen=16, hit 88%): TTFT saved 62% @prefix=2000 ->
  **79% @4000** (grows with prefix ✓), tput **1.37x -> 1.78x**, quality
  1.00/1.00 both rows. As-shipped comparison (APC cell eager vs no-APC
  graphs) — the speedup is NET of the eager tax.
- Full report + artifacts: /tmp/savings_demo on the pod.

## TASK 3 (main sweep) ✅ MEASURED 2026-06-12 (N=16, groups=1, hit 94%, gen=32, util 0.60)

| prefix | TTFT miss | TTFT hit | saved | tput off | tput apc | speedup | quality |
|-------:|----------:|---------:|------:|---------:|---------:|--------:|---------|
|   1000 |  142.2 ms |  66.4 ms |  53%  |      109 |      130 |  1.19x  | 1.00/1.00 |
|   2000 |  215.2 ms |  94.5 ms |  56%  |       76 |       98 |  1.29x  | 1.00/1.00 |
|   4000 |  362.8 ms |  81.3 ms |  78%  |       48 |       78 |  1.64x  | 1.00/1.00 |
|   8000 |  704.5 ms |  98.3 ms |  86%  |       28 |       52 |  1.85x  | 1.00/1.00 |

Headline: APC saves up to **86% of TTFT per cache hit** (prefix=8000) and
**1.85x throughput** at 94% hit rate, quality clean (1.00 == no-APC) — net
of the eager tax (APC cell eager, no-APC cell graphs, as shipped).
Mechanism signature visible in the data: miss-TTFT linear in prefix,
hit-TTFT ~flat (~66-98 ms). 78%@4000 replicates the quick run's 79% at a
different gpu_util -> util change measurement-neutral, as claimed.

## TASK 3 (mixed, groups=4, hit 75%) ✅ MEASURED 2026-06-12

| prefix | TTFT miss -> hit | saved | tput off -> apc | speedup | quality |
|-------:|-----------------:|------:|----------------:|--------:|---------|
|   2000 | 215.7 -> 88.5 ms |  59%  |      76 -> 97   |  1.28x  | 1.00/1.00 |
|   4000 | 359.0 -> 72.6 ms |  80%  |      49 -> 75   |  1.54x  | 1.00/1.00 |

Miss-TTFT matches the groups=1 sweep at both prefixes (same prefill cost,
independent run) — internal consistency check passed.

## TASK 2 (gather-fusion headroom, B=1, gen=64) ✅ MEASURED 2026-06-12

- ctx=8000:  FUSEABLE **59.9%** (gather 469ms + splice 484ms + prep 112ms +
  backing 39ms) vs KERNEL 40.1% (739ms) -> **GO**. Splice as costly as the
  gather at this regime — 6F must absorb both. All regions GPU-bound
  (cpu/gpu 0.2-1.0x) -> CUDA fusion, not python vectorization.
- ctx=32000: FUSEABLE **42.0%** (gather alone 35.6% = 1.31s) vs KERNEL
  58.0% (2.14s) -> **GO**, narrowing: kernel grows faster than gather.
  Small regions flip CPU-bound at 32K (kernel_prep 8.8x, splice 2.6x) but
  are only ~230ms combined — secondary vectorization targets.
- ctx=16000: pending paste (interpolates; verdict unchanged unless surprise).

RECOMMENDATION: **BUILD 6F** (in-kernel paged gather + K-tail splice).
Measured headroom 60%@8K -> 42%@32K, GO at both ends (threshold 35%);
biggest relative win at short-mid context; realized < headroom; decode
ceiling ~0.27-0.30x unchanged until built.

## TASK 4 (read-skip crossover >32K) ✅ MEASURED 2026-06-12 — ANSWER: NO CROSSOVER

| ctx   | bf16 tps | int4 tps (/bf16) | rs tps (/bf16) | skip% | quality bf/int4/rs |
|------:|---------:|-----------------:|---------------:|------:|--------------------|
| 32000 |    66.19 |    14.91 (0.23x) |  16.14 (0.24x) |  77.1 | 1.00/1.00/1.00 |
| 44000 |    62.72 |    11.96 (0.19x) |  14.39 (0.23x) |  83.3 | 1.00/1.00/1.00 |
| 52000 |    60.13 |    10.85 (0.18x) |  13.71 (0.23x) |  85.6 | 1.00/1.00/1.00 |
| 60000 |    57.74 |     9.65 (0.17x) |  13.10 (0.23x) |  87.7 | 1.00/1.00/1.00 |
| 80000 |    53.40 |     7.51 (0.14x) |  11.45 (0.21x) |  90.6 | 1.00/1.00/1.00 |
| 100000 |   49.26 |     6.28 (0.13x) |  10.34 (0.21x) |  93.3 | 1.00/1.00/1.00 |

EXTENDED 2026-06-12 to 80K/100K (seeds 1,2,3 x depths 0.1/0.5, repeats 2):
**QUALITY CEILING RAISED 60K -> 100K** — needle 1.00 for bf16/int4/rs at
both lengths, including retention at **93.3% skip** (retained ~6,280 of
~93,675: the bounded-set mechanism measured end-to-end; relative win
grows +8%@32K -> +65%@100K). Still NO bf16 crossover; quant-alone floor
slides 0.17 -> **0.13x @100K** -> cost range re-widened to 0.13-0.67x in
brief/DESIGN/demo/QUICKSTART (second self-correction). rs holds ~0.21x
flat at 80-100K. The 100K-document (prefill/SSD-tier) claims are now
GATED, not extrapolated.

(B=1, gen=128, eager; bf16 cells at util 0.85, AB cells at 0.55 — B=1
decode tok/s is pool-independent.) NO bf16 crossover up to 60K: rs flat
~0.23x while quant-alone slopes 0.23->0.17x; read-skip claws back
+8%->+36% over quant-alone as skip grows 77->88%, quality 1.00 everywhere
(notable at 87.7% skip). The parity thesis is unsupported at these
lengths — story stays density + quality + APC. NOTE: 0.17x is BELOW the
previously disclosed 0.22x floor -> cost range updated to 0.17-0.67x in
brief/DESIGN/demo/QUICKSTART. The relative read-skip delta is
keep-set-dependent (prior ~95%-skip config measured +25->+72%).

Docs (task 5) DONE for density + APC + headroom + crossover (brief, DESIGN
§6, demo, QUICKSTART all carry measured numbers; page-1 stale ~50K
extrapolation replaced with the measured answer).


Status: every script below is **CPU-validated only** (selftests ALL PASS, dry-runs
emit correct per-cell commands, the savings-report renderer verified against
fixture JSONs on 2026-06-12 — cross-file JSON contracts checked field-by-field).
**No GPU numbers exist yet.** Do NOT update the docs until these runs produce them.

## Preamble (every run)

```bash
source /workspace/venv-vllm/bin/activate 2>/dev/null || true   # fresh pods may have NO venv —
# that's fine: system python works IF the import check below passes (seen 2026-06:
# pod b628c63c system python3.12 already carried vllm==0.7.3 + torch==2.5.1+cu121).
M=NousResearch/Meta-Llama-3.1-8B-Instruct
export PROTECT_MASK_PATH=/workspace/dev/build-logs/meta_llama_3_1_8b_instruct_protect_mask_4pct.pt
pkill -9 -f vllm; sleep 2          # clear orphans
python -c "import vllm; from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache; print('ok', vllm.__version__)"
# if that import fails:
#   export TORCH_CUDA_ARCH_LIST=8.0   # A100; 9.0 for H100
#   bash CTM_plus/Bench/scripts/rebuild_all_kernels.sh --clean --verify-source
# Build notes (learned 2026-06 on a 256-vCPU A100 pod):
#   * the script now auto-sizes MAX_JOBS from MemAvailable (~6GB/nvcc-job,
#     clamp [4,32], <=nproc) — the old nproc default (-j=256) OOMed the build.
#     Pin explicitly on shared/RAM-tight pods: MAX_JOBS=8 bash ... --clean
#   * before retrying a failed build, check whether it WAS an OOM:
#     dmesg -T | grep -iE 'out of memory|oom-kill|killed process' | tail
#     (no OOM lines => real compile error => read the full log instead)
#   * do NOT run training jobs on the box during the build (they fight for RAM
#     and the OOM killer shoots the biggest process).
#   * full build logs: /workspace/dev/build-logs/fa_wheel_build_*.log /
#     int4C_build_*.log — read those on failure, the console only tails.
```

## TASK 6K.18 (chunked prefill) — BUILT 2026-06-12, ⛔ NOT GATED — RUN THIS FIRST

Code is on the branch (D1 tail splice, D2 rid contract, D3 factory
opt-in; CPU suites green incl. the storage byte-gate across chunk
boundaries). **NO pod numbers exist. The factory default stays False and
the init warning stays until every gate below is green.** Design + gate
contract: PHASE6K18_CHUNKED_PREFILL_DESIGN.md. Order is binding:
P2 first (the STOP rule), then G1->G6; G2 red = build wrong, full stop.

Pod realities that bite here: preamble + import check as below;
PROTECT_MASK_PATH per-model (recalibrate if absent — cheap,
deterministic); 6k12 needs --model AND --protect-mask; sidecars live
OUTSIDE gpu_memory_utilization (the chunked prize is about the
ACTIVATION spike, so judge cells by nvml peak + did-it-OOM, not by the
paged-pool number); chunked cells are eager-forced by the factory.

```bash
# 0) preamble ($M, PROTECT_MASK_PATH, import check) — see Preamble below.
M=NousResearch/Meta-Llama-3.1-8B-Instruct
G=CTM_plus/Bench/scripts/phase6k18_chunked_gates.py

# P1 — gap trace (~10 min). As SCOPED it documents the OLD failure: run
#   it from main (pre-merge) and capture the ctx%32-rail / arming-check
#   stack trace. On THIS branch the same probe must instead die at the
#   C-ID stash refusal (raw bypass has no hook -> identity unprovable):
#   both traces together document gap -> guard. Raw-bypass repro:
INT4_PROTECTED_ALLOW_CHUNKED_PREFILL=1 python - <<'EOF'
import os, kv_policy.int4_protected  # registers backend
from vllm import LLM, SamplingParams
llm = LLM(model=os.environ["M"], kv_cache_dtype="int4_protected",
          block_size=32, max_model_len=8192, enforce_eager=True,
          enable_chunked_prefill=True, max_num_batched_tokens=472,
          gpu_memory_utilization=0.5)
llm.generate(["word " * 1500], SamplingParams(max_tokens=2))  # expect loud refusal, stack trace = P1 evidence
EOF

# P2 — PRIZE BOUND on STOCK bf16 (~20 min). 44K and 100K, chunked
#   on/off, util 0.85. THE STOP RULE: if the 100K chunked-on cell cannot
#   run at util 0.85 (OOM) or shows no peak-memory headroom vs off,
#   the prize is smaller than claimed -> re-scope the story before G4.
python $G --probe p2 --chunked off --p2-tokens 44000  --gpu-util 0.85 --model $M --out /tmp/p2_44k_off.json   # expect: OOM or huge spike (the banked 76.3 GiB shape)
python $G --probe p2 --chunked on  --p2-tokens 44000  --gpu-util 0.85 --model $M --out /tmp/p2_44k_on.json
python $G --probe p2 --chunked off --p2-tokens 100000 --gpu-util 0.85 --model $M --out /tmp/p2_100k_off.json
python $G --probe p2 --chunked on  --p2-tokens 100000 --gpu-util 0.85 --model $M --out /tmp/p2_100k_on.json
# record: nvml_peak_used_gib, prefill_wall_s, ttft_s, short_ttfts_s, ran-at-all.

# G1 — selftests + guard tests (every suite, incl. the new 6K.18 one):
python CTM_plus/KVPolicy/kv_policy/phase6k16_prefix_prefill.py          # incl. tail-splice §6
python CTM_plus/KVPolicy/tests/test_phase6k18_chunked_prefill.py
python CTM_plus/KVPolicy/tests/test_phase6n_prot_int8.py
for t in CTM_plus/KVPolicy/tests/test_*.py; do python $t || break; done
python $G --selftest

# G2 — S1-chunked byte-gate (THE machinery gate; red = full stop).
#   Aligns dump events BY BLOCK ID (chunked finalize order differs).
python $G --mode mono    --dump /tmp/s1_mono.pt    --model $M
python $G --mode chunked --dump /tmp/s1_chunked.pt --model $M
python $G --compare /tmp/s1_mono.pt /tmp/s1_chunked.pt

# G3 — greedy chunked vs monolithic (6 prompts + one >2-chunk prompt).
#   EXPECT near-bar, NOT bit-exact (context-quant residual: chunk k sees
#   QUANTIZED full blocks where monolithic saw exact bf16). Divergences
#   must be coherent near-ties; any degenerate text = machinery FAIL.
python $G --greedy mono    --out /tmp/g3_mono.json    --model $M
python $G --greedy chunked --out /tmp/g3_chunked.json --model $M
python $G --compare-greedy /tmp/g3_mono.json /tmp/g3_chunked.json

# G4 — needle 32K + 100K WITH chunking at util 0.85 (THE prize cell).
#   Baseline = the unchunked util-0.55 numbers. Record retrieval + peak
#   memory + TTFT. (6k12 trap: --model AND --protect-mask, always.)
NEEDLE_CHUNKED=1 NEEDLE_GPU_UTIL=0.85 NEEDLE_MAX_BATCHED=2048 \
  python CTM_plus/Bench/scripts/phase6k12_hard_needle.py \
  --mml 32768 --items 4 --cells bf16,protected --model $M --protect-mask $PROTECT_MASK_PATH
NEEDLE_CHUNKED=1 NEEDLE_GPU_UTIL=0.85 NEEDLE_MAX_BATCHED=2048 \
  python CTM_plus/Bench/scripts/phase6k12_hard_needle.py \
  --mml 102400 --items 2 --cells protected --model $M --protect-mask $PROTECT_MASK_PATH
# unchunked util-0.55 baseline (only if not already banked this pod):
NEEDLE_GPU_UTIL=0.55 python CTM_plus/Bench/scripts/phase6k12_hard_needle.py \
  --mml 32768 --items 4 --cells protected --model $M --protect-mask $PROTECT_MASK_PATH

# G5 — mixed-batch TTFT on the int4 engine (decode stall), chunked A/B:
python $G --probe p2 --engine int4 --chunked off --p2-tokens 32000 --gpu-util 0.55 --model $M --out /tmp/g5_off.json
python $G --probe p2 --engine int4 --chunked on  --p2-tokens 32000 --gpu-util 0.55 --model $M --out /tmp/g5_on.json
# compare short_ttfts_s: chunked-on shorts must not stall behind the long prefill.

# G6 — interaction cells (D4 decision happens HERE, by measurement):
#   (a) APC+chunked: pass => supported combo; fail => wire the loud
#       refusal for the combination (factory) and ship chunked w/o APC.
python $G --mode chunked --apc --dump /tmp/s1_apc_chunked.pt --model $M
python $G --compare /tmp/s1_mono.pt /tmp/s1_apc_chunked.pt
python $G --greedy chunked --apc --out /tmp/g6_apc.json --model $M
python $G --compare-greedy /tmp/g3_mono.json /tmp/g6_apc.json
NEEDLE_APC=1 NEEDLE_CHUNKED=1 python CTM_plus/Bench/scripts/phase6k12_hard_needle.py \
  --mml 8192 --items 4 --cells protected --model $M --protect-mask $PROTECT_MASK_PATH
#   (b) prot-int8 (6N) + chunked (set the flag in BOTH compared cells):
INT4_PROTECTED_PROT_INT8=1 python $G --mode mono    --dump /tmp/s1_mono8.pt    --model $M
INT4_PROTECTED_PROT_INT8=1 python $G --mode chunked --dump /tmp/s1_chunked8.pt --model $M
python $G --compare /tmp/s1_mono8.pt /tmp/s1_chunked8.pt

# AFTER all green (and only then, with the measured numbers):
#  - design doc status -> GATED + checklist results (P2/G4 peak-mem +
#    util numbers are the headline; G5 TTFT secondary),
#  - downgrade the factory's POD-GATES-PENDING warning to logger.info,
#  - this ledger entry -> ✅ with the numbers,
#  - deploy/INT4_PROTECTED_DESIGN.md + VC-brief long-context paragraphs.
# If ANY gate is red: fix or revert — never ship red; a win on corrupted
# output never counts.
```

## TASK 6N ✅ ALL GATES GREEN 2026-06-12 (A100-SXM4-80G, same pod)

Phase 6N (asym-static int8 protected channels) behind
`INT4_PROTECTED_PROT_INT8` (default REMAINS OFF — rollout decision
separate from the banked measurement). MEASURED RESULTS, gates in order:

1. Recalibration reproduced the deployed mask BYTE-IDENTICALLY (two
   independent runs: pre-sync v1 script and v2 script) + emitted
   k_min/k_max (margin 1.1; artifact 35,733 B -> ~167 KB).
2. All selftests/guard tests/capture-safety GREEN on pod.
3. Savings probe A/B (util 0.85, mml 32768, 24,987 blocks): needle
   RETRIEVED both cells; sidecar_bytes 8,867,932,672 -> 7,844,475,392
   = **-0.953 GiB**, matching 1280 B/block x 24,987 x 32 layers minus
   the 10,240 B of dequant constants TO THE BYTE.
4. Greedy A/B: **6/6 BIT-IDENTICAL** ON vs OFF (driver activation guard:
   32/32 layers ON-cell, 0/32 OFF-cell).
5. S1 APC byte-gate 13/13 byte-exact, both engines confirmed under
   `prot_int8_asym_static` markers; 6k12 hard needle: protected ==
   bf16 bucket-for-bucket (strict 0.875 / retrieval 0.955, 0 ERROR) in
   BOTH flag states. Two invalid 6k12 runs first — driver needs
   --model AND --protect-mask (it POPS $PROTECT_MASK_PATH); without
   them int4 cells ERROR 24/24 on the legacy Qwen artifact paths.
6. Demo flag-ON: density line **~1.78x net** (sidecars 7.3 GiB vs 8.3
   flag-off at the same pool); APC rows quality 1.00/1.00, TTFT -79%
   @4000 / 1.81x — in family with the flag-off sweeps.

Docs updated post-gates: PHASE6N_PROT_INT8_DESIGN.md (status GATED +
checklist results), deploy/INT4_PROTECTED_DESIGN.md §6 (density row +
customer statement carry 1.78x-with-flag). Reproduction commands below.

SCHEDULING-PARAMS SWEEP MEASURED 2026-06-12 (decision: polish, not a
lever — do not re-litigate without new evidence): int4 backend, eager,
util 0.60, mml 4096, 32x ~500-tok prompts gen=64 + B=1 gen=128 control.
B=1 decode FLAT across max_num_seqs 4/16/64 (12.85/13.05/12.50 tok/s,
+/-2% = noise: the scheduler cannot move the kernel-bound path). Agg
throughput 40.7 -> 113.2 -> 165.7 tok/s, scaling efficiency FALLING
(2.8x for 4x seqs, then ~73% of the remaining 2x) — saturating toward
the kernel ceiling (= 6F territory). max_num_batched_tokens < mml is
REFUSED by vLLM V0 without chunked prefill (verified verbatim) — the
one TTFT-shaping scheduler knob is locked behind 6K.18. Cross-check:
B=1 ~12.5-13 vs bf16 ~35 tok/s same pod/short ctx = 0.36x, inside the
disclosed 0.13-0.67x range.

```bash
# 0) preamble as above ($M, PROTECT_MASK_PATH, import check).

# 1) Recalibrate -> v2 artifact (adds per-channel k_min/k_max; mask math
#    unchanged). Back up the deployed artifact first and CHECK the mask
#    itself is unchanged — if it isn't, STOP (corpus/model drift would
#    confound every A/B below):
cp $PROTECT_MASK_PATH ${PROTECT_MASK_PATH}.pre6n
python CTM_plus/Bench/scripts/calibrate_phase5b_protect_mask.py \
  --model $M --output $PROTECT_MASK_PATH
python - <<'EOF'
import os, torch
new = torch.load(os.environ["PROTECT_MASK_PATH"], weights_only=False)
old = torch.load(os.environ["PROTECT_MASK_PATH"] + ".pre6n", weights_only=False)
assert torch.equal(new["mask"], old["mask"]), "MASK CHANGED — stop, investigate"
assert "k_min" in new and "k_max" in new, "v2 keys missing"
print("mask unchanged; v2 minmax present; margin", new.get("minmax_margin"))
EOF

# 2) Selftests + guard tests (incl. the new 6N suite):
python CTM_plus/KVPolicy/tests/test_phase6n_prot_int8.py
for t in CTM_plus/KVPolicy/tests/test_*.py; do python $t || break; done
python CTM_plus/KVPolicy/kv_policy/phase6k16_prefix_prefill.py
python CTM_plus/Bench/scripts/phase6k16_byte_gate.py --selftest
(cd CTM_plus/Bench && PYTHONPATH=../KVPolicy python scripts/verify_phase6_b_pre5_write_path_capture_safe.py)

# 3) Savings probe A/B at mml 32768 (needle RETRIEVED in BOTH cells;
#    sidecar_bytes drops ~1 GiB flag-on; PASTE BOTH JSONs):
python deploy/_savings_probe.py --backend int4 --model $M --mml 32768 --needle --out /tmp/p6n_cap_off.json
INT4_PROTECTED_PROT_INT8=1 python deploy/_savings_probe.py --backend int4 --model $M --mml 32768 --needle --out /tmp/p6n_cap_on.json

# 4) 6-prompt greedy bitexact, flag ON vs OFF (driver verifies prot-int8
#    actually activated on ALL layers — a bf16 fallback cell refuses):
python CTM_plus/Bench/scripts/phase6n_prot_int8_gate.py --cell off --model $M --out /tmp/p6n_off.json
python CTM_plus/Bench/scripts/phase6n_prot_int8_gate.py --cell on  --model $M --out /tmp/p6n_on.json
python CTM_plus/Bench/scripts/phase6n_prot_int8_gate.py --compare /tmp/p6n_off.json /tmp/p6n_on.json

# 5) APC S1 byte-gate with the flag ON in BOTH engines (dumps carry a
#    k_protect format marker; mixed-format dumps refuse loudly), then the
#    6k12 hard-needle cell, flag OFF then ON. 6k12 GOTCHA (hit live
#    2026-06-12, twice): the worker POPS $PROTECT_MASK_PATH and honors
#    only --protect-mask/--naive-mask (legacy Qwen defaults otherwise —
#    Llama cells ERROR 24/24 on mask-shape at _lazy_alloc); pass
#    --cells bf16,protected unless a Llama naive mask exists:
INT4_PROTECTED_PROT_INT8=1 python CTM_plus/Bench/scripts/phase6k16_byte_gate.py --mode noapc --dump /tmp/s1_noapc.pt --model $M
INT4_PROTECTED_PROT_INT8=1 python CTM_plus/Bench/scripts/phase6k16_byte_gate.py --mode apc   --dump /tmp/s1_apc.pt   --model $M
python CTM_plus/Bench/scripts/phase6k16_byte_gate.py --compare /tmp/s1_noapc.pt /tmp/s1_apc.pt
python CTM_plus/Bench/scripts/phase6k12_hard_needle.py --model $M \
  --protect-mask $PROTECT_MASK_PATH --cells bf16,protected --mml 8192 2>&1 | tee /tmp/p6n_6k12_off.log
INT4_PROTECTED_PROT_INT8=1 python CTM_plus/Bench/scripts/phase6k12_hard_needle.py --model $M \
  --protect-mask $PROTECT_MASK_PATH --cells bf16,protected --mml 8192 2>&1 | tee /tmp/p6n_6k12_on.log

# 6) Demo with the flag ON — density line should read ~1.78x net:
INT4_PROTECTED_PROT_INT8=1 bash deploy/customer_savings_demo.sh --model $M --quick
```

ONLY after 1-6 are green: update PHASE6N_PROT_INT8_DESIGN.md status, the
ledger, and DESIGN §6's density row (1.75x -> measured ~1.78x). If any
gate fails: fix or revert — the flag ships default-OFF either way.

## 1) Deploy package end-to-end

```bash
bash deploy/customer_savings_demo.sh --model $M --quick
```

Accept: SAVINGS REPORT renders with a LIVE density ratio (expect ~2x raw /
~1.83x net), needle RETRIEVED, an APC saving line. Any error in
`deploy/_savings_probe.py` / the demo on the real pod: fix it, re-run, commit.
Paste the report verbatim into the session log.

## 2) Gather-fusion headroom (build/skip the "6F" in-kernel paged gather)

```bash
python CTM_plus/Bench/scripts/bench_decode_gather_fusion_headroom.py --model $M --context-tokens 32000 --gen 64 --batch 1
for C in 8000 16000 32000; do python CTM_plus/Bench/scripts/bench_decode_gather_fusion_headroom.py --model $M --context-tokens $C --gen 64 --batch 1; done
```

Read the VERDICT line: GO (>=35% headroom), MAYBE (15-35%), NO-GO (<15%).
If cpu/gpu ratio on `view_gather` is >>1, the fix is Python vectorization,
not CUDA fusion. Deliverable: headroom block per context + one-line
build/skip recommendation.

## 3) APC payoff (replace the mechanism claim with a measured number)

```bash
python CTM_plus/Bench/scripts/apc_payoff_sweep.py --model $M --prefixes 1000,2000,4000,8000 --num-requests 16 --num-groups 1 --gen 32 --out-dir /tmp/apc
python CTM_plus/Bench/scripts/apc_payoff_sweep.py --model $M --prefixes 2000,4000 --num-requests 16 --num-groups 4 --gen 32 --out-dir /tmp/apc_mixed
```

Accept: TTFT saved% GROWS with prefix length; quality apc == off (bit-exact
expected). Note when reading throughput: the APC cell runs **eager** (factory
forces it — APC is eager-only) while the no-APC cell runs with graphs, so
`tput_speedup` is the **as-shipped** net (APC benefit minus eager tax) — honest,
but say so when quoting it.

## 4) (optional) Read-skip crossover >32K

```bash
python CTM_plus/Bench/scripts/phase10_crossover_sweep.py --model $M --contexts 32000,44000,52000,60000 --gen 128 --plot --out-dir /tmp/x10
```

Trust a crossover ONLY where read-skip quality == bf16 (the driver gates this).
If no crossover: say so and bound the story — density/niche framing, not parity.

## 5) Doc updates (ONLY with the measured numbers from 1-3)

- `INT4_PROTECTED_VC_BRIEF.md`: replace the APC "mechanism" wording with the
  measured TTFT/throughput saving — the "first lever that reduces the throughput
  tax" paragraphs (slot-pool/APC row of the limits table, and §4
  "APC-compatible by construction" payoff bullet); add the gather-headroom
  verdict next to the kernel-bound discussion.
- `deploy/INT4_PROTECTED_DESIGN.md` §6 "The savings model (honest)": same.
- Keep the framing: density + quality + APC prefill saving; decode cost
  disclosed (0.22-0.67x, ceiling ~0.27-0.30x). Quality-gate every number.

## Pre-flight already done (don't redo)

- All four `--selftest`s pass on CPU; both sweep drivers' `--dry-run` paths OK.
- JSON contracts verified by reading both sides: demo report <-> probe JSONs
  (`total_token_slots`, `quality.retrieved`) and <-> `apc_payoff_summary.json`
  (list of rows: `quality_ok`, `ttft_saving_pct`, `prefix_tokens`,
  `tput_speedup`, `hit_rate`); crossover driver <-> `phase9_p3_fused_needle.py`
  (`--bf16-ref` exists; `tps_mean`, `per_mode.{off,retention}`,
  `skip_diag.steady_skip_frac` all emitted).
- Profiler contract verified: `DecodeProfiler` + `_DECODE_PROFILER` global +
  regions `{batched,one}.{seqids_blockids,view_gather,splice,bf16_backing,kernel_prep,kernel}`
  all present in `phase5b_backend_install.py`; `reset_sequence("all")` supported.
- Demo hardened: `python`->`python3` fallback; the no-data NET line now says
  "density NOT measured this run" instead of quoting ~2x as if live.
- GPU memory accounting gotcha (hit live 2026-06-12, A100-80G, util 0.85):
  the int4 sidecars (~16-20% of pool bytes) AND the per-slot staging that
  CUDA-graph capture inflates to max_num_seqs (V0 default 256 -> ~6 GiB)
  live OUTSIDE gpu_memory_utilization -> engine init OOMs at high util.
  Fixes shipped: savings probe runs EAGER with max_num_seqs=16 (B=1 probe;
  pool size/density unaffected) and now MEASURES the sidecar bytes -> the
  report prints raw pool ratio AND net-of-sidecars at equal total VRAM;
  apc_payoff_sweep caps max_num_seqs at the batch size (noapc cell keeps
  graphs, as shipped). First live numbers: bf16 399,792 slots vs int4
  24,987x32 = 799,584 -> 2.00x raw pool (vLLM's own log: max concurrency
  12.20x vs 24.40x).
- bench_decode_gather_fusion_headroom now forces enforce_eager=True — under
  graph replay the python read path (where the profiler regions live) never
  executes per step, so a graphs run would record nothing. The headroom it
  measures is the EAGER read path (the path the fusion would fix).
- Phase 6K.17 (hit live on the 32K headroom cell): vLLM V0 AUTO-ENABLES
  chunked prefill at max_model_len > 32768; chunk 2+ arrives as a
  prefill-with-context and the backend refuses it on the prefix-aware
  branch. The factory now pins enable_chunked_prefill=False explicitly
  (True refused; INT4_PROTECTED_ALLOW_CHUNKED_PREFILL=1 dev override) —
  guard-tested in tests/test_phase6k17_chunked_guard.py. phase9's
  _engine_kwargs pins False too (bf16 ref + route-A comparability at >32K).
- Second OOM shape (hit live, noapc p2000 cell): SMALL mml -> vLLM profiles
  tiny activations -> BIGGER pool (51.5 GiB at mml=6096) -> bigger sidecars
  (~16% of pool) -> graphs capture allocates them all ("capture took 11.82
  GiB") -> 79.06/79.14 used -> first prefill OOMs. Fix: apc_payoff_sweep
  default --gpu-util 0.60 (sweep needs ~2 GiB of cache; TTFT/tput are
  pool-independent), headroom bench default 0.70, demo no longer forwards
  its density-util into the APC stage. High util remains ONLY where it is
  the point (the density probe).
- Task 4 note: crossover driver default --gpu-util now 0.55 (route-A's own
  int4 store + eager 44K-prefill activations live outside the vLLM budget;
  at 0.85 the ab_ctx44000 cell hit 76.3 GiB committed pre-prefill -> OOM).
  bf16 cells measured at 0.85 stay valid (B=1 decode tok/s is
  pool-independent); resume with --reuse on the same out-dir.
- bf16 graphs-vs-eager MEASURED (32K B=1, two-pass): eager 66.6 vs graphs
  67.2 tok/s -> +0.9%, NEUTRAL. Validates the crossover's eager bf16
  baseline (no handicap asterisk needed on the 0.23x ratio) and kills
  graphs/multi-step as B=1 long-ctx bf16 levers — the remaining real
  levers are speculative decoding, TP, or hardware.
- bench_8bit_kv_gate.py added: 3-cell (~12 min) gate for the "8-bit KV is
  the better fast tier" claim ON OUR STACK — runtime-introspects what
  kv dtypes this vLLM actually accepts (int8 expected ABSENT), measures
  density/needles/6-prompt bit-exactness/decode tok/s for fp8_e4m3
  (+calculated scales if supported) and fp8_e5m2 vs bf16. LMDeploy/TRT
  int8 explicitly out of scope.
- 8-BIT KV GATE MEASURED 2026-06-12 (bench_8bit_kv_gate.py, graphs ON,
  B=1, mml 36096, util 0.55): vLLM 0.7.3 accepts auto/fp8/fp8_e4m3/
  fp8_e5m2 — NO int8 (verified from CacheConfig source);
  calculate_kv_scales supported. bf16 202,480 slots / 66.9 tok/s.
  fp8_e4m3+calc-scales: 2.00x slots, needles 3/3+5/5, greedy 2/6
  identical / 84% overlap, 21.9 tok/s = 0.33x. fp8_e5m2: 2.00x slots,
  needles pass, greedy 1/6 / 41% (FAIL), 50.8 tok/s = 0.76x.
  CONCLUSIONS: (a) the fp8 needle catastrophe (Qwen 1/15) is
  MODEL-DEPENDENT — brief updated to rest the quality wedge on greedy
  divergence + hard gates, not needles-always-fail; (b) NO fast 8-bit
  tier exists on vLLM 0.7.3 — both fp8 variants slower than bf16;
  (c) fp8-e4m3 = max-density option (2.00x, no sidecars) at 0.33x with
  lite-grade quality; KVPro keeps hard-gated quality + APC-measured.
  Escalation if ever needed: run 6k12 hard-needle on fp8_e4m3.
- probe_block_quant_error.py added (dynamic-protect decision data): stock
  bf16 engine + per-layer hooks capture post-RoPE K/V/q on a mixed corpus;
  replays the EXACT validated quantizer (int4_per_channel_kv, group=32,
  asym, bits=4) under policies {noprot, cur_bf16-protect, protect@int8,
  fresh-mask 1-8% sweep, sensitivity-mask@4%}; per-block max-err CDF ->
  %blocks tagged + int8-fallback GiB/100K-session at each threshold;
  score-space SNR per layer (|q.dk| vs std(q.K), GQA-mapped). Artifacts:
  summary.json + blocks.npz + channels.npz — sized so NO re-runs are
  needed for later threshold/mask questions. Selftest needs torch (pod).
- QUANT-ERROR PROBE MEASURED 2026-06-12 (26,629 tokens x 32 layers, real
  activations, exact validated quantizer): mean|err| noprot 0.0611,
  cur(4% bf16-protect) 0.0578 (94.7%), protect@int8 0.0580 (95.0%).
  VERDICTS: (1) int8-protect adds only 0.3pp vs bf16-protect -> the ~1 GB
  sidecar saving is mathematically nearly free; graduate to gates.
  (2) dynamic-protect: WEAK — block max-err tail is mild (p50 0.283,
  p99 0.450 = 1.6x median; tagging worst 1% costs 15 MB/100K but no
  catastrophic-block population exists to catch). Don't build on this
  evidence. (3) REFRAME: the 4% mask removes only 5.3% of mean
  element error (1.3x its share) — with per-channel-per-block scales
  there is no cross-channel contamination, so protect's value must be
  score-space (|k_d| x |q_d| weighting), not element-space; the per-layer
  score SNR + sensitivity-mask overlap live in /tmp/qerr/summary.json
  (offline analysis; no GPU rerun needed by design).
- SCORE-NOISE ATTRIBUTION (offline from channels.npz): deployed 4% mask
  carries 11.2% of score-noise weight (5.8-15.0% by layer) = 2.8x its
  budget share; sensitivity-ranked ceiling at same budget = 16.0%.
  READ: protect is a real but SECONDARY contributor — ~89% of the
  measured near-bf16 quality is carried by block-local per-channel int4
  itself; protect's clearest job is tail-trimming (block p99 -24%).
  DECISIONS: (a) mask re-ranking SHELVED — +4.8pp score-noise removal is
  below gate sensitivity on a model already at needle 1.0; it becomes
  the FIRST lever for models that fail gates (Mistral keep-set depth-0.5,
  Qwen-1M rope). (b) rotation-v2 thesis STRENGTHENED: deleting all
  protect machinery (sidecar + splice, ~half the fuseable decode
  overhead) risks only ~11% score-noise increase — pending its own
  end-to-end gates. (c) int8-protect even safer (demotes an 11%-share
  population from exact to ~16x-finer-than-int4). OPTIONAL closer: a
  no-protect end-to-end ablation (needle 32-60K + 6-prompt greedy,
  ~10 min) would convert the 89% proxy into a measured claim.
- PROT-INT8 (Phase 6N): NOT integrated — probe evidence only; shipping
  path still stores protect at bf16. Design doc: PHASE6N_PROT_INT8_DESIGN.md
  (touch points, static-vs-dynamic scale decision, byte-gate contract note,
  gate checklist). Probe gained 'prot_int8_static' policy: rerun probe
  (~5 min) — if static ~= dynamic int8, Variant A (no streaming changes,
  1-2 days + gates) proceeds; build belongs in a pod session, flag
  INT4_PROTECTED_PROT_INT8 default OFF until gated.
- PHASE 6N VARIANT LOCKED (3rd probe run): asym-static int8 protect =
  95.9% of no-protect (82% of protect benefit retained) vs dynamic 95.3%
  (94%) vs deployed bf16 95.0%. Variant A (asymmetric static min/max
  scales, ~10 KB constants, zero streaming changes) WINS — the residual
  gap is ~1.3% of total score noise (below gate resolution), and Variant
  B is strictly worse on memory (per-block scale sidecars) while adding
  hot-path code. Design doc finalized: PHASE6N_PROT_INT8_DESIGN.md.
  Build = 1-2 days + gates in a pod session; flag default OFF.
