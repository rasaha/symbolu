# USE Evaluation Protocol

USE is an **evaluation label** for the cross-modal coupling contribution — not a
privileged formula (`use_eval.py`). It answers: does context-conditioned coupling add
identity information beyond fair multimodal marginals, and is that beyond what shuffled
or task/context-matched controls explain?

## Representations (fixed a priori)

Lagged cross-correlation, zero-lag cross-correlation, event cross-correlogram, windowed
CCA (and, where continuous streams exist, spectral/wavelet coherence; phase-based
features only where instantaneous phase is meaningful). No representation is selected
after seeing test results.

## Arms

- `MM` — all-modalities marginals (quality-aware), the FAIR baseline.
- `MM_SHUFFLED` — MM + time-shuffled coupling (destroys cross-modal alignment, keeps
  marginals) — controls "coupling is just marginals".
- `MM_COUPLING` — MM + real coupling.
- `MM_COUPLING_CONTEXT` — MM + context-conditioned coupling (real residualized against
  the task/UI/device-matched control) — controls "coupling is just task-forced".

## Primary comparisons (context-conditioned coupling must beat BOTH)

- `MM_COUPLING_CONTEXT − MM`
- `MM_COUPLING_CONTEXT − MM_SHUFFLED`

paired, participant-clustered bootstrap. Diagnostics: raw vs context-conditioned
coupling; same-user vs live-impostor; same-device vs different-device; timestamp
perturbation.

## Mechanical outcomes

- `USER_SPECIFIC_COUPLING_SUPPORTED` — beats marginal AND shuffle by the practical
  margin, survives context conditioning and the device gate.
- `USER_SPECIFIC_COUPLING_SMALL_EFFECT` — favorable but below the practical margin.
- `DEVICE_BOUND_COUPLING_ONLY` — gain collapses across devices.
- `HUMANNESS_SIGNAL_ONLY` — coordination real (beats shuffle) but no identity gain over
  marginals.
- `SAMPLING_OR_CONTEXT_ARTIFACT` — the gain does not survive the shuffle/context control.
- `COUPLING_NOT_SUPPORTED` — no gain.

Mock/stub data returns `USE_PATH_VERIFIED`, never the scientific verdict.

## Fairness guard

Coupling is **never** credited merely for adding modalities or feature slots. The
`MM_SHUFFLED` control has the same coupling slots with decorrelated values, so a gain
from extra capacity alone shows up equally in the shuffled arm and is not credited
(`tests/test_identity_and_use.py::test_use_cannot_be_credited_for_extra_modalities`).
