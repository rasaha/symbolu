# B1.1 Bridge-Pool Generation — REPORT (DRAFT, FALLBACK_QUALIFIED)

## Scope and non-claims
Deterministic transform of the resolved binding/liberating lexicon into **68 bridge phrases**
(binding + liberating per varṇa). No model / generation / scoring / judge. Generated from the B1.1 JSON only;
source lexicons untouched. **FALLBACK_QUALIFIED** — the real embedding gate is `BLOCKED_DEPENDENCY_UNAVAILABLE`
and still owed; this is **not** a B1.1 freeze and **not** generation authorization. Does not modify B1, change
the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B (**BLOCKED**). **Structure, not validated meaning.**

## Inputs & derivation
- input: `b1_1_experimental_contrastive_lexicon_draft.json` (sha256 `e8aeb105027907092b28eb17896fc699cf780f180fe38ca645f7ca94751b5bb7`)
- entries loaded: **34** · bridge phrases: **68**
- binding_bridge = binding_expression (normalized) · liberating_bridge = liberating_expression + " — " + functional_operation
- **manual/heuristic per-entry alteration: NONE** (uniform template; every phrase links to one source expression)

## Validator checks
| check | result | detail |
|---|---|---|
| 1_34_entries | PASS | 34 |
| 2_68_phrases | PASS | 68 |
| 3_no_missing_varnas | PASS | 34 |
| 4_no_duplicate_bridge | PASS | [] |
| 5_no_empty_phrase | PASS | 0 |
| 6_no_forbidden_framing | PASS | [] |
| 7_no_moksha_endpoint | PASS | [] |
| 8_ca_va_distinct | PASS | {'Ca': 'falsehood-discerning insight without egoic superiority — separates tru', |
| 9_ha_ksa_distinct | PASS | {'Ha': 'realized knowing without ownership — lets knowledge dissolve identity ', |
| 10_sa_guna_binding_aware | PASS | sattvic clarity/order owned as purity, superiority, or attachment to harmony |
| 11_ra_dual_source | PASS | rajasic activation driven by compulsion, desire, projection, or destructive coll |
| 12_ddha_la_distinct | PASS | {'Ḍha': 'malice — sadistic cruelty toward the maligned', 'La': 'physical harm in |
| 13_ka_sa_not_identical | PASS | {'Ka': 'forward-orientation held without attachment to the outcome — aspires a', |
| 14_each_phrase_one_source | PASS | True |

## Distinction checks
Ca/Va ✓ · Ha/Kṣa ✓ ·
Sa guṇa-aware ✓ · Ra dual-source ✓ ·
Ḍha/La ✓ · Ka/Sa non-identical ✓

## Gate status
**`PASS_BRIDGE_DRAFT`**

## Caveat
Bridge pool generated under **FALLBACK_QUALIFIED** because the embedding gate remains blocked. Not final
B1.1 freeze; not generation authorization. Before freeze: run the real embedding gate, OR the prereg must
explicitly record the weaker local fallback and the elevated R-risk.

## Manual process checks
- source lexicons in `varna_lens/`: NOT modified · B1 artifacts: NOT modified
- no embedding / model / generation / scoring / judging run · no bridge generation authorized

## Final status
```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
Bridge pool:           DRAFT (FALLBACK_QUALIFIED)
Embedding gate:        BLOCKED (still owed)
Gate status:           PASS_BRIDGE_DRAFT
```
**Structure, not validated meaning.**
