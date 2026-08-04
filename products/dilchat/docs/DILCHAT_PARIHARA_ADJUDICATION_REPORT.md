# DilChat Guna Milan — Parihara Adjudication Report

Adjudication record for the **ordered deterministic** dosha-parihara model defined in
`rules/ashtakoota_muhurta_chintamani_raman_v1/parihara.json`. This document adjudicates each of the
six parihara rules and states the deterministic precedence that governs how they interact.

**Pack:** `ashtakoota_muhurta_chintamani_raman_v1` · **Component:** `parihara` · **Executable:** no ·
**Review status:** `PENDING_DOMAIN_REVIEW` · **All parihara rules ship `enabled: false`.**

> **This is an ordered DETERMINISTIC model — NOT a weighted-probability model.** Doshas are detected,
> eligible pariharas are gathered, and a strict precedence + stacking policy selects **at most one**
> effect per dosha. There is no weighted accumulation, no partial-credit blending, and no probability
> weighting. Enabling any parihara is a domain-review + founder decision, never an engineering
> default. Silent cancellation is prohibited: every applied parihara is written to the decision trace.
> **Nothing here is approved and nothing is executable.**

---

## 1. Model policy (from `parihara.json`)

| Policy field | Value |
|---|---|
| `ordered` | `true` |
| `no_weighted_accumulation` | `true` |
| `default` | `no_cancellation` |
| `no_silent_cancellation` | `true` — every fired parihara recorded in the report's decision trace |
| `precedence_principle` | Lower priority integer applies first. Within one dosha, at most ONE parihara takes effect (`EXCLUSIVE_HIGHEST_PRIORITY`) unless a rule is explicitly `SINGLE_APPLICATION`. |
| `numeric_before_interpretive` | Numeric (`cancel_dosha`) pariharas are evaluated before interpretive-relief pariharas; a numeric cancellation pre-empts any interpretive relief for the same dosha. |
| `mutual_exclusion_principle` | Contradictory pariharas list each other in `mutual_exclusions`; if one fires the others are suppressed for that dosha. |
| `mangal_scope` | Mangal / Manglik (Kuja) dosha is OUTSIDE the 36-point sum (DEC-019); a separate flag, never folded into the Guna score or cancelled by any Ashtakoota parihara. |

### Allowed outcomes

`NO_DOSHA` · `DOSHA_PRESENT` · `DOSHA_CANCELLED` · `DOSHA_PARTIALLY_RELIEVED` · `SOURCE_CONFLICT` ·
`REQUIRES_DOMAIN_REVIEW`.

### Effect vocabulary

| Effect | Numeric? | Meaning |
|---|---|---|
| `cancel_dosha` | **yes** — `changes_numeric_score = true` | The dosha's 0 is restored to the koota's full score. |
| `partial_relief_interpretive` | no — `changes_interpretive_severity_only = true` | Severity wording softened; numeric score UNCHANGED. |
| `no_numeric_change` | no | Separate-flag placeholder (e.g. Mangal); no numeric effect. |

### Stacking vocabulary

- **`EXCLUSIVE_HIGHEST_PRIORITY`** — among all eligible pariharas for ONE dosha, only the single
  lowest-priority-integer rule applies; the rest are suppressed.
- **`NON_STACKING`** — this rule never combines its effect additively with another; if another rule
  already resolved the dosha, this one is skipped.
- **`SINGLE_APPLICATION`** — this rule may apply at most once per evaluation for its dosha.

---

## 2. Per-rule adjudication

For each rule: stable ID, affected koota, intended source, exact condition, priority, effect,
numeric-vs-interpretive nature, stacking policy, mutual exclusions, regional applicability, reviewer
decision (PENDING), and v1 inclusion (PENDING). Every rule is `enabled: false`.

### R1 · `nadi_cancel_same_rashi_diff_nakshatra`

| Field | Value |
|---|---|
| Affected koota | nadi |
| Intended source | `MC-NORMATIVE` |
| Exact condition | `same_nadi: true`, `same_rashi: true`, `same_nakshatra: false` |
| Priority | 10 |
| Effect | `cancel_dosha` |
| Numeric vs interpretive | **numeric** (`changes_numeric_score = true`) — restores Nadi to 8 |
| Stacking policy | `EXCLUSIVE_HIGHEST_PRIORITY` |
| Mutual exclusions | `nadi_cancel_lords_friends` |
| Regional applicability | north_indian (school-variable) |
| Adjudication status | `PENDING_DOMAIN_REVIEW` · source_conflict = NONE |
| Reviewer decision | `PENDING` |
| v1 inclusion | `PENDING` · `enabled: false` |

### R2 · `nadi_cancel_same_nakshatra_diff_pada`

