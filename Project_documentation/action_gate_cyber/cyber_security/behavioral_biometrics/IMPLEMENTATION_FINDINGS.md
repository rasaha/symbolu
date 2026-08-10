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

## F9 — real browser collector added (`collector_app/`)
The transport-agnostic collector is now bound to a real, local, cloud-free **browser**
application (`collector_app/`): a stdlib `http.server` (127.0.0.1 only) serves a
single-page app that captures in-page keyboard/pointer/context events (page-scoped
listeners — **no global keylogger**) and POSTs them at completion. A browser→schema
adapter (`adapter.py`) maps events into the FROZEN schema (no second format), validates
each, and **quarantines** malformed ones. The raw character (`event.key`) is used in
the browser only to derive the privacy-safe key class/id and is never stored or sent;
the adapter additionally quarantines any event that carries a raw-content field.

## F9a — real browser E2E via raw CDP (no playwright)
Python `playwright` is not installed, but Node 22 (with a global `WebSocket`) and a
Chromium binary are present. Rather than skip browser testing, `tests/browser_e2e.js`
drives headless Chromium over the Chrome DevTools Protocol directly, dispatching REAL
keyboard and pointer events into the actual page and asserting privacy-safe capture
(no raw content) plus local storage. `test_browser_e2e.py` runs it and SKIPS cleanly if
node/Chromium are absent, in which case the adapter/server layers plus the manual
`ACCEPTANCE_CHECKLIST.md` provide coverage.

## F9b — data_origin lock (REAL_PARTICIPANT / SYNTHETIC_TEST_ONLY / DEMO_ONLY)
A stricter `data_origin` field was added to the schema (alongside `data_provenance`).
`verdicts.session_is_real` treats only `REAL_PARTICIPANT` as real; SYNTHETIC and DEMO
are both non-real and can never yield a positive identity/coupling verdict. Ambiguity
resolved: `features.extract` now carries `data_origin` into the feature record so the
lock survives feature extraction (a DEMO record was briefly misclassified as
real-but-insufficient before this fix). The collector-app readiness verdict
(`REAL_COLLECTOR_READY_FOR_PILOT` / `_DEGRADED` / `_NOT_READY`) concerns only the
collection application, not biometric validity.

## F9c — key-class parity across two runtimes
The key→class mapping necessarily exists twice (Python `privacy.key_to_class` for the
adapter/analysis, `static/keyclass.js` for the browser). `test_keyclass_parity.py`
executes the JS in node over a shared key set and asserts byte-for-byte parity, so the
two implementations cannot silently diverge.

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

## F14 — study machinery (`study/`) added; every scientific claim origin-locked
The full evaluation pipeline (identity runner, USE, BCVF, fusion, confidence, temporal,
end-to-end runner, evidence export, preregistration) lives under `study/`. It runs on
`MOCK_TEST_ONLY` fixtures and emits only `*_PATH_VERIFIED` / `*_NO_SCIENTIFIC_VERDICT`.
`data_origin` was extended with `MOCK_TEST_ONLY`; `origin.guarded` wraps every
scientific classifier so non-real data can never emit a positive verdict, and
`origin.assert_not_positive_on_nonreal` is a defensive tripwire (tested).

## F14a — pure classifiers vs guarded verdicts
Each machinery has a PURE classifier (`classify_use/bcvf/fusion/confidence`) over
measured numbers and a GUARDED wrapper that applies the origin lock. Branches that a
well-behaved model does not cleanly produce from a stub (`BCVF_REGRESSES`,
`DEVICE_BOUND_COUPLING_ONLY`, some `*_SMALL_EFFECT`) are exercised by unit tests over
FABRICATED numbers — testing the decision function, not manufacturing a data verdict.

## F14b — capacity-matched BCVF contrast
The BCVF fair contrast is capacity-matched: the no-disagreement arm gets a matched
random noise feature so both arms have equal parameter count and the ONLY difference is
the explicit normalized disagreement `q`. This prevents crediting BCVF for extra
capacity. Eligibility requires two structurally-distinct estimators each showing
held-out signal; a fast/slow same-stream pair is refused.

## F14c — coupling never credited for extra modalities
The `MM_SHUFFLED` arm carries the same coupling slots with decorrelated values, so any
gain from extra feature slots alone appears equally in the shuffled control and is not
credited. USE is supported only when context-conditioned coupling beats BOTH the fair
marginal baseline and the shuffled control.

## F14d — confidence needs held-out evaluation; calibration split isolation
Calibration is fit on a chronological calibration split and evaluated on an untouched
test split. The verdict uses the best ACHIEVABLE held-out ECE (min of raw vs calibrated)
so an already-calibrated model is not penalized by a distorting calibrator, while
genuine held-out miscalibration (drift) is still caught. Isotonic uses a clean
block-based pool-adjacent-violators (an earlier naive PAV overflowed — fixed).

## F14e — estimator-uncertainty proxy in the end-to-end runner
When deriving BCVF/fusion estimators from the identity arms in `runner.py`, per-estimate
σ is a documented proxy (constant) and z-scores are standardized descriptively. This is
adequate for path verification; the dedicated BCVF fixtures carry explicit σ for the
real-contrast tests. Recorded as an ambiguity for the real-data phase.

## F14f — temporal machinery is diagnostic-only
The takeover/temporal runner reuses the frozen LLT-Kalman+CUSUM observer and emits only
diagnostics (TTD, false-challenges/hour, change-point timing) with no security claim.
Composite arms (quality-aware multimodal, fusion+USE, fusion+BCVF, confidence-gated) are
wired as later-ready arms that currently reduce to the single-stream detector on a
single mock stream, clearly flagged `later_ready_stub`.

## F13 — what remains untested
Whether **stable, user-specific behavioral signals exist** is untested — that is the
purpose of a *later* real-data run through this harness. No real participant data has
been collected. The synthetic marginal separability (AUC ≈ 0.8) is a property of the
test oscillator, not a biometric result, and the verdict layer refuses to report it as
one.
