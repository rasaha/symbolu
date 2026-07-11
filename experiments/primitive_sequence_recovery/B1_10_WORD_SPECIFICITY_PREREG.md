# B1.10 — Word-Specificity Follow-up Preregistration (docs-only)

**Docs-only preregistration.** No code, no scaffold, no run, no word selection, no context authoring, no new
experiment number. Stays under B1.10. Motivated by `B1_10_CONTROL_EXT_V3_RESULTS.md` Appendix A.4: run01
tested **pole / source-condition discrimination** (varṇa packets added no value over a generic source-condition
control) and did **not** test **word-specificity**. This document pre-registers a clean word-specificity test.
Resonance / phonetic-fidelity refinement only. **No `GENUTILITY_*`, no `ONTOLOGICAL_SIGNAL`, no semantic-truth
/ ontology / Sanskrit-privilege / generation-utility claim, no individual-varṇa attribution.** B1.4b′ remains
`NULL_RETURN_BOTTOM`; original B1.4b blocked; Track B blocked. **Structure, not validated meaning.**

> **Rev 3 (docs-only).** Hard pre-implementation **word-set distinctness gate (Gate G0, §8)**; re-weighted
> **visibility arms** (word-level Arm A0 + word-visible-context Arm A are primary; masked Arm B secondary,
> §4.3); **two instruments** — 0–6 rating + anonymous forced-choice/ranking (§2–§3, §6); explicit **H1/H2
> scope** (§0.1); **failure modes (§9)**; and a **recommendation (§10)**. Nothing run01 (ratings, results,
> packets, contexts, judges, experiment numbering) is changed; nothing is selected, authored, built, or run.

---

## 0. Question

Does a word's **own** Tier-3 (varṇa-derived) packet resemble **that word** more than a **different word's**
same-pole Tier-3 packet does? Pole legibility (run01) and word-specificity (this) are **separate hypotheses**;
a null in one does not settle the other.

## 0.1 Hypothesis scope — H1 vs H2 (kept firmly separate)

- **H1 — rendered-packet identifiability.** The plain-English Tier-3 packet is identifiable to its source word
  (a word's own packet fits it better than other words' packets). **This preregistration tests H1 only.** The
  whole B1.10 pipeline operates on prose *renderings* of the varṇa facets, so H1 is the most it can reach.
- **H2 — compositional information beyond the summary.** The *ordered varṇa composition* carries information
  lost in the rendered packet. **This preregistration does NOT test H2.**
- Explicit consequences:
  - an **H1 null does not settle H2**;
  - an **H1 positive does not prove individual-varṇa meaning** (no single-varṇa attribution; the packet is a
    bag of constituent-varṇa readings);
  - **H2 would require a structurally different experiment** operating on the varṇa **sequence / facet-set
    composition** directly, not on prose packet summaries.

## 1. Words — PENDING Gate G0 (not fixed, not selected here)

The run01 six (pride, freedom, patience, courage, control, doubt) are **provisional only**. The final word set
is chosen by the mechanical distinctness audit in **§8 (Gate G0)** and is **still pending**. The current six
are **not** retained for continuity.

## 2. Core design — 6×6 packet-source × target-word confusion (two instruments)

After Gate G0 fixes the k = 6 word set, then for each **target word** and pole, the k words' same-pole Tier-3
packets are presented as **anonymous** candidates (no word labels; source hidden; order randomized per target).
Two instruments run over the same anonymous packets:

- **Instrument 1 — independent 0–6 rating.** Each anonymous packet is rated 0–6:
  *"How well does this packet describe the target word in this context?"* (run01-comparable). Yields a **6×6
  fit matrix** (rows = packet-source word, columns = target), separately for binding and liberating.
- **Instrument 2 — anonymous forced-choice / ranking.** All six anonymous same-pole packets shown together;
  the judge **chooses the single best-fitting** packet for the target, and **optionally ranks** all six.
  Yields a **6×6 choice-confusion matrix** and per-target ranks.

Both are repeated across the three visibility arms (§4.3). The diagonal = own-word packet on own-word target.

## 3. Primary statistics

