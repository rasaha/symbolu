# Pre-Registration — Track F: Varṇa Boundary Inference-Steering Test (docs only)

**Pre-registration of a NEW hypothesis. Nothing implemented, run, or changed.** No experiment, no
scoring, no LLM call, no code, no artifact mutation. `frozen/manifest.json` remains NOT_READY;
runner remains NOT_RUN; Stage A untouched; **Track B remains BLOCKED**; no `ONTOLOGICAL_SIGNAL`, no
Sanskrit privilege. This authorizes nothing.

**Not a rescue of Track C / D0 / Track E.** Those tested dictionary-referent recovery (Track C: no
robust signal), experiential-weather matching (D0: `LLM_PILOT_NO_SIGNAL`), and candidate-boundary
selection (Track E-flat: `CONTEXT_ONLY_EXPLAINS`). Track F asks a **different** question —
inference *behavior change* — and its result cannot reinterpret, soften, or overturn those
negatives, which remain valid for what they tested.

**Skeptical preamble (read first).** The overwhelming prior is `PROMPT_PRIMING_ONLY`: injecting
*any* extra text ("consider this internal constraint: …") changes an LLM's output. So a raw A-vs-X
difference is **expected and uninteresting**. The entire test hinges on **specificity** — whether
the *real* varṇa boundary steers inference **differently and more usefully** than a *scrambled*
boundary (B) or a *generic Barnum* boundary (I) built from the same style of language. Absent that,
any "effect" is generic prompt priming, not a varṇa-specific phenomenon. A second trap is rewarding
**poetic noise**: an answer that becomes more evocative but less correct is harmful steering, not
utility. Default expectation: `PROMPT_PRIMING_ONLY` or `NO_EFFECT`.

---

## 1. Purpose

Track F tests whether injecting varṇa/vṛtti boundary text as a **soft constraint** into a real LLM
prompt **changes the model's inference behavior** — interpretation, ambiguity resolution, candidate
ranking, reasoning path, or answer style — in a way that is **specific to the real varṇa content**
and **useful without degrading correctness**. It is an **inference-steering / behavior-change**
test. It is **not** a test of semantic truth, dictionary recovery, experiential matching, or Track B
validation. Even a positive would mean only "these prompts steer *this* model's behavior in a
specific, useful way here" — an engineering/prompting effect, never evidence that varṇa meanings are
true.

## 2. Core distinction

Four distinct claims; only the fourth is Track F:

- **Track C — dictionary-referent recovery:** the varṇa sequence recovers a word's dictionary
  meaning. *Tested; no robust signal.*
- **D0 — experiential-weather matching:** the varṇa composition matches a word's emotional profile.
  *Tested; `LLM_PILOT_NO_SIGNAL`.*
- **Track E — candidate-boundary selection:** the varṇa boundary reweights candidate meanings toward
  the context-correct one. *Tested (flat); `CONTEXT_ONLY_EXPLAINS`, now closed.*
- **Track F — inference-behavior change (new):** whether varṇa-boundary-augmented *prompting* shifts
  a real LLM's *inference output* specifically and usefully, relative to normal prompting and to
  scrambled / dictionary-etymology / generic-Barnum boundary prompting. The unit is a **behavioral
  delta on the model**, not a claim about the varṇa content being correct.

## 3. Hypothesis

**H_F:** real varṇa boundary prompting produces a **specific, useful inference delta** beyond:
- **X** — the normal prompt (no boundary),
- **B** — a scrambled-varṇa boundary prompt (same glosses, permuted mapping),
- **F** — a dictionary/etymology-only prompt,
- **I** — a generic (Barnum) symbolic-boundary prompt.

**H0 (default):** it does not — either it changes nothing (`NO_EFFECT`), or it changes output no
more specifically than any boundary text (`PROMPT_PRIMING_ONLY`), or a scrambled/Barnum boundary
steers equivalently (`SCRAMBLE_EQUIVALENT` / `BARNUM_EQUIVALENT`), or it changes output while
**reducing** correctness (`CORRECTNESS_DEGRADED`). H_F is **incremental and specific**: real varṇa
must add over context *and* differ from scramble/Barnum, without harming correctness.

