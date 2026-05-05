# Replay / record-and-replay framework — design

The §9-row-#3 industry-features-roadmap pick. When a fielded
vehicle has an incident, the recall investigator needs
**bit-identical replay** of what the kernel saw and did. That's
the contract this framework ships.

The doc follows the same maturation pattern as
`SAFETY_STATE_MACHINE_DESIGN.md` and `ROS2_DDS_SBOM_DESIGN.md`:
design first, implementation second, ship-when-ready criteria
explicit. The design is small — the runtime already has nearly
all the pieces — but the contract layer is load-bearing.

## §1 Why this exists

The current capability:

* `TrustShapedEpisodeRecord` captures per-tick **output** state
  (weights, BCVF cost, exclusion bits, V2 state, deadband
  activations). ✓
* `EpisodeDiagnostics` captures the realised predictor
  trajectories + applied controls per episode. ✓
* `RunConfig` carries the full configuration needed to re-run
  an episode (kernel config, planner config, scenario, RNG
  seed, predictor failure injection). ✓
* `BasePredictor` is RNG-seeded; identical seed + identical
  control sequence ⇒ identical trajectory (deterministic
  replay property baked in). ✓
* `MPPIPlanner.set_seed()` captures the planner's RNG. ✓

What's missing:

* **A bundle artifact** that ties `(config, seed, recorded
  output)` together as a single named, JSON-serialisable
  artifact a recall investigator opens. ✗
* **A reconstructor** that takes the bundle, re-runs the
  episode against the current code, and compares the
  re-produced output to the recorded output bit-exact. ✗
* **A validation result** that names *what* diverged when the
  re-run doesn't match (which tick, which field) so an
  investigator can localise the kernel diff that broke the
  bit-identity. ✗

This is what closes a recall investigation. Without it, the
investigator has only the output state and must guess at the
inputs; with it, the investigator can run the bundle through
the current code and either confirm "the lab reproduces what
the field saw" (clean replay) or surface "the lab now
produces Y where the field saw X" (kernel diverged — point at
the commit that introduced the divergence).

The discipline also pays off without an incident: every
characterization-grid cell can ship as a replay bundle, so a
new contributor can replay the bundle and confirm the
property the cell pins still holds.

## §2 The bundle contract

A `ReplayBundle` is a single, JSON-serialisable artifact
containing:

| Field | Type | Why |
|---|---|---|
| `bundle_version` | str | Schema version of the bundle format itself. Bumps when the on-disk shape changes. |
| `package_version` | str | `bcvf_autonomous.__version__` at record time. Replay surfaces a version mismatch loudly. |
| `recorded_at` | str (ISO 8601) | When the original episode ran. |
| `episode_id` | str | Caller-provided identifier — typically vehicle ID + trip ID + timestamp. |
| `run_config` | dict | Full `RunConfig` serialised — scenario, kernel config, planner config, seed, failure injection, every knob the runner consumes. |
| `recorded_record` | dict | The original `TrustShapedEpisodeRecord.to_dict()` output — what the field saw. |
| `recorded_collision` | bool | The original episode's collision flag. |
| `recorded_total_steps` | int | The original episode's tick count. |
| `metadata` | dict | Free-form caller annotations (vehicle ID, fleet, deployment partner, scenario classification, recall-case ID). Not interpreted by the framework. |

The bundle is intentionally NOT a binary blob. CycloneDX-style
discipline: a recall investigator opens the JSON, reads the
config, and understands what's there. The TrustShapedEpisodeRecord
inside is the same structured per-tick record `aggregate_fleet`
already consumes, so existing tooling (FleetSummary,
StreamingFleetMonitor) accepts the bundle's recorded record
without modification.

## §3 Capture path

A `ReplayBundle` is produced two ways:

1. **End-of-episode capture by the runner.** When
   `RunConfig.replay_capture_path` is set, the runner writes
   the bundle to that path at episode end alongside the
   existing `trust_diagnostics_path`. The bundle wraps the
   in-memory `TrustShapedEpisodeRecord` + the `RunConfig` it
   was produced from. No additional cost beyond the existing
   diagnostics-write.
