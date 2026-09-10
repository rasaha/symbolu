"""Which published vocabulary the classification label was written against.

`VV-A` to `VV-E`, authorized by `PUB-2`. The ruling that shapes this package is `VV-C`,
and it is the one that says *no*: the binding goes into the record digest and
deliberately **not** into the derived id, because this record's identity is the system
binding, the owner and the window, and the label never took part in it. Adding the
vocabulary to the id here would change what a registration *is*, to record something
about how it was read.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import pathlib
import sqlite3

import pytest

import ugence_ai_system_registry as pkg
from ugence_ai_system_registry import (
    CONTRACT_VERSION,
    LEGACY_CONTRACT_VERSION,
    LEGACY_SCHEMA_VERSION,
    SCHEMA_VERSION,
    ContractViolation,
    RegistryStorageError,
    SqliteSystemRegistry,
    SystemRegistration,
    VocabularyBinding,
    VocabularyBindingState,
    registration_from_record,
    registration_id_for,
    registration_record,
)

from _fixtures import (
    CLASSIFICATION_VOCABULARY,
    LABEL,
    NEXT_CLASSIFICATION_VOCABULARY,
    OWNER,
    T1,
    TENANT,
    binding,
    legacy_registration,
    registration,
    window,
)

SRC = pathlib.Path(pkg.__file__).resolve().parent

#: The digest of the canonical fixture as the v1 code took it, captured from the
#: released 0.2.0 projection. Pinned literally: a test that recomputes both sides proves
#: only that the code agrees with itself.
V1_RECORD_DIGEST = "f4c73de096faccc09df7af360a58c9a1760d68746c338854f45ba6864a77694f"
V1_REGISTRATION_ID = "reg_4548967efa55f21bf292d1565c397094"


# --------------------------------------------------------------------------- #
# VV-C — in the digest, and out of the identity
# --------------------------------------------------------------------------- #
def test_the_binding_changes_the_digest_and_never_the_id():
    """The two-of-four split, stated as a test.

    ``DataUseDeclaration`` and ``VendorDependencyDeclaration`` bind their label into a
    derived id; this record does not, and `VV-C` rejected the binary framing that would
    have given all four the same answer. So the vocabulary follows the label: covered by
    the content digest, absent from the identity.
    """

    under_1 = registration()
    under_2 = registration(classification_vocabulary=NEXT_CLASSIFICATION_VOCABULARY)

    assert under_1.registration_id == under_2.registration_id
    assert under_1.record_digest() != under_2.record_digest()


def test_the_derived_id_still_ignores_the_label_itself():
    """Which is why the vocabulary is absent from it: the id follows the label's role."""

    assert registration(label="high-risk").registration_id == \
        registration(label="whatever-the-org-calls-it").registration_id


def test_a_historical_registration_keeps_the_id_and_digest_it_was_stored_with():
    """VV-B: historical digests stay valid under their historical record version.

    Pinned against literals captured from 0.2.0, so this fails if the v1 projection is
    disturbed — which would make every stored record unverifiable at once.
    """

    old = legacy_registration()
    assert old.registration_id == V1_REGISTRATION_ID
    assert old.record_digest() == V1_RECORD_DIGEST
    assert "record_version" not in old.to_dict()
    assert "classification_vocabulary" not in old.to_dict()


# --------------------------------------------------------------------------- #
# VV-A — on the record, and governance-contracts is untouched
# --------------------------------------------------------------------------- #
def test_the_binding_is_this_packages_own_type():
    """VV-A put it on the record so no new neutral type enters governance-contracts."""

    assert VocabularyBinding.__module__.startswith("ugence_ai_system_registry")

    import ugence_governance_contracts

    assert not hasattr(ugence_governance_contracts, "VocabularyBinding")


