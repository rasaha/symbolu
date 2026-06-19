# Outcome Reputation Observable (Phase 2 — deterministic)

**Status:** PROVISIONAL · advisory/confirm-only · shadow-recorded · **off by default**. No ML,
no hidden state, no production behaviour change. Second Phase 2 observable.

## Definition

Outcome Reputation converts **accumulated governance history** — the existing audit chain —
into a present-decision trust signal, per **action type** (keyed by tool name). It reads only
fields already recorded on audit entries; it computes nothing about model internals.

Failure/quality modes it surfaces (all from history):

| Example | Derived from |
|---|---|
| repeated confirmations later approved | high `approval_rate` → **good** (SAFE) |
| repeated confirmations later denied | low `approval_rate` → **poor** |
| recurring escalations | high `confirmation_rate` → **poor** |
| recurring policy violations | high `violation_rate` (blocked) → **poor** |
| historical approval rate by action type | `approvals / (approvals+denials)` |
| historical confirmation rate by action type | `(approvals+denials) / n` |

## Asymmetry (safety)

Reputation can **only lower** trust (escalate to CONFIRM on a poor history); a *good* history
**never raises** trust or auto-allows anything — mirroring the TRUST_SIGNAL asymmetry. So the
observable is purely conservative and cannot relax any decision.

## Determinism (no ML, no hidden state)

Pure aggregation of prior audit entries for the tool, then fixed-threshold classification:

- Each prior entry is classified deterministically from `decision` + `human_confirmed`:
  `approved` (allowed + human_confirmed), `denied` (escalate), `auto_allow` (allowed, no
  human), `blocked` (violation), `error` (error/timeout).
- Rates: `approval_rate`, `confirmation_rate`, `violation_rate`, `error_rate`.
- Verdict (fixed policy thresholds — **calibration placeholders**, see Promotion):
  - `n < MIN_VOLUME` → no signal (inert).
  - `UNSAFE` (egregious) — `approval_rate == 0` over ≥`MIN_ADJUDICATED` confirmations, or
    `violation_rate ≥ EGREGIOUS_VIOLATION`.
  - `UNSURE` (poor) — `approval_rate < APPROVAL_FLOOR`, or `violation_rate ≥ VIOLATION_CEIL`,
    or `denial_rate ≥ DENIAL_CEIL` (recurring *denied* escalations).
  - else `SAFE`.

  A high `confirmation_rate` whose confirmations are mostly *approved* is **not** poor — only
  recurring *denials*/violations lower trust (asymmetry: an approval-gated action humans keep
  approving stays SAFE).

No time-decay (wall-clock would break determinism); a bounded count window (`MAX_LOOKBACK`)
keeps it bounded and reproducible from the same chain. While PROVISIONAL, `UNSAFE`/`UNSURE`
both collapse to CONFIRM (the kernel guarantees a PROVISIONAL validator never blocks); the
split only matters after promotion to PROVEN.

## Uses only existing audit-chain data

It reads the gateway's own audit log (the in-memory view of the durable, hash-chained store) —
`tool_name`, `decision`, `human_confirmed` — fields already persisted in Phase 1.5. It adds
**no** new recorded fields and makes **no** new store queries on the hot path.

## Inert by default (no production behaviour change)

Computed **only** when `SafeMCPGateway(enable_outcome_reputation=True)` (default **False**). With
the flag off the observable is never built → the recorded/authoritative decision is unchanged;
existing parity / shadow-volume corpora (single calls per tool, flag off) are unaffected. When
on, it participates in **shadow mode**, **parity reporting** (a `outcome_reputation` driver,
stricter-only escalation classified `intended`), **audit persistence** (`trust_shadow.drivers`
+ `trust_observations`), and **shadow_report aggregation** (mismatch-by-driver).

## Promotion plan (PROVISIONAL → PROVEN)

Promotion would let an *egregious* reputation BLOCK (instead of only CONFIRM). It requires:

1. **Minimum volume.** Per action type, ≥ a calibrated `MIN_VOLUME` of adjudicated outcomes
   (initial placeholder 5; real value set from production distribution so the rate estimates
   are stable, not noise). Aggregate program-wide ≥ a few thousand governed calls.
2. **Calibration requirements.** The fixed thresholds (`APPROVAL_FLOOR`, `VIOLATION_CEIL`,
   `DENIAL_CEIL`, `EGREGIOUS_VIOLATION`, `MIN_ADJUDICATED`, `MAX_LOOKBACK`) re-derived
   from real traffic so that a "poor" verdict corresponds to a genuinely elevated
   downstream-denial/violation rate (precision target agreed with governance owner). Still
   fixed constants after calibration — **no fitted model**.
3. **Review process.** Run in shadow with the flag on over a production window; `shadow_report`
   must show **0 unsafe_relaxation, 0 unintended**, and the `outcome_reputation` escalations
   must be spot-audited against the underlying history (every UNSAFE/UNSURE traced to real
   denials/violations, no deterministic bug, no feedback loop where the signal inflates its own
   confirmation rate).
4. **Sign-offs.** Governance/safety (accepts reputation as a blocking authority), audit/
   compliance (chain integrity + provenance of the history is authoritative, not model-
   supplied), and service/on-call (confirm-flow capacity) — same gate as the JEPA demotion.

Promotion is a one-line evidence change (`PROVISIONAL → PROVEN`) plus the egregious→BLOCK it
unlocks, itself parity-gated and differential-checked. **Not done here. No authority expansion.**
