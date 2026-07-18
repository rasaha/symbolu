# Varṇa–Affliction Resolution Test — Narrow-Hypothesis Review

Docs-only conceptual refinement. Modifies **no** preregistration or artifact. Evaluates whether a proposed
narrow hypothesis faithfully captures the test actually frozen in `VARNA_AFFLICTION_RESOLUTION_TEST_PREREG_V1.md`.
`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`.

**Readiness: `NEEDS_MINOR_REFINEMENT`** — the proposed statement is directionally correct but drops three
elements the frozen test carries (consonant-primary restriction; the "does not conspicuously embody" disjunct;
a precise definition of "resonate"). The frozen test's own §1 is already accurate and remains
`READY_FOR_WORDLIST_PRECOMMITMENT`.

---

## 1. Repository evidence (frozen)

`VARNA_AFFLICTION_RESOLUTION_TEST_PREREG_V1.md` (status `READY_FOR_WORDLIST_PRECOMMITMENT`), §1 core hypothesis;
§4 R3–R6 (frozen consonant mappings, occurrence-level R4, AND-composition R5, no-progression R6); §5 vowel arm
`PROVISIONAL/DEVELOPMENT_ONLY` (never merged); §6 Stages A(blind referent)/B(bidirectional)/C(scoring); §7 R7–R12
absolute `{0,25,50,75,100}` scale, mean/minimum/embodiment-counts/coverage; §8 PASS/PARTIAL_FIT/FAIL/INDETERMINATE;
§10 adversarial wordlist precommitment; §12 falsification/null; §13 prohibited rescues. Parser
`sanskrit_stage1_parser.py` (sha `d885391f…`), lexicon `varna_native_stage1_merged_v1.json` (sha `af4c1f54…`),
**33** confirmatory consonants. Supporting: `B1_12_DEVELOPMENT_RESET…` (`2442604`, order framing stopped),
`B1_12_ORDER_HYPOTHESIS_REVIEW.md` (`90eb5e0`, order not a theory prediction; mapping-set specificity is a
*separate* complementary study), `SYMBOL_U_THEORY_V1_FREEZE.md` (T-OPERATOR, disavowed for this test).

## 2. Final narrow hypothesis (Question 1)

The proposed statement is **not fully faithful** — it (a) omits the **consonantal / primary-arm** restriction
(§4: primary uses consonant backbone only; vowels are secondary/provisional), (b) drops the **"or does not
conspicuously embody"** disjunct that §1 and the 0-point score (§7) make central, and (c) uses the undefined word
**"resonate."** Narrowest scientifically accurate version (aligned to §1 + R5/R6):

> **For an attested Sanskrit word, the prototypical, unqualified referent resolves, transcends, stands free from,
> or does not conspicuously embody the specific binding-state afflictions that the frozen lexicon assigns to the
> word's pronunciation-derived *consonantal* varṇas — where those afflictions combine by simultaneous
> AND-composition (membership only; no order, progression, or causal chain), and each mapped affliction is
> scored independently on its own occurrence.**

