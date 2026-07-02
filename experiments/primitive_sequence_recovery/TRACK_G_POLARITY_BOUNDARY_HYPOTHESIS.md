# Track G — Polarity Boundary Hypothesis (docs only)

**Hypothesis note only. Nothing implemented, run, or scored.** No experiment, no LLM/scorer call,
no code, no artifact mutation. `frozen/manifest.json` remains NOT_READY; runner NOT_RUN; Stage A
untouched; four-sphere JSON parked/not integrated; **Track B remains BLOCKED**; no
`ONTOLOGICAL_SIGNAL`, no Sanskrit privilege. This authorizes nothing.

**Not a rescue of Tracks C / D0 / E / F.** Those tested dictionary-referent recovery (no signal),
experiential-weather matching (`LLM_PILOT_NO_SIGNAL`), candidate-boundary selection
(`CONTEXT_ONLY_EXPLAINS`, closed), and inference-steering (`CORRECTNESS_DEGRADED`, no useful
steering). Track G proposes a **different** relation — polarity-boundary alignment — and its
eventual result cannot reinterpret, soften, or reopen those negatives.

**Skeptical preamble (read first — this is the most flexible hypothesis yet).** Polarity introduces
a dangerous new degree of freedom: a word can "conform" to a varṇa polarity **either** by direct
alignment (happy ↔ contentment pole) **or** by contrast (happy ↔ the desire/fear/lack pole it
"resolves"). If *both* directions count as success, the hypothesis is unfalsifiable — every word
matches its axis somehow. That is a "heads-I-win, tails-you-lose" trap. Track G is only meaningful
if the **polarity (which pole a word sits on) is frozen before scoring** (§4) and a **random
polarity-flip control** (§6) fails to explain the result. Absent those, this is not a test. Default
expectation: `NO_SIGNAL` / `RANDOM_POLARITY_EXPLAINS` / `CONTEXT_ONLY_EXPLAINS`.

## 1. Motivation

Tracks C–F all tested some form of **alignment magnitude**: does the varṇa composition *point at*
the dictionary meaning (C), the emotional profile (D0), the context-correct candidate (E), or a
useful inference shift (F). All failed. One structural reason they might miss a real effect: the
varṇa content read as **affliction/tension vocabulary** (hope, fear, attachment, craving,
annihilation…), which rarely equals a word's dictionary sense and, when injected, acted as a
distractor. But affliction/tension vocabulary is exactly what you'd expect if varṇas encode not the
meaning itself but the **polarity field around it** — the axis of tension a meaning resolves or sits
on. Direct-match and flat-boundary tests cannot see this: a word whose meaning is the *positive*
pole of an axis will look *unrelated* to varṇa glosses naming the *negative* pole, and be scored as
"no match," when the real (hypothesized) relation is **oppositional**, not identical.

## 2. Core hypothesis

**H_G:** varṇa composition constrains a word's dictionary/contextual meaning through **polarity
axes** (a signed position on an opposition) rather than by direct semantic match. A word's meaning
"conforms" to its varṇa polarity vector either by **direct alignment** (same pole) or by **contrast**
(the opposite pole the meaning negates/resolves) — **but only if the intended relation (which pole,
which direction) is pre-registered per word before any scoring** (§4). Otherwise H_G is
unfalsifiable and no test is possible.

- **H0 (default):** it does not — a **random** polarity assignment explains as much
  (`RANDOM_POLARITY_EXPLAINS`), or **context** already fixes the pole (`CONTEXT_ONLY_EXPLAINS`), or
  a **scrambled** varṇa polarity works as well (`SCRAMBLE_EQUIVALENT`), or a **generic Barnum**
  polarity does (`BARNUM_POLARITY`), or there is simply no alignment (`NO_SIGNAL`).

## 3. Polarity axes (candidate set — to be frozen before use)

Signed oppositions; each word is pre-assigned a pole (or "off-axis") per axis:

- **expansion vs contraction**
- **clarity vs obscuration**
- **binding vs release**
- **desire vs contentment**
- **fear vs courage**
- **attachment vs freedom**
- **activity vs inertia**
- **ascent vs descent**
- **illumination vs darkness**
- **integration vs fragmentation**

