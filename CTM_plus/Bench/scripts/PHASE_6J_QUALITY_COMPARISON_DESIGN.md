# Phase 6J — int4_protected vs int4_naive quality comparison (design)

> **Status:** DESIGN ONLY. No code changes, no bench runs until
> the cell definitions + metric thresholds in this doc are
> approved.
>
> **Trigger:** Phase 6H high-load bench (commit `62307be`) showed
> int4_protected does NOT deliver a measurable performance or
> capacity advantage over stock bf16 at the operating points
> tested. Combined with Phase 6G's sidecar-diet ceiling (~2.5 GB,
> insufficient to close the 5 GB HBM gap), the **performance**
> narrative for the protect-mask design is exhausted on this
> hardware/workload.
>
> The **quality** narrative is the unmeasured differentiator. The
> protect-mask design was originally motivated as a way to
> preserve int4's memory savings while reducing quality
> degradation vs naive per-channel int4. Phases 6E-6H all compared
> int4_protected to bf16 (apples-to-oranges: quantized vs not).
> The right comparison for the protect-mask CLAIM is int4_protected
> vs int4_naive — same quantization scheme, same backend, only
> the protect-mask toggled.
>
> **Goal:** Test the actual protect-mask claim. Does protected-K
> INT4 preserve long-context retrieval quality better than naive
> INT4 under the same serving conditions?
>
> **Acceptance (decision tree):**
> * **JUSTIFIED:** protected materially outperforms naive on
>   long-context retrieval AND approaches bf16 on quality. The
>   protect-mask design's research contribution is real; the
>   project ships as a long-context quality-preserving int4
>   backend (NOT a throughput accelerator).
> * **NOT_JUSTIFIED:** protected and naive are within noise of
>   each other on quality. The protect-mask adds complexity +
>   memory + perf overhead without quality benefit. **Close the
>   int4_protected line as a research artifact**, document
>   findings, end Phase 6.

## The three cells

| Cell | Backend | KV dtype | Protect mask | Purpose |
|---|---|---|---|---|
| **A — bf16** | stock vLLM | bf16 (auto) | n/a | quality ceiling |
| **B — int4_naive** | int4_protected backend | int4_protected (uint8 packed) | **disabled** (zero channels protected) | quality floor for the int4 quant scheme |
| **C — int4_protected** | int4_protected backend | int4_protected | **enabled** (calibrated n_protect=5) | the design under test |

**Critical constraint: B and C must differ only in the protect-mask
toggle.** Same int4 packing math, same kernel, same writer, same
flash_attn template, same group_size, same n_groups. Anything else
that differs is a confound.

### How "naive int4" is implemented

Three implementation paths, ranked by simplicity:

**Path 1 (RECOMMENDED): all-zeros protect-mask artifact**
* Create `qwen2_5_7b_protect_mask_naive.pt` — same shape as the
  calibrated mask but all entries zero.
* Run with `PROTECT_MASK_PATH=...naive.pt`.
* The writer's `_build_protect_tables` then sets `n_protect=max(1,0)=1`
  and `protected_d_per_head[h, 0] = 0` for every head. The "protected
  channel" is arbitrarily channel 0.
* Confound: channel 0 of every head is still preserved at bf16. This
  is NOT pure naive — it's 1-channel-protected.
* **Mitigation:** add a debug env flag `PHASE6J_NAIVE_FORCE_ZERO=1`
  that causes the read kernel to multiply k_packed_protect_bf16 by 0
  before attention (effectively disabling the protect contribution
  even though the sidecar is allocated). The naive cell uses both
  the all-zeros mask AND the force-zero flag. Pure naive.

**Path 2: dedicated `int4_naive` backend class**
* New backend `Int4NaiveAttentionImpl` that mirrors the int4_protected
  implementation but skips `k_protect_ext` allocation and the gather
  in the writer.
* Clean separation; cells B and C have no shared state.
* Cost: ~1-2 days to write + verify byte-eq against path 1.

**Path 3: kernel-level toggle**
* Pass `n_protect=0` through the flash_attn kernel. Requires kernel
  surgery to skip the protect-dim loop when `n_protect==0`.
* Cleanest semantically but highest implementation risk.

**Recommendation: Path 1 + force-zero flag for the bench; Path 2 if
the bench results justify the cleaner separation.**

## Metrics

Five quality metrics; the first two are load-bearing for the
acceptance decision.

