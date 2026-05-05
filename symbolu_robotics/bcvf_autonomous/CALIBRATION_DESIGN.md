# Calibration parameter management + drift detection — design

The §9-row-#6 industry-features-roadmap pick. *"Required for any
fleet > 10 vehicles."* Every production deployment needs
versioned, signed calibration bundles + a drift-detection
surface that fires when a fleet vehicle's live behaviour drifts
from the deployed bundle.

The doc follows the maturation pattern from the prior four
landings (state machine, ROS 2 / DDS / SBOM, replay,
real-time budget): design first, implementation second,
ship-when-ready criteria explicit.

## §1 Why this exists

The runtime today carries ~9 typed configuration dataclasses
spread across the kernel (`BCVFConfig`), planner (`MPPIConfig`),
trust shaper (`ConsumerV2Config`), predictors (`BicycleConfig`,
`FailureConfig`), real-time budget (`RealTimeBudget`), DDS
(`DDSQoSProfile`), safety state machine
(`SafetyStateMachineConfig`), and ROS 2 node
(`BCVFNodeConfig`). A deployment partner picks values for each
based on their hardware + scenario + tier requirements. The
problem the roadmap §6 identifies:

* **No bundling.** A "calibration" today is a tuple of nine
  separate dataclasses constructed at runtime. There's no
  artifact a deployment partner ships, signs, version-controls,
  or hands to a recall investigator. ✗
* **No identity / hash.** Two vehicles running "the same
  config" have no machine-checkable proof. A field engineer's
  copy-paste mistake is invisible until a divergence symptom
  surfaces. ✗
* **No kernel-version binding.** A calibration tuned against
  kernel v0.4.0 can silently load against v0.5.0 even if the
  kernel's gate-noise interaction changed. Drift = the
  calibration is now mis-tuned, but nothing surfaces it. ✗
* **No drift-detection surface.** The fleet monitor reports
  argmax-flip rates + near-veto rates + V2 engagement
  fractions, but there's no calibrated *expected* range for
  those metrics. Every deployment partner re-derives the alert
  thresholds from their own data. ✗

This is what closes the *"can we deploy this to a fleet of 10+
vehicles without re-tuning per vehicle?"* conversation. Without
it, deployment scales linearly with engineering effort; with
it, the bundle is the deployment unit and the drift detector
is the operational surface.

## §2 The CalibrationSet bundle contract

A `CalibrationSet` is a frozen, JSON-serialisable, hash-identified
artifact bundling the per-deployment tuning knobs:

