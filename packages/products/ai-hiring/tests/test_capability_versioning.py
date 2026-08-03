"""Capability versioning + immutability tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ugence_ai_hiring.errors import CapabilityCycleError, VersionConflictError
from ugence_ai_hiring.ontology import Capability, CapabilityStatus, EvidenceType, build_graph

from .conftest import AUTHOR, make_capability, publish_capability


def test_version_history_grows(platform):
    publish_capability(platform, "cap.a", name="A")
    platform.ontology_service.retire("cap.a", actor_id=AUTHOR)
    history = platform.ontology_service.history("cap.a")
    assert [c.version for c in history] == [1, 2]
    assert history[0].status is CapabilityStatus.PUBLISHED
    assert history[1].status is CapabilityStatus.RETIRED


def test_get_specific_version(platform):
    publish_capability(platform, "cap.a", name="A")
    platform.ontology_service.retire("cap.a", actor_id=AUTHOR)
    v1 = platform.ontology_service.get_version("cap.a", 1)
    assert v1.status is CapabilityStatus.PUBLISHED  # older version unchanged


def test_capability_is_frozen():
    cap = make_capability("cap.a", name="A")
    with pytest.raises(ValidationError):
        cap.name = "Renamed"  # frozen


def test_as_status_bumps_version():
    cap = make_capability("cap.a", name="A")
    v2 = cap.as_status(CapabilityStatus.RETIRED)
    assert v2.version == 2 and cap.version == 1


def test_supersede_creates_new_immutable_record(platform):
    publish_capability(platform, "cap.old", name="Old")
    platform.ontology_service.supersede("cap.old", make_capability("cap.new", name="New"),
                                        actor_id=AUTHOR)
    # old retained at v1 (published) and v2 (superseded)
    versions = [c.version for c in platform.ontology_service.history("cap.old")]
    assert versions == [1, 2]


def test_cycle_detection_in_graph():
    a = make_capability("a", name="A", parent_id="b")
    b = make_capability("b", name="B", parent_id="a")
    with pytest.raises(CapabilityCycleError):
        build_graph((a, b)).validate()


def test_self_parent_rejected():
    with pytest.raises(Exception):
        Capability(capability_id="x", name="X", parent_id="x")


def test_minimum_evidence_count_nonnegative():
    with pytest.raises(Exception):
        make_capability("x", name="X", minimum_evidence_count=-1)


def test_required_must_be_subset_of_allowed():
    with pytest.raises(Exception):
        Capability(capability_id="x", name="X",
                   allowed_evidence_types=(EvidenceType.GITHUB,),
                   required_evidence_types=(EvidenceType.CODING_TEST,))
