# PHASE 6N — int8 protected channels (prot-int8) DESIGN

Status: DESIGN + probe evidence. NOT implemented in the shipping path —
`k_protect_ext` is bf16 everywhere today. Build gated on the static-scale
probe run below.

## Evidence (probe_block_quant_error, 2026-06-12, 26,629 tokens x 32 layers)

- prot_int8 (per-block dynamic scales): mean|err| 0.0580 vs cur_bf16 0.0578
  (95.0% vs 94.7% of no-protect) — int8 storage costs **0.3pp** of mean error.
- Protected channels carry **11.2%** of score-noise weight (2.8x their 4%
  budget) — demoting them from exact to int8 adds well under 1% score noise.
- Prize: protect sidecar 2560 B/block -> ~1300 B/block ≈ **-1.0 to -1.1 GiB**
  at the max-util pool; net density ~1.75x -> **~1.78x**.

## The streaming wrinkle (why scale choice is THE design decision)

`k_protect_ext` is written PER TOKEN (writer lines ~917 / ~1802 / ~2164:
`k_protect_ext[block_ids, positions] = k_protect`). A per-block dynamic int8
scale needs all 32 tokens -> block-finalize/requant machinery (the same
problem the streaming K/V quantizers solve). Two variants:

- **Variant A — STATIC per-(layer, head, channel) scale (preferred if gated):**
  scale = calib_absmax / 127, computed at calibration time alongside the mask
  (~5 KB constant sidecar TOTAL). Per-token write = `round(x/s).clamp(±127)`.
  No streaming changes, no finalize, deterministic. Risk: clipping if a live
  value exceeds calibration max (mitigate: 1.25x margin; clipped extremes are
  inside the 11%-share error budget). DECIDE via the probe's
  `prot_int8_static` policy (same-corpus scale = lower bound on error; if it
  is ~= dynamic int8 there, variant A proceeds with a margin).
- **Variant B — per-block dynamic scales:** matches the probe's measured
  0.3pp exactly, but requires block-finalize requant on the streaming write
  path (+2 small sidecars: scale/offset per (block,H,n_protect)). Only if A
  fails its probe check. Effort roughly doubles.

## Touch points (exact)

| Site | Change |
|---|---|
| writer alloc (`phase5b_4c_paged_writer.py` ~1532) | `k_protect_ext` dtype bf16 -> int8; + static scale buffer (L-local: (H, n_protect) per layer writer) |
| writer write sites (~917, ~1802, ~2164) | quantize protect slice with static scale before scatter |
| writer read view (~2505 `get_packed_view_batched`, + the `one.*` path) | dequant gathered protect to bf16 buffer — KERNEL UNCHANGED (it keeps receiving bf16 `k_protect`) |
| backend `_resolve_k_protect_bf16` (`phase5b_backend_install.py` ~206) | operates on the dequanted view — verify no raw-tensor assumptions |
| prefix-prefill (`phase6k16_prefix_prefill.py` ~71/~117/~311) | dequant before scatter-merge |
| calibration (`calibrate_phase5b_protect_mask.py`) | emit per-channel absmax for protected channels into the mask artifact (mask artifact version bump) |
| debug snapshot (writer ~567) | dequant for the debug dict |

## Contract notes

- **S1 byte-gate (6K.16)**: sidecar BYTES change format. The byte-gate must
  either compare DEQUANTED protect values or version the contract — flag in
  the PR; do not let the gate silently compare int8 vs bf16 bytes.
- Rollout: env flag `INT4_PROTECTED_PROT_INT8=1`, default OFF until gates.
- Swap/preemption guards (6K.15/17) unaffected (sidecars still not migrated).

## Gate checklist (build session, pod)

1. probe `prot_int8_static` policy ~= dynamic int8 (pre-build decision).
2. Selftests + guard tests still green.
3. Needle 16K/32K (savings probe) + 6-prompt greedy bit-exactness vs the
   bf16-protect build (expect: same identical-count, overlap within noise).
4. APC S1 byte-gate (with the contract note above) + hard-needle 6k12 cell.
5. Sidecar measurement (savings probe) confirms ~-1 GiB; density line moves
   1.75x -> ~1.78x in the demo report.

## Probe verdict (in progress, 2026-06-12)

First static run (SYMMETRIC absmax/127 scales): noprot 0.0611 /
cur_bf16 95.0% / prot_int8(dynamic) 95.3% / prot_int8_static 96.3% —
static retains ~74% of protect's mean-error benefit vs dynamic's ~94%
(score-noise delta ~2% of total; SNR ~30 -> ~29.4). Outside the 0.5pp
auto-lock threshold -> added the ASYMMETRIC static policy (min/max per
channel, ~10 KB constants, still zero streaming changes; one-sided
channels recover up to 2x resolution). Final variant call after the
prot_int8_static_asym run. If asym-static ~= dynamic -> Variant A with
asymmetric static scales; else judgment call between A (simplicity,
~74-85% of an 11%-share benefit) and B (fidelity, streaming machinery).

Effort: Variant A ~1-2 days dev + ~1 day gates. Variant B ~3-4 days dev.
