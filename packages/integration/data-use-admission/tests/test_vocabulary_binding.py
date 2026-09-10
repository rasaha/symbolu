"""Which published vocabulary a label was written against — VV-A to VV-E, PUB-2.

The ballot's §2 lists four conditions that must hold before any package may interpret
rather than record a label. Condition 4 is that the record carries which vocabulary it
was written against, "or an old record silently re-reads under a new taxonomy". These
tests hold the five rulings that scoped the fix, and one thing none of them said but
all of them assume: that adding the field did not quietly rewrite what the records
already stored say.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib
import sqlite3

import pytest

import ugence_data_use_admission as pkg
from ugence_data_use_admission import (
    CONTRACT_VERSION,
    LEGACY_CONTRACT_VERSION,
    LEGACY_SCHEMA_VERSION,
    SCHEMA_VERSION,
    ContractViolation,
    DataClassificationLabel,
    DataUseDeclaration,
    DeclarationStorageError,
    SqliteDataUseDeclarations,
    VocabularyBinding,
    VocabularyBindingState,
    declaration_from_record,
    declaration_id_for,
    declaration_record,
    supersession_refusals,
    vocabulary_binding_from_dict,
    vocabulary_binding_to_dict,
)

from _fixtures import (
    CLASSIFICATION_VOCABULARY,
    DATA,
    LABEL,
    NEXT_CLASSIFICATION_VOCABULARY,
    PURPOSE,
    PURPOSE_VOCABULARY,
    T1,
    TENANT,
    binding,
    declaration,
    legacy_declaration,
    window,
)

SRC = pathlib.Path(pkg.__file__).resolve().parent

#: The id and digest of the canonical fixture as the v1 code derived them, captured
#: from the released 0.2.0 projection before the bindings were added. They are pinned
#: literally rather than recomputed, because a test that recomputes both sides proves
#: only that the code agrees with itself.
V1_DECLARATION_ID = "dud_4d7f3e58cac10ca8cec2b2120dcea160"
V1_RECORD_DIGEST = "a2205bde3dce21f40794f8c9c3e0a564bda35dc47d80aa963cb97e43df598383"


# --------------------------------------------------------------------------- #
# VV-A — on the record, and governance-contracts is untouched
# --------------------------------------------------------------------------- #
def test_the_binding_is_this_packages_own_type_and_lands_on_the_record():
    """2B, not 2A. The neutral label types keep their one field.

    VV-A put the binding on the record precisely so no new neutral type lands in
    governance-contracts and LP-5 is not pre-empted by accident. So the type is local,
    and the label it describes is unchanged.
    """

    assert VocabularyBinding.__module__.startswith("ugence_data_use_admission")
    assert [f.name for f in dataclasses.fields(DataClassificationLabel)] == ["label"]

    import ugence_governance_contracts

    assert not hasattr(ugence_governance_contracts, "VocabularyBinding")


def test_each_governed_label_carries_its_own_binding_on_the_record():
    d = declaration()
    assert d.classification_vocabulary is CLASSIFICATION_VOCABULARY
    assert d.purpose_vocabulary is PURPOSE_VOCABULARY
    assert d.vocabulary_state is VocabularyBindingState.BOUND and d.is_current_record


# --------------------------------------------------------------------------- #
# PUB-2 — an authoritative reference, not a context-free version string
# --------------------------------------------------------------------------- #
def test_a_binding_names_one_specification_and_a_bare_version_is_insufficient():
    good = VocabularyBinding("data-classification", "1.0.0", "sha256:" + "9f" * 32)
    assert good.to_dict() == {"vocabulary": "data-classification", "version": "1.0.0",
                              "specification_digest": "sha256:" + "9f" * 32}

    for version, digest in (("1.0", "sha256:" + "9f" * 32),
                            ("v1.0.0", "sha256:" + "9f" * 32),
                            ("1.0.0.0", "sha256:" + "9f" * 32),
                            ("01.0.0", "sha256:" + "9f" * 32),
                            ("1.0.0", "1.0.0"),
                            ("1.0.0", "sha256:" + "9F" * 32),
                            ("1.0.0", "sha256:" + "9f" * 31),
                            ("1.0.0", "9f" * 32)):
        with pytest.raises(ContractViolation):
            VocabularyBinding("data-classification", version, digest)


def test_a_moving_reference_is_refused_by_name():
    """VV-E refuses "current" and "latest" semantics, and PUB-1 publishes no latest.

    A record citing a moving reference records nothing durable: what it meant changes
    the next time somebody publishes, which is the failure the whole field exists to
    prevent.
    """

    for moving in ("latest", "current", "newest", "HEAD", "*"):
        with pytest.raises(ContractViolation, match="whatever is current|moving reference"):
            VocabularyBinding("data-classification", moving, "sha256:" + "9f" * 32)
        with pytest.raises(ContractViolation, match="moving reference"):
            VocabularyBinding(moving, "1.0.0", "sha256:" + "9f" * 32)

    for empty in ("", "   "):
        with pytest.raises(ContractViolation):
            VocabularyBinding("data-classification", empty, "sha256:" + "9f" * 32)


def test_a_unicode_digit_is_not_a_version():
    """``str.isdigit`` accepts Arabic-Indic digits, so the check does not use it.

    A version that "looks like digits" but is not the published one would name a
    specification that does not exist while passing a laxer check.
    """

    with pytest.raises(ContractViolation):
        VocabularyBinding("data-classification", "١.0.0", "sha256:" + "9f" * 32)


# --------------------------------------------------------------------------- #
# VV-D — two independent bindings, neither borrowed from the other
# --------------------------------------------------------------------------- #
def test_the_purpose_binding_is_independent_of_the_classification_binding():
    """LV-E's open shape does not mean purpose terminology is anonymously sourced.

    The two are separate fields with separate values, and moving either one alone
    changes the record — so neither can be reconstructed from the other.
    """

    base = declaration()
    other_purpose_vocabulary = VocabularyBinding("data-use-purpose", "2.0.0",
                                                 "sha256:" + "4d" * 32)
    moved_purpose = declaration(purpose_vocabulary=other_purpose_vocabulary)
    moved_classification = declaration(
        classification_vocabulary=NEXT_CLASSIFICATION_VOCABULARY)

    ids = {base.declaration_id, moved_purpose.declaration_id,
           moved_classification.declaration_id}
    assert len(ids) == 3
    assert base.classification_vocabulary != base.purpose_vocabulary


def test_one_binding_without_the_other_is_refused():
    """There is no third record shape, so there is no half-bound record to interpret."""

    b, v = binding(), window()
    with pytest.raises(ContractViolation, match="both vocabulary bindings or neither"):
        declaration_id_for(b, DATA, LABEL, PURPOSE, v, CLASSIFICATION_VOCABULARY, None)

    derived = declaration_id_for(b, DATA, LABEL, PURPOSE, v, CLASSIFICATION_VOCABULARY,
                                 PURPOSE_VOCABULARY)
    with pytest.raises(ContractViolation, match="purpose_vocabulary"):
        DataUseDeclaration(declaration_id=derived, tenant_id=TENANT, binding=b,
                           data_ref=DATA, classification=LABEL, purpose_label=PURPOSE,
                           validity=v, classification_vocabulary=CLASSIFICATION_VOCABULARY)


# --------------------------------------------------------------------------- #
# VV-B and VV-C — in the digest, and in the derived id
# --------------------------------------------------------------------------- #
def test_two_records_differing_only_in_vocabulary_version_are_two_records():
    """VV-B: a digest that excluded the taxonomy would prove the bytes of a label while
    failing to prove what that label meant."""

    written_under_1 = declaration()
    written_under_2 = declaration(classification_vocabulary=NEXT_CLASSIFICATION_VOCABULARY)

    assert written_under_1.classification_label == written_under_2.classification_label
    assert written_under_1.purpose_label == written_under_2.purpose_label
    assert written_under_1.record_digest() != written_under_2.record_digest()
    assert written_under_1.declaration_id != written_under_2.declaration_id


def test_the_projection_carries_the_bindings_and_the_record_version():
    projected = declaration().to_dict()
    assert projected["record_version"] == CONTRACT_VERSION
    assert projected["classification_vocabulary"] == CLASSIFICATION_VOCABULARY.to_dict()
    assert projected["purpose_vocabulary"] == PURPOSE_VOCABULARY.to_dict()


def test_a_record_round_trips_through_the_reconstructible_form():
    original = declaration(residency="eu-west", declared_by="admin-2")
    rebuilt = declaration_from_record(declaration_record(original))
    assert rebuilt == original
    assert rebuilt.record_digest() == original.record_digest()
    assert rebuilt.vocabulary_state is VocabularyBindingState.BOUND


def test_a_partial_binding_in_a_record_is_refused_rather_than_completed():
    """PUB-2: an absent reference is never defaulted to the current vocabulary.

    So a half-written one is a refusal, not something to finish from context.
    """

    record = declaration_record(declaration())
    record["declaration"]["classification_vocabulary"] = {"vocabulary": "data-classification"}
    with pytest.raises(ContractViolation):
        declaration_from_record(record)

    with pytest.raises(ContractViolation, match="unknown fields"):
        vocabulary_binding_from_dict(
            {"vocabulary": "x", "version": "1.0.0", "specification_digest": "sha256:" + "1" * 64,
             "resolved_at": "now"}, "binding")

    assert vocabulary_binding_from_dict(None, "binding") is None
    assert vocabulary_binding_from_dict({}, "binding") is None


# --------------------------------------------------------------------------- #
# VV-E — required now; historical records readable, and never upgraded
# --------------------------------------------------------------------------- #
def test_a_look_alike_binding_is_refused():
    """The record takes this package's own type, not something shaped like it."""

    class NotABinding:
        vocabulary = "data-classification"
        version = "1.0.0"
        specification_digest = "sha256:" + "9f" * 32

    b, v = binding(), window()
    with pytest.raises(ContractViolation, match="must be a VocabularyBinding"):
        DataUseDeclaration(
            declaration_id=declaration_id_for(b, DATA, LABEL, PURPOSE, v,
                                              CLASSIFICATION_VOCABULARY, PURPOSE_VOCABULARY),
            tenant_id=TENANT, binding=b, data_ref=DATA, classification=LABEL,
            purpose_label=PURPOSE, validity=v,
            classification_vocabulary=NotABinding(),  # type: ignore[arg-type]
            purpose_vocabulary=PURPOSE_VOCABULARY)


