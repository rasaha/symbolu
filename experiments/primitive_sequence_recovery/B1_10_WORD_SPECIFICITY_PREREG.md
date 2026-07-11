# B1.10 — Word-Specificity Follow-up Preregistration (docs-only)

**Docs-only preregistration.** No code, no scaffold, no run, no new experiment number. Stays under B1.10.
Motivated by `B1_10_CONTROL_EXT_V3_RESULTS.md` Appendix A.4: run01 tested **pole / source-condition
discrimination** and found the varṇa packets add no value over a generic source-condition control; it did
**not** test **word-specificity**. This document pre-registers a clean word-specificity test. Resonance /
phonetic-fidelity refinement only. **No `GENUTILITY_*`, no `ONTOLOGICAL_SIGNAL`, no semantic-truth / ontology /
Sanskrit-privilege / generation-utility claim, no individual-varṇa attribution.** B1.4b′ remains
`NULL_RETURN_BOTTOM`; original B1.4b blocked; Track B blocked. **Structure, not validated meaning.**

---

## 0. Question

Does a word's **own** Tier-3 (varṇa-derived) packet fit **that word's** context better than a **different
word's** same-pole Tier-3 packet does? Pole legibility (run01) and word-specificity (this) are **separate
hypotheses**; a null in one does not settle the other.

## 1. Words (unchanged)

pride, freedom, patience, courage, control, doubt.

## 2. Core design — 6×6 packet-source × target-word confusion

For each **target word** and each of its contexts, judges rate the fit of:
- the **target word's own** Tier-3 packet (same pole as the context), **and**
- each of the **other five words'** corresponding-pole Tier-3 packets.

This yields a **6×6 matrix** (rows = packet-source word, columns = target word/context), built **separately
for binding contexts and for liberating contexts**. The diagonal = own-word packet on own-word context.

Cell count (before the masking factor, §5.3): 6 targets × 2 poles × 6 packet-sources = **72 fits per judge**
in the word-visible arm. (This is a *different* 72 from run01: run01 crossed tiers×poles within a word; this
crosses packet-source×target within a pole.)

## 3. Primary word-specificity statistic

For a target word *w* and pole *p*:
```
own_word_advantage(w, p) = fit(own_packet(w,p) | context(w,p))
                           − mean_{v≠w} fit(packet(v,p) | context(w,p))
```
Report per pole (binding, liberating), then combined (mean over poles). Aggregate = mean over the six words.
Also report the diagonal mean and off-diagonal mean of each 6×6 matrix.

## 4. Required controls

**4.1 Tier-2 word-blind baseline (calibration, not a competitor).** Apply the *single* generic Tier-2 packet
(same for every word) to every target context. By construction it has **no own-word diagonal** (it is
identical across packet-sources), so its `own_word_advantage ≡ 0`. It calibrates the floor and confirms the
statistic behaves; it is **not** treated as a competing word-specific packet.

**4.2 Same-pole matching.** Binding packets are rated **only** against binding contexts; liberating packets
**only** against liberating contexts. Cross-pole cells are excluded by design so that generic pole/valence
cannot drive the own-vs-other comparison — every comparison in a matrix holds pole constant.

