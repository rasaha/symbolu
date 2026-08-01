"""Runnable scenarios for the sequence-risk analyzer.

These are illustrations, not a benchmark. Numeric evaluation lives in ``eval/``.

* ``firearm_events`` — the original prompt's synthetic illustration (grouped by
  correlation, since the toy events carry no enterprise entities).
* ``exfiltration_events`` — the digital target: within one workflow, each action
  independently clears the per-action ActionGate, yet together they assemble a
  data-exfiltration capability.
* ``benign_migration_events`` — a look-alike: same nouns, but the outbound path is
  an approved/internal sink, so the exfil-grade EGRESS_PATH fragment never forms.
* ``approved_export_events`` — external egress but under a valid, scope-matched
  approval, so the escalation is qualified (NEUTRALIZED).
"""

from __future__ import annotations

from composite_threat_detector import BY_CASE, BY_CORRELATION, SequenceRiskAnalyzer

# --- physical firearm illustration ---------------------------------------
firearm_events = [
    {"tenant_id": "synthetic", "correlation_id": "buyer-42",
     "sequence_id": "buyer-42:0001", "event_id": "a1", "item": "steel_rod"},
    {"tenant_id": "synthetic", "correlation_id": "buyer-42",
     "sequence_id": "buyer-42:0002", "event_id": "a2", "item": "steel_piston"},
    {"tenant_id": "synthetic", "correlation_id": "buyer-42",
     "sequence_id": "buyer-42:0003", "event_id": "a3", "item": "trigger_mechanism"},
    {"tenant_id": "synthetic", "correlation_id": "buyer-42",
     "sequence_id": "buyer-42:0004", "event_id": "a4", "item": "ball_bearings"},
]


def _digital(op, seq, eid, args, **extra):
    e = {"tenant_id": "acme", "workflow_id": "wf-9", "actor": "agent://etl/1",
         "correlation_id": "sess-9", "sequence_id": seq, "event_id": eid,
         "operation": op, "credential_scope": {"principal": "agent://etl/1"},
         "arguments": args}
    e.update(extra)
    return e


# Each of these clears the per-action gate on its own; the composite is the risk.
exfiltration_events = [
    _digital("SECRET_READ", "sess-9:0001", "b1", {"enumerate": True}),
    _digital("DB_MUTATION", "sess-9:0002", "b2", {"bounded": True},
             target_resource=["arn:aws:rds:::customers"]),
    _digital("MONITORING_DISABLE", "sess-9:0003", "b3", {"scope": "one-alert"}),
    _digital("NET_EXPOSE", "sess-9:0004", "b4", {"cidr": "203.0.113.4/32"}),
]

# Look-alike: identical fragments EXCEPT the outbound path is an approved sink,
# so EGRESS_PATH never forms → fragment-count alone does not escalate.
benign_migration_events = [
    _digital("SECRET_READ", "wf-mig:0001", "c1", {"enumerate": True},
             workflow_id="wf-mig"),
    _digital("DB_MUTATION", "wf-mig:0002", "c2", {"bounded": True},
             workflow_id="wf-mig", target_resource=["arn:aws:rds:::customers"]),
    _digital("NET_EXPOSE", "wf-mig:0003", "c3",
             {"cidr": "10.0.0.5/32", "sink_approved": True}, workflow_id="wf-mig"),
]

# External egress but under a valid, scope-matched approval → NEUTRALIZED.
approved_export_events = [
    _digital("SECRET_READ", "wf-exp:0001", "d1", {"enumerate": True},
             workflow_id="wf-exp"),
    _digital("DB_MUTATION", "wf-exp:0002", "d2", {"bounded": True},
             workflow_id="wf-exp", target_resource=["arn:aws:rds:::customers"]),
    _digital("NET_EXPOSE", "wf-exp:0003", "d3", {"cidr": "203.0.113.9/32"},
             workflow_id="wf-exp",
             approval={"tag": "compliance_export", "approver": "user://dpo",
                       "ticket": "CHG-771", "workflow_id": "wf-exp"}),
]


def run(ontology, events, specs=None):
    """Feed ``events`` through an analyzer; return (finding dicts, run report)."""
    if specs is None:
        specs = (BY_CORRELATION,) if ontology.ontology_id.startswith("ctd.physical") \
            else (BY_CASE,)
    az = SequenceRiskAnalyzer(ontology, specs=specs)
    emitted = []
    for ev in events:
        for f in az.observe(ev):
            emitted.append(f.to_dict())
    return emitted, az.report.to_dict()
