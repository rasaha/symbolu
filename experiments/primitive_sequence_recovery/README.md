# experiments/primitive_sequence_recovery — realization-factored scaffold (synthetic only)

Machinery for the **realization-factored primitive-sequence recovery** test pre-registered in
`varna_lens/PREREG_PRIMITIVE_SEQUENCE_RECOVERY.md`, built on the ontology in
`varna_lens/CANONICAL_PRIMITIVE_REPRESENTATION.md`. **Scaffolding only:** synthetic fixtures,
synthetic tests, a guarded runner. **No real lexicon, no external embeddings, no LLM, no fit,
no result, no semantic claim.** Stage A is neither imported nor modified.

## Ontology vs realization (the split this scaffold enforces)

- **Ontology** = the **canonical primitive sequence**: an ordered tuple over **opaque atom IDs**
  (`canonical.py`). An atom is a bare `int` identity — no gloss, no vector, no coordinates.
- **Realization** = a layer `R_j` (`realization.py`) that maps opaque atoms to **content**
  (here: synthetic content vectors + a meaning encoder). English-gloss concatenation is **one**
  realization, not the ontology.

## Why the canonical opaque sequence cannot be scored directly

By the **relabeling-invariance theorem**, any function of the opaque sequence that is invariant
under renaming atoms — which includes every opaque sequence-similarity measure — gives the
**same** answer for the real assignment and any scrambled (relabeled) assignment
(`test_real_vs_scrambled_invisible_at_opaque_level`). So the real-vs-scrambled contrast, the
basis of falsifiability, is **invisible** on the opaque sequence. Scoring meanings therefore
**requires** attaching content, i.e. a realization (`score_opaque` raises;
`test_realization_required_for_scoring`).

## Why multiple realizations are required

Because content-attachment is a realization, a positive result under a **single** realization
(e.g. English) could be an artifact of that rendering. The confirmatory claim is
**cross-realization invariance**: the real assignment must beat scrambled under **every**
realization `R_j`. The decision helper (`decision.py`) enforces this:

| outcome across realizations | label |
|---|---|
| positive under **all** `R_j` | `ONTOLOGICAL_SIGNAL` |
| positive under **some but not all** | `REALIZATION_ARTIFACT` |
| positive under **none** | `NO_SIGNAL` |
| encoder disagreement within a realization | `REALIZER_DEPENDENT` |
| an inconclusive realization | `INCONCLUSIVE` |

English is never privileged: English-only positive → `REALIZATION_ARTIFACT`.

## Files

| file | role |
|---|---|
| `canonical.py` | opaque-atom canonical sequence; relabeling-invariant opaque similarity |
| `realization.py` | `Realization` interface; synthetic signal / noise / english realizations |
| `scoring.py` | MRR ranking/retrieval; assignment-scramble null; `delta_j`; `score_opaque` guard |
| `decision.py` | per-realization verdict + cross-realization decision helper |
| `run_primitive_recovery.py` | guarded runner → **NOT_RUN** (no frozen dataset; writes no artifacts) |
| `test_primitive_sequence_recovery.py` | synthetic tests (30 checks) |

## Why the synthetic tests do NOT validate the theory

The "signal" realizations here are **planted** (meaning vectors are constructed so the real
assignment recovers them). This proves the **machinery** — MRR, the scramble null, the
cross-realization decision logic — behaves correctly. It says **nothing** about whether the real
varṇa→vṛtti table carries any signal; that is an empirical question requiring a frozen, approved
lexicon and real realizations, which this scaffold deliberately does not run.

## Run

```bash
python3 experiments/primitive_sequence_recovery/test_primitive_sequence_recovery.py  # 30 checks
python3 experiments/primitive_sequence_recovery/run_primitive_recovery.py            # NOT_RUN
```

> structure, not validated meaning.
