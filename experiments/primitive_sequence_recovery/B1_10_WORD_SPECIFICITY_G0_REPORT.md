# B1.10 — Gate G0 Word-Set Distinctness Audit — Report (docs-only)

**Final status: `G0_NOT_TESTABLE_WITH_CURRENT_PROSE_PACKETS`.** The deterministic, representational audit
executed the frozen mechanical selection rule from `B1_10_WORD_SPECIFICITY_PREREG.md` (Rev 3, commit
`658a6475`). **No context authored, no harness built, no judge run, no evidence-freeze declaration, no run01
change, no new experiment number.** No word set was selected (none qualifies). Structure, not validated
meaning. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; B1.4b′ `NULL_RETURN_BOTTOM`; original B1.4b blocked; Track
B blocked; no ontology / semantic-truth / Sanskrit-privilege / generation-utility / individual-varṇa claim.

---

## 1. What ran

`b1_10_g0_word_set_audit.py` — purely representational. For each candidate word it derived the varṇa sequence
from the **frozen active mapping** (`varna_bridge_active`, era `fidelity_bundle_v1`, table v3, bridge
`bridge_v2_plus_theta_eth_ta`) and the Tier-3 facet sets from the **frozen facet map**
(`build_b1_10_control_ext.VARNA_PLAIN`), computed the pre-registered overlap metrics, and applied the rule
exactly. **No network / model call.** (Semantic similarity is supplementary — §5.)

## 2. Candidate pool and validity

- **37 candidate words** (the frozen §8 pool, assembled for phonetic breadth, never for semantic fit).
- **Decisive structural limit:** the frozen facet map renders only **11 varṇas**
  (`ba da ga ka la ma na pa ra ta tta`). Any word decomposing into a varṇa outside these 11 has **no facet
  render → invalid packet**. **21 of 37 candidates are invalid** on this basis, e.g. love/wonder/aversion/…
  (`va`), trust/desire/focus/… (`sa`), hope/humility (`ha`), joy (`ja`), shame (`sha`), anger/craving (`nga`),
  attachment/detachment (`ca`), envy/clarity/equanimity (`ya`).
- **16 valid candidates** (all varṇas renderable, no target-word leakage): ambition, boredom, calm,
  contentment, control, courage, doubt, faith, fear, freedom, gratitude, greed, grief, patience, peace, pride.

Varṇa frequency among the 16 valid words: `ra`×9, `ta`×6, `da`×6, `ka`×6, `ma`×5, `na`×4, `ga`×4, `ba`×3,
`pa`×3, `la`×2, `tta`×1 — i.e. a handful of varṇas dominate, so packets overlap heavily.

## 3. Result of the frozen selection rule (k=6)

Examined **all 8008** size-6 subsets of the 16 valid words:

| filter | subsets passing |
|---|---|
| max pairwise facet-Jaccard ≤ 0.34 | 344 |
| mean pairwise facet-Jaccard ≤ 0.20 | 4729 |
| **per-word ≥ 1 unique discriminating facet** | **0** |
| **all three (eligible)** | **0** |

**The Jaccard caps are satisfiable** (min achievable max facet-Jaccard = **0.25**; min achievable mean =
**0.067**). The **binding failure is the per-word distinctiveness requirement**: in *every* size-6 subset, at
least one word's varṇas are a subset of the others' → that word has **zero** facets no other subset member
also has. With only 11 renderable varṇas and `ra` alone in 9 of 16 words, six mutually-distinguishable packets
cannot be formed. **`n_eligible_subsets = 0` → `G0_NOT_TESTABLE_WITH_CURRENT_PROSE_PACKETS`.** No best-effort
set was selected; caps were **not** relaxed.

## 4. Old six-word set (for context only — not a candidate for reuse)