def test_a_current_record_cannot_be_built_without_naming_its_vocabularies():
    b, v = binding(), window()
    with pytest.raises(ContractViolation, match="VV-E"):
        DataUseDeclaration(
            declaration_id=declaration_id_for(b, DATA, LABEL, PURPOSE, v),
            tenant_id=TENANT, binding=b, data_ref=DATA, classification=LABEL,
            purpose_label=PURPOSE, validity=v)


def test_a_historical_record_reads_as_unversioned_legacy_and_is_never_resolved():
    old = legacy_declaration()
    assert old.record_version == LEGACY_CONTRACT_VERSION and not old.is_current_record
    assert old.vocabulary_state is VocabularyBindingState.UNVERSIONED_LEGACY
    assert old.classification_vocabulary is None and old.purpose_vocabulary is None

    rebuilt = declaration_from_record(declaration_record(old))
    assert rebuilt == old
    assert rebuilt.vocabulary_state is VocabularyBindingState.UNVERSIONED_LEGACY
    # Nothing anywhere turned the absence into the vocabulary this build happens to know.
    assert CLASSIFICATION_VOCABULARY.vocabulary not in str(rebuilt.to_dict())


def test_a_historical_record_keeps_the_id_and_digest_it_was_stored_with():
    """VV-B: historical digests remain valid under their historical record version and
    are never recomputed under the new projection.

    Pinned against literals captured from 0.2.0, so this fails if the v1 projection is
    ever disturbed — which would make every stored record unreadable at once.
    """

    old = legacy_declaration()
    assert old.declaration_id == V1_DECLARATION_ID
    assert old.record_digest() == V1_RECORD_DIGEST
    assert "record_version" not in old.to_dict()
    assert "classification_vocabulary" not in old.to_dict()


