# Pre-Registration — Track G: Polarity Boundary Test (docs only)

**Pre-registration of a NEW hypothesis. Nothing implemented, run, or changed.** No experiment, no
scoring, no LLM call, no code, no artifact mutation. `frozen/manifest.json` remains NOT_READY;
runner NOT_RUN; Stage A untouched; four-sphere JSON parked/not integrated; **Track B remains
BLOCKED**; no `ONTOLOGICAL_SIGNAL`, no Sanskrit privilege. This authorizes **no run**.

**Not a rescue of Tracks C / D0 / E / F.** Those tested dictionary-referent recovery (no signal),
experiential-weather matching (`LLM_PILOT_NO_SIGNAL`), candidate-boundary selection
(`CONTEXT_ONLY_EXPLAINS`), and inference steering (`CORRECTNESS_DEGRADED`). Track G tests a
**different** relation (signed polarity boundary) and cannot reinterpret or soften those negatives.

**Skeptical preamble (this is the most flexible hypothesis in the arc).** Polarity lets a word
"conform" to a varṇa axis **either** by direct alignment **or** by contrast against the opposite
pole. If both directions are allowed to count as success *at analysis time*, the hypothesis is
**unfalsifiable** — every word matches somehow ("heads-I-win"). Track G is a valid test **only** if
(a) each word's polarity direction and target pole are **frozen before scoring** (§5), and (b) a
**random polarity-flip control** (§7) fails to explain the result. Absent either, the run is
`INVALID_POSTHOC_POLARITY`, not a positive. Default expectation: `NO_SIGNAL` /
`RANDOM_POLARITY_EXPLAINS` / `CONTEXT_ONLY_EXPLAINS`.

## 1. Executive position

Track G is a **fresh polarity-boundary hypothesis**: varṇa composition may constrain meaning by
placing it on a **signed position of an opposition** rather than by naming the meaning. It **does
not rescue** the prior failed tracks and takes no position on their questions; it stands or falls on
its own pre-registered evidence, under controls designed to catch the specific ways a flexible
polarity hypothesis can fake success.

## 2. Core hypothesis

**H_G:** varṇa composition constrains a word's dictionary/contextual meaning through **signed
polarity axes** (a pole on an opposition) rather than by direct semantic match. A word conforms
either by **direct alignment** (same pole) or by **contrast** (the opposite pole it
negates/resolves) — **but the intended direction and pole are pre-registered per word before any
scoring.**

- **H0 (default):** it does not — a **random** polarity assignment explains as much
  (`RANDOM_POLARITY_EXPLAINS`); or **context** already fixes the pole (`CONTEXT_ONLY_EXPLAINS`); or
  a **scrambled** varṇa polarity works as well (`SCRAMBLE_EQUIVALENT`); or a **Barnum** polarity
  does (`BARNUM_POLARITY`); or there is no alignment (`NO_SIGNAL`).

## 3. What Track G can and cannot prove

- **Can (at most) test:** whether a *pre-registered* real varṇa polarity boundary provides
  **incremental candidate-selection utility in this architecture**, beating random-flip, scramble,
  Barnum, context-only, and dictionary-only.
- **Cannot prove:** ontological truth, Sanskrit privilege, spiritual/experiential truth, or that
  varṇa meanings are "real." **It cannot unblock Track B.** Even a `POLARITY_BOUNDARY_SIGNAL` would
  be an architecture-bound, English/LLM-mediated engineering result requiring independent
  replication — never validation of Symbol-U.

## 4. Polarity axes (candidate set — frozen before use)

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

The axis list, each varṇa's per-axis contribution, and each word's target pole are authored and
**hashed before any scoring**, blind to outputs, agreement-gated; low-agreement items excluded.

## 5. Frozen polarity rule (load-bearing)

- **Sign/direction is assigned before scoring** and hashed; it is never chosen or changed after
  seeing outputs.
- **No post-hoc polarity flipping** — a word scored as "matches by contrast" *because* direct
  alignment failed (or vice versa) is a **protocol violation**.
- Each case must specify, in advance, whether the expected relation is:
  - **direct alignment** (word sits on the same pole as its varṇa polarity), or
  - **contrast / opposite-boundary** (word sits on the pole its varṇa polarity negates/resolves), or
  - **excluded** if the relation is ambiguous or low-agreement.
- Illustrative pre-registered directions (must be frozen, not tuned): *happy* bounded by the
  resolution of fear/craving/attachment/lack; *peace* against agitation/conflict/craving/withdrawal;
  *courage* against fear; *freedom* against attachment/bondage; *knowledge* against
  obscuration/confusion.

## 6. Dataset design

Each case (pre-registered, frozen, hashed) contains:

- **word / concept**,
- **context** (disambiguating sentence),
- **dictionary meaning**,
- **target polarity candidate** (the pre-registered correct reading/pole),
- **opposite-pole candidate** (the other end of the target axis),
- **hard-negative candidates** (semantically adjacent, on/near the axis),
- **real varṇa polarity vector** (the frozen signed position across §4 axes, from the varṇa
  composition + frozen per-varṇa axis contributions),
- **scrambled varṇa polarity vector** (same axis magnitudes under a frozen scrambled varṇa→axis
  mapping),