The axis list, each varṇa's axis contributions, and each test word's target pole must all be
authored and hashed **before** scoring (blind to the scored outputs), with inter-annotator
agreement recorded and low-agreement items excluded.

## 4. No-random-flip rule (the load-bearing constraint)

**Polarity cannot be chosen after seeing the result.** For every word, the **direction of
conformance** (direct-alignment vs contrast) and the **target pole** on each axis are **frozen and
hashed before any scoring**. It is forbidden to score a word as "matches by contrast" *because*
direct alignment failed (or vice versa). If, at analysis time, either direction is accepted
per-word to maximize the score, the test is **invalid** (`INCONCLUSIVE` at best, and reported as a
protocol violation). A pre-registered, per-word, frozen polarity assignment is the only thing that
separates a real test from a post-hoc curve-fit.

## 5. Test design

Each case (pre-registered, frozen, hashed) contains:

- **dictionary meaning** of the word,
- **context** (a disambiguating sentence),
- **candidate meaning** (the context-correct reading),
- **opposite-pole candidate** (the reading on the other end of the target axis),
- **real varṇa polarity vector** (the word's pre-registered signed position across the §3 axes,
  derived from its varṇa composition + the frozen per-varṇa axis contributions),
- **scrambled polarity vector** (same axis magnitudes under a frozen scrambled varṇa→axis mapping),
- **Barnum polarity vector** (a generic "could-fit-anything" polarity profile),
- **context-only baseline** (no polarity vector).

Scoring asks whether the real polarity vector places the word on the **pre-registered** pole
(directly or by the pre-registered contrast direction) better than the controls — with the
direction fixed in advance, never chosen to fit.

## 6. Controls

Identical data/architecture; only the polarity input changes:

- **real polarity boundary** (the pre-registered varṇa polarity vector),
- **random polarity flip** (each axis sign randomized, frozen seed) — **the key control**: if
  random signs score as well, polarity carries no information,
- **scrambled varṇa polarity** (frozen scrambled varṇa→axis mapping),
- **Barnum polarity** (generic polarity profile),
- **context-only** (no polarity),
- **dictionary-only** (dictionary gloss, no context, no polarity).

The **random-polarity-flip** control is what makes the frozen-polarity rule (§4) enforceable: it
directly measures whether *sign* (which pole) matters, independent of the axis vocabulary.

## 7. Falsifiers

- **Random polarity flipping works as well as real polarity → no signal** (`RANDOM_POLARITY_EXPLAINS`):
  the sign carries no information; any polarity "matches."
- **Context-only works as well as real polarity → no signal** (`CONTEXT_ONLY_EXPLAINS`): context
  already fixes the pole; varṇa polarity adds nothing (the Track E-flat pattern recurring).
- **Barnum polarity works as well as real polarity → no signal** (`BARNUM_POLARITY`): a generic
  polarity profile suffices; not varṇa-specific.
- **Scrambled varṇa polarity works as well as real → no signal** (`SCRAMBLE_EQUIVALENT`).
- **Polarity chosen post-hoc → test invalid.** If direction/pole is selected after seeing outputs,
  the run is discarded (protocol violation), not scored as positive.

Any one of these blocks a `POLARITY_BOUNDARY_SIGNAL`.

## 8. Allowed labels

- `POLARITY_BOUNDARY_SIGNAL` — real polarity places words on their pre-registered pole better than
  **all** of random-flip, scramble, Barnum, context-only, and dictionary-only, with the direction
  frozen in advance, CI-lower > 0, and seed-stable.
- `RANDOM_POLARITY_EXPLAINS`
- `CONTEXT_ONLY_EXPLAINS`
- `SCRAMBLE_EQUIVALENT`
- `BARNUM_POLARITY`
- `NO_SIGNAL`
- `INCONCLUSIVE`

**Forbidden:** `ONTOLOGICAL_SIGNAL`, `SANSKRIT_PRIVILEGE`, any Track-B-unblocking or
validation-of-Symbol-U language. Even `POLARITY_BOUNDARY_SIGNAL` would support only "varṇa polarity
predicts a pre-registered pole in this architecture," never ontological truth, and would require
rigorous, independent replication — and it is only reachable at all if §4 is honored.

## 9. Boundary statement

Track G tests polarity-boundary behavior as a new hypothesis. It does not rescue prior negative tracks. Track B remains blocked. Structure, not validated meaning.
