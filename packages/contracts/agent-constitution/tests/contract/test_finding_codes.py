"""Finding codes are a closed, declared set with stable, unique values."""

from __future__ import annotations

import fixtures

from ugence_agent_constitution import ArtifactKind, validate_artifact
from ugence_agent_constitution.validation import codes


def _declared_constants():
    return {
        name: value
        for name, value in vars(codes).items()
        if name.isupper() and name != "ALL_CODES" and isinstance(value, str)
    }


def test_every_declared_constant_is_in_all_codes():
    for name, value in _declared_constants().items():
        assert value in codes.ALL_CODES, name


def test_all_codes_contains_nothing_undeclared():
    assert codes.ALL_CODES == set(_declared_constants().values())


def test_code_values_are_unique():
    values = list(_declared_constants().values())
    assert len(values) == len(set(values))


def test_every_code_is_namespaced_so_it_cannot_collide_with_another_package():
    for value in codes.ALL_CODES:
        assert value.startswith("AC_"), value


def test_no_code_escapes_the_declared_set_across_a_broad_corpus():
    corpus = [
        (fixtures.manifest(), ArtifactKind.AGENT_ROLE_MANIFEST),
        (fixtures.manifest(author_id=""), ArtifactKind.AGENT_ROLE_MANIFEST),
        (fixtures.constitution(), ArtifactKind.AGENT_CONSTITUTION),
        (fixtures.constitution(role_name=" x "), ArtifactKind.AGENT_CONSTITUTION),
        (fixtures.constitution(artifact_version="x"), ArtifactKind.AGENT_CONSTITUTION),
        (fixtures.contract(), ArtifactKind.DEVELOPER_IMPLEMENTATION_CONTRACT),
        (fixtures.subject(), ArtifactKind.CONFORMANCE_SUBJECT),
        ({}, ArtifactKind.AGENT_CONSTITUTION),
        ("not a mapping", ArtifactKind.AGENT_CONSTITUTION),
    ]
    for payload, kind in corpus:
        for code in validate_artifact(payload, kind).codes:
            assert code in codes.ALL_CODES, code