`{pride, freedom, patience, courage, control, doubt}`: max facet-Jaccard **0.50**, mean **0.180**; per-word
unique-facet counts `control 2, courage 1, doubt 1, freedom 1, patience 0, pride 0` → **patience and pride
have zero distinctive facets** (pride ⊂ others, patience ⊂ others). It fails both the max cap and the
per-word-uniqueness rule — confirming, mechanically, the Appendix-A/prereg concern that the run01 set is
unsuitable for word-specificity.

## 5. Semantic-similarity status

**`PENDING_SUPPLEMENTARY`.** The frozen selection/tie-break rule (min max facet-Jaccard → min mean
facet-Jaccard → min mean lexical-Jaccard → alphabetical) does **not** use semantic similarity; it is a
supplementary reporting metric only. No embedding model/revision is pinned in the prereg. Because it is **not
required for selection**, its absence does **not** block G0 (this is **not** `G0_BLOCKED_MISSING_SEMANTIC_SIM_
SPEC`). It was **not** computed (no network/model call) and is labelled pending/supplementary.

## 6. Confirmations

- **Semantic correctness was never inspected or used** — selection used only overlap / length / distinctiveness
  metrics (`semantic_correctness_inspected = false`).
- **No post-hoc relaxation** of caps; **no best-effort set** selected.
- **Determinism (tests, 10 passed):** repeated runs produce byte-identical artifacts; candidate-list ordering
  does not change the result (all internal orderings sorted; tie-break ends alphabetical); the facet↔varṇa
  bijection holds (facet-Jaccard binding == liberating == varṇa-Jaccard); no network/model import; no frozen
  artifact, run01, packet, context, or judge configuration modified.

## 7. Machine-readable artifacts (`b1_10_g0_audit/`)

| file | sha256 (first 16) | contents |
|---|---|---|
| `candidate_table.json` | `56adebe9eb9afa14` | per-word varṇa seq, facet count, missing varṇas, validity, leakage, packet lengths |
| `pairwise_binding.json` | `793dd310d6b19539` | binding pairwise: shared varṇas, shared/unique facet counts, facet-Jaccard, lexical-Jaccard |
| `pairwise_liberating.json` | `ad8af04450fa9556` | liberating pairwise (same fields) |
| `combined_distinctness.json` | `5bb9f0d871ffc373` | per-pair shared/unique varṇa counts, facet-Jaccard, mean lexical-Jaccard, combined overlap |
| `selection.json` | `c7e24344b63e1a8b` | rule constants, valid/invalid lists, subset counts, status, trace, old-six context |
| `b1_10_g0_word_set_audit.py` | `75a96b03bd7ca34d` | the deterministic audit script |

## 8. Readiness for Gate G1 (context design)

**NOT ready.** Gate G0 did not pass. A clean word-specificity test is **not feasible with the current
prose-packet rendering**, because the render map covers only 11 varṇas and no size-6 subset yields
mutually-distinctive packets. Per the prereg, **do not proceed to context authoring** and **do not weaken the
caps**. The honest options (each a *separate, explicitly-approved* decision, none taken here) are:
- **extend the varṇa→facet render map** to cover more varṇas (a mapping-authoring task that would itself need
  pre-registration and its own blinding discipline), enlarging the valid, low-overlap candidate space; and/or
- **change the representation** away from union-of-facet prose packets (e.g. a sequence/composition-level
  instrument) — which moves toward **H2**, explicitly out of scope for the H1 prose-packet program.
Absent one of those, the prose-packet word-specificity test (H1) is **not testable**, and that is itself the
G0 finding.

## 9. Guardrails
Docs-only report of a deterministic, representational audit. No word selected, no context authored, no code
beyond the audit script + tests, no run, no new experiment number; run01 and all frozen artifacts unchanged.
Resonance / phonetic-fidelity refinement only. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no ontology /
semantic-truth / Sanskrit-privilege / generation-utility claim; no individual-varṇa attribution. **B1.4b′
remains `NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B blocked. Structure, not validated meaning.**
