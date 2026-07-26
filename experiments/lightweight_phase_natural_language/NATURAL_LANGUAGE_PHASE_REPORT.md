# Natural-Language Phase Validation — Report (v1.6)

**Question A:** Does frozen Phase improve natural-language evidence use beyond a
sliding window? **Measured by B − A.**

All numbers below are from the committed run: `results/aggregate.json`,
`results/tables.md`, `results/isolated_transfer.json`, `results/ablations.json`,
`results/resources.json`. 3 seeds, CPU-only, early-stopping (best validation
answer-accuracy checkpoint).

## Frozen baseline

Git commit `6e2942927f930cdfd789cd10b555d72669a55ba3`, 98/98 lightweight_phase
tests pass, FREEZE OK, torch 2.13.0, CPU 4-core / 15 GiB. The frozen
`LightweightPhaseAttention` is used **unmodified** (exact constructor config in
`EXPERIMENT_MANIFEST.json`: embed 96, heads 4, head_dim 24, bounded_phase True,
a=σ (floor 0, scale 1), normalizer clamp 0.1 detached, decay none, aux_scale 1.0,
complex64/float32 state).

## Arm definitions (same backbone, protected additive fusion)

| arm | local | Phase | slots |
|---|---|---|---|
| A | ✓ | | |
| B | ✓ | ✓ (frozen) | |
| C | ✓ | ✓ (frozen) | ✓ |
| C-no-Phase | ✓ | | ✓ |

## No-quadratic proof

Every arm runs under the frozen shape audit (raises on any two-sequence-axis
tensor) — none triggered. Measured peak intermediate element count is **exactly
96·N** (N=48→4608, 64→6144, 96→9216): linear, not quadratic. Recurrent state is
bounded and constant in N: Phase 384 numel/seq (O(D)), slots 6272 numel/seq
(O(M·D)). Runtime scaling exponent: A 0.07, B 0.49, C 1.01, C-no-Phase 1.02
(≤ linear).

## Parameter/compute fairness

Same tokenizer, corpus generator, optimizer (Adam), schedule, batch size, seeds,
dropout (0), init, hardware, eval sets. Capability paths add parameters (this is
inherent and reported, not hidden): A 258,626 · B 369,604 · C 443,912 ·
C-no-Phase 332,934. Same-backbone comparison is primary; the added parameters are
the mechanism under test.

## Language-model quality (Task 1)

All arms reach next-token accuracy 1.00 / perplexity ≈ 1.0 on the prose control —
**no arm degrades ordinary language modeling** to gain task accuracy. Caveat: the
synthetic enterprise prose is templated and trivially predictable, so this is a
*non-degradation* check, not a strong language-quality benchmark.

## Distant natural-language retrieval and the B − A result

Accuracy (mean ± std over 3 seeds), and the decisive **B − A** delta:

| task | A | B | **B − A** |
|---|---|---|---|
| distant_fact | 0.03±0.03 | 0.07±0.03 | **+0.03** |
| multi_candidate | 0.00±0.00 | 0.03±0.03 | +0.03 |
| entity_binding | 0.04±0.02 | 0.03±0.00 | −0.01 |
| source_attr | 0.03±0.00 | 0.02±0.03 | −0.01 |
| supersession | 0.06±0.03 | 0.06±0.02 | −0.00 |
| insufficient (abstain) | 0.96±0.06 | 1.00±0.00 | +0.04 |
| lm (next-token) | 1.00 | 1.00 | 0.00 |

**B ≈ A on every capability.** Frozen Phase adds no measurable natural-language
evidence capability beyond the sliding window in the joint multitask setting.

### Isolated single-task transfer (no multitask interference)

Training A vs B on distant-recall alone (800 steps, 3 seeds):

| seed | A | B |
|---|---|---|
| 0 | 0.03 | 0.05 |
| 1 | 0.05 | 0.10 |
| 2 | 0.07 | 0.35 |
| **mean** | **0.05** | **0.17** |

Isolated **B − A = +0.12**, weak and seed-dependent (one seed +0.28, two ≈ +0.03).
(Note: an earlier exploratory probe with a *shorter* context and *single-token*
entities reached B≈0.77; the transfer is fragile to context length, answer-vocab
size, and entity tokenization — it does not hold at the study configuration.)

## Causal Phase ablations (load-bearing test)

Corrupting Phase in arm B changes **nothing** (all values identical to baseline):

| ablation | distant | binding | source |
|---|---|---|---|
| baseline | 0.07 | 0.00 | 0.03 |
| Phase disabled | 0.07 | 0.00 | 0.03 |
| Phase weights randomized | 0.07 | 0.00 | 0.03 |
| Phase capacity reduced | 0.07 | 0.00 | 0.03 |

**Phase is not load-bearing in B** — its (chance-level) behavior does not depend on
Phase at all. (Phase ablations inside C are covered in `PHASE_BINDING_REPORT.md`;
same conclusion.)

## Resource analysis (per-arm, N=256)

| arm | params | phase-state/seq | slot-state/seq | latency | tok/s | scaling exp |
|---|---|---|---|---|---|---|
| A | 258,626 | 0 | 0 | 2.9 ms | 89,294 | 0.07 |
| B | 369,604 | 384 (O(D)) | 0 | 6.4 ms | 39,943 | 0.49 |
| C | 443,912 | 384 | 6272 (O(M·D)) | 248 ms | 1,032 | 1.01 |
| C-no-Phase | 332,934 | 0 | 6272 | 244 ms | 1,049 | 1.02 |

## Findings, separated

- **Implemented:** 7 NL task families; A/B/C/C-no-Phase from frozen modules;
  leakage-controlled splits; early-stopping; no-quadratic + resource + ablation
  harnesses.
- **Tested:** no-quadratic invariant (linear peak numel; bounded state); 3-seed
  accuracy; isolated transfer; Phase ablations.
- **Demonstrated:** B ≈ A on all NL tasks; Phase ablation-neutral in B (and C);
  isolated B−A weak (+0.12) and seed-dependent; no LM-quality regression.
- **Unsupported (at tested scale):** frozen Phase improving NL evidence use
  beyond the sliding window. The clean controlled-token recall result does **not**
  transfer to natural-language multitask evidence here.
- **Deferred:** larger models / longer training; real (non-templated) corpora;
  context lengths ≥ 1K–8K (slot Python loop makes this slow on CPU); full
  contradiction / temporal / multi-hop task batteries at scale.

## Verdict (Question A)

**Phase transfer to natural-language long-context evidence: NOT SUPPORTED /
FALSIFIED AT TESTED SCALE** in the joint multitask setting (B ≈ A; Phase
ablation-neutral). Isolated transfer is at best **PROVISIONALLY SUPPORTED** and
weak (+0.12, one of three seeds). No universal claim is made from this
micro-scale result.
