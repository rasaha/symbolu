# Trust Core — Operations Runbook (shadow / canary / reports)

How to run production SHADOW, collect `trust_shadow`, run the JEPA canary, and measure
approve/deny — on real traffic, later. No code change is required to switch stages; it is a
flag + policy selection via `runtime_config.py`. Defaults are LEGACY/PARITY; nothing here
changes production behaviour until an operator opts in.

## A. Production SHADOW under REVIEWED

Records the REVIEWED flip candidate in parallel while **legacy still decides and executes**.

```python
from agentic.agentic_framework.trust.runtime_config import build_shadow_gateway
gw = build_shadow_gateway(mcp_client=my_client,
                          audit_db_path="/var/data/governance_audit.db")
# equivalently: SafeMCPGateway(..., trust_mode="shadow", trust_authority_policy="reviewed",
#                              audit_store=GovernanceAuditStore("/var/data/governance_audit.db"))
```

Env-driven (operational entry point):

```bash
export TRUST_MODE=shadow
export TRUST_AUTHORITY_POLICY=reviewed
export GOVERNANCE_AUDIT_DB=/var/data/governance_audit.db
# export TRUST_OUTCOME_REPUTATION=1   # optional: also shadow the reputation observable
```
```python
from agentic.agentic_framework.trust.runtime_config import gateway_from_env
gw = gateway_from_env(mcp_client=my_client)
```

Invariants (covered by the smoke test): legacy still executes; `trust_shadow` is persisted;
the REVIEWED-policy parallel decision is recorded; the audit hash chain validates.

## B. Collect `trust_shadow` data → flip-readiness report

`shadow_report` reads the durable store directly (read-only). The flip gate is its exit code.

```bash
make trust-shadow-report DB=/var/data/governance_audit.db
# or:
PYTHONPATH="$(pwd)" python3 -m experiments.trust_signal.shadow_report \
    --store /var/data/governance_audit.db --entropy --fail-on-unintended
```

Expected output shape:

```
## Verdict: READY FOR REVIEW          # unsafe_relaxation=0 and unintended=0  → exit 0
# or
## Verdict: NOT READY TO FLIP         # unsafe_relaxation>0 (or unintended>0 with the flag) → exit 1
```

Thresholds to clear before considering a flip: `unsafe_relaxation == 0`, `unintended == 0`,
intended demotions reviewed, hash chain valid (see `TRUST_CORE_FLIP_READINESS.md`).

## C. JEPA canary flip (opt-in, NOT default)

Only after §B is clean over real traffic + sign-offs. Route **only the canary cohort** here.

```python
from agentic.agentic_framework.trust.runtime_config import build_canary_gateway
canary = build_canary_gateway(mcp_client=my_client,
                              audit_db_path="/var/data/governance_audit_canary.db")
```
```bash
export TRUST_MODE=trust_core
export TRUST_AUTHORITY_POLICY=reviewed
export GOVERNANCE_AUDIT_DB=/var/data/governance_audit_canary.db
```

What changes: a **JEPA-sole BLOCK becomes a human CONFIRM** (deny → ESCALATE, approve →
ALLOWED with `human_confirmed=True`). Forbidden / domain / shadow blocks remain blocks; no
silent ALLOW. Rollback = set `TRUST_MODE=shadow` (or `legacy`, or
`TRUST_AUTHORITY_POLICY=parity`) — instant, no migration. See `TRUST_CORE_CANARY_RUNBOOK.md`.

## D. Measure approve/deny on the canary

```bash
make trust-canary-report DB=/var/data/governance_audit_canary.db
# or:
PYTHONPATH="$(pwd)" python3 -m experiments.trust_signal.canary_report \
    --store /var/data/governance_audit_canary.db
```

Reports (from persisted audit data only): total JEPA-sole confirmations, approved / denied /
timeout counts, approval & denial rates, average confirmation latency, mismatch-class counts,
and `unsafe_relaxation` / `unintended`. Exits non-zero on any `unsafe_relaxation`.

> Signal-shift note: in SHADOW the JEPA demotions read as `intended` (legacy=block,
> trust=confirm); under TRUST_CORE the legacy decision *is* the relaxed CONFIRM, so they read
> as `match` — the live signal is the **approve/deny rate**, which `canary_report` surfaces.

## What still requires real production traffic

Everything here is config + scripts + tests; the **decisions** (flip / promote) need real
volume: a representative SHADOW window with `unsafe_relaxation==0 / unintended==0`, then a
canary window whose approve/deny rate informs whether JEPA stays confirm-only, is demoted
further, or re-promoted. No synthetic corpus substitutes for that.