| Field | Value |
|---|---|
| Affected koota | nadi |
| Intended source | `MC-NORMATIVE` |
| Exact condition | `same_nadi: true`, `same_nakshatra: true`, `same_pada: false` |
| Priority | 11 |
| Effect | `cancel_dosha` |
| Numeric vs interpretive | **numeric** — restores Nadi to 8 |
| Stacking policy | `EXCLUSIVE_HIGHEST_PRIORITY` |
| Mutual exclusions | _(none)_ |
| Regional applicability | north_indian (school-variable) |
| Adjudication status | `PENDING_DOMAIN_REVIEW` · source_conflict = NONE |
| Reviewer decision | `PENDING` |
| v1 inclusion | `PENDING` · `enabled: false` |

### R3 · `nadi_relief_lords_friends`

| Field | Value |
|---|---|
| Affected koota | nadi |
| Intended source | `RAMAN-ENGINEERING` |
| Exact condition | `same_nadi: true`, `rashi_lords_mutual_friends: true` |
| Priority | 30 |
| Effect | `partial_relief_interpretive` |
| Numeric vs interpretive | **interpretive only** (`changes_interpretive_severity_only = true`) — no numeric change |
| Stacking policy | `NON_STACKING` |
| Mutual exclusions | `nadi_cancel_same_rashi_diff_nakshatra` |
| Regional applicability | school-variable (**BLOCKED — weak source support**) |
| Adjudication status | `BLOCKED_DOMAIN_SOURCE` · source_conflict = NONE |
| Reviewer decision | `PENDING` |
| v1 inclusion | `PENDING` · `enabled: false` |

### R4 · `bhakoot_cancel_same_rashi_lord`

| Field | Value |
|---|---|
| Affected koota | bhakoot |
| Intended source | `MC-NORMATIVE` |
| Exact condition | `bhakoot_dosha: true`, `same_rashi_lord: true` |
| Priority | 10 |
| Effect | `cancel_dosha` |
| Numeric vs interpretive | **numeric** — restores Bhakoot to 7 |
| Stacking policy | `EXCLUSIVE_HIGHEST_PRIORITY` |
| Mutual exclusions | `bhakoot_relief_lords_friends` |
| Regional applicability | widely cited (north_indian) |
| Adjudication status | `PENDING_DOMAIN_REVIEW` · source_conflict = NONE |
| Reviewer decision | `PENDING` |
| v1 inclusion | `PENDING` · `enabled: false` |

### R5 · `bhakoot_relief_lords_friends` — **SOURCE_CONFLICT (Dossier D)**

| Field | Value |
|---|---|
| Affected koota | bhakoot |
| Intended source | `RAMAN-ENGINEERING` |
| Exact condition | `bhakoot_dosha: true`, `rashi_lords_mutual_friends: true`, `same_rashi_lord: false` |
| Priority | 20 |
| Effect (declared) | `partial_relief_interpretive` |
| Conflict | **full numeric cancellation vs interpretive relief only** — candidate effects differ; NOT resolved |
| Numeric vs interpretive | **disputed** — this is exactly the conflict; not adjudicated |
| Stacking policy | `NON_STACKING` |
| Mutual exclusions | `bhakoot_cancel_same_rashi_lord` |
| Regional applicability | school-variable |
| Adjudication status | `SOURCE_CONFLICT` |
| Reviewer decision | `PENDING` |
| v1 inclusion | `PENDING` · `enabled: false` |

### R6 · `mangal_dosha_separate_flag` — placeholder, OUTSIDE the 36-point sum

| Field | Value |
|---|---|
| Affected koota | `external_mangal` (not an Ashtakoota koota) |
| Intended source | `RAMAN-ENGINEERING` |
| Exact condition | _(none — placeholder)_ |
| Priority | 99 |
| Effect | `no_numeric_change` |
| Numeric vs interpretive | **neither** — a separate report flag; never numeric, never interpretive relief on the Guna score |
| Stacking policy | `SINGLE_APPLICATION` |
| Mutual exclusions | _(none)_ |
| Regional applicability | n/a — OUTSIDE the 36-point sum (DEC-019) |
| Adjudication status | `PENDING_DOMAIN_REVIEW` · source_conflict = NONE |
| Reviewer decision | `PENDING` |
| v1 inclusion | `PENDING` · `enabled: false` |

Mangal / Kuja (Manglik) dosha is included **only** as a disabled, non-numeric placeholder so it can
never be silently folded into the Guna score. It is a separate flag with its own matching rules if
DilChat ever evaluates it.

---

## 3. Deterministic precedence rules

These rules make the model reproducible: given the same inputs and the same enabled-set, exactly one
outcome per dosha is produced, with no accumulation and no silent override.

