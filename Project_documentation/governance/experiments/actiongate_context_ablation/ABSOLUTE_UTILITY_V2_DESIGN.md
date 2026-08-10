# ABSOLUTE_UTILITY_V2_DESIGN

How the V2 benchmark is built, what it measures, and exactly how it differs from V1.
V1 is immutable; V2 is additive (new modules, new fingerprint, new result path).

## Goal
V1 proved a *paired* result: protected compression preserves ActionGate decisions and does
not regress task accuracy *relative to the uncompressed context*. It could not report a
meaningful **absolute** utility number, because three tasks were unanswerable-from-context
or scored on brittle exact-match (see `TASK_SUITE_AUDIT_V2.md`). V2 repairs the suite so
absolute accuracy is measurable, then re-freezes.

## Modules (all new; V1 files untouched)
| module | role |
|---|---|
| `normalize_v2.py` | frozen, general, symmetric answer normalization + preregistered concept aliases |
| `scoring_v2.py` | deterministic scorers: text, bool, number, date, concept, field-level JSON, contains-all, format+value |
| `llm_tasks_v2.py` | V2 task suite (all answerable), ground truth from the frozen envelope, `derivable_from_context` checker, complete `OPERATION_MAP` |
| `real_llm_bench_v2.py` | `SYSTEM_V2`, budgets, arms, frozen thresholds, `_success` verdict + eligibility, report |
| `benchmark_v2.py` | V2 fingerprint manifest (component hashes → full V2 fingerprint) |

## Task families (all answerable from supplied context)
1. `factual_qa` — affected count (numeric).
2. `tool_selection` — tool.verb (header).
3. `tool_argument_generation` — request args as JSON (field-level).
4. `amount_extraction` — affected count as integer.
5. `approval_status` — approval presence + single/dual (field-level).
6. `policy_condition` — approved-sink allowlist recognition (bool).
7. `negation_exception` — "fully reversible at NO cost?" (bool; tests negation).
8. `rollback_simulation` — rollback present + simulation present + fidelity (field-level).
9. `scope_target` — target resource (header).
10. `reversibility` — reversible + cost (field-level).
11. `multi_hop_reasoning` — governing RULE supplied inline, derivable yes/no.
12. `envelope_field_extraction` — only supplied/derivable fields (tool, verb, target).
13. `instruction_following` — observable format requirement (lowercase, short) on a derivable value.
14. `summarization` — preserve tool/verb/target (normalized contains-all).
15. `operation_mapping` — internal enum WITH the complete mapping table supplied inline.

No task asks for a private internal value unless its mapping/rule is provided in the prompt
(families 11 and 15). Every expected answer is checked by `derivable_from_context` in the
test suite for all 77 contexts (653 tasks).

## Scoring design
- **Deterministic primary metrics only.** No LLM judge in any primary score.
- **Structured answers** → `fields_scorer`: each field's value is *isolated* by key (JSON
  parse, then `"name": value` fallback) so multi-field answers don't cross-contaminate
  (e.g. two booleans), then typed comparison (bool/number/date/text). Reports per-field hits.
- **Text answers** → frozen general normalization (Unicode NFKC, casefold, punctuation and
  whitespace normalization, underscore/hyphen/space equivalence, article removal).
- **Semantic equivalence** not covered by normalization → a finite, **preregistered** alias
  dictionary (`normalize_v2._CONCEPT_ALIASES`) mapping corpus phrasings to canonical
  concepts, applied identically to every arm. Aliases are derived from the corpus source
  text (recognized + paraphrased), never from any model output or V1 result.
- **Method-agnostic:** a scorer's only argument is the model text; it cannot see the arm.
- An optional LLM judge is permitted for **secondary diagnostics only** (frozen rubric,
  raw outputs retained, different model) and is not implemented as a primary metric here.

## Arms & budgets
Arms `original / structural_only / protected / protection_unaware` and budgets 20/30/40%
are byte-identical to V1 — reused from `real_llm_bench._surviving` / `._prompt` (the frozen
compressor). Only the tasks/prompt/scoring/verdict change.

## V1 → V2 differences (exact)
| aspect | V1 | V2 |
|---|---|---|
| benchmark id | (implicit V1 real-LLM harness) | `ACTIONGATE_REAL_LLM_ABSOLUTE_UTILITY_V2` |
| fingerprint | `sha256:ac4e0692…` | `sha256:4b947848…` (distinct) |
| task families | 8 (3 defective) | 15 (all answerable) |
| internal enum | asked without mapping (0%) | separate task with mapping supplied |
| evidence extraction | exact internal strings | concept aliases + normalization |
| structured scoring | contains-all (brittle) | field-level typed, key-isolated |
| verdict | GO / LIMITED_GO / STOP | ABSOLUTE_UTILITY_GO / LIMITED_GO / STOP / BENCHMARK_NOT_ELIGIBLE |
| eligibility gate | none | original ≥ 0.60 or `BENCHMARK_NOT_ELIGIBLE` |
| compressor / ActionGate / corpus / budgets | — | **unchanged** |

## Runner integration
`run_benchmark.py` is version-aware via `BENCHMARK_VERSION=v2`: it selects the V2 tasks,
`SYSTEM_V2`, task types, and fingerprint; stamps `benchmark_version` on every record and in
`run_config.json`; and the resume guard rejects any record whose `benchmark_version`, model
revision, prompt hash, or fingerprint disagrees — so V1 and V2 records can never mix.
Results go to a distinct run dir (`absolute_utility_v2_<model>`). See `collect_v2.py` for
the V2 verify → score → manifest path.

## Status
Frozen harness committed. **No V2 inference has been run.** To execute on RunPod see the
exact commands in `runpod/RUNPOD_ABSOLUTE_UTILITY_V2.md`.
