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

## Schema validator + readiness gate

Real runs are gated by a **frozen bundle** under `frozen/` that must validate before any
execution. `schemas/*.schema.json` are the JSON Schemas (per `SCHEMA_SPECIFICATION.md`);
`manifest.py` is a dependency-free validator + readiness gate:

- **schema validation** — each artifact (`assignment`, ≥3 `realization_*`, `word_list`,
  `meaning_reference`, `distractors`, `realizer`, `manifest`) is checked against its schema,
  plus semantic rules (assignment must be **semantics-free**; realizer must be
  `deterministic` **and** `offline`; no duplicate atoms/varṇas/words).
- **hash verification** — every artifact's sha256 must match the manifest.
- **referential integrity** — realization `atom_content` is total over the assignment atoms;
  every word has a meaning covering every realization; distractor candidates resolve.
- **independence** — the manifest must declare an independence basis for **every**
  realization pair (English is never privileged).
- `check_readiness(frozen_dir)` returns `status` (`READY`/`NOT_READY`), `reasons`,
  `hashes_ok`, `schema_ok`, `references_ok`, `realization_count`,
  `realization_independence_ok`.

**Why `READY` is not a result.** `READY` means the *inputs* are frozen, well-formed, and
mutually consistent — it says nothing about whether the varṇa assignment carries any signal.
No scores are computed anywhere in this layer.

**Why the runner still returns `NOT_RUN`.** `run_primitive_recovery.py` consults the gate
and returns `NOT_RUN` when `NOT_READY` — and **also** when `READY`, because real experiment
execution is intentionally not implemented in this validation-only layer. It computes no
scores, loads no embeddings, calls no network/LLM, and writes no result artifacts.

## Files

| file | role |
|---|---|
| `canonical.py` | opaque-atom canonical sequence; relabeling-invariant opaque similarity |
| `realization.py` | `Realization` interface; synthetic signal / noise / english realizations |
| `scoring.py` | MRR ranking/retrieval; assignment-scramble null; `delta_j`; `score_opaque` guard |
| `decision.py` | per-realization verdict + cross-realization decision helper |
| `schemas/*.schema.json` | JSON Schemas for every frozen artifact + the manifest |
| `manifest.py` | schema validator + hash verify + referential integrity + `check_readiness` |
| `run_primitive_recovery.py` | guarded runner → **NOT_RUN** (gate-aware; still NOT_RUN even when READY) |
| `test_primitive_sequence_recovery.py` | synthetic scaffold tests |
| `test_manifest_gate.py` | synthetic readiness-gate tests (temp frozen dirs) |

## Why the synthetic tests do NOT validate the theory

The "signal" realizations here are **planted** (meaning vectors are constructed so the real
assignment recovers them). This proves the **machinery** — MRR, the scramble null, the
cross-realization decision logic — behaves correctly. It says **nothing** about whether the real
varṇa→vṛtti table carries any signal; that is an empirical question requiring a frozen, approved
lexicon and real realizations, which this scaffold deliberately does not run.

## Run

```bash
python3 experiments/primitive_sequence_recovery/test_primitive_sequence_recovery.py  # scaffold checks
python3 experiments/primitive_sequence_recovery/test_manifest_gate.py                # readiness-gate checks
python3 experiments/primitive_sequence_recovery/run_primitive_recovery.py            # NOT_RUN
```

> structure, not validated meaning.
