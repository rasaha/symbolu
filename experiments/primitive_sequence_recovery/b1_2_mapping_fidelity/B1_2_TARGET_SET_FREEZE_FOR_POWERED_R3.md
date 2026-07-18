# B1.2 Target-Set Freeze for Powered R3 Style-Tell Re-Adjudication

## 1. Scope and non-rescue rule

Freezes a real B1.2 target word set for a **properly powered R3 V↔G style-tell re-adjudication** — nothing
more. This does **not** run the powered R3 audit, run B1.2 alignment, judge mapping fidelity, or score
Symbol-U. It does **not** modify or rescue B1.1, change its verdict, claim generation utility / ontology /
Sanskrit privilege / semantic truth, or unblock Track B. **Freezing this target set does not reopen B1.2:**
the current **`STOP_NOW_G_IMPLEMENTATION_BLOCKED`** (R3 style-tell 0.5625 > 0.55 at N=16) **remains in force**
until a powered R3 re-adjudication passes. **No threshold relaxation and no renderer tuning are permitted.**
**Structure, not validated meaning.**

## 2. Why a powered target set

The provisional R3 audit used N=16 (8 V + 8 G) — far too small for a stable balanced-accuracy estimate. The
corrected symmetric keyword schema brought style separability from 0.9375 to **0.5625** (near chance), but at
N=16 that point estimate is statistically indistinguishable from 0.5 *and* marginally over the pre-registered
0.55 bar. A larger frozen set enables a properly powered re-adjudication with a real CI — the only legitimate,
non-gaming way to revisit the STOP (relaxing the 0.55 threshold in place is **not** allowed).

## 3. Target set

- **File:** `b1_2_powered_r3_target_set.json`
- **Count:** **70 targets** (≥40 required; ≥40 met).
- **Content hash (`target_set_sha256`):** `fe7aa7ac0081d4dcf6db788ca1fe94449844b40467d78bb7e23d7370f8d82fda`
- **Frozen:** yes; selected **before** any powered R3 audit; **no post-hoc replacement**.

Targets (70): justice, silence, mountain, river, music, friendship, teacher, shadow, freedom, honesty,
empathy, ocean, envy, order, integrity, autumn, water, fire, stone, tree, forest, star, wind, storm, cloud,
rain, snow, mother, father, child, friend, stranger, doctor, farmer, hunter, bridge, window, temple, village,
road, boat, sword, book, letter, song, dance, dream, memory, fear, anger, joy, sorrow, wisdom, truth, wealth,
wound, journey, promise, law, war, peace, bird, flower, island, desert, valley, shield, crown, market, prison.

## 4. Selection — word-agnostic, outcome-blind

- **Candidate pool (89):** the B1/B1.1 word pool (`b1_dry_run_harness` PRIMARY + PRIVATIVE) plus a broad
  neutral common-noun list spanning nature, objects, roles, and abstractions — ordered and deduped.
- **Selection was NOT based on any V/G style-tell outcome.** Words were kept purely by eligibility, screened
  by fixed rules before any powered audit. No cherry-picking toward words likely to help V.

## 5. Inclusion criteria

A candidate is included iff **all** hold:

1. present in **cmudict** (G2P) **and** yields **≥1 varṇa** via the real `core_A` (varṇa routing works);
2. has a **WordNet noun synset** (POS resolved to the first noun synset);
3. has **≥10 usable synonyms/near-neighbors** under the frozen G neighbor rule (target lemmas + co-hyponyms +
   hypernym terms);
4. **not a duplicate/near-duplicate** in the candidate pool.

## 6. Exclusion criteria (predeclared) and exclusions recorded

Exclusion rules: `no_cmudict_g2p`, `varna_routing_failure`, `no_wordnet_noun_synset`, `under_10_synonyms`,
`duplicate_or_near_duplicate`.

**19 candidates excluded — all by the `under_10_synonyms` rule** (WordNet gave fewer than 10 usable
neighbors): grief(9), courage(6), patience(9), echo(6), moon(6), sun(5), soldier(5), mirror(6), door(7),
garden(5), city(4), lamp(5), hope(7), mercy(4), hunger(6), gift(8), harvest(6), throne(8), ladder(4). Every
exclusion is recorded in `b1_2_powered_r3_target_set.json` under `exclusions` with its rule and synonym count.
No word was excluded by judgment; all by rule.

## 7. Provenance and hash

- **Source:** candidate pool = B1/B1.1 pool + neutral common-noun list; WordNet **v3.0** (offline, hashed in
  the G manifest); cmudict; real `core_A` for varṇa routing.
- **Target-set hash:** `fe7aa7ac0081d4dcf6db788ca1fe94449844b40467d78bb7e23d7370f8d82fda` (sha256 over the
  canonical sorted payload, excluding the hash field). Recorded inside the JSON.

## 8. Powered-R3 setup constraints (carried forward, not executed here)

- This set is for **style-tell re-adjudication only** — it does **not** authorize mapping-fidelity scoring or
  B1.2 evidence generation.
- G outputs from this set remain **audit artifacts** until the full B1.2 freeze.
- V/G rendering must use the **already-committed corrected symmetric matched-length keyword schema**
  (`run_b1_2_g_builder.py`); **no further renderer tuning** before the powered audit unless documented as a
  **new prereg amendment**.
- The powered R3 audit runs **only after** this target set is frozen and committed (i.e., the next gate).

## 9. Decision

```
DECISION: TARGET_SET_FROZEN_FOR_POWERED_R3
```

70 eligible targets (≥40) were selected word-agnostically and frozen with a content hash; exclusions are all
rule-based and recorded. `TARGET_SET_FREEZE_BLOCKED_STOP_NOW` is not triggered (the eligible pool far exceeds
40). This freeze does **not** reopen B1.2; the `STOP_NOW_G_IMPLEMENTATION_BLOCKED` stands until a powered R3
re-adjudication passes.

## 10. Final status block

```
document:                   B1.2 target-set FREEZE for powered R3 (freeze only; no audit/scoring run)
decision:                   TARGET_SET_FROZEN_FOR_POWERED_R3
target set:                 b1_2_powered_r3_target_set.json (70 targets; hash fe7aa7ac…)
excluded:                   19, all under_10_synonyms (recorded)
powered R3 audit:           NOT RUN (next gate)
B1.2 status:                STOP_NOW_G_IMPLEMENTATION_BLOCKED — REMAINS IN FORCE
threshold relaxation:       NONE (0.55 bar unchanged)
renderer tuning:            NONE (corrected symmetric schema frozen)
B1.1 verdict:               UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
LIMITED_GENERATION_UTILITY: NOT earned
Track B:                    BLOCKED
Track G / Track F:          RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
next gate:                  B1_2_POWERED_R3_STYLE_TELL_RE_ADJUDICATION
```

**Structure, not validated meaning.** A powered target set is frozen for one honest R3 re-adjudication; the
B1.1 verdict stands, Track B remains BLOCKED, the STOP_NOW remains in force, and no threshold or renderer was
relaxed.
