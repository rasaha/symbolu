# Claude prompt — next session (int4_protected packaging + customer-style test)

Copy-paste everything below the line as the session prompt.

---

You are continuing work on int4_protected (Cognade Labs' quality-preserving 4-bit
KV-cache backend for vLLM 0.7.3 V0, on Llama-3.1-8B). Be the honest engineer +
strategic sounding board — no rosy numbers, disclose costs.

BRANCH: claude/bold-johnson-rXAd4  (git pull first; commit+push your work,
rebase if the remote moved).

WHAT'S TRUE (measured 2026-06-12 on a live A100-SXM4-80G pod; don't re-litigate):
- DENSITY: 2.00x raw pool measured live (399,792 -> 799,584 token-slots,
  util 0.85, mml 32768); sidecars 8.3 GiB OUTSIDE the pool (measured, ~16%
  of pool, scales with pool) -> ~1.75x net at equal total VRAM.
- QUALITY: needle RETRIEVED at ctx=16K (eager B=1, post cu128-toolchain
  rebuild); hard-needle 0.955 == bf16 (6K.16).
- APC (eager-only, shipped): TTFT saved 53/56/78/86% per cache hit at
  1K/2K/4K/8K shared prefixes; batch throughput 1.19-1.85x at 94% hit rate
  (1.28-1.54x at 75%); quality 1.00 == APC-off in EVERY cell; net of the
  eager tax. Banked in the docs.
- GATHER-FUSION HEADROOM: GO — fuseable pre-kernel gather+splice+prep =
  59.9% of the B=1 int4 read path at 8K ctx, 42.0% at 32K (kernel grows
  faster); gather is GPU-time-bound (cpu/gpu 0.2-0.7x) so the fix is the 6F
  CUDA fusion, NOT python vectorization. Building 6F is NOT this session's
  job (funding-gated; deploy-first priority stands).
- DECODE COST unchanged + disclosed: 0.22-0.67x bf16, ceiling ~0.27-0.30x,
  never parity.
- Guards: chunked prefill factory-pinned OFF (6K.17 — vLLM V0 auto-enables
  it at mml>32768; CPU guard tests exist); APC eager-only (graphs+APC gated
  off, kernel not graph-safe at B>1); swap preemption refused (6K.15).
- Docs already carry all measured numbers (INT4_PROTECTED_VC_BRIEF.md;
  deploy/INT4_PROTECTED_DESIGN.md §6). Session ledger with every gotcha:
  CTM_plus/Bench/scripts/NEXT_POD_SESSION_INT4_GPU_RUNS.md — READ IT FIRST.

POD REALITIES (hit live; in the ledger — do not re-learn them):
- Fresh pods may have NO /workspace/venv-vllm. System python is the working
  stack when this prints ok:
    python -c "import vllm; from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache; print('ok', vllm.__version__)"
  Never tell the operator to source a venv that doesn't exist.
- rebuild_all_kernels.sh: auto-sizes MAX_JOBS from RAM (the nproc default
  OOMed a 256-vCPU pod), writes full logs to /workspace/dev/build-logs/,
  auto-untars the fork from /workspace/vllm-flash-attn-dev-src.tar.gz;
  install/restore scripts derive the vendored slot from the active python.
- The protect mask may be MISSING on a fresh pod; regenerate (~3 min):
    python CTM_plus/Bench/scripts/calibrate_phase5b_protect_mask.py \
      --model NousResearch/Meta-Llama-3.1-8B-Instruct \
      --output /workspace/dev/build-logs/meta_llama_3_1_8b_instruct_protect_mask_4pct.pt
- GPU memory: sidecars + graph-capture staging live OUTSIDE
  gpu_memory_utilization. Probes run eager with capped max_num_seqs; sweeps
  default util 0.60/0.70. Do NOT "optimize" these back to 0.85.
- Environment preamble for every GPU run:
    M=NousResearch/Meta-Llama-3.1-8B-Instruct
    export PROTECT_MASK_PATH=/workspace/dev/build-logs/meta_llama_3_1_8b_instruct_protect_mask_4pct.pt
    pkill -9 -f vllm; sleep 2

LOOSE ENDS (collect at session start, before the main task):
- ctx=16000 gather-headroom block (expect ~50%, GO) — bank in the ledger.
- Task 4 crossover results (phase10_crossover_sweep.py, /tmp/x10 on the
  pod): if available, bank the table + update the brief's read-skip section
  HONESTLY — a quality-clean crossover is a headline; NO crossover means
  bound the story to the density/niche framing. The driver quality-gates;
  trust only clean rows.

THE TASK — PACKAGE int4_protected so a customer pod goes from zero to the
savings demo through ONE entry point, then test it like a customer would:

1) BUILD THE PACKAGE (deploy/pkg/ or similar):
   - install.sh (idempotent, full logs, loud FAILs): enforce pins
     (vllm==0.7.3, torch==2.5.1+cu121) -> build/install kernels (reuse
     rebuild_all_kernels.sh; derive TORCH_CUDA_ARCH_LIST from nvidia-smi)
     -> vendored-slot install -> mask calibration (skip if artifact exists)
     -> import + patched-source smoke.
   - Make kv_policy pip-installable from the repo (CTM_plus/KVPolicy has a
     setup.py — verify completeness: packages, version pins, no GPU import
     at install time).
   - The fork tarball and built wheels are TOO BIG for git: document the
     artifact channel (tarball under /workspace or object storage) in
     QUICKSTART. Do NOT commit binaries.
   - One entry point (Makefile or int4ctl wrapper): install / calibrate /
     verify / demo subcommands mapping to the existing scripts.

2) TEST THE PACKAGE like a customer (acceptance gates, run on the pod):
   - Fresh shell, ONLY package entry points (no repo-internal knowledge):
     install -> verify (import ok + 4/0 patched call sites) -> calibrate or
     detect mask -> customer_savings_demo.sh --quick.
   - Gates: density ~2.00x raw / ~1.75x net renders LIVE; needle RETRIEVED;
     APC saving present and GROWING with prefix; quality clean everywhere.
   - Run the CPU guard tests (tests/test_phase6k15_swap_guard.py,
     test_phase6k16_prefix_guard.py, test_phase6k17_chunked_guard.py) and
     every script --selftest; paste results.

3) DOCS: rewrite deploy/QUICKSTART.md against the real entry point (every
   command copy-paste-able on a fresh pod); update DESIGN §8 if the flow
   changed; refresh the ledger.

RULES: measure before claiming; quality-gate every throughput number (a win
on corrupted output never counts); if a package step errors on a real pod,
FIX the script and push — the script IS the product. If a result is
null/negative, say so and bound the story. Don't put the model id in
commits/docs. Disclose costs (decode tax, sidecar tax scaling with pool,
eager-only APC).