(The frozen test's §1 already states this; the proposed restatement should be aligned to it, not vice-versa.)

## 3. Definition of "resonate" (Question 2)

"Resonance" must **not** mean a vague "coherent philosophical relationship" — §6/§12 explicitly forbid that path
(no "unsupported symbolism," and "flexible reconciliation" is a **null** signature, §166). Repository-supported
definition:

> **Resonance(component) = the scored degree to which the prototypical unqualified referent is contrary to, free
> from, or non-embodying of that component's exact frozen binding gloss**, placed on the frozen absolute 5-point
> scale (§7 R7): **100** = clear resolution / conspicuously free; **75** substantial; **50** mixed/ambiguous;
> **25** substantial embodiment; **0** conspicuous embodiment of the exact mapped affliction.
> **Resonance(word) = the AND-composition of component resonances** — reported as mean (R9), **minimum** (R10),
> and **embodiment counts** (R11) — **not** a holistic gestalt impression.

So resonance = *resolution / characteristic-freedom / non-embodiment*, measured **per component, absolutely** —
the second and third of the user's candidate readings, operationalized; never "philosophical coherence."

## 4. Definition of the "stable view of the word" (Question 3)

Repository-defined (§1 "**prototypical, unqualified** referent"; §6 Stage A "prototypical unqualified referent";
prohibitions §6/§13 against "select an exceptional subtype"):

> **The stable referent = the enduring, default, unqualified prototype** of the word's ordinary accepted meaning
> — its characteristic nature, **not** an exceptional subtype, extreme instance, or temporary perturbed state.

**Why exceptional cases must be excluded:** allowing a subtype that happens to embody the affliction (or a
special calm subtype that happens to resolve it) is a **rescue/Barnum mechanism** that would inflate PASS and
destroy falsifiability — exactly what §13 prohibits. The prototype is fixed **blind** in Stage A before the
packet is seen. Concretely: **elephant** (its steady default nature), *not* a musth (rutting) elephant;
**river** (its ordinary flow), *not* one flooded river; **peace** (settled peace), *not* temporarily disturbed
peace. The affliction is scored against the default, not against a cherry-picked instance.

## 5. Scope exclusions — what this experiment is NOT testing (Question 4)

Grounded in the frozen rules, the test does **not** attempt to determine:
- **dictionary/ordinary-meaning recovery** — Stage A is *given* the ordinary meaning; nothing is recovered
  (contrast the rejected O1 referent-identification, `6b8e561`);
- **unique packet identification** — R8 is absolute, not identification;
- **superiority over any/every other packet** — R8 explicitly *"not vs another word, a control, the sample
  average, or a ranking"*;
- **order sensitivity** — R6: order only determines which units occur; no order claim (see `90eb5e0`);
- **semantic progression / transformation** — R6: no varṇa transforms/balances/removes another;
- **pronunciation reconstruction** — §3: varṇas come only from the frozen parser; no orthographic/spelling/
  silent-letter reconstruction.

## 6. Minimum experimental procedure (Question 5)

The frozen §6–§8 already **is** the minimum. Smallest test capable of evaluating the hypothesis:
1. **Precommit** an adversarial word list (§10: calm/stable referents · fierce animals · destructive forces ·
   unstable phenomena · explicitly afflictive concepts · abstract negative states), **before** any packet.
2. **Frozen packet:** parser → consonant occurrences → verbatim binding glosses (R3, R4 occurrence-level).
3. **Stage A (blind):** lock the prototypical unqualified referent profile.
4. **Stage B (bidirectional):** strongest resolution **and** strongest embodiment argument per component
   (symmetric; no prototype/gloss alteration, no exceptional subtype, no vowel/liberating-pole rescue).
5. **Stage C absolute component scoring** `{0,25,50,75,100}` (R7), scored **before** aggregation (R13).
6. **Absolute overall verdict:** mean (R9) + minimum (R10) + embodiment counts (R11) + coverage ≥80% (R12) →
   PASS/PARTIAL_FIT/FAIL/INDETERMINATE (§8).

**No comparative packet controls are logically required** for this hypothesis — it is an **absolute** claim
("resolves its **own** afflictions," R8). *(A random/decoy-packet control would strengthen it against the
disclosed nonblind-Barnum limitation, but that is the separate, complementary **mapping-set specificity** study
of `90eb5e0`, not part of this minimum, and must not be merged in.)*

## 7. Falsification conditions (Question 6)

**PASS** = mean ≥75 **and** minimum ≥50 **and** no component = 0 or 25 **and** coverage ≥80.
**PARTIAL_FIT** = mean in [50,75); or mean ≥75 with any component = 25; or a genuine mixture — **never** PASS.
**FAIL** = mean < 50; **or any component = 0** (conspicuous embodiment of the exact frozen affliction).

Words that **should naturally FAIL if the theory is false** (do not soften): the **explicitly afflictive
concepts** and **fierce/destructive** referents, whose prototypes conspicuously *embody* their varṇas'
afflictions —
- **kāma** (desire): `k` → *āśā, grasping/clinging hope* — the prototype *desire* **is** grasping hope →
  that component ≈ **0** → **FAIL**;
- **krodha** (anger): `r` → *sarvanāśa, defeatist annihilation-thought* + `k` grasping — anger embodies
  destructive impulse → low components → **FAIL**;
- **lobha** (greed): `l` → *kruratā, cruelty* — greed embodies grasping/cruelty → **FAIL/PARTIAL**;
- **bhaya** (fear): `y` → *aviśvāsa, self-doubt* — fear embodies distrust → low → **FAIL/PARTIAL**;
- fierce animals (**vyāghra/siṃha**) and destructive forces should embody aggression/annihilation afflictions.

If, instead, such words are scored **PASS** through flexible reconciliation, rare 0/25 assignment, or inability
to distinguish the adversarial categories, that is the **null** signature (§12, §166–168): "a process
effectively incapable of saying no." A single component = 0 on any afflictive-concept word is a clean
**contradiction** of the *universal* form (§12).

## 8. Retained B1.12 infrastructure (Question 7)

Reuse (theory-neutral infrastructure, already used by or compatible with this test):
- **Frozen parser** `sanskrit_stage1_parser.py` — pronunciation→consonant extraction (§2, R3). Retain.
- **Frozen merged lexicon** binding mappings (33 confirmatory consonants). Retain.
- **Occurrence-level scoring / multiplicity** (R4) — repeats scored independently; a **multiset** property fully
  compatible with AND-composition (membership + multiplicity, *not* order). Retain.
- **Coverage gating (≥80%)** and **INDETERMINATE ≠ 50%** — retain (already R12/§8).
- **Candidate-curation *methodology*** from the B1.12 pool freeze (attested-only, blind-to-structure,
  deterministic selection) — reusable for §10 precommitment. Retain the **method**, not the specific set.

## 9. Rejected concepts (abandoned hypotheses; do not carry in)
- **Ordered composition / order advantage (H2)** and the **order-scramble arm** — order is not a theory
  prediction (`90eb5e0`); inert under AND-composition.
- **Order-distinctness G0 machinery** (edit distance, self-order `o(x)`, `d_ord|inv`, ordered n-grams, endpoint
  caps) and the **G0-selected six** — selected *by* order-distinctness, a rejected criterion (the words are
  attested and may be re-precommitted under §10, but **not** the set/rationale).
- **G1 evaluator instruments** (opaque-ID; semantic descriptors as *referent* labels) — referent-identification,
  domain-mismatched (`6b8e561`).
- **Comparative packet controls** — not part of *this* absolute test (they belong to the separate mapping-set
  specificity study; no merge).

## 10. Readiness assessment

**`NEEDS_MINOR_REFINEMENT`.** The narrow hypothesis is **repository-consistent in substance**, but the *proposed
wording* must be tightened to §2 above (add consonant-primary restriction; restore the "does not conspicuously
embody" disjunct; replace "resonate" with the §3 operational definition). The frozen test itself needs **no**
change — its §1 already carries the accurate hypothesis and it remains `READY_FOR_WORDLIST_PRECOMMITMENT`. Not
`THEORY_UNCLEAR` (the theory is precisely specified). Not `READY_FOR_CONFIRMATORY_EXPLORATORY_RUN` — the frozen
**next gate is §10 wordlist precommitment** (an adversarial ~8–10-word mix fixed *before* any packet), which has
not occurred; only after that can Stages A→C run.

## Guardrails
Docs-only review; the Varṇa–Affliction Resolution Test, all B1.12 artifacts, B1.10, B1.11, parser, and lexicon
are **unchanged**; no words selected, no packet computed, no run, no freeze. Structure, not validated meaning.
