# VC Brief — Replication Audit

> **Status:** Audit only. **VC brief unchanged pending review.** Phase 8
> retirement requires NO removal from this brief — Phase 4 KV eviction
> is not mentioned anywhere in `INT4_PROTECTED_VC_BRIEF.md`. The audit
> is about replication depth and source traceability for the existing
> INT4 protected claims.
>
> **Date:** 2026-05-26. Audit standard: every partner-facing number
> must have ≥2 independent measurements; 60s-wall provisional;
> measured ≠ projected ≠ computed.

## Headline findings (read first)

1. **Two claims have no traceable measurement support.** They look
   like reframings of other numbers or external claims with no
   attribution. Material partner-safety risk.

   * `fp8 ~12% needle-in-haystack recall vs bf16's 100%`
     (Pages 1, 3, 4). The 12% number is *common-prefix overlap*
     measured by `bench_phase5c_v1.py` (PHASE5C_SHIP_REPORT §"Headline"),
     NOT needle recall. fp8 needle was never measured on this codebase.

   * `pure int4 KIVI on K + V catastrophically loses long-context
     recall (100% → 11-29% on needle at 16K)` (Pages 1, 4). The
     11-29% figure does not appear in any committed benchmark
     artifact. Either an external citation is missing or the
     measurement was never run on our infrastructure.

2. **A cuda-blocks number is internally inconsistent.** Page 3
   reports `bf16 cuda blocks = 13,967`. PHASE5C_SHIP_REPORT.md
   and PHASE6_PERF_REPORT.md both consistently report `bf16 cuda
   blocks = 27,934`. The brief's number is exactly 50% of the
   bench evidence. Likely a typo or a non-standard normalization
   that's not explained.

3. **The bit-identical denominator drifted (3/5 vs 3/6).**
   Page 3 table reports `int4_protected: 3/5` and `fp8: 0/5`.
   All bench docs (PHASE5C, PHASE6) consistently report 3/6 and
   0/6 from a 6-prompt run. Either an unreported 5-prompt re-run
   exists, or the brief truncated. Affects two cells.

4. **All 4-model needle results are single-run-per-model.** No
   2-of-2 replication exists for any model. The methodology is
   sound (15 trials per run), but a partner asking "is this
   repeatable?" gets a one-run answer today.

5. **Aggregate throughput "42.5 tok/s @ B=8 Qwen-7B"** comes from
   one OPTION_B_PREFLIGHT measurement post-buffer-fix. Not
   replicated at the audit's 180s standard.

6. **Phase 8 retirement: no impact.** The brief does not mention
   Phase 4 KV eviction, CTM+ Phase 4 trig, route-A, the bridge,
   or any combined-stack operating point. Nothing to remove.

## Claim-by-claim table

Pages reference the existing brief. "Replicated" = 2+ independent
measurement runs. Scope categories: **Q** (measured quality),
**T** (measured throughput/serving), **M** (memory accounting,
computed from kernel config + cuda-block count), **P** (projected/
not-yet-measured), **C** (competitive claim about other systems).

### Page 1 — The Problem

| # | Claim | Cat | Evidence source | Replicated | Wall / sample | Scope caveat | Disposition | Follow-up |
|---|---|---|---|---|---|---|---|---|
| 1.1 | `fp8 ~12% needle vs bf16's 100%` | C/Q | NOT MEASURED. PHASE5C measured 12% common-prefix overlap, not needle. | ❌ | — | **misrepresents the underlying measurement** | **REVISE** — replace with measured "0/6 bit-identical, 12% prefix match" OR run fp8 needle to substantiate | R1: run fp8 needle on Qwen-7B (~$0.05) |
| 1.2 | `pure int4: needle 11-29% at 16K` | C | No traceable source in bench artifacts | ❌ | — | claim about KIVI baseline | **REVISE or REMOVE** — needs either external citation or own measurement | R2: optional route-B INT4-K-and-V needle on 16K (~$0.10) |
| 1.3 | `4 models validated this quarter` | Q | PHASE5C_USAGE.md model table | partial (4 models × 1 run each) | 15 trials per model | each model 1 measurement | **KEEP but note "single-run per model"** in honest-status table | R3: 2x replication of needle on all 4 models (~$0.30) |

### Page 3 — Validated Portfolio

