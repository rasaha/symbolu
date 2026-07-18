# B1.2 External Feature Inventory Spec

## 1. Scope and non-rescue rule

Specifies and evaluates the **external** semantic feature inventory for the Layer-3 feature-space redesign,
under the restriction `FEATURE_SPACE_RISK_RESOLVED_WITH_EXTERNAL_INVENTORY_ONLY`. **Spec/evaluation only** —
no B1.2 mapping-fidelity scoring, no Symbol-U scoring, no alignment run. It does **not** reopen B1.2 for
scoring, does **not** overturn the B1/B1.1 null results, does **not** claim mapping-fidelity signal, and makes
**no** ontology / Sanskrit privilege / semantic-truth / Track-B-unblock claim. B1.1 stays
`RANDOM_OR_SCRAMBLED_MATCHES`; Track B stays BLOCKED. **Structure, not validated meaning.**

## 2. Inventory source selection

**WordNet supersenses / lexnames** are the preferred first external inventory: external, offline,
version-pinned (WordNet 3.0), **not derived from varṇa glosses**, already provisioned, reproducible. This spec
**evaluates** them for adequacy (§10) before freezing. A hand-curated Symbol-U/varṇa feature list is
**forbidden** (risk adjudication).

**Adequacy evaluation (empirical, grounded in the corpus):** WordNet 3.0 exposes **45 lexnames**. Their
granularity was tested on the near-neighbor pairs Axis 1 must separate (§10) — and it is **too coarse**: the
critical near-neighbors collapse to a single lexname. WordNet lexnames are therefore **not** frozen as the
final inventory (see §13).

## 3. Inventory contents

The evaluated inventory is frozen as a **candidate artifact** in `b1_2_external_feature_inventory.json` — the
45 WordNet 3.0 lexname categories (26 noun.*, 15 verb.*, 3 adj.*, 1 adv.*). Each feature carries `feature_id`,
`feature_name`, `wordnet_lexname`, `pos`, `description`, `source` (WordNet 3.0 lexicographer files), and
`used_for` (both V and G). The file's `status` is `EVALUATED_CANDIDATE_TOO_COARSE_NOT_FROZEN_AS_FINAL` — it is
a documented evaluation, **not** the final frozen inventory.

## 4. Forbidden inventory rule

Feature names may **not** be added because they match varṇa vocabulary. Forbidden/controlled as *selection
criteria*: release, dissolution, contraction, expansion, clarity, concealment, liberation, binding,
attachment, order, pure/impure, prāṇa-like energy labels, Sanskrit-derived labels, varṇa pole labels. Such
concepts may appear **only** if native to the external inventory and present **because the external source
contains them** — never selected for Symbol-U resemblance. (WordNet lexnames contain none of these, by
construction.)

## 5. G→feature extraction spec

- **Input:** the deterministic dictionary/WordNet differential output of `G(word)` (target synset + neighbor
  synsets). **No varṇa/V input, no Symbol-U glossary, no hand-polishing.**
- **Method (mechanical):** count the **lexname distribution** over the target synset + its neighbor synsets
  (and their definition/hypernym synsets), producing counts per inventory feature.
- **Output:** a fixed-length vector over the frozen inventory.
- **Normalization:** L1-normalize (proportions) so vector density is comparable across words; zero for absent
  lexnames.

## 6. V→feature extraction spec

- **Input:** the existing varṇa-derived V text/signature only (bridge text / varṇa skeleton). **No target
  word (if avoidable), no dictionary definitions, no G(word), no synonym set, no arm label.**
- **Same frozen extractor** for V_real, V_scrambled, V_deranged, V_removed/random.
- **Output:** the same fixed-length vector over the frozen inventory.
- **Allowed methods:** (A) frozen **blind extractor** from V text → inventory; (B) fixed **lexical/rule**
  mapping from V bridge terms → inventory (e.g., map each V content word to the lexname of its own WordNet
  synset); (C) if neither is defensible → STOP_NOW. **Assessment:** (B) is deterministic and reproducible but
  routes V's abstract vocabulary through WordNet, which is coarse; (A) is cleaner but LLM-based. **Method
  choice is deferred to the extraction-freeze gate** and is moot here because the inventory itself fails
  adequacy (§10, §13).

## 7. Blindness and provenance

Both extractors must be **frozen before** any G/V alignment; **no per-word edits**; **no post-hoc feature
additions**; **no tuning after seeing alignment**; **all configs/prompts/inventory files hashed**. (Carried to
the extraction-freeze gate; not exercised here since the inventory is not frozen as final.)

## 8. Triviality audit preregistration (mandatory before any scoring)

- **V_random** and **V_deranged** must **not** match G broadly (near baseline).
- **V_real** must **not** have uniformly high similarity to **all** G's.
- Average **random-pair** V↔G similarity must be near a documented **baseline**.
- Feature vectors must **not** be too **dense**; feature entropy/frequency must **not** collapse to a few
  universal features.
- **If V matches most G's equally well → STOP_NOW.**
- Concrete thresholds (e.g., mean off-target similarity, max density, min entropy) are to be **finalized in
  the extraction-freeze gate before scoring** — none are relaxed here.

## 9. Density / frequency audit

