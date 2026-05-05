# Functional-safety state machine — design

This doc specifies the four-state safety state machine the
`bcvf_autonomous` runtime composes into. It follows the pattern
established by `HIERARCHICAL_BCVF_DESIGN.md` and
`MULTI_MODAL_PREDICTORS_DESIGN.md`: design first, implementation
second, ship-when-ready criteria explicit. The doc lands paired
with a thin-shim implementation in
`safety_state/`; the shim is registered as
`PROVISIONAL_API` per §9.

## §1 Why this exists

The bcvf_autonomous code today is a **runtime layer** — kernel
(`core.py`), arbitration (`trust.py` + `mppi_planner.py`),
diagnostics (`trust_diagnostics.py`), fleet harness
(`analysis/`). What's missing is the **behavioural contract** the
runtime composes into: a named state model, with named
transitions and named recovery actions, that an ISO 26262 safety
case can argue against.

That gap is architectural, not tactical. Every other industry-
features-roadmap item (real-time budget, replay, calibration,
attestation) is incremental coverage — useful but not
load-bearing for the deal-unlock conversation. The state machine
is the single piece that turns *"we have a kernel"* into *"we have
a safety component."* A safety reviewer doesn't argue against a
kernel; they argue against a state graph with named transitions
and named mitigations per state. The state machine is that graph.

The state machine **does not replace the kernel.** It composes
the kernel's per-tick output (BCVF cost, exclusion vector,
near-veto signal) into a system-level posture the planner can
condition on. The kernel is still the detector; the state machine
is the supervisor that names what to do when the detector keeps
firing.

## §2 Four states + state-transition diagram

The four states partition the kernel's per-tick runtime posture
into operationally distinct regimes a planner can condition on.

| State | Predictor consensus | BCVF posture | Planner posture |
|---|---|---|---|
| **NORMAL** | every predictor agrees | quiet (BCVF total below noise floor on rolling window) | full-resolution consensus, full-speed envelope |
| **DEGRADED** | one predictor flagged near-veto | firing intermittently (rolling-window rate elevated, no exclusion sustained) | reduced speed envelope, increased headway |
| **FAULT** | one predictor sustained-excluded | sustained activity (BCVF firing on most ticks in window, exclusion logic triggered) | minimum-risk maneuver (pull over, hand back to teleop) |
| **FAILSAFE** | ≥ 2 predictors excluded — kernel cannot form quorum | persistent activity, multi-predictor exclusion | emergency stop |

The transition graph (six legal edges, two manual-reset paths,
no direct jumps):

```
                  trigger: rolling near-veto rate > θ_NV
                  recovery: T_recovery sustained NORMAL
   NORMAL  ────────────────────────────────────►  DEGRADED
                                                      │
                                                      │ trigger: sustained BCVF
                                                      │ + ≥ 1 excluded predictor
                                                      ▼
   FAULT  ◄─── reset_with_diagnostic_clear() ──── DEGRADED
     │                  (manual, ASIL-B)            ▲
     │                                              │
     │  trigger: ≥ 2 excluded predictors            │ NEVER (machine raises)
     ▼                                              │
   FAILSAFE  ─── reset_with_diagnostic_clear() ─────┘
                  (manual, ASIL-B)
```

**Direct jumps from NORMAL to FAULT or FAILSAFE are
prohibited** — the machine raises `IllegalTransitionError` on
any attempt. See §6.

The state machine is monotonic on degradation under automatic
triggers — every automatic transition either holds the current
state or escalates one step. Recovery (de-escalation) is
automatic only on the DEGRADED → NORMAL edge; FAULT → DEGRADED
and FAILSAFE → FAULT require explicit
`reset_with_diagnostic_clear()` per §4.

## §3 Trigger conditions per transition

Triggers read from the existing `TrustShapedEpisodeRecord`
fields. The machine maintains a configurable rolling window of
the last `N` per-step observations and evaluates the trigger
predicate on every `observe()` call.

