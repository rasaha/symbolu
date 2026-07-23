# Live Shadow — Go/No-Go Review

*Phase 16. Gate for whether a controlled Stage A (synthetic connectivity calibration) may begin.
This document does NOT begin live execution.*

## Verdict: **LIMITED GO** — ready for controlled Stage A, contingent on the two unresolved
data-handling facts being settled by the data owner first.

## GO checklist

| Requirement | Status |
|---|---|
| Root-level tests pass (research suites) | ✅ 76 passed together (execution_gate 21, shadow 23, pilot 17, experiment 15) |
| replay_v1 hashes verify | ✅ `verify_frozen.py` OK (aggregate `8b05b2da798a6222`) |
| Live calls disabled by default | ✅ `ShadowConfig.live_calls_enabled=False`; RealProviderAdapter refuses; tested |
| Privacy controls tested | ✅ redaction test (secrets + project IDs); no raw content persisted by default |
| Spend + request + quota caps tested | ✅ cap-exceeded aborts; non-approved provider blocked |
| Audit records append correctly | ✅ append-only JSONL; audit-write-failure aborts (tested) |
| Prediction and observation independent | ✅ separate logs; contradictory observation test |
| Dry-run metrics reproduce deterministically | ✅ identical prediction-log hash + metrics across runs |
| Approved provider/model allowlist explicit | ✅ empty by default; explicit sets required for any live call |
| No unresolved **critical** data-handling issue | ⚠️ see below |

## Why LIMITED (not full) GO

Two data-handling facts are marked **UNRESOLVED** in `LIVE_PILOT_DATA_HANDLING.md` and must be
settled by the data owner **before** Stage A persists anything:

1. **Retention period** for shadow records.
2. **Access-control specifics** for shadow artifacts.

These are governance decisions, not code — the harness enforces redaction, append-only audit, and
caps regardless, but the retention/access policy must be set by a human owner. Until then, Stage A
may run **only** in an ephemeral, self-contained mode that writes to a local, access-controlled
scratch location and deletes on completion.

## Conditions attached to the LIMITED GO

- Stage A only: synthetic prompts, approved providers/models explicitly listed, spend/request/quota
  caps set > 0, `live_calls_enabled=True` set explicitly by an operator (never defaulted).
- The RealProviderAdapter in this track deliberately does **not** perform network calls even when
  enabled; a real network implementation is a separate, reviewed change with its own tests.
- Abort conditions active: audit-write failure, cap breach, non-approved provider, missing
  protocol/manifest version, cost-not-estimable.
- No Stage B (advisory shadow traffic over real partner contexts) until Stage A completes and the
  retention/access facts are resolved.

## What a NO-GO would have looked like

Any of: tests failing, replay_v1 drift, live calls enabled by default, redaction/audit/cap tests
failing, or an unresolved **critical** (not merely governance-config) data-handling issue such as
raw partner content flowing to a new provider. None of these is present.

## Next action (not automatic)

Resolve retention + access policy, list the approved provider/model allowlist, set caps, then run
Stage A connectivity calibration under explicit operator control. **Do not begin live execution
from this document.**