### 1. Needle-in-haystack retrieval (PRIMARY)

**Method**

* Synthetic long context: `N`-sentence "haystack" of neutral
  filler text.
* Inject one needle sentence at depth `d ∈ {10%, 25%, 50%, 75%, 90%}`
  of the haystack.
* Needle template: `"Hidden in this document: the secret code is
  {NEEDLE_VALUE}."` where `NEEDLE_VALUE` is a unique 6-character
  alphanumeric token (e.g., `HORIZ4`). Five distinct needles per
  context length to avoid one-shot memorization across the sweep.
* Question at the end: `"What is the secret code mentioned in
  the document?"`
* Generate up to `max_tokens=32` with greedy decode (`temperature=0`).
* **Score per item**: 1.0 if output exact-contains `NEEDLE_VALUE`;
  0.5 if output contains the first 3 characters of the needle (partial
  recall); 0.0 otherwise.

**Sweep**

* `max_model_len ∈ {8192, 16384, 32768}`.
* `depth ∈ {10%, 25%, 50%, 75%, 90%}`.
* `needle_index ∈ {0, 1, 2, 3, 4}` — 5 unique needles per (mml, depth).
* Total: 3 mmls × 5 depths × 5 needles = **75 test items per cell**.
  Across 3 cells = **225 generations**.

**Acceptance thresholds**

Let `acc(cell, mml)` = mean needle score across all (depth, needle)
combinations at that mml. Then:

* **JUSTIFIED**: at `mml ∈ {16K, 32K}`, `acc(protected) ≥ 0.7` AND
  `acc(naive) ≤ acc(protected) − 0.20`. The 20-point gap rules
  out within-noise effects (each (depth, needle) is a discrete 0/0.5/1
  score over 25 items per mml; the standard error is ~10 points).
* **PARTIAL**: protected beats naive by 0.10-0.20. Inconclusive;
  recommend re-running with more needles per (mml, depth) for
  tighter SE.
* **NOT_JUSTIFIED**: `acc(protected) − acc(naive) ≤ 0.10` at every
  mml. Protect-mask doesn't help long-context retrieval.

### 2. Token agreement with bf16 (PRIMARY)

**Method**

* Take `N=20` fixed prompts (mix of factual Q&A, summarization,
  code completion — drawn from a held-out set).
* For each prompt and cell, greedy-decode 32 tokens.
* **Score per (prompt, cell, step)**: 1 if cell's top-1 token matches
  bf16's top-1 token at that step; 0 otherwise.
* Report **mean agreement** per cell across all (prompt, step) pairs.

**Acceptance thresholds**

* **JUSTIFIED**: at `mml=16K`, `agreement(protected) ≥ 0.85` AND
  `agreement(protected) − agreement(naive) ≥ 0.10`. Protected
  produces same-token-as-bf16 at least 85% of the time, with a
  10-point margin over naive.
* **NOT_JUSTIFIED**: protected and naive within 5 points of each
  other. Protect-mask not driving token-level agreement.

### 3. Decode collapse / repetition (SECONDARY)

**Method**

* On the needle-in-haystack outputs (already generated for metric 1),
  compute:
  * **Trigram repetition rate**: fraction of generated 3-grams that
    appear more than once in the output.
  * **Distinct-token ratio**: `len(set(tokens)) / len(tokens)`.
  * **Longest identical run**: max consecutive identical tokens.
* Aggregate per cell.

**Acceptance thresholds (informational)**

* protected's collapse metrics should be in line with bf16's.
* naive's collapse metrics should be notably worse if naive
  quantization is degrading the model's coherence.

Not a hard gate; this is a diagnostic to characterize HOW int4
degrades when it does.

### 4. Perplexity on a held-out slice (SECONDARY)

**Method**

