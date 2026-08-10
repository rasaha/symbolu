# Study Runner

The complete, executable evaluation pipeline for the behavioral identity study. It is
built so that, once eligible **real** participant sessions exist, the full study runs
without redesigning or implementing new algorithms. In this phase it is exercised only
on clearly-labeled **MOCK_TEST_ONLY** fixtures and emits **no** scientific claim.

## Pipeline (`runner.run_study`)

1. Validate origin + claim lock (`origin.py`).
2. Check sample eligibility (`effects.MinimumSamples`).
3. Build leakage-safe splits (`splits.py`); verify no leakage.
4. Fit all transforms on training folds only (`baselines`, train-only standardizer).
5. Train modality baselines (K / P / T / M).
6. Train fair multimodal marginals (MM) with quality-aware fusion.
7. Evaluate coupling arms (MM_SHUFFLED / MM_COUPLING / MM_COUPLING_CONTEXT → USE).
8. Evaluate BCVF arms (MM_BCVF vs MM_BCVF_NO_DISAGREEMENT).
9. Evaluate fusion arms (best-single vs quality/dependence-aware fusion).
10. Fit confidence calibration on a held-out calibration split only.
11. Evaluate on the untouched test split.
12. Bootstrap **paired, participant-clustered** contrasts (`metrics.py`).
13. Apply frozen practical-effect thresholds (`effects.py`).
14. Emit a machine-readable report (`report.py`).
15. Emit the claim lock based on origin.

## Frozen fair arms (`arms.py`)

`K, P, T, M` (single modality) · `MM` (all marginals, quality-aware) · `MM_SHUFFLED`
(marginals + shuffled coupling control) · `MM_COUPLING` (+ real coupling) ·
`MM_COUPLING_CONTEXT` (+ context-conditioned coupling) · `MM_BCVF` /
`MM_BCVF_NO_DISAGREEMENT` (capacity-matched BCVF contrast) · `FULL`.

Equalization: same participants, trials, modality availability, preprocessing,
train/test split, and model family across arms. **No arm is credited for receiving more
modalities or more parameters** — coupling arms add only coupling slots; the BCVF arms
are capacity-matched (matched noise feature vs the disagreement feature).

## CLI

```bash
S="python -m cyber_security.behavioral_biometrics.study.cli"
$S prereg-template --out prereg.json
$S generate-mock --regime COUPLING_ONLY_SIGNAL --out mock.json
$S validate --data mock.json
$S run-identity --regime KEYBOARD_ONLY_SIGNAL
$S run-coupling --regime COUPLING_ONLY_SIGNAL
$S run-bcvf --regime BCVF_HELPFUL
$S run-fusion --regime FUSION_HELPFUL
$S calibrate --regime CONFIDENCE_MISCALIBRATED --method isotonic
$S run-temporal --regime ABRUPT_TAKEOVER
$S run --regime COUPLING_PLUS_MARGINAL_SIGNAL --temporal SLOW_TAKEOVER --output report.json
$S export-evidence --regime MULTIMODAL_MARGINAL_SIGNAL
$S report --input report.json
```

## Report sections

dataset eligibility · quality summary · marginal identity · multimodal fusion ·
coupling/USE · BCVF · confidence calibration · temporal diagnostics · confound/artifact
gates · mechanical verdicts · limitations · origin banner.

## Claim lock

On non-real data the report's `origin_banner` is **TEST DATA ONLY — NO BIOMETRIC
CLAIM** and every verdict is a `*_PATH_VERIFIED` / `*_NO_SCIENTIFIC_VERDICT` outcome.
Positive scientific verdicts (`*_SUPPORTED`, `CONFIDENCE_CALIBRATED`) are reachable
**only** on eligible `REAL_PARTICIPANT` data. See `REAL_DATA_ELIGIBILITY.md`.