| Field | Type | Source |
|---|---|---|
| `calibration_id` | str | Caller-provided unique identifier (e.g. `"oem-X-fleet-A-v2"`). |
| `kernel_version` | str | The `bcvf_autonomous.__version__` the calibration was tuned against. Validated on load. |
| `created_at` | str (ISO 8601) | When the calibration was minted. |
| `bcvf_config` | dict | Serialised `BCVFConfig` (kernel knobs). |
| `mppi_config` | dict | Serialised `MPPIConfig` (planner knobs). |
| `consumer_v2_config` | dict | Serialised `ConsumerV2Config` (V2 hysteresis). |
| `bicycle_config` | dict | Serialised `BicycleConfig` (vehicle dynamics). |
| `realtime_budget` | dict | Serialised `RealTimeBudget` (latency budget). |
| `dds_qos_profile` | dict | Serialised `DDSQoSProfile` (DDS quad). |
| `safety_state_config` | dict | Serialised `SafetyStateMachineConfig`. |
| `per_predictor_failure_thresholds` | dict[str, dict] | Per-predictor failure-injection knobs. Keyed by predictor name. |
| `expected_metrics` | dict[str, dict] | Tuned expected ranges for fleet-monitor metrics — `{"argmax_flips_per_step.p95": {"min": 0.0, "max": 0.05}, ...}`. The drift detector compares live fleet aggregates against these. |
| `metadata` | dict | Free-form caller annotations (deployment partner, fleet ID, vehicle class). Not interpreted by the framework. |
| `digest` | str | Computed SHA-256 over the canonical JSON serialisation of the rest of the bundle. The signed-by-deployment-partner integrity field gates lands at STABLE_API graduation (§8 criterion #4). |

The bundle is deliberately a JSON artifact, not a binary blob —
same discipline as the SBOM and replay bundle. A field engineer
opens the JSON, reads the values, understands what's deployed.

## §3 Versioning + identity

Two integrity discipline pieces:

**Identity** is the SHA-256 digest over the bundle's canonical
JSON (sorted keys, fixed serialisation). Two bundles with the
same content produce the same digest; the digest IS the bundle's
identity. A fleet vehicle reports its `calibration_id +
digest`; an operator running the audit verifies the digest
matches what was distributed.

**Versioning** is the `kernel_version` field. On load,
`load_calibration_set()` compares the bundle's `kernel_version`
against `bcvf_autonomous.__version__`. Mismatch is a
`CalibrationVersionError` — a calibration tuned against an
older kernel may not fit the current code's behaviour. The
caller can override with an explicit
`allow_version_drift=True` flag at load time when they've
verified the kernel changes don't affect their tuning.

The discipline matches how SBOM + replay bundle handle the
same problem: bundle.package_version is recorded; load
surfaces drift loud; caller decides whether to override.

## §4 Drift detection

`CalibrationDriftDetector` compares live fleet aggregates
against the bundle's `expected_metrics` and emits one or more
typed `CalibrationDriftAlert` records when ranges are violated.

```python
detector = CalibrationDriftDetector(calibration_set)
alerts = detector.evaluate(windowed_fleet_summary)
for alert in alerts:
    log.warning(
        "%s out of expected range [%s, %s], observed %s",
        alert.metric, alert.expected_min, alert.expected_max,
        alert.observed_value,
    )
```

Each `CalibrationDriftAlert` carries:

| Field | Why |
|---|---|
| `metric` | Dotted-path name into the fleet summary (same as `AlertRule.metric`). |
| `observed_value` | What the fleet summary reported. |
| `expected_min` / `expected_max` | The calibrated range from the bundle. |
| `direction` | `"above"` / `"below"` — which boundary was crossed. |
| `calibration_id` | The bundle the comparison was made against. |
| `n_episodes_in_window` | Sample-size context. |

The detector is intentionally **not** integrated into
`StreamingFleetMonitor` by default — the monitor stays
calibration-agnostic + the deployment partner wires the
detector in via their alerting pipeline. Composition pattern:

```python
windowed = monitor.summary(window=timedelta(hours=24))
calibration_alerts = detector.evaluate(windowed)
threshold_alerts = monitor.evaluate_alerts(rules, window=...)
all_alerts = list(threshold_alerts) + list(calibration_alerts)
```

The monitor's existing `AlertRule` surface remains the right
tool for ad-hoc thresholds the deployment partner adds at
runtime; the calibration detector covers the *expected ranges
the bundle was tuned against*. They compose, not subsume.

## §5 Strict round-trip discipline

Bundle JSON I/O follows the same strict-validation pattern
established by `analysis/io.py`, `safety_case/sbom/`, and
`replay/`:

* Required keys must be present at load; missing field raises
  `CalibrationSetError` naming the missing key.
* `calibration_id` + `kernel_version` non-empty after stripping
  whitespace.
* `created_at` parses as ISO 8601 — same `datetime.fromisoformat`
  gate the replay framework uses.
* `digest` recomputed at load time against the canonical
  serialisation; mismatch raises `CalibrationDigestError`. A
  tampered or corrupted bundle fails loud, not silently
  reconstructs.
* Embedded config dicts are validated by re-instantiating the
  source dataclass (e.g. `BCVFConfig(**bcvf_config)` raises
  if a knob is missing or invalid). The bundle can't smuggle a
  malformed config past the gate.

The strict discipline is the safety case: a deployment partner
opening a bundle gets a loud error on corruption / tampering /
version drift, not a silently-wrong runtime configuration.

## §6 Composition with existing surfaces

* **All 9 typed configs (existing).** The bundle holds each as
  a serialised dict; the load path re-instantiates the source
  dataclass. No changes to any config.
* **`StreamingFleetMonitor` + `AlertRule` (existing).** The
  drift detector consumes `WindowedFleetSummary` (the
  monitor's aggregation surface) and emits typed
  `CalibrationDriftAlert` records. Composition is at the
  caller's layer; the monitor stays calibration-agnostic.
* **`SafetyStateMachine` (post-v0.7).** A calibration drift
  alert is a deployment-partner signal; the integrator decides
  whether to feed it into the state machine's
  `consec_suspect`-equivalent path. The framework doesn't
  impose the routing.
* **`ReplayBundle` (post-v0.7.x).** A replay bundle's
  `run_config` can carry the `CalibrationSet` it ran against;
  replay verifies bit-identity AND can re-validate that the
  same calibration would still fire the same drift alerts.
  Class-A divergence (kernel diverged) and calibration drift
  are orthogonal but stack — both surface loud through their
  respective comparators.
* **CycloneDX SBOM (post-v0.7.x).** The CalibrationSet is the
  configuration-management sibling of the SBOM. Both ship as
  versioned JSON artifacts a procurement gate consumes; SOTIF
  clause 12 (release-to-market + configuration management)
  gains the CalibrationSet as a sibling evidence artifact.
* **`bcvf_autonomous.__version__`.** The kernel version the
  bundle was tuned against. Surface mismatch loud at load
  time; caller overrides with explicit flag when they've
  verified the kernel changes don't affect their tuning.

## §7 What this is NOT

* **Not a runtime config loader.** A `Runner(config=...)` keeps
  taking a `RunConfig`. The calibration bundle is the
  *deployment artifact* the operator distributes; an
  integrator may extract a `RunConfig` from a CalibrationSet
  via a helper, but the framework doesn't impose the
  conversion.
* **Not a signing implementation.** The `digest` field is
  SHA-256 over canonical JSON; a real deployment-partner
  signing layer (cryptographic signing of the digest with the
  partner's key) is out of scope. Documented as a STABLE_API
  graduation gate (§8 criterion #4).
* **Not a fleet-management dashboard.** The drift detector
  emits typed alerts; the deployment partner's operations
  team wires them into their alerting pipeline. We don't ship
  Grafana boards or pager rotations.
* **Not a substitute for the deployment partner's
  configuration-management process.** Their CM is the
  load-bearing process; the bundle is one artifact in it.
* **Not a replacement for `RunConfig`.** Some bundle fields
  (failure injection, scenario overrides) live on `RunConfig`
  for backward compatibility; the bundle adds the deployment-
  unit-level discipline on top.

## §8 Ship-when-ready criteria for STABLE_API graduation

The calibration framework ships in `PROVISIONAL_API`. Promotion
requires:

1. **One deployment partner runs the bundle as the primary
   calibration artifact for a fleet of ≥ 10 vehicles for one
   quarter** without filing a bundle-format change request.
   The roadmap §6 frames this as the "fleet > 10 vehicles"
   gate; live deployment at that scale is the empirical
   filter.
2. **One real fleet drift detection** — a known calibration-
   mismatch incident is correctly localised by the drift
   detector against a recorded fleet summary. Negative
   control proving the detector surfaces real drift, not just
   synthetic test cases.
3. **Bundle format gains a `signature` field** verified
   against a deployment partner's signing key (cryptographic,
   not the SHA-256 digest). The §5 strict-validation
   discipline doesn't currently pin tamper-detection beyond
   digest integrity.
4. **External auditor signs off the bundle JSON shape** as
   admissible evidence in an ISO 26262 §12 configuration-
   management report. Out-of-sandbox manual gate.
5. **The drift detector's `expected_metrics` schema is
   stabilised** against ≥ 3 deployment partners' real
   tuning-range distributions. The schema in v0.7.x is
   straightforward (per-metric min/max); STABLE_API graduation
   confirms that's sufficient or extends to per-tier (per-
   scenario, per-fleet-segment) ranges.

Until all five land, the symbols stay in `PROVISIONAL_API`.

## §9 API sketch (no implementation in this doc)

```python
# calibration/bundle.py

@dataclass(frozen=True)
class CalibrationSet:
    calibration_id: str
    kernel_version: str
    created_at: str
    bcvf_config: Dict[str, Any]
    mppi_config: Dict[str, Any]
    consumer_v2_config: Dict[str, Any]
    bicycle_config: Dict[str, Any]
    realtime_budget: Dict[str, Any]
    dds_qos_profile: Dict[str, Any]
    safety_state_config: Dict[str, Any]
    per_predictor_failure_thresholds: Dict[str, Dict[str, Any]]
    expected_metrics: Dict[str, Dict[str, float]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    digest: str = ""

    def to_dict(self) -> Dict[str, Any]: ...

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CalibrationSet": ...

    @property
    def matches_running_kernel(self) -> bool: ...


def build_calibration_set(
    *,
    calibration_id: str,
    bcvf_config: BCVFConfig,
    mppi_config: MPPIConfig,
    consumer_v2_config: ConsumerV2Config,
    bicycle_config: BicycleConfig,
    realtime_budget: RealTimeBudget,
    dds_qos_profile: DDSQoSProfile,
    safety_state_config: SafetyStateMachineConfig,
    per_predictor_failure_thresholds: Optional[Dict[str, FailureConfig]] = None,
    expected_metrics: Optional[Dict[str, Dict[str, float]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    kernel_version: Optional[str] = None,
    created_at: Optional[str] = None,
) -> CalibrationSet: ...


# calibration/io.py

def save_calibration_set(
    calibration: CalibrationSet, path: Union[str, Path],
) -> None: ...

def load_calibration_set(
    path: Union[str, Path],
    *,
    allow_version_drift: bool = False,
) -> CalibrationSet: ...


# calibration/drift.py

@dataclass(frozen=True)
class CalibrationDriftAlert:
    metric: str
    observed_value: float
    expected_min: float
    expected_max: float
    direction: str   # "above" | "below"
    calibration_id: str
    n_episodes_in_window: int


class CalibrationDriftDetector:
    def __init__(self, calibration: CalibrationSet) -> None: ...

    def evaluate(
        self, windowed_fleet_summary: WindowedFleetSummary,
    ) -> Tuple[CalibrationDriftAlert, ...]: ...


# calibration/errors.py

class CalibrationSetError(Exception): ...
class CalibrationVersionError(CalibrationSetError): ...
class CalibrationDigestError(CalibrationSetError): ...
```

The implementation lands paired with this doc. This section
captures the surface a future refactor must preserve.
