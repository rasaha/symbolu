# B1.2 Alternate-Inventory Empirical Probe — blind V→hypernym projection

## Status: `ALT_INVENTORY_V_PROJECTION_TRIVIAL_STOP_NOW`

## 1. Scope guard

Feasibility/triviality probe **only**. It does **not** test Symbol-U success, does **not** run final
mapping-fidelity scoring or V↔G alignment, and makes **no** mapping-fidelity / utility / ontology / Sanskrit /
semantic-truth claim. It tests one thing: **can the varṇa prediction V be blindly projected into WordNet-
hypernym space (without target-word lookup) in a way that is non-trivial and word-specific?** B1.1 stays
`RANDOM_OR_SCRAMBLED_MATCHES`; Track B stays BLOCKED. **Structure, not validated meaning.**

## 2. Frozen target set

Loaded the frozen 70-word set; hash **verified** = `fe7aa7ac…`. No add/remove/replace.

## 3. Feature representation

**WordNet 3.0 hypernym-ancestor synsets** (bag), sparse L1-normalized vectors over the union hypernym space
(**5,391** synsets; G-side vocab a subset). Finer than lexnames; the G side separates near-neighbors (§7).
**Honest caveat:** a bag-of-hypernyms projection is **order-invariant**, so **V_scrambled ≡ V_real exactly** —
this representation cannot even express the Axis-2 varṇa-order control.

## 4. G-side adequacy

G vectors (target + ≥10 neighbor lookups; target-word lookup allowed) are non-degenerate and separate
near-neighbors: father~teacher 0.686, water~ocean 0.556, justice~law 0.465. **The G side works.**

## 5. V-side blind projection method

**Method C** (deterministic, blind): project V by looking up **only the V bridge-gloss words** in WordNet and
bagging their hypernym ancestors — the **target word is never looked up** (guard-asserted `w not in
bridge_words` for all 70). V_real from `core_A`; V_deranged from another target's `core_A` (cyclic shift);
V_random from `core_R_same`. No dictionary, no G, no synonym set, no target synset.

## 6. Triviality check results (the decisive evidence)

| quantity | value | reading |
|---|---|---|
| V_real → G(target) | **0.5194** | |
| V_real → G(random off-target) | **0.5147** | **margin 0.0046 ≈ 0** — V matches its own word no better than a random word |
| V_real top-1 matches own G | **0.014** | = chance (1/70) — no word-specific signal |
| V_deranged → G(target) | **0.5118** | ≈ V_real — another word's varṇa fits just as well |
| V_random → G(target) | **0.5651** | ≥ V_real — random bridges fit *better* |
| beats deranged & random | **False** | |
| mean density | 0.034 | not collapsed / not all-zero (all-zero rate 0.0) |
| mean entropy | 4.85 | |
| top-feature dominance | 0.039 | |
| universal features (≥90% of V) | **16** | abstract glosses collapse to a few high-level hypernyms shared by all words |

**Required fail conditions triggered:** V_real similarity to random G ≈ to target G (margin ~0); V_deranged
and V_random perform ≥ V_real; V vectors dominated by universal high-level features. → **trivial / generic**.

## 7. Near-neighbor adequacy — split verdict

- **Inventory (G side): adequate** — hypernym features separate the near-neighbor pairs.
- **Blind V projection: inadequate** — V does not land word-specifically; the same abstract varṇa glosses map
  to the same generic hypernyms for every word.

## 8. Controls

V_deranged (another word's varṇa) ≈ V_real, and V_random ≥ V_real. The controls are **not** beaten — the
signature of no word-specific signal. This is **not** treated as any kind of positive result.

## 9. Decision

```
DECISION: ALT_INVENTORY_V_PROJECTION_TRIVIAL_STOP_NOW
```

The blind V→hypernym projection is technically runnable (non-collapsed, target-word-blind) but **trivial and
generic**: it carries no word-specific information (margin ≈ 0, top-1 at chance, deranged ≈ real, random ≥
real). `…_FEASIBLE_GO_SPEC` is not met; `…_COLLAPSES` is not the mode (vectors are non-empty); this is the
**triviality** failure.

## 10. Interpretation — the failure is V-content-based, not inventory-based

`V_deranged ≈ V_real` is the key: **another word's varṇa gloss fits a target's dictionary as well as the
target's own** does. That deficit lives in **V's content** — the varṇa bridge glosses are abstract themes that
recur across all words — and is therefore **inventory-independent**. This directly echoes the B1/B1.1
`RANDOM_OR_SCRAMBLED_MATCHES` finding (generic resonance, no word-specific fit) and Track G
`RANDOM_POLARITY_EXPLAINS`. A finer measuring stick cannot recover a word-specific signal that is not in V.

## 11. Next gate

- **Recommended: `VARNA_LINE_CLOSURE_MEMO`.** The triviality failure is inventory-independent (V is not
  word-specific), so the feature-space redesign does not rescue the line.
- *Remaining-but-unlikely alternative:* `B1_2_FRAMENET_PROVISIONING_REVIEW` — the task's escape hatch if the
  failure were *specifically* a hypernym-inventory mismatch. The evidence argues against it: because
  V_deranged ≈ V_real, the deficit is V's word-non-specificity, not the inventory's granularity, so FrameNet
  is unlikely to help and would need explicit justification before spending provisioning effort.

## 12. Final status block

```
document:                   B1.2 alternate-inventory EMPIRICAL PROBE (feasibility/triviality only)
decision:                   ALT_INVENTORY_V_PROJECTION_TRIVIAL_STOP_NOW
V_real→G_target / off-target: 0.5194 / 0.5147 (margin 0.0046); top-1 own-G = 0.014 (chance)
V_deranged / V_random → G:  0.5118 / 0.5651 (controls NOT beaten)
feature space:              WordNet hypernym bag (union 5391); G side separates near-neighbors, V side does not
V_scrambled:                ≡ V_real under order-invariant bag (Axis-2 order not expressible here)
failure locus:              V content (word-non-specific), inventory-independent — echoes B1/B1.1 null
powered R3 prose failure:   REMAINS VALID (ba 0.70, CI [0.5929, 0.7929])
B1.2 reopened for evidence: NO
B1.1 verdict:               UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
LIMITED_GENERATION_UTILITY: NOT earned
MAPPING_FIDELITY_SIGNAL:    NOT earned
Track B:                    BLOCKED
Track G / Track F:          RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
next gate:                  VARNA_LINE_CLOSURE_MEMO (FrameNet review remaining but unlikely)
```

**Structure, not validated meaning.** The blind varṇa→hypernym projection is generic and word-non-specific;
the deficit is in V, not the inventory, so a finer external feature space does not rescue the line. The
powered R3 failure stands, B1.1's verdict is unchanged, B1.2 is not reopened, and Track B remains BLOCKED.