def test_a_historical_record_may_not_carry_a_binding():
    """The two shapes are exclusive, so there is no record that is partly either."""

    b, v = binding(), window()
    with pytest.raises(ContractViolation, match="carries no vocabulary binding"):
        DataUseDeclaration(
            declaration_id=declaration_id_for(b, DATA, LABEL, PURPOSE, v),
            tenant_id=TENANT, binding=b, data_ref=DATA, classification=LABEL,
            purpose_label=PURPOSE, validity=v, record_version=LEGACY_CONTRACT_VERSION,
            classification_vocabulary=CLASSIFICATION_VOCABULARY,
            purpose_vocabulary=PURPOSE_VOCABULARY)


def test_an_unknown_record_version_is_refused():
    b, v = binding(), window()
    with pytest.raises(ContractViolation, match="record_version"):
        DataUseDeclaration(
            declaration_id=declaration_id_for(b, DATA, LABEL, PURPOSE, v),
            tenant_id=TENANT, binding=b, data_ref=DATA, classification=LABEL,
            purpose_label=PURPOSE, validity=v, record_version="data_use_admission.v99")


# --------------------------------------------------------------------------- #
# Supersession — a new vocabulary version is a change worth recording
# --------------------------------------------------------------------------- #
def test_re_declaring_the_same_label_under_a_new_vocabulary_is_a_supersession():
    """The words are identical and what they were read to mean is not.

    Leaving the bindings out of the declared terms would refuse exactly the supersession
    a vocabulary revision exists to record.
    """

    first = declaration()
    revised = declaration(classification_vocabulary=NEXT_CLASSIFICATION_VOCABULARY,
                          supersedes=first.declaration_id)
    assert first.classification_label == revised.classification_label
    assert supersession_refusals(revised, first) == ()

    unchanged = declaration(supersedes=first.declaration_id)
    assert any("must change what was declared" in reason
               for reason in supersession_refusals(unchanged, first))


