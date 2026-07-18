# B1.2 Layer 3 Feature-Space Redesign (memo only)

## 1. Scope and non-rescue rule

Proposes an **alternate Layer 3** that replaces prose-to-prose V↔G comparison with alignment in a **shared
semantic feature space**. **Redesign proposal only** — no implementation, no models, no scoring. It does
**not** overturn the powered R3 failure (`STOP_NOW_R3_STYLE_TELL_ROBUST_FAIL`, balanced accuracy 0.70, CI
[0.5929, 0.7929]), does **not** change or rescue B1.1, does **not** authorize implementation, and makes
**no** claim of generation utility / ontology / Sanskrit privilege / semantic truth. B1.1 stays
`RANDOM_OR_SCRAMBLED_MATCHES`; Track B stays BLOCKED. **Structure, not validated meaning.**

## 2. Why prose-based R3 failed

The powered R3 audit (N=140) showed V (varṇa-gloss prose) and G (dictionary-feature text) are **robustly
style-separable** (balanced accuracy 0.70, CI excluding chance). A blinded judge can tell source from style
alone, so a fair prose-to-prose *alignment* test cannot run — any "fit" signal would be confounded by style,
not semantics. Crucially, this was a **measurement-comparability failure**, not a mapping-fidelity result:
Symbol-U was neither supported nor falsified; the two pipelines simply could not be rendered comparably.

## 3. New Layer 3 proposal (thesis)

**Layer 3 = a shared semantic-feature inventory.** Rather than comparing prose, project **both** V(word) and
G(word) into the **same frozen feature schema**:

- **G(word)** = dictionary-derived differential **feature vector** (over the frozen inventory).
- **V(word)** = varṇa-derived predicted **feature vector** (over the *same* inventory).
- Same feature names, same length, same numeric/sparse encoding.
- The test becomes **feature-alignment** (vector similarity), **not** prose preference — removing the register
  gap that killed R3.

## 4. Feature inventory (proposed, with a hard caveat)

A **fixed** inventory of semantic features, frozen before any mapping. Candidate features: origin/lineage,
nurture/care, protection, authority, guidance, provision, identity-formation, belonging, shelter, motion,
force, boundary, expansion, contraction, clarity, dissolution, order, conflict, restoration, concealment,
transformation, attachment, release, embodiment, abstraction.

Requirements: inventory **frozen before scoring**; **no per-word feature invention** after seeing alignments;
each feature **defined** in words; **feature count controlled** (broad enough to carry signal, narrow enough
to avoid universal overlap).

**⚠ Central caveat (this is the crux, see §11/§12):** the list above **reads like the varṇa gloss
vocabulary** — "dissolution", "release", "clarity", "order", "contraction/expansion" are near-verbatim bridge-
pool terms. If the inventory is derived from (or shaped like) the varṇa ontology, **V maps into it trivially
and the test is circular** — a built-in false positive. A valid inventory must be constructed **independently
of the varṇa glosses** (e.g., from a neutral external semantic resource such as WordNet supersenses /
lexicographic semantic roles / an established psycholinguistic feature-norm set), **not** authored to mirror
the bridge pool.

## 5. G-to-feature mapping

- G(word) is derived from **dictionary definitions + synonym differential features** (the existing
  deterministic WordNet G builder), then mapped into the frozen inventory.
- Mapping is **mechanical** (lexical-overlap / WordNet relation rules) or **frozen-prompt JSON extraction**
  (temp-0, schema-only), applied identically to every word.
- **No varṇa/V input; no hand-polishing.**

## 6. V-to-feature mapping

- V(word) is derived from the **existing varṇa machinery** (bound in the V-function binding spec), then mapped
  into the **same** inventory. Options:
  a. a **direct varṇa→feature table** (each varṇa/pole → inventory features), frozen;
  b. a **bridge-pool phrase→feature** mapping, frozen;
  c. **frozen-prompt extraction** from V bridge text → feature vector (temp-0, schema-only);
  d. **rule-based keyword** mapping.
- Must be **word-agnostic**, must **not** use G(word), and must support **V_real, V_scrambled, V_deranged,
  V_removed** (the ablations carry over unchanged).
- **⚠** Options (a)/(b) are where the theory can be smuggled: a hand-built varṇa→feature table tuned toward G
  is the feature-space analogue of hand-authoring the signature. It must be frozen and justified before any
  alignment is seen.

## 7. Style-tell replacement (schema-equality + leakage audit)

Because judge-facing prose is removed, the prose style-tell is replaced by **schema-equality checks**:

- identical **feature inventory**, identical **vector length**, identical **numeric range/encoding**;
- **no source labels**, **no prose source markers** in the vectors.
- If frozen-prompt extraction is used, **audit source leakage** in feature names/values (nothing varṇa- or
  dictionary-specific leaks the source).

