# B1.4 Vṛtti Ground-Truth Adjudication

## 1. Scope and non-rescue rule

Adjudicates **whether any external, non-circular, genuinely-vṛtti ground truth exists** to test the B1.4
vṛtti-native hypothesis. Ground-truth adjudication only: no implementation, no models, no judges, no scoring,
**no EVIDENCE_FREEZE**. Does not change any prior verdict and claims no validation. No
`VRITTI_PROPENSITY_SIGNAL` / `PROPENSITY_MODULATION_SIGNAL` / `LLM_PROPENSITY_FIELD_DISCRIMINATION` /
`LIMITED_GENERATION_UTILITY` / `MAPPING_FIDELITY_SIGNAL` / ontology / Sanskrit / semantic-truth / Track-B claim.
**Structure, not validated meaning.**

## 2. What the ground truth would need to be

A valid vṛtti answer key must be **all** of: **external** to Symbol-U; **predating/independent** of this test;
**genuinely vṛtti** (grasping/release/surrender/ego…), not merely affective/register; at **word/phrase/śloka
level**; **reproducible**; **not selected because it matches the varṇa glossary**; usable **before** scoring;
and able to **distinguish real vs scrambled/deranged/random** controls. Missing any one → not a valid ground
truth.

## 3. Source A — naive human ratings

Naive raters asked "how much *grasping* / *ego* / *surrender* does the word *father* carry?" will either
**infer from the word's meaning** (father→provider→…) — semantic leakage, not vṛtti — or answer
idiosyncratically (**low inter-rater agreement**). **Verdict: subjective impression, not genuinely-vṛtti ground
truth.**

## 4. Source B — LLM ratings

LLMs produce reproducible ratings, but from **learned textual convention and the prompt's own vocabulary** —
if handed the vṛtti dimension words and asked to rate, they rate from their semantic model (which infers from
meaning). No **independent contemplative** ground truth; **circular** with the constructed dimensions. Since
Symbol-U's prediction is sound-driven and the LLM rating is meaning-driven, and sound↔meaning is ρ≈0, a proxy
study would merely re-find the same null. **Verdict: development proxy at best, invalid as ground truth.**

## 5. Source C — trained / cross-tradition raters

Trained raters understand vṛtti, but training **imports the doctrine** → agreement may be **shared-framework
circularity**, not independent perception. Cross-tradition convergence *could* reduce this **only** if the
traditions are genuinely independent — but most vṛtti vocabulary descends from a **shared Indic contemplative
lineage**, so "independence" is doubtful, and demand characteristics are high. **Verdict: high circularity;
not a clean external ground truth.**

## 6. Source D — commentarial tradition

Gita/śāstra commentaries identify **themes** (attachment, surrender, ego, discipline) at the **verse/teaching**
level — about **meaning**, not about a **word-form's sound-propensity** — and are **not word-form-level**.
Mapping their themes to varṇa profiles is **circular if the categories are chosen to match** the glossary.
**Verdict: not an independent word-form-level vṛtti label.**

## 7. Source E — psychological / affective norms

Valence/arousal/dominance/concreteness are **affective**, **not vṛtti** (grasping/release ≠ valence). Useful
only as **confound baselines** (already in the B1.3 spec), never as the vṛtti target. **Verdict: wrong space.**

## 8. Source F — pseudoword impressions

Pseudowords remove convention, but a rater's impression of a pseudoword is an **acoustic/articulatory
impression** = **sound-symbolism (annamaya)** — the level the hypothesis explicitly disowned. Using it as
"vṛtti ground truth" **redefines the hypothesis** into sound-symbolism, which is a different (and already
weak/established) claim, not Symbol-U's manomaya vṛtti. **Verdict: not vṛtti unless the claim is redefined.**

## 9. Source G — first-person / contemplative judgment

This is the **closest to the intended phenomenon** — vṛtti as directly apprehended. But it is **not
third-person, not reproducible, not externally validated**; it is a **contemplative/philosophical** mode of
knowing. Legitimate on its own terms, but **outside the project's empirical evidence standard** by
construction. **Verdict: genuinely-vṛtti but non-empirical.**

## 10. Order-sensitivity blocker

