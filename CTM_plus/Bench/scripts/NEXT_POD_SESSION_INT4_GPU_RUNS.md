# NEXT POD SESSION — int4_protected GPU runs (deploy verify + headroom + APC payoff)

Status: every script below is **CPU-validated only** (selftests ALL PASS, dry-runs
emit correct per-cell commands, the savings-report renderer verified against
fixture JSONs on 2026-06-12 — cross-file JSON contracts checked field-by-field).
**No GPU numbers exist yet.** Do NOT update the docs until these runs produce them.

## Preamble (every run)

```bash
source /workspace/venv-vllm/bin/activate
M=NousResearch/Meta-Llama-3.1-8B-Instruct
export PROTECT_MASK_PATH=/workspace/dev/build-logs/meta_llama_3_1_8b_instruct_protect_mask_4pct.pt
pkill -9 -f vllm; sleep 2          # clear orphans
python -c "import vllm; from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache; print('ok', vllm.__version__)"
# if that import fails:
#   bash CTM_plus/Bench/scripts/rebuild_all_kernels.sh --clean --verify-source
#   (TORCH_CUDA_ARCH_LIST=8.0 for A100, 9.0 for H100)
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