# --------------------------------------------------------------------------- #
# PUB-2 — an authoritative reference, not a context-free version string
# --------------------------------------------------------------------------- #
def test_a_binding_names_one_specification_and_a_bare_version_is_insufficient():
    good = VocabularyBinding("eu-ai-act-system-classification", "1.0.0", "sha256:" + "9f" * 32)
    assert good.to_dict() == {"vocabulary": "eu-ai-act-system-classification",
                              "version": "1.0.0",
                              "specification_digest": "sha256:" + "9f" * 32}

    for version, digest in (("1.0", "sha256:" + "9f" * 32),
                            ("v1.0.0", "sha256:" + "9f" * 32),
                            ("01.0.0", "sha256:" + "9f" * 32),
                            ("١.0.0", "sha256:" + "9f" * 32),
                            ("1.0.0", "1.0.0"),
                            ("1.0.0", "sha256:" + "9F" * 32),
                            ("1.0.0", "9f" * 32)):
        with pytest.raises(ContractViolation):
            VocabularyBinding("eu-ai-act-system-classification", version, digest)


def test_a_moving_reference_is_refused_by_name():
    """VV-E refuses "current" and "latest" semantics; PUB-1 publishes no latest."""

    for moving in ("latest", "current", "HEAD", "*"):
        with pytest.raises(ContractViolation):
            VocabularyBinding("eu-ai-act-system-classification", moving, "sha256:" + "9f" * 32)
        with pytest.raises(ContractViolation, match="moving reference"):
            VocabularyBinding(moving, "1.0.0", "sha256:" + "9f" * 32)


# --------------------------------------------------------------------------- #
# VV-E — required now; historical records readable, and never upgraded
# --------------------------------------------------------------------------- #
def test_a_current_record_cannot_be_built_without_naming_its_vocabulary():
    b, v = binding(), window()
    with pytest.raises(ContractViolation, match="VV-E"):
        SystemRegistration(registration_id=registration_id_for(b, OWNER, v), binding=b,
                           owner_ref=OWNER, classification_label=LABEL, validity=v)


def test_a_historical_record_reads_as_unversioned_legacy_and_is_never_resolved():
    old = legacy_registration()
    assert old.record_version == LEGACY_CONTRACT_VERSION and not old.is_current_record
    assert old.vocabulary_state is VocabularyBindingState.UNVERSIONED_LEGACY
    assert old.classification_vocabulary is None

    rebuilt = registration_from_record(registration_record(old))
    assert rebuilt == old
    assert rebuilt.vocabulary_state is VocabularyBindingState.UNVERSIONED_LEGACY
    # Nothing turned the absence into the vocabulary this build happens to know.
    assert CLASSIFICATION_VOCABULARY.vocabulary not in str(rebuilt.to_dict())


def test_a_historical_record_may_not_carry_a_binding():
    b, v = binding(), window()
    with pytest.raises(ContractViolation, match="carries no vocabulary binding"):
        SystemRegistration(registration_id=registration_id_for(b, OWNER, v), binding=b,
                           owner_ref=OWNER, classification_label=LABEL, validity=v,
                           record_version=LEGACY_CONTRACT_VERSION,
                           classification_vocabulary=CLASSIFICATION_VOCABULARY)


def test_an_unknown_record_version_is_refused():
    b, v = binding(), window()
    with pytest.raises(ContractViolation, match="record_version"):
        SystemRegistration(registration_id=registration_id_for(b, OWNER, v), binding=b,
                           owner_ref=OWNER, classification_label=LABEL, validity=v,
                           record_version="ai_system_registry.v99")


def test_a_current_record_round_trips_and_a_partial_binding_is_refused():
    original = registration()
    rebuilt = registration_from_record(registration_record(original))
    assert rebuilt == original and rebuilt.record_digest() == original.record_digest()
    assert rebuilt.vocabulary_state is VocabularyBindingState.BOUND

    record = registration_record(original)
    record["registration"]["classification_vocabulary"] = {"version": "1.0.0"}
    with pytest.raises(ContractViolation):
        registration_from_record(record)