**Instrument 1 (rating) — `own_word_advantage`.** For target word *w*, pole *p*:
```
own_word_advantage(w, p) = own-packet rating(w, p)
                           − mean rating of the other words' same-pole packets on target (w, p)
```
Report per pole, then combined; aggregate = mean over words; also diagonal mean and off-diagonal mean per
matrix. **Report separately for all six arm×pole cells:** word-only binding, word-only liberating,
visible-context binding, visible-context liberating, masked-context binding, masked-context liberating.

**Instrument 2 (forced-choice / ranking):**
- **top-1 own-packet accuracy** (fraction of targets whose own packet is chosen); **chance = 1/6 ≈ 0.167**;
- **mean reciprocal rank (MRR)** of the own packet (chance MRR for k=6 ≈ 0.408);
- **diagonal rank** distribution (rank assigned to the own packet per target);
- **full choice/rank confusion matrix**;
- **tie handling (pre-declared):** ties in the rating that feed a forced choice are broken by the judge's
  explicit pick; if a judge emits a tie in an explicit ranking, assign the **average rank** to tied items
  (standard fractional ranking); a judge refusal/parse-failure follows the missing-data rule (§6).

`own_word_advantage > 0` ⇔ top-1 accuracy > 1/6 ⇔ MRR > chance are the concordant positive signatures. Both
instruments are reported side by side; disagreement is reported as-is, not reconciled.

## 4. Required controls

**4.1 Tier-2 word-blind baseline (calibration, not a competitor).** The single generic Tier-2 packet is
identical across words, so it has **no own-word diagonal** by construction (`own_word_advantage ≡ 0`; forced
choice among six identical texts = chance). It calibrates the floor and confirms the instruments behave; it is
**not** a competing word-specific packet.

**4.2 Same-pole matching.** Binding packets are compared **only** against binding contexts; liberating packets
**only** against liberating contexts. Cross-pole cells are excluded so generic pole/valence cannot drive the
own-vs-other comparison — every comparison holds pole constant.

**4.3 Visibility arms (re-weighted: word-level/word-visible PRIMARY, masked SECONDARY).** Symbol-U's claim is
about the **word** (*pride's sounds encode pride's meaning*). Because packets are **word-blind** (no target
word, no obvious synonyms — §4.4), showing the word does **not** leak the answer: the only thing a judge can
match on is whether the varṇa-derived *content* resembles the word. Run three arms:

- **Arm A0 — word-only, no context (PRIMARY).** Present only `Word: <w>` + the six anonymous same-pole
  packets. On-target H1 test: *does the rendered varṇa packet resemble its source word more than packets from
  other words?* — with no context-generality to dilute it.
- **Arm A — word-visible context (PRIMARY).** The target word plus a natural context sentence containing it +
  the six anonymous packets. Context-anchored version of Arm A0. The judge is never told which packet is the
  target's own, which source word produced any packet, or the expected diagonal.
- **Arm B — target-word-masked context (SECONDARY strictness probe).** Replace **only** the target-word
  occurrence with the literal placeholder `[TARGET]`, leaving the situation intact. A **stricter contextual**
  specificity probe — **not** the primary test — because masking may remove the very **lexical identity the
  Symbol-U claim concerns**. With pole-generic contexts Arm B is ≈ 0 by construction (§8/Gate G1); an Arm-B
  null does **not** override Arm A0 / Arm A, and an Arm-A>Arm-B gap means "specificity is word-level/lexical,
  not context-carried," which is *consistent with* the word claim, not a refutation.

Compare word-only (A0) vs word-visible-in-context (A) vs word-masked-context (B). Primary inference = A0 + A;
B reported alongside per its caveat. Masking rules (placeholder `[TARGET]`, capitalization, determiners) frozen
here before any run.

**4.4 Packet-length / register parity + no leakage.** Tier-3 packets share the plain-English rendering rules;
re-check per-source-word length and style parity within the final set; **no packet may contain its own target
word** (blinding leak-check re-verified). Judge-visible text stays ASCII-only, no pole/varṇa/system tokens.

**4.5 Repeated-varṇa / packet-overlap → handled by Gate G0.** Because a Tier-3 packet is the **union of its
varṇas' facets**, words sharing varṇas share facets and their packets become **near-duplicates** — which makes
`own_word_advantage`/forced-choice **≈ chance by construction**, independent of the theory. This is the
dominant constraint and is resolved **before** anything else by the word-set distinctness gate (§8). Overlap
matrices are reported **alongside every result** for conditional reading; near-duplicate pairs at chance are
**expected**, not a finding, and are **never** dropped post-hoc.

