# B1.2 G(word) Implementation Plan — GO / STOP_NOW gate

## 1. Scope and non-rescue rule

A **plan / go-no-go decision only** on whether the `G(word)` dictionary-differential builder can be
implemented **word-agnostically and reproducibly**. No implementation, no models, no G outputs, no judging,
no scoring. Does **not** change or rescue B1.1, does **not** claim generation utility / ontology / Sanskrit
privilege / semantic truth, does **not** unblock Track B. B1.1 stays `RANDOM_OR_SCRAMBLED_MATCHES`; Track B
stays BLOCKED. **Structure, not validated meaning.**

## 2. Implementation feasibility question

**Can `G(word)` be built without hand-authored per-word prose?** Assessed per stage: the retrieval, synonym
selection, tiering, output-freezing, and audit stages are **deterministic and clearly word-agnostic**. The
one stage carrying genuine risk is **target-specific residual extraction** (shared-feature subtraction), and
the one cross-cutting risk is **stylistic comparability with V**. Both are **resolvable under restrictions**
(§10, §12) — so the answer is **yes, conditionally**, not an unqualified yes.

## 3. Proposed G builder pipeline (planned stages)

1. **Target word list input** — the frozen B1.2 word set.
2. **Part-of-speech locking** — pin the target sense's POS (WordNet synset id) per word.
3. **Dictionary/thesaurus retrieval** — pull target + candidate-neighbor definitions from a fixed, versioned
   source (WordNet recommended: offline, versioned, definitions + synsets + hypernyms).
4. **Synonym / near-neighbor selection (≥10)** — deterministic rule (synset members + hypernym siblings,
   top-k by a frozen metric), POS-matched.
5. **Definition normalization** — uniform cleaning (lowercase, strip examples, tokenize gloss) by fixed rule.
6. **Shared-feature extraction** — features common to target + neighbors (hypernym features + high-overlap
   terms), structured list.
7. **Target-specific residual extraction** — subtract shared features; retain distinguishing features
   (the risk stage — deterministic rule preferred, frozen-prompt LLM only if rules are too brittle).
8. **Output schema writing** — emit the frozen JSON (G-spec §9).
9. **Lexical audit** — feature-overlap checks, format/length checks, leakage scan (no varṇa/V/labels).
10. **Hash / provenance binding** — hash inputs + outputs; record source versions; bind under the B1.2
    manifest.

## 4. Required dependencies

- **Dictionary/thesaurus source:** WordNet (offline, versioned) as the primary; any secondary dictionary
  pinned by edition + hash.
- **WordNet** for synsets, hypernyms, path/Wu-Palmer distance (synonym selection + tiering).
- **Embedding model** (optional, named + revision-pinned) for neighbor ranking / tiering.
- **LLM** (optional, named + revision-pinned) **only** for residual extraction if rules are insufficient.
- **Frozen prompt** (if LLM used) — exact text hash-bound.
- **Deterministic decoding** — temperature 0 / greedy, fixed max tokens.
- **Source versioning** — every source pinned by version + retrieval date + hash.

## 5. Word-agnostic rules (anti-hand-tuning)

- **Same retrieval rule** for every word (same source, same query construction).
- **Same synonym-selection rule** for every word (same metric, same k, same POS filter).
- **Same extraction prompt/rule** for every word.
- **No per-word editing** after extraction — the residual is whatever the frozen procedure emits.
- **No replacement after viewing alignment scores** — inputs and outputs are frozen before any V↔G scoring.
- **All failures handled by predeclared fallback rules** (missing synset → drop word by rule; <10 neighbors →
  documented exclusion; malformed gloss → normalization fallback), never ad-hoc judgment.

## 6. Frozen-prompt LLM extraction policy (only if LLM used)

- **Same model** (revision-pinned) for all words; **same frozen prompt**; **temperature 0 / deterministic**;
  **JSON-schema output**.
- **No varṇa / V input**, **no B1.1 outputs**, **no arm labels** in the prompt or context.
- **No manual polishing** of the model's output.
- **Parser-failure policy declared** (schema-invalid → one bounded repair of the same class allowed, else the
  word is dropped by rule — mirroring the B1.1 judge parser discipline).
