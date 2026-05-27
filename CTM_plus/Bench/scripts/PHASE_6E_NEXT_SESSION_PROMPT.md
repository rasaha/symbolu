# Phase 6E next-session prompt

Paste this into a new Claude session at the start of focused CUDA-dev
work on Phase 6E Days 2-5. The prompt is self-contained — Claude
will pick up with full context.

---

## Prompt to paste

I'm continuing Phase 6E of the int4_protected backend work, on
branch `claude/phase-6b1-write-preflight-fjYee` of `rasaha/symbolu`.

**Project state going in:**

- Repo at `/workspace/symbolu` (or `/home/user/symbolu` in non-pod env).
- venv at `/workspace/venv-vllm` (activate with
  `source /workspace/venv-vllm/bin/activate`).
- Phase 6E Day 1 (scaffold + Python reference + CPU verifier + CUDA
  skeletons) is **DONE**. Commit: search for "Phase 6E Day 1" in git log.
- Days 2-5 (CUDA kernel implementation) are the work for this session.
- Phase 6 ARCHITECTURAL diagnosis already done: see
  `CTM_plus/Bench/scripts/PHASE_6D_PROFILING_RUNBOOK.md` and
  `CTM_plus/Bench/bench_out/phase6d_profile/PHASE_6D_PROFILE_SUMMARY.md`.
  Key finding: int4_protected captured is ~3x slower than stock vLLM
  bf16, and 100% of the gap is in the writer's ~30-small-CUDA-ops-per-
  decode-step Python chain. Phase 6E fuses those into 2 custom CUDA
  kernels.

**Read first:**

1. `CTM_plus/Bench/scripts/PHASE_6E_WRITER_FUSION_DESIGN.md` — the
   plan-of-record, including kernel signatures, contract, CPU
   verification plan, GPU acceptance gates, and risks.
2. `CTM_plus/CUDA_int4_protected/csrc/fused_decode_write.h` — the API.
3. `CTM_plus/CUDA_int4_protected/csrc/fused_decode_write_v.cu` — the V
   kernel skeleton with the full implementation spec in the file
   header (~30 lines of step-by-step guidance for the kernel body).
4. `CTM_plus/CUDA_int4_protected/csrc/fused_decode_write_k.cu` — same
   for the K kernel (the harder one due to the partial-accumulation
   + block-fill state machine).
5. `CTM_plus/KVPolicy/kv_policy/phase5b_4c_paged_writer.py` lines ~265-440
   for `_phase6e_fused_decode_write_python_ref` — the byte-equivalent
   Python reference any CUDA implementation must match.

**Work plan:**

Day 2 (today):
1. Build the extension on the pod:
   ```bash
   source /workspace/venv-vllm/bin/activate
   cd /workspace/symbolu && git pull origin claude/phase-6b1-write-preflight-fjYee
   cd CTM_plus/CUDA_int4_protected
   pip install --no-build-isolation -e .
   ```
   IMPORTANT: must use `--no-build-isolation`, otherwise pip downloads
   the latest torch from PyPI which mismatches the pod's CUDA driver.
2. Verify the extension loads (must `import torch` first):
   ```bash
   python -c "import torch; import int4_protected_C; print(dir(int4_protected_C))"
   ```
