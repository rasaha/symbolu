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

For the recorded run the ontology, normalization rules, metric definitions, and baseline
configuration were frozen, and the eval inputs were content-hash locked. **However, eval
outputs were inspected during iterative engineering and debugging, and implementation
changes followed some observed evaluation failures.** Disclosed development changes
include:

- unit-level **co-occurrence gap handling** (detecting ≥2 entities with no predicate at the
  unit level rather than per-clause);
- **predicate-lexicon additions** (e.g. `depended on`, `authorizes`);
- **historical-dependency handling** for "previously … but now …" segments;
- cross-segment **subject inheritance** in coordinated clauses;
- **consolidation behavior** (the consolidation key that keeps different-value assertions
  apart so conflicts are not merged away);
- numeric **value extraction** used by `VALUE_CONFLICT` detection;
- **deterministic tie-breaking** and small **test-data corrections**.

These are ordinary iterative mechanism development, **not misconduct**. But because the
engineering loop saw eval behavior (gold labels stayed withheld from the code and the final
selection used dev only), the reported evaluation is a **locked *development* evaluation,
not a double-blind or interpreter-blind holdout.** No numeric result or the verdict changed
as a result of this disclosure.

## Placeholder for a future independent holdout

A genuinely independent confirmation would require a freshly authored evaluation set whose
outputs are never inspected during engineering, authored by someone other than the
implementer, plus (if a model-based interpreter is later added) a comparison against the
frozen deterministic baseline. These are future work, not part of this study.
