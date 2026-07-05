# B1.1 Non-Synonym Embedding Gate — REPORT (BLOCKED: dependency unavailable)

## 1. Scope and non-claims
Embedding-similarity diagnostic over the 32 non-deferred experimental counter-poles. NOT generation, NOT
scoring, NOT an LLM judge. Does not modify B1, change the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock
Track B (**BLOCKED**). No ontology / Sanskrit privilege / semantic-truth claim. **Structure, not validated
meaning.**

## 2. Frozen model and thresholds
- model_id (frozen): `sentence-transformers/all-MiniLM-L6-v2` · fallback (approval-only): `sentence-transformers/all-mpnet-base-v2`
- metric: cosine_over_L2_normalized_embeddings · thresholds: hard ≥ 0.88, soft 0.82–0.88, pass < 0.82
- **STATUS: model NOT loaded** — sentence_transformers not installed

## 3. Inputs and exclusions
- input: `b1_1_experimental_contrastive_lexicon_draft.json` (sha256 `b383a654d4b1c025bff86364ab7ab1b95cd6e9e4d729028cf123b36d0a4d986a`)
- evaluated scope: 32 non-deferred entries · excluded (deferred): ['Ra', 'Śa'] · vowels excluded

## 4. Exact duplicate check (no model needed — RAN)
- english_rendering duplicates: NONE
- functional_operation duplicates: NONE
- exact-duplicate result: **PASS (no exact duplicates)**

## 5. Pairwise similarity summary
**NOT COMPUTED** — embedding dependency unavailable (no fabricated scores).

## 6. Hard flags
NOT COMPUTED (dependency unavailable).

## 7. Soft flags
NOT COMPUTED (dependency unavailable).

## 8. Ra/Śa exclusion note
Ra (source_complex) and Śa (neutral_principle) carry deferred null counter-poles and are excluded from this
check. Before B1.1 freeze: either resolve their counter-poles and re-run over 34, or pre-register exclusion.

## 9. Human adjudication requirements
None yet — no flags computed. Adjudication applies once the embedding run completes.

## 10. Pass/fail gate status
**`BLOCKED_DEPENDENCY_UNAVAILABLE`** — the exact-duplicate sub-check passed
(no dups), but the embedding portion could not run. The gate is **not
PASS**; the lexicon may **not** proceed to bridge generation.

**To unblock (requires approval):** install `sentence-transformers` (pulls `torch`) and cache `sentence-transformers/all-MiniLM-L6-v2`,
then re-run this script; OR approve switching to a different available embedding model. Do not substitute a
model silently.

## 11. Next recommended gate
Resolve dependency/model availability (with approval), then re-run this gate to completion; only then
`B1_1_BRIDGE_POOL_GENERATION`.

## Final status
```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
This step:             EMBEDDING DIAGNOSTIC — BLOCKED (dependency unavailable)
Bridge pool generated: NO
Generation run:        NO
Scoring run:           NO
LLM judge run:         NO
Source lexicon:        NOT modified
Exact-duplicate check: PASS
```
**Structure, not validated meaning.** Embedding diagnostic blocked; verdict stands, Track B BLOCKED.
