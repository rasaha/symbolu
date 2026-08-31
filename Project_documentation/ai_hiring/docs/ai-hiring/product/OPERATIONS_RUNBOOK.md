# Operations Runbook

Operational procedures for the AI Hiring **controlled-pilot package**. Because the
package runs in-memory and deterministically with no production effect, "operations"
here means verification, demonstration, evidence-gathering, and diagnosis — not
incident response against live systems (there are none).

## Health / readiness check

```bash
python -m ai_hiring.product verify
```
`RESULT: PASS` confirms deterministic mode, no production certification, and a
successful demo run. A non-zero exit code indicates a broken install — reinstall per
[`INSTALL.md`](INSTALL.md).

## Produce an accountability record for a case

```bash
python -m ai_hiring.product --json report > report.json     # machine-readable
python -m ai_hiring.product report                          # human-readable, redacted
```
For a specific case, use the API:
```python
import ai_hiring.product as P
prod = P.build_dev_platform(P.load_config({"tenant": "acme"}))
run = prod.run_case(P.CaseSpec(case_id="case-123"))
print(P.build_accountability_report(prod, run.action_proposal_id).render_text())
```

## Runbook: recommendation stuck in review

**Symptom:** `recommendation_status == "ASSERTION_REVIEW_REQUIRED"`, no decision.
**Cause (by design):** a material claim was `UNSUPPORTED` at TAP evaluation. The
lifecycle correctly refuses to advance to human decision until review resolves it.
**Action:** inspect the claims in the accountability report (`claims[*].assertion_outcome`).
This is a fail-safe stop, not a fault.

## Runbook: authorization denied

**Symptom:** `authorization_outcome == "DENIED"`, `proposal_status ==
"AUTHORIZATION_DENIED"`, no execution.
**Cause (by design):** ActionGate denied the proposed action.
**Action:** confirmed correct — no execution occurred. Review the authorization entry
(`authorization.outcome`) in the report.

## Runbook: reconciliation mismatch → compensation required

**Symptom:** `reconciliation_outcome in {MISMATCHED, DUPLICATE_EXECUTION}`,
`proposal_status == "COMPENSATION_REQUIRED"`.
**Cause:** what the (simulated) external system did differs from what was authorized.
**Action:** the mismatch is surfaced, not hidden; the chain remains reconstructable
and a compensation entry is required. Inspect `reconciliation.mismatched_count` and
the compensation entries. **No silent success is ever reported.**

## Runbook: audit-chain integrity failure

**Symptom:** report `integrity.hiring_hash_chain_valid == False` or
`reconstructed == False` with `issues`.
**Cause:** a tampered or broken hiring-domain audit chain (the reconstruction detects
altered hashes, broken links, or inconsistent tenant scope).
**Action:** treat as an integrity incident for that record — the platform is
reporting exactly what it is designed to detect. Do not trust that record's outcome.

## Runbook: cross-tenant access attempt

**Symptom:** `CrossTenantHiringAccessError` on reconstruct.
**Cause (by design):** an actor tried to reconstruct a record outside its tenant.
**Action:** confirmed correct isolation — the access was refused.

## Log / evidence collection

The authoritative record for any case is its accountability report (human + JSON).
Collect `--json report` output alongside the case's `CaseRun` fields for a complete,
de-identified evidence bundle.

## Escalation boundary

This package cannot cause a production incident (no production effect exists). Any
requirement involving real hiring actions, communications, or data egress is **out of
scope** — see [`DEPLOYMENT.md`](DEPLOYMENT.md) and
[`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md).
