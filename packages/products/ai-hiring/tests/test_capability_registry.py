"""Capability registry / ontology-service tests."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.domain.enums import AuditEventType
from ugence_ai_hiring.errors import CapabilityNotFoundError, OntologyError, VersionConflictError
from ugence_ai_hiring.ontology import Capability, CapabilityStatus, EvidenceType

from .conftest import AUTHOR, make_capability, publish_capability


def test_publish_capability(platform):
    cap = publish_capability(platform, "cap.python")
    assert cap.status is CapabilityStatus.PUBLISHED
    assert platform.ontology_service.get("cap.python").name == "Python"


def test_publish_audited(platform):
    publish_capability(platform, "cap.python")
    assert any(e.event_type is AuditEventType.CAPABILITY_PUBLISHED
               for e in platform.audit_repo.all())


def test_hierarchy_parent_child(platform):
    publish_capability(platform, "cap.se", name="Software Engineering",
                       allowed_evidence_types=(EvidenceType.CODING_TEST,),
                       required_evidence_types=(), minimum_evidence_count=0)
    publish_capability(platform, "cap.python", name="Python", parent_id="cap.se")
    graph = platform.ontology_service.graph()
    assert "cap.se" in graph.ancestors("cap.python")
    assert "cap.python" in graph.descendants("cap.se")


def test_publish_child_before_parent_fails(platform):
    with pytest.raises(CapabilityNotFoundError):
        platform.ontology_service.publish(
            make_capability("cap.python", parent_id="cap.missing"), actor_id=AUTHOR)


def test_lookup_and_list(platform):
    publish_capability(platform, "cap.a", name="A")
    publish_capability(platform, "cap.b", name="B")
    ids = {c.capability_id for c in platform.ontology_service.list()}
    assert {"cap.a", "cap.b"} <= ids


def test_by_status(platform):
    publish_capability(platform, "cap.a", name="A")
    published = platform.ontology_service.by_status(CapabilityStatus.PUBLISHED)
    assert any(c.capability_id == "cap.a" for c in published)


def test_retire_capability(platform):
    publish_capability(platform, "cap.a", name="A")
    retired = platform.ontology_service.retire("cap.a", actor_id=AUTHOR)
    assert retired.status is CapabilityStatus.RETIRED
    assert retired.version == 2
    assert any(e.event_type is AuditEventType.CAPABILITY_RETIRED
               for e in platform.audit_repo.all())


def test_supersede_capability(platform):
    publish_capability(platform, "cap.old", name="Old")
    new = make_capability("cap.new", name="New")
    stored = platform.ontology_service.supersede("cap.old", new, actor_id=AUTHOR)
    assert stored.capability_id == "cap.new"
    assert stored.supersedes == "cap.old"
    assert platform.ontology_service.get("cap.old").status is CapabilityStatus.SUPERSEDED


def test_capabilities_are_immutable(platform):
    publish_capability(platform, "cap.a", name="A")
    # re-adding the same id+version is a conflict (immutability)
    with pytest.raises(VersionConflictError):
        platform.ontology_repo.add(platform.ontology_service.get("cap.a"))


def test_get_missing_capability_raises(platform):
    with pytest.raises(CapabilityNotFoundError):
        platform.ontology_service.get("cap.ghost")