2. **Post-hoc construction from a recorded record.** A
   `build_replay_bundle(run_config, recorded_record,
   episode_id, ...)` factory builds a bundle from a
   serialised episode record (a JSON file produced by an
   older runner build, an aggregate-fleet input, a deployment
   partner's recorded trip). Lets a recall investigator turn
   a pile of legacy JSONs into bundles without re-running.

Both paths produce identical bundle JSONs — the bundle format
is the canonical shipping unit.

## §4 Reconstruction

`replay_bundle(bundle, runner_factory) → ReplayResult` runs
the bundle's `run_config` against the current code and
compares the resulting `TrustShapedEpisodeRecord` to the
recorded one.

```python
@dataclass(frozen=True)
class ReplayResult:
    bundle: ReplayBundle              # the bundle that was replayed
    reconstructed_record: TrustShapedEpisodeRecord
    matches_recorded: bool            # bit-identity verdict
    per_field_divergences: Tuple[str, ...]  # named fields that differ
    per_step_divergences: Tuple[int, ...]   # tick indices that differ
    package_version_at_replay: str
```

The bit-identity check uses `np.array_equal` on every per-step
array (weights, costs, residuals, EMA, BCVF totals, exclusion
bits, V2 states, deadband counts, gate activations) plus the
scalar fields. Any mismatch lands in the divergence tuples
with field-level granularity:

* `"per_step_weights[12]"` — divergence at tick 12 in weights.
* `"per_step_v2_state"` — V2 state list disagrees somewhere.
* `"n_steps"` — episode length differs.

Determinism contract: given identical
`(RunConfig, package_version)`, replay_bundle MUST produce a
bit-identical `TrustShapedEpisodeRecord`. The deterministic
property is already baked in (every RNG is seeded, every
predictor is RNG-deterministic, the kernel is fp64-stable);
the framework just exercises it as a contract.

## §5 What divergence means

A bit-identity mismatch is a **signal**, not a failure. Three
classes:

* **Class A (kernel diverged):** the same `RunConfig` produces
  different output. The investigator points at the kernel diff
  introduced between record-time `package_version` and
  replay-time. Either (a) the change was a deliberate behaviour
  fix and the divergence is expected (the bundle's recorded
  output is now obsolete), or (b) the change was a regression
  and the divergence is the bug. The framework doesn't
  classify; it surfaces the divergence loud.
* **Class B (config drift):** the `RunConfig` itself was
  changed in a non-load-bearing way (e.g. a default added
  with backward-compat). Replay reconstructs the config and
  the divergence is structural. Tests pin the bundle JSON
  shape so this fails CI loudly until the bundle format is
  bumped.
* **Class C (host non-determinism):** the platform changed in
  a way the runtime didn't anticipate (numpy version bump
  changed a bit, BLAS rounding-mode flipped). Acknowledged as
  out-of-scope for this surface; documented in §8 as a
  *what this is NOT*.

For all three, the value is the same: the divergence is
visible. The investigator decides what to do about it.

## §6 Strict round-trip discipline

The bundle JSON I/O follows the same strict-validation pattern
as `analysis/io.py:episode_record_from_dict` — corrupt
artifacts fail loudly at load time rather than silently
producing zero-fill records:

* Required keys must be present; a missing field raises
  `ReplayBundleError` at load time, naming the missing key.
* `package_version` must parse as semver; a non-semver value
  raises.
* `recorded_record` must validate via the existing
  `episode_record_from_dict` (so the bundle can't smuggle a
  malformed record past the validator).
* `bundle_version` must match the on-disk schema version the
  loader supports; a future schema bump is rejected with a
  loader-version error.

The strictness is the safety case: a recall investigator
opening a tampered or corrupted bundle gets a loud error, not
a silently-wrong replay.

## §7 Composition with existing surfaces

* **`TrustShapedEpisodeRecord` (existing).** The bundle's
  `recorded_record` field IS this dataclass's `to_dict()`
  output. No changes to the record format.
* **`Runner` + `RunConfig` (existing).** The runner writes
  bundles when `RunConfig.replay_capture_path` is set; the
  reconstructor re-instantiates a `Runner` from the bundle's
  config. No changes to the runner's main loop.
* **`SafetyStateMachine` (post-v0.7).** The state machine
  reads `TrustShapedEpisodeRecord` directly; replay
  reconstructions feed naturally into it. A bundle replayed
  through the state machine reproduces the same state-graph
  walk recorded at incident time.
* **`StreamingFleetMonitor` (existing).** A bundle's recorded
  record is the same `TrustShapedEpisodeRecord` the streaming
  monitor already accepts via `observe_episode`. A fleet of
  bundles is a fleet of records — same surface.
* **SOTIF traceability matrix (existing).** SOTIF clause 10
  (operational design + field monitoring) gains the replay
  bundle as the post-incident-recall evidence artifact.
  ISO 26262 Part 6 §11 (verification of software safety
  requirements) gains the replay bit-identity contract as the
  V&V evidence the recall investigator argues against.

## §8 What this is NOT

* **Not a recording protocol.** The bundle is the artifact;
  capturing it requires the runner to be configured to write
  it. The framework doesn't override or replace the deployment
  partner's existing trip-recording infrastructure.
