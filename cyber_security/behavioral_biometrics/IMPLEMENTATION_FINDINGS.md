# Implementation Findings

Decisions, ambiguities, and honest limitations from building the instrumentation
pilot. This is not an architecture roadmap.

## F1 — numpy-only numerics (no scipy/sklearn)
The environment has numpy but not scipy/sklearn. All estimators are implemented in
`numerics.py`: Mahalanobis/Gaussian prototype, logistic regression (batch GD),
nearest-centroid, CCA (via SVD of whitened cross-covariance), AUC (Mann–Whitney),
TPR@FAR, Cohen's d, and percentile/paired bootstrap. Deterministic; no external solver.

## F2 — jitter is measured as linear-fit residuals, not raw inter-sample MAD
Raw inter-arrival MAD **caps at ~half the sample interval** once jitter exceeds the
spacing, because sorting timestamps removes crossings. Sampling jitter is therefore
measured as the MAD of residuals from a linear fit of timestamp vs sample index on the
periodically-sampled streams (pointer move, motion). Event-driven keyboard is excluded
(its inter-event spacing is irregular by design). This scales monotonically with true
jitter (verified in `test_quality.py`).

## F3 — quantization = timer resolution, not sample rate
"Timestamp quantization" is the finest distinct timestamp step across events (the
effective timer grid), so a coarse tick (e.g. 15.6 ms) is caught independent of a
stream's sample rate. A regular 50–125 Hz stream is not falsely flagged.

## F4 — one coherent decorrelation transform drives all coupling controls
Every coupling statistic (max |lagged xcorr|, zero-lag xcorr, event-correlogram peak,
windowed CCA) is computed in three matched variants — `real`, `shuf` (cross-modal
timing decorrelated, marginals preserved), `ctxm` (decorrelated within task-stage) —
seeded deterministically from the session id. `coupling.coupling_view(arm)` maps each
variant into a common feature slot so the identity model sees matched features across
arms. This is what makes "coupling beats its controls" a fair contrast rather than a
capacity/more-modalities artifact.

## F5 — coupling-beyond-marginals is hard to isolate (an honest negative)
On the synthetic generator, user-specific cross-modal coupling is strongly detectable
at the **feature** level (real xcorr ≫ shuffled), but it adds little **identity**
information beyond the marginal baseline, because user-specific coupling also perturbs
the marginal pointer-speed distribution — so marginals already capture much of it. The
harness correctly returns near-zero coupling gain and refuses to credit coupling for
merely existing. This matches the domain prior ("plausibly small") in
`../USE_CONTRIBUTION_MAP.md`. Consequently the `USER_SPECIFIC_COUPLING_SUPPORTED` path
is exercised by **pure-classifier unit tests over fabricated measured numbers**
(`test_verdicts.py`), which is legitimate (testing the decision function, not emitting
a data verdict) and avoids manufacturing a positive from synthetic data.

## F6 — synthetic guard; instrumentation allowed on synthetic
No identity or coupling verdict is emitted when any input session is
`SYNTHETIC_TEST_ONLY` (`*_SYNTHETIC_NO_VERDICT`). Instrumentation verdicts **are**
allowed on synthetic data, since they concern the instrument, not identity — this is
what lets the pilot validate timing quality end-to-end without a biometric claim.

## F7 — device gate "not assessed" without a second device
The device-instance confound (analysis E) needs same-participant second-device
sessions. When absent, the coupling verdict carries `device_gate_not_assessed` and the
classifier does not label the result device-bound (it also cannot grant a fully clean
`SUPPORTED` without the gate). A real pilot that wants a positive coupling verdict must
collect the (exploratory) second-device condition.

## F8 — at-rest encryption is stdlib-only, not audited
No AES/libsodium is available. `storage.py` provides a PBKDF2-HMAC-SHA256 +
SHA-256-CTR + HMAC stream cipher: real integrity + confidentiality against casual
inspection, but **not an audited AEAD**. Documented in `PRIVACY_AND_ETHICS.md`; pair
with full-disk encryption for real use. File deletion is best-effort overwrite (no
guarantee on wear-leveled/CoW media).

## F9 — no OS input-hook adapter (out of scope)
The collector is transport-agnostic (`ingest`), exercised here by the task runner and
synthetic driver. A real OS/browser input hook (keylogger-class code) is intentionally
not implemented in this phase; the binding point and privacy contract are documented in
`DATA_COLLECTION_PROTOCOL.md`.

## F10 — BCVF / USE / SCC / phase are not privileged
Coupling features are ordinary candidates, not a favored mechanism. Phase-based
features are gated to continuous motion signals (where instantaneous phase is
meaningful) and given no special weight; spectral coherence is computed only when
motion exists. The second-order BCVF term is excluded from primary detection,
consistent with `../BCVF_CONCEPT_DIRECTION.md` (refuted as a primary detector). The
temporal baseline is a standard local-linear-trend Kalman + CUSUM, exposed but not
elevated.

## F11 — ambiguity: "usable windows per session"
The pilot analyzes at **session** granularity (one feature record per session). The
minimum "usable windows per session" is checked structurally, and windowed CCA is used
inside coupling, but a fully **window-level** split (with window-disjointness and
window-level leakage checks) is noted as the next step for a continuous-auth study —
the leakage checker currently guarantees **session**-disjointness.

## F12 — determinism & leakage discipline
Every random draw is seeded (cohort seed, per-session control seeds derived from the
session id, bootstrap seeds from the master seed). The standardizer and every model
parameter are fit on the split's enroll (train) records only, then applied to test;
`test_splits.py` asserts the fitted mean equals the train mean. Identifiers never enter
the vectorized feature space (`test_features.py`, `test_adversarial_fixtures.py`).

## F13 — what remains untested
Whether **stable, user-specific behavioral signals exist** is untested — that is the
purpose of a *later* real-data run through this harness. No real participant data has
been collected. The synthetic marginal separability (AUC ≈ 0.8) is a property of the
test oscillator, not a biometric result, and the verdict layer refuses to report it as
one.
