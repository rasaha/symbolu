# Code Governance Pilot Runbook

> A concrete operator runbook for a **read-only, shadow-only** pilot. Every step is
> read-only: the operator has no GitHub write path and execution stays `DISABLED`.
> Credentials are supplied at runtime and never persisted.

## 1. Installation

```
pip install ugence-code-governance   # provides the `cg-pilot` console entry point
cg-pilot version                      # {"version": "0.4.0", "execution_status": "DISABLED"}
```

Container (optional): build from `examples/deployment/Dockerfile` (non-root, no
baked credentials, mounts `/data/cg-pilot`).

## 2. Configuration

Copy `examples/deployment/pilot_deployment.example.json`, edit the tenant,
repository allowlist (explicit repos only), branch allowlist, durable store path,
adapter registry ref, reviewer role allowlist, evaluation/concurrency bounds, and
pilot window. **Never** put a credential value in the config — only a
`credential_references` entry naming an env var.

```
cg-pilot validate --config pilot_deployment.json
```

## 3. GitHub read-only credential setup

Provision a **read-only** GitHub token/app with only `metadata:read`,
`pull_requests:read`, `checks:read`, `statuses:read`. Never grant a `*:write`
permission. Export it as the referenced env var:

```
export CG_PILOT_GITHUB_READONLY_TOKEN=<read-only-token>
```

The operator resolves this env var only immediately before a read; it is never
stored, logged, or fingerprinted.

## 4. Preflight

Run the security + readiness preflight before starting:

```python
op = open_pilot_operator(config, service=svc, registry=registry, profile=profile,
                         credential_resolver=env_resolver)
result = op.preflight(); assert result.passed
```

`cg-pilot security-scan` runs the static read-only boundary scan independently.

## 5. Start / run

```python
op.start(now)                      # DRAFT -> READY -> ACTIVE (explicit)
op.run_once(revision_id, adapters, collection_time=now, evaluation_time=now)
op.run_batch(items, collection_time=now, evaluation_time=now)
```

The scheduler selects only allowlisted, known workflow revisions (never an
org-wide scan). Batch/count/concurrency bounds are enforced.

## 6. Pause / resume

```python
op.pause(now, reason="maintenance")   # no collection occurs while paused
op.resume(now)                        # explicit
```

## 7. Kill switch

```python
op.activate_kill_switch(now, reason="incident")   # no new adapter call / evaluation
op.clear_kill_switch(now)                          # does NOT restart the pilot
```

Kill-switch activation needs no GitHub access and is durable.

## 8. Review queue + feedback

```python
for item in op.review_queue(): ...          # ESCALATE / policy-routed items
op.record_feedback(feedback, at=now)        # curated, audit-only, never changes policy
```

Assignment respects the reviewer role allowlist and is **not** approval.

## 9. Metrics / inspect / health

```python
op.metrics().snapshot(); op.inspect(); op.health(); op.readiness()
```

## 10. Integrity verification

```python
svc.reconstruct_chain_from_store(tenant, revision_id)   # COMPLETE
bundle = svc.export_governance_audit_bundle(tenant, revision_id)
CodeGovernanceService.verify_governance_audit_bundle(bundle)   # offline
```

## 11. Stop / abort / closeout

```python
op.abort(now, reason="operator_stop")   # any active state -> ABORTED
summary = op.closeout(now)              # STOPPING -> COMPLETED, final report + metrics
```

Closeout stops new evaluations, computes final metrics, exports + verifies the
report, inventories unresolved queue items + missing feedback, records limitations,
and reports execution disabled. Closeout does **not** enable enforcement.

## 12. Restart / recovery

On process restart, reopen the store and recover — no GitHub call is made and an
ACTIVE pilot is never auto-resumed:

```python
recovery = recover_pilot(store, config)     # reports RECOVERED_* status
op.confirm_recovery(recovery, now)          # EXPLICIT operator confirmation
```

A config fingerprint mismatch reports `CONFIGURATION_MISMATCH` and blocks resume.

## 13. Incident response

Activate the kill switch, then `record_security_event(...)`; a critical event
(write-permission detected, credential leak, boundary violation, store integrity
failure, unexpected execution symbol) aborts the pilot. Nothing enables execution.

## 14. Credential rotation

Rotate the external read-only token and update the referenced env var. No durable
record changes (credentials were never stored). Re-run preflight.

## 15. Data backup / closeout artifacts

The durable store file (`durable_store_path`) is the audit substrate; back it up
per the configured retention category. Export the pilot report and governance audit
bundle for offline verification and archival.

## Optional live smoke

```
UGENCE_LIVE_GITHUB_PILOT=1 UGENCE_LIVE_REPO=owner/repo UGENCE_LIVE_PR=123 \
  UGENCE_LIVE_BRANCH=main UGENCE_LIVE_STORE_PATH=/data/cg-pilot/gov.db \
  UGENCE_LIVE_CREDENTIAL_REF=github-readonly pytest -k live_github_pilot_smoke
```

Skipped by default. GET/HEAD only, prints no credential, verifies exact repo + head
SHA, persists normalized facts only, one shadow evaluation, execution disabled.
