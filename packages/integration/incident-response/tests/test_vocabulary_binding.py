"""Which published vocabulary the severity label was written against.

`VV-A` to `VV-E`, authorized by `PUB-2`. Two things make this package's case its own.

`VV-C` says no here: the binding is covered by the record digest and deliberately kept
out of the derived id, because an incident's identity is its tenant, subject, evidence
and instant, and the severity label never took part in it.

And `AE-3`'s restraint is sharpest here, because `SEV1` to `SEV4` *look* ranked. `LV-D`
ruled them opaque and unordered anyway, accepting that "every incident at or above SEV2"
is unanswerable in this repository. Naming the vocabulary does not smuggle the ordering
back: the binding says which taxonomy was in force, never what a member outranks.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib
import pickle

import pytest

import ugence_incident_response as pkg
from ugence_incident_response import (
    CONTRACT_VERSION,
    LEGACY_CONTRACT_VERSION,
    ContractViolation,
    IncidentRecord,
    VocabularyBinding,
    VocabularyBindingState,
    incident_id_for,
    vocabulary_binding_from_dict,
    vocabulary_binding_to_dict,
)

from _fixtures import (
    NEXT_SEVERITY_VOCABULARY,
    SEVERITY,
    SEVERITY_VOCABULARY,
    SUBJECT,
    T0,
    TENANT,
    audit_ref,
    incident,
    legacy_incident,
)

SRC = pathlib.Path(pkg.__file__).resolve().parent

#: The id and digest of the canonical fixture as the v1 code produced them, captured
#: from the released 0.1.0 projection. Pinned literally: a test that recomputes both
#: sides proves only that the code agrees with itself.
V1_INCIDENT_ID = "inc_d40a23c1711b5a349c6ea45c8bec7281"
V1_RECORD_DIGEST = "0732491f2cd2b81723d8be6970b99f411f82379c5f9f1ad4bc159c985f764bbd"


# --------------------------------------------------------------------------- #
# VV-C — in the digest, and out of the identity
# --------------------------------------------------------------------------- #
def test_the_binding_changes_the_digest_and_never_the_id():
    under_1 = incident()
    under_2 = incident(severity_vocabulary=NEXT_SEVERITY_VOCABULARY)

    assert under_1.incident_id == under_2.incident_id
    assert under_1.record_digest() != under_2.record_digest()


def test_the_derived_id_still_ignores_the_label_itself():
    """Which is why the vocabulary is absent from it: the binding follows the label."""

    assert incident(severity="sev-1").incident_id == incident(severity="sev-4").incident_id


def test_a_historical_incident_keeps_the_id_and_digest_it_was_recorded_with():
    """VV-B: digests taken under the historical version stay valid and are never
    recomputed under the new projection.

    No store ships here (D-4), so an incident's durability is its ``AuditReference``
    into somebody else's store — which is exactly why the v1 projection has to keep
    reproducing: the digests that outlive this package are held elsewhere.
    """

    old = legacy_incident()
    assert old.incident_id == V1_INCIDENT_ID
    assert old.record_digest() == V1_RECORD_DIGEST
    assert "record_version" not in old.to_dict()
    assert "severity_vocabulary" not in old.to_dict()


# --------------------------------------------------------------------------- #
# AE-3 and LV-D — naming a vocabulary does not smuggle back an ordering
# --------------------------------------------------------------------------- #
def test_the_binding_carries_no_ordering_and_the_record_gains_no_rank():
    """LV-D ruled severity opaque and unordered, and accepted the cost by name."""

    surface = {n for n in dir(incident()) if not n.startswith("_")}
    assert not surface & {"severity", "rank", "level", "escalate", "at_or_above",
                          "outranks", "compare_severity"}
    binding_fields = {f.name for f in dataclasses.fields(VocabularyBinding)}
    assert not binding_fields & {"ordering", "rank", "members", "order"}


# --------------------------------------------------------------------------- #
# VV-A — the type is this package's own
# --------------------------------------------------------------------------- #
def test_the_binding_is_this_packages_own_type():
    assert VocabularyBinding.__module__.startswith("ugence_incident_response")

    import ugence_governance_contracts

    assert not hasattr(ugence_governance_contracts, "VocabularyBinding")


# --------------------------------------------------------------------------- #
# PUB-2 — an authoritative reference, not a context-free version string
# --------------------------------------------------------------------------- #
def test_a_binding_names_one_specification_and_a_bare_version_is_insufficient():
    good = VocabularyBinding("incident-severity", "1.0.0", "sha256:" + "9f" * 32)
    assert good.to_dict() == {"vocabulary": "incident-severity", "version": "1.0.0",
                              "specification_digest": "sha256:" + "9f" * 32}

    for version, digest in (("1.0", "sha256:" + "9f" * 32),
                            ("v1.0.0", "sha256:" + "9f" * 32),
                            ("01.0.0", "sha256:" + "9f" * 32),
                            ("١.0.0", "sha256:" + "9f" * 32),
                            ("1.0.0", "1.0.0"),
                            ("1.0.0", "sha256:" + "9F" * 32),
                            ("1.0.0", "9f" * 32)):
        with pytest.raises(ContractViolation):
            VocabularyBinding("incident-severity", version, digest)


def test_a_moving_reference_is_refused_by_name():
    """By name, and with the reason that names it.

    Every moving spelling would also fail the MAJOR.MINOR.PATCH check, so the message
    is the only observable difference — and it is the part that matters, because VV-E
    refuses these spellings specifically rather than as malformed versions.
    """

    for moving in ("latest", "current", "HEAD", "*"):
        with pytest.raises(ContractViolation, match="whatever is current"):
            VocabularyBinding("incident-severity", moving, "sha256:" + "9f" * 32)
        with pytest.raises(ContractViolation, match="moving reference"):
            VocabularyBinding(moving, "1.0.0", "sha256:" + "9f" * 32)


# --------------------------------------------------------------------------- #
# VV-E — required now; historical records readable, and never upgraded
# --------------------------------------------------------------------------- #
def test_a_current_record_cannot_be_built_without_naming_its_vocabulary():
    refs = (audit_ref(),)
    with pytest.raises(ContractViolation, match="VV-E"):
        IncidentRecord(incident_id=incident_id_for(TENANT, SUBJECT, refs, T0),
                       tenant_id=TENANT, subject_ref=SUBJECT, severity_label=SEVERITY,
                       evidence=refs, opened_at=T0, opened_by="operator-1")


def test_a_historical_record_reads_as_unversioned_legacy_and_is_never_resolved():
    old = legacy_incident()
    assert old.record_version == LEGACY_CONTRACT_VERSION and not old.is_current_record
    assert old.vocabulary_state is VocabularyBindingState.UNVERSIONED_LEGACY
    assert old.severity_vocabulary is None
    # Nothing turned the absence into the vocabulary this build happens to know.
    assert SEVERITY_VOCABULARY.vocabulary not in str(old.to_dict())


def test_a_look_alike_binding_is_refused():
    """The record takes this package's own type, not something shaped like it."""

    class NotABinding:
        vocabulary = "incident-severity"
        version = "1.0.0"
        specification_digest = "sha256:" + "9f" * 32

    refs = (audit_ref(),)
    with pytest.raises(ContractViolation, match="must be a VocabularyBinding"):
        IncidentRecord(incident_id=incident_id_for(TENANT, SUBJECT, refs, T0),
                       tenant_id=TENANT, subject_ref=SUBJECT, severity_label=SEVERITY,
                       evidence=refs, opened_at=T0, opened_by="operator-1",
                       severity_vocabulary=NotABinding())  # type: ignore[arg-type]


