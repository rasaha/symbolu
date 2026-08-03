"""Job-relevance and prohibited-field quarantine tests."""

from __future__ import annotations

from ugence_ai_hiring.normalization.models import (
    EvidenceFormat,
    QuarantineCategory,
    RawSubmission,
)
from ugence_ai_hiring.normalization.quarantine import (
    DEFAULT_POLICY,
    QuarantineEngine,
    QuarantinePolicy,
)

SERVICE_ID = "svc-ats"


def _structured(fields: dict[str, str], **kw) -> RawSubmission:
    base = dict(
        candidate_id="c1", role_id="r1", assessment_item_id="a1",
        declared_format=EvidenceFormat.STRUCTURED_RESPONSE, uploader=SERVICE_ID,
    )
    base.update(kw)
    return RawSubmission(fields=fields, **base)


# --- engine-level ----------------------------------------------------------
def test_prohibited_fields_are_quarantined():
    engine = QuarantineEngine(DEFAULT_POLICY)
    result = engine.apply({"answer": "good", "age": "34", "gender": "f"})
    assert set(result.clean_fields) == {"answer"}
    cats = {f.field_name: f.category for f in result.quarantined}
    assert cats["age"] is QuarantineCategory.PROHIBITED
    assert cats["gender"] is QuarantineCategory.PROHIBITED


def test_prohibited_aliases_detected():
    engine = QuarantineEngine(DEFAULT_POLICY)
    result = engine.apply({"DOB": "1990-01-01", "Nationality": "X", "response": "ok"})
    quarantined = {f.field_name for f in result.quarantined}
    assert "DOB" in quarantined and "Nationality" in quarantined
    assert set(result.clean_fields) == {"response"}


def test_unknown_fields_quarantined_when_allowlist_configured():
    policy = QuarantinePolicy(job_relevant_allowlist=frozenset({"answer", "approach"}))
    engine = QuarantineEngine(policy)
    result = engine.apply({"answer": "a", "mystery": "b"})
    assert set(result.clean_fields) == {"answer"}
    assert result.quarantined[0].field_name == "mystery"
    assert result.quarantined[0].category is QuarantineCategory.UNKNOWN


def test_no_allowlist_keeps_nonprohibited_fields():
    engine = QuarantineEngine(DEFAULT_POLICY)
    result = engine.apply({"a": "1", "b": "2"})
    assert set(result.clean_fields) == {"a", "b"}
    assert result.quarantined == ()


# --- pipeline / service integration ---------------------------------------
def test_quarantined_fields_never_reach_normalized_evidence(platform):
    sub = _structured({"answer": "used recursion", "race": "redacted", "age": "40"})
    ing = platform.evidence_ingestion_service.ingest(sub)
    # prohibited fields absent from normalized text, chunks, and index
    assert "race" not in ing.normalized_text
    assert "age=" not in ing.normalized_text
    assert "answer=used recursion" in ing.normalized_text
    entries = platform.search_service.by_evidence(ing.evidence_id)
    for e in entries:
        assert "race" not in e.text and "40" not in e.text


def test_quarantine_preserved_separately_and_audited(platform):
    sub = _structured({"answer": "ok", "gender": "x"})
    ing = platform.evidence_ingestion_service.ingest(sub)
    # values are never deleted — stored in the quarantine record
    assert ing.quarantine is not None
    stored = platform.quarantine_repo.for_evidence(ing.evidence_id, ing.version)
    assert stored is not None
    gender = [f for f in stored.fields if f.field_name == "gender"][0]
    assert gender.category is QuarantineCategory.PROHIBITED
    assert gender.value == "x"  # preserved, never deleted
    # a quarantine audit event exists
    from ugence_ai_hiring.domain.enums import AuditEventType

    events = platform.audit_service.history(ing.evidence_id)
    assert any(e.event_type is AuditEventType.EVIDENCE_PII_QUARANTINED for e in events)


def test_unstructured_text_has_no_field_quarantine(platform):
    sub = RawSubmission.from_text(
        "free text answer mentioning age informally",
        candidate_id="c1", role_id="r1", assessment_item_id="a1",
        declared_format=EvidenceFormat.TEXT, uploader=SERVICE_ID,
    )
    ing = platform.evidence_ingestion_service.ingest(sub)
    # no discrete fields -> nothing quarantined; semantic text is not altered
    assert ing.quarantine is None
    assert "age" in ing.normalized_text
