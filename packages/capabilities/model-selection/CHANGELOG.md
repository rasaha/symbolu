# Changelog

All notable changes to `ugence-model-selection` are documented here.
This project versions the distribution independently of the Ugence platform.

## 0.2.0 — House standard, and a hard capability floor

Brings the package to the repository's standard artifact set and closes the
soft-by-default quality-floor gap the capability audit recorded. Ruled by the repository
owner, 2026-09-09: a package describing itself as a binding external contract may not
remain weakly tested legacy.

### Added

- **A hard, non-compensatory capability floor** at `gate.py`: the optional
  `GateConfig.quality_floor` and the `quality_within_floor` condition, reading a `quality`
  signal with its own evidence and TTL. Below the floor, missing, stale, or not a real
  number in `[0, 1]` → INELIGIBLE. `ReasonCode.QUALITY_BELOW_FLOOR` is appended to the
  taxonomy. See [`docs/QUALITY_FLOOR.md`](docs/QUALITY_FLOOR.md).
- `docs/` — `ARCHITECTURE.md`, `AUTHORITY_BOUNDARY.md`, `QUALITY_FLOOR.md`,
  `LIMITATIONS.md`.
- `py.typed`, shipped via `[tool.setuptools.package-data]` so a consumer's type checker
  does not silently ignore every annotation.
- A committed public-API snapshot: `scripts/public_api_snapshot.py` and
  `artifacts/public_api.json` (33 names), compared on every run by
  `tests/packaging/test_public_api.py`.
- Package gates: `tests/packaging/test_boundaries.py` (per-module import scan, an
  isolated-subprocess probe for indirect reach, and a no-system-clock scan) and
  `tests/test_determinism.py` (identical records and fingerprints, pinned condition order,
  insertion-order independence, staleness measured against the supplied `now`).
- This changelog.

Suite: 18 → 72 tests.

### Why the floor is a gate and not a weight

`policy.select` multiplies the capability prior by `PolicyWeights.quality` and adds it to
a utility from which price and latency subtract up to `0.85` at default weights — so a
free, instant, mediocre model out-scores a costly, slow, better one. Correct for a
preference; wrong for a requirement. As a gate condition it is non-compensatory by
construction: `_aggregate` makes a `CRITICAL_OP` failure INELIGIBLE, and `policy.select`
only ever sees `dec.selectable`. A quality weight of 10,000 still cannot rescue a floored
candidate.

### Compatibility

**No new selection behaviour, and no behaviour change without configuration.** With
`quality_floor` unset — the default — the condition is not evaluated at all, so decision
records are byte-identical to `0.1.0`, including their serialized condition list. The
soft `PolicyWeights.quality` term is untouched and still orders the survivors; among
candidates the floor admits, ranking is byte-identical to an unfloored run. The eligibility
aggregation, the authority contract, the fallback chain, the reason-code meanings and the
`exec_gate_v1` policy version are all unchanged. All 18 pre-existing tests pass unmodified.

The floor **narrows only**: it can remove a candidate from the eligible set and can never
add one. A perfect score does not approve an unapproved provider or rescue a residency,
region, context, or cost-cap failure.

### Not addressed

No model-quality or provider-reliability claim is established; the prior is a
caller-supplied number this package neither computes, validates nor benchmarks. Not
pilot-validated, not production-certified, no live-provider validation. See
[`docs/LIMITATIONS.md`](docs/LIMITATIONS.md).

## 0.1.0 — First canonical distribution

Behaviour-preserving structural migration of the production-shaped `execution_gate` source
into a leaf capability package: ExecutionGate (eligibility), ModelPolicy (ranking) and
ModelAuthority (the binding ALLOW / DENY / HOLD / ESCALATE contract), with the supporting
contracts, reason-code taxonomy and executable registry. The root `execution_gate`
namespace remains a logic-free, identity-preserving compatibility surface.
