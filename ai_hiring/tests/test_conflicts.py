"""Conflict-representation tests (represent, never resolve)."""

from __future__ import annotations

import pytest

from ai_hiring.rubrics import Conflict, ConflictSeverity, ConflictSource, ConflictStatus


def _sources():
    return (ConflictSource(source_ref="resume", claim="Senior"),
            ConflictSource(source_ref="interview", claim="Junior"))


def test_create_conflict():
    c = Conflict(conflict_id="cf1", capability_id="cap.python", sources=_sources(),
                 severity=ConflictSeverity.HIGH, reason="Seniority disagreement")
    assert c.status is ConflictStatus.OPEN
    assert len(c.sources) == 2


def test_requires_two_sources():
    with pytest.raises(Exception):
        Conflict(conflict_id="cf1", capability_id="cap.python",
                 sources=(ConflictSource(source_ref="resume", claim="Senior"),),
                 severity=ConflictSeverity.LOW, reason="x")


def test_no_resolved_status():
    # the contract deliberately has no RESOLVED state — conflicts are recorded
    assert "RESOLVED" not in {s.value for s in ConflictStatus}
    assert {s.value for s in ConflictStatus} == {"OPEN", "ACKNOWLEDGED", "ESCALATED"}


def test_severity_levels():
    assert {s.value for s in ConflictSeverity} == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def test_reason_required():
    with pytest.raises(Exception):
        Conflict(conflict_id="cf1", capability_id="cap.python", sources=_sources(),
                 severity=ConflictSeverity.LOW, reason="  ")


def test_serialization_round_trip():
    c = Conflict(conflict_id="cf1", capability_id="cap.python", sources=_sources(),
                 severity=ConflictSeverity.CRITICAL, reason="contradiction",
                 status=ConflictStatus.ESCALATED)
    data = c.model_dump()
    restored = Conflict(**data)
    assert restored == c
    assert restored.severity is ConflictSeverity.CRITICAL


def test_conflict_is_frozen():
    from pydantic import ValidationError
    c = Conflict(conflict_id="cf1", capability_id="cap.python", sources=_sources(),
                 severity=ConflictSeverity.LOW, reason="x")
    with pytest.raises(ValidationError):
        c.status = ConflictStatus.ACKNOWLEDGED
