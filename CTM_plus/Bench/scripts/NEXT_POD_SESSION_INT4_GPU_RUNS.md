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

Still to run: task 3 mixed (groups=4), task 2 headroom verdicts, task 4
(optional); docs update (task 5) after 2+3.


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
