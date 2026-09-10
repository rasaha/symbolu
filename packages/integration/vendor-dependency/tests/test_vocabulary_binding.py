"""Which published vocabulary the risk posture was written against.

`VV-A` to `VV-E`, authorized by `PUB-2`. Two rulings landed here specifically.

**`PUB-2` decided the shape of the binding by examining this package's `policy_ref`.**
Reuse was authorized only if `policy_ref` normatively identified the exact vocabulary,
and `VR-4` forbids resolving, verifying, interpreting or fetching it — so it references
*some* policy, with no guarantee which, and cannot identify a vocabulary. The binding is
a separate field beside it. `policy_ref` is the shape to copy, not the carrier.

**`VV-C` says yes here.** `risk_posture` already participates in the derived
declaration id, so the vocabulary it was read under participates too. This is one of the
two records where the answer is yes, and it is yes for that reason rather than by
default.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import pathlib
import sqlite3

import pytest

import ugence_vendor_dependency as pkg
from ugence_vendor_dependency import (
    CONTRACT_VERSION,
    LEGACY_CONTRACT_VERSION,
    LEGACY_SCHEMA_VERSION,
    SCHEMA_VERSION,
    ContractViolation,
    DeclarationStorageError,
    SqliteVendorDeclarations,
    VendorDependencyDeclaration,
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
    NEXT_POSTURE_VOCABULARY,
    POLICY,
    POSTURE,
    POSTURE_VOCABULARY,
    T1,
    TENANT,
    VENDOR,
    binding,
    declaration,
    legacy_declaration,
    window,
)

SRC = pathlib.Path(pkg.__file__).resolve().parent

#: The id and digest of the canonical fixture as the v1 code derived them, captured from
#: the released 0.2.0 projection. Pinned literally: a test that recomputes both sides
#: proves only that the code agrees with itself.
V1_DECLARATION_ID = "vdd_5cf630c1f339f7eb0e17e3569daa1289"
V1_RECORD_DIGEST = "50535ef75b5ce5b8aca6d5945cddb6a3a40fb1bbecbf6c2983a2ab8addc03e22"


# --------------------------------------------------------------------------- #
# PUB-2 — policy_ref is the shape to copy, not the carrier
# --------------------------------------------------------------------------- #
def test_the_vocabulary_reference_is_a_separate_field_from_policy_ref():
    """VR-4 forbids interpreting policy_ref, so it cannot normatively identify anything.

    The two coexist and mean different things: one references a policy this package may
    not resolve, the other names one immutable published specification exactly.
    """

    d = declaration()
    assert d.policy_ref == POLICY
    assert d.posture_vocabulary == POSTURE_VOCABULARY
    assert POLICY != POSTURE_VOCABULARY.vocabulary

    # Moving the policy reference and moving the vocabulary are different changes,
    # and each is its own declaration.
    other_policy = declaration(policy="policy://vendor-risk/v9")
    other_vocabulary = declaration(posture_vocabulary=NEXT_POSTURE_VOCABULARY)
    assert len({d.declaration_id, other_policy.declaration_id,
                other_vocabulary.declaration_id}) == 3


def test_the_refusal_names_why_policy_ref_does_not_stand_in():
    """A caller who reaches for the obvious shortcut is told the ruling, not just no."""

    b, v = binding(), window()
    with pytest.raises(ContractViolation, match="policy_ref does not stand in for it"):
        VendorDependencyDeclaration(
            declaration_id=declaration_id_for(b, VENDOR, POSTURE, POLICY, v),
            tenant_id=TENANT, binding=b, vendor_ref=VENDOR, risk_posture=POSTURE,
            policy_ref=POLICY, validity=v)


# --------------------------------------------------------------------------- #
# VV-C — yes here, because the posture is already part of the identity
# --------------------------------------------------------------------------- #
def test_two_declarations_differing_only_in_vocabulary_version_are_two_declarations():
    under_1 = declaration()
    under_2 = declaration(posture_vocabulary=NEXT_POSTURE_VOCABULARY)

    assert under_1.risk_posture == under_2.risk_posture
    assert under_1.declaration_id != under_2.declaration_id
    assert under_1.record_digest() != under_2.record_digest()


def test_a_historical_declaration_keeps_the_id_and_digest_it_was_stored_with():
    """VV-B: historical digests stay valid under their historical record version.

    Pinned against literals captured from 0.2.0, so this fails if the v1 projection is
    disturbed — which would make every stored record unreadable at once.
    """

    old = legacy_declaration()
    assert old.declaration_id == V1_DECLARATION_ID
    assert old.record_digest() == V1_RECORD_DIGEST
    assert "record_version" not in old.to_dict()
    assert "posture_vocabulary" not in old.to_dict()


def test_re_declaring_the_same_posture_under_a_new_vocabulary_is_a_supersession():
    """The words are identical and what they were read to mean is not.

    Leaving the binding out of the declared terms would refuse exactly the supersession
    a vocabulary revision exists to record.
    """

    first = declaration()
    revised = declaration(posture_vocabulary=NEXT_POSTURE_VOCABULARY,
                          supersedes=first.declaration_id)
    assert first.risk_posture == revised.risk_posture
    assert supersession_refusals(revised, first) == ()

    unchanged = declaration(supersedes=first.declaration_id)
    assert any("must change what was declared" in reason
               for reason in supersession_refusals(unchanged, first))


# --------------------------------------------------------------------------- #
# VR-3 and PUB-1a — citing a vocabulary confers nothing
# --------------------------------------------------------------------------- #
def test_the_binding_confers_no_eligibility_and_carries_no_ordering():
    """VR-3 forbids implied eligibility, and PUB-1a renamed the vocabulary for it.

    LV-C refused a permission ladder because a member reading APPROVED would be read as
    a permission whatever the type said. Naming the vocabulary must not undo that: the
    record gains no approval surface, and the binding holds three strings.
    """

    surface = {n for n in dir(declaration()) if not n.startswith("_")}
    assert not surface & {"approved", "is_approved", "eligible", "eligibility", "grade",
                          "score", "rank", "tier", "onboarded"}
    binding_fields = {f.name for f in dataclasses.fields(VocabularyBinding)}
    assert not binding_fields & {"eligibility", "ordering", "members", "grade"}
    assert "permission" not in POSTURE_VOCABULARY.vocabulary


# --------------------------------------------------------------------------- #
# VV-A — the type is this package's own
# --------------------------------------------------------------------------- #
def test_the_binding_is_this_packages_own_type_and_the_label_is_unchanged():
    assert VocabularyBinding.__module__.startswith("ugence_vendor_dependency")

    import ugence_governance_contracts
    from ugence_governance_contracts.api import VendorRiskLabel

    assert not hasattr(ugence_governance_contracts, "VocabularyBinding")
    assert [f.name for f in dataclasses.fields(VendorRiskLabel)] == ["label"]


# --------------------------------------------------------------------------- #
# PUB-2 — an authoritative reference, not a context-free version string
# --------------------------------------------------------------------------- #
def test_a_binding_names_one_specification_and_a_bare_version_is_insufficient():
    good = VocabularyBinding("vendor-dependency-assessment-state", "1.0.0",
                             "sha256:" + "9f" * 32)
    assert good.to_dict() == {"vocabulary": "vendor-dependency-assessment-state",
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
            VocabularyBinding("vendor-dependency-assessment-state", version, digest)


def test_a_moving_reference_is_refused_by_name():
    """By name, and with the reason that names it.

    Every moving spelling would also fail the MAJOR.MINOR.PATCH check, so the message is
    the only observable difference — and it is the part that matters, because VV-E
    refuses these spellings specifically rather than as malformed versions.
    """

    for moving in ("latest", "current", "HEAD", "*"):
        with pytest.raises(ContractViolation, match="whatever is current"):
            VocabularyBinding("vendor-dependency-assessment-state", moving,
                              "sha256:" + "9f" * 32)
        with pytest.raises(ContractViolation, match="moving reference"):
            VocabularyBinding(moving, "1.0.0", "sha256:" + "9f" * 32)


# --------------------------------------------------------------------------- #
# VV-E — required now; historical records readable, and never upgraded
# --------------------------------------------------------------------------- #
def test_a_look_alike_binding_is_refused():
    class NotABinding:
        vocabulary = "vendor-dependency-assessment-state"
        version = "1.0.0"
        specification_digest = "sha256:" + "9f" * 32

    b, v = binding(), window()
    with pytest.raises(ContractViolation, match="must be a VocabularyBinding"):
        VendorDependencyDeclaration(
            declaration_id=declaration_id_for(b, VENDOR, POSTURE, POLICY, v),
            tenant_id=TENANT, binding=b, vendor_ref=VENDOR, risk_posture=POSTURE,
            policy_ref=POLICY, validity=v,
            posture_vocabulary=NotABinding())  # type: ignore[arg-type]


def test_a_historical_record_reads_as_unversioned_legacy_and_is_never_resolved():
    old = legacy_declaration()
    assert old.record_version == LEGACY_CONTRACT_VERSION and not old.is_current_record
    assert old.vocabulary_state is VocabularyBindingState.UNVERSIONED_LEGACY
    assert old.posture_vocabulary is None

    rebuilt = declaration_from_record(declaration_record(old))
    assert rebuilt == old
    assert rebuilt.vocabulary_state is VocabularyBindingState.UNVERSIONED_LEGACY
    assert POSTURE_VOCABULARY.vocabulary not in str(rebuilt.to_dict())


def test_a_historical_record_may_not_carry_a_binding():
    b, v = binding(), window()
    with pytest.raises(ContractViolation, match="carries no vocabulary binding"):
        VendorDependencyDeclaration(
            declaration_id=declaration_id_for(b, VENDOR, POSTURE, POLICY, v),
            tenant_id=TENANT, binding=b, vendor_ref=VENDOR, risk_posture=POSTURE,
            policy_ref=POLICY, validity=v, record_version=LEGACY_CONTRACT_VERSION,
            posture_vocabulary=POSTURE_VOCABULARY)


def test_an_unknown_record_version_is_refused():
    b, v = binding(), window()
    with pytest.raises(ContractViolation, match="record_version"):
        VendorDependencyDeclaration(
            declaration_id=declaration_id_for(b, VENDOR, POSTURE, POLICY, v),
            tenant_id=TENANT, binding=b, vendor_ref=VENDOR, risk_posture=POSTURE,
            policy_ref=POLICY, validity=v, record_version="vendor_dependency.v99")


def test_a_current_record_round_trips_and_a_partial_binding_is_refused():
    original = declaration(declared_by="admin-2")
    rebuilt = declaration_from_record(declaration_record(original))
    assert rebuilt == original and rebuilt.record_digest() == original.record_digest()
    assert rebuilt.vocabulary_state is VocabularyBindingState.BOUND
    assert rebuilt.to_dict()["record_version"] == CONTRACT_VERSION

    record = declaration_record(original)
    record["declaration"]["posture_vocabulary"] = {"version": "1.0.0"}
    with pytest.raises(ContractViolation):
        declaration_from_record(record)


# --------------------------------------------------------------------------- #
# The store — a v1 file reads, and takes no new records
# --------------------------------------------------------------------------- #
def test_a_current_file_records_the_binding_and_reads_it_back(tmp_path):
    store = SqliteVendorDeclarations(str(tmp_path / "v.sqlite3"), tenant_id=TENANT)
    assert store.schema_version == SCHEMA_VERSION and store.accepts_writes
    original = declaration()
    store.declare(original)
    (stored,) = store.declarations_for_tenant(tenant_id=TENANT, as_of=T1)
    assert stored.posture_vocabulary == POSTURE_VOCABULARY
    assert stored.record_digest() == original.record_digest()
    store.close()


def test_a_legacy_file_reads_its_records_and_refuses_every_write(tmp_path):
    """The v1 file is closed permanently, and the refusal says so.

    `VV-E` left migration to a ruled process; `MIG-5` ruled there will not be one, so the
    message must not read as a promise that a reader could wait for.
    """

    path = tmp_path / "legacy.sqlite3"
    old = legacy_declaration()
    _write_legacy_file(path, old)

    store = SqliteVendorDeclarations(str(path), tenant_id=TENANT)
    assert store.schema_version == LEGACY_SCHEMA_VERSION and not store.accepts_writes

    (read_back,) = store.declarations_for_tenant(tenant_id=TENANT, as_of=T1)
    assert read_back == old
    assert read_back.declaration_id == V1_DECLARATION_ID
    assert read_back.vocabulary_state is VocabularyBindingState.UNVERSIONED_LEGACY

    with pytest.raises(DeclarationStorageError, match="closed permanently: MIG-5"):
        store.declare(declaration())
    store.close()


def test_a_current_file_refuses_a_historical_record(tmp_path):
    store = SqliteVendorDeclarations(str(tmp_path / "v.sqlite3"), tenant_id=TENANT)
    with pytest.raises(ContractViolation, match="historical shape"):
        store.declare(legacy_declaration())
    assert store.count() == 0
    store.close()


def test_an_unknown_schema_version_is_refused_rather_than_guessed(tmp_path):
    path = tmp_path / "future.sqlite3"
    _write_legacy_file(path, legacy_declaration(),
                       schema_version="vendor_dependency.sqlite.v9")
    with pytest.raises(DeclarationStorageError, match="does not know"):
        SqliteVendorDeclarations(str(path), tenant_id=TENANT)


# --------------------------------------------------------------------------- #
# The reference is recorded, never resolved
# --------------------------------------------------------------------------- #
def test_nothing_here_resolves_a_binding_against_a_published_document():
    """A package forbidden to resolve policy_ref is not about to resolve this either."""

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


def test_the_helpers_refuse_the_wrong_shape_rather_than_coercing_it():
    with pytest.raises(ContractViolation, match="takes a VocabularyBinding"):
        vocabulary_binding_to_dict("assessment-state@1.0.0")  # type: ignore[arg-type]
    assert vocabulary_binding_to_dict(None) is None

    with pytest.raises(ContractViolation, match="mapping"):
        vocabulary_binding_from_dict("assessment-state@1.0.0", "binding")
    with pytest.raises(ContractViolation, match="unknown fields"):
        vocabulary_binding_from_dict(
            {"vocabulary": "x", "version": "1.0.0",
             "specification_digest": "sha256:" + "1" * 64, "resolved_at": "now"}, "binding")
    assert vocabulary_binding_from_dict(None, "binding") is None
    assert vocabulary_binding_from_dict({}, "binding") is None


def test_a_refusal_from_a_mapping_keeps_the_precise_reason():
    """ContractViolation is a ValueError, so a broad ``except`` would swallow it."""

    with pytest.raises(ContractViolation, match="MAJOR.MINOR.PATCH"):
        vocabulary_binding_from_dict(
            {"vocabulary": "x", "version": "1.0", "specification_digest": "sha256:" + "1" * 64},
            "binding")
    with pytest.raises(ContractViolation, match="whatever is current"):
        vocabulary_binding_from_dict(
            {"vocabulary": "x", "version": "latest",
             "specification_digest": "sha256:" + "1" * 64}, "binding")


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


def _write_legacy_file(path: pathlib.Path, old: VendorDependencyDeclaration,
                       schema_version: str = LEGACY_SCHEMA_VERSION) -> None:
    """A file exactly as 0.2.0 wrote one: v1 schema row, v1 record projection."""

    connection = sqlite3.connect(str(path), isolation_level=None)
    connection.execute(
        "CREATE TABLE declarations (seq INTEGER PRIMARY KEY AUTOINCREMENT,"
        " declaration_id TEXT NOT NULL UNIQUE, tenant_id TEXT NOT NULL,"
        " vendor_ref TEXT NOT NULL, system_id TEXT NOT NULL, system_version TEXT NOT NULL,"
        " risk_posture_label TEXT NOT NULL, policy_ref TEXT NOT NULL,"
        " supersedes TEXT NOT NULL, record_digest TEXT NOT NULL, record_json TEXT NOT NULL)")
    connection.execute(
        "CREATE TABLE declarations_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.execute("INSERT INTO declarations_meta VALUES ('schema_version', ?)",
                       (schema_version,))
    connection.execute("INSERT INTO declarations_meta VALUES ('tenant_id', ?)", (TENANT,))
    connection.execute(
        "INSERT INTO declarations(declaration_id, tenant_id, vendor_ref, system_id, "
        "system_version, risk_posture_label, policy_ref, supersedes, record_digest, "
        "record_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (old.declaration_id, old.tenant_id, old.vendor_ref, old.system_id,
         old.system_version, old.risk_posture.label, old.policy_ref, old.supersedes,
         old.record_digest(),
         json.dumps(declaration_record(old), sort_keys=True, separators=(",", ":"))))
    connection.close()