def test_a_historical_record_may_not_carry_a_binding():
    refs = (audit_ref(),)
    with pytest.raises(ContractViolation, match="carries no vocabulary binding"):
        IncidentRecord(incident_id=incident_id_for(TENANT, SUBJECT, refs, T0),
                       tenant_id=TENANT, subject_ref=SUBJECT, severity_label=SEVERITY,
                       evidence=refs, opened_at=T0, opened_by="operator-1",
                       record_version=LEGACY_CONTRACT_VERSION,
                       severity_vocabulary=SEVERITY_VOCABULARY)


def test_an_unknown_record_version_is_refused():
    refs = (audit_ref(),)
    with pytest.raises(ContractViolation, match="record_version"):
        IncidentRecord(incident_id=incident_id_for(TENANT, SUBJECT, refs, T0),
                       tenant_id=TENANT, subject_ref=SUBJECT, severity_label=SEVERITY,
                       evidence=refs, opened_at=T0, opened_by="operator-1",
                       severity_vocabulary=SEVERITY_VOCABULARY,
                       record_version="incident_response.v99")


def test_a_record_cannot_be_stripped_of_its_binding_in_transit_and_revived():
    """``__setstate__`` re-runs every invariant, and the binding rule is one of them.

    This is the bypass the containment asymmetry already had to close: serialise, edit,
    revive. A record that lost its vocabulary on the way back is refused rather than
    quietly becoming a record that never named one.
    """

    current = incident()
    assert pickle.loads(pickle.dumps(current)) == current

    state = dict(current.__dict__)
    state["severity_vocabulary"] = None
    with pytest.raises(ContractViolation, match="VV-E"):
        current.__setstate__(state)


