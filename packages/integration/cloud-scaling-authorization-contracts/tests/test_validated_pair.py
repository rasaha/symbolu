"""The validated-pair discipline: nothing is re-read after it has been validated.

``reconcile_phase4`` reads each source value exactly once and *returns* what it read.
``build_capacity_authorization_candidate`` then builds from those returned values. If the
builder instead re-read ``projection``/``decision`` after validation, a check-then-use
window would open: a value that passed validation on the first read could differ on the
second, and the second is the one that would reach the candidate digest.

Proving this needs care. The exact-type gate refuses subclasses, so a diverting subclass
cannot even get in — which is good for security but useless as instrumentation. Instead the
tests below install a counting **data descriptor on the genuine class**, so the instance
stays exactly the right type and every attribute read is observed. The count is sampled at
the instant ``reconcile_phase4`` returns; any read after that instant is a re-read.

This is the regression test named in the gate-removal matrix: reintroducing a
post-validation source re-read into the builder makes ``test_no_post_validation_source_reread``
fail.
"""

from __future__ import annotations

import contextlib

import pytest

from conftest import coordinate_for

from ugence_cloud_scaling_authorization_contracts import candidate as candidate_module
from ugence_cloud_scaling_authorization_contracts import (
    build_capacity_authorization_candidate,
)
from ugence_cloud_scaling_risk_integration import CapacityRiskSubjectProjection
from risk_authority.integrations import SubjectRiskDecision


@contextlib.contextmanager
def counting_attribute(cls, name, counter):
    """Replace ``cls.name`` with a data descriptor that counts reads and returns the value.

    The instance keeps its exact type, so the package's exact-type admission still applies —
    this observes the real production path rather than a weakened one.
    """

    original = cls.__dict__.get(name, None)

    def _get(instance):
        counter.append(name)
        return instance.__dict__[name]

    setattr(cls, name, property(_get))
    try:
        yield
    finally:
        if original is None:
            delattr(cls, name)
        else:  # pragma: no cover - these names are plain dataclass fields
            setattr(cls, name, original)


@contextlib.contextmanager
def sampling_reconciler(counter, sample):
    """Record the read count at the exact moment reconciliation returns."""

    original = candidate_module.reconcile_phase4

    def _wrapped(projection, decision):
        facts = original(projection, decision)
        sample.append(len(counter))
        return facts

    candidate_module.reconcile_phase4 = _wrapped
    try:
        yield
    finally:
        candidate_module.reconcile_phase4 = original


@pytest.mark.parametrize(
    "cls,attribute",
    [
        (CapacityRiskSubjectProjection, "context"),
        (CapacityRiskSubjectProjection, "tenant_id"),
        (CapacityRiskSubjectProjection, "recommendation_digest"),
        (CapacityRiskSubjectProjection, "request_digest"),
        (SubjectRiskDecision, "decision_snapshot"),
        (SubjectRiskDecision, "tenant_id"),
    ],
)
def test_no_post_validation_source_reread(
    projection, decision, attestation, target_scope, policy_binding, cls, attribute
):
    """The builder must not read any source attribute after reconciliation returned."""

    counter: list[str] = []
    sample: list[int] = []
    with counting_attribute(cls, attribute, counter), sampling_reconciler(counter, sample):
        built = build_capacity_authorization_candidate(
            projection=projection,
            decision=decision,
            producer_attestation=attestation,
            policy_binding=policy_binding,
            policy_coordinate_binding=coordinate_for(policy_binding),
            target_scope=target_scope,
        )

    assert built is not None
    assert sample, "the reconciler wrapper was not invoked"
    reads_after_validation = len(counter) - sample[0]
    assert reads_after_validation == 0, (
        f"{cls.__name__}.{attribute} was read {reads_after_validation} time(s) after "
        "reconciliation completed — a check-then-use window is open"
    )


def test_reconciliation_reads_each_source_attribute_at_most_once(projection, decision):
    """Within reconciliation itself, a single read per attribute closes the same window."""

    from ugence_cloud_scaling_authorization_contracts import reconcile_phase4

    for cls, attribute in (
        (CapacityRiskSubjectProjection, "tenant_id"),
        (CapacityRiskSubjectProjection, "request_digest"),
        (CapacityRiskSubjectProjection, "recommendation_digest"),
        (SubjectRiskDecision, "tenant_id"),
        (SubjectRiskDecision, "decision_digest"),
    ):
        counter: list[str] = []
        with counting_attribute(cls, attribute, counter):
            reconcile_phase4(projection, decision)
        assert len(counter) <= 1, (
            f"{cls.__name__}.{attribute} was read {len(counter)} times during "
            "reconciliation; each source value must be read exactly once"
        )


def test_the_builder_consumes_the_returned_facts_not_the_sources(
    projection, decision, attestation, target_scope, policy_binding
):
    """A reconciler returning different facts changes the candidate — proof of consumption.

    If the builder were quietly re-deriving from the sources, substituting the reconciler's
    return value would not change the result. It does, so the returned record is genuinely
    what the candidate is built from.
    """

    original = candidate_module.reconcile_phase4
    import dataclasses

    def _shifted(p, d):
        facts = original(p, d)
        return dataclasses.replace(facts, subject_id=facts.subject_id + "-shifted")

    candidate_module.reconcile_phase4 = _shifted
    try:
        built = build_capacity_authorization_candidate(
            projection=projection, decision=decision, producer_attestation=attestation,
            policy_binding=policy_binding,
            policy_coordinate_binding=coordinate_for(policy_binding),
            target_scope=target_scope,
        )
    finally:
        candidate_module.reconcile_phase4 = original

    assert built.subject_id.endswith("-shifted")
    assert built.subject_id != projection.subject_id