- **random-flip polarity vector** (each axis sign randomized, frozen seed),
- **Barnum polarity vector** (a generic "could-fit-anything" polarity profile).

Blind authoring, inter-annotator agreement recorded, low-agreement items excluded, all inputs hashed
before any run.

## 7. Controls

Identical data/architecture; only the polarity input changes:

- **A — real frozen polarity boundary** (pre-registered varṇa polarity vector),
- **R — random polarity flip** (axis signs randomized, frozen seed) — **the key control**: measures
  whether *sign* carries information at all,
- **B — scrambled varṇa polarity** (frozen scrambled varṇa→axis mapping),
- **I — Barnum / generic polarity boundary** (generic polarity profile),
- **X — context-only** (no polarity),
- **D — dictionary-only** (dictionary gloss, no context, no polarity).

## 8. Primary endpoint

The **real frozen polarity boundary (A)** must beat **all** of: random polarity flip (R), scrambled
polarity (B), Barnum polarity (I), context-only (X), and dictionary-only (D), at placing each word on
its **pre-registered** pole/target candidate. Metrics: **MRR, Top-1, pairwise accuracy** on the
target candidate, with **family-aware bootstrap CIs (CI lower > 0 for each contrast)** and multi-seed
stability **if sample size permits** (a smoke pilot reports point deltas and is exploratory only).
`A_vs_R` (does sign matter) and `A_vs_X` (incremental over context) are the two primary bars; A must
clear **every** control, not just one.

## 9. Critical falsifiers

- **Random polarity flip performs as well as real (A ≈ R)** → `RANDOM_POLARITY_EXPLAINS` (sign
  carries no information; any polarity "matches").
- **Context-only performs as well as real (A ≈ X)** → `CONTEXT_ONLY_EXPLAINS` (context already fixes
  the pole; the Track E-flat pattern recurring).
- **Scrambled polarity performs as well as real (A ≈ B)** → `SCRAMBLE_EQUIVALENT`.
- **Barnum polarity performs as well as real (A ≈ I)** → `BARNUM_POLARITY`.
- **Polarity direction chosen post-hoc** → `INVALID_POSTHOC_POLARITY` (run discarded; not a
  positive, not scored as signal).

Any one blocks a `POLARITY_BOUNDARY_SIGNAL`.

## 10. Allowed labels

- `POLARITY_BOUNDARY_SIGNAL` — A beats R, B, I, X, and D on the pre-registered pole, direction frozen
  in advance, CI-lower > 0, seed-stable.
- `RANDOM_POLARITY_EXPLAINS`
- `CONTEXT_ONLY_EXPLAINS`
- `SCRAMBLE_EQUIVALENT`
- `BARNUM_POLARITY`
- `NO_SIGNAL`
- `INCONCLUSIVE`
- `INVALID_POSTHOC_POLARITY`

**Forbidden:** `ONTOLOGICAL_SIGNAL`, `SANSKRIT_PRIVILEGE`, any Track-B-unblocking or
validation-of-Symbol-U language.

## 11. Leakage and circularity controls

- **No root-name leakage** (moha/bhaya/kāma/… never in scorer-facing fields).
- **No surface-word leakage** where blinding requires hiding the word (esp. famous words).
- **No candidate-label leakage** (roles: target / opposite-pole / hard-negative hidden from the
  scorer; anonymized candidate ids; shuffled order).
- **No post-hoc axis selection** — the axis set and per-word pole are frozen before scoring.
- **No hand-tuning after seeing outputs** — no re-editing of polarity, axes, contexts, or candidates
  once any output is observed.
- **Random-flip control mandatory** — a run without R is invalid; R is what makes the frozen-polarity
  rule (§5) enforceable.
- (For an LLM-scored pilot, the D0/E/F blinding + contamination-probe protocol applies:
  generator ≠ scorer ≠ judge where feasible; anonymized packets; JSON-only; malformed-rate gate.)

## 12. Relation to prior tracks

- **Track C** remains **negative** (no robust dictionary-referent recovery).
- **Track D0** remains **negative** (`LLM_PILOT_NO_SIGNAL`; `BARNUM_OVERMATCH` + `SCRAMBLE_EQUIVALENT`).
- **Track E-flat** remains **`CONTEXT_ONLY_EXPLAINS`** (closed).
- **Track F** remains **`CORRECTNESS_DEGRADED`** (no useful steering).
- **Track G does not reinterpret, soften, or rescue any of them.** A Track G result says nothing
  about their questions, and theirs say nothing about Track G's. Track B stays blocked regardless.

## 13. Next-step gate

After this pre-registration, the **only** next allowed step is a **docs-only Track G implementation
plan + synthetic-harness design** (schemas, controls incl. random-flip, packet/blinding format,
metrics, decision logic, and toy-fixture plan). **No real run is authorized by this
pre-registration.** A real run would additionally require: a synthetic-first harness proven on toy
data, a frozen `track_g_config` bundle, a separate approved run config, a completed approval
checklist, and an explicit go decision — none of which exist.

## 14. Boundary statement

Track G tests polarity-boundary behavior as a fresh hypothesis. It does not rescue prior negative tracks. Track B remains blocked. Structure, not validated meaning.
