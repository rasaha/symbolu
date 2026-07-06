# B1.2 Feature-Space Circularity Risk Adjudication

## 1. Scope and non-rescue rule

Adjudicates whether the proposed Layer-3 **feature-space** redesign can avoid **circularity / false-positive
bias** before any inventory is specified. **Risk adjudication only** — no implementation, no inventory
created, no models, no scoring. It does **not** reopen B1.2, does **not** overturn the powered R3 prose
failure (`STOP_NOW_R3_STYLE_TELL_ROBUST_FAIL`, ba 0.70, CI [0.5929, 0.7929]), does **not** authorize
implementation, and makes **no** claim of generation utility / ontology / Sanskrit privilege / semantic truth
/ Track-B unblock. B1.1 stays `RANDOM_OR_SCRAMBLED_MATCHES`; Track B stays BLOCKED. **Structure, not
validated meaning.**

## 2. Risk A — feature inventory circularity

If the inventory uses **varṇa-gloss concepts** (release, dissolution, contraction, expansion, clarity, order,
attachment, concealment…), V maps into it **by construction** — the test would then measure whether the
inventory *resembles the varṇa glossary*, not whether varṇa predicts dictionary meaning. That manufactures a
**false positive** (V would match even `G(hammer)` via "force/boundary"). **Decision: RESOLVABLE only by
requiring an externally-sourced inventory (§5), an exclusion rule on varṇa-derived feature names (§6), and a
mandatory triviality audit (§9).** Otherwise unresolved → STOP_NOW.

## 3. Risk B — V→feature mapping hand-tuning

If humans map varṇa bridge phrases → features **after** seeing G, the mapping can be tuned toward the answer
key; freezing it later does not cleanse contaminated provenance. **Decision: RESOLVABLE only if the V→feature
mapping is FIXED before any G alignment, is word-agnostic, and is built without consulting G or the dictionary
— a blind frozen extractor (§7 Option B) or a pre-existing/rule mapping over the external inventory.**

## 4. Risk C — G→feature dictionary dominance

If G maps cleanly into external features but V does not, the test may simply show that dictionary meaning is
more legible than varṇa prediction. **This is an ACCEPTABLE null** (an honest negative for Symbol-U), **not** a
bias — *provided* the feature space is **not** adjusted to help V. It becomes invalid only if the inventory or
mapping is tweaked to rescue V after seeing that V maps poorly. **Decision: ACCEPTABLE as a possible null; any
post-hoc feature-space adjustment to help V is forbidden (STOP_NOW).**

## 5. Inventory independence requirement

An acceptable inventory must be:

- **externally sourced**, **not** derived from varṇa glosses, **not** from the B1.1 bridge pool, **not** from
  any Symbol-U ontology terms;
- **frozen before** any V/G scoring; **documented source/provenance**; **no post-hoc feature addition**.

**Candidate acceptable sources** (offline, version-pinnable, independent of Symbol-U):

- **WordNet supersenses / lexnames** (45 lexicographer categories: noun.person, noun.state, noun.act,
  noun.artifact, noun.feeling, verb.change, verb.motion, …) — strongest first candidate: offline, versioned,
  demonstrably not built for Symbol-U. *Caveat: may be too coarse to separate near-neighbors (father/guardian
  /teacher all → noun.person) — the inventory spec must verify granularity or escalate to a finer source.*
- existing **lexical-semantic feature norms** (e.g., published attribute-norm sets), if obtainable offline;
- **FrameNet-style frames** if available offline;
- **ConceptNet-style relations** only if versioned + offline;
- a **manually curated inventory** only if created **without consulting varṇa glosses** and **before** any
  V/G alignment — flagged **high risk** and least preferred (it reintroduces Risk A).

## 6. Inventory exclusion rule

Feature names that come **directly from the varṇa glossary vocabulary** are forbidden as *selection criteria*:
release, dissolution, contraction, expansion, clarity, concealment, liberation, binding, attachment, order,
pure/impure, prāṇa-like energy labels, any Sanskrit-derived label. These concepts may appear **only** if they
are already part of an **external** semantic inventory and are present **because the external source contains
them**, never because they match varṇa terms. Provenance of every feature must trace to the external source.

## 7. V→feature mapping requirement

- **Option A — pre-existing varṇa→external-feature mapping.** Valid only if it existed **before** this
  experiment and was **not** tuned to it. *Risk: none such is known to exist → effectively unavailable.*
- **Option B — frozen blind extractor** *(recommended).* Receives **only** V text + the external inventory;
  **no target word, no G, no dictionary definitions, no arm labels**; **same** prompt/rule for **all** V
  variants (real/scrambled/deranged/removed); outputs a feature vector. *Risk: LLM reflects its own reading of
  V prose — acceptable, because it never sees G; contamination is structurally impossible.*
- **Option C — rule-based lexical mapping.** Fixed keyword→feature table over the external inventory, no
  per-word edits. *Risk: the keyword→feature table itself can be tuned; must be frozen + justified against the
  external inventory, not the varṇa glosses.*