# --------------------------------------------------------------------------- #
# The store — a v1 file reads, and takes no new records
# --------------------------------------------------------------------------- #
def test_a_current_file_records_the_bindings_and_reads_them_back(tmp_path):
    store = SqliteDataUseDeclarations(str(tmp_path / "d.sqlite3"), tenant_id=TENANT)
    assert store.schema_version == SCHEMA_VERSION and store.accepts_writes
    original = declaration()
    store.declare(original)
    (stored,) = store.declarations_for_tenant(tenant_id=TENANT, as_of=T1)
    assert stored.classification_vocabulary == CLASSIFICATION_VOCABULARY
    assert stored.purpose_vocabulary == PURPOSE_VOCABULARY
    assert stored.record_digest() == original.record_digest()
    store.close()


def test_a_legacy_file_reads_its_records_and_refuses_every_write(tmp_path):
    """VV-E: migration needs its own ruled process, not the next append.

    Appending a v2 record to a v1 file would make the file's own schema row a lie, and
    the records already in it would sit beside records of a shape they never anticipated.
    """

    path = tmp_path / "legacy.sqlite3"
    old = legacy_declaration()
    _write_legacy_file(path, old)

    store = SqliteDataUseDeclarations(str(path), tenant_id=TENANT)
    assert store.schema_version == LEGACY_SCHEMA_VERSION and not store.accepts_writes

    (read_back,) = store.declarations_for_tenant(tenant_id=TENANT, as_of=T1)
    assert read_back == old
    assert read_back.vocabulary_state is VocabularyBindingState.UNVERSIONED_LEGACY
    assert read_back.declaration_id == V1_DECLARATION_ID

    with pytest.raises(DeclarationStorageError, match="ruled process"):
        store.declare(declaration())
    store.close()


def test_a_current_file_refuses_a_historical_record(tmp_path):
    """The requirement is structural at the write boundary too, not only at the type."""

    store = SqliteDataUseDeclarations(str(tmp_path / "d.sqlite3"), tenant_id=TENANT)
    with pytest.raises(ContractViolation, match="historical shape"):
        store.declare(legacy_declaration())
    assert store.count() == 0
    store.close()


def test_an_unknown_schema_version_is_refused_rather_than_guessed(tmp_path):
    path = tmp_path / "future.sqlite3"
    _write_legacy_file(path, legacy_declaration(), schema_version="data_use_admission.sqlite.v9")
    with pytest.raises(DeclarationStorageError, match="does not know"):
        SqliteDataUseDeclarations(str(path), tenant_id=TENANT)


