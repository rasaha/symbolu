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