## 5. Judge blinding

Judges receive only {arm-appropriate stem (word, word+context, or masked context) + the anonymous packet(s) +
the question}. They must **not** know: which packet is the target's own; which source word produced any packet;
the expected diagonal; or the hypothesis direction. Same official panel and independence rules
(`B1_10_OFFICIAL_JUDGE_PANEL_SPEC.md`): J0 Llama-3.1-8B, J1 Meta-Llama-3-8B, J2 gemma-2-9b; greedy/temp 0; no
Claude/Mistral/Qwen judges. Same fail-closed gate discipline as run01 (declaration + pinned hashes) when a run
is eventually authorized.

## 6. Statistics (report all)

For **each arm (A0, A, B)** × pole (binding, liberating), per judge and pooled:
- **Instrument 1:** full 6×6 fit matrix; diagonal + off-diagonal means; `own_word_advantage` per word (per
  pole and combined) and aggregate.
- **Instrument 2:** full 6×6 choice/rank confusion matrix; **top-1 accuracy** vs 1/6; **MRR** vs chance;
  diagonal-rank distribution.
- **judge-level** before pooling; **leave-one-word-out** and **leave-one-judge-out** sensitivity for both
  instruments.
- Gate-G0 **overlap matrices** (facet-Jaccard, lexical-Jaccard, semantic-similarity) reported alongside.
- missing-data / inconclusive rule identical to run01 (drop + redraw ≤ 2; > 15% missing → inconclusive).
- Primary inference = Arm A0 + Arm A (both instruments); Arm B reported per its §4.3 caveat.

## 7. Interpretation (bounded)

`own_word_advantage > 0` ⇔ top-1 > 1/6 ⇔ MRR > chance:
- **positive** → **word-specific (H1) packet legibility to judges only** — nothing more.
- **≈ zero / chance** → **no detectable word specificity** (or overlap too high to detect — distinguished via
  Gate G0 / §4.5).
- **negative / below chance** → **wrong-word packets fit as well or better** — evidence against word-specific
  packet content.
- **Arm A0/A positive but Arm B ≈ 0** → specificity is **word-level / lexical**, not context-carried; given the
  claim is about the *word*, this is *consistent with* H1, reported as such (not a refutation).
- Scope guard: any positive is **H1 only** (§0.1) — nothing about H2 or individual-varṇa meaning.
- In all cases: no ontology, semantic-truth, Sanskrit-privilege, generation-utility, or individual-varṇa
  claim; B1.4b′ remains `NULL_RETURN_BOTTOM`.

## 8. Gate G0 (HARD PRE-IMPLEMENTATION GATE) — word-set distinctness audit

**The current six-word set is provisionally UNSUITABLE for a clean word-specificity test**, because many
Tier-3 packets share most of their varṇa-derived facets. Example:
```
pride  = pa · ra · da       freedom = ra · da · ma
```
pride and freedom share `ra, da` → **2 of 3** facets are the identical clause on **both** the binding and the
liberating pole → their packets are near-duplicates and no instrument can separate them. **Do not silently
retain the current six for continuity.**

**G0.1 Candidate pool (broad; these are CANDIDATES for the audit, not selections).** Assemble ≥ ~28 single
English state/emotion/disposition words spanning diverse phonetics (so a low-overlap subset can exist), e.g.:
pride, freedom, patience, courage, control, doubt, anger, greed, envy, fear, hope, joy, grief, love, calm,
trust, shame, desire, peace, faith, humility, gratitude, contentment, compassion, discipline, focus, clarity,
confusion, attachment, detachment, ambition, restlessness, craving, aversion, equanimity, boredom, wonder.
(The pool is assembled for **phonetic/varṇa breadth**, never for whether a packet looks semantically "right.")

**G0.2 Per-candidate + pairwise metrics (compute mechanically over the pool, before any ratings).** For each
candidate, via the frozen g2p→varṇa bridge and the frozen VARNA_PLAIN facet map:
- exact **varṇa-sequence** (deduped) and **packet length** per pole;
- **shared-facet count** and **unique-facet count** for every pair;
- **Jaccard overlap of facet sets** (per pole);
- **lexical Jaccard** of the rendered packets (Porter-stemmed, stopworded — same method as the audit script);
- **semantic similarity** of the rendered packets (embedding cosine; model + revision recorded);
- **number of unique discriminating facets** (facets not shared with any other candidate in a proposed subset);
- **target-word leakage** check (packet must not contain its own word or an obvious synonym);
- **validity** of both binding and liberating packets.

