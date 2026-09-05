"""`ACC-IA-4` — preflight replays every pre-signing check and mutates nothing.

Each check the dry run reports is exercised in both directions, and the
mutation-free claim is proven with the authority's own recording wrappers: a
preflight over a recording signer and registry leaves the signer never asked to
sign and the registry byte-identical — including on a run whose report is all
green.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta

import pytest
from _activation_fixtures import (
    GLOBAL_TENANT,
    T_ISSUE,
    make_first_constitution,
    make_runtime_approval,
    make_world,
)
from _authority_fixtures import (
    RecordingApprovalVerifier,
    RecordingRegistry,
    RecordingSigner,
    registry_snapshot,
)
from ugence_agent_constitution_activation import (
    ActivationRequestError,
    PreflightCheck,
    PreflightReport,
    build_activation_root,
    preflight_issuance,
)
from ugence_agent_constitution_policy import (
    LIFECYCLE_DRAFT,
    PLACEHOLDER_CONTENT_DIGEST,
)
from ugence_policy_authority.api import ApprovalEvidenceRef


@pytest.fixture()
def world():
    return make_world()


def _preflight(world, policy, **overrides):
    kwargs = dict(
        policy=policy,
        record_id="rec-preflight",
        approval=world.evidence,
        as_of=T_ISSUE,
    )
    kwargs.update(overrides)
    return world.root.preflight_issuance(**kwargs)


def _row(report, name):
    rows = {check.name: check for check in report.checks}
    assert name in rows, f"no {name!r} row in {sorted(rows)}"
    return rows[name]


# --------------------------------------------------------------------------- #
# The green path
# --------------------------------------------------------------------------- #


def test_a_lawful_issuance_preflights_ready(world):
    report = _preflight(world, make_first_constitution())
    assert report.ready is True
    assert {check.name for check in report.checks} == {
        "artifact-recognition",
        "supersession",
        "body-digest",
        "lifecycle",
        "effectivity",
        "approval",
    }
    assert all(check.ok for check in report.checks)
    assert len(report.policy_body_digest) == 64


def test_the_reference_tenant_row_appears_only_when_asked(world):
    policy = make_first_constitution()
    without = _preflight(world, policy)
    assert "reference-tenant" not in {c.name for c in without.checks}
    with_row = _preflight(
        world, policy, expected_reference_tenant_id=GLOBAL_TENANT
    )
    assert _row(with_row, "reference-tenant").ok is True
    mismatched = _preflight(
        world, policy, expected_reference_tenant_id="tenant-9"
    )
    assert _row(mismatched, "reference-tenant").ok is False
    assert mismatched.ready is False


# --------------------------------------------------------------------------- #
# Each check, red
# --------------------------------------------------------------------------- #


def test_an_unrecognized_artifact_stops_the_run(world):
    report = _preflight(world, object())
    assert [check.name for check in report.checks] == ["artifact-recognition"]
    assert report.ready is False
    assert report.policy_body_digest == ""


def test_a_declared_supersession_reference_reports_red(world):
    policy = make_first_constitution(supersedes_ref="some-earlier-version")
    report = _preflight(world, policy)
    assert _row(report, "supersession").ok is False
    assert report.ready is False


def test_a_forged_content_digest_reports_red(world):
    lawful = make_first_constitution()
    forged = dataclasses.replace(
        lawful,
        metadata=dataclasses.replace(
            lawful.metadata, content_digest=PLACEHOLDER_CONTENT_DIGEST
        ),
    )
    report = _preflight(world, forged)
    assert _row(report, "body-digest").ok is False
    assert report.ready is False


def test_an_inactive_lifecycle_reports_red(world):
    policy = make_first_constitution(lifecycle_state=LIFECYCLE_DRAFT)
    report = _preflight(world, policy)
    assert _row(report, "lifecycle").ok is False


def test_an_elapsed_effective_period_reports_red(world):
    policy = make_first_constitution(effective_to=T_ISSUE + timedelta(days=1))
    report = _preflight(world, policy, as_of=T_ISSUE + timedelta(days=2))
    assert _row(report, "effectivity").ok is False


def test_an_unbounded_window_admits_any_later_instant(world):
    policy = make_first_constitution()
    report = _preflight(world, policy, as_of=T_ISSUE + timedelta(days=3650))
    assert _row(report, "effectivity").ok is True


def test_missing_approval_evidence_reports_red_not_raising(world):
    absent = ApprovalEvidenceRef(
        approval_ref="APPROVAL-NOBODY-HOLDS",
        approval_digest="ab" * 32,
        approving_authority_id="ugence.governance.policy-approval-board",
    )
    report = _preflight(world, make_first_constitution(), approval=absent)
    assert _row(report, "approval").ok is False
    assert report.ready is False


def test_a_raising_verifier_reports_red_not_raising():
    class _Raising:
        def verify_approval(self, **kwargs):
            raise RuntimeError("verifier fell over")

    world = make_world(approval_verifier=_Raising())
    report = _preflight(world, make_first_constitution())
    assert _row(report, "approval").ok is False


def test_a_verifier_answer_binding_a_different_digest_reports_red():
    verifier = RecordingApprovalVerifier(override_body_digest="cd" * 32)
    world = make_world(approval_verifier=verifier)
    report = _preflight(world, make_first_constitution())
    assert _row(report, "approval").ok is False


def test_an_approved_window_outside_the_instant_reports_red():
    verifier = RecordingApprovalVerifier(
        approved_from=T_ISSUE + timedelta(days=1)
    )
    world = make_world(approval_verifier=verifier)
    report = _preflight(world, make_first_constitution())
    assert _row(report, "approval").ok is False


# --------------------------------------------------------------------------- #
# Alien inputs raise; policy findings never do
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "overrides",
    [
        dict(record_id=""),
        dict(record_id=7),
        dict(approval="not-evidence"),
        dict(as_of=datetime(2026, 9, 1)),
        dict(expected_reference_tenant_id=7),
    ],
    ids=["empty-record-id", "non-str-record-id", "loose-approval", "naive-as-of",
         "non-str-tenant"],
)
def test_alien_inputs_raise_a_typed_request_error(world, overrides):
    with pytest.raises(ActivationRequestError):
        _preflight(world, make_first_constitution(), **overrides)


def test_the_standalone_function_requires_its_own_wiring(world):
    with pytest.raises(ActivationRequestError):
        preflight_issuance(
            policy=make_first_constitution(),
            record_id="rec-1",
            approval=world.evidence,
            approval_verifier=None,
            adapters=world.root._adapters,
            as_of=T_ISSUE,
        )
    with pytest.raises(ActivationRequestError):
        preflight_issuance(
            policy=make_first_constitution(),
            record_id="rec-1",
            approval=world.evidence,
            approval_verifier=world.approval_verifier,
            adapters="not-a-registry",
            as_of=T_ISSUE,
        )


# --------------------------------------------------------------------------- #
# Mutation-freedom, proven with recording wrappers
# --------------------------------------------------------------------------- #


def test_preflight_signs_nothing_and_stores_nothing():
    from _activation_fixtures import make_ephemeral_signer

    signer = RecordingSigner(inner=make_ephemeral_signer())
    registry = RecordingRegistry()
    evidence, verifier = make_runtime_approval()
    root = build_activation_root(
        registry=registry,
        signer=signer,
        signature_verifier=_AnyVerifier(),
        approval_verifier=verifier,
    )
    before = registry_snapshot(registry)
    report = root.preflight_issuance(
        policy=make_first_constitution(),
        record_id="rec-dry",
        approval=evidence,
        as_of=T_ISSUE,
    )
    assert report.ready is True
    assert signer.calls == [], "preflight asked the signer to sign"
    assert registry.appends == [], "preflight appended an issuance"
    assert registry_snapshot(registry) == before


class _AnyVerifier:
    """Shape-only stand-in for the signature verifier, never consulted here."""

    def verify(self, **kwargs):
        raise AssertionError("preflight consulted the signature verifier")


# --------------------------------------------------------------------------- #
# The report shapes validate themselves
# --------------------------------------------------------------------------- #


def test_report_shapes_refuse_alien_content():
    with pytest.raises(ActivationRequestError):
        PreflightCheck(name="", ok=True)
    with pytest.raises(ActivationRequestError):
        PreflightCheck(name="x", ok="yes")
    with pytest.raises(ActivationRequestError):
        PreflightReport(checks=())
    with pytest.raises(ActivationRequestError):
        PreflightReport(checks=("not-a-check",))


def test_ready_is_the_conjunction_of_every_row():
    good = PreflightCheck(name="a", ok=True)
    bad = PreflightCheck(name="b", ok=False, detail="because")
    assert PreflightReport(checks=(good,)).ready is True
    assert PreflightReport(checks=(good, bad)).ready is False
