# Phase 6F — Read-path kernel fusion: PREP RUNBOOK (Test 3)

> **Status: PREP ONLY — NO KERNEL IMPLEMENTED, NOT STARTED.** This readies the
> scaffolding (correctness oracle, acceptance A/B, flag convention, step plan) so
> that *if* Test 3 is greenlit, the multi-week CUDA work starts instantly and
> burns zero pod time on tooling. The actual kernel fusion in the vendored
> `vllm-flash-attn-dev` fork is **deliberately not written here** — it is gated.
> Full kernel design lives in `PHASE_6F_KERNEL_OPT_DESIGN.md`.

## ⛔ ENTRY GATE — do NOT start the kernel until ALL hold

1. **Test 1 (6M.5) verdict ∈ {compute-bound, bandwidth-bound-uncoalesced}.**
   If bandwidth-bound-**coalesced**, 6F has a low ceiling → prefer Test 2 (H200)
   / §HBM. If **occupancy-bound**, re-measure first. *(Test 1 has NOT run yet.)*
2. The bounded ceiling (**~0.27–0.30×, NOT bf16 parity**) clears the product bar
   you are funding for.
3. **Explicit user go-ahead** — Test 3 is the "fund interactive" arm; it is a
   funding decision, not a measurement. Tests 1–2 do not authorize it.

If any fails: **stop**. Density + quality are the proven product; batch/offline
is the position. Throughput recovery is bounded upside, by design.

## What this prep gives you (ready now, CPU-verified)

| Artifact | Role | Verified |
|---|---|---|
| `phase6f_correctness_oracle.sh` | THE non-negotiable gate: byte-eq + COLLAPSE=0 + hard-needle + token-agreement, flag OFF vs ON | bash -n; runs on pod |
| `phase6f_acceptance_ab.sh` | performance A/B: profiles flag off/on, runs the acceptance analyzer | bash -n; runs on pod |
| `analyze_phase6f_acceptance.py` | CPU: gather/copy (name-matched) share drop ≤ 1/3 + no time regression → ACCEPTED | `--selftest` 7/7 |
| `tests/test_phase6f_acceptance.py` | CPU regression for the acceptance logic | 9/9 |

The eval scripts (`phase6k12_hard_needle.py`, `bench_phase6j_quality_gpu.py`,
`verify_phase6e_fused_byte_eq.py`) honor env flags, so the oracle passes the
read-path flag through to each. The kernel just needs to read `PHASE6F_FUSED_READ`.

## The flag scaffold (the isolation contract)

- **Env flag: `PHASE6F_FUSED_READ`** (mirrors the writer-side `PHASE6E_FUSED_WRITER`).
  `=0` (default) → today's unfused read path (paged gather + sidecar read +
  protected splice as separate ops). `=1` → the experimental fused kernel.
- **Rollback = revert the kernel commit.** The fork change must be gated so that
  with the flag off the binary path is byte-identical to today. That is what
  `phase6f_correctness_oracle.sh` proves (flag-off == reference, then flag-on ==
  reference) before any perf claim.
- **Do NOT couple to CUDA graphs** — 6M.3 showed graphs are ~neutral at
  saturation. Graph-capture of the fused path is not required.

## Implementation order (when greenlit) — execute top to bottom

0. **Baseline the oracle GREEN** on the target pod: run
   `phase6f_correctness_oracle.sh` with the flag a no-op → record the reference
   (byte-eq pass, needle pass, agreement ≥ 20.4, COLLAPSE=0). *Do this first so
   any later regression is unambiguous.* Then `phase6f_acceptance_ab.sh` →
   establishes the NOT-ACCEPTED baseline the real change must beat.
1. **Add the `PHASE6F_FUSED_READ` flag** plumbing in the fork + the int4 attn
   impl; flag-off path unchanged. Re-run the oracle → still GREEN.
2. **Fuse the paged gather + sidecar (scale/xmin) read INTO the kernel's
   per-block load** (kill the separate `aten::index`/`index_elementwise` pass).
   Read-path only — the writer is already at its lower bound.
3. **Fold the protected-K bf16 splice into the in-kernel dequant blend**
   (no separate splice op).
4. **Tighten the in-kernel group-wise dequant** per `PHASE_6F_KERNEL_OPT_DESIGN.md`.
   If Test 1 said **bandwidth-bound-uncoalesced**, the priority is the **byte
   layout**: interleave nibbles + scale + xmin + protected so each block read is
   one contiguous, coalesced transaction (the §HBM software answer).
5. After EACH step: `phase6f_correctness_oracle.sh` (must stay GREEN) then
   `phase6f_acceptance_ab.sh` (watch the gather/copy share shrink).

## Acceptance (performance) — when do we call it done

- `analyze_phase6f_acceptance.py`: gather/copy self-CUDA share drops to
  **≤ 1/3** of its pre-6F share AND total kernel time does not regress.
- End-to-end: protected agg-tps ratio moves toward the **~0.27–0.30× ceiling**
  (use the optional capacity `--compare` legs in `phase6f_acceptance_ab.sh`).
- **Correctness UNCHANGED** (the oracle): byte-eq GREEN; COLLAPSE=0; hard-needle
  + token-agreement within noise of the ≥ 20.4 baseline.

## Stop conditions (record and fall back to batch/offline)

- Oracle goes RED and can't be made byte-eq → **revert the kernel commit**.
- Gain **< ~0.05× absolute after weeks** → **stop**, record, batch/offline stands.
- Ceiling (~0.30×) never clears the product bar → the funding premise failed.

## Closed tracks (NEVER reopen here — 6G.2 RED for Qwen-7B)

int8-V, `n_protect` reduction, predicted-/symmetric-xmin, sidecar diet. **6F is
data-movement/compute orchestration ONLY — never a quality/compression change.**

## CPU prep verification (run anywhere; no GPU)

```bash
python CTM_plus/Bench/scripts/analyze_phase6f_acceptance.py --selftest   # 7/7
python CTM_plus/Bench/tests/test_phase6f_acceptance.py                   # 9/9
bash -n CTM_plus/Bench/scripts/phase6f_correctness_oracle.sh
bash -n CTM_plus/Bench/scripts/phase6f_acceptance_ab.sh
```
