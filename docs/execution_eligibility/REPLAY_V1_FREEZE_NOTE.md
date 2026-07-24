# replay_v1 Freeze Note

*Phase 2 deliverable.*

## What is frozen

The completed deterministic Execution Eligibility replay evaluation is frozen as an
immutable versioned artifact at `execution_gate/frozen/replay_v1/`:

- `artifacts/` — byte-exact copies of the scenario dataset + ground truth (`scenarios.py`),
  baseline configuration (`baselines.py`), eligibility policy engine + types + state
  semantics + reason-code version (`gate.py`, `model.py`, `states.py`, `reason_codes.py`),
  executable registry (`registry.py`), model policy (`policy.py`), metric definitions +
  simulator (`harness.py`), the exact evaluation output (`evaluation.json`), and the
  evaluation protocol, report, and limitations/falsification documents.
- `MANIFEST.json` — artifact version, protocol version, package version, repository commit
  SHA, creation timestamp, per-file SHA-256, aggregate manifest hash, scenario/baseline
  counts, metric names, primary endpoint, success criteria, the reported result summary, and
  an explicit statement that this version is **outcome-bearing and no longer tunable**.
- `build_freeze.py` / `verify_frozen.py` — the builder and a drift-verification script that
  recomputes all hashes and exits non-zero on any change.

**Aggregate manifest hash:** `8b05b2da798a6222…` (13 artifacts).

## Why it is frozen

The replay evaluation has produced results and a falsification verdict. From this point it is
**evidence**, not a design under tuning. Freezing with cryptographic hashes prevents silent
retroactive edits to scenarios, ground truth, baselines, thresholds, or reported numbers, and
lets any reviewer confirm the exact artifacts behind the report.

Note: a packaging-only import refactor (Milestone 1) touched import lines in the source
modules; the evaluation **output is byte-identical** before and after (verified), so the
frozen `evaluation.json` is the exact output used in the completed report.

## What future work may not change retroactively

- The replay_v1 scenarios, ground truth, baseline definitions, eligibility/reason-code/state
  semantics, metric definitions, thresholds, success criteria, and reported endpoint values.
- The completed evaluation report and limitations/falsification report as historical records.

Any of these that must change requires a **new version**, not an edit.

## How a replay_v2 or calibration study must be versioned

- A new evaluation (new scenarios, changed thresholds, TTL calibration, live data) must live
  under a new directory (`execution_gate/frozen/replay_v2/`, or a `ttl_calibration_v1/`
  study) with its own manifest, hashes, protocol, and pre-registration.
- It must **not** reuse replay_v1 as fresh confirmatory evidence, and must cite replay_v1 as
  prior, frozen context.
- The TTL calibration (the dominant replay limitation) is explicitly a **separate, prospective
  study** (see `LIVE_SHADOW_PILOT_PROTOCOL.md`), not a re-interpretation of replay_v1.

## Unresolved limitations that remain (carried forward, not fixed here)

- Modeled ground truth (not live-billed); external validity requires the live shadow pilot.
- Small hand-built suite (11 scenarios); aggregate metrics depend on the scenario mix.
- Staleness/TTL is the dominant risk and is unaddressed by replay_v1 — deferred to a
  prospective calibration study.
- Reference ModelPolicy is intentionally simple; the scientific selection engine is the
  frozen Model Selection Policy.

## Verification command

```
python3 execution_gate/frozen/replay_v1/verify_frozen.py   # exits non-zero on drift
```
Run before relying on replay_v1 or before any commit that touches the freeze.