Independent of ground truth: **scrambled ≈ real (cosine 0.967)** means varṇa order carries no information under
any non-tuned composition. **Even if a ground truth existed**, a valid test must first show real ≠ scrambled
without tuning — which the arc's repeated scrambled-ties say it will not. This blocker alone would sink an
empirical vṛtti test.

## 11. Decision matrix

| source | external? | non-circular? | genuinely vṛtti? | word/form-level? | reproducible? | verdict |
|---|---|---|---|---|---|---|
| A naive human | yes | partial | **no** (meaning-inferred) | yes | **low** | invalid |
| B LLM | yes | **no** (meaning+vocab) | **no** | yes | yes | proxy-only, circular |
| C trained/cross-tradition | yes | **no** (doctrine) | yes | yes | low | circular |
| D commentary | yes | **no** if matched | theme, not form | **no** (verse-level) | yes | not word-form GT |
| E affect norms | yes | yes | **no** (affective) | yes | yes | baseline only |
| F pseudoword impression | yes | yes | **no** (acoustic) | yes | moderate | redefines hypothesis |
| G first-person | **no** (internal) | n/a | **yes** | yes | **no** | non-empirical |

**No source satisfies external + non-circular + genuinely-vṛtti + reproducible simultaneously.** The one
genuinely-vṛtti source (G) is non-empirical; every empirical source is either circular, off-target, or
meaning/acoustic-leaking.

## 12. Decision

```
DECISION: VRITTI_GROUND_TRUTH_ABSENT_CLOSE_LINE
```

There is **no external, non-circular, genuinely-vṛtti, reproducible word-level ground truth**. The only source
that is authentically vṛtti (first-person/contemplative) is non-empirical; the only reproducible sources
(LLM/affect/pseudoword) are not vṛtti or are circular. `…FOUND_GO_TEST_DESIGN` is false. `…WEAK_PROXY_ONLY` is
rejected because the sole proxy (LLM ratings) is **circular and meaning-driven** — it cannot distinguish
"Symbol-U works" from "the rating used Symbol-U's own vocabulary," so it isn't even a useful development proxy
for the *sound→vṛtti* question. Compounded by the independent order-sensitivity blocker (§10), the vṛtti-native
hypothesis is **not empirically testable under this project's evidence standard**.

## 13–15. Interpretation and routing

- **Not found / not proxy-viable → the line closes empirically.** The vṛtti hypothesis remains **coherent as a
  contemplative / first-person framework** (source G) — it is not *disproven*; it is **outside the reach of
  third-person falsification**. That is a statement of epistemic category, not a verdict of falsehood, and it
  mirrors the project motto: *structure, not validated meaning.*
- Its verification, if pursued, would be **contemplative** (convergent first-person report under trained
  practice), which is a different tradition of knowing with different standards — not experiments.

```
next gate: VARNA_LINE_CLOSURE_MEMO
```

## 16. Final status block

```
document:                    B1.4 vṛtti GROUND-TRUTH adjudication (adjudication only; nothing run)
decision:                    VRITTI_GROUND_TRUTH_ABSENT_CLOSE_LINE
strongest candidate:         G (first-person/contemplative) — genuinely vṛtti but NON-EMPIRICAL
external + non-circular + vṛtti + reproducible: NO source satisfies all
order sensitivity:           scrambled ≈ real (0.967) — independent blocker; would sink a test even with a GT
ran models / judges / scoring: NO
EVIDENCE_FREEZE:             NONE
social/register field:       CLOSED
vṛtti-native path:           NOT empirically testable (coherent only as contemplative/first-person)
B1.1 verdict:                UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
B1.2 / B1.3 prior:           UNCHANGED (not rescued)
VRITTI_PROPENSITY_SIGNAL / PROPENSITY_MODULATION_SIGNAL / LLM_PROPENSITY_FIELD_DISCRIMINATION: NOT earned
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
Track G / Track F:           RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
next gate:                   VARNA_LINE_CLOSURE_MEMO
```

**Structure, not validated meaning.** No external, non-circular, genuinely-vṛtti ground truth exists, and
order-sensitivity independently blocks a test; the vṛtti-native hypothesis is coherent only as a
contemplative/first-person framework, outside this project's empirical standard. Nothing was run or scored, no
prior result changed, Track B remains BLOCKED, and the honest next step is the varṇa-line closure memo.
