# B1.2 G(word) Function Spec — dictionary-differential answer-key builder

## 1. Scope and non-rescue rule

Specifies **`G(word)` only** — the dictionary-derived differential **answer key** the varṇa prediction
`V(word)` must align with. This is a **spec only**: no implementation, no models, no packet generation, no
judging, no scoring. It does **not** change or rescue B1.1, does **not** authorize implementation, and makes
**no** claim of generation utility, ontology validation, Sanskrit privilege, semantic truth, or Track-B
unblock. B1.1 stays `RANDOM_OR_SCRAMBLED_MATCHES`; Track B stays BLOCKED. **Structure, not validated meaning.**

## 2. Definition of G(word)

**`G(word)` = dictionary-derived differential answer key.** Built mechanically from:

1. the **target word's dictionary meaning**;
2. **≥10 synonyms / near-neighbor** definitions;
3. **shared-feature extraction** (features common across target + neighbors);
4. **target-specific residual extraction** (what distinguishes the target after removing shared features);
5. a **fixed rendering format**.

`G(word)` is **NOT** derived from: varṇa; Sanskrit labels; `V(word)`; any B1/B1.1 judge output; or any
generation result. Human meaning enters only through **published dictionaries**, via a **uniform procedure**,
never per-word hand-authoring keyed to the answer.

## 3. G/V independence

- **G never reads varṇa** (no phoneme skeleton, no gloss table, no `read_op`).
- **V never reads G** (no dictionary definition, no synonym set, no answer key).
- **G and V are independent pipelines** computed separately; they meet **only** at the alignment-scoring step.
- This **non-circularity is the basis of B1.2**: "does the varṇa-only prediction land on the dictionary-only
  answer key" is meaningful *only* because neither pipeline can see the other's output.

## 4. Input requirements (per target word)

- target word;
- named **dictionary source(s)** (with edition/version);
- **≥10 synonyms / near-neighbor terms**;
- **definitions** for the target and each synonym/neighbor (from the same source policy);
- optional **part-of-speech** constraint (sense disambiguation);
- optional **domain tag**;
- **source provenance** for every definition (source id + retrieval date/version + hash).

## 5. Synonym / neighbor selection

- Draw candidates from a **named dictionary/thesaurus source**, **WordNet** synsets if available, and/or
  **embedding-nearest lexical neighbors** (named model, fixed k) — the exact source(s) pinned in the freeze.
