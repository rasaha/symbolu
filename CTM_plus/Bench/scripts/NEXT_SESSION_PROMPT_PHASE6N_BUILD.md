# Claude prompt — Phase 6N build session (int8 asymmetric-static protected channels)

Copy-paste everything below the line as the session prompt. Run it in a
session WITH pod access (the gates are mandatory before merge).

---

You are continuing work on int4_protected (Cognade Labs' quality-preserving
4-bit KV-cache backend for vLLM 0.7.3 V0, Llama-3.1-8B). Be the honest
engineer — no rosy numbers, gate every change.

BRANCH: claude/bold-johnson-rXAd4 (git pull first; commit+push your work).

THE TASK — implement Phase 6N exactly as specified in
CTM_plus/Bench/scripts/PHASE6N_PROT_INT8_DESIGN.md (READ IT FIRST — it has
the locked variant, all touch points with line refs, and the gate
checklist). Summary of the locked decision (probe-measured, 3 runs):

- Store protected K channels at **int8 with ASYMMETRIC STATIC per-channel
  scales** (x_min/x_max from calibration, widened by a ~1.1x margin;
  ~10 KB of constants). Measured: 95.9% of no-protect error vs deployed
  bf16-protect's 95.0% — residual gap ~1.3% of total score noise, below
  gate resolution. Variant B (per-block dynamic) is RETIRED: strictly
  worse on memory, adds streaming-finalize code.
- Prize: protect sidecar 2560 -> ~1280 B/block ≈ -1.0-1.1 GiB at max-util
  pool; net density 1.75x -> ~1.78x.
- Rollout flag: INT4_PROTECTED_PROT_INT8=1, DEFAULT OFF. Flag unset =>
  byte-identical behavior to today (bf16 protect). Build additive.

BUILD ORDER (from the design doc):
1. calibrate_phase5b_protect_mask.py: also accumulate per-channel signed
   min/max for protected channels; write into the artifact (version bump,
   backward compatible — old artifacts simply disable the feature).
2. Writer (phase5b_4c_paged_writer.py): flag-gated int8 alloc for
   k_protect_ext + per-layer (H, n_protect) scale/offset constants;
   quantize at the 3 per-token write sites (~917, ~1802, ~2164).
3. Read paths: dequant to bf16 buffers at get_packed_view_batched (~2505),
   the one.* path, the debug snapshot (~567), and phase6k16_prefix_prefill
   (~71/~117/~311). THE KERNEL IS UNCHANGED — it keeps receiving bf16
   k_protect buffers.
4. S1 byte-gate: compare DEQUANTED protect values (or version the
   contract) — do NOT let it diff int8 vs bf16 bytes silently.
5. CPU unit tests mirroring tests/test_phase6k17_chunked_guard.py style:
   quant/dequant roundtrip vs the probe's policy math
   (probe_block_quant_error.policy_errors is the reference), flag-off
   no-op, artifact-missing fallback.

GATES (pod, in order; flag ON vs OFF A/B):
1. Recalibrate the mask artifact (now with minmax):
     python CTM_plus/Bench/scripts/calibrate_phase5b_protect_mask.py \
       --model NousResearch/Meta-Llama-3.1-8B-Instruct \
       --output /workspace/dev/build-logs/meta_llama_3_1_8b_instruct_protect_mask_4pct.pt
2. All selftests + guard tests green (incl. new unit tests).
3. deploy/_savings_probe.py int4 needle at mml 32768 (needle RETRIEVED;
   sidecar_bytes drops ~1 GiB vs flag-off — paste both JSONs).
4. 6-prompt greedy bit-exactness vs the flag-OFF build (bench_8bit_kv_gate
   bitexact methodology or a 10-line script): expect same identical-count,
   overlap within noise.
5. APC S1 byte-gate + 6k12 hard-needle cell.
6. customer_savings_demo.sh --quick with flag ON: density line should read
   ~1.78x net.

POD REALITIES: read CTM_plus/Bench/scripts/NEXT_POD_SESSION_INT4_GPU_RUNS.md
(venv may not exist — system python OK when the kernel import prints ok;
PROTECT_MASK_PATH required; sidecars live OUTSIDE gpu_memory_utilization —
probes run eager/capped; chunked prefill is factory-pinned OFF).

RULES: flag default OFF until every gate passes; if any gate fails, fix or
revert — never ship red; measure before claiming; a win on corrupted
output never counts. Don't put the model id in commits/docs. Update
PHASE6N_PROT_INT8_DESIGN.md status + the ledger + DESIGN §6 density row
(1.78x) ONLY after gates pass.