# --------------------------------------------------------------------------- #
# The store — a v1 file reads, and takes no new records
# --------------------------------------------------------------------------- #
def test_a_current_file_records_the_binding_and_reads_it_back(tmp_path):
    store = SqliteSystemRegistry(str(tmp_path / "r.sqlite3"), tenant_id=TENANT)
    assert store.schema_version == SCHEMA_VERSION and store.accepts_writes
    original = registration()
    store.register(original)
    (stored,) = store.registrations_for_tenant(tenant_id=TENANT, as_of=T1)
    assert stored.classification_vocabulary == CLASSIFICATION_VOCABULARY
    assert stored.record_digest() == original.record_digest()
    store.close()


def test_a_legacy_file_reads_its_records_and_refuses_every_write(tmp_path):
    """VV-E: migration needs its own ruled process, not the next append."""

    path = tmp_path / "legacy.sqlite3"
    old = legacy_registration()
    _write_legacy_file(path, old)

    store = SqliteSystemRegistry(str(path), tenant_id=TENANT)
    assert store.schema_version == LEGACY_SCHEMA_VERSION and not store.accepts_writes

    (read_back,) = store.registrations_for_tenant(tenant_id=TENANT, as_of=T1)
    assert read_back == old
    assert read_back.vocabulary_state is VocabularyBindingState.UNVERSIONED_LEGACY

    with pytest.raises(RegistryStorageError, match="ruled process"):
        store.register(registration())
    store.close()


def test_a_current_file_refuses_a_historical_record(tmp_path):
    store = SqliteSystemRegistry(str(tmp_path / "r.sqlite3"), tenant_id=TENANT)
    with pytest.raises(ContractViolation, match="historical shape"):
        store.register(legacy_registration())
    assert store.count() == 0
    store.close()


def test_an_unknown_schema_version_is_refused_rather_than_guessed(tmp_path):
    path = tmp_path / "future.sqlite3"
    _write_legacy_file(path, legacy_registration(),
                       schema_version="ai_system_registry.sqlite.v9")
    with pytest.raises(RegistryStorageError, match="does not know"):
        SqliteSystemRegistry(str(path), tenant_id=TENANT)


# --------------------------------------------------------------------------- #
# The reference is recorded, never resolved
# --------------------------------------------------------------------------- #
def test_nothing_here_resolves_a_binding_against_a_published_document():
    """PUB-2 required a reference precise enough for somebody else to check; it did not
    make this package the checker."""

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


def test_the_binding_holds_three_short_strings_and_nothing_that_could_hide_data():
    names = [f.name for f in dataclasses.fields(VocabularyBinding)]
    assert names == ["vocabulary", "version", "specification_digest"]
    for forbidden in ("data", "payload", "content", "body", "document", "text"):
        assert forbidden not in names, forbidden


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


def _write_legacy_file(path: pathlib.Path, old: SystemRegistration,
                       schema_version: str = LEGACY_SCHEMA_VERSION) -> None:
    """A file exactly as 0.2.0 wrote one: v1 schema row, v1 record projection."""

    connection = sqlite3.connect(str(path), isolation_level=None)
    connection.execute(
        "CREATE TABLE registrations (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        " registration_id TEXT NOT NULL UNIQUE, tenant_id TEXT NOT NULL,"
        " system_id TEXT NOT NULL, system_version TEXT NOT NULL,"
        " classification_label TEXT NOT NULL, supersedes TEXT NOT NULL,"
        " record_digest TEXT NOT NULL, record_json TEXT NOT NULL)")
    connection.execute(
        "CREATE TABLE registry_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.execute("INSERT INTO registry_meta VALUES ('schema_version', ?)",
                       (schema_version,))
    connection.execute("INSERT INTO registry_meta VALUES ('tenant_id', ?)", (TENANT,))
    connection.execute(
        "INSERT INTO registrations(registration_id, tenant_id, system_id, system_version, "
        "classification_label, supersedes, record_digest, record_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (old.registration_id, old.tenant_id, old.system_id, old.system_version,
         old.classification_label, old.supersedes, old.record_digest(),
         json.dumps(registration_record(old), sort_keys=True, separators=(",", ":"))))
    connection.close()
