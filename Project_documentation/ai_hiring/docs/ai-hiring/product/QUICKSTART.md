# Quickstart

Everything below runs **in-memory and deterministically**. Nothing here contacts a
production system, sends a message, or writes to an external record.

## 1. Run the canonical demo (CLI)

```bash
python -m ai_hiring.product demo
```

You'll see five synthetic cases exercising the governed branches:

```
Canonical demo — product 0.6.0 (deterministic simulation)
  demo-advance   stage=reconciliation  rec=READY_FOR_HUMAN_REVIEW  decision=ADVANCE  auth=AUTHORIZED  proposal=RECONCILED           recon=MATCHED
  demo-hold      stage=reconciliation  rec=READY_FOR_HUMAN_REVIEW  decision=HOLD     auth=AUTHORIZED  proposal=RECONCILED           recon=MATCHED
  demo-reject    stage=reconciliation  rec=READY_FOR_HUMAN_REVIEW  decision=REJECT   auth=AUTHORIZED  proposal=RECONCILED           recon=MATCHED
  demo-review    stage=recommendation  rec=ASSERTION_REVIEW_REQUIRED  decision=-     auth=-           proposal=-                    recon=-
  demo-denied    stage=authorization   rec=READY_FOR_HUMAN_REVIEW  decision=ADVANCE  auth=DENIED      proposal=AUTHORIZATION_DENIED  recon=-
```

## 2. Print an accountability report

```bash
python -m ai_hiring.product report            # redacted (default)
python -m ai_hiring.product report --no-redact # un-redacted identifiers
python -m ai_hiring.product --json report      # machine-readable
```

The report reconstructs one advanced case end to end — recommendation, TAP claim
evaluations, human decision, ActionGate authorization, execution, reconciliation —
and reports audit-chain integrity.

## 3. Use the Python API

```python
import ai_hiring.product as P

# Compose a deterministic product (dev wiring with your own config).
product = P.build_dev_platform(P.load_config({"tenant": "acme", "redact_pii": True}))

# Drive one governed case end to end.
run = product.run_case(P.CaseSpec(case_id="candidate-42"))
print(run.decision_outcome, run.reconciliation_outcome)   # ADVANCE MATCHED

# Build the accountable record.
report = P.build_accountability_report(product, run.action_proposal_id)
print(report.render_text())
assert report.integrity["reconstructed"] is True
```

## 4. Shape a case

`CaseSpec` describes one synthetic case. Analysis-only attributes (`group_label`,
`protected_attributes`) are **never** passed into the operational pipeline — that
blindness is a validated leakage guarantee, not a convention. Common fields:

| Field | Meaning |
|---|---|
| `case_id` | Unique id for the case's records |
| `provided_evidence` | Evidence types supplied (incomplete → no recommendation) |
| `assertion_coverage` | TAP coverage; `UNSUPPORTED` → stays in review |
| `decision_intent` | Human intent (`ADVANCE`/`HOLD`/`REJECT`); `None` → no decision |
| `action_type` | Proposed action; `None` → no action |
| `action_denied` | Action types ActionGate denies |
| `exec_flags` | Execution-adapter behavior (e.g. observed-parameter mismatch) |

See [`API_REFERENCE.md`](API_REFERENCE.md) and [`CONFIG_REFERENCE.md`](CONFIG_REFERENCE.md).
