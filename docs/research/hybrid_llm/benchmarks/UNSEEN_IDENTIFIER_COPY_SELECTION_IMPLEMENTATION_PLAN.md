# Unseen-identifier copy/selection — implementation plan (DRAFT, documentation-only)

**Documentation-only. No code is written, no dataset generated, no model trained, no seed consumed,
no execution authorized.** This plan makes the future implementation precise, reviewable, and
bounded. It authorizes nothing beyond what the companion
`…_IMPLEMENTATION_AUTHORIZATION.md` states.

Always preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `E1_TEMPORAL_TRANSFER_PARTIAL`
· `KDA_VALIDATION_BLOCKED`.

## Implementation scope (allowed / forbidden)
**May include only:** (1) deterministic identifier-pool generation; (2) deterministic C1–C8 example
generation; (3) the one frozen representation serializer; (4) exact-output parser; (5) task metrics;
(6) shortcut baselines; (7) deterministic model-training harness using the **exact frozen recipe**;
(8) configuration and manifest generation; (9) hash/fingerprint utilities; (10) unit and integrity
tests; (11) CI checks; (12) future command interfaces that remain **unexecuted**.

**Must not include:** constrained decoding · candidate-index output · candidate-ranking objective ·
pointer/copy head · curriculum intervention · capacity increase · tokenizer change · BindingSlots ·
E1 memory · relational reader · pretrained model · multi-hop task · temporal task · enterprise-schema
task · production integration.

## Decision 1 — Implementation package location
The frozen recipe already exists and is merged in `experiments/single_hop_typed_vs_prose/`. The new
diagnostic **reuses it by import** and does **not** copy or re-implement it. Chosen structure: a
**sibling package** `experiments/unseen_identifier_copy_selection/` under the same research
namespace, importing the frozen model / tokenizer / trainer / config / execution-gate directly.

Reusable components (imported, **never modified or copied**):
| Concern | Reused from (merged) |
|---|---|
| Model + `build_model` + `parameter_digest` | `single_hop_typed_vs_prose/model.py` (`StructuredOutputModel`) |
| Tokenizer | `single_hop_typed_vs_prose/tokenizer.py` (`LexicalTokenizer`, vocab 200) |
| Trainer | `single_hop_typed_vs_prose/trainer.py` (`train_in_memory`, `deterministic_batch_order`) |
| Frozen recipe | `single_hop_typed_vs_prose/config.py` (`FROZEN_MODEL_RECIPE`, `FROZEN_TRAIN_RECIPE`) |
| Fail-closed seed gate | `single_hop_typed_vs_prose/execution.py` (`guard_seed`) pattern |

Rationale: smallest isolated implementation; **no new architecture abstraction**; the frozen 209,728-
parameter recipe is consumed unchanged. A sibling package keeps the new task/serializer/verdict code
from entangling with the completed typed-vs-prose benchmark while sharing the exact model.

## Decision 2 — Exact planned files
Only the files below may be added or modified by a future implementation. Any other file requires a
scoped authorization correction first.

| File | New/Reused | Purpose | Allowed | Forbidden | Depends on |
|---|---|---|---|---|---|
| `experiments/unseen_identifier_copy_selection/__init__.py` | new | bounded API surface | export pure builders/evaluators | no import side effects, no RNG, no run | stdlib |
| `…/config.py` | new | split counts, candidate counts, pool sizes, fixture-seed namespace, decode cap; **imports** frozen recipe | declarative constants | must not redefine/alter the frozen recipe | reused `config` |
| `…/identifiers.py` | new | deterministic identifier pools + collision/round-trip checks | generate opaque IDs, fail-closed checks | no label/shape leakage; no reserved-pool generation | reused `tokenizer` |
| `…/tasks.py` | new | C1–C8 example generation + metadata | deterministic construction | no constant-gold in primary; no final-pool generation | `identifiers`, `config` |
| `…/serializer.py` | new | the one frozen representation serializer | byte-identical templates | no serializer search, no candidate-index | `tasks` |
| `…/parser.py` | new | exact-output parser (7 categories) | classify output | no silent ID repair, no constrained decoding | stdlib |
| `…/metrics.py` | new | pure deterministic metric functions | compute per-split metrics | no verdict inference | `parser` |
| `…/verdict.py` | new | verdict engine (frozen precedence) | apply Decision-8 precedence | no new gates/scope | `metrics` |
| `…/shortcuts.py` | new | frozen shortcut baselines | compute chance + score | cannot satisfy a positive verdict | `tasks`, `parser` |
| `…/runner.py` | new | future CLI (unexecuted) | wire the pipeline; refuse reserved seeds without authorization token | no execution in this/next session; fail-closed | reused `trainer`, `model` |
| `…/manifest.py` | new | fingerprint/hash utilities + manifest | actual digest values | none | stdlib, hashlib |
| `tests/experiments/unseen_identifier_copy_selection/test_*.py` | new | unit + integrity tests (fixture seeds only) | assert contracts | no reserved-cohort generation | package |
| `.github/workflows/unseen-identifier-integrity.yml` | new | experiment-specific CI | unit/integrity checks only | no training, no cohort, no reserved seed | package |
| `docs/…/UNSEEN_IDENTIFIER_COPY_SELECTION_IMPLEMENTATION_AUDIT.md` | new (future) | implementation-integrity audit report | record audit | — | — |
| `docs/…/README.md` | reused | navigation | link new docs | — | — |

