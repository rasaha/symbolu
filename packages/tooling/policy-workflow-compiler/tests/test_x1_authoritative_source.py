"""PA/PWC-X1 — authoritative-source carriage and its validation.

The compiler attests **carriage, not authenticity**: that a reference is present
where required, well-formed, complete and internally consistent. It never verifies a
signature, establishes key trust, or consults revocation state, and it imports
nothing from Policy Authority. These tests hold both halves of that claim.
"""

from __future__ import annotations

import pathlib
import re

import ugence_policy_workflow_compiler.api as api
from ugence_policy_workflow_compiler.approval.records import (
    build_approval_record,
    compute_pack_digest,
)
from ugence_policy_workflow_compiler.models.common import SCHEMA_VERSION_V2
from ugence_policy_workflow_compiler.models.declarations import AuthoritativeSourceRef
from ugence_policy_workflow_compiler.reference.procurement import (
    build_procurement_approval_fixture,
    build_procurement_policy_pack,
)
from ugence_policy_workflow_compiler.semantics import compile_workflow_v2
from ugence_policy_workflow_compiler.validation.authoritative_source import (
    check_authoritative_source,
    check_release_source_agreement,
    coordinate_string,
)

PINNED_PACK_DIGEST = "sha256:28eedf60892bc1b3e9f8c15c56d43b0aa353659c8158a793f94168a81de98b14"
PINNED_V1_RELEASE_DIGEST = "sha256:fb9fd4b934cb94425a67b0f6b469ca0bbc198b356cd265822c3550ad9938158a"
PINNED_V1_IR_DIGEST = "sha256:169ad24c09e45ac7176a75a2708ff4687085f2f8f878990862542df0c20ca1e1"
PINNED_V2_FINGERPRINT = "sha256:2e031c78918f5d62378d460a6e1efd311f823ba234576f33ba8097739b29a0d7"


def _source(**overrides):
    fields = {
        "policy_family": "procurement",
        "policy_id": "policy.purchase_approval",
        "policy_version": "4",
        "content_digest": "sha256:" + "a" * 64,
        "scope": "global",
        "tenant_id": "tenant-1",
        "record_id": "rec-1",
        "policy_body_digest": "sha256:" + "b" * 64,
        "issuing_authority_id": "authority.policy",
        "key_id": "key-1",
        "signature_alg": "ed25519",
        "signature_b64": "c2ln",
        "approving_authority_id": "authority.approval",
        "approval_ref": "approval/1",
        "approval_digest": "sha256:" + "c" * 64,
        "issued_at": "2026-09-06T00:00:00Z",
        "resolved_as_of": "2026-09-06T00:00:00Z",
    }
    fields.update(overrides)
    return AuthoritativeSourceRef(**fields)


def _v1():
    pack = build_procurement_policy_pack()
    return pack, build_procurement_approval_fixture(pack)


def _v2(source):
    pack = build_procurement_policy_pack().model_copy(
        update={"schema_version": SCHEMA_VERSION_V2, "authoritative_source": source}
    )
    approval = build_approval_record(
        approval_id="approval-x1",
        pack=pack,
        reviewer_id="reviewer-1",
        reviewer_role="approver",
        is_fixture=True,
    )
    return pack, approval


# -- the boundary --------------------------------------------------------------


def test_nothing_imports_policy_authority():
    root = pathlib.Path(__file__).resolve().parent.parent / "src" / "ugence_policy_workflow_compiler"
    banned = re.compile(r"ugence_policy_authority|policy-authority|from\s+ugence_policy_authority")
    offenders = [
        str(module.relative_to(root))
        for module in root.rglob("*.py")
        if banned.search(module.read_text())
    ]
    assert offenders == [], offenders


def test_maturity_separates_carriage_from_verification():
    info = api.version_info().to_dict()
    assert info["authoritative_source_carriage_implemented"] is True
    # The compiler never claims to have verified an issuance.
    assert info["authoritative_source_verification_implemented"] is False


def test_no_diagnostic_implies_an_authenticity_check():
    # Carriage vocabulary only: nothing here may read as "signature valid",
    # "key trusted" or "not revoked".
    # A whitespace-only value passes the model's min_length and is caught by the
    # coordinate check — which is why that check strips rather than tests truthiness.
    pack, _ = _v2(_source(policy_family=" "))
    codes = {d.code for d in check_authoritative_source(pack)}
    banned = {"SIGNATURE", "REVOK", "KEY_TRUST", "AUTHENTIC", "VERIFIED"}
    for code in codes:
        assert not any(word in code for word in banned), code