| # | Claim | Cat | Evidence source | Replicated | Wall / sample | Scope caveat | Disposition | Follow-up |
|---|---|---|---|---|---|---|---|---|
| 3.1 | Qwen2.5-7B needle 15/15 | Q | `verify_phase5b_5_needle.py` Phase 5B.6 | ❌ (1 run) | 15 trials, ≤1200 filler tokens | short-context (≤1200 tokens, NOT 4096+ or 16K+) | **KEEP** with scope label "≤1200 filler tokens" | R3 |
| 3.2 | Mistral-7B-Instruct-v0.3 needle 15/15 | Q | PHASE5C_USAGE.md Phase 7 row | ❌ (1 run) | 15 trials, ≤1200 filler tokens | same scope as 3.1 | **KEEP** with same scope label | R3 |
| 3.3 | Llama-3.1-8B-Instruct needle 15/15 | Q | PHASE5C_USAGE.md Phase 7 row | ❌ (1 run) | 15 trials, ≤1200 filler tokens | same scope; **ungated NousResearch mirror, NOT meta-llama/** | **KEEP** with both scope labels | R3 |
| 3.4 | Qwen2.5-14B-Instruct needle 15/15 | Q | PHASE5C_USAGE.md Phase 7 row | ❌ (1 run) | 15 trials, ≤1200 filler tokens | same scope as 3.1 | **KEEP** with same scope label | R3 |
| 3.5 | `0 fallbacks across ~100K aggregate decode calls` | Q | PHASE5C_USAGE (Llama 30240+30720; Qwen14B 45360+46080) | aggregate across models | ~100K total = decodes + writes summed | "100K" is loose: decodes + writes, not all decodes | **REVISE wording** to "decode + write calls aggregate" OR compute the actual decode-only count | R4 (free, recount from logs) |
| 3.6 | `bf16 cuda blocks = 13,967` | M | **inconsistent**: PHASE5C says 27,934 | ❌ — internally inconsistent | one run | factor-of-2 error vs source bench | **REVISE** — match PHASE5C's 27,934 OR explain the normalization | R5: re-bench three-way (~$0.05) AND fix wording |
| 3.7 | `fp8 cuda blocks = 28,060; int4_protected = 28,060` | M | PHASE5C says fp8=56120, int4_proto=28060 | ❌ — fp8 number inconsistent | one run | brief's 28,060 for fp8 doesn't match PHASE5C's 56,120 | **REVISE** — either match PHASE5C OR document normalization | R5 |
| 3.8 | `218× max concurrency vs stock 109× (Qwen-7B at 4096)` | T | `executor_base.py:116` log line; PHASE5C 219.22 | ❌ (1 run, log scrape) | one engine init | single startup log, not a benchmark | **KEEP** with note "from single engine-init log line"; replicate at 2 different gpu_memory_utilization settings would strengthen | R6: replicate startup log (~$0.02) |
| 3.9 | `3/5 bit-identical greedy on Qwen-7B` (Page 3 table) | Q | PHASE5C / PHASE6 say 3/6 | inconsistent denominator | 5 or 6 prompts? | denominator drift | **REVISE** to 3/6 OR cite the unreported 5-prompt run | R4 (free, decide which is canonical) |
| 3.10 | `fp8 0/5 bit-identical` (Page 3 table) | Q | PHASE5C / PHASE6 say 0/6 | inconsistent denominator | same as 3.9 | same as 3.9 | **REVISE** to 0/6 | R4 |
| 3.11 | `per-seq decode latency ~3.7×` | T | PHASE6_PERF_REPORT 3.75× | ❌ (1 run) | one benchmark | single OPTION_B post-fix measurement | **KEEP, rounded to 3.7-3.8×** | R7: replicate at 180s (~$0.10) |
| 3.12 | `42.5 tok/s @ B=8 Qwen-7B` | T | OPTION_B_PREFLIGHT.md "post-buffer-fix" | ❌ (1 run) | short benchmark, not 180s | NOT replicated at audit standard | **MARK PROVISIONAL** until replicated | R7 (combined with 3.11) |
| 3.13 | `CUDA Graphs projects 2-3× aggregate throughput, closes most of the gap` | P | PHASE6 phase profile (90% launch overhead) | n/a — projected | n/a | properly labeled projection | **KEEP** — already labeled projected | none |

### Page 4 — Competitive Landscape

| # | Claim | Cat | Evidence source | Replicated | Wall / sample | Scope caveat | Disposition | Follow-up |
|---|---|---|---|---|---|---|---|---|
| 4.1 | `fp8 0/6 bit-identical` (Page 4 table, correct denominator) | Q | PHASE5C/PHASE6 | ❌ (1 run) | 6 prompts | matches bench evidence | **KEEP** | R3 captures replication |
| 4.2 | `KIVI 11-29% at 16K context` (Page 4 table) | C | No traceable source | ❌ | — | same as 1.2 | **REVISE or REMOVE** | R2 |
| 4.3 | `TurboQuant W4A4 <1% MMLU loss on Llama-2` | C | external paper (presumably) | n/a — competitor claim | n/a | needs citation | **KEEP with citation** | R8: cite source paper |
| 4.4 | `AWQ / GPTQ does NOT compress KV` | C | true by definition (weight-only) | n/a — definitional | n/a | accurate | **KEEP** | none |
| 4.5 | `4-bit-quality gap has been an open problem for ~18 months` | C | framing | n/a | n/a | not numerically verifiable | **KEEP** if accurate to literature | none |
| 4.6 | Cross-family/scale generalization claims (Qwen-7B IoU 11.1% vs Qwen-14B IoU 2.6%) | Q | PHASE5C_USAGE (?) | ❌ (1 calibration per model) | one calibration run | **per-layer specialization claim — needs source pin** | **KEEP with source citation in appendix** | R9: pin IoU evidence to specific script output |

### Page 6 — Honest Validation Status

This page already separates measured/projected. The structure is
fine; the **content** of the measured rows is what gets audited
elsewhere in this table.

| # | Claim | Cat | Evidence source | Replicated | Disposition |
|---|---|---|---|---|---|
| 6.1 | `4 models all hit 15/15 needle` | Q | per-model verify_phase5b_5_needle.py | ❌ (1 run each) | already labeled "measured" — fine; R3 strengthens it |
| 6.2 | `2.01× cuda blocks at same memory budget` | M | PHASE5C_USAGE §"Memory accounting" | ❌ (1 run) | this is the 27,934 / 56,120 ratio — but the BRIEF page 3 says 13,967 / 28,060. Internal contradiction. | REVISE Page 3 OR Page 6 to match |
| 6.3 | `100K aggregate packed decodes` | Q | get_call_stats snapshots | aggregate, multiple cells | same as 3.5 | revise wording |
| 6.4 | `42.5 tok/s @ B=8 on Qwen-7B H100` | T | bench_phase6_batched_throughput.py | ❌ (1 run) | same as 3.12 | mark provisional |
| 6.5 | `Read-path preflight for CUDA Graphs (B-pre-1..4) COMPLETE` | engineering status | OPTION_B_PREFLIGHT.md | n/a | **KEEP** — engineering status, not a metric |

### Page 6 — Projected section

This section is properly labeled. No action needed.

### Page 7 — Business Case

| # | Claim | Cat | Evidence source | Disposition |
|---|---|---|---|---|
| 7.1 | `2× concurrent users per GPU at preserved quality on Qwen-7B (218× vs 109×)` | T/Q | restatement of 3.8 + 3.1 | **KEEP** if 3.8 and 3.1 hold |
| 7.2 | `Equivalent ratios projected for other models` | P | properly labeled projected | **KEEP** |
| 7.3 | `~3000 lines of carefully-tuned code` | engineering | uncontested | **KEEP** |

## Summary by disposition

| Disposition | Count | Highest-priority items |
|---|---|---|
| **KEEP** | 9 | Engineering/projection items already correctly labeled |
| **KEEP + add scope label** | 5 | Needle scope "≤1200 filler tokens" + "single run per model"; concurrency "from single startup log" |
| **REVISE wording** | 5 | 3.5 (100K), 3.9-3.10 (3/5 vs 3/6), 4.3 (cite), 6.2 (internal contradiction) |
| **REVISE substantively** | 3 | 1.1 fp8 needle, 3.6-3.7 cuda blocks, 4.2 KIVI 11-29% (or remove) |
| **REMOVE** | 0 | None required by Phase 8 retirement |

## Minimal GPU run set to make the brief partner-safe

Ordered by partner-safety impact. **No runs are recommended at this time** — the audit asks for review and approval before any GPU spend.

| ID | Run | Address | Cost | Why partner-safe |
|---|---|---|---|---|
| **R1** | fp8 needle on Qwen-7B (5 codes × 3 buckets, like the int4_protected run) | claim 1.1 | ~$0.05 | replaces an inferred-but-misframed number with a real measurement. Highest partner-safety value per dollar |
| **R3** | Replicate needle on all 4 models, 2 independent runs each | claims 1.3, 3.1-3.4, 6.1 | ~$0.30 | turns "single-run per model" into "2-of-2 replicated" — the audit-standard headline |
| **R5** | Re-bench three-way cuda blocks (bf16 / fp8 / int4_protected, Qwen-7B) | claims 3.6, 3.7, 6.2 | ~$0.05 | resolves the 13,967 vs 27,934 contradiction with a fresh measurement |
| **R7** | Replicate aggregate throughput at B=8 + per-seq latency, Qwen-7B, 180s wall | claims 3.11, 3.12, 6.4 | ~$0.10 | takes the headline TPS number from provisional to replicated-at-audit-standard |
| **R2** | (Optional) Route-B INT4-K-and-V needle at 16K context | claim 1.2, 4.2 | ~$0.10 | substantiates the KIVI competitive comparison with own measurement; alternative is to cite an external source |
| **R4** | Recount "100K decode calls" from existing logs + decide 3/5-vs-3/6 canonical | claims 3.5, 3.9, 3.10 | $0 (CPU) | wording fixes, no GPU |
| **R6** | Replicate 218× concurrency log line at 2 gpu_memory_utilization settings | claim 3.8 | ~$0.02 | strengthens a single-data-point claim |
| **R8** | Locate citation for TurboQuant W4A4 paper | claim 4.3 | $0 (web) | bibliographic |
| **R9** | Pin IoU evidence (Qwen-7B 11.1% vs Qwen-14B 2.6%) to script output | claim 4.6 | $0 (audit pass) | strengthens cross-scale claim |

### Recommended bundle

**Tier A (most partner-safety per dollar — total ~$0.50):** R1, R3, R5, R7. Resolves the misframed fp8 needle, the cuda-blocks contradiction, and converts the four 15/15s + 42.5 tok/s from single-run to 2-of-2 replicated.

**Tier B (optional, +~$0.12):** R2, R6. Closes the KIVI claim and strengthens the concurrency number.

**Tier C (CPU/free):** R4, R8, R9. Pure documentation cleanup.

**Total Tier A+B+C: ~$0.62, ~30 minutes of GPU pod time** to take the brief from "single-run claims with two inferred numbers" to "fully replicated, no inferred claims, scope-labeled."

## What I would NOT do

* Add new claims (e.g., long-context >1200 filler tokens needle). The
  brief is honest about being needle-only at v1; expanding the quality
  bar is v2 work per Page 5.
* Touch the Phase 8 / route-A / bridge story in the brief. None of it
  is currently claimed and adding it would require partner-credible
  replication that doesn't exist post-retirement.
* Remove any claims that are correctly labeled "projected" today.

## Final read

The brief is in much better shape than I expected pre-audit. The
methodology is honest, projections are labeled, and there's no
Phase 4 fallout to clean up. The remaining work is:

* **Two reframings / unsourced claims** (1.1 fp8 needle, 1.2/4.2
  KIVI 11-29%) that should be measured or revised before any
  partner conversation.
* **One internal inconsistency** (cuda blocks 13,967 vs 27,934)
  that should be reconciled.
* **One denominator drift** (3/5 vs 3/6) that should be picked.
* **Replication depth** — five claims that are single-run and would
  benefit from a second measurement.

These are all addressable for ~$0.50 in GPU time + an hour of
editing. Until that work lands, the brief should remain "review
copy, not partner-shareable." After Tier A, it is partner-safe.

## Awaiting approval

Per directive: **VC brief is unchanged.** No GPU runs initiated.
This audit is the deliverable for your review.

If you approve a particular tier of follow-up runs (or none), I'll
write up the run script for that bundle and stop. If you approve
the wording-only revisions (denominator pick, "100K" wording, etc.),
I'll prepare an edit-set against `INT4_PROTECTED_VC_BRIEF.md` and
stop before applying.