**Dependency direction:** `identifiers → tasks → serializer/parser → metrics → verdict`; `shortcuts`
consumes `tasks`+`parser`; `runner`/`manifest` sit at the top and import the frozen recipe. No cycle;
nothing in this package is imported by the frozen `single_hop_typed_vs_prose` package.

## Decision 3 — Identifier-pool implementation contract
`identifiers.py` must generate training / development / final / evidence / source / target
identifiers deterministically. Requirements:
- **fixed alphabet** (uppercase ASCII letters + digits) and **fixed length** (four characters,
  per the protocol lock);
- **deterministic** generation from a domain-separated seed; **collision-free** pools;
- **no** semantic prefixes and **no** task-correlated shape (opaque);
- **train / dev / final pools disjoint**; **evidence IDs from a distinct domain-separated pool**;
- **tokenizer round-trip verified** (each ID re-encodes/decodes exactly; character-visible, e.g. a
  four-character ID occupies four tokens);
- **domain-separated sub-seeds** for {identifier pools, dataset generation, initialization, batch
  order, perturbations, position allocation} — the exact derivation rule is fixed at implementation
  and mirrors the typed-vs-prose domain-separation discipline.

**Fail-closed checks (raise before any use):** empty/degenerate alphabet · length mismatch ·
collision detected · train∩final ≠ ∅ · evidence pool overlaps ID pools · tokenizer round-trip
mismatch · any label/position/answerability/seen-status/relation signal detectable from surface
form.

**Fixture seeds:** unit fixtures use the reserved testing namespace **`993000–993004`** (mechanically
verified 0 external mentions) — **never** 9070, 9071–9073, or 90760–90764. Implementation tests must
**not** partially generate any reserved cohort.

## Decision 4 — Dataset implementation contract
`tasks.py` exposes a deterministic generator per split (C1–C8) returning examples with metadata (as
applicable): task name · cohort · base seed · derived sub-seed · source ID · target ID · candidate
IDs · correct position · evidence ID · seen/unseen classification · tokenizer length · lexical-decoy
class · expected exact output · expected abstention state · canonical example hash.

Requirements:
- **balanced position allocation** (first/middle/last) and **balanced answerable/unanswerable**
  allocation where applicable;
- **deterministic candidate count** and **deterministic lexical-decoy construction**;
- **no constant-output leakage into the primary competence score** (C8 abstention reported
  separately, matching the protocol lock);
- **exact split counts frozen from the protocol** (fixed at implementation from the locked
  per-split counts);
- **no train/final identifier overlap**; **no final-pool generation during implementation** (final
  cohorts are generated only under a separate reserved-final execution authorization).

Every generator is a pure function of (split, cohort, seed); repeated calls are byte-identical.

## Decision 5 — Serializer and parser implementation contract
`serializer.py` implements **exactly** the merged protocol templates (`TASK = …`, `QUERY_SOURCE`,
`FACTS:`, `-> `, `| EVIDENCE = `, `ANSWER =`, `TASK = DIRECT_COPY`/`TARGET`, `TASK = MISSING_KEY`).
Requirements: **byte-identical** output under repeated generation · fixed newlines · fixed
capitalization · fixed whitespace · fixed fact ordering · fixed answer prefix · **no** optional
formatting · **no** serializer search · **no** candidate-index representation.

`parser.py` must classify each model output into exactly one category: exact-correct-ID ·
token-level-partial-match · malformed · wrong-in-context-ID · fabricated-out-of-context-ID ·
correct-abstention · false-abstention. **No post-processing may silently repair a malformed ID**;
**no constrained decoding may be added**. The parser is a pure function of (raw output, example
context).

## Decision 6 — Model / training implementation contract
The training harness **reuses the exact merged recipe by import** (`build_model`, `LexicalTokenizer`,
`train_in_memory`, `FROZEN_MODEL_RECIPE`, `FROZEN_TRAIN_RECIPE`). It names: model class
`StructuredOutputModel` (`SoftmaxTransformerLM`), wrapper/build path
`single_hop_typed_vs_prose.model.build_model`, tokenizer `LexicalTokenizer`, initialization
(`torch.manual_seed` under `fork_rng`), optimizer AdamW (3e-4, β 0.9/0.95, eps 1e-8, wd 0.01, clip
1.0), training loop `train_in_memory`, update count 2000, batch size 8, checkpoint policy (final
parameter digest), deterministic flags (no dropout; fixed batch order), device CPU / precision
float32.

