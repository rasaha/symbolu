# Phase 9 — FINAL VERDICT: read-skip kernel is justified (GREEN)

> Capstone tying the whole Phase 9 arc together. The gating question —
> *is the read-skip / sparse-decode kernel (and PCAM behind it) worth building?* —
> is answered: **YES, conditionally GREEN.**

## The question and the proven baseline

- **int4_protected** (the product) was never in doubt: **1.83× density, quality =
  bf16**. Shippable today.
- int4 is a *density* play — on its own it is *slower* than bf16 (0.22–0.54×). The
  ONLY way it wins **throughput** is **read-skip** (not reading cold KV each step).
  That prize had two unproven IFs.

## The two IFs — both now satisfied

| IF | How tested | Result |
|---|---|---|
| **Throughput**: does read-skip decode faster at long context? | sliding-window proxy (Mistral SWA on/off) | ✅ **~10× at 16k** (scales with length, per Step-0 model) |
| **Quality**: does dropping cold KV keep recall (the H2O risk)? | decode-time attention-retention harness, Qwen2.5-7B, ctx8192 | ✅ **GREEN** — retention keeps `needle_retained 1.0` + `hit 1.0` on BOTH single- and multi-needle, where fixed windows drop to 0.33; MMLU unchanged |

The decisive insight: **decode-time attention** (what the generated-token queries
actually retrieve) correctly selects the needle's block, where the earlier
prefill-relevance signal (v1) and fixed recent-windows fail. `needle_retained`
in the logs proves this is a *selection* win, not a generation fluke.

## Verdict

**Build the read-skip kernel.** The composition is:
- **int4_protected** as the cold-tier store (proven density + quality), AND
- **attention-guided read-skip** (sink + recent + decode-attention-selected blocks)
  to avoid reading the cold majority each step.

This is the int4 *throughput* prize, reachable without sacrificing quality — and
the empirical basis for PCAM (the hardware embodiment of the per-step skip decision).

## Build gates (carry forward — do NOT skip)

1. **Bank the full quality run** (4 seeds × 5 depths × both tasks) for the record;
   the fast runs showed perfect separation but N is modest.
2. **Verify the composition**, not just the parts: int4 cold store + read-skip
   together must keep needle + MMLU within noise (storage ⊥ access pattern is the
   assumption; confirm it).
3. **Physical pruning == masked behaviour:** this harness *masks* a full cache
   (correctness, not speed). The kernel physically prunes/skips; verify it
   reproduces the masked quality.
4. **The dispatch tax (the PCAM gate):** the per-step skip decision is the Phase-8
   −20% hot-path. Profile it; if it eats the gain in Python, that is the case for
   the fast-path (Cython/CUDA/PCAM) implementation — software read-skip must not
   reintroduce the tax.

## The honest path that got here

The GREEN is credible only because the baseline was made trustworthy. That took
isolating a chain of confounds (each a real bug): copy-hostile payloads → number-
laden filler → chat run-on → and the decisive one, **eager+bf16 fuzzing the QK
matmul** (sdpa=1.0 vs eager-bf16≈0.9; fixed via eager+fp32, which keeps
decode-attention observation intact). Lesson logged: a quality gate is only as
good as its baseline — validate the yardstick before judging the policy.

## What this session delivered (all on PR #1058)

- Step 0 (CPU model): read-skip prize sized + made achievable-derived.
- Step 1 (GPU smoke): Route-A integration + bridge verified; flusher + bootstrap
  fixes.
- Scope reconciliation: read-skip = intra-sequence sparsity (not the cross-request
  evictor); needs a kernel.
- De-risk ladder: sliding-window proxy (throughput real) → retention prototype
  (v1 flaw found) → **decode-time retention harness → GREEN**.
- Decision: **read-skip kernel justified**; int4_protected density+quality remains
  the shipped product regardless.