# --------------------------------------------------------------------------- #
# The reference is recorded, never resolved
# --------------------------------------------------------------------------- #
def test_nothing_here_resolves_a_binding_against_a_published_document():
    """Structural validation is not resolution.

    PUB-2 required a reference precise enough for somebody else to check; it did not
    make this package the checker, and a package that opened docs/vocabularies/ would
    be reading a governance document to decide something — which is the interpreting
    layer that still does not exist.
    """

    # Reading a document, not reaching the network: the import boundary in
    # tests/test_boundaries.py already forbids every transport this package could use.
    # ``get`` is deliberately absent — ``dict.get`` is everywhere in the reconstruction
    # path, and a guard that fires on it would be turned off rather than obeyed.
    forbidden_calls = {"open", "read_text", "read_bytes", "urlopen", "fetch",
                       "resolve", "glob", "iterdir", "load", "loads_from_path"}
    for source in sorted(SRC.glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                assert name not in forbidden_calls, (source.name, name)
        # Docstrings may name the published directory to state that this package never
        # opens it, exactly as they may say "admit" to state that it never admits. A
        # path in live code would be something else entirely.
        for literal in _string_literals(tree):
            assert "vocabularies" not in literal, (source.name, literal)
            assert ".json" not in literal, (source.name, literal)


def test_the_binding_is_never_reconstructed_from_its_display_spelling():
    """``reference`` is a convenience, and a second encoding would be a second truth."""

    spelling = CLASSIFICATION_VOCABULARY.reference
    assert CLASSIFICATION_VOCABULARY.vocabulary in spelling
    for source in sorted(SRC.glob("*.py")):
        text = source.read_text(encoding="utf-8")
        assert ".reference.split" not in text and "parse_reference" not in text


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


def _write_legacy_file(path: pathlib.Path, old: DataUseDeclaration,
                       schema_version: str = LEGACY_SCHEMA_VERSION) -> None:
    """A file exactly as 0.2.0 wrote one: v1 schema row, v1 record projection."""

    import json

    connection = sqlite3.connect(str(path), isolation_level=None)
    connection.execute(
        "CREATE TABLE declarations (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        " declaration_id TEXT NOT NULL UNIQUE, tenant_id TEXT NOT NULL,"
        " data_ref TEXT NOT NULL, system_id TEXT NOT NULL, system_version TEXT NOT NULL,"
        " classification_label TEXT NOT NULL, purpose_label TEXT NOT NULL,"
        " supersedes TEXT NOT NULL, record_digest TEXT NOT NULL, record_json TEXT NOT NULL)")
    connection.execute(
        "CREATE TABLE declarations_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.execute("INSERT INTO declarations_meta VALUES ('schema_version', ?)",
                       (schema_version,))
    connection.execute("INSERT INTO declarations_meta VALUES ('tenant_id', ?)", (TENANT,))
    connection.execute(
        "INSERT INTO declarations(declaration_id, tenant_id, data_ref, system_id, "
        "system_version, classification_label, purpose_label, supersedes, record_digest, "
        "record_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (old.declaration_id, old.tenant_id, old.data_ref, old.system_id,
         old.system_version, old.classification_label, old.purpose_label, old.supersedes,
         old.record_digest(),
         json.dumps(declaration_record(old), sort_keys=True, separators=(",", ":"))))
    connection.close()


# --------------------------------------------------------------------------- #
# The reconstruction helpers refuse rather than repair
# --------------------------------------------------------------------------- #
def test_the_helpers_refuse_the_wrong_shape_rather_than_coercing_it():
    """Found missing by incident-response's mutation sweep, which runs over the same
    file: a guard nothing exercises is a guard that can be deleted without a test
    noticing, which is the same as not having it."""

    with pytest.raises(ContractViolation, match="takes a VocabularyBinding"):
        vocabulary_binding_to_dict("data-classification@1.0.0")  # type: ignore[arg-type]
    assert vocabulary_binding_to_dict(None) is None

    with pytest.raises(ContractViolation, match="mapping"):
        vocabulary_binding_from_dict("data-classification@1.0.0", "binding")
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
