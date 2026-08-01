"""H5 — trusted-context provider failure modes must never silently neutralize."""

from __future__ import annotations

from composite_threat_detector import (
    BY_CASE, DIGITAL_ONTOLOGY, FailingProvider, FixtureProvider, ProviderRegistry,
    SequenceRiskAnalyzer, signals,
)

EXFIL = "DATA_EXFILTRATION_ASSEMBLY"
TENANT = "acme"
WF = "wf-9"


def _events(claim):
    a = "agent://etl/1"

    def e(op, seq, eid, args=None, **kw):
        d = {"tenant_id": TENANT, "workflow_id": WF, "actor": a,
             "correlation_id": "s", "sequence_id": seq, "event_id": eid,
             "operation": op, "credential_scope": {"principal": a},
             "arguments": args or {}}
        d.update(kw)
        return d
    return [e("SECRET_READ", "s:1", "1"),
            e("DB_MUTATION", "s:2", "2", target_resource=["arn:aws:rds:::customers"]),
            e("NET_EXPOSE", "s:3", "3", {"cidr": "203.0.113.4/32"}, approval=claim)]


def _base_record(**over):
    r = {"record_id": "REC-1", "tag": "compliance_export", "tenant": TENANT,
         "workflow": WF, "actor": "*", "target_family": "*", "operations": "*",
         "destinations": "*", "environment": "*", "tools": "*",
         "approver_identity": "user://dpo", "approver_authority": "dpo"}
    r.update(over)
    return r


def _run(records=None, providers=None):
    claim = {"tag": "compliance_export", "approver": "u", "ticket": "REC-1"}
    if providers is None:
        providers = ProviderRegistry(providers=(
            FixtureProvider("fx", "1.0.0", records or []),))
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,), providers=providers)
    out = []
    for ev in _events(claim):
        out.extend(az.observe(ev))
    escalated = any(f.signal == signals.ESCALATE and f.recipe_id == EXFIL for f in out)
    key = out[0].assembly_key if out else None
    standing = az.standing_findings(TENANT, key) if key else []
    exfil = next((f for f in standing if f.recipe_id == EXFIL), None)
    return escalated, exfil


def _status(exfil):
    return exfil.purpose["purpose_consistency_status"] if exfil else None


# control: valid verified authorization DOES neutralize --------------------
def test_valid_authorization_neutralizes():
    esc, exfil = _run([_base_record()])
    assert esc is False
    assert _status(exfil) == "VERIFIED_CONSISTENT"


# each failure mode must NOT neutralize ------------------------------------
def test_provider_unavailable():
    esc, exfil = _run(providers=ProviderRegistry(providers=(FailingProvider(),)))
    assert esc is True
    assert _status(exfil) == "PROVIDER_UNAVAILABLE"
    assert exfil.purpose["provider_unavailable"] is True


def test_revoked():
    esc, exfil = _run([_base_record(revoked=True)])
    assert esc is True and _status(exfil) == "REVOKED"


def test_superseded():
    esc, exfil = _run([_base_record(superseded_by="REC-2")])
    assert esc is True and _status(exfil) == "SUPERSEDED"


def test_stale():
    esc, exfil = _run([_base_record(stale=True)])
    assert esc is True and _status(exfil) == "STALE"


def test_expired_window():
    esc, exfil = _run([_base_record(expiry=1.0)])   # now (position) > 1.0
    assert esc is True and _status(exfil) == "EXPIRED"


def test_invalid_signature():
    esc, exfil = _run([_base_record(signature="forged")])
    assert esc is True and _status(exfil) == "INVALID"


def test_version_mismatch():
    esc, exfil = _run([_base_record(provider_version_required="9.9.9")])
    assert esc is True and _status(exfil) == "INVALID"


def test_unverifiable_source():
    esc, exfil = _run([_base_record(unverifiable=True)])
    assert esc is True and _status(exfil) == "INVALID"


def test_modified_after_activity():
    esc, exfil = _run([_base_record(modified_at=2.5)])  # > activity_start (pos 1)
    assert esc is True and _status(exfil) == "INVALID"


def test_delayed_ingestion_not_yet_available():
    esc, exfil = _run([_base_record(available_from=1000.0)])
    assert esc is True and _status(exfil) in ("UNVERIFIED",)


def test_wrong_tenant_never_matches():
    esc, exfil = _run([_base_record(tenant="other")])
    assert esc is True and _status(exfil) == "UNVERIFIED"


def test_wrong_scope_reports_field():
    esc, exfil = _run([_base_record(workflow="OTHER-WF")])
    assert esc is True
    assert "workflow" in exfil.purpose["scope_mismatch_fields"]


def test_missing_authority():
    esc, exfil = _run([_base_record(approver_authority="")])
    assert esc is True and _status(exfil) == "UNVERIFIED"


def test_conflicting_evidence_is_ambiguous():
    esc, exfil = _run([_base_record(), _base_record(revoked=True)])
    assert esc is True and _status(exfil) == "AMBIGUOUS"


def test_duplicate_authorization_ids_ambiguous():
    esc, exfil = _run([_base_record(), _base_record()])  # same record_id twice
    assert esc is True and _status(exfil) == "AMBIGUOUS"
