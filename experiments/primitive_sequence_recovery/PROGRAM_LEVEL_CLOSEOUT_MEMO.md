# Program-Level Closeout Memo — Symbol-U / Varṇa Semantic-Evaluation Arc

**Closeout memo only. Nothing run, scored, or changed.** No experiment, no LLM/scorer call, no
network. `frozen/manifest.json` remains NOT_READY; runner NOT_RUN; Stage A untouched; four-sphere
JSON parked/not integrated; **Track B remains BLOCKED**; no `ONTOLOGICAL_SIGNAL`, no Sanskrit
privilege. This memo summarizes results to date; it does **not** reinterpret any negative as a
positive or weaken any prior result.

## 1. Executive conclusion

**Four practical operationalizations of the varṇa semantic hypothesis have been tested (Tracks C,
D0, E-flat, F), and none demonstrated useful or robust varṇa semantic signal.** Dictionary-referent
recovery, experiential-weather matching, candidate-boundary selection, and inference-output steering
each returned a negative or no-signal result under adversarial controls. The evaluation framework
itself performed as designed — it rejected weak positives — and the core ontological claim remains
**untested, not validated**. The confirmatory, non-circular path (Track B) was never opened and
remains blocked.

## 2. Scoreboard

| Track | Question / status | Result | Implication |
|---|---|---|---|
| **C** — dictionary-referent recovery | Do varṇa sequences recover a word's dictionary meaning? | **No robust signal** (borderline/seed-fragile effects did not survive; domain-mismatch + leakage/collision limits) | Direct semantic recovery not demonstrated |
| **D0** — experiential-weather matching | Does flat varṇa/vṛtti composition match a word's emotional profile? | **`LLM_PILOT_NO_SIGNAL`** (`BARNUM_OVERMATCH` + `SCRAMBLE_EQUIVALENT`) | No match beyond generic/scrambled controls |
| **E-flat** — candidate boundary selection | Does the varṇa boundary reweight candidates toward the context-correct one? | **`CONTEXT_ONLY_EXPLAINS`** (context solved 11/12; A beat only dictionary-only) | Boundary adds nothing over context; do not scale |
| **F** — inference-output steering | Does varṇa-boundary prompting usefully steer a real LLM's inference? | **`CORRECTNESS_DEGRADED`** (distinctive steer, but correctness/usefulness dropped; single-model-judge caveat) | No useful steering demonstrated |
| **Four-sphere representation** | Alternative richer varṇa input? | **Unvalidated candidate artifact; parked / not integrated** | Not evidence; not validation |
| **Track G** — polarity-boundary | New hypothesis: signed polarity axes, direct or contrast? | **Hypothesis note only; not run** | Requires frozen polarity + random-flip control before any run |
| **Track B** — confirmatory / non-circular | An ontology-supporting, non-circular validation path? | **BLOCKED** (unreachable in this environment) | No confirmatory evidence exists |

## 3. What failed

- **Dictionary-referent recovery (C) failed.** Any apparent effect was seed-fragile and did not
  survive family-bootstrap CIs / multi-seed stability; the failure audit found semantic-domain
  mismatch (affliction-vṛttis vs concrete/abstract referents) and leakage/collision limits, not a
  recoverable mapping.
- **Experiential-weather matching (D0) failed.** The real composition matched a generic Barnum
  profile at least as well as the word's own (`BARNUM_OVERMATCH`) and no better than a scrambled
  assignment (`SCRAMBLE_EQUIVALENT`).
- **Boundary candidate selection (E-flat) was explained by context.** Context-only ranked the
  correct candidate #1 in 11/12 cases; the real boundary was worse than context and lost to
  scrambled, etymology-only, and Barnum, beating only the (weak) dictionary-only baseline —
  insufficient.
- **Inference steering (F) degraded correctness/usefulness.** The real boundary did steer
  distinctively versus some controls, but the steer reduced correctness with no usefulness gain
  (`CORRECTNESS_DEGRADED`) — and even that is soft, given the single-model self-judge.

## 4. What did not fail

- **The evaluation framework worked.** Pre-registration, frozen inputs, blinded/anonymized packets,
  refusal-gated no-model-call runners, and adversarial controls consistently caught weak positives
  and produced honest labels.
