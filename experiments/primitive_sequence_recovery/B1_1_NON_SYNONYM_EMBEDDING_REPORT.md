# B1.1 Non-Synonym Embedding Gate — REPORT (BLOCKED)

## 1. Scope and non-claims
Embedding-similarity diagnostic over all **34 resolved** binding/liberating counter-poles. NOT generation,
NOT scoring, NOT an LLM judge. Does not modify B1, change the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or
unblock Track B (**BLOCKED**). No ontology / Sanskrit privilege / semantic-truth claim. Necessary but not
sufficient; `R_deranged` remains the crux. **Structure, not validated meaning.**

## 2. Frozen model and thresholds
- model_id (frozen): `sentence-transformers/all-MiniLM-L6-v2`
- model_meta: {"reason": "ProxyError: 403 Forbidden"}
- metric: cosine_over_L2_normalized_embeddings · thresholds: hard ≥ 0.88, soft 0.82–0.88, pass < 0.82
- fields (primary): liberating_expression, functional_operation · combined = diagnostic · contrast_boundary NOT a primary target
- **STATUS: model NOT loaded** — ProxyError: 403 Forbidden. `sentence-transformers` 5.6.0 + `torch` 2.12.1 installed OK; the block is the **model download**: the organization egress policy denies `huggingface.co:443` (proxy status: `connect_rejected`, "gateway answered 403 to CONNECT"). Not retried / routed-around, per proxy policy.

## 3. Inputs and exclusions
- input: `b1_1_experimental_contrastive_lexicon_draft.json` (sha256 `acf8ee6d791e988f73ffeb1f1f8558efdabb403a2267c66576b471fe79f2244f`)
- evaluated: **34** entries · no deferrals · vowels excluded

## 4. Exact duplicate check
- liberating_expression duplicates: NONE
- functional_operation duplicates: NONE
- exact-duplicate result: **PASS (no exact duplicates)**

## 5. Pairwise similarity summary
**NOT COMPUTED** — embedding dependency unavailable (no fabricated scores).

## 6. Hard flags
NOT COMPUTED (dependency unavailable).
## 7. Soft flags
NOT COMPUTED (dependency unavailable).
## 8. Human adjudication requirements
Every flagged pair requires one of: rewrite · accept-with-rationale (operationally distinct) · defer.
Rationale placeholders (`<TBD_HUMAN>`) are in the JSON report; no flag passes by synonym substitution.
Deliberate contrast-pairs (e.g. Ha↔Kṣa knowing-by-intuition vs -inference; Ḍha↔La shield-maligned vs
protect-weak) are expected soft flags and are candidates for accept-with-rationale.

## 9. Gate status
**`BLOCKED_DEPENDENCY_UNAVAILABLE`** — the exact-duplicate sub-check passed, but the embedding portion could not run. Libraries are installed; the block is the **model host**. To unblock: the environment's egress policy must allow `huggingface.co` (currently denied, 403), OR the `all-MiniLM-L6-v2` weights must be supplied through an allowed channel / pre-populated local cache. No model was substituted.

## 10/11. Next gate
resolve dependency (approval), then re-run

## Final status
```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
This step:             EMBEDDING DIAGNOSTIC — BLOCKED
Entries evaluated:     34
Bridge pool generated: NO
Generation/scoring/judge: NO
Source lexicon:        NOT modified
Gate status:           BLOCKED_DEPENDENCY_UNAVAILABLE
```
**Structure, not validated meaning.**
