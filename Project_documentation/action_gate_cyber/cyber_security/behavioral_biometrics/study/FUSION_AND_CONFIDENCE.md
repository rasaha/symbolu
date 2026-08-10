# Fusion & Confidence

## Fusion (`fusion.py`)

Two distinct problems, handled correctly:

**Same-latent fusion** — combine multiple estimates of the SAME quantity (e.g. keyboard
identity + pointer identity): inverse-variance weighting, quality weighting, calibrated
score fusion, and an explicit dependence (correlation) correction (covariance-whitened
fusion). Evaluated as an AUC contrast vs the best single modality (fit on train,
evaluated on test, participant-clustered bootstrap).

**Different-latent evidence** — identity vs liveness vs device-trust vs behavior-quality
vs context-consistency are DISTINCT channels, never subtracted as if they estimate the
same quantity. `fuse_channels` combines them with weighted logistic fusion +
**non-compensatory hard gates** (a failed hard gate caps the soft evidence and cannot be
outvoted), missing-modality handling (absent channels are dropped and lower evidence
sufficiency), and a conservative fallback when total uncertainty is high.

Comparison arms: best single modality · naive weighted sum · quality-aware fusion ·
dependence-aware fusion · non-compensatory fusion.

Outcomes: `FUSION_SUPPORTED` · `FUSION_SMALL_EFFECT` · `FUSION_NO_VALUE` ·
`FUSION_REGRESSES` · `FUSION_NOT_ELIGIBLE`. Mock emits `FUSION_PATH_VERIFIED_*`.

## Confidence (`confidence.py`)

Cleanly separates: raw model score → calibrated probability → uncertainty → quality →
evidence sufficiency → final confidence. An uncalibrated classifier probability is
**never** treated as confidence.

Calibration methods (NumPy/stdlib): Platt/logistic, histogram/bin, isotonic
(pool-adjacent-violators), with temperature-style scaling available. Calibration is fit
on a **calibration split** and evaluated on an **untouched test split** (chronological
held-out), so `CONFIDENCE_CALIBRATED` cannot be claimed without held-out evaluation and
calibration DRIFT surfaces as held-out miscalibration.

Metrics: Brier, ECE, MCE, reliability bins, NLL, selective-risk curve, coverage curve.

Structured output:

```json
{ "identity_probability": ..., "calibration_status": ..., "uncertainty": ...,
  "quality": ..., "evidence_sufficiency": ..., "confidence": ...,
  "recommended_evidence_action": "CONTINUE_PASSIVE | OBSERVE_MORE |
     REQUEST_PASSIVE_EVIDENCE | REQUEST_ACTIVE_EVIDENCE | INSUFFICIENT_EVIDENCE" }
```

The engine **never** returns ALLOW or DENY — the Action Gate owns decisions.

Outcomes: `CONFIDENCE_CALIBRATED` · `CONFIDENCE_SMALL_SAMPLE` ·
`CONFIDENCE_MISCALIBRATED` · `CONFIDENCE_NOT_ELIGIBLE`. Mock emits
`CONFIDENCE_PATH_VERIFIED_*`.

## Action-Gate evidence export (`evidence.py`)

A transport-neutral `EvidenceExport` (session id, timestamp, identity probability,
confidence, uncertainty, modality quality, evidence sufficiency, anomaly/CUSUM state,
coupling + BCVF diagnostics, calibration/model versions, data freshness, recommended
evidence action). It does **not** call or modify the Action Gate and **never** contains
an authorization decision — `validate()` fails closed on any `ALLOW`/`DENY` token.