**4.3 Target-word visibility audit (two arms).** Run **both**:
- **Arm A — word-visible context** (as written).
- **Arm B — target-word-masked context** (the target token replaced by a neutral placeholder, e.g. "the
  feeling" / "it", leaving the situation intact).
Compare `own_word_advantage` across arms. If a positive advantage appears **only** in Arm A, judges are
matching packets to **ordinary lexical knowledge of the word**, not to contextual source-condition; Arm B is
the stricter test of context-carried word-specificity. Masking rules (placeholder token, capitalization,
determiners) are frozen here before any run.

**4.4 Packet-length / register parity.** Tier-3 packets already share the plain-English rendering rules
(§build_b1_10_control_ext). Re-check per-source-word length and style parity before the run; **no packet may
contain its own target word** (already guaranteed by the blinding leak-check, re-verified here).

**4.5 Repeated-varṇa / packet-overlap audit (PRE-REGISTERED, decisive constraint).** The six words share many
varṇas, so their Tier-3 packets share facets:
```
pride pa·ra·da   freedom ra·da·ma   patience pa·ta·na·ka   courage ka·ra·ga   control ka·na·ṭa·ra·la   doubt da·ba·ta
```
`ra` ∈ {pride, freedom, courage, control}; `da` ∈ {pride, freedom, doubt}; `ka` ∈ {patience, courage,
control}; `ta` ∈ {patience, doubt}; `pa` ∈ {pride, patience}; `na` ∈ {patience, control}. Shared varṇas →
shared (identical-text) facets → **high off-diagonal similarity**, which **structurally suppresses**
`own_word_advantage` even if the mapping "worked." Before running, compute and report a **6×6 facet-overlap
matrix** (fraction of shared facet clauses) and a lexical-Jaccard matrix among the packets. Pre-registered
handling: **report every pair; interpret own_word_advantage conditional on packet distinctness; do NOT exclude
high-overlap pairs after seeing ratings.** A near-zero advantage for a pair whose packets are ~identical is
*expected* and must not be reported as a failure of word-specificity — it is a limitation of the word set.

## 5. Judge blinding

Judges receive only {target context sentence (Arm A or B) + one packet + the 0–6 question}. They must **not**
know: which packet is the target word's own; which word generated the packet; the expected diagonal; or the
hypothesis direction. Packet order randomized per target; same leak-checks as run01 (no pole/varṇa/system
tokens, no target words in packets, ASCII-only). Same official panel and independence rules
(`B1_10_OFFICIAL_JUDGE_PANEL_SPEC.md`): J0/J1/J2 Llama/Gemma, greedy/temp 0, no Claude/Mistral/Qwen judges.

## 6. Statistics (report all)

- full **6×6 matrices** for binding and for liberating contexts (per judge and pooled), each arm (A, B);
- **diagonal mean** and **off-diagonal mean** per matrix;
- **own_word_advantage per target word** (per pole and combined);
- **aggregate own_word_advantage**;
- **judge-level** results before pooling;
- **leave-one-word-out** and **leave-one-judge-out** sensitivity;
- the §4.5 facet-overlap and lexical-Jaccard matrices alongside, for conditional reading;
- missing-data / inconclusive rule identical to run01 (drop+redraw ≤2; >15% missing → inconclusive).

## 7. Interpretation (bounded)

- **own_word_advantage > 0** → **word-specific packet legibility to judges only** — nothing more.
- **own_word_advantage ≈ 0** → **no detectable word specificity** (or the word set's varṇa overlap is too high
  to detect it — distinguished via §4.5).
- **own_word_advantage < 0** → **wrong-word packets fit as well or better** — evidence against word-specific
  packet content.
- Arm A > Arm B gap → the apparent specificity is **lexical word-knowledge**, not contextual source-condition.
- In **all** cases: no ontology, semantic-truth, Sanskrit-privilege, generation-utility, or individual-varṇa
  claim; B1.4b′ remains `NULL_RETURN_BOTTOM`.

## 8. DESIGN QUESTION (resolve BEFORE any implementation) — are the run01 contexts suitable?

**Do not auto-reuse the six approved run01 contexts merely because they passed the pole-discrimination audit.**
Assessment:

- The run01 contexts were authored to instantiate the **generic Condition A/B (outside vs inner) axis** — by
  design they are **pole-generic**: a "self-grounded" freedom sentence and a "self-grounded" pride sentence
  differ mainly by the **target word token**, not by word-specific *situational content*.
- Consequence for Arm B (masked): once the target word is removed, pole-generic contexts become **nearly
  interchangeable across words**, so `own_word_advantage` is **≈ 0 by construction** — the masked test would be
  uninformative (a floor artifact, not a finding).
- Consequence for Arm A (visible): any positive advantage would likely reflect **lexical matching to the
  visible word**, which §4.3 explicitly flags as *not* the target construct.
- **Provisional conclusion: the run01 contexts are NOT well-suited to a word-specificity test.** A proper test
  most likely needs **new contexts** that carry **word-specific situational content** (situations
  characteristic of each word's ordinary meaning) rather than pole-generic templates — so that a word's own
  packet has something word-specific (beyond the token) to match, and Arm B is informative.
- **Compounding structural limit:** even with better contexts, the §4.5 varṇa overlap caps how much
  own-vs-other separation is achievable with *this* six-word set. A cleaner word-specificity test might require
  a **new word set chosen for low pairwise varṇa overlap** (a separate design decision, not assumed here).

**Gate:** this design question must be resolved (reuse vs. author new contexts; keep vs. change the word set)
**before** any scaffold or run is built. This document does **not** approve reuse, does **not** author
contexts, and does **not** build anything.

## 9. Guardrails
Docs-only preregistration. No code, no scaffold, no run, no new experiment number; nothing under B1.10 is
changed by this document. Resonance / phonetic-fidelity refinement only. No `GENUTILITY_*`; no
`ONTOLOGICAL_SIGNAL`; no semantic-truth / ontology / Sanskrit-privilege / generation-utility claim; no
individual-varṇa attribution. **B1.4b′ remains `NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B blocked.
Structure, not validated meaning.**
