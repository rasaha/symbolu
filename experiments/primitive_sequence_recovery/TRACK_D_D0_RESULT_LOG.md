# Track D — D0 Real Pilot Result Log (exploratory triage)

**Exploratory triage result. Not validation.** No `EXPERIENTIAL_WEATHER_SIGNAL`, no
`ONTOLOGICAL_SIGNAL`, no Sanskrit privilege. `manifest.json` remains NOT_READY; the psr runner
remains NOT_RUN; Stage A untouched; **Track B remains BLOCKED.** Per the no-rescue rule
(`TRACK_D_D0_ERROR_TAXONOMY.md`), this result cannot be converted into a positive.

## Run

- **Environment:** RunPod, NVIDIA RTX 6000 Ada (48 GB), Python 3.12, CUDA available.
- **Repo/commit:** `b803a83` (branch `claude/symbolu-adversarial-eval-zevb4h`).
- **Config:** `/workspace/d0_config.json` from `build_d0_config.py` — 24 words
  (8 abstract_primary + 10 concrete_control + 6 famous_exploratory), consonant-only,
  contamination-reduced.
- **Models (cross-model; generator ≠ scorer):** generator `Qwen/Qwen2.5-7B-Instruct`,
  scorer `mistralai/Mistral-7B-Instruct-v0.3`. Deterministic decoding; loaded sequentially.
- **Full report (pod-local, not committed):** `/workspace/d0_report.json`.

## Result

- **Primary label:** **`LLM_PILOT_NO_SIGNAL`**
- **Error taxonomy:** `BARNUM_OVERMATCH = true`, `SCRAMBLE_EQUIVALENT = true`
- Harness synthetic sanity tests passed before the run; guardrails after the run: manifest
  NOT_READY, psr runner NOT_RUN, Stage A untouched. (The wrapper's final "GUARD FAIL:
  ONTOLOGICAL_SIGNAL" line on this run was a **false positive** — a naive substring grep matched
  the disclaimer note; fixed to check label fields only. The actual primary label is
  `LLM_PILOT_NO_SIGNAL`; no forbidden label was emitted.)

## Honest interpretation

- **`BARNUM_OVERMATCH`:** the real varṇa/vṛtti composition matched a generic Barnum profile
  (`max(I₁..I₄)`) at least as well as the word's own specific profile. This is the predicted
  outcome: the vṛtti glosses *are* affliction concepts, so the affliction/wound Barnum profile
  (I₃) fits them about as well as any specific profile.
- **`SCRAMBLE_EQUIVALENT`:** the real assignment scored no better than a scrambled assignment of
  the same glosses — the specific varṇa→gloss mapping carried no advantage.
- Together: under this cross-model, English-mediated, consonant-only D0 setup, there is **no
  evidence** that varṇa composition predicts an experiential-weather profile beyond a generic
  emotional profile or a random reassignment. This is **consistent with the Track C V1 negative**
  (no robust dictionary-referent signal) and does **not** support Symbol-U.

## Consequence (per the roadmap)

- **Triage decision:** on this evidence, **D1 human-blind validation is NOT justified** for the
  experiential-weather construct as posed. A `LLM_PILOT_NO_SIGNAL` is a legitimate,
  money-saving triage outcome — not a failure of the pipeline.
- **No rescue:** this result must not be reinterpreted as positive. Any reformulated construct
  (e.g. an affliction-field or guṇa/polarity hypothesis suggested by the taxonomy) would require
  a **new, separate pre-registration** authored before looking at more data — it is a lead, not a
  finding.
- Version 1's conclusion is unchanged and reinforced: the framework works and is honest; the
  confirmatory question (Track B) remains blocked; the theory remains untested-not-disproven, and
  now this exploratory probe also returns no signal.

> D0 exploratory triage only. No validation. Track B remains blocked. Structure, not validated
> meaning.
