# MVP 1E Limitations

> MVP 1E is a bounded **operationalization** phase: it makes the 1D read-only pilot
> safely deployable and operable against a narrowly allowlisted GitHub environment.
> It does not turn Code Governance into an enforcement system.

## Not production enforcement readiness

A pilot that meets its configured thresholds is not proof of perfect safety and
does not enable enforcement. Metrics are descriptive; reviewer-derived error
categories remain *possible* until ground truth is independently established.

## Explicitly out of scope

No execution · no GitHub write operations (approve/merge/close/label/comment/
assign/modify/deploy) · no GitHub write permissions · no merge credential · no
GitHub execution provider · no `ProviderKind` · no `reserve_once` · no authoritative
authorization-consumption ledger · no deployment/merge enforcement · no external
database · no broad multi-tenant SaaS control plane · no automatic policy learning ·
reviewer feedback never changes policy automatically · no fabricated live-pilot
results when credentials/environment are unavailable.

## Evidence classification

This build is `IMPLEMENTED` + `OFFLINE_VERIFIED`. It is **not** `LIVE_SMOKE_VERIFIED`
and no `PILOT_DATA_COLLECTED`. No live customer pilot occurred, no reviewer
agreement was measured against real reviewers, no false-positive rates were
established, and GitHub permissions were not verified against a real installation.

## Authority boundary preserved

The operator coordinates; it owns no authority. Adapters supply conditions only.
The DecisionRecord remains the binding decision; ActionGate authorization is still
required before clearance; the canonical Action Clearance package is unmodified. The
only changed product boundary is `products/code-governance/`.
