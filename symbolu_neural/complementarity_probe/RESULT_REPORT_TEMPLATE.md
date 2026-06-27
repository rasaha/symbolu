# Complementarity Probe — Result Report

> Fill this in from a real run. The committed decision MUST come from the `hf`
> embedding backend. The `hashing` backend is pipeline-only and cannot support a
> verdict.

## Run metadata

| field | value |
|---|---|
| date | |
| embedding backend | `hf` / `hashing` |
| model name | e.g. `sentence-transformers/all-MiniLM-L6-v2` |
| E dim | |
| U dim | |
| seed(s) | |
| datasets | `data/synonyms.jsonl`, `data/sentences.jsonl` (or real STS/NLI) |
| command(s) | |

## Experiment 1 — Synonym invariance (no LLM)

| metric | value |
|---|---|
| invariance index (Symbol-U Vritti) | |
| permutation p-value | |
| phonological-null index | |
| n groups / n words | |

**Reading:** index ≈ 0 ⇒ synonyms scatter ⇒ `U` is phonological, not semantic
(FAIL). index ≫ 0, small p, and ≫ phonological-null ⇒ meaning-aligned (PASS).

## Experiment 2 — Incremental information (E vs E+U vs nulls)

| features | cv_acc | Δ vs E |
|---|---|---|
| E | | 0 |
| **E+U** | | |
| E+shuffled_U | | |
| E+random | | |
| E+surface | | |
| E+phonological | | |
| U_alone | | |

**Pass condition:** `E+U > E` AND `E+U >` every `E+null`.

## Verdict (circle one, per strategy memo §9)

- [ ] **STOP** — `U` fails invariance, or `E+U ≈ E` / ties nulls. Clean negative.
- [ ] **PIVOT** — `U` helps only phonological tasks or is explained by surface /
      known taxonomies. Refutes the semantic thesis; pivot to phonology.
- [ ] **CONTINUE** — invariant + `E+U` beats `E` and all nulls, replicated across
      models. Climb the hierarchy (causality → utility) before any deployment.

## Migration consequence

- [ ] Keep new path / delete older detector files
- [ ] Merge selected pieces
- [ ] Abandon new path

(Deletion of `clean_softmax/` detector files is gated on a real `hf` verdict
here — see `MIGRATION_NOTE.md`.)

## Notes / caveats

(seeds, dataset size, label quality, single-model caveat, anything that bounds
the conclusion.)
