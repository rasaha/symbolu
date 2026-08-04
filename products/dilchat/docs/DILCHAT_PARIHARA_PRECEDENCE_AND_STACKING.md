# DilChat Guna Milan — Parihara Precedence and Stacking

Describes the **ordered, deterministic** dosha-cancellation (parihara) model defined in
`rules/ashtakoota_muhurta_chintamani_raman_v1/parihara.json`.

> **Not a weighted matrix. No weighted accumulation.** Doshas are detected, eligible pariharas are
> gathered, and a strict precedence + stacking policy selects **at most one** effect per dosha.
> Every parihara ships `enabled: false`. Enabling any is a domain-review + founder decision, never an
> engineering default. Silent cancellation is prohibited — every applied parihara is written to the
> decision trace.

---

## The 8-step deterministic pipeline

1. **Derive inputs.** From each partner's Moon: rashi, nakshatra, pada, rashi lord, nadi, plus
   derived predicates (`same_rashi`, `same_nakshatra`, `same_pada`, `same_rashi_lord`,
   `rashi_lords_mutual_friends`). Directional role mapping (bride/groom) is **PENDING OQ-2**.
2. **Raw score.** Compute each koota's raw score from its table (no cancellation yet). Sum → raw
   36-point total. Mangal/Manglik dosha is **not** part of this sum (DEC-019).
3. **Detect dosha.** Flag Bhakoot dosha ({2,12}/{5,9}/{6,8}) and Nadi dosha (same nadi). A koota with
   no dosha → outcome `NO_DOSHA`; a koota with a dosha and no eligible parihara → `DOSHA_PRESENT`.
4. **Eligible parihara.** For each detected dosha, gather every parihara whose `exact_conditions`
   match. If none match → keep `DOSHA_PRESENT`.
5. **Precedence.** Sort eligible pariharas by `priority` (lower integer first). Apply the
   **numeric-before-interpretive** rule: `cancel_dosha` (numeric) rules are considered before
   `partial_relief_interpretive` rules for the same dosha.
6. **Stacking.** Apply the stacking policy:
   - `EXCLUSIVE_HIGHEST_PRIORITY` — only the single lowest-priority rule applies; the rest are
     suppressed.
   - `NON_STACKING` — skipped if the dosha was already resolved by a higher-priority rule.
   - `SINGLE_APPLICATION` — applies at most once.
   - `mutual_exclusions` — if one of a contradictory pair fires, the other is suppressed.
7. **Final status / effect.** Compute the koota's final score and outcome (see allowed outcomes).
   A numeric cancellation restores the koota's full score; an interpretive relief leaves the number
   unchanged and only softens severity wording.
8. **Decision trace.** Record, per dosha: raw koota score, detected dosha, the parihara `rule_id`
   applied (if any), whether it changed the number, the resulting score, and the final outcome. This
   trace is mandatory — no silent cancellation.

---

## Allowed outcomes

| Outcome | Meaning |
|---|---|
| `NO_DOSHA` | No dosha detected in the koota. |
| `DOSHA_PRESENT` | Dosha detected; no eligible/enabled parihara — dosha stands. |
| `DOSHA_CANCELLED` | A numeric parihara restored the koota's full score. |
| `DOSHA_PARTIALLY_RELIEVED` | An interpretive parihara softened severity; **number unchanged**. |
| `SOURCE_CONFLICT` | Sources disagree on the parihara's effect; not resolved. |
| `REQUIRES_DOMAIN_REVIEW` | Rule/effect not yet approved (default while pack is blocked). |

---

## Precedence and stacking rules

| Situation | Rule |
|---|---|
| Multiple applicable cancellations | `EXCLUSIVE_HIGHEST_PRIORITY` — lowest `priority` integer wins; others suppressed. |
| Contradictory exceptions | Resolved via `mutual_exclusions` — one firing suppresses the listed others. |
| Same-lord vs friendly-lord (Bhakoot) | `bhakoot_cancel_same_rashi_lord` (priority 10) applies before `bhakoot_relief_lords_friends` (priority 20); the latter is a listed mutual exclusion. |
| Score-cancellation vs interpretive-relief | Numeric (`cancel_dosha`) evaluated before interpretive (`partial_relief_interpretive`); a numeric cancellation pre-empts interpretive relief for the same dosha. |
| Regional variants | Carried per-rule in `regional_applicability`; disabled until the regional school is confirmed (OQ-1). |
| Incomplete source support | Rules with weak/absent source support are `BLOCKED_DOMAIN_SOURCE` and stay disabled. |

---

## Rules currently defined (all disabled)

| `rule_id` | Koota | Priority | Effect | Stacking | Mutual exclusions | Review |
|---|---|---|---|---|---|---|
| `nadi_cancel_same_rashi_diff_nakshatra` | nadi | 10 | cancel (numeric) | EXCLUSIVE_HIGHEST_PRIORITY | `nadi_cancel_lords_friends` | PENDING_DOMAIN_REVIEW |
| `nadi_cancel_same_nakshatra_diff_pada` | nadi | 11 | cancel (numeric) | EXCLUSIVE_HIGHEST_PRIORITY | — | PENDING_DOMAIN_REVIEW |
| `nadi_relief_lords_friends` | nadi | 30 | interpretive relief | NON_STACKING | `nadi_cancel_same_rashi_diff_nakshatra` | BLOCKED_DOMAIN_SOURCE |
| `bhakoot_cancel_same_rashi_lord` | bhakoot | 10 | cancel (numeric) | EXCLUSIVE_HIGHEST_PRIORITY | `bhakoot_relief_lords_friends` | PENDING_DOMAIN_REVIEW |
| `bhakoot_relief_lords_friends` | bhakoot | 20 | cancel vs relief (SOURCE_CONFLICT) | NON_STACKING | `bhakoot_cancel_same_rashi_lord` | SOURCE_CONFLICT |
| `mangal_dosha_separate_flag` | external_mangal | 99 | no numeric change (separate flag) | SINGLE_APPLICATION | — | PENDING_DOMAIN_REVIEW |

---

## No weighted accumulation

There is **no** weighted sum of pariharas, no partial-credit blending, and no probability weighting.
Each dosha resolves to exactly one of the allowed outcomes via the ordered pipeline above. This keeps
cancellation auditable and reproducible, and keeps numeric vs interpretive effects strictly separated.

**Reference:** `rules/ashtakoota_muhurta_chintamani_raman_v1/parihara.json`.
