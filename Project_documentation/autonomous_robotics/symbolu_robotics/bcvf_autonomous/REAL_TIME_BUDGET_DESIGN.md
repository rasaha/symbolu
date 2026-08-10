# Real-time / no-allocation hot path + p999 budget — design

The §9-row-#4 industry-features-roadmap pick. AUTOSAR Adaptive
integration's first technical objection is *"what's your worst-
case execution time, and what happens when you blow it?"*. This
doc specifies the contract layer that answers that question.

The doc follows the maturation pattern from the prior three
design-doc landings (state machine, ROS 2 / DDS / SBOM, replay).
The contract is small — the existing latency benchmark
(`benchmarks/latency.py`) already measures p99; what's missing
is the typed budget surface, the p999 / p9999 percentile
reporter, the over-budget-tick audit trail, and the no-
allocation discipline.

## §1 Why this exists

The current capability:

* `runner.benchmark_planner()` measures plan-cycle latency over
  N cycles + reports `mean / p50 / p95 / p99 / max` in ms. ✓
* `EpisodeDiagnostics.solve_times_ms` carries the per-tick
  series; `RunResult.p99_solve_time_ms` is the aggregated
  p99. ✓
* `benchmarks/latency.py` runs an 18-cell M × K × H sweep and
  emits a markdown report with pass/fail against three tier
  budgets (automotive 100 ms / industrial 20 ms / drone
  10 ms). ✓
* Test suite pins `p99 < 20 ms` (K=1000, H=50) +
  `p99 < 5 ms` (K=200, H=30). ✓

What's missing for an AUTOSAR-class deployment partner:

* **A typed budget contract** — a `RealTimeBudget` dataclass
  with named knobs (target_hz, p99_budget_ms, p999_budget_ms,
  p9999_budget_ms, max_budget_ms) the integrator copies into
  their config. The current per-test hardcoded thresholds
  aren't a contract surface. ✗
* **p999 / p9999 percentile reporting** — `np.percentile(99.9)`
  + `(99.99)` need 1000+ / 10000+ samples to be meaningful.
  No existing reporter; the hardcoded `p99` cuts off at 1-in-
  100 ticks. AUTOSAR partners ask for 1-in-1000 +
  1-in-10000. ✗
* **An over-budget-tick audit trail** — when a tick blows the
  budget, the integrator needs to know *which* tick + *what*
  the latency was. Current capture is aggregated post-episode
  only. ✗
* **The no-allocation discipline** — a real-time loop can't
  allocate per tick (heap alloc → GC pause → blown deadline).
  No current code path asserts allocation count. ✗
* **Documented thread-safety contract** — currently
  undocumented. AUTOSAR partners ask. ✗

This is what closes the AUTOSAR-Adaptive integration
conversation. Without it, the partner's safety team has only
"we measured p99 in our test suite" — which is one or two
orders of magnitude short of what their certification process
expects.

## §2 The budget contract

A `RealTimeBudget` is a typed dataclass an integrator copies
into their config:

| Field | Default | Why |
|---|---|---|
| `target_hz` | 100.0 | Target tick rate. Establishes the deadline `1000 / target_hz` ms. Common values: 100 Hz (drone), 50 Hz (industrial), 10 Hz (automotive). |
| `p99_budget_ms` | 8.0 | 1-in-100 tick budget. The headroom under deadline. Default leaves 2 ms of headroom against a 10 ms deadline. |
| `p999_budget_ms` | 9.5 | 1-in-1000 tick budget. The AUTOSAR-class question. Default leaves 0.5 ms headroom. |
| `p9999_budget_ms` | 10.0 | 1-in-10000 tick budget — the deadline itself. By design, no headroom: a tick at this percentile is on the bleeding edge. |
| `max_budget_ms` | 15.0 | Absolute worst-case. A single tick that exceeds this is a hard violation. Default 1.5× deadline. |
| `min_samples_for_p999` | 1000 | Below this sample count, p999 is not reported (n=10 doesn't define a 1-in-1000 percentile). |
| `min_samples_for_p9999` | 10000 | Same discipline for p9999. |
| `over_budget_log_capacity` | 100 | Ring-buffer capacity for over-budget tick records. Prevents the audit log from growing unbounded under sustained violations. |

The defaults target a 100 Hz deployment with sensible
headroom. Every field is exposed for calibration; AUTOSAR
partners override per their tier.

## §3 Per-tick observation

A `LatencyMonitor` ingests one observation per tick:

```python
monitor = LatencyMonitor(budget=RealTimeBudget())
for tick_index in range(n_ticks):
    start = time.perf_counter()
    planner.plan()
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    monitor.observe(elapsed_ms, tick_index=tick_index)
```

The monitor:

* Appends each observation to an internal series.
* Tracks per-budget-tier violation counts (n_p99_violations,
  n_p999_violations, n_p9999_violations, n_max_violations).
* Maintains a ring buffer of `OverBudgetTick` records — each
  carrying `(tick_index, observed_ms, budget_tier_violated,
  budget_threshold_ms)` — so an investigator can find the
  worst N violations.
* Computes percentile stats lazily on `summary()` call so the
  per-tick `observe()` cost stays O(1) amortised.

The monitor is intentionally NOT integrated into the planner
hot path by default. The planner keeps its existing
`solve_time_ms` capture; the monitor wraps the planner via
the runner / a deployment-partner-supplied harness. Two
reasons:

1. **Optional cost.** Some deployments care about latency
   reporting; some don't. Mandating it in the planner forces
   the cost on everyone.
2. **Composition with multiple measurement points.** A
   deployment partner might measure planner + perception +
   localisation latencies separately; the monitor is generic
   enough to accept all three.

## §4 Percentile reporting

`monitor.summary() → BudgetSummary` returns:

```python
@dataclass(frozen=True)
class BudgetSummary:
    n_observations: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    p999_ms: Optional[float]    # None if n < min_samples_for_p999
    p9999_ms: Optional[float]   # None if n < min_samples_for_p9999
    max_ms: float
    n_p99_violations: int
    n_p999_violations: int
    n_p9999_violations: int
    n_max_violations: int
    over_budget_ticks: Tuple[OverBudgetTick, ...]
    budget: RealTimeBudget
    meets_budget: bool          # True iff all violation counts == 0
```

Percentile-availability discipline: a p999 reported on n=10
samples is statistical noise, not a contract. The summary
returns `None` when sample count is below the documented
threshold; downstream code that ignores `None` gets a clear
`TypeError` rather than a fake number. The `min_samples_for_*`
knobs are calibration: an integrator running a small
sanity-check sweep can lower them; an integrator running
a full 1M-tick load test takes the defaults.

## §5 The over-budget audit trail

`OverBudgetTick` records carry `(tick_index, observed_ms,
budget_tier, threshold_ms)`. The ring buffer keeps the most
recent `over_budget_log_capacity` violations (default 100) so
the audit trail is bounded under sustained violation.

The discipline matches the safety-state-machine's transition
log: every violation is named, timestamped (via tick index +
optional wall-clock), and bounded. A recall investigator
opening a `BudgetSummary` sees exactly which ticks violated
which tier — enabling replay (per `REPLAY_FRAMEWORK_DESIGN.md`)
of the offending tick and root-cause investigation of the
specific code path that allocated more than expected.

## §6 No-allocation discipline (advisory)

The roadmap §2 calls for a `realtime_mode=True` flag asserting
no allocation under load. This is a hard problem in pure
Python — the interpreter allocates internally (frame objects,
intermediate references) on every call regardless of user
code, so a strict "zero allocations" assertion would always
fail.

The implementation ships a **softer discipline**: the monitor
records `tracemalloc` allocation deltas per tick and reports
them in the summary. This is advisory, not contractual:

```python
@dataclass(frozen=True)
class AllocationTrace:
    n_observations: int
    mean_bytes_per_tick: float
    p99_bytes_per_tick: float
    max_bytes_per_tick: int
```

A deployment partner that needs strict no-allocation discipline
ships against the C++ port (out of scope; tracked separately).
The Python implementation surfaces the data so partners can
diagnose allocation hotspots — a per-tick allocation delta of
50 KB tells the integrator the planner is allocating more than
they expect, and points at the code change that introduced it.

The advisory-not-contractual framing is documented in §8 as
*what this is NOT*.

## §7 Composition with existing surfaces

* **`runner.benchmark_planner()` (existing).** Already
  measures plan-cycle latency. The monitor accepts the same
  per-cycle ms values; a deployment partner who already calls
  `benchmark_planner()` wraps it with `monitor.observe(...)`
  per cycle.
* **`benchmarks/latency.py` (existing).** The 18-cell sweep
  emits per-cell `p99_ms`. A new
  `benchmarks/realtime_budget.py` script extends the sweep
  with p999 / p9999 + the budget-tier pass/fail matrix.
  Mirrors the existing markdown-report format.
* **`EpisodeDiagnostics.solve_times_ms` (existing).** The
  per-tick series the monitor would replay via
  `monitor.observe_series(diagnostics.solve_times_ms)`.
* **`SafetyStateMachine` (post-v0.7).** A budget violation is
  a deployment-partner signal — typically routes to
  `safety_state_machine.observe()` via the existing
  `consec_suspect`-equivalent path on the budget-violated
  tick. Composition is at the integrator's layer; the
  framework doesn't impose it.
* **`ReplayBundle` (post-v0.7.x).** A bundle's recorded
  `RunConfig` can carry the `RealTimeBudget` it ran against;
  replay verifies the bit-identity contract AND re-validates
  the latency budget against the current code. A kernel
  commit that regressed p999 surfaces as both a Class-A
  divergence (different output) AND a budget violation
  (different latency).
* **SOTIF traceability matrix (existing).** ISO 26262 Part 6
  §10 (integration verification) gains the budget contract as
  the runtime-deadline V&V evidence. SOTIF clause 9 (V&V) gains
  the percentile reporter as the latency-evidence layer.

## §8 What this is NOT

* **Not a real-time guarantee.** The framework runs inside
  CPython with the GIL; we cannot deliver hard-real-time
  bounds. The budget surface is a measurement + audit layer,
  not a real-time scheduler. A hard-real-time deployment
  ships against the C++ port (out of scope).
* **Not a replacement for the integrator's worst-case
  execution time analysis.** AUTOSAR / ISO 26262 expects a
  formal WCET analysis (static code analysis + measurement +
  margin). The framework provides the measurement + reporting
  layer; the formal analysis is the deployment partner's
  responsibility.
* **Not a no-allocation enforcer.** `tracemalloc` deltas are
  advisory. Pure-Python "zero allocations" is not achievable
  inside CPython. The C++ port is the right surface for that
  discipline.
* **Not a thread-safety enforcer.** The monitor is single-
  writer (one ingest thread per monitor instance). Multi-
  threaded ingest must serialise externally; the framework
  doesn't impose locks (the cost would be unacceptable in the
  hot path). Documented as a contract, not a runtime check.