**Requirement:** use Option B or C, fixed and hash-bound **before** any G alignment; word-agnostic; must
support V_real / V_scrambled / V_deranged / V_removed.

## 8. G→feature mapping requirement

- G maps from the deterministic dictionary-differential outputs into the **same external inventory**.
- **No varṇa/V input.** Same extractor (or a parallel extractor with identical schema) as V's — so both sides
  use the same projection into the same feature names, differing only in their *inputs* (varṇa vs dictionary).
- **No hand-polishing;** frozen before scoring.

## 9. Triviality / false-positive audit (mandatory, before any real scoring)

- **V_random** and **V_deranged** must **not** match many G's broadly — they should sit at baseline.
- Feature vectors must **not** be too **dense** (a vector that lights up most features matches everything).
- Mean V-to-G similarity across **random pairs** must be near a **documented baseline**.
- **If V matches most G's equally well → the inventory is too generic → STOP_NOW.**
- **If V maps into high-value features regardless of the word → STOP_NOW** (the varṇa side is
  word-insensitive).

This audit **replaces** the prose style-tell as the fairness gate: instead of "can you detect V vs G by
style," it asks "does the inventory let V match everything." Its thresholds are pre-registered in the
inventory spec.

## 10. Style-replacement (schema) audit

With prose removed, require: **schema equality** (identical inventory, length, encoding); **vector-density**
check; **feature-frequency balance** across V and G; **no source-specific missingness** (V and G must populate
the same features, not systematically different subsets); **no source labels**; **no feature names that reveal
V/G source**.

## 11. Decision

```
DECISION: FEATURE_SPACE_RISK_RESOLVED_WITH_EXTERNAL_INVENTORY_ONLY
```

The circularity and hand-tuning risks are **resolvable, but only under strict conditions**: an
**externally-sourced, non-varṇa-shaped inventory** (§5–§6), a **blind/frozen word-agnostic V→feature mapping**
fixed before G alignment (§7 Option B/C), a **parallel G→feature mapping** (§8), and **mandatory triviality +
schema audits** (§9–§10) whose thresholds are pre-registered. Unconditional
`FEATURE_SPACE_RISK_RESOLVED_GO_INVENTORY_SPEC` is **not** chosen because it would permit a hand-curated
inventory (Risk A re-enters). `FEATURE_SPACE_RISK_UNRESOLVED_STOP_NOW` is **not** chosen because at least one
genuinely external, offline inventory (WordNet supersenses) exists as a starting candidate. **Residual open
risk carried to the next gate:** whether an external inventory can be both *non-varṇa-shaped* **and**
*fine-grained enough* to separate near-neighbors — if none can, the next gate defaults to STOP_NOW.

## 12. If GO — constraints for the next gate (`B1_2_FEATURE_INVENTORY_SPEC`)

The inventory spec must: **choose an external / independently-justified inventory** (start with WordNet
supersenses; escalate to a finer external source if too coarse; document provenance); **freeze feature
definitions**; **define the V→feature extraction** (blind, frozen, word-agnostic, all V variants); **define
the G→feature extraction** (parallel, no varṇa/V); **define the triviality audit** (baseline + density
thresholds); **define the density/frequency audit**; and **define STOP_NOW conditions** (too coarse, too
generic, contaminated provenance, or hand-tuning). Nothing is built until this spec is frozen and reviewed.

## 13. If STOP_NOW — closure wording (not triggered, recorded for completeness)

> The feature-space redesign cannot proceed because the inventory/mapping would be circular or hand-tuned,
> making any positive result uninterpretable. The current varṇa utility / mapping-fidelity line should close.

This wording applies only if the next gate finds **no** external inventory that is both non-varṇa-shaped and
adequately fine-grained; it is **not** the current decision.

## 14. Final status block

```
document:                   B1.2 feature-space circularity RISK ADJUDICATION (adjudication only)
decision:                   FEATURE_SPACE_RISK_RESOLVED_WITH_EXTERNAL_INVENTORY_ONLY
risk A (inventory circular): resolvable only via external inventory + exclusion rule + triviality audit
risk B (V→feature tuning):   resolvable only via blind frozen word-agnostic mapping fixed before G
risk C (G dominance):        acceptable as a possible NULL; no post-hoc feature-space help for V
powered R3 prose failure:    REMAINS VALID (ba 0.70, CI [0.5929, 0.7929])
B1.2 reopened?:              NO — requires a new feature-space prereg + freeze
B1.1 verdict:                UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
LIMITED_GENERATION_UTILITY:  NOT earned
Track B:                     BLOCKED
Track G / Track F:           RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
next gate:                   B1_2_FEATURE_INVENTORY_SPEC (external inventory only; else STOP_NOW)
```

**Structure, not validated meaning.** The feature-space risks are resolvable only with an external inventory
and a blind, pre-frozen V→feature mapping; the powered R3 failure stands, B1.1's verdict is unchanged, B1.2 is
not reopened, and Track B remains BLOCKED.
