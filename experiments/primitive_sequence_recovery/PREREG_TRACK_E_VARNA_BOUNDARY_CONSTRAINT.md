# Pre-Registration — Track E: Varṇa Boundary-Constraint Test (docs only)

**Pre-registration of a NEW hypothesis. Nothing implemented, run, or changed.** No experiment,
no scoring, no code, no artifact mutation, no `manifest_v2`. `manifest.json` remains NOT_READY;
runner remains NOT_RUN; Stage A untouched; **Track B remains BLOCKED**; no `ONTOLOGICAL_SIGNAL`,
no Sanskrit privilege.

**This is not a rescue of Track C or D0.** Those tested *dictionary-referent recovery* (Track C:
no robust signal) and *experiential-weather recovery* (D0: `LLM_PILOT_NO_SIGNAL`). Track E asks a
**different question** (varṇa as a *boundary/reweighting function* over candidate meanings), and
its result says nothing about — and cannot reinterpret — the prior negatives, which remain valid
for the questions they actually tested.

**Skeptical preamble.** A "boundary/reweighting" hypothesis is *more* flexible than recovery, so
it is *more* prone to researcher degrees of freedom and to looking successful for trivial reasons
(context alone does the work; the boundary is generic). The controls and falsifiers below exist to
make it refutable; the default expectation remains `NO_SIGNAL` / `CONTEXT_ONLY_EXPLAINS`.

---

## 1. Core distinction

Three distinct claims, only the third is Track E:

- **Dictionary-referent recovery (Track C):** the varṇa sequence recovers the *word's dictionary
  meaning* (e.g. hṛdaya → "heart"). **Tested; no robust signal.**
- **Experiential-weather recovery (Track D0):** the varṇa composition matches a word's *emotional
  profile*. **Tested; `LLM_PILOT_NO_SIGNAL`.**
- **Varṇa boundary constraint (Track E, new):** the varṇa composition does **not** name the
  meaning; it acts as a **boundary/reweighting function** that accepts, rejects, or reweights
  *candidate* interpretations already supplied by dictionary + context + etymology. The claim is
  relational ("which candidate is admissible here"), not generative ("what does the word mean").

## 2. Formal hypothesis

Given a polysemous word in context:
- **dictionary** provides a candidate interpretation set,
- **context** narrows candidates to a locally-correct one,
- **etymology** supplies historical/root priors,
- **varṇa/vṛtti composition** provides a **boundary function** that reweights/rejects candidates.

**H_E:** the *real* varṇa boundary improves selection of the context-correct candidate **beyond**
what context, etymology, dictionary, a *scrambled* varṇa boundary, and a *generic (Barnum)*
boundary achieve. **H0 (default):** it does not — context (and/or etymology) explains selection,
or the boundary is generic, or the specific mapping adds nothing (scramble-equivalent).

Crucially, H_E is **incremental**: varṇa must add over context/etymology, not merely correlate
with the correct answer (which context already encodes).

## 3. Architecture

For word *w* in context:
- **candidate set** `C = {c₁, c₂, …, cₙ}` — pre-registered interpretations (dictionary-permitted).
- **context vector** `x` — from the context sentence (fixed encoder).
- **etymology prior** `e` — root/historical prior over candidates (where available).
- **varṇa boundary vector** `v` — from the frozen varṇa/vṛtti composition of *w*.
- **boundary score** `B(cᵢ | v, x, e)` — a fixed, pre-registered scoring function producing a
  reweighting over candidates.

Prediction is **not** `v ≈ meaning`; it is that `B(·|v,·,·)` **reorders** candidates toward the
context-correct one *better than the same architecture with v removed / scrambled / made generic*.
The scoring function and encoders must be frozen before any run (they are researcher DOF — §
Controls/Falsifier). No absolute-match requirement; selection is relative/ranking (as in D0).

## 4. Examples (illustrative only — must not be used to tune the test)

Polysemous targets whose dictionary meaning admits several *kinds* of the same gloss; context
picks one; the question is whether the varṇa boundary reweights toward it:

- **happy:** peace · pleasure · desire-fulfilled · affection · relief · ego-satisfaction · inner
  contentment.