3. Adapt `CTM_plus/KVPolicy/tests/verify_phase6e_fused_byte_eq.py` so
   it runs on CUDA tensors (it's CPU-only today). Add a `--device cuda`
   option and run the same byte-equality checks. Should PASS using the
   Python ref alone (since `PHASE6E_FUSED_WRITER=1` currently calls
   the Python ref).
4. Implement `fused_decode_write_v` (simpler kernel; the V-side path).
   Spec in `fused_decode_write_v.cu` file header.
5. Wire it into Python: add `int4_protected_C.fused_decode_write_v(...)`
   call inside `_phase6e_fused_decode_write_python_ref` (gated behind
   another env or a build-time presence check, so the Python fallback
   still works if the extension isn't built).
6. Re-run `PHASE6E_FUSED_WRITER=1 verify_phase6e_fused_byte_eq.py
   --device cuda` to confirm the V kernel is byte-equivalent.

Day 3-4:
7. Implement `fused_decode_write_k`. The K kernel is more complex —
   read the state-machine description in its `.cu` header carefully.
   Key items: partial-accumulation into k_stage_pool, block-fill
   detection, conditional finalize writing to kv_cache + k_scale/xmin
   sidecars, atomic seq_pos_pool increment.
8. Wire it into Python similarly. Re-run the verifier.

Day 5:
9. End-to-end smoke test:
   ```bash
   PHASE6E_FUSED_WRITER=1 python CTM_plus/Bench/scripts/bench_phase6_b3_capture_gpu_smoke.py
   ```
   Expected: 20/20 G_CAPTURE.2 semantic-eq checks GREEN (same as
   default; the fused path must preserve correctness).
10. Throughput re-bench:
    ```bash
    PHASE6E_FUSED_WRITER=1 python CTM_plus/Bench/scripts/bench_phase6_b4_throughput_gpu.py
    ```
    Acceptance gates (from PHASE_6E_WRITER_FUSION_DESIGN.md):
    - 6B.3 semantic-eq still GREEN
    - captured B=8 agg_tps ≥ 220 tok/s (current 174 → at least 1.25×)
    - cap/bf16 ratio at B=32 ≥ 0.25× (current 0.19×)
    - HBM ≤ 46 GB (no regression)
    - captured B=1 agg_tps within 5% of current 39.2 tok/s

11. Write `PHASE_6E_WRITER_FUSION_FINDINGS.md`: methodology, measured
    deltas vs Phase 6C, what worked, what didn't, lessons.
12. Update `PHASE_6B_CUDA_GRAPHS_PLAN.md` to mark 6E CLOSED.
13. Regen G5c SHA baseline for `phase5b_4c_paged_writer.py` (only
    file that changes outside the new `CUDA_int4_protected/` package).

**Critical things to get right in the CUDA kernels:**

- **Memory ordering in fused_decode_write_k.** The kernel reads
  prior_block_id and current_k_stage, then writes back updated
  k_stage_pool, then reads it for quantization. Use `__threadfence()`
  between the write and the subsequent read if reading via gmem (use
  registers if possible — single thread block per (B, H) means the
  whole BS×D tile fits in registers/shared mem).
- **Atomic seq_pos_pool increment.** Multiple batch positions might
  alias to the same slot (shouldn't in production but the inactive-
  mask scenario allows it). Use `atomicAdd(seq_pos_pool + slot, 1)`
  guarded by active_mask.
- **Inactive mask handling.** If `slot_mapping[b] < 0`, the thread
  writes to slot 0 / block 0 / position 0 (harmless, matches the
  Python ref's `torch.where(active_mask, ..., torch.zeros_like(...))`
  pattern). Don't try to skip the work — keeping all threads active
  is graph-capture-friendly.
- **Byte equivalence vs FP equivalence.** The CPU verifier asserts
  EXACT byte equality. The quantization math (amax/amin/scale/round)
  must produce identical bytes. Use `__float2uint_rn` for round-to-
  nearest-even on uint8 conversion; PyTorch's `.round()` is half-to-
  even, so match that semantics.

**Common gotchas (already hit in Phase 6 work):**

- `pip install -e .` without `--no-build-isolation` will download
  latest torch and break on CUDA version mismatch. Always use
  `--no-build-isolation`.
- `import int4_protected_C` requires `import torch` first (loads
  libc10.so dependencies).
- The CPU verifier's test workload MUST keep `block_ids` distinct
  across batch positions, otherwise the captured region's scatter
  `kv_cache[0, block_ids, ...]` hits PyTorch's non-deterministic
  duplicate-index scatter and the test becomes flaky.
- vLLM 0.7.3 V0's `capture_model` runs the forward INSIDE
  `torch.cuda.graph()` — any `.item() / .cpu() / .tolist()` in the
  captured region crashes. The CUDA kernels themselves are fine; just
  don't add any Python host syncs around the kernel launch.

**What CAN'T be done without a GPU pod:**

- Actually compiling the .cu files.
- Running CUDA-tensor verifiers.
- Running the throughput bench.

If the GPU pod is unavailable, the highest-value no-GPU work is
extending the CPU verifier with more edge cases (B values up to 32,
longer sequences, inactive-mask scenarios) so the eventual CUDA
implementation has tighter test coverage.

**Key context dump:**

- Branch: `claude/phase-6b1-write-preflight-fjYee`
- Phase 6E env flag: `PHASE6E_FUSED_WRITER=1` opts in; default is `0`.
- Phase 6C env flag (also relevant): `PHASE6C_BF16_BACKING_SKIP=1`
  (default) skips the dead bf16 backing pool — DO NOT disable this
  during 6E work.
- Test command (CPU, today):
  `python CTM_plus/KVPolicy/tests/verify_phase6e_fused_byte_eq.py`
- Test command (CUDA, after Day 2):
  `PHASE6E_FUSED_WRITER=1 python CTM_plus/KVPolicy/tests/verify_phase6e_fused_byte_eq.py --device cuda`
- Throughput bench (Day 5):
  `PHASE6E_FUSED_WRITER=1 python CTM_plus/Bench/scripts/bench_phase6_b4_throughput_gpu.py`

Begin by reading `PHASE_6E_WRITER_FUSION_DESIGN.md` and the two `.cu`
file headers. Confirm the design + spec are clear. Then implement.