- **The guardrails worked.** `frozen/manifest.json` stayed NOT_READY, base run manifests stayed
  `run_enabled:false` / `NOT_APPROVED`, Stage A was never touched, forbidden labels were asserted
  against, and no run occurred without an explicit separate approval.
- **Negative results were preserved** — none was reinterpreted, softened, or rescued.
- **The broader architecture / patent infrastructure is not automatically disproven.** These tests
  falsified *specific semantic operationalizations*, not every possible use of the framework; a
  symbolic-control / structural application stands or falls on its own separate evidence.
- **The core ontological claim remains untested, not validated.** Track B (the only path that could
  confirm it non-circularly) was never opened; "not demonstrated" here means *unshown*, not
  *disproven* — and equally, *not validated*.

## 5. Main cross-track failure mechanisms

- **Barnum overmatch** — a generic "could-fit-anything" profile matches the affliction-vṛtti
  composition as well as the specific target (D0).
- **Scramble equivalence** — a scrambled varṇa→gloss mapping scores as well as the real one; the
  specific assignment carries no advantage (D0, E, F).
- **Context dominance** — context alone already selects the answer, leaving no headroom for the
  boundary (E-flat).
- **Semantic-domain mismatch** — affliction/tension vocabulary rarely equals a word's dictionary or
  experiential sense (C, D0).
- **Flat affliction-boundary mismatch on concrete controls** — on river/mountain/house the boundary
  actively mis-ranked the correct meaning (E-flat).
- **Correctness degradation under steering** — injecting the boundary changed outputs but slightly
  reduced correctness/usefulness (F).
- **English / LLM-mediation ceiling** — all tests run through English glosses and a specific model;
  even a positive would be capped by this and require non-English / independent replication.
- **Researcher-authored representation risk** — richer representations (e.g. four-sphere) are
  researcher interpretations (high degrees of freedom), so they raise, not lower, the evidentiary
  bar.
- **Post-hoc polarity risk** — a polarity hypothesis (G) that allows both direct and contrast
  conformance is unfalsifiable unless sign/direction is frozen before scoring and a random-flip
  control is run.

## 6. Decision

- **Do not use Tracks C / D0 / E-flat / F as evidence of semantic truth.** They are negative or
  no-signal results.
- **Do not unblock Track B.** No non-circular confirmatory path exists in this environment.
- **Do not scale Track E-flat or Track F as currently designed** to a full pilot.
- **Preserve these results as evidence of disciplined falsification** — the arc's value is a
  framework that kills weak hypotheses cleanly and keeps unvalidated claims quarantined.

## 7. Allowed future paths (fresh, separately-approved hypotheses only)

Each requires its **own** pre-registration, controls, config, and approval — none is a rescue:

- **answer ≠ judge Track F re-run** (distinct judge model, finer scale) to test whether F's small
  correctness cost is real or a self-judge artifact;
- **Track E-FS** — four-sphere boundary variant of candidate selection;
- **Track F-FS** — four-sphere steering variant;
- **one revised harder-context Track E smoke**, only if explicitly pre-registered (with the binding
  one-rerun stop rule already on file);
- **Track G polarity-boundary test**, only with frozen sign/direction rules and the random-flip
  control;
- a **non-English / non-LLM / human-blind validation path** (the only kind that could begin to
  address the mediation ceiling and, eventually, Track B);
- **shift focus away from semantic-truth claims toward symbolic-control / structural architecture**,
  evaluated on its own engineering merits.

## 8. Investor / researcher-safe wording

> We ran adversarial exploratory tests of the varṇa semantic-recovery and steering hypotheses. The
> tests did not support using those semantic claims as validation. The useful outcome is that the
> framework rejects weak positives and keeps unvalidated symbolic claims separate from engineering
> architecture.

## 9. No-rescue rule

None of the negative tracks (C, D0, E-flat, F) may be reinterpreted as positive, partial-positive,
or "trending." Four-sphere and Track G remain **new hypotheses only**. Any future variant must
**start from its own pre-registration and controls**, authored before looking at more data; it may
not reuse, soften, or retrofit a prior negative. A positive, if one ever appears, would be a *new*
result under a *new* protocol — never a re-reading of these.

## 10. Boundary statement

Program-level closeout: no robust or useful varṇa semantic signal has been demonstrated across Tracks C, D0, E-flat, or F. Track G and four-sphere variants remain new hypotheses only. Track B remains blocked. Structure, not validated meaning.