- **heart:** organ · emotional center · courage · love · vulnerability.
- **desire:** aspiration · craving · love · lust · ambition.
- **peace:** silence · relief · harmony · surrender · avoidance.

(These are exposition; the frozen dataset's candidate sets and context-correct labels are authored
separately and blind to the varṇa decomposition — see §5.)

## 5. Dataset design

Use **broad/polysemous** words where the dictionary permits multiple interpretations. Each item:
- **dictionary meaning** (candidate-permitting),
- **context sentence** (disambiguating),
- **candidate interpretations** `C` (pre-registered, controlled set),
- **one context-correct interpretation** (labeled **blind to the varṇa decomposition**),
- **hard-negative interpretations** (semantically adjacent, e.g. peace vs relief vs harmony),
- **etymology notes** where available,
- **varṇa/vṛtti decomposition** (consonant-only and/or vowel-aware; stated).

Freeze rules: candidate sets + context-correct labels + contexts authored by independent
annotators **before** attaching varṇa decompositions; inter-annotator agreement on the
context-correct label reported; low-agreement items excluded. Include a **control domain** of
items where varṇa should be irrelevant (sanity that the method isn't "always helps"). All hashed
before any run. (For an LLM-scored pilot, the D0 blinding/contamination protocol applies:
generator ≠ scorer, anonymized packets, contamination probe.)

## 6. Controls

Score candidate selection under each, identical data/architecture:
- **A — real varṇa boundary** (v from the true composition),
- **B — scrambled varṇa boundary** (v from a scrambled assignment; same glosses, permuted),
- **X — no-varṇa / context-only** baseline (v removed),
- **F — etymology-only** baseline,
- **D — dictionary-only** baseline (no context),
- **I — Barnum / generic-emotional boundary** baseline (v = a generic affliction/emotional
  boundary; the D0 Barnum family, adapted to a boundary).

## 7. Primary endpoint

The **real varṇa boundary (A)** must improve selection of the **context-correct** candidate over
**all** of: context-only (X), etymology-only (F), dictionary-only (D), scrambled varṇa (B), and
Barnum boundary (I). Metrics: **MRR, Top-1, pairwise accuracy** on the context-correct candidate,
with bootstrap CIs (CI lower bound > 0 for each contrast) and multi-seed stability — a positive
requires beating **every** control, not just the dictionary baseline.

## 8. Critical falsifier

- If **context-only (X)** or **etymology-only (F)** performs as well as real varṇa → varṇa adds
  **no boundary signal** (`CONTEXT_ONLY_EXPLAINS` / `ETYMOLOGY_EXPLAINS`).
- If **scrambled varṇa (B)** performs as well as real varṇa → the **specific mapping** adds
  nothing (`SCRAMBLE_EQUIVALENT`).
- If **Barnum boundary (I)** performs as well as real varṇa → the boundary is **generic**, not
  varṇa-specific (`BARNUM_BOUNDARY`).
Any one of these → not a boundary signal. The incremental-over-context bar (A > X) is the core
falsifier: if context already selects the right candidate, varṇa has nothing left to explain.

## 9. Allowed labels

- `BOUNDARY_CONSTRAINT_SIGNAL` — A beats X, F, D, B, **and** I on the primary metric, with CI
  lower > 0 and seed-stability, and hard-negatives ruled out.
- `NO_SIGNAL`
- `CONTEXT_ONLY_EXPLAINS`
- `ETYMOLOGY_EXPLAINS`
- `SCRAMBLE_EQUIVALENT`
- `BARNUM_BOUNDARY`
- `INCONCLUSIVE`

**Forbidden:** `ONTOLOGICAL_SIGNAL`, `SANSKRIT_PRIVILEGE`, any Track-B-unblocking or
validation-of-Symbol-U language. Note: even `BOUNDARY_CONSTRAINT_SIGNAL` supports only "varṇa
adds incremental candidate-selection value in this architecture," **not** ontological truth, and
(as in D0) is capped by English-mediation/shared-source ceilings and would require a rigorous,
independent replication before any strong claim.

## 10. Boundary statement

Track E tests whether varṇa acts as a boundary over candidate meanings, not whether it recovers
dictionary meaning. Track B remains blocked. Structure, not validated meaning.