- **Reproducibility rule:** the **generated G outputs are frozen and hash-bound as the authoritative
  artifact**; downstream reproducibility rests on the frozen output, with the model+prompt recorded as
  provenance. If the model cannot be revision-pinned, the LLM step is **dropped** in favor of rule-only
  extraction (or STOP_NOW if rules can't carry it).

## 7. Human review policy

**Allowed** only for: checking malformed dictionary entries; applying **predeclared** inclusion/exclusion
rules; documenting exclusions. **Not allowed:** improving the residual prose; choosing synonyms that make V
look better; editing G after seeing any V alignment. Every human action is logged and rule-cited.

## 8. Tiering plan

Near / mid / far tiers assigned by **embedding and/or WordNet distance**, **frozen before scoring**,
**independent of V** (word–word distance only), with **no post-hoc reassignment**; divergent cases resolved
by pre-set rule or dropped.

## 9. G/V independence verification (planned proofs)

- **G logs contain no varṇa/V fields** — schema whitelist + a scan asserting absence of gloss-table/`read_op`/
  `core_*` content.
- **V logs contain no G fields** — no dictionary definition, synonym set, or `G(...)` present.
- **Separate hashes** — V artifacts and G artifacts hashed independently; the B1.2 manifest records both but
  the builders never cross-read.
- **Pipelines meet only at alignment scoring** — enforced by construction order (G and V produced in separate
  runs before any scoring step exists).

## 10. STOP_NOW checks (before implementation)

Stop if: dictionary source **cannot be fixed/versioned**; synonym selection **cannot be made word-agnostic**;
LLM extraction **cannot be made reproducible** and rules can't replace it; output **requires hand-polishing**;
**tiering cannot be frozen** independently of V; **G becomes stylistically incomparable to V**; **G uses V or
varṇa** information; or implementation **needs post-hoc judgment calls**. Any one → `STOP_NOW`.

## 11. Implementation deliverables if GO (future files — not created here)

- `run_b1_2_g_builder.py` — the pipeline (stdlib + pinned deps).
- `g_function_config.json` — sources, versions, selection metric/k, tiering thresholds, seeds.
- `g_extraction_prompt.txt` — frozen prompt (if LLM used).
- `g_outputs.jsonl` — frozen G records (the authoritative answer keys).
- `g_audit_report.md` / `.json` — lexical/format/leakage audit.
- `g_manifest.json` — hashes + provenance (folded into the joint B1.2 freeze).

## 12. Decision

```
DECISION: GO_WITH_RESTRICTIONS
```

`G(word)` **is implementable** word-agnostically and reproducibly, but **only under these restrictions**,
which require explicit adjudication before build:

- **R1 — Minimize the LLM footprint.** Prefer deterministic WordNet/rule extraction (Option A); invoke the
  frozen-prompt LLM (Option C) **only** for the residual step if rules are demonstrably too brittle, and only
  with a revision-pinned model.
- **R2 — Freeze outputs as authoritative.** Because LLM greedy decoding can drift across
  environments/versions, the **generated G outputs are frozen + hashed** as the artifact of record; the
  method is provenance. If the model can't be revision-pinned, drop the LLM step.
- **R3 — Joint V↔G rendering format (the fragile point).** V (varṇa-gloss prose) and G (dictionary features)
  must be rendered to a **shared, length/register-matched schema** frozen **together**, with a style-tell
  audit — this is an open design decision that must be adjudicated, not assumed.
- **R4 — Reproducibility acceptance test.** Re-running the builder on frozen inputs must reproduce frozen
  outputs by hash; if not (LLM nondeterminism), the frozen cached outputs are authoritative and this is
  documented.
- **R5 — Fixed, versioned dictionary source** (WordNet primary); unstable/online-only sources → STOP_NOW.

Unrestricted `GO_IMPLEMENTATION_PLAN_APPROVED` is **not** chosen because R3 (V↔G comparability) and R1/R2
(LLM reproducibility) are genuine open items whose resolution changes the build; rubber-stamping them would
understate real risk. `STOP_NOW_G_NOT_REPRODUCIBLE` is **not** chosen because deterministic fallbacks
(WordNet rule extraction, frozen outputs) make G reproducible in principle.

## 13. Final status block

```
document:                   B1.2 G-function IMPLEMENTATION PLAN / go-no-go (decision only; nothing built/run)
decision:                   GO_WITH_RESTRICTIONS (R1–R5 to be adjudicated before build)
G implementable:            YES, conditionally (deterministic core; LLM residual optional + restricted)
B1.1 verdict:               UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
LIMITED_GENERATION_UTILITY: NOT earned
Track B:                    BLOCKED
Track G / Track F:          RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
authorized to run:          NO — requires restriction adjudication, then build, then joint B1.2 freeze + prereg review
next gate:                  B1_2_G_FUNCTION_RESTRICTION_ADJUDICATION
```

**Structure, not validated meaning.** G is implementable under stated restrictions; the B1.1 verdict stands,
Track B remains BLOCKED, and B1.2 cannot run until the restrictions are adjudicated and a new freeze is
created.
