# Track D Roadmap — D0 (LLM pilot) / D1 (human-blind, deferred) (docs only)

**Planning only. No scoring, no experiment, no results.** `manifest.json` remains NOT_READY; the
runner remains NOT_RUN; Stage A untouched; **Track B remains BLOCKED**; no `ONTOLOGICAL_SIGNAL`;
no Sanskrit privilege; the Track C V1 negative (no robust dictionary-referent signal) stands.

Track D (experiential semantic-weather recovery, `PREREG_TRACK_D_EXPERIENTIAL_WEATHER.md`) is
split into two stages so a cheap triage can inform whether the rigorous version is worth funding.

---

## Why the split

The rigorous protocol requires **independent human annotators** authoring **blind** profiles
with inter-rater agreement (`TRACK_D_IMPLEMENTATION_PLAN.md` §4–5). That is an operational burden
being **deferred** (appropriate post-funding). In the interim, an **LLM-scored exploratory
pilot** can triage — fast, cheap — whether the hypothesis shows *any* promise worth the later
rigorous investment. The pilot is explicitly **weaker** and cannot produce a Track D verdict.

| | **D0 — LLM pilot (now)** | **D1 — human-blind validation (deferred)** |
|---|---|---|
| profiles | **LLM-generated** from dictionary meaning | **human**, blind, agreement-gated |
| scorer | **LLM judge** (contamination-prone) | fixed deterministic offline scorer |
| purpose | **triage only** | rigorous validation |
| strongest label | `LLM_PILOT_SUGGESTIVE` | `EXPERIENTIAL_WEATHER_SIGNAL` |
| status | plan ready; run on approval | **deferred** (post-funding) |

## Stage D0 — LLM-scored exploratory pilot (acceptable now, as triage)

- **Acceptable now because:** it is cheap, fast, and only used to *triage* — decide whether D1 is
  worth funding. It changes nothing about the recorded findings.
- **Contamination-prone by construction:** the judge LLM likely knows Sanskrit, the words, and
  cultural/symbolic lore; and the **profiles are LLM-generated**, so a "match" can be the model's
  own internal consistency (its notion of "anger" matching its own reading of the glosses) rather
  than signal. Mitigated (two-stage blinding, anonymization, cross-model generator≠scorer,
  contamination probes) but **not eliminated**.
- **Cannot produce a strict `EXPERIENTIAL_WEATHER_SIGNAL`.** Allowed labels only:
  `LLM_PILOT_SUGGESTIVE`, `LLM_PILOT_NO_SIGNAL`, `LLM_PILOT_INCONCLUSIVE`,
  `LLM_PILOT_CONTAMINATED`.
- **What D0 can support:** "worth (or not worth) the cost of D1." Nothing more.
- **What D0 cannot support:** validation, `EXPERIENTIAL_WEATHER_SIGNAL`, `ONTOLOGICAL_SIGNAL`,
  Sanskrit privilege, Track B readiness, or any weakening of Track C V1.
- Full design: `TRACK_D_LLM_SCORER_PILOT_PLAN.md`.

## Stage D1 — human-blind validation (deferred, required for rigorous claims)

- **Deferred, not executed.** To be undertaken **after funding/resources** permit independent
  human annotation.
- Requires: independent human annotators; frozen controlled vocabulary; **blind** profile
  construction; inter-rater agreement; the full control battery and robustness plan
  (`TRACK_D_IMPLEMENTATION_PLAN.md`).
- **The final Track D decision labels (`EXPERIENTIAL_WEATHER_SIGNAL` / `NO_SIGNAL` /
  `REALIZER_DEPENDENT` / `INCONCLUSIVE`) are only obtainable in D1.** A `LLM_PILOT_SUGGESTIVE` at
  D0 is a *reason to fund D1*, never a substitute for it.

## Decision flow

```
D0 LLM pilot (triage)
  ├─ LLM_PILOT_NO_SIGNAL / CONTAMINATED  → do NOT fund D1 (hypothesis not worth rigorous cost)
  ├─ LLM_PILOT_INCONCLUSIVE              → refine pilot or shelve
  └─ LLM_PILOT_SUGGESTIVE                → consider funding D1 (human-blind), which alone can
                                           yield a rigorous Track D verdict
```

A suggestive D0 never becomes a claim on its own; it only unlocks the *option* to run D1.

---

D0 is exploratory triage only. D1 human-blind validation is deferred. Track B remains blocked.
Structure, not validated meaning.
