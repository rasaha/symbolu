# Behavioral Biometrics — Instrumentation & Signal-Quality Pilot

A local telemetry-collection and analysis pipeline for **one narrow question**:

> Can we collect synchronized, privacy-conscious behavioral telemetry with sufficient
> timing quality and repeated-session stability to support a *later* real-data
> signal-existence study?

This phase is **instrumentation, not proof**. It does **not** attempt to prove BCVF,
USE, SCC, continuous authentication, or takeover detection, and it makes **no
biometric-validity claim**. BCVF/USE/SCC and phase features are **not** privileged
here (see `../BCVF_CONCEPT_DIRECTION.md`, `../USE_CONTRIBUTION_MAP.md`).

The action-gateway packages are separate and untouched by this work.

## What it is

```
collector → synchronized event schema → quality gate → privacy-safe features
          → leakage-safe splits → strong baselines → signal-existence analyses
          → mechanical, preregistered verdicts (refused on synthetic data)
```

- **Collector** (`collector.py`) — session lifecycle, receipt-stamping, sequence
  numbers, privacy sanitization at ingest (raw keyboard content never stored).
- **Schema** (`schema.py`, `EVENT_SCHEMA.md`) — fail-closed multimodal event schema
  (keyboard / pointer / touch / motion / context) with full timing + provenance.
- **Quality gate** (`quality.py`) — event-loss / duplicate / reorder / clock-drift /
  jitter / quantization / latency / activity diagnostics → a mechanical
  `INSTRUMENTATION_READY | _DEGRADED | _NOT_READY` verdict (thresholds frozen in
  `config.py`, documented in `INSTRUMENTATION_THRESHOLDS.md`). Poor sessions are
  **excluded from identity analysis with a recorded reason — never silently dropped.**
- **Privacy** (`privacy.py`, `PRIVACY_AND_ETHICS.md`) — key-class mapping, field
  suppression, redaction, deletion, retention, consent hooks, at-rest encryption.
- **Features** (`features.py`, `coupling.py`) — deterministic, versioned keyboard /
  pointer / touch / motion marginals + cross-modal coupling candidates **with matched
  shuffled and context-matched controls**. Identifiers are never model features.
- **Splits** (`splits.py`) — session-disjoint, live-impostor, task-disjoint,
  device-instance, and participant-disjoint (transfer) splits with a leakage checker.
- **Baselines** (`baselines.py`) — prototype / Mahalanobis / nearest-centroid identity,
  a local-linear-trend Kalman + CUSUM temporal observer, and a fair quality-weighted
  multimodal fusion (no coupling). All fits are **train-only**.
- **Analyses** (`analysis.py`) — A instrument quality · B within-user repeatability ·
  C marginal identity · D coupling residual (real vs shuffled vs context controls) ·
  E device-instance confound · F task/context confound — all with bootstrap CIs.
- **Verdicts** (`verdicts.py`) — preregistered mechanical outcomes with two hard
  guards: **synthetic data yields no identity/coupling verdict**, and **real-data
  minimum-sample requirements** must be met before any positive verdict.

## Run

```bash
# generate a clearly-marked SYNTHETIC_TEST_ONLY cohort into a local store
python -m cyber_security.behavioral_biometrics.cli --root /tmp/bbio synthetic \
    --participants 12 --sessions 4 --coupling 0.6 --second-device

python -m cyber_security.behavioral_biometrics.cli --root /tmp/bbio quality
python -m cyber_security.behavioral_biometrics.cli --root /tmp/bbio features
python -m cyber_security.behavioral_biometrics.cli --root /tmp/bbio splits --type session_disjoint
python -m cyber_security.behavioral_biometrics.cli --root /tmp/bbio baseline evaluate
python -m cyber_security.behavioral_biometrics.cli --root /tmp/bbio pilot report

# 14 executable demonstrations
python -m cyber_security.behavioral_biometrics.demos.demo

# tests
python -m pytest cyber_security/behavioral_biometrics/tests/ -q
```

Real collection is performed manually per `DATA_COLLECTION_PROTOCOL.md` (an OS
input-hook adapter binds the task specs to real events; the adapter is out of scope
for this phase and documented, not implemented).

## Runtime & dependencies

Python 3.11, **numpy only** (no scipy/sklearn — all numerics are implemented in
`numerics.py`). Deterministic: every random draw is seeded; core code reads no clock,
RNG, or network. Storage is local JSONL with optional stdlib at-rest encryption.

## Integrity guarantees (enforced in code + tests)

- No raw typed content is stored by default (keyboard is key-class + salted id only).
- Participant / device / session identifiers are **never** model features.
- Normalization and residualization are fit on **training folds only**.
- Coupling is credited only if it beats a fair all-modalities marginal baseline **and**
  its shuffled/context-matched controls — never for using more modalities.
- No identity or coupling verdict is emitted from synthetic fixtures.
- Low-quality sessions are excluded **with a recorded reason**, not silently dropped.
- BCVF / USE / SCC / phase are not privileged; the second-order BCVF term is excluded
  from primary detection (see `IMPLEMENTATION_FINDINGS.md`).

## Status

A functioning collection + analysis pipeline. On synthetic fixtures it reaches
`INSTRUMENTATION_READY` and measures a marginal separability signal, and it correctly
**refuses** to convert that into a biometric verdict. **No real participant data has
been collected.** Whether stable, user-specific behavioral signals exist is
**untested** and awaits a real-data pilot run through this same harness.