**Mechanical assertions the implementation must include (fail-closed):**
- parameter count **== 209,728**;
- recipe source hashes **match** the frozen lock values (`config.py`, `tokenizer.py`, `model.py`,
  `trainer.py`);
- tokenizer behavior matches the lock (identifiers character-visible; round-trip exact);
- **no** new trainable module; **no** task-specific head; **no** copy/pointer/ranking component;
  **no** candidate-index output.

Training code may be written under a future merged authorization, but **no training command may be
executed** in this or the authorization-draft session. The bare-identifier grader reuses the existing
greedy decoder; any decode-length bound must be arm-neutral and unable to truncate a valid
identifier (pinned at implementation).

## Decision 7 — Metrics and verdict implementation contract
`metrics.py` provides **pure deterministic** functions: exact-sequence accuracy · token-level
accuracy · malformed rate · wrong-in-context-ID rate · fabricated-out-of-context-ID rate ·
abstention accuracy · false-answer rate · first/middle/last accuracy · lexical-decoy degradation ·
seen-ID accuracy · unseen-ID accuracy · seen−unseen gap · per-seed gate evaluation · 4-of-5
replication counts.

`verdict.py` implements the merged **verdict precedence exactly** (Decision 8 of the protocol lock:
first-match-wins total order — `PROTOCOL_VIOLATED` → `RESOURCE_BLOCKED` → copy/generalization base
(`GENERALIZATION_FAILED` / `COPY_CAPABILITY_NOT_FOUND`, with the copy-masks-selection rule) →
`SELECTION_FAILED` (`COPY_ONLY_PARTIAL` synonym) → `EVIDENCE_LOOKUP_FAILED` → `ABSTENTION_GATE_FAILED`
→ `CONFIRMED`). The verdict is computed **mechanically from metrics**, never inferred from report
prose.

**Required unit tests for every boundary:** exactly equal to threshold · one value below · one value
above · co-occurring failure modes · protocol violation overriding capability verdicts · resource
block · shortcut block · C1 failure masking C2 selection interpretation · C6-pass/C7-fail →
generalization failure · C6/C7-fail → copy-capability-not-found.

## Decision 8 — Shortcut implementation contract
`shortcuts.py` implements every frozen baseline (first/last/middle target · most-frequent target ·
lexical-similarity · prefix-match · character-overlap · source–target co-occurrence · seen-ID
frequency · constant-abstention · output-template leakage · task-label leakage). For each it computes
**task-specific chance**, the shortcut score, the competence-floor comparison, and a pass/fail status
(threshold chance + 0.05).

The **shortcut precheck runs before any reserved-final authorization record can be created**; a
shortcut failure must produce a **blocking artifact** and prevent final execution. The plan requires
tests proving that **final execution cannot proceed while shortcut status is unresolved** (the runner
refuses to enter the final phase unless a passing shortcut-precheck artifact exists).

## Decision 9 — Determinism and fingerprint contract
`manifest.py` records **actual digest values, not booleans** — at minimum: source hash · config hash
· tokenizer hash · identifier-pool hash · dataset hash · serializer hash · model-initialization hash
· batch-order hash · checkpoint/parameter hash · prediction hash · evaluator hash · environment
manifest hash. Requirements: **byte-identical dataset regeneration** · **byte-identical
serialization** · deterministic paired replay where applicable · **provenance labels** for any
audit-derived artifact (`AUDIT_DERIVED_FROM_UNCHANGED_ARTIFACT` / `AUDIT_REPLAY_DERIVED`) ·
**per-example traces** committed in evidence (or a protocol-approved equivalent). This closes the
aggregate-only and missing-fingerprint gaps observed in the typed-vs-prose benchmark: fingerprints
are computed and stored as values from the start, and per-example predictions are retained.

## Decision 10 — Test plan (fixture seeds only)
A complete frozen test matrix; **all tests use fixture-only seeds `993000–993004`**:
identifier-pool disjointness · collision rejection · tokenizer round-trip · character visibility ·
deterministic generation · deterministic serialization · exact C1–C8 construction · position
balance · lexical-decoy construction · seen/unseen separation · missing-key construction · **no
reserved-pool generation** · exact parser categories · metrics · verdict precedence (every boundary)
· shortcut baselines · parameter-count equality (== 209,728) · source-hash equality · **no forbidden
modules** (scan) · seed guards (reserved seeds refuse without an authorization token) · fingerprint
generation · manifest completeness · **CLI refusal without a future authorization token**.

The seed-guard and CLI-refusal tests assert the fail-closed posture: the runner/CLI must **raise**
when handed a reserved seed (9070 / 9071–9073 / 90760–90764) without the (future) execution
authorization token, so no accidental cohort can be generated by the test suite or CI.