## 4. Prompt arms

Identical base model, task, and decoding; only the injected boundary text differs:

- **X — normal prompt:** the task, no boundary.
- **A — real varṇa boundary prompt:** the true varṇa/vṛtti composition, phrased as a soft "internal
  constraint / lens."
- **B — scrambled varṇa boundary prompt:** same glosses under a frozen scrambled mapping.
- **F — dictionary/etymology-only prompt:** the dictionary gloss and/or root prior, no varṇa.
- **I — generic Barnum symbolic-boundary prompt:** a generic "could-apply-to-anything" symbolic lens
  (the D0/Track E Barnum family, adapted).
- **R — random unrelated boundary prompt (optional):** an off-topic "constraint" of matched length/
  style, to bound the pure "any extra text" effect.

All boundary texts are matched for length/register so the comparison is content, not verbosity.
Arm identity is never shown to the scorer; arms are randomized and blinded.

## 5. Task types

Prompts span (per §11, 3–5 chosen for the smoke):

- **ambiguous word interpretation** (which sense is meant),
- **context-sensitive meaning** (meaning shifts with a supplied context),
- **moral / emotional interpretation** (read a situation's affective/ethical valence),
- **metaphor interpretation** (unpack a figurative expression),
- **candidate ranking** (order supplied interpretations),
- **short answer generation** (free-form answer to a prompt),
- **explanation style / reasoning-path analysis** (how the model justifies its answer).

Each task must have a **ground-truth or reference** where correctness is checkable (for the
correctness-preservation endpoint), plus room for interpretive variation (for the steering endpoint).

## 6. Primary endpoints

- **Inference-delta magnitude:** how much A's output differs from X (answer change rate, ranking
  shift, semantic distance of rationale) — measured but **not** sufficient alone.
- **Specificity (the crux):** A differs from **B** and **I**, not merely from X. If A ≈ B or A ≈ I,
  the effect is generic priming, not varṇa-specific.
- **Usefulness:** A **improves** judged answer quality / interpretive precision over X (and over B/I)
  on the same items.
- **Correctness preservation:** A does **not** reduce factual/contextual correctness vs X. A gain in
  "specificity" that costs correctness is **harmful steering**, not utility.
- **Stability:** the pattern holds across ≥ a few seeds and prompt phrasings (the Track C/D0/E lesson
  that single-seed borderline effects are not results).

Primary falsifier: if A is not **both** specific (≠ B and ≠ I) **and** correctness-preserving, H_F
fails regardless of raw A-vs-X magnitude.

## 7. Scoring

Blinded human judges and/or a **judge model** (generator ≠ scorer ≠ judge where feasible), scoring
anonymized outputs on:

- **answer correctness** (vs reference),
- **context fit**,
- **specificity** (targeted vs vague),
- **non-genericity** (not a one-size-fits-all reading),
- **usefulness** (does it help answer the task better),
- **over-poetic / noise penalty** (evocative-but-empty language is penalized, not rewarded),
- **hallucination penalty** (invented facts penalized),
- **task obedience** (did the answer actually do the requested task, in the requested format).

JSON/structured scoring; contamination probe (the judge must not be able to name a Sanskrit/varṇa/
root token from an anonymized output); malformed-output rate tracked.

## 8. Controls

A must **beat or differ specifically from** all of:

- **X** — normal prompt (there must be an effect at all),
- **B** — scrambled boundary (the *specific mapping* must matter),
- **I** — Barnum boundary (the effect must not be generic symbolic language),
- **F** — dictionary/etymology-only (varṇa must add beyond root/gloss priors).

**If A is not distinguishable from B or I → label `PROMPT_PRIMING_ONLY` (or the matching
scramble/Barnum-equivalent label), not a varṇa-specific effect.** The R arm (if used) bounds the
pure "any added text" effect. A positive requires A to be specifically distinct **and** useful
**and** correctness-preserving — not just different.