| Transition | Trigger condition | Reads |
|---|---|---|
| NORMAL → DEGRADED | rolling fraction of ticks with `near_veto` ≥ `near_veto_rate_threshold` | `per_step_consec_suspect` |
| DEGRADED → FAULT | (any predictor `is_excluded` for ≥ `exclusion_persistence_ticks` consecutive ticks in window) **AND** (rolling fraction of ticks with `bcvf_total` > `bcvf_active_threshold` ≥ `bcvf_active_rate_threshold`) | `per_step_is_excluded` + `per_step_bcvf_total` |
| FAULT → FAILSAFE | rolling count of distinct predictors with `is_excluded == True` at any tick in window ≥ `failsafe_excluded_predictor_count` (default 2) | `per_step_is_excluded` |

Definitions:

* **near_veto** at tick `t` for predictor `m`: `consec_suspect[t,
  m] ≥ near_veto_consec_floor` (default 3 — one short of the
  default `T_exclude` of 4 in `ConsumerV2Config`). Encodes "this
  predictor crested the suspicion floor without yet crossing the
  exclusion threshold."
* **bcvf_active** at tick `t`: `bcvf_total[t] >
  bcvf_active_threshold` (default 0.05 — above the kernel's
  noise floor on nominal scenarios).
* **rolling fraction**: number of ticks satisfying the predicate
  in the last `rolling_window_ticks` (default 200) divided by the
  window length.

The defaults are calibration knobs, not safety-critical
invariants. A deployment partner is expected to tune them
against their operational design domain; the machine exposes
all three thresholds + window length on
`SafetyStateMachineConfig`. Defaults are picked so the
characterization grid's nominal scenarios sit comfortably in
NORMAL and the failure families (`accelerating`, `outlier`,
`sensor_dropout`) walk through DEGRADED → FAULT cleanly at the
documented magnitudes.