# -- v1 is untouched -----------------------------------------------------------


def test_v1_digests_and_approval_are_unchanged():
    pack, approval = _v1()
    assert compute_pack_digest(pack) == PINNED_PACK_DIGEST
    result = api.compile_policy_pack(pack, approval)
    assert result.success
    assert result.logical_digest == PINNED_V1_RELEASE_DIGEST
    assert result.workflow_ir.logical_digest() == PINNED_V1_IR_DIGEST
    assert compile_workflow_v2(pack, approval).workflow_fingerprint == PINNED_V2_FINGERPRINT


def test_a_v1_pack_carries_no_coordinate_in_its_manifest():
    pack, approval = _v1()
    manifest = api.compile_policy_pack(pack, approval).compiled_package.manifest
    assert manifest.authoritative_source_coordinate == ""


# -- carriage ------------------------------------------------------------------


def test_a_v2_pack_binds_its_source_and_denormalizes_the_coordinate():
    pack, approval = _v2(_source())
    result = api.compile_policy_pack(pack, approval)
    assert result.success, [d.message for d in result.validation_report.diagnostics]
    manifest = result.compiled_package.manifest
    assert manifest.authoritative_source_coordinate == coordinate_string(
        pack.authoritative_source
    )
    # The binding is the pack's own reference, which a v2 digest commits to.
    assert result.compiled_package.policy_pack.authoritative_source == pack.authoritative_source


def test_the_manifest_coordinate_is_outside_the_logical_digest():
    pack, approval = _v2(_source())
    result = api.compile_policy_pack(pack, approval)
    payload = result.compiled_package.logical_payload()
    assert "manifest" not in payload
    assert result.compiled_package.recompute_digest() == result.logical_digest


def test_a_well_formed_source_raises_nothing():
    pack, _ = _v2(_source())
    assert check_authoritative_source(pack, required=True) == []


# -- fail closed ---------------------------------------------------------------


def test_missing_source_is_raised_only_when_required():
    pack, _ = _v2(None)
    assert check_authoritative_source(pack) == []
    codes = {d.code for d in check_authoritative_source(pack, required=True)}
    assert codes == {"MISSING_AUTHORITATIVE_SOURCE"}


def test_an_incomplete_coordinate_is_refused():
    pack, approval = _v2(_source(record_id=" "))
    codes = {d.code for d in check_authoritative_source(pack)}
    assert "MALFORMED_AUTHORITATIVE_COORDINATE" in codes
    assert api.compile_policy_pack(pack, approval).success is False


def test_a_non_digest_shaped_value_is_refused():
    pack, _ = _v2(_source(content_digest="not-a-digest"))
    assert "MALFORMED_AUTHORITATIVE_COORDINATE" in {
        d.code for d in check_authoritative_source(pack)
    }


def test_a_partial_attestation_is_refused():
    # All-or-none, mirroring Policy Authority's own descriptor rule: a partial
    # attestation looks checkable and is not.
    pack, _ = _v2(_source(signature_b64=""))
    assert "INCOMPLETE_ISSUANCE_ATTESTATION" in {
        d.code for d in check_authoritative_source(pack)
    }


def test_no_attestation_at_all_is_accepted():
    pack, _ = _v2(
        _source(issuing_authority_id="", key_id="", signature_alg="", signature_b64="")
    )
    assert check_authoritative_source(pack) == []


def test_manifest_drift_from_the_pack_is_refused():
    pack, _ = _v2(_source())
    diags = check_release_source_agreement(
        pack.authoritative_source, "some/other/coordinate", pack.pack_id
    )
    assert [d.code for d in diags] == ["AUTHORITATIVE_SOURCE_MISMATCH"]
    assert check_release_source_agreement(
        pack.authoritative_source,
        coordinate_string(pack.authoritative_source),
        pack.pack_id,
    ) == []


def test_a_v1_pack_carrying_a_source_is_refused_by_the_schema_gate():
    pack, approval = _v1()
    smuggled = pack.model_copy(update={"authoritative_source": _source()})
    result = api.compile_policy_pack(smuggled, approval)
    assert result.success is False
    assert "V2_FIELD_IN_V1_PACK" in {
        d.code for d in result.validation_report.diagnostics
    }