* Use a small held-out corpus (e.g., 100 short sequences from
  WikiText-2 validation, or a custom set if WikiText isn't in
  the pod's data path).
* For each sequence, compute log-likelihood under each cell's
  model.
* Report mean perplexity per cell.

**Acceptance thresholds (informational)**

* protected perplexity should be within 5% of bf16's.
* naive perplexity expected to be 10-30% higher than bf16's.
* Gap between protected and naive is the protect-mask's
  per-token quality contribution.

Not a hard gate; complements 1 and 2.

### 5. lm-eval-harness slice (OPTIONAL, if installed)

**Method**

* If `lm-eval` is available in the pod environment, run a small
  subset of tasks: `piqa`, `hellaswag`, `arc_easy` — limit to
  100 samples per task for runtime.
* Compare accuracy per cell.

**Acceptance thresholds (informational)**

* Same direction: protected ≈ bf16 ≈ naive on short-context tasks
  (these benchmarks are mostly <2K context; int4 quant has minimal
  impact). Goal here is sanity check, not differentiation.

If long-context benchmarks like `longbench` or `ruler` are
available, those are more informative — defer to the runtime
inventory.

### Throughput + HBM (TERTIARY)

Captured from the bench harness for diagnostic purposes only. Not
load-bearing; serves to confirm cells are running correctly. Expected:

* A (bf16): fastest, lowest HBM.
* B (int4_naive): comparable to int4_protected on throughput; lower
  HBM by ~1 GB (no k_protect_ext if Path 2; same as protected if Path 1).
* C (int4_protected): per Phase 6E/6G/6H data.

## Bench harness scaffold

New script: `bench_phase6j_quality_gpu.py`. Borrows the
subprocess-per-cell pattern from Phase 6H but each subprocess runs
a multi-prompt evaluation rather than a saturation burst.

```
Per subprocess (cell, mml):
  1. Load LLM with the cell's config + appropriate
     PROTECT_MASK_PATH + (if naive) PHASE6J_NAIVE_FORCE_ZERO=1.
  2. Run needle-in-haystack sweep (5 depths × 5 needles).
  3. Run token-agreement sweep (20 fixed prompts; bf16 outputs
     are pre-computed in the bf16 subprocess and stored to disk;
     int4 cells read them for comparison).
  4. Compute decode-collapse + perplexity on the gathered outputs.
  5. Optional: run lm-eval slice.
  6. Write per-cell JSON.

Driver aggregates 3 cells × 3 mmls = 9 JSONs:
  - Per-mml score tables for all 5 metrics.
  - Verdict per metric + overall acceptance call.
  - Findings doc skeleton with the measured numbers.
```

## Sample evaluation files (deliverables for implementation phase)

1. `needle_haystack_corpus.json` — 25 fixed (depth, needle) items
   per mml. Frozen at first run so all three cells see identical
   inputs.
2. `token_agreement_prompts.txt` — 20 fixed prompts. Drawn from
   held-out data to avoid memorization confound.
3. `perplexity_corpus.json` — 100 short sequences. Held-out.
4. `protect_mask_naive.pt` — all-zeros version of the calibrated
   mask, for the int4_naive cell.

## Decision tree (full)

```
Run all 3 cells, 5 metrics, 3 mmls.

For each primary metric (needle-in-haystack, token-agreement):
  Compute (protected - naive) gap at mml ∈ {16K, 32K}.

If BOTH primary metrics show JUSTIFIED gap (>= 0.20 / 0.10):
  → Verdict: PROTECT_MASK_VALIDATED
  Project framing: "long-context quality-preserving int4 backend".
  Action: write findings doc; begin VC brief draft with quality
          narrative (NOT throughput); document throughput cost
          as acceptable trade-off for the quality preservation.

If exactly ONE primary metric shows JUSTIFIED:
  → Verdict: MIXED
  Action: investigate WHY one metric agrees and the other doesn't.
          Likely calibration issue or metric sensitivity. Re-run
          with adjusted thresholds before deciding.

If NEITHER primary metric shows JUSTIFIED (gaps within 0.10):
  → Verdict: PROTECT_MASK_NOT_VALIDATED
  Action: CLOSE the int4_protected line as research artifact.
          Document findings:
          - Phase 6E: byte-eq fusion landed but throughput parity
            didn't.
          - Phase 6G: sidecar diet has a ceiling.
          - Phase 6H: high-load capacity advantage unmeasurable.
          - Phase 6J: quality advantage absent.
          Total: ~6 weeks of engineering. Negative result is
          still a result.
```

## Effort estimate

| Step | Work | Time |
|---|---|---|
| Create all-zeros protect mask artifact + verify | Calibration + 1-shot check | 0.5 day |
| Add `PHASE6J_NAIVE_FORCE_ZERO=1` env flag in flash_attn read | Kernel code edit + byte-eq A/B | 0.5 day |
| Bench scaffold (`bench_phase6j_quality_gpu.py`) | Python (~600 LOC) | 1 day |
| Frozen evaluation corpora (4 files above) | Data prep | 0.5 day |
| First run + interpretation | GPU bench (~3 mmls × 3 cells × ~10min ≈ 1.5h) + analysis | 0.5 day |
| Findings doc (`PHASE_6J_QUALITY_FINDINGS.md`) | Writing | 0.5 day |
| **Total** | | **~3.5 days** |

This is the SMALLEST workstream that could produce a definitive
verdict on the protect-mask claim. Worth doing before closing the
project line.

## Risks

1. **The all-zeros mask isn't pure naive**: even with Path 1, the
   writer reserves k_protect_ext space (just unused). The Path 2
   dedicated `int4_naive` backend is cleaner but ~1-2 days more
   work. Mitigation: start with Path 1 + force-zero flag; if results
   are close, do Path 2 for a clean confirmation.

2. **Greedy decode at max_tokens=32 may not be enough to surface
   the needle even when the model "knows" it**: greedy generation
   could elaborate before stating the code. Mitigation: bump
   max_tokens to 64 if needle pass rate is suspiciously low for
   ALL cells including bf16.

3. **The protect-mask calibration was tuned at low context**:
   Phase 5B.0's protect-mask selection used short-context activation
   stats. At long context, the activations may differ enough that
   the calibrated channels aren't the right ones. If protected
   doesn't beat naive, this might be the cause rather than the
   protect-mask concept itself. Mitigation: try re-calibrating at
   long context if the first run shows protected ≈ naive.

4. **bf16 quality on this model + workload may already be limited**:
   Qwen2.5-7B-Instruct may not score very high on needle retrieval
   at 32K even at bf16 (long-context performance varies wildly by
   model). If bf16 itself scores <50% at 32K, the dynamic range
   for protected-vs-naive comparison is narrow. Mitigation: pre-run
   bf16-only at all mmls; if bf16's score is too low for clean
   differentiation, drop 32K from the sweep and focus on 8K/16K.

5. **lm-eval-harness may not be installed**: optional metric.
   Skip if unavailable.

## What this does NOT include

* Cross-family verification (Mistral, Llama). Defer to a Phase 6K
  if 6J validates the design and motivates broader testing.
* Multi-needle / NIAH-Long full benchmark. The 5-depth × 5-needle
  sweep here is a screening-grade test, not a production-grade
  benchmark. Sufficient for the binary go/no-go decision.
* Adversarial / corner-case prompts. Same reason.
* HBM/throughput re-measurement. Already characterized in
  Phases 6E-6H; secondary diagnostic only here.
* VC brief edits. Blocked until 6J verdict lands.

## Files (planned, NOT YET CREATED)

```
NEW:
  CTM_plus/Bench/scripts/bench_phase6j_quality_gpu.py
  CTM_plus/Bench/scripts/PHASE_6J_QUALITY_FINDINGS.md
  CTM_plus/Bench/data/needle_haystack_corpus_phase6j.json
  CTM_plus/Bench/data/token_agreement_prompts_phase6j.txt
  CTM_plus/Bench/data/perplexity_corpus_phase6j.json
  /workspace/dev/build-logs/qwen2_5_7b_protect_mask_naive.pt
                          (all-zeros companion to the calibrated
                          protect-mask artifact)

MODIFIED (small):
  CTM_plus/CUDA_int4_protected/csrc/fused_decode_write_k.cu
       — only if Path 2 (dedicated naive backend) is needed; Path 1
         requires no .cu changes.
  vllm-flash-attn-dev/.../int4_packed_kernel.h
       — only if Path 1 + force-zero flag is implemented at the
         kernel level (preferred over a Python read-side override).
```

## Cross-references

* `PHASE_6E_WRITER_FUSION_FINDINGS.md` — byte-eq + throughput.
* `PHASE_6G_SIDECAR_DIET_FINDINGS.md` — sidecar audit + diet ceiling.
* `PHASE_6H_HIGH_LOAD_FINDINGS.md` — high-B saturation test.
* This doc — quality A/B between int4 variants.

Phase 6E + 6G + 6H all asked "is int4_protected a better backend
than bf16?". Answer across all three: no, not on this
hardware/workload. **Phase 6J asks the right question instead:
"is int4_protected a better int4 than the obvious alternative?"**.
A YES here justifies the protect-mask line as a research
contribution; a NO closes it cleanly.