| Situation | Deterministic rule |
|---|---|
| **Multiple applicable cancellations** | `EXCLUSIVE_HIGHEST_PRIORITY` — the single lowest `priority` integer wins; all other eligible pariharas for that dosha are suppressed. |
| **Contradictory rules** | Resolved via `mutual_exclusions` — if one of a contradictory pair fires, the listed others are suppressed for that dosha. |
| **Same-lord vs friendly-lord (Bhakoot)** | `bhakoot_cancel_same_rashi_lord` (priority 10, numeric) applies before `bhakoot_relief_lords_friends` (priority 20); the friendly-lord rule lists the same-lord rule as a mutual exclusion and is suppressed when it fires. |
| **Numeric restoration vs interpretive relief** | Numeric (`cancel_dosha`) is evaluated before interpretive (`partial_relief_interpretive`) for the same dosha; a numeric cancellation, once applied, pre-empts any interpretive relief. |
| **Koota-specific vs general relief** | Every parihara is scoped to a specific koota (`koota` field) and matches only that koota's dosha via `exact_conditions`; there is no general/global relief that can reach across kootas. |
| **Regional exceptions** | Carried per-rule in `regional_applicability`; a rule stays disabled until its regional school is confirmed (tradition scope is north_indian_ashtakoota, ASSUMED per DEC-009; South-Indian Dashakoota variants are out of scope until confirmed). |
| **Excluded rules** | Rules with weak/absent source support are `BLOCKED_DOMAIN_SOURCE` (e.g. `nadi_relief_lords_friends`) and stay disabled; rules whose effect is disputed are `SOURCE_CONFLICT` (e.g. `bhakoot_relief_lords_friends`) and stay disabled. |

### Worked precedence examples (illustrative; all rules disabled, so no effect fires today)

- **Nadi dosha, same rashi, different nakshatra, lords also friends:** R1 (priority 10, numeric) and
  R3 (priority 30, interpretive) are both eligible; R1 lists R3 as a mutual exclusion and is
  numeric-before-interpretive → R1 would win; R3 suppressed. *If enabled*, outcome `DOSHA_CANCELLED`.
- **Bhakoot dosha, same rashi lord AND friendly lords:** R4 (priority 10, numeric) and R5 (priority
  20) are both eligible; R4 lists R5 as a mutual exclusion → R4 would win; R5 suppressed. *If enabled*,
  outcome `DOSHA_CANCELLED`.
- **Bhakoot dosha, friendly lords but NOT same lord:** only R5 is eligible, and its effect is
  `SOURCE_CONFLICT` → outcome `SOURCE_CONFLICT` / `REQUIRES_DOMAIN_REVIEW`; never a silent numeric
  cancellation.

---

## 4. Guardrails (explicit)

- **A lower-priority rule must never silently override a higher-priority one.** Precedence is by
  ascending priority integer with `EXCLUSIVE_HIGHEST_PRIORITY`; a higher-numbered rule can only apply
  when no lower-numbered eligible rule resolved the dosha, and mutual exclusions enforce this.
- **Two weak rules must never accumulate into an invented probability.** `no_weighted_accumulation`
  is `true`; at most one effect applies per dosha. There is no summing, blending, or probability
  weighting of pariharas.
- **Mangal / Kuja dosha stays OUTSIDE the 36-point sum (DEC-019).** It is a separate flag only, never
  folded into or cancelled by any Ashtakoota parihara.
- **No silent cancellation.** Whenever an enabled parihara fires, its `rule_id`, the raw koota score,
  the effect, and the resulting status are recorded in the report's decision trace.
- **Numeric and interpretive effects are strictly separated.** A `cancel_dosha` restores the full
  koota score; a `partial_relief_interpretive` leaves the number unchanged and only softens wording.

---

## 5. Precedence and stacking summary (from `parihara.json`)

| Key | Value |
|---|---|
| `multiple_applicable_cancellations` | `EXCLUSIVE_HIGHEST_PRIORITY` — lowest priority integer wins; others suppressed. |
| `contradictory_exceptions` | Resolved via `mutual_exclusions`. |
| `same_lord_vs_friendly_lord` | same-lord (priority 10) applies before friendly-lord (priority 20); friendly-lord suppressed by mutual exclusion when same-lord fires. |
| `score_cancellation_vs_interpretive_relief` | numeric (`cancel_dosha`) evaluated before interpretive (`partial_relief_interpretive`); numeric pre-empts interpretive relief. |
| `regional_variants` | carried per-rule in `regional_applicability`; disabled until the regional school is confirmed. |
| `incomplete_source_support` | rules with weak/absent source support are `BLOCKED_DOMAIN_SOURCE` and stay disabled. |

---

## 6. Status

**All six parihara rules remain `enabled: false`.** None is approved, none is executable. One rule is
`BLOCKED_DOMAIN_SOURCE` (`nadi_relief_lords_friends`), one is `SOURCE_CONFLICT`
(`bhakoot_relief_lords_friends`, Dossier D), and the remaining four are `PENDING_DOMAIN_REVIEW`.
Enabling any parihara requires a frozen edition + qualified reviewer + founder decision.

**Reference:** `rules/ashtakoota_muhurta_chintamani_raman_v1/parihara.json`;
`docs/DILCHAT_GUNA_RULE_ADJUDICATION_LEDGER.md` (Dossier D);
`docs/DILCHAT_PARIHARA_PRECEDENCE_AND_STACKING.md` (pipeline view).