**G0.3 Pre-declared mechanical selection rule (no semantic cherry-picking).** Fix **k = 6** (keeps forced-choice
chance = 1/6 and run01 comparability). Among candidates passing the filters —
- valid binding **and** liberating packets;
- packet length within the frozen parity band;
- no target-word leakage;
- **≥ 1 unique discriminating facet** (target **≥ 2** where achievable) —
select the size-6 subset that **minimizes the maximum pairwise facet-set Jaccard** (a min-max maximum-diversity
selection); tie-break by (a) minimize mean pairwise facet-Jaccard, then (b) minimize mean lexical-Jaccard,
then (c) alphabetical. Pre-declared caps: **max pairwise facet-Jaccard ≤ 0.34** (i.e. < 2 shared facets for
3-facet words) and **mean facet-Jaccard ≤ 0.20**. If no size-6 subset meets the caps, report that and treat
the word-specificity test as **not feasible with prose packets** (do not relax caps post-hoc). **Selection uses
overlap / length / distinctiveness ONLY — never whether the packet appears semantically correct for the word.**

**G0.4 Freeze order.** The final word set is chosen by this rule **before** any context is authored and
**before** any rating exists, then frozen (recorded with its overlap matrices). **Final word set = PENDING.**

## Gate G1 — contexts (only after G0) — likely require NEW contexts

Even with a low-overlap set, the run01 contexts are **pole-generic** (a self-grounded freedom sentence and a
self-grounded pride sentence differ mainly by the target token). So: Arm B masked would be ≈ 0 by construction,
and reuse would tie the test to pole-discrimination rather than word-specificity. **Provisional conclusion:
new, word-specific contexts are likely required** (situations characteristic of each word's ordinary meaning),
so a word's own packet has word-specific content to match. Contexts are **not** authored here; this is gated on
G0 completing first.

## 9. Failure modes (pre-registered)

- **Overlap floor:** near-duplicate packets → advantage/accuracy ≈ chance regardless of theory (mitigated by
  Gate G0; residual overlap reported and interpreted conditionally).
- **Lexical shortcut (Arm A/A0):** a positive could reflect the judge matching the *rendered prose* to the
  word via ordinary language rather than any varṇa-specific structure — this is still H1 (packet↔word
  identifiability), but must **not** be inflated to a compositional/individual-varṇa claim (H2).
- **Masking floor (Arm B):** pole-generic contexts make Arm B uninformative; do not read its null as refuting
  H1.
- **Forced-choice noise:** intrinsic coin-flips between near-duplicates — the reason Gate G0 is mandatory.
- **Register/length tells:** a packet distinguishable by style rather than content — controlled by §4.4 parity
  re-check.
- **Judge prior leakage:** a judge inferring the word from packet phrasing — controlled by anonymity + leak
  checks (§4.4, §5).
- **Infeasibility:** if Gate G0 finds no size-6 subset under the caps, the honest outcome is "prose-packet
  word-specificity not testable with this framework," not a relaxed run.

## 10. Recommendation

**READY FOR WORD-SET DISTINCTNESS AUDIT (Gate G0).** **NOT ready for context authoring or implementation.** The
next authorized step is to *run the Gate G0 mechanical audit over the candidate pool and produce the frozen,
distinctness-selected word set* — a separate, explicitly-approved step. No contexts, no scaffold, no code, no
judges until G0 completes and its output is accepted, and G1 (contexts) is resolved.

## 11. Guardrails
Docs-only preregistration. No word selection, no context authoring, no code, no scaffold, no run, no new
experiment number; nothing under B1.10 (run01 ratings/results, packets, contexts, judges, numbering) is changed
by this document. Resonance / phonetic-fidelity refinement only. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no
ontology / semantic-truth / Sanskrit-privilege / generation-utility claim; no individual-varṇa attribution.
**B1.4b′ remains `NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B blocked. Structure, not validated
meaning.**
