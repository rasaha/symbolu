# StoryGraph File Map & Artifact Classification

Gate **S1** support. Every StoryGraph artifact classified before any move. Roles:
`CANONICAL_SOURCE` · `CANONICAL_TEST` · `CANONICAL_SCHEMA` · `CANONICAL_DOCUMENTATION` ·
`PUBLIC_ADAPTER` · `COMPATIBILITY_LAYER` · `FIXTURE` · `EVALUATION_EVIDENCE` ·
`RESEARCH` · `DUPLICATE` · `DEPRECATED_CANDIDATE` · `UNRELATED`.

Old root: `cyber_security/composite_threat_detector/`.
New canonical root: `packages/capabilities/storygraph/`
(source under `src/ugence_storygraph/`, tests under `tests/`, docs under `docs/`).

## Core implementation — `composite_threat_detector/*.py` → `src/ugence_storygraph/*.py`

| File | Role | Target |
|---|---|---|
| `__init__.py` | CANONICAL_SOURCE (public surface) | `ugence_storygraph/__init__.py` (+ new `api.py`) |
| `analyzer.py` | CANONICAL_SOURCE (application) | same |
| `storygraph.py` | CANONICAL_SOURCE (matcher / domain) | same |
| `storyverdict.py` | CANONICAL_SOURCE (witness/verdict/proposed-action) | same |
| `matcher`* (semantics live in `storygraph.py`) | CANONICAL_SOURCE | same |
| `model.py`, `fragments.py`, `recipes.py`, `financial.py` | CANONICAL_SOURCE (domain) | same |
| `stories.py`, `legitimate.py`, `contradictions.py`, `benign.py`, `completion.py`, `narrative.py`, `purpose.py` | CANONICAL_SOURCE (domain) | same |
| `linkage.py`, `ordering.py`, `signals.py`, `governance.py`, `policy.py` | CANONICAL_SOURCE | same |
| `providers.py` | PUBLIC_ADAPTER (context providers / ports) | same |
| `evidence.py` | CANONICAL_SOURCE (advisory-evidence emitter) | same |
| `audit.py`, `durable_audit.py`, `ledger.py` | CANONICAL_SOURCE (evidence/persistence) | same |
| `canonical.py`, `timeutil.py` | CANONICAL_SOURCE (deterministic digest / time) | same |
| `story_bridge.py`, `replay.py` | CANONICAL_SOURCE (replay support) | same |
| `cli.py` | PUBLIC_ADAPTER (JSON CLI) | same (lazy `evaluation`/`demos` imports made package-relative) |
| `signals.py`/`purpose.py`/… | CANONICAL_SOURCE | same |

## Policy Pack — `composite_threat_detector/policypack/*` → `src/ugence_storygraph/policypack/*`

| File | Role |
|---|---|
| `compiler.py`, `schema.py`, `reference.py`, `lifecycle.py`, `business_form.py` | CANONICAL_SOURCE (policy) |
| `event_mapping.py`, `providers_mapping.py` | CANONICAL_SOURCE (policy) |
| `replay.py`, `replay_gates.py` | CANONICAL_SOURCE (replay) |
| `schemas/storypolicypack.schema.json` | CANONICAL_SCHEMA (ships as package data) |
| `fixtures/account_takeover_replay.json` | FIXTURE (ships as package data — reference replay input) |

## Replay intake — `replay_intake/*` → `src/ugence_storygraph/replay_intake/*`

| File | Role |
|---|---|
| `replay_record.schema.json` | CANONICAL_SCHEMA (ships) |
| `*.template.json`, `*.template.md`, `README.md`, `example_sanitized_record.json` | FIXTURE / CANONICAL_DOCUMENTATION (intake templates — ship) |

## Evaluation infrastructure — `evaluation/*` → `src/ugence_storygraph/evaluation/*`

| File | Role |
|---|---|
| `harness.py`, `benchmark.py`, `corpus.py`, `corpus_gen.py`, `readiness.py`, `review.py`, `review_sim.py`, `alerts.py`, `final_eval.py` | CANONICAL_SOURCE (evaluation infrastructure) |
| `freeze.py` | CANONICAL_SOURCE (freeze config + digests) |
| `evidence_chain.py` | CANONICAL_SOURCE (evidence-record governance; holds `APPROVED_EVIDENCE_PATHS`) |
| `story_corpus.py`, `story_corpus_v2.py` | CANONICAL_SOURCE (frozen corpora) |
| `prior_runs.py` | EVALUATION_EVIDENCE (RUN_1..RUN_3 official prior-run records — **preserved verbatim**) |
| `fixtures/k8s_replay_example.jsonl` | FIXTURE |
| `results/eval_results_template.json` | EVALUATION_EVIDENCE (template; no sealed record present) |

## Demos — `demos/*` → `src/ugence_storygraph/demos/*`

| File | Role |
|---|---|
| `scenarios.py`, `__init__.py` | CANONICAL_SOURCE (demo/example scenarios; also test input) |

## Tests — `tests/*` → `tests/` (co-located, canonical imports)

24 files → 289 tests. All **CANONICAL_TEST**. Classified by kind in
`STORYGRAPH_CANONICAL_PACKAGE_MIGRATION_REPORT.md` §test-migration
(unit / integration / contract / replay / evaluation). A new
`tests/compatibility/` group is **added** (legacy-import identity, digest stability,
authority, non-mutation, dependency, packaging).

## Documentation — `*.md` → `packages/capabilities/storygraph/docs/*`

| File | Role |
|---|---|
| `README.md` | CANONICAL_DOCUMENTATION (replaced at new root; original preserved in `docs/`) |
| `STORY_GRAPH_SPEC.md`, `STORY_GRAPH_PARTIAL_MATCH_SPEC.md`, `LINKAGE_SCHEMA.md`, `RECIPE_SCHEMA.md`, `ENTERPRISE_STORY_POLICY_PACK.md` | CANONICAL_DOCUMENTATION |
| `STORY_GRAPH_EVIDENCE_LEDGER.md`, `STORY_GRAPH_ADVERSARIAL_VALIDATION.md`, `STORY_GRAPH_PARTIAL_MATCH_VALIDATION.md`, `STORY_GRAPH_VERIFICATION_VALIDATION.md`, `STORY_GRAPH_FINAL_SPLIT_AUDIT.md`, `SANITIZED_ENTERPRISE_REPLAY_REPORT.md` | EVALUATION_EVIDENCE (validation/evidence records — **preserved verbatim**) |
| `MIGRATION_NOTES.md` | CANONICAL_DOCUMENTATION (historical; kept) |
| `conftest.py` | COMPATIBILITY_LAYER (root-run bootstrap) |

## Not StoryGraph / not moved

- Nothing in this directory is `RESEARCH`, `DUPLICATE`, `DEPRECATED_CANDIDATE`, or
  `UNRELATED`. The whole tree is the single canonical StoryGraph capability.
- No other capability is touched in this phase.