* **Not a binary trace format.** It's JSON. Inspectable by
  hand, by jq, by every CI pipeline. CycloneDX-class
  discipline.
* **Not a compression scheme.** The bundle is a few hundred KB
  to a few MB depending on episode length. Production
  deployments that need higher density write only on
  exceptional events (collision, hard-disengagement,
  near-veto) and ship the bundles to a central recall vault.
  The framework doesn't impose a compression layer.
* **Not a kernel-input capture.** The bundle captures the
  config + recorded output, not the per-tick `(K, M, H, 3)`
  rollout tensor the planner sampled. Bit-identity comes from
  RNG-seeded determinism, not from input replay. A bundle
  whose `RunConfig` produces a different kernel input under
  the current code (because a predictor implementation
  changed) surfaces as a Class-A divergence — visible loud.
* **Not a substitute for the deployment partner's recall
  process.** The OEM's recall investigation includes
  hardware-in-the-loop, sensor-data replay, vehicle-level
  reconstruction. The replay bundle is one evidence artifact
  the OEM's investigator opens; it doesn't replace the rest.
* **Not host-non-determinism robust.** A numpy version bump
  that flips a bit in a fp64 op manifests as a Class-C
  divergence. Out of scope for this surface; documented in §5.

## §9 Ship-when-ready criteria for STABLE_API graduation

The replay framework ships in `PROVISIONAL_API`. Promotion
requires:

1. **One deployment partner uses the bundle as the primary
   recall-investigation artifact for one quarter** without
   filing a bundle-format change request. The bundle JSON
   shape is the integration contract — three months of live
   investigator use is the empirical filter.
2. **One bit-identity replay across a real recall case.** A
   field incident's recorded bundle replays bit-identically
   under the same `package_version` it was recorded under. The
   framework already pins this for synthetic episodes; the
   field gate is recall-bundle-replays-bit-identical-on-the-
   commit-it-was-recorded-under.
3. **One Class-A divergence detection across a real kernel
   change.** A landed kernel commit causes a known
   field-recorded bundle to diverge; the per-field /
   per-step divergence tuples correctly localise the
   divergence to the changed code. Functions as the negative
   control — proves the framework actually surfaces bugs, not
   just clean cases.
4. **Bundle format gains a `signed_at` integrity field**
   verified against a deployment partner's signing key. The
   §6 strict-validation discipline doesn't currently pin
   tamper-detection; promotion to STABLE includes the signing
   layer.
5. **External auditor signs off the bundle JSON shape.** The
   shape is the load-bearing artifact a recall court of law
   reads against; an OEM's auditor or TÜV-equivalent reviewer
   confirms the format clears their evidentiary bar.

Until all five land, the symbols stay in `PROVISIONAL_API`.

## §10 API sketch (no implementation in this doc)

```python
# replay/bundle.py

@dataclass(frozen=True)
class ReplayBundle:
    bundle_version: str             # "1.0"
    package_version: str            # bcvf_autonomous.__version__
    recorded_at: str                # ISO 8601
    episode_id: str
    run_config: Dict[str, Any]      # serialised RunConfig
    recorded_record: Dict[str, Any]  # TrustShapedEpisodeRecord.to_dict()
    recorded_collision: bool
    recorded_total_steps: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]: ...

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ReplayBundle": ...


# replay/io.py

def save_replay_bundle(
    bundle: ReplayBundle, path: Union[str, Path]
) -> None: ...

def load_replay_bundle(path: Union[str, Path]) -> ReplayBundle: ...


# replay/reconstructor.py

@dataclass(frozen=True)
class ReplayResult:
    bundle: ReplayBundle
    reconstructed_record: TrustShapedEpisodeRecord
    matches_recorded: bool
    per_field_divergences: Tuple[str, ...]
    per_step_divergences: Tuple[int, ...]
    package_version_at_replay: str

def replay_bundle(
    bundle: ReplayBundle,
    runner_factory: Callable[[Dict[str, Any]], TrustShapedEpisodeRecord],
) -> ReplayResult: ...

def build_replay_bundle(
    run_config: Any,
    recorded_record: TrustShapedEpisodeRecord,
    *,
    episode_id: str,
    metadata: Optional[Dict[str, Any]] = None,
    recorded_collision: bool = False,
    recorded_total_steps: Optional[int] = None,
) -> ReplayBundle: ...


# replay/errors.py

class ReplayBundleError(Exception): ...
class ReplayBundleVersionError(ReplayBundleError): ...
```

The implementation lands paired with this doc. This section
captures the surface a future refactor must preserve.