def test_the_projection_carries_the_binding_and_the_record_version():
    projected = incident().to_dict()
    assert projected["record_version"] == CONTRACT_VERSION
    assert projected["severity_vocabulary"] == SEVERITY_VOCABULARY.to_dict()


# --------------------------------------------------------------------------- #
# The reference is recorded, never resolved
# --------------------------------------------------------------------------- #
def test_nothing_here_resolves_a_binding_against_a_published_document():
    forbidden_calls = {"open", "read_text", "read_bytes", "urlopen", "fetch", "resolve",
                       "glob", "iterdir"}
    for source in sorted(SRC.glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                assert name not in forbidden_calls, (source.name, name)
        for literal in _string_literals(tree):
            assert "vocabularies" not in literal, (source.name, literal)
            assert ".json" not in literal, (source.name, literal)


def _string_literals(tree: ast.AST) -> list[str]:
    """Every string constant that is not a docstring."""

    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = node.body[0] if node.body else None
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                docstrings.add(id(first.value))
    return [node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and id(node) not in docstrings]


# --------------------------------------------------------------------------- #
# The reconstruction helpers refuse rather than repair
# --------------------------------------------------------------------------- #
def test_the_helpers_refuse_the_wrong_shape_rather_than_coercing_it():
    """Each refusal below is its own: the mutation sweep is what found them missing.

    A guard nothing exercises is a guard that can be deleted without a test noticing,
    which is the same as not having it.
    """

    with pytest.raises(ContractViolation, match="takes a VocabularyBinding"):
        vocabulary_binding_to_dict("data-classification@1.0.0")  # type: ignore[arg-type]
    assert vocabulary_binding_to_dict(None) is None

    with pytest.raises(ContractViolation, match="mapping"):
        vocabulary_binding_from_dict("data-classification@1.0.0", "binding")
    with pytest.raises(ContractViolation, match="unknown fields"):
        vocabulary_binding_from_dict(
            {"vocabulary": "x", "version": "1.0.0",
             "specification_digest": "sha256:" + "1" * 64, "resolved_at": "now"}, "binding")
    assert vocabulary_binding_from_dict(None, "binding") is None
    assert vocabulary_binding_from_dict({}, "binding") is None


def test_a_refusal_from_a_mapping_keeps_the_precise_reason():
    """ContractViolation is a ValueError, so a broad ``except`` would swallow it.

    Reconstruction therefore wraps nothing: a bad version says it is a bad version,
    rather than arriving as a generic "refused" with the reason folded into a string.
    """

    with pytest.raises(ContractViolation, match="MAJOR.MINOR.PATCH"):
        vocabulary_binding_from_dict(
            {"vocabulary": "x", "version": "1.0", "specification_digest": "sha256:" + "1" * 64},
            "binding")
    with pytest.raises(ContractViolation, match="whatever is current"):
        vocabulary_binding_from_dict(
            {"vocabulary": "x", "version": "latest",
             "specification_digest": "sha256:" + "1" * 64}, "binding")
