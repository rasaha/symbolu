"""H3 — durable audit store + restart/recovery (replay-based)."""

from __future__ import annotations

import os

from ugence_storygraph import (
    BY_CASE, DIGITAL_ONTOLOGY, DurableAuditLog, SequenceRiskAnalyzer, signals,
    recover_from_audit,
)
from ugence_storygraph.demos import scenarios


def _exfil(az):
    out = []
    for ev in scenarios.exfiltration_events:
        out.extend(az.observe(ev))
    return out


def test_durable_audit_is_append_only_and_tamper_evident(tmp_path):
    db = str(tmp_path / "audit.sqlite")
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,),
                              audit=DurableAuditLog(db))
    _exfil(az)
    assert az.audit.verify_chain() is True
    assert len(az.audit) > 0
    # append-only: UPDATE/DELETE are rejected by triggers
    import sqlite3
    conn = sqlite3.connect(db)
    for stmt in ("UPDATE audit_events SET kind='x'", "DELETE FROM audit_events"):
        try:
            conn.execute(stmt)
            raised = False
        except sqlite3.IntegrityError:
            raised = True
        except sqlite3.OperationalError:
            raised = True
        assert raised, stmt
    conn.close()


def test_restart_recovery_reproduces_findings_and_digests(tmp_path):
    db = str(tmp_path / "audit.sqlite")
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,),
                              audit=DurableAuditLog(db))
    live = _exfil(az)
    live_esc = sorted(f.finding_id for f in live if f.signal == signals.ESCALATE)
    az.audit.close()

    # "restart": reopen the durable log from disk, replay to recover state
    reopened = DurableAuditLog(db)
    recovered = recover_from_audit(reopened, DIGITAL_ONTOLOGY, specs=(BY_CASE,))
    # recovered standing findings match live escalations by digest
    akey = list(recovered.ledger._by_tenant["acme"].keys())[0]
    rec_esc = sorted(f.finding_id for f in recovered.standing_findings("acme", akey)
                     if f.signal == signals.ESCALATE)
    assert rec_esc == live_esc and rec_esc


def test_recovery_preserves_dedup_and_version_bindings(tmp_path):
    db = str(tmp_path / "audit.sqlite")
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,),
                              audit=DurableAuditLog(db))
    e = scenarios.exfiltration_events
    for ev in [e[0], e[0], e[1], e[2], e[3]]:   # duplicate e[0]
        az.observe(ev)
    dupes = az.report.duplicates_suppressed
    az.audit.close()

    recovered = recover_from_audit(DurableAuditLog(db), DIGITAL_ONTOLOGY, specs=(BY_CASE,))
    assert recovered.report.duplicates_suppressed == dupes >= 1
    akey = list(recovered.ledger._by_tenant["acme"].keys())[0]
    asm = recovered.ledger.get("acme", akey)
    assert "DATA_EXFILTRATION_ASSEMBLY" in asm.bound_recipe_versions


def test_raw_evidence_survives_after_reset_in_durable_store(tmp_path):
    db = str(tmp_path / "audit.sqlite")
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,),
                              audit=DurableAuditLog(db))
    _exfil(az)
    az.observe({"type": "reset", "tenant_id": "acme", "workflow_id": "wf-9",
                "correlation_id": "sess-9", "sequence_id": "r:1", "event_id": "rst"})
    kinds = {r.kind for r in az.audit.all()}
    assert "RAW_EVIDENCE" in kinds and "ASSEMBLY_RESET" in kinds
    assert az.audit.verify_chain() is True


def test_durable_schema_versioned(tmp_path):
    db = str(tmp_path / "audit.sqlite")
    store = DurableAuditLog(db)
    assert store.schema_version().startswith("ctd.audit/")
