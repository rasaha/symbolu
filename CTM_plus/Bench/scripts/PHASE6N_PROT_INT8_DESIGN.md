# PHASE 6N — int8 protected channels (prot-int8) DESIGN

Status: **GATED 2026-06-12** (A100-SXM4-80G pod, all checklist gates green
— results below). Shipped behind `INT4_PROTECTED_PROT_INT8` (DEFAULT
remains OFF — flag unset = byte-identical bf16-protect build; flipping
the default is a separate rollout decision, the measurement basis is
banked). Measured at the max-util pool (util 0.85, mml 32K, 24,987
blocks): sidecar tax 8.259 -> 7.306 GiB = **-0.953 GiB** (matches
1280 B/block x 24,987 x 32 layers minus the 10,240 B of dequant
constants TO THE BYTE); demo net density line **1.75x -> ~1.78x**.
Quality: greedy 6/6 BIT-IDENTICAL flag-ON vs OFF (32/32 layers active,
guard-verified); needle RETRIEVED at 16K both cells; S1 APC byte-gate
13/13 byte-exact under the `prot_int8_asym_static` marker; 6k12 hard
needle protected == bf16 bucket-for-bucket (0.875/0.955) in BOTH flag
states; recalibration reproduced the deployed mask byte-identically
(v2 artifact adds k_min/k_max, margin 1.1).
Storage note: codes are uint8 0..255 with the xmin offset (the probe's
exact math and the int4 path's existing asym convention) — "int8" in this
doc means 8-bit integer storage; the byte count is identical.
MODEL SCOPE: the full gate set above is **Llama-3.1-8B**. The mechanism
is per-model by construction (each model's own v2 calibration supplies
its min/max); protect's weight is model-specific, so each model gets the
short check before the flag is enabled there: recalibrate v2 ->
probe_block_quant_error (prot_int8_static_asym for THAT model) ->
phase6n_prot_int8_gate greedy A/B -> savings-probe needle A/B.

| model (short check 2026-06-12, same pod) | probe: cur_bf16 / asym-static (benefit retained) | greedy A/B | needle A/B | sidecar delta |
|---|---|---|---|---|
| Llama-3.1-8B (full gates) | 95.0% / 95.9% (**82%**) | 6/6 identical, 32/32 active | OK both | **-0.953 GiB** @24,987 blk (byte-exact) |
| Qwen2.5-7B | 93.9% / 94.7% (**87%**) | 6/6 identical, 28/28 active | OK both | **-0.991 GiB** @59,388 blk (byte-exact) |
| Mistral-7B-v0.3 | 93.7% / 94.6% (**86%**) | 6/6 identical, 32/32 active | OK both | **-1.015 GiB** @26,609 blk (byte-exact) |

THREE-MODEL READ: benefit retained 82-87% everywhere; greedy 18/18
prompts bit-identical across the three ON/OFF pairs; needles clean; all
three sidecar deltas match the byte arithmetic EXACTLY (the saving is
~1 GiB/model at util-0.85 pools despite different shapes — Qwen's
half-size per-block saving is offset by its 2.4x bigger pool). Mistral's
thin margins on unrelated gates did NOT materialize for prot-int8.
Lineage note: the Qwen and Mistral masks were freshly calibrated on this
pod (no prior artifacts existed here) — their A/Bs are internally
consistent but not comparable against historical pods' numbers.

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

## Gate checklist — ALL GREEN 2026-06-12 (A100-80G pod)

1. ~~probe static ~= dynamic~~ DONE (verdict above: asym-static, 95.9%).
2. ~~Selftests + guard tests still green.~~ DONE — all 8 test files, all
   module selftests, capture-safety verifier GREEN on pod.
3. ~~Needle + greedy bit-exactness~~ DONE — needle RETRIEVED at ctx=16384
   in BOTH flag states (savings probe, mml 32768); greedy **6/6
   BIT-IDENTICAL** ON vs OFF, 100% overlap (phase6n_prot_int8_gate,
   activation guard 32/32 ON / 0/32 OFF).
4. ~~APC S1 byte-gate + hard-needle 6k12~~ DONE — S1 13/13 events
   byte-exact, both engines under `prot_int8_asym_static`; 6k12
   protected == bf16 (strict 0.875 / retrieval 0.955, 0 ERROR) in BOTH
   flag states. (Driver gotcha recorded in the runbook: 6k12 needs
   --model AND --protect-mask — it pops $PROTECT_MASK_PATH.)
5. ~~Sidecar measurement~~ DONE — 8,867,932,672 -> 7,844,475,392 B
   (**-0.953 GiB**, exact to the byte vs the 1280 B/block arithmetic
   incl. +10,240 B constants); demo density line reads **~1.78x net**
   (sidecars 8.3 -> 7.3 GiB at the same 24,987-block pool).

## Probe verdict — FINAL (2026-06-12, three runs, 26,629 tokens x 32 layers)

| policy | mean|err| | % of no-protect | protect benefit retained |
|---|---|---|---|
| noprot | 0.06110 | 100.0% | — |
| cur_bf16 (deployed) | 0.05804 | 95.0% | 100% |
| prot_int8 dynamic (per-block) | 0.05822 | 95.3% | 94% |
| prot_int8 static SYM (absmax/127) | 0.05885 | 96.3% | 74% |
| **prot_int8 static ASYM (min/max)** | **0.05858** | **95.9%** | **82%** |

**DECISION: Variant A with ASYMMETRIC static scales.** The honest
arithmetic behind choosing simplicity over the last fraction:

- The asym-static vs dynamic gap is 12% of protect's benefit = 12% x the
  11.2% score-noise share ≈ **1.3% of total score noise** (SNR ~30 ->
  ~29.8). No end-to-end gate we run resolves that.
- Variant B is STRICTLY WORSE on memory, not just effort: per-block
  scale/offset sidecars cost ~160 B/block on top of the int8 values
  (1440 vs A's ~1280 B/block + 10 KB constants) — B buys 12% more of an
  11% effect while saving less memory and adding streaming-finalize
  code to the validated write hot path.
- Same-corpus caveat: real calibration adds a range margin (~1.1x each
  side); expect asym-static to land ~96.0-96.1% in deployment. Same
  argument holds. The build-time gate checklist (needle / greedy /
  byte-gate / hard-needle) is the final arbiter.

Calibration emits per protected channel: x_min, x_max (fp16, widened by
the margin factor) alongside the mask -> artifact version bump.

Effort: Variant A ~1-2 days dev + ~1 day gates. (Variant B retired.)