## 9. Decision labels

Allowed only:

- `INFERENCE_STEERING_SIGNAL` — A produces a specific (≠ B, ≠ I, ≠ F), useful, correctness-preserving
  inference delta over X, seed-stable.
- `PROMPT_PRIMING_ONLY` — A changes output but no more specifically than a generic boundary (A ≈ B or
  A ≈ I).
- `SCRAMBLE_EQUIVALENT` — scrambled boundary steers as well as real (no mapping-specific effect).
- `BARNUM_EQUIVALENT` — generic Barnum boundary steers as well as real.
- `CORRECTNESS_DEGRADED` — A changes output but reduces correctness (harmful steering).
- `NO_EFFECT` — A does not change output meaningfully vs X.
- `INCONCLUSIVE` — CIs include 0, high malformed rate, low judge agreement, or arms not separable.

**Forbidden:** `ONTOLOGICAL_SIGNAL`, `SANSKRIT_PRIVILEGE`, any Track-B-unblocking or
validation-of-Symbol-U language. Even `INFERENCE_STEERING_SIGNAL` supports only "these prompts steer
this model's behavior specifically and usefully in this setup," never ontological truth, and would
require independent replication before any strong claim.

## 10. Failure interpretations

- **All boundary prompts change output equally → `PROMPT_PRIMING_ONLY`.** The effect is "extra text
  in the prompt," not varṇa content.
- **Scrambled works as well as real → `SCRAMBLE_EQUIVALENT`.** No mapping-specific effect (the
  Track E/D0 pattern recurring).
- **Barnum works as well as real → `BARNUM_EQUIVALENT`.** A generic symbolic lens does the same;
  not varṇa-specific.
- **A changes output but reduces correctness → `CORRECTNESS_DEGRADED`.** Harmful steering; a
  poetic/specific-sounding answer that is more wrong is a cost, not a benefit.
- **A preserves correctness *and* adds specificity (≠ B, ≠ I) → possible
  `INFERENCE_STEERING_SIGNAL`** — the only outcome that would justify a larger, pre-registered
  Track F pilot. Even then it is engineering utility, not semantic validation.

## 11. Pilot design (recommendation; not frozen, not approved)

A small **exploratory smoke pilot**:

- **20–30 prompts**; **3–5 task types** from §5;
- **same base LLM** and **same decoding settings** across all arms;
- **randomized / blinded arms**; boundary texts length/register-matched;
- **no memory / no carryover** between prompts;
- **JSON / structured scoring** via blinded judge(s); generator ≠ scorer ≠ judge where feasible;
- contamination probe + malformed-rate gate; multi-seed/phrasing stability check;
- **result is exploratory triage only** — smoke size cannot validate; a positive only justifies a
  larger pre-registered pilot with CIs, seed stability, and independent replication.

Like prior tracks, this will be built **synthetic-first** (a harness proven on toy data with a
refusal-gated, no-model-call runner) before any real run is proposed and separately approved.

## 12. Relationship to the Track E revised smoke

Track E revised smoke and Track F are **separate**:

- **Track E revised smoke** tests candidate-*selection* under harder contexts (does the boundary pick
  the context-correct candidate once the context ceiling is removed) — a one-time confound check,
  currently parked.
- **Track F** tests inference-*output steering* (does boundary prompting change how the model
  answers, specifically and usefully).

Neither rescues the other, and neither reinterprets Track C / D0 / Track E-flat. A Track F result
says nothing about Track E's candidate-selection question, and vice versa.

**Four-sphere note:** the four-sphere varṇa lexicon remains **parked and not integrated**. A
four-sphere Track F variant (four-sphere boundary text as the A arm) is a **future, separate**
proposal requiring its own pre-registration, controls, and config; it is not part of this prereg.

## 13. Boundary statement

Track F tests whether varṇa boundary prompts steer LLM inference behavior. It does not validate varṇa truth, does not rescue Track C/D0/E, and does not unblock Track B. Structure, not validated meaning.
