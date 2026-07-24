# Reviewer Label Schema (Phase 10)

*The structured label a reviewer submits, and the rules that validate it. Implemented in
`reviewer_ready_pilot/schema.py`; the interface, metrics, adjudication, and audit all consume it.*

Validation **rejects** malformed labels — it never repairs, guesses, or fills them in.

## Stage A — blinded label (no system result visible)

| Field | Type | Allowed / rule |
|---|---|---|
| `obligation` | enum | `E0 E1 E2 E3 E4 ER` |
| `risk_tier` | enum | `low medium high critical unknown` |
| `source_authority` | enum | `authoritative non_authoritative self_referential stale unknown` |
| `obligation_satisfied` | bool? | does the available evidence meet the obligation? |
| `action_present` | bool? | is an action proposed? |
| `action_requires_approval` | bool? | if `action_present`, must be `True` |
| `trap_detected` | str | trap family name, or `none` |
| `confidence` | float | `0..1` |
| `review_time_seconds` | float | `>= 0` |
| `reason` | str | free text |

Guard: `E0` is invalid at `high`/`critical` risk (surface guard; the frozen policy remains the authority).

## Stage B — post-reveal label (after the system result is shown)

| Field | Type | Allowed / rule |
|---|---|---|
| `obligation` | enum | `E0..ER` |
| `agreement` | bool? | agrees with the system's obligation? |
| `override` | bool? | reviewer overrides the system result |
| `override_direction` | enum | `stricter more_permissive none` |
| `override_reason` | str | **required** when `override` is true |
| `acceptable_actiongate_outcome` | enum | a **native** ActionGate outcome (below) |
| `explanation_useful` | int? | `1..5` |
| `trace_comprehensible` | bool? | |
| `missing_context` | bool? | |
| `confidence` | float | `0..1` |

Rule: `override` requires both a `reason` and a non-`none` `direction`; no override ⇒ direction `none`.

## Native ActionGate vocabulary (never collapsed)

`ALLOW`, `ALLOW_WITH_CONSTRAINTS`, `DENY`, `ESCALATE_TO_HUMAN`, `REQUEST_MORE_EVIDENCE`,
`SIMULATE_AND_RETRY` (plus `not_applicable`). The schema rejects any attempt to record an ActionGate
outcome as `allow`/`deny` — the six outcomes carry distinct meaning and must be preserved.

## The four separations the schema encodes

`obligation` (what standard applies) · `obligation_satisfied` (is it met) · claim truth (never asserted by
the reviewer) · deliverable/action authorization (Stage B + ActionGate outcome). Conflating these is the
most common review error; the schema keeps them in distinct fields.

## Honesty notes

- The schema stores what a **real reviewer** submits; nothing here generates labels.
- Stage A is blinded by construction — no schema field carries the system result, and the interface
  (Phase 11) refuses to reveal it before Stage A is locked.
- `enforced` never appears as a writable field: no label can trigger enforcement or an external action.