- **Human review only under fixed, pre-registered rules** (e.g. "keep the top-N by the frozen metric that
  share the target's part of speech"), **never per-result tuning**.
- **Freeze the synonym list before computing G** for that word.
- **No post-hoc synonym replacement** — a neighbor may not be swapped after seeing G, V, or any alignment.
- Selection must be **word-agnostic** (same rule for every target) and must **not** consult varṇa or V.

## 6. Shared-feature extraction

- Extract the **features common** across the target and its synonym set — the broad category features and
  features shared with most near neighbors.
- Keep a **structured list** (not prose), one feature per item.
- If LLM-assisted, use the **same frozen prompt / model / decoding for every word**.
- **No varṇa input**; no access to V or G_target's eventual residual.

## 7. Target-specific residual extraction

- **Subtract** the shared features from the target's definition.
- **Retain** the features that distinguish the target from its near neighbors.
- Produce a **concise, structured differential residual** — short, and **format-comparable to V** (§12).
- **No hand-polished per-word prose** after extraction: the residual is whatever the frozen procedure emits.
  Post-hoc editing of a word's residual is a STOP_NOW trigger (§16).

## 8. Mechanical options for G

- **A. Rule/template only** — deterministic dictionary feature extraction (parse definitions, set-difference
  features). *Safest / fully reproducible, but brittle on messy real definitions.*
- **B. LLM-assisted with a frozen prompt** — dictionary definitions in, structured residual out; **same
  prompt/model/decoding for all words**; **no varṇa input**; must be frozen and hash-bound. *Highly
  implementable, but requires strict freezing and a leakage/consistency audit.*
- **C. Hybrid** — deterministic dictionary/thesaurus/WordNet **retrieval** + LLM **extraction under a frozen
  prompt** + **validation by lexical audits** (feature-overlap checks, format checks). *Best balance of
  robustness and reproducibility.*

**Recommended: C (Hybrid).** Deterministic where the data allows (retrieval, synonym selection, tiering);
frozen-prompt LLM only for the extraction/subtraction step that plain rules handle brittly; every step
audited and hash-bound. See §17.

## 9. Output schema

G is **structured JSON**, never a free-form essay:

```json
{
  "target_word": "…",
  "part_of_speech": "…",
  "target_definition": "…",
  "synonym_set": ["…", "… (≥10)"],
  "synonym_definitions": {"syn": "def", "…": "…"},
  "shared_features": ["…"],
  "target_specific_features": ["…"],
  "excluded_neighbor_features": ["…"],
  "differential_summary": "concise, format-matched to V (§12)",
  "provenance": {"sources": ["dict@version"], "retrieved": "…", "hashes": {"…": "…"}},
  "extraction_method": "hybrid | rule | llm-frozen",
  "hash_inputs": "sha256 over frozen inputs (defs + synonym set + prompt + seeds)"
}
```

The judge-facing artifact is a **blinded** projection of this (e.g. `differential_summary` +
`target_specific_features`), never the raw record with provenance/labels.

## 10. G-side distractors (Axis 1 answer keys)

The answer keys `V(target)` is scored against (all produced by the **same** G procedure):

- **G_target** — the correct key;
- **G_near**, **G_mid**, **G_far** — wrong-word keys at increasing semantic distance (§11);
- **G_same** — random same-pool word's key (distance-free);
- **G_domain** — mismatched-domain word's key;
- **generic_symbolic** — non-varṇa reflective text, retained as an answer-key-like floor.

These are **Axis 1** (word-specificity) controls, distinct from the Axis 2 prediction ablations bound in the
V-function spec.

## 11. Semantic-distance tiering

- **near / mid / far** tier assignment is **frozen before scoring**, by a documented procedure: embedding
  similarity (named model, pre-registered thresholds) and/or WordNet distance and/or fixed human-blind
  grouping.
- **No post-hoc reassignment**; divergent cases resolved by pre-set rule or dropped.
- Tiering is computed from **word–word semantic distance only** — **independent of any V score** and of G's
  residual content, so tiers can't be tuned to the result.

## 12. Alignment compatibility with V

- **G output must be comparable to V output** so the judge scores *fit*, not *style*.
- If V is **prose bridge**, G's `differential_summary` must be **concise, comparable feature text** of matched
  length/register.
- If V is a **feature list/vector**, G must **expose a feature list** for like-for-like comparison.
- **Avoid stylistic advantage** in either direction: length, register, ornateness, and clause count matched
  across V, G_target, and every distractor key.
- The V-side format wrapper (V-spec §4 task 1) and G's rendering format are pinned **together** at freeze so
  neither carries a surface tell.

## 13. Dictionary-only baseline relation

- **G is the answer key.** It is never a prediction arm and is never "scored for word-fit on its own."
- **`core_D` / dictionary-only is an Axis-2 prediction baseline** (V_removed) — the ceiling/sanity + mechanism
  probe.
- **Do not confuse G with core_D.** Both touch dictionaries, but G is the *target* the varṇa prediction must
  hit, while core_D is a *predictor* used to sanity-check that the alignment machinery works and to bound how
  much varṇa adds. `core_D` may be aligned against G_target as a ceiling check; **G itself never acts as a
  prediction.**

## 14. Leakage controls

- **No varṇa / Sanskrit labels** in G, and no gloss-table content.
- **No arm labels** in judge-facing packets.
- **No source-word leakage** in judge-facing packets beyond the allowed **target word** (wrong keys must not
  reveal which word they came from).
- **No V text** enters G construction; **no B1.1 output** (judge/scoring/generation) is used anywhere in G.
- Leak scan of every judge-facing G projection before freeze.

## 15. Freeze requirements

Before any B1.2 run, freeze and hash-bind: the **target word set**; **dictionary sources** (with versions);
**synonym sets**; **definitions**; the **G extraction method** (prompt/model/decoding if LLM-assisted); the
**G outputs**; the **near/mid/far tiers**; the **G-side distractor assignments**; and **all input hashes** —
under the **new B1.2 manifest** (with the bound V artifacts). No post-hoc edits (`INVALID_POSTHOC`).

## 16. STOP_NOW conditions

Default to **`STOP_NOW`** (per the prereg default rule) if any of:

- G requires **manual per-word writing** (no word-agnostic procedure exists);
- synonym sets **cannot be frozen** (unstable/non-reproducible neighbor selection);
- target-specific residuals are **hand-polished** after extraction;
- G **leaks varṇa or V** (independence broken);
- G is **too stylistically different from V** to compare fairly (uncontrollable surface tell);
- **tiering cannot be frozen** independently of V scores;
- dictionary sources are **unstable/unavailable** (non-reproducible provenance);
- G **cannot be generated consistently** across words by the same procedure.

## 17. Recommended method

**Hybrid (Option C):** deterministic dictionary/thesaurus/WordNet **retrieval** and synonym selection +
**frozen-prompt LLM extraction** of shared/target-specific features + **deterministic lexical-audit
validation** (feature-overlap and format checks) + **deterministic embedding/WordNet tiering**. Fall back to
**rule/template (Option A)** for any step where a deterministic rule is demonstrably stable, minimizing the
LLM's footprint. The extraction prompt, model, decoding, and seeds are frozen and hash-bound; if the hybrid
cannot be made word-agnostic and reproducible without hand-tuning, **STOP_NOW** (§16).

## 18. Final status block

```
document:                   B1.2 G-function SPEC (spec only; nothing built/run)
status:                     NOT_IMPLEMENTED · NOT_FROZEN · NOT_RUN
G(word):                    dictionary-derived differential answer key (target + ≥10 synonyms → shared-feature
                            subtraction → target-specific residual; fixed JSON schema)
recommended method:         Hybrid (deterministic retrieval/tiering + frozen-prompt LLM extraction + audits)
V function:                 already bound (B1_2_V_FUNCTION_BINDING_SPEC): core_A/S/R_deranged/D/R_same
G ⟂ V:                      REQUIRED until alignment scoring (non-circularity is the basis of B1.2)
B1.1 verdict:               UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
LIMITED_GENERATION_UTILITY: NOT earned
Track B:                    BLOCKED
Track G / Track F:          RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
authorized to run:          NO — requires new B1.2 freeze + prereg review
next gate:                  B1_2_G_FUNCTION_IMPLEMENTATION_PLAN_OR_STOP_NOW
```

**Structure, not validated meaning.** This specifies the dictionary-differential answer key only; G and V
remain independent, the B1.1 verdict stands, Track B remains BLOCKED, and B1.2 cannot run until a new freeze.
