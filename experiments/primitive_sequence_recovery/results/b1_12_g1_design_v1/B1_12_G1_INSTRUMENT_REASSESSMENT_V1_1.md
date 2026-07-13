# B1.12 — Gate G1 Instrument Reassessment V1.1 (methodological correction)

**Supersedes the claim of `B1_12_G1_REPORT.md` (commit `9e8da86`), which is preserved unchanged as development
history.** The prior verdict `G1_PASS_WITH_LIMITED_CLAIM` **overstated** what the opaque within-word task
establishes. Corrected verdict: **`G1_BLOCKED_NO_IDENTIFIABLE_TASK`** (with the frozen resources and the frozen
selected six). No G0/pool/threshold/parser/map/selected-six change; no judges; no run.

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`. Allowed because no confirmatory evidence was frozen
or collected. B1.4b′ `NULL_RETURN_BOTTOM`; B1.10 `G0_NOT_TESTABLE_WITH_CURRENT_PROSE_PACKETS`; B1.11 unchanged.

---

## Task 1 — Audit of the current claim

Prior claim: *"the instrument can test whether a word's true ordered opaque composition is distinguishable from
its own scrambled and unordered versions."* The word **"distinguishable"** was equivocal:

- **As string inequality** (A, B, D are different strings): **trivially true and not an evaluator experiment** —
  a `!=` check settles it; it establishes *representation integrity*, nothing about order carrying information.
- **As identifying which arm is the word's TRUE order:** requires information linking a permutation of
  **meaning-free opaque IDs** to "truth." With no key, no gloss, and no training/reference phase, **no such
  information is supplied.** The evaluator can see the arms differ but has **no basis** to pick the true one.

Therefore the current opaque within-word task is **underdetermined** for order *recovery*. It achieves
representation integrity only.

**Classification of the current instrument: `REPRESENTATION_INTEGRITY_ONLY`** (equivalently
`TASK_UNDERDETERMINED` for order recovery). The prior `G1_PASS_WITH_LIMITED_CLAIM` is **not preserved** — it
conflated mechanical string inequality with evaluator-identifiable order.

## Task 2 — Chance / exchangeability argument (formal, opaque-synthetic)

Setup: a trial shows arms that are permutations of one opaque multiset (A = true order, B = fixed-seed scramble,
D = canonical-sorted). The only information available from an opaque arm **without a key** is its
**relabel-invariant canonical form** (rename tokens by order of first appearance) — i.e. its **length and
repetition pattern**. Analysis (`b1_12_g1_identifiability_check.py`, deterministic, opaque symbols):

- **Distinct-token multiset — the case of ALL SIX selected words (no repeats):** every one of the `n!`
  permutations canonicalizes to the **same** form (`abcde…`). For n=5: **120 permutations → 1 canonical form.**
  `canon(A) = canon(B) = canon(D)`. The arms are **exchangeable**; no key-free feature correlates with truth.
  - **Observable feature correlated with truth:** *none.* Length and multiset are identical across arms;
    repetition pattern is null (distinct tokens); token identities are meaning-free.
  - **Is any such feature supplied independently of the answer?** No.
  - **Expected accuracy under exchangeability:** **0.5** for A-vs-B (D is eliminable only as "the sorted one,"
    which is *canonical*, not *true* — recognizing D does not identify A vs B).
  - **Any above-chance performance would necessarily imply** one of: **leakage** (a template/ID-assignment
    artifact), **memorization** (the judge has seen this word's varṇa order), or an **undocumented prior** (the
    judge reconstructs the Sanskrit word from IDs that were supposed to be opaque — i.e. the IDs are not truly
    opaque). None of these is the hypothesis under test.
- **Repeated-token multiset (not present in the six):** the canonical form carries the repetition *pattern*
  (12 permutations → 6 canonical forms in the demo), which is key-free-visible — but still does **not** identify
  which arrangement is the word's true order.
- **Semantic key breaks exchangeability:** supplying token→gloss + a target meaning yields a feature
  (`ordered-gloss match to target`) with `match(A_true)=1.0 > match(B_scramble)=0.0` → identifiable **in
  principle** — but only *with* a supplied key/gloss.

**Conclusion:** opaque-only "identify the true order" is at chance; identifiability requires a supplied semantic
key.

## Task 3 — Re-evaluation of Models 1–4

| model | route to the answer? | isolates order? | leakage-safe? | instantiable on the six now? | verdict |
|---|---|---|---|---|---|
| **1A** learned-key seq→label demos | via induced mapping | **No** — the six have **distinct inventories**, so the code learned is *inventory→label*, not order (memorization / code-induction) | opaque ok | yes but tests the wrong thing | reject (memorization; no order isolation) |
| **1B** opaque + structural descriptors → meaning | via phonetic descriptors | partially | **No** — C/V/aspiration/articulation are near-phonetic → word reconstruction → Sanskrit-knowledge prior | descriptors exist | reject — `LEAKAGE_DEPENDENT` |
| **2** candidate-relative cross-word match | via inventory | **No** — distinct inventories + unique first unit identify the word without order | — | leaks | reject (inventory task) |
| **3** same-word structural discrimination | **none** (opaque, no anchor) | n/a | opaque ok | yes but **underdetermined** (Task 2) | `REPRESENTATION_INTEGRITY_ONLY` |
| **4** semantic ordered-gloss judgment | **yes** — glosses + candidate meanings give a principled basis | **Yes** if A/B/D share gloss inventory and differ only in order | risk: B1.10 prose confound; must control | **No — coverage-blocked (below)** | only principled route, but currently blocked |

**Decisive coverage finding (blocks Model 4 for the six).** The frozen varṇa→gloss map (`VARNA_PLAIN`) is
**consonant-only** — 11 consonants `{b,d,g,k,l,m,n,p,r,t,tt}` — and renders **no vowels**. The selected six use
18 distinct units including vowels `{a,e,i,ī,ā,ū}` (present in *every* word) and uncovered consonants
`{s,th,j,v,y,ñ,ś}`. Per-word gloss coverage: asthi 0/4, jñāna 1/5, keśa 1/4, sūrya 1/5, grīvā 2/5, nadī 2/4 —
**no word is fully glossable.** A complete ordered-gloss rendering of the six is **impossible** under frozen
resources — the same 11-varṇa ceiling that produced B1.10's `G0_NOT_TESTABLE`.

## Task 4 — Recommended scientifically-meaningful G1 instrument (and why it is not yet runnable)

The **only** design with a principled answer route that isolates order is a **controlled semantic ordered-
component test (Model 4)**:

- **Supplied before test:** a frozen, per-varṇa **component descriptor** (its fixed meaning), supplied
  independently of the test words; and a fixed set of **candidate meanings**.
- **Principled basis for identifying the true-order arm:** the ordered component descriptors can be matched to a
  candidate meaning; if varṇa order carries meaning-relevant information, the **true order (A)** matches the
  word's meaning better than its scramble (B) or unordered inventory (D).
- **Held out:** the mapping from words to meanings is the test; component descriptors and candidate meanings are
  given.
- **A vs B:** identical component multiset, identical length, **only order differs** (fixed-seed scramble).
- **D:** same components, order removed (canonical inventory).
- **Memorization control:** held-out words; report whether accuracy exceeds an inventory-only (D) baseline.
- **Semantic-leakage / B1.10-confound control (what makes it H2, not a prose packet):** *same component
  inventory across A/B/D*; *only order changes*; *rigid position-tagged template* (`p1:<desc> p2:<desc> …`);
  **no authored connective prose**, **no progression verbs** ("becomes/leads-to/resolves"); the **order
  advantage `Acc(A) − Acc(B)`** is the *primary* contrast (B1.10 had no order manipulation at all).
- **Success would mean:** true varṇa order improves held-out meaning identification over its own scramble and
  unordered inventory — the necessary evaluator-usable signal for H2.
- **Failure would mean:** order gives no advantage over inventory (`A ≈ B ≈ D`) — order is not evaluator-usable
  for meaning (the honest expected outcome given B1.10's null and arbitrariness-of-the-sign).

**Why it cannot be recommended as a runnable task now:** it is **coverage-blocked** for the six (no full gloss
rendering exists), and it requires a **frozen, non-narrative, coverage-adequate component-descriptor mapping**
that does not yet exist. Authoring that mapping is a **separate pre-registration** with its own blinding and
leakage discipline — explicitly out of scope here. Recommending Model 4 *on the six now* would violate "do not
recommend a task whose correct answer is inaccessible from the supplied information."

## Task 5 — Revised G1 status

**`G1_BLOCKED_NO_IDENTIFIABLE_TASK`** — with the frozen selected six and frozen resources, there is **no** task
that is simultaneously (a) answerable from supplied information, (b) order-isolating, (c) leakage/memorization-
safe, and (d) instantiable now: opaque Model 3 is underdetermined; Models 1A/1B/2 fail on order-isolation or
leakage; Model 4 (the only principled route) is coverage-blocked and confound-risky.

**A diagnostic usability probe is NOT allowed / not scientifically meaningful yet** — no revised task gives the
evaluator a principled route to the answer with frozen resources. (Probing the opaque Model-3 task would only
measure chance, or worse, reward leakage/memorization.)

**Resolution path (each a separate, explicitly pre-registered step; none taken here):**
1. Author a **frozen, coverage-adequate, non-narrative ordered component-descriptor mapping** (covering the six's
   varṇas incl. vowels), with its own blinding/leakage pre-registration — this reopens the semantic route while
   documenting the B1.10-confound controls above; **or**
2. Accept that a **leakage-safe opaque** B1.12 can only ever establish *representation integrity*, not order
   recoverability, and record H2-via-this-instrument as **not testable without a semantic anchor**.
Only after (1) does the Model-4 usability probe become `G1_READY_FOR_DIAGNOSTIC_USABILITY_PROBE`.

## Artifacts & discipline

Added (this reassessment): this doc + `b1_12_g1_identifiability_check.py` (opaque-synthetic, deterministic).
The prior G1 v1 artifacts (`B1_12_G1_REPORT.md`, `g1_manifest.json`, etc., commit `9e8da86`) are **preserved
unchanged** as development history. No judges, no contexts, no prompts, no evidence run; selected six, G0, pool,
thresholds, parser, and opaque-ID map untouched; B1.10/B1.11 unchanged. Structure, not validated meaning.