* **Not a substitute for end-to-end latency measurement.** The
  monitor measures the per-tick interval the caller hands it.
  End-to-end latency (sensor → actuator) is a deployment-
  partner concern — they measure across the whole pipeline,
  the monitor measures the BCVF layer slice.

## §9 Ship-when-ready criteria for STABLE_API graduation

The real-time budget surface ships in `PROVISIONAL_API`.
Promotion requires:

1. **One AUTOSAR-class deployment partner runs the budget
   contract against their AUTOSAR-Adaptive integration for
   one quarter** without filing a contract-shape change
   request. The dataclass shape + percentile-availability
   discipline are the integration contract; three months of
   live use is the empirical filter.
2. **One real load test of ≥ 10⁶ ticks** under sustained
   load with the documented `min_samples_for_p9999` of
   10000. The framework already pins p99 against synthetic
   tests; the gate is real-load p9999 measurement.
3. **One C++-port-equivalent benchmark** demonstrates the
   pure-Python implementation is within 2× of the C++ port's
   p99 for the smallest config (M=4, K=128, H=10). Establishes
   the pure-Python implementation isn't pathological vs the
   real-time-capable port.
4. **One TÜV / external auditor signs off the percentile
   reporting + the over-budget audit trail format** as
   admissible evidence in an ISO 26262 Part 6 §10 integration-
   verification report. Out-of-sandbox manual gate.
5. **The over-budget log carries a configurable persistence
   layer** (currently in-memory ring buffer; promotion
   requires file-backed log + retention policy + recall-vault
   handoff). A deployment partner needs the log to survive
   beyond a process crash.

Until all five land, the symbols stay in `PROVISIONAL_API`.

## §10 API sketch (no implementation in this doc)

```python
# realtime/budget.py

@dataclass(frozen=True)
class RealTimeBudget:
    target_hz: float = 100.0
    p99_budget_ms: float = 8.0
    p999_budget_ms: float = 9.5
    p9999_budget_ms: float = 10.0
    max_budget_ms: float = 15.0
    min_samples_for_p999: int = 1000
    min_samples_for_p9999: int = 10000
    over_budget_log_capacity: int = 100

    @property
    def deadline_ms(self) -> float:
        return 1000.0 / self.target_hz


@dataclass(frozen=True)
class OverBudgetTick:
    tick_index: int
    observed_ms: float
    budget_tier: str          # "p99" | "p999" | "p9999" | "max"
    threshold_ms: float


@dataclass(frozen=True)
class AllocationTrace:
    n_observations: int
    mean_bytes_per_tick: float
    p99_bytes_per_tick: float
    max_bytes_per_tick: int


@dataclass(frozen=True)
class BudgetSummary:
    n_observations: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    p999_ms: Optional[float]
    p9999_ms: Optional[float]
    max_ms: float
    n_p99_violations: int
    n_p999_violations: int
    n_p9999_violations: int
    n_max_violations: int
    over_budget_ticks: Tuple[OverBudgetTick, ...]
    budget: RealTimeBudget
    meets_budget: bool
    allocation_trace: Optional[AllocationTrace] = None


# realtime/monitor.py

class LatencyMonitor:
    def __init__(
        self,
        budget: RealTimeBudget,
        *,
        track_allocations: bool = False,
    ) -> None: ...

    def observe(self, elapsed_ms: float, *, tick_index: int) -> None: ...
    def observe_series(self, series: np.ndarray) -> None: ...

    def summary(self) -> BudgetSummary: ...

    def reset(self) -> None: ...

    @property
    def n_observations(self) -> int: ...


# realtime/errors.py

class RealTimeBudgetError(Exception): ...
class BudgetViolationError(RealTimeBudgetError): ...
```

The implementation lands paired with this doc. The bare
percentile reporter is sandbox-friendly + composes with the
existing `benchmarks/latency.py`; the AUTOSAR-class load test
is gated behind `@pytest.mark.slow` per the existing
host-speed-sensitive test discipline.
