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
