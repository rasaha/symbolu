# Track E-flat — Revised-Smoke Design (one-time confound check)

**Design note only. Nothing run, scored, or changed.** No experiment, no LLM/scorer call, no
network, no model download. `frozen/manifest.json` remains NOT_READY; the base smoke manifest stays
`run_enabled:false` / `NOT_APPROVED`; psr runner NOT_RUN; Stage A untouched; four-sphere JSON
parked/not integrated; **Track B remains BLOCKED**; no `ONTOLOGICAL_SIGNAL`, no Sanskrit privilege.
This plan authorizes nothing; it specifies a **single** revised rerun for later approval.

## 1. Purpose

Specify **one** revised Track E-flat smoke rerun whose sole purpose is to test the **context-ceiling
confound** identified in the diagnostic breakdown: in the first smoke, context-only (X) ranked the
correct candidate #1 in **11/12** cases (MRR 0.958), leaving almost no headroom to detect whether
the varṇa boundary adds anything. This rerun makes the contexts and candidate sets **harder** so the
test can actually discriminate — nothing else about the design changes.

## 2. Non-rescue rule

- The first Track E smoke result **remains `CONTEXT_ONLY_EXPLAINS`** and is not reopened, softened,
  or reinterpreted by this plan or its eventual rerun.
- This rerun **cannot rescue** that result or produce a positive about Symbol-U. It tests exactly
  one methodological question — *was context/candidate difficulty too easy?* — and nothing more.
- A different measurement on a harder set is a **new** data point with its own pre-commitment; it
  does not retroactively convert the prior negative, and it does not touch the Track C / D0
  negatives or the Track B block.

## 3. Stop rule (pre-committed, binding)

- **Exactly one** revised flat-boundary smoke rerun is permitted. No second revised smoke.
- **If A does not beat X → STOP Track E-flat.** (The incremental-over-context bar is primary.)
- **If A does not beat B (scramble) or I (Barnum) → STOP Track E-flat**, even if it beats X.
- **No further tuning after this rerun** — no context re-editing, candidate reshuffling, prompt
  changes, model swaps, or seed hunting to chase a result. One shot, then a decision.
- A `STOP` outcome closes the flat-boundary Track E path; it is a legitimate, money-saving
  conclusion, not a failure.

## 4. Revised context design (harder, less clueing)

Each primary context must:

- contain **less clueing** — no phrase that paraphrases or entails the correct candidate;
- contain **no obvious synonym** of the correct candidate gloss (the first smoke's contexts often
  half-named the answer);
- **not already select the answer** — a competent reader (and X, context-only) should find the item
  genuinely ambiguous;
- leave **2–3 plausible candidates alive** after reading the context (so context alone cannot
  saturate the ranking).

Operational target: the revised set should drive the **X (context-only) baseline down to roughly
MRR ≲ 0.75 / Top-1 ≲ 0.6** (vs 0.958 / 0.917 before). If a pre-run blind check shows context-only
still near-ceiling, the contexts are still too easy and must be hardened **before** the single
approved run (this hardening is authoring, not a second rerun).

## 5. Revised candidate design (closer negatives)

Each primary item must have:

- **closer hard negatives** — near-synonyms/adjacent senses that context does not trivially exclude;
- **all candidates dictionary-valid** where possible (every option a real sense of the word), so the
  scorer cannot eliminate options on well-formedness alone;
- **at least two candidates plausible from context alone**, so the item is live after context;
- authored **blind to the varṇa decomposition**, agreement-gated, low-agreement items excluded (as
  before). Candidate order shuffled per packet; correct label in the hidden key only.

## 6. Concrete controls (diagnostic-only)

Concrete-referent items (river/mountain/house-type) move into a **diagnostic-only subset** and are
**excluded from the primary label**. In the first smoke these were where the boundary did most
damage (rank_A 6/3/2), but the flat vṛtti boundary is not designed for concrete referents, so they
should not drive the primary decision. Keep a small concrete subset **only** as a sanity check
(expected at chance / boundary-irrelevant); report it separately.

## 7. Primary subset

- **Primary label uses abstract / polysemous cases only.**
- **Keep 10–12 primary cases.** (Plus the separate diagnostic-only concrete subset from §6 and,
  if used, a clearly-marked famous/exploratory subset excluded from the primary label, as before.)
- Still a smoke pilot: too small for bootstrap CIs / multi-seed stability, so it can trigger a
  larger pre-registered pilot but **cannot itself validate** anything.

## 8. Controls unchanged

- Keep the six arms: **A** real boundary · **B** scrambled · **X** context-only · **F**
  etymology-only · **D** dictionary-only · **I** Barnum.
- Keep **`A_vs_X`** as the **primary falsifier** (incremental over context).
- Keep the **Barnum (I)** and **scramble (B)** vetoes.
- Same runner, same anonymization/leak scan, same JSON-only scorer contract, same seeds mechanism
  (re-frozen for the new inputs). Only the word/context/candidate inputs change; the machinery does
  not.

## 9. Decision criteria (to justify a larger pilot)

To justify a larger pre-registered Track E-flat pilot, on the harder primary subset the real
boundary **A must**:

- **beat X** (context-only) — the primary bar;
- **beat B** (scrambled);
- **beat I** (Barnum);
- **beat F** (etymology-only);
- **beat D** (dictionary-only);
- with **no contamination** (scorer never names a Sanskrit/varṇa/root token);
- and **no malformed-output issue** (malformed-JSON rate within the pre-set threshold, e.g. ≤ ~15%).

Anything short of A beating **all** of X, B, F, D, and I cleanly → **STOP** per §3.

## 10. Failure interpretation

If the revised smoke again returns **`CONTEXT_ONLY_EXPLAINS`**, **`SCRAMBLE_EQUIVALENT`**, or
**`BARNUM_BOUNDARY`** (or `NO_SIGNAL` / `INCONCLUSIVE`), **close the Track E-flat path.** That
outcome would mean the flat varṇa boundary adds no incremental candidate-selection value even once
the context ceiling is removed — i.e., the first smoke's negative was not merely an artifact of easy
contexts. This is the expected default and is a clean, honest close, not a pipeline failure.

## 11. Relationship to four-sphere

The four-sphere varṇa lexicon (`track_e_varna_sphere_lexicon.json`) **remains a parked candidate
artifact and is not integrated** by this plan or its rerun. Any four-sphere **Track E-FS** path is a
**separate** investigation requiring its **own** pre-registration, controls (a flat-gloss
gatekeeper, four-sphere scramble, sphere-ablation, four-sphere Barnum), config, and approval. A
`STOP` on Track E-flat does not authorize Track E-FS; it would be proposed and justified
independently, and it is not a rescue of this negative.

## 12. Boundary statement

This is a one-time Track E-flat revised-smoke confound check. The first smoke remains CONTEXT_ONLY_EXPLAINS. Track B remains blocked. Structure, not validated meaning.