Define (thresholds finalized next gate): **max average vector density**; **max single-feature dominance**;
**min feature diversity/entropy**; **source-balance** check between V and G vectors; **missingness** check;
**all-zero vector** handling (drop by rule / documented). These replace the prose style-tell as the fairness
gate.

## 10. Near-neighbor adequacy (the decisive finding)

Empirical lexname assignment (first noun synset) for the required near-neighbor cases:

| case | lexnames | separates? |
|---|---|---|
| father / guardian / teacher / hammer | noun.person / noun.person / noun.person / noun.artifact | **NO** (person-triple collides; only hammer separates) |
| mother / caregiver | noun.person / noun.person | **NO** |
| water / ocean | noun.substance / noun.object | yes |
| fire / light | noun.event / noun.phenomenon | yes |
| justice / law | noun.attribute / noun.group | yes |
| freedom / power | noun.state / noun.attribute | yes |

**The critical near-neighbor cases collapse.** father/guardian/teacher all map to `noun.person`, and
mother/caregiver both map to `noun.person`, so the Axis-1 gradient **father > guardian > teacher** (and
**mother > caregiver**) is **impossible** under this inventory — the very discrimination B1.2 needs is
unrepresentable. WordNet lexnames can, at best, support a **coarse upper-level** test (father vs hammer), not
the near-neighbor mapping-fidelity test. **Inadequate for B1.2.**

## 11. Axis-1 / Axis-2 compatibility

- **Axis 1** (V(target) vs G(target/near/mid/far), gradient target > near > mid > far): **not supported** —
  near-neighbors are indistinguishable under lexnames (§10).
- **Axis 2** (V_real vs V_scrambled/V_deranged/V_removed against G(target)): structurally expressible, but
  meaningless without an inventory that can carry word-specific signal.

Both axes require a **finer** external inventory than lexnames.

## 12. STOP_NOW conditions

STOP_NOW if: no external inventory is available; the external inventory is **too coarse for near-neighbor
separation**; V→feature mapping requires hand-tuning toward G; the inventory requires varṇa-derived labels;
the triviality audit fails; vectors are too dense/generic; V_random/V_deranged broadly match G; or feature
extraction cannot be made blind and reproducible. **The "too coarse" condition is met (§10)** — but an
**alternate external source** may still exist (§13), so this is a *needs-alt-source* outcome, not an outright
stop.

## 13. Decision

```
DECISION: EXTERNAL_FEATURE_INVENTORY_TOO_COARSE_NEEDS_ALT_SOURCE
```

WordNet lexnames are validly external and non-varṇa, but empirically **too coarse** to separate the
near-neighbors B1.2 requires (§10). `EXTERNAL_FEATURE_INVENTORY_FROZEN` is **not** chosen (freezing an
inadequate inventory would guarantee a null-by-construction, not a fair test). `FEATURE_INVENTORY_SPEC_BLOCKED_
STOP_NOW` is **not yet** chosen because a **finer external, offline, non-varṇa inventory may exist** and must
be reviewed first — candidates to evaluate next: **FrameNet** frames (not currently provisioned; downloadable
like WordNet, needs check), **published semantic feature-norm** sets (e.g., attribute norms), or a **finer
WordNet-derived** signal (shared-hypernym synsets at a fixed depth — external, non-varṇa, more granular than
lexnames). If none proves both non-varṇa-shaped **and** fine-grained enough, the alt-source review defaults to
`VARNA_LINE_CLOSURE_MEMO`.

## 14. Next gate

- frozen → (not chosen)
- **too coarse → `B1_2_EXTERNAL_INVENTORY_ALT_SOURCE_REVIEW`** *(recommended)*
- blocked → `VARNA_LINE_CLOSURE_MEMO`

## 15. Final status block

```
document:                   B1.2 external feature INVENTORY SPEC (spec/evaluation only; no scoring/alignment)
decision:                   EXTERNAL_FEATURE_INVENTORY_TOO_COARSE_NEEDS_ALT_SOURCE
evaluated inventory:        WordNet 3.0 lexnames (45) — external, non-varṇa, but too coarse for near-neighbors
inventory file:             b1_2_external_feature_inventory.json (candidate; NOT frozen as final)
near-neighbor test:         father/guardian/teacher & mother/caregiver collapse to noun.person → Axis-1 gradient impossible
powered R3 prose failure:   REMAINS VALID (ba 0.70, CI [0.5929, 0.7929])
B1.2 reopened for evidence: NO
B1.1 verdict:               UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
LIMITED_GENERATION_UTILITY: NOT earned
MAPPING_FIDELITY_SIGNAL:    NOT earned
Track B:                    BLOCKED
Track G / Track F:          RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
next gate:                  B1_2_EXTERNAL_INVENTORY_ALT_SOURCE_REVIEW (else VARNA_LINE_CLOSURE_MEMO)
```

**Structure, not validated meaning.** The first external inventory (WordNet lexnames) is genuinely external
and non-varṇa but too coarse for the near-neighbor test; a finer external source must be reviewed before any
feature-space B1.2 can proceed. The powered R3 failure stands, B1.1's verdict is unchanged, B1.2 is not
reopened for evidence, and Track B remains BLOCKED.