The trigger predicates are **rolling-window**, not single-tick,
to bound transition chatter. Single-tick BCVF spikes (an outlier
on one frame, a sensor dropout that recovers in two ticks) do
**not** transition the machine — only sustained signal does.
That's the design discipline that lets the safety case argue
"each transition reflects a real shift in posture, not a
momentary spike." Single-tick chatter immunity is the same
discipline `ConsumerV2` applies one level lower (Schmitt
trigger on the kernel's per-tick output); the state machine
applies the same discipline one level higher.

## §4 Recovery conditions

Recovery (de-escalation) follows three different disciplines
across the state-graph:

* **DEGRADED → NORMAL** is automatic. Recovers when the rolling
  near-veto rate drops below `near_veto_rate_threshold` AND has
  remained below for `T_recovery_ticks` consecutive ticks
  (default 100, ≈ 1 second at 100 Hz). The dwell time gates a
  fast oscillation between NORMAL and DEGRADED — a transient dip
  in near-veto rate within a sustained-degraded run won't bounce
  the machine back to NORMAL.

* **FAULT → DEGRADED** is **manual only** via
  `reset_with_diagnostic_clear()`. The discipline: a planner
  that took the minimum-risk maneuver should not return to
  reduced-envelope operation just because the kernel went quiet;
  a human (or a higher-level supervisor) must affirmatively
  acknowledge the diagnostic before the machine releases the
  FAULT posture. The reset call records the operator identity +
  free-form clear reason on the transition log so the audit
  trail is complete.

* **FAILSAFE → FAULT** is **manual only** via the same call.
  The discipline: a vehicle that emergency-stopped because the
  kernel couldn't form quorum must not auto-recover into the
  FAULT (minimum-risk maneuver) posture even if quorum returns.
  The deployment-partner safety case decides what "diagnostic
  clear" means — typically a teleop handshake or a maintenance
  inspection. The machine just enforces that *some* explicit
  clear happened.

There is intentionally **no** automatic recovery from FAULT or
FAILSAFE. A safety case for a Tier 1 deployment cannot rely on
"the kernel went quiet" as a sufficient signal that the cause
of the FAULT was resolved — quiet kernel is necessary but not
sufficient. The manual-reset gate makes the safety case
defensible.

## §5 ASIL decomposition

ISO 26262 asks every safety-relevant function to carry an ASIL
classification. The state machine's transitions decompose as:

| Transition | ASIL | Reasoning |
|---|---|---|
| NORMAL → DEGRADED | **B** | Warning, not safety-critical — the planner reduces envelope but the vehicle is still under nominal control. A spurious DEGRADED entry is an availability issue, not a safety issue. ASIL-B is the warning-class floor. |
| DEGRADED → NORMAL | **B** | Same — recovery to nominal envelope. A spurious NORMAL recovery in a still-degrading scenario is an availability issue (system bounces) but the kernel-level signal will re-trigger the next DEGRADED transition. ASIL-B floor. |
| DEGRADED → FAULT | **D** | Safety-critical action — the planner switches into minimum-risk maneuver (pull-over, hand-back). Missing this transition when warranted (false-negative) leaves the vehicle operating against a confirmed-failing predictor stack; firing this transition spuriously (false-positive) interrupts service. Both failure modes hit ASIL-D risk thresholds. |
| FAULT → FAILSAFE | **D** | Safety-critical action — the planner switches to emergency stop. Same false-negative / false-positive analysis as DEGRADED → FAULT, with the additional load that FAILSAFE escalates from a controlled minimum-risk maneuver to an unconditional stop, which can introduce its own hazards in dense traffic. ASIL-D. |
| FAULT → DEGRADED | **B** | Manual-reset path — the operator (or supervisor) explicitly acknowledged the diagnostic and authorized the return to reduced-envelope operation. The safety-critical decision is the human's; the machine just enforces that the call happened. ASIL-B for the state-machine bookkeeping (the human-factors layer carries its own ASIL classification at the deployment-partner level). |
| FAILSAFE → FAULT | **B** | Same manual-reset discipline. The human-factors layer is the load-bearing safety argument; the state machine's ASIL classification covers the bookkeeping (transition recorded, log written, no auto-recovery). |

ASIL-D transitions (DEGRADED → FAULT, FAULT → FAILSAFE) carry
the strongest verification discipline in this codebase: pinned
trigger condition tests + pinned non-trigger condition tests +
characterization-grid `state_transition_consistency` family
exercising each transition at the documented threshold + at
adjacent-but-non-triggering thresholds. The traceability matrix
references each ASIL-D transition as evidence in SOTIF clause 8
(functional insufficiencies + mitigations).

## §6 Direct-jump prohibition

The state graph forbids direct transitions from NORMAL to FAULT
or NORMAL to FAILSAFE. The machine enforces this:
`SafetyStateMachine.observe()` evaluates triggers in escalation
order (NORMAL → DEGRADED first, then DEGRADED → FAULT, then
FAULT → FAILSAFE), so a single tick that satisfies multiple
triggers walks the graph one edge per `observe()` call.

The discipline:

* **Auditability.** A direct NORMAL → FAULT jump masks whether
  the system passed through DEGRADED first. The DEGRADED window
  is the safety case's diagnostic preamble — *"the system saw
  near-veto signals before it took the minimum-risk maneuver"*
  is a stronger argument than *"the system jumped straight to
  pull-over."*
* **Single-cause discipline.** If the NORMAL → DEGRADED
  trigger doesn't fire, the DEGRADED → FAULT trigger shouldn't
  either — the latter is a strict subset of the former
  (sustained BCVF activity is a stronger condition than
  intermittent near-veto). A direct NORMAL → FAULT jump means
  the trigger thresholds are inconsistent; better to fail
  loudly than to silently transition.
* **Test surface.** The forbidden-transition table is
  machine-readable; every (s_from, s_to) pair NOT in the
  legal-edge table is exercised by a parametrized test that
  asserts `IllegalTransitionError`.

The machine raises `IllegalTransitionError` (subclass of
`SafetyStateMachineError`) on any attempt to call the internal
`_transition(from, to)` with a `(from, to)` pair not in the
legal-edge table. Public `observe()` cannot trigger the error
under normal use — its dispatch logic by construction only
issues legal transitions — but a future contributor adding a
new automatic recovery path (e.g. FAULT → DEGRADED automatic)
without first widening the legal-edge table will trip the
error in tests.

## §7 Composition with existing surfaces

The state machine is designed to compose with — not replace —
the surfaces already shipped:

* **`StreamingFleetMonitor` + `AlertRule` (analysis/streaming.py).**
  The state machine emits a per-tick state. A deployment partner
  ingests the state stream into the existing monitor as a custom
  metric (`current_safety_state == DEGRADED`,
  `time_in_FAULT_seconds`) and writes `AlertRule`s against that
  metric — *"alert if a fleet vehicle spends > 5% of a 24-hour
  window in DEGRADED."* The state machine does not subsume the
  monitor; it adds a behavioural-state surface the monitor's
  threshold rules can fire on.

* **SOTIF traceability matrix
  (`safety_case/traceability.py`).** The matrix gains a new
  evidence artifact `_SAFETY_STATE_MACHINE` referenced from SOTIF
  clause 8 (functional insufficiencies + mitigations) — the
  state machine is the **insufficiency-handling layer** the
  per-tick V2 chatter mitigation composes into. ISO 26262
  Part 6 §8 (architectural design) gains the same artifact —
  the state machine is a named module in the architecture, with
  named interfaces (`observe`, `state`, `transition_log`,
  `reset_with_diagnostic_clear`) and ASIL-decomposed transitions.
  Clause 9 (V&V) notes acknowledge the state machine as the
  behavioural-contract layer the per-cell threshold gates
  compose into.

* **Characterization grid (`characterization/sweep.py`).** The
  grid extends with a `state_transition_consistency` cell
  family. Each cell exercises one transition at one trigger
  magnitude across N seeds, and asserts both:
  - the documented trigger condition fires the transition
    (must-fire);
  - an adjacent-but-non-triggering condition does NOT fire the
    transition (must-be-quiet).
  The pattern mirrors the existing per-family acceptance
  thresholds — the cell's `pass / fail` verdict is the per-
  transition consistency property, with Wilson 95% CI lower
  bound the same as the rest of the grid.

* **`TrustShapedEpisodeRecord` (trust_diagnostics.py).** The
  state machine is a *consumer* of this record — it reads the
  per-step fields described in §3 and emits a per-step state.
  No changes to `TrustShapedEpisodeRecord` are required; the
  machine's view is read-only.

## §8 What this is NOT

* **Not a planner replacement.** The state machine emits a
  named state per tick; a planner conditions on that state. The
  state machine itself does not generate trajectories, decide
  speed envelopes, or issue actuator commands. Mapping a state
  to planner posture is the deployment partner's responsibility.
* **Not a generic state-machine library.** The four states +
  six edges are the BCVF-specific contract. A different safety
  component (perception, localization, comms) needs its own
  state graph; this one is not a base class for those.
* **Not a substitute for the deployment partner's safety case.**
  The matrix maps the state machine to ISO 26262 Part 6 §8
  + SOTIF clause 8, but the document an OEM signs against is
  the OEM's, not ours. The state machine is one evidence
  artifact in their case.
* **Not a replacement for `ConsumerV2`'s per-tick chatter
  immunity.** Consumer V2 prevents single-tick argmax flips
  inside the kernel; the state machine prevents single-tick
  state transitions at the system level. They compose — V2
  smooths the input, the state machine smooths the output.
* **Not field-deployable today.** Per §9, all symbols enter
  `PROVISIONAL_API`. STABLE_API graduation requires three
  deployment-partner production exercises + a TÜV / external
  auditor review — see §9.

## §9 Ship-when-ready criteria for STABLE_API graduation

The state machine ships in `PROVISIONAL_API`. Three explicit
gates promote it to `STABLE_API`:

1. **Three deployment partners** exercise the state machine in
   production for one quarter without filing a state-graph
   change request. The four-state graph is not a research
   surface — it's a contract a safety case is built against.
   If three independent OEMs agree the four-state model is the
   right cut, that's the empirical ratification.
2. **Characterization grid extension.** The `state_transition_
   consistency` cell family lands with one cell per documented
   transition, asserting both must-fire and must-be-quiet
   behaviour at adjacent thresholds. Every cell must clear the
   per-config Wilson 95% CI floor (0.90, same as the rest of
   the grid). Failure of any cell blocks promotion.
3. **External auditor review.** A TÜV / SGS / DEKRA-equivalent
   reviewer signs off the ASIL decomposition table in §5.
   This gate is **out-of-sandbox** — it cannot be exercised by
   the test suite. It is pinned here as the explicit promotion
   checkpoint so a future contributor cannot accidentally
   promote without it.

Until all three land, the symbols stay in `PROVISIONAL_API` and
the API stability policy in `API_STABILITY.md` §2.2 governs
their evolution (signature may evolve in a minor release with a
release-note line). The maturation path is the same one
documented in `INDUSTRY_FEATURES_ROADMAP.md` §11 — design doc
→ provisional implementation → stable graduation gated on
explicit, named criteria.

## §10 API sketch (no implementation in this doc)

The implementation lives in `safety_state/`; this section
captures the type signatures the implementation will satisfy.

```python
# safety_state/state.py

class SafetyState(str, Enum):
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    FAULT = "FAULT"
    FAILSAFE = "FAILSAFE"


@dataclass(frozen=True)
class StateTransition:
    from_state: SafetyState
    to_state: SafetyState
    trigger: str           # named trigger / "manual_reset"
    asil: str              # "ASIL-B" or "ASIL-D"


# The ordered list of legal transitions — pinned by tests.
LEGAL_TRANSITIONS: tuple[StateTransition, ...] = (
    StateTransition(NORMAL,   DEGRADED, "near_veto_rate",    "ASIL-B"),
    StateTransition(DEGRADED, NORMAL,   "sustained_recovery", "ASIL-B"),
    StateTransition(DEGRADED, FAULT,    "exclusion_sustained", "ASIL-D"),
    StateTransition(FAULT,    FAILSAFE, "multi_predictor_excluded", "ASIL-D"),
    StateTransition(FAULT,    DEGRADED, "manual_reset",       "ASIL-B"),
    StateTransition(FAILSAFE, FAULT,    "manual_reset",       "ASIL-B"),
)
```

```python
# safety_state/triggers.py

class TriggerCondition(Protocol):
    """Evaluates against a rolling-window view of TrustShapedEpisodeRecord."""

    name: str

    def evaluate(self, window: RollingWindow) -> bool: ...
```

```python
# safety_state/machine.py

@dataclass
class SafetyStateMachineConfig:
    rolling_window_ticks: int = 200
    near_veto_consec_floor: int = 3
    near_veto_rate_threshold: float = 0.10
    bcvf_active_threshold: float = 0.05
    bcvf_active_rate_threshold: float = 0.50
    exclusion_persistence_ticks: int = 5
    failsafe_excluded_predictor_count: int = 2
    t_recovery_ticks: int = 100


@dataclass(frozen=True)
class StateTransitionLogEntry:
    timestamp: datetime
    transition: StateTransition
    cause: str             # human-readable trigger description
    tick_index: int


class SafetyStateMachine:
    def __init__(self, config: SafetyStateMachineConfig | None = None,
                 clock: Callable[[], datetime] | None = None) -> None: ...

    @property
    def state(self) -> SafetyState: ...

    @property
    def transition_log(self) -> tuple[StateTransitionLogEntry, ...]: ...

    def observe(self,
                record: TrustShapedEpisodeRecord,
                tick_index: int | None = None,
                classification: str | None = None) -> SafetyState: ...

    def reset_with_diagnostic_clear(self,
                                    operator: str,
                                    reason: str) -> SafetyState: ...
```

```python
# safety_state/errors.py

class SafetyStateMachineError(Exception): ...
class IllegalTransitionError(SafetyStateMachineError): ...
```

The implementation is design only at the **doc level** —
implementation lands in the same commit per the maturation
discipline documented in `INDUSTRY_FEATURES_ROADMAP.md` §11.
This section pins the surface a future refactor must preserve.
