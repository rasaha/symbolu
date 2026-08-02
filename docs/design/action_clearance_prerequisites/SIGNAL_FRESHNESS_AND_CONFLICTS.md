# Signal Freshness & Conflict Resolution

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Extends
`docs/design/action_clearance/TIME_AND_FRESHNESS.md` and the merged condition table in
`TRUSTED_SIGNAL_MODEL.md`. Introduces no new status; all outcomes map to the four merged statuses.

## Part 1 — Freshness

### Core predicate (all must hold for a required, time-bounded signal)

```text
signal.captured_at <= evaluation_time                      # not from the future
evaluation_time    <= signal.valid_until                   # not expired
(evaluation_time - signal.captured_at) <= policy.max_age   # not stale
```

`evaluation_time` is caller-supplied (no core clock read), per the merged determinism decision.

### Rules

| Case | Rule | Result |
|---|---|---|
| exact boundary `evaluation_time == valid_until` | boundary-at-expiry counts as **expired** (merged decision) | `SIGNAL_STALE → HOLD` |
| `captured_at > evaluation_time` (future capture) | reject; a signal cannot be observed after evaluation | `NON_RETRYABLE_ERROR` (malformed) |
| clock skew | a bounded, policy-declared skew allowance may apply to `captured_at ≤ evaluation_time` only; **skew never extends `valid_until`** | per policy |
| signal without `valid_until`, type is time-bounded | missing mandatory bound → **fail closed** | `SIGNAL_STALE → HOLD` |
| signal without `valid_until`, type not time-bounded | permitted; freshness governed by `max_age` only | evaluate |
| source-specific freshness limit | the source registry's per-source `max_age` overrides the neutral default when stricter | evaluate (stricter wins) |
| stale but non-critical signal | policy may downgrade to advisory reason without blocking, **only** if the signal is not mandatory | `CLEAR` with advisory reason |
| stale mandatory signal | never CLEAR | `SIGNAL_STALE → HOLD` |

### Supersession & repetition

- **Replacement / supersession:** when two signals of the same type describe the same subject, the one
  with the newer `captured_at` supersedes — **unless** they *disagree on value*, which is a conflict
  (Part 2), not a supersession.
- **Repeated identical signal** (same content fingerprint): deduplicated; contributes once.
- **Conflicting capture times with identical value:** newest `captured_at` wins; no conflict.

### Where freshness policy lives (decision)

| Owner | Owns |
|---|---|
| **neutral Action Clearance policy** | the *shape* of the predicate and the fail-closed defaults (boundary-at-expiry, missing-bound → fail closed) |
| **domain profile** | per-signal-type `max_age` defaults for the profile (e.g. GitHub required-check freshness) |
| **source registry** | per-source overrides (a stricter `max_age` for a specific source) |
| **product policy** | tenant-level tuning within the profile's allowed range |

To avoid duplicate sources of truth, the **neutral policy owns the invariant**, the **profile owns the
defaults**, and the **registry owns per-source stricter overrides** — precedence: `registry override >
product policy > profile default > neutral default`, and a stricter value always wins.

## Part 2 — Conflict resolution (deterministic, non-compensatory)

Action Clearance uses **non-compensatory** rules: a mandatory negative fact is never averaged away by
positive facts. There is no score.

### Semantics

| Situation | Rule | Result |
|---|---|---|
| compatible signals | deterministic **intersection** of constraints; all positive facts must hold | contributes to `CLEAR` |
| a mandatory negative signal | e.g. `ACTOR_INVALID`, `ALREADY_CONSUMED`, `ACTIVE_INCIDENT` (blocking) | **BLOCK** or **HOLD** per the reason code's default status |
| direct conflict (two signals of one type disagree) | no deterministic winner unless an authoritative owner is declared | **ESCALATE** (or **BLOCK** by policy) — `SIGNAL_CONFLICT` |
| missing conflict rule | fail closed | **ESCALATE**/`CLEARANCE_POLICY_CONFLICT` |

### Worked examples

| Signals | Resolution |
|---|---|
| identity `ACTIVE` vs security `SUSPENDED` | security-status is authoritative-negative for actor validity → **BLOCK** (`ACTOR_INVALID`) — no averaging |
| GitHub checks `PASS` vs policy cache "check set outdated" | the policy-version signal is authoritative on *which* checks are required; outdated check set → **HOLD**/`GITHUB_REQUIRED_CHECK_PENDING` until re-evaluated against current required set |
| incident `NO_INCIDENT` vs change-mgmt `FREEZE_ACTIVE` | different facts, both mandatory; freeze is a blocking operational state → **HOLD** (`ACTIVE_CHANGE_FREEZE`); no incident does not override an active freeze |
| two identity sources disagree on actor status | direct conflict, no single authoritative owner declared → **ESCALATE** (`SIGNAL_CONFLICT`) |

### Source precedence

Precedence is declared **only where an authoritative owner exists** (see
`docs/design/action_clearance/SIGNAL_OWNERSHIP_MATRIX.md`): identity provider owns `ACTOR_STATUS`,
incident system owns `ACTIVE_INCIDENT`, change-management owns `CHANGE_FREEZE`, execution ledger owns
`PRIOR_CONSUMPTION`. Where two *distinct* authoritative owners assert *different facts*, both facts hold
(intersection). Where two sources assert the *same fact type* and disagree, and neither is the declared
owner, the result is `ESCALATE`. Contradictory operational facts are **never** averaged into a score.

## Closure

**CLOSED_BY_NEW_PRODUCT_INTERFACE** — freshness precedence and non-compensatory conflict rules are
deterministic policy over the merged signal model; no new status, algorithm, or store.
