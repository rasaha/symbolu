# TAP-E3 — Leakage Audit

## Enforced controls

- **Locked eval split** with a content-hash lock (`eval_inputs_hash`).
- **Gold-free public loader** — `loader.public_cases` exposes only
  `case_id / split / request_text / units`; relationship gold, expected conflicts/gaps,
  and dimension labels are never returned (a key whitelist assertion enforces this).
- **Dev/eval separation** — no case-id overlap; distinct request texts.
- **Corpus + units content hashes**, **ontology version freeze**
  (`tap-e3-ontology/1.0.0`), **schema version freeze** (`tap-e3-relationship/1.0.0`),
  **frozen-components hash** (extractor + metrics + gates + baselines), and an
  **experiment manifest** (`experiment_lock.json`).
- **No randomness** anywhere; output is byte-identical across runs (a test enforces this).
- **Dev-only configuration selection** — the selection rule never reads eval.

## What these controls do NOT guarantee (honest disclosure)

The eval split was **not** an untouched independent holdout. During iterative engineering
and debugging, eval outputs were inspected and the deterministic extractor and gap rules
were adjusted (e.g. unit-level co-occurrence detection, the `depended on` lexicon entry,
the consolidation key) while eval metrics were visible. Gold labels stayed withheld from
the code and the final selection used dev only, but the engineering loop saw eval
behavior. This is therefore a **locked development evaluation, not a double-blind or
interpreter-blind holdout.**

## Placeholder for a future independent holdout

A genuinely independent confirmation would require a freshly authored evaluation set whose
outputs are never inspected during engineering, authored by someone other than the
implementer, plus (if a model-based interpreter is later added) a comparison against the
frozen deterministic baseline. These are future work, not part of this study.