**New required confound audit (replacing style-tell):** a **triviality/baseline check** — verify V does **not**
match *every* G merely because the inventory is varṇa-shaped. Concretely: the mean similarity of V(target) to
**wrong** G's must be well below the target similarity, and a **shuffled/random V** must sit at the chance
baseline. If V matches all G's highly, the inventory is smuggling the theory → invalid (§10).

## 8. Scoring

Vector-similarity options: **cosine** similarity, **Jaccard** overlap (sparse), **rank correlation**, **top-k
feature overlap**, **weighted feature similarity**.

- **Primary score:** similarity(V(target), G(target)).
- **Axis 1 (word-specificity):** similarity(V(target), G(target)) > similarity(V(target), G(near/mid/far)).
- **Axis 2 (mechanism):** similarity(V_real(target), G(target)) > similarity(V_scrambled / V_deranged /
  V_removed / random-V, G(target)).

## 9. Primary success criteria (both axes required)

**Axis 1:** V(target) is **closest** to G(target); a **semantic-distance gradient** target > near > mid > far;
and V(target) beats the **R_same / R_domain** G-side distractors.

**Axis 2:** V_real beats **V_scrambled**, **V_deranged**, **V_removed / no-varṇa**, and **chance/random V**.

**Only allowed positive label:** `MAPPING_FIDELITY_SIGNAL` — never `LIMITED_GENERATION_UTILITY`, ontology
validation, Sanskrit privilege, semantic truth, or Track-B unblock.

## 10. Kill criteria

- V_real **flat** across G(target/near/mid/far) → generic resonance.
- V_real ≈ **V_scrambled** → varṇa order carries no signal.
- V_real ≈ **V_deranged** → the target's own varṇa carries no word-specific signal.
- V_real ≈ **V_removed / no-varṇa** → dictionary/no-varṇa baseline explains the result.
- **feature inventory too broad/generic** (everything overlaps) → invalid.
- **feature mapping hand-authored per word** → invalid.
- **feature extractor uses G to build V** (or inventory shaped by the varṇa glosses) → **invalid / circular**.

## 11. Risks

- **Inventory smuggles the theory** *(highest risk)* — a feature list resembling the varṇa glosses makes V
  match by construction; the proposed list already does this. Must be built from a neutral external resource.
- **varṇa→feature mapping hand-tuned** — a bespoke table tuned toward G is a hidden degree of freedom.
- **Dictionary features dominate** — G is rich lexical content; V may be forced to "predict" what the
  dictionary already encodes.
- **Too many broad features** → universal overlap → high baseline similarity → false gradient washes out.
- **Too few features** → signal lost.
- **Post-hoc feature choice** — inventing/dropping features after seeing alignments invalidates the test.

The redesign genuinely fixes the *style/register* confound — but it **trades it for an
inventory-provenance/circularity confound** that is subtler and, if unmanaged, more dangerous (it manufactures
false positives rather than blocking the test). That is why this needs adjudication, not immediate build.

## 12. Decision

```
DECISION: FEATURE_SPACE_REDESIGN_HIGH_RISK_NEEDS_ADJUDICATION
```

Feature-space alignment is a **legitimate methodological fix** for the prose style-tell and is not obviously
infeasible (a neutral, externally-sourced inventory + frozen word-agnostic mappings + a triviality/leakage
audit is a plausible path) — so it is **not** `NOT_FEASIBLE_CLOSE_LINE`. But the crux decisions — how to build
the inventory **independently of the varṇa ontology**, and how to fix the V→feature mapping **without hand-
tuning toward G** — are **unresolved and load-bearing**, exactly the "fragile point" the prose failure warned
about. Calling it `FEASIBLE_TO_SPEC` would understate that the inventory-provenance/circularity problem is the
whole ballgame. Hence **high risk, needs adjudication** before any inventory is specified.

## 13. Next gate

- feasible-to-spec → (not chosen)
- **high risk → `B1_2_FEATURE_SPACE_RISK_ADJUDICATION`** *(recommended)*
- not feasible → `VARNA_LINE_CLOSURE_MEMO`

## 14. Final status block

```
document:                   B1.2 Layer-3 feature-space REDESIGN (memo only; nothing built/run)
decision:                   FEATURE_SPACE_REDESIGN_HIGH_RISK_NEEDS_ADJUDICATION
prose R3 failure:           REMAINS VALID (STOP_NOW_R3_STYLE_TELL_ROBUST_FAIL; ba 0.70, CI [0.5929,0.7929])
B1.2 reopened?:             NO — requires a new feature-space prereg + freeze
B1.1 verdict:               UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
LIMITED_GENERATION_UTILITY: NOT earned
only allowed positive:      MAPPING_FIDELITY_SIGNAL
Track B:                    BLOCKED
Track G / Track F:          RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
next gate:                  B1_2_FEATURE_SPACE_RISK_ADJUDICATION
```

**Structure, not validated meaning.** A feature-space Layer 3 is proposed to bypass the prose style-tell, but
its inventory-provenance/circularity risk must be adjudicated before build; the powered R3 failure stands,
B1.1's verdict is unchanged, B1.2 is not reopened, and Track B remains BLOCKED.
