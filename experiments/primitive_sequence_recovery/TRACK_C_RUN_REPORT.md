# Track C — Exploratory Semantic-Realizer Run Report

**EXPLORATORY. NOT Track B. NOT confirmatory. NOT evidence for `ONTOLOGICAL_SIGNAL`.** Allowed
labels only: `ENGINE_REALIZATION_SIGNAL` / `NO_SIGNAL` / `REALIZER_DEPENDENT` / `INCONCLUSIVE`.

## Run status: COMPLETED on RunPod (A100-80GB), English channel only

Executed `run_track_c_runpod.sh` on a real pod (all asset hosts reachable; asset acquired,
hash-pinned, scored offline). Machine: hostname `472e10a43793`, Linux 6.8, Python 3.12.3,
NVIDIA A100-SXM4-80GB (GPU unused — CPU scoring). All five test suites passed; manifest
NOT_READY; runner NOT_RUN; Stage A untouched (diff vs `2d42bf6` empty); `manifest.json`
unmodified.

## Asset (acquired + pinned)

| field | value |
|---|---|
| name | `glove-wiki-gigaword-50` (GloVe Wikipedia+Gigaword, dim 50) |
| source | gensim-data GitHub release |
| license | ODC-PDDL (permissive) |
| upstream md5 (cached .gz) | `c289bc5d7f2f02c6dc9f2f9b67641813` — **matches** known-good |
| **pinned sha256** (exported text) | `c7225dc6be8004c0451152074eb54ca7a0790e88614ac91384a7c67259736557` |
| vocab | 400,000 tokens |
| path (pod-local, not committed) | `/workspace/track_c_assets/glove-wiki-gigaword-50.txt` |

## Metrics (en_gloss; n_scram=1000, seed=0, K=8, N=107)

| metric | value | chance (K=8) | reading |
|---|---|---|---|
| coverage (en_gloss tokens) | **0.9803** (199/203) | — | good |
| MRR (real) | **0.3606** | **≈ 0.340** | barely above chance |
| MRR (scramble mean) | 0.3347 | ≈ 0.340 | at chance (expected) |
| **scramble delta** | **0.0259** | 0 | tiny |
| scramble_pct | **0.954** → one-sided p ≈ **0.046** | — | *just* clears 0.05 |
| Top-1 | 0.1495 | 0.125 | marginally above chance |
| **LABEL** | **`ENGINE_REALIZATION_SIGNAL`** | — | **knife-edge; see below** |

`ONTOLOGICAL_SIGNAL` was neither emitted nor emittable.

## Honest interpretation (do not overclaim)

- The gate emitted `ENGINE_REALIZATION_SIGNAL` only because delta (0.0259) just cleared the
  0.02 threshold **and** p (0.046) just cleared 0.05. It is **borderline**: a slightly
  different threshold, seed, distractor set, or composition would flip it to `NO_SIGNAL`.
- The real MRR (0.36) is **barely above the K=8 chance baseline (≈0.34)**, and the scramble
  mean (0.335) sits at chance. The entire effect is a ~0.026 MRR sliver.
- This is a **single realization (English), a single engine, no multiple-comparison control,
  N=107, class-agnostic (easy) distractors.** By design this is capped at the
  **`REALIZATION_ARTIFACT`** ceiling — English-only positives are never confirmatory.
- **Most parsimonious explanation:** English-gloss/embedding alignment + shared-source gloss
  authoring (F4), not intrinsic varṇa meaning. GloVe places the composed English gloss tokens
  slightly nearer the English meaning word than a scrambled gloss table does — exactly what a
  rendering artifact produces. This is **not** evidence for Symbol-U.
- **Bottom line:** a weak, borderline, English-only exploratory effect. Interesting enough to
  probe further (below), but it does **not** move the confirmatory question, and **Track B
  remains BLOCKED**.

## Semantic vs lexical floor (computed) + robustness (partial)

