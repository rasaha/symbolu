# B1.3 — Lexicon-Source Audit (bridge pool vs authoritative varṇa lexicon)

## 1. Scope

Integrity audit only. Checks whether the B1.3 concrete-object study was built on the **authoritative** varṇa
lexicon, and whether the **bridge pool** it *was* built on faithfully represents that lexicon.
**No lexicon edit · no v2 change · no judge run · no scoring · no EVIDENCE_FREEZE · no positive label.**
**Structure, not validated meaning.**

## 2. Provenance (the core finding)

- **B1.3 v2 stimuli were built on** `b1_2_varna_bridge_pool.json` (via `ArmBuilder`).
- **That bridge pool's `source_lexicon`** is `b1_1_experimental_contrastive_lexicon_draft.json`, and it is
  self-tagged **`FALLBACK_QUALIFIED`**: *"Generated under weaker LOCAL lexical fallback; the real embedding gate
  remains BLOCKED_DEPENDENCY_UNAVAILABLE (huggingface.co egress-denied) and is still owed."*
- **The authoritative lexicon** `varna_lens/lexicon_authoritative_varna.json` (source *Sanskrit_letters_full.docx*,
  user-confirmed AUTHORITATIVE) **was NOT used.**

So the primary evidence line was built on a **fallback-qualified experimental draft**, not the authoritative
source.

## 3. Pole-direction check — PRESERVED (no swap)

Across all **34** consonants, the bridge pool's `binding_expression` is a bound/distorted state and its
`liberating_expression` is a freed/positive state — **no binding/liberating pole was swapped.** (A crude token-
overlap heuristic flagged 2 "flips": `dda` is a **false positive** — direction is correct; `ha` is a construct
reframe, not a swap.) This is the reassuring half: the study is **not wrong-direction.**

## 4. Construct fidelity — 29 faithful, 5 drifted, 0 flips

- **29/34 faithful paraphrases** — same construct, reworded (e.g. envy→"sting at another's success",
  fear→"collapse/flight before danger", greed→"hoarding"). Low token-overlap here is just rewording, not drift.
- **5/34 construct drift** — the bridge pool shifted the underlying concept:

| varṇa | authoritative binding | bridge-pool binding | drift |
|---|---|---|---|
| `ca` | confused / lack-of-discrimination | discernment hardened into judgment/pride | different distortion |
| `va` | Dharma / sustaining-order / righteousness | truth-assent / discernment | axis reframed |
| `ha` | Darkness / Night / Inertia (tamas) | higher-knowledge-owned-as-pride | different construct |
| `ra` | annihilation / defeatist destruction | + compulsion / desire / projection | construct widened |
| `sa` | Escapism / premature-withdrawal | sattvic-clarity-owned-as-superiority | different construct |

## 5. Impact on the study

**28 of 53** primary concrete objects (**53%**) route through at least one construct-drifted varṇa
(`ca`/`va`/`ha`/`ra`/`sa`) — e.g. rope (`ra`), wall/window/wheel/well (`va`), box/basket/stone/sand/seed (`sa`),
hammer/house (`ha`), chair/branch (`ca`+`ra`). So the drift is not a corner case; it touches over half the A_real
stimuli.

## 6. Decision

```
DECISION: LEXICON_SOURCE_REBUILD_ON_AUTHORITATIVE_REQUIRED
```

Rationale: the bridge pool is **self-labeled FALLBACK_QUALIFIED** and derives from an experimental draft, not
the authoritative lexicon; **an authoritative lexicon exists**; **5 varṇas show genuine construct drift touching
28/53 objects.** Freezing the *primary* evidence line on a fallback source when an authoritative one is
available is **not defensible.** This is not `…BRIDGE_POOL_ACCEPTABLE` (a fallback source + real drift is not
acceptable for a frozen evidence run) and not `…HIGH_RISK_NEEDS_ADJUDICATION` (the fix is clear: use the
authoritative source).

**Honest caveat (no rescue):** pole direction is intact, so the current study is not *wrong*, and the rebuild is
**unlikely to change the outcome** — the semantic baseline still names object-function directly and the prior
stays low. The rebuild is about **using the correct authoritative source**, not about improving A_real's odds.
It must be run whichever way the result lands.

## 7. Next step (follow-on gate, not executed here)

Build an **authoritative-sourced pool** from `lexicon_authoritative_varna.json` (`binding_state` /
`liberating_state` per varṇa), regenerate B1.3 stimuli as **v3-authoritative** with the *same* deterministic
pipeline + global register polish, re-run all audits, then re-do the freeze review. v2 preserved as historical.

## 8. Final status block

```
document:                    B1.3 LEXICON-SOURCE AUDIT (bridge pool vs authoritative)
decision:                    LEXICON_SOURCE_REBUILD_ON_AUTHORITATIVE_REQUIRED
built on authoritative:      NO (built on FALLBACK_QUALIFIED bridge pool from experimental draft)
pole direction:              PRESERVED across 34 (no swap)
construct fidelity:          29 faithful / 5 drift (ca,va,ha,ra,sa) / 0 flips
objects affected:            28 / 53 primary objects route through a drifted varṇa
outcome impact:              LIKELY NONE (semantic baseline still dominates; prior low) — rebuild is for source-correctness
next:                        build authoritative pool -> regenerate v3-authoritative -> re-audit -> freeze review
ran judges / scoring:        NO
EVIDENCE_FREEZE:             NOT declared
prior nulls:                 PRESERVED (B1.1 LLM null; B1.2/B1.3 automated; scrambled≈real 0.967; Track G; Track F)
B1.3 register-field:         CLOSED    | B1.4 vṛtti ground-truth: CLOSED
LLM_OBJECT_MODULATION_SIGNAL / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
ontology / Sanskrit / truth: NONE
```

**Structure, not validated meaning.** B1.3 v2 was built on a FALLBACK_QUALIFIED bridge pool derived from an
experimental draft, not the authoritative varṇa lexicon; pole direction is intact but 5 varṇas drift in
construct and touch 28/53 objects, so a rebuild on the authoritative lexicon is required before freezing the
primary evidence line — a source-correctness fix, not a rescue, with outcome impact expected to be none. No
lexicon was edited, v2 is unchanged, nothing was run or scored, prior nulls stand, Track B remains BLOCKED, and
EVIDENCE_FREEZE is not declared.
