"""The five fail-closed requirements, and the derivation that follows them."""

from __future__ import annotations

import pytest
from ugence_policy_authority.api import (
    PolicyResolutionReason,
    PolicyResolutionStatus,
)
from ugence_policy_workflow_compiler.api import (
    check_authoritative_source,
    compile_policy_pack,
    compute_pack_digest,
)
from ugence_policy_workflow_compiler.approval.records import build_approval_record

import _fixtures as fx
from ugence_authoritative_policy_compilation import (
    AuthoritativeCompilationError,
    AuthoritativePolicyCompilationService,
    RefusalCode,
)

SERVICE = AuthoritativePolicyCompilationService()


def _draft(resolution=None, **kw):
    kw.setdefault("requested_coordinate", fx.coordinate())
    kw.setdefault("pack_builder", fx.pack_builder)
    return SERVICE.draft_from_resolution(resolution or fx.resolution(), **kw)


def _refusal(resolution=None, **kw) -> RefusalCode:
    with pytest.raises(AuthoritativeCompilationError) as excinfo:
        _draft(resolution, **kw)
    return excinfo.value.code


# -- the happy path ------------------------------------------------------------


def test_a_verified_resolution_yields_a_compilable_draft():
    draft = _draft()
    assert draft.pack.authoritative_source is not None
    assert draft.pack_digest == compute_pack_digest(draft.pack)
    assert check_authoritative_source(draft.pack, required=True) == []


def test_the_derived_reference_mirrors_the_resolution():
    resolution = fx.resolution()
    source = _draft(resolution).authoritative_source
    coordinate = resolution.record.coordinate
    assert source.policy_family == coordinate.policy_family
    assert source.policy_id == coordinate.policy_id
    assert source.policy_version == coordinate.version
    assert source.scope == coordinate.scope
    assert source.tenant_id == coordinate.tenant_id
    assert source.record_id == resolution.record.record_id
    assert source.issuing_authority_id == resolution.record.issuing_authority_id
    assert source.historical is False


def test_digest_conventions_are_translated_losslessly():
    # Policy Authority states bare hex; the compiler states sha256:<hex>. The hex
    # is carried through unaltered — only the prefix differs.
    resolution = fx.resolution()
    source = _draft(resolution).authoritative_source
    assert source.content_digest == f"sha256:{resolution.record.coordinate.content_digest}"
    assert source.policy_body_digest == f"sha256:{resolution.record.policy_body_digest}"


def test_the_draft_compiles_once_a_human_has_approved_its_digest():
    # Ruling CR-1: the root returns the pack; approval happens outside it.
    draft = _draft()
    approval = build_approval_record(
        approval_id="approval-1",
        pack=draft.pack,
        reviewer_id="reviewer-1",
        reviewer_role="approver",
        is_fixture=True,
    )
    assert approval.policy_pack_digest == draft.pack_digest
    result = compile_policy_pack(draft.pack, approval)
    assert result.success, [d.message for d in result.validation_report.diagnostics]


# -- the five requirements -----------------------------------------------------


def test_an_unresolved_answer_is_refused():
    unresolved = fx.resolution(
        status=PolicyResolutionStatus.UNRESOLVED,
        reason=PolicyResolutionReason.NOT_FOUND,
    )
    assert _refusal(unresolved) is RefusalCode.POLICY_NOT_RESOLVED


def test_an_answer_about_another_coordinate_is_refused():
    other = fx.coordinate(policy_id="policy.something_else")
    assert (
        _refusal(requested_coordinate=other) is RefusalCode.RESOLVED_COORDINATE_MISMATCH
    )


def test_a_missing_descriptor_is_refused():
    # Without the descriptor triple the body digest cannot be re-verified here.
    assert (
        _refusal(fx.resolution(with_descriptor=False))
        is RefusalCode.INCOMPLETE_RESOLUTION_DESCRIPTOR
    )


def test_a_body_digest_that_does_not_recompute_is_refused():
    coordinate = fx.coordinate()
    record = fx.issued_record(coordinate, body_digest="d" * 64)
    assert (
        _refusal(fx.resolution(coord=coordinate, record=record))
        is RefusalCode.BODY_DIGEST_MISMATCH
    )


def test_a_historical_answer_is_refused_unless_asked_for():
    historical = fx.resolution(historical=True)
    assert (
        _refusal(historical) is RefusalCode.HISTORICAL_RESOLUTION_NOT_REQUESTED
    )
    draft = _draft(historical, allow_historical=True)
    assert draft.authoritative_source.historical is True


# -- the derivation prohibition ------------------------------------------------


def test_a_builder_supplied_reference_is_refused():
    def authoring_builder(artifact):
        pack = fx.pack_builder(artifact)
        return pack.model_copy(
            update={"authoritative_source": _draft().authoritative_source}
        )

    assert (
        _refusal(pack_builder=authoring_builder) is RefusalCode.AUTHORED_SOURCE_REFUSED
    )


def test_no_builder_is_refused():
    # Ruling CR-2: families supply the mapping; this root ships none.
    assert _refusal(pack_builder=None) is RefusalCode.NO_PACK_BUILDER


def test_a_v1_pack_from_a_builder_is_refused():
    def v1_builder(artifact):
        return fx.pack_builder(artifact).model_copy(
            update={"schema_version": "policy_pack.v1"}
        )

    assert (
        _refusal(pack_builder=v1_builder) is RefusalCode.BUILDER_RETURNED_UNUSABLE_PACK
    )


# -- resolution seam -----------------------------------------------------------


def test_draft_from_coordinate_delegates_to_the_injected_resolver():
    calls = {}

    def resolver(**kwargs):
        calls.update(kwargs)
        return fx.resolution()

    draft = SERVICE.draft_from_coordinate(
        coordinate=fx.coordinate(),
        as_of=fx.AS_OF,
        registry=object(),
        signature_verifier=object(),
        adapters=object(),
        pack_builder=fx.pack_builder,
        resolver=resolver,
    )
    assert draft.pack.authoritative_source is not None
    # Trust is passed through, never constructed here.
    for key in ("registry", "signature_verifier", "adapters", "as_of", "reference"):
        assert key in calls