Lexical baselines on the same corpus/distractors (no asset needed; `diagnose_track_c.py`):

| realizer | MRR | Top-1 | scramble delta | one-sided p | MRR 95% CI (family bootstrap) | CI low > chance? |
|---|---|---|---|---|---|---|
| chance (K=8) | 0.340 | 0.125 | — | — | — | — |
| lexical Jaccard | 0.3478 | 0.140 | 0.0059 | ~0.14 (stable 0.12–0.16) | **[0.295, 0.404]** | **no** |
| order LCS | 0.3478 | 0.140 | 0.0059 | ~0.14 | [0.295, 0.404] | no |
| **GloVe semantic** | **0.3606** | 0.150 | **0.0259** | **~0.046** | *(run on pod — see below)* | *(expected: no)* |

**Semantic gain over lexical: +0.013 MRR** and ~4× the scramble delta; GloVe clears the gate,
lexical does not. So the effect has a small **semantic** component, not pure token overlap.

**But the decisive robustness point:** the family-bootstrap 95% CI on lexical MRR
**[0.295, 0.404]** already **straddles chance (0.340)** — its width (~±0.05) is **about twice
the GloVe delta (0.026)**. That means the result is fragile to *which words* populate the
corpus (N=107), independent of the scramble null. The scramble-p (0.046) only says "real beats
random *assignments of the same glosses*"; the bootstrap CI says "MRR_real is *not* robustly
distinguishable from chance given corpus sampling." **Expectation: GloVe's bootstrap CI will
also include chance** → the sliver is not robust. Confirm on the pod:

```bash
python3 experiments/primitive_sequence_recovery/diagnose_track_c.py \
  --glove /workspace/track_c_assets/glove-wiki-gigaword-50.txt \
  --sha c7225dc6be8004c0451152074eb54ca7a0790e88614ac91384a7c67259736557 \
  --n_scram 1000 --boot 2000
```
If `static_embedding_glove.ci_low_above_chance` is **false**, the honest verdict is: an
English-only effect that clears the pre-registered gate but is **not robust** to corpus
resampling — consistent with a rendering/shared-source artifact, not a stable signal.

## Robustness checks still open (all exploratory, on-pod)

1. **Bootstrap CI on delta** (word-level, family-aware) — is 0.026 distinguishable from 0?
2. **Multiple seeds** for the scramble null — is p stable around 0.05 or does it wander below/above?
3. **Beat the lexical baselines?** Compare GloVe MRR vs Phase-1 Jaccard and Phase-2 LCS on the
   same corpus/distractors. If semantic ≈ lexical, there is **no semantic gain** — the whole
   point of Track C.
4. **Order-scramble null** — mean-pool is order-insensitive, so this should be ~null; a
   sanity check that the tiny signal is not order-dependent.
5. **Leakage probe** — can GloVe recover the meaning from the *bare word* or from unrelated
   tokens? Quantify how much of the 0.026 is gloss↔meaning token proximity vs assignment.
6. **Hard-negative distractors** — re-freeze class-matched negatives; the current easy
   distractors inflate MRR and make the sliver look larger than it is.

## Channels

- `en_gloss`: **run** (result above).
- `sa_term`: **skipped** — no offline Sanskrit vectors were acquired (fastText host blocked).
- `concept_id`: **skipped** — no non-circular concept resolver exists (`CONCEPT_RESOLVER_
  CIRCULARITY_AUDIT.md`). Cross-realization invariance therefore cannot be assessed.

## Reminder — Track B remains BLOCKED

This is Track C (exploratory). The English-only, borderline effect above does **not** unblock
Track B, which requires an independent, non-circular concept channel that does not exist. No
output may be reported as `ONTOLOGICAL_SIGNAL`. `manifest.json` remains NOT_READY; the runner
remains NOT_RUN; no `manifest_v2`, no READY, no concept resolver; Stage A untouched.

> structure, not validated meaning.
