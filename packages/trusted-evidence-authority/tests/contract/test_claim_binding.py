"""Claim/metric identity and units/measurement semantics (ADR §9 rows 11-12).

Audit finding A-02. These two rows are ratified evidence coordinates and were
absent: row 11 requires "claim or metric identity ... absent for raw non-metric
evidence, **explicitly**", and row 12 makes "units and measurement semantics"
required whenever row 11 is present.

The tests establish the co-requirement behaviorally — every permitted and every
forbidden combination — rather than asserting a validator was called.
"""

from __future__ import annotations

import dataclasses
import itertools

import pytest
from _builders import claim, identity
from ugence_trusted_evidence_authority.api import (
    ApplicabilityDeclaration,
    CanonicalEvidenceIdentity,
    EvidenceClaimBinding,
    TrustedEvidenceContractError,
)

GROUP = ("claim_ref", "metric_ref", "unit", "measurement_semantics_ref")


def test_declared_field_order_is_pinned():
    assert [f.name for f in dataclasses.fields(EvidenceClaimBinding)] == [
        "applicability",
        *GROUP,
    ]


def test_the_claim_binding_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        claim().claim_ref = "other"


def test_identity_carries_the_claim_between_scope_and_provenance():
    """Declared order follows the ADR's own row order: 7-10, 11-12, 13."""

    names = [f.name for f in dataclasses.fields(CanonicalEvidenceIdentity)]
    assert names.index("scope") < names.index("claim") < names.index("provenance")


# --------------------------------------------------------------------------- #
# Applicability is declared, never inferred
# --------------------------------------------------------------------------- #

def test_applicability_has_no_default():
    field = {f.name: f for f in dataclasses.fields(EvidenceClaimBinding)}["applicability"]
    assert field.default is dataclasses.MISSING
    assert field.default_factory is dataclasses.MISSING
    with pytest.raises(TypeError):
        EvidenceClaimBinding()


def test_the_identity_cannot_omit_the_claim_coordinate():
    with pytest.raises(TypeError):
        CanonicalEvidenceIdentity(
            **{
                f.name: getattr(identity(), f.name)
                for f in dataclasses.fields(CanonicalEvidenceIdentity)
                if f.name != "claim"
            }
        )


def test_not_applicable_is_a_recorded_decision_not_an_empty_value():
    declared = EvidenceClaimBinding.not_applicable()
    assert declared.applicability is ApplicabilityDeclaration.NOT_APPLICABLE
    assert all(getattr(declared, n) == "" for n in GROUP)
    # It is a distinct decision, digest-visible, not an accidental absence.
    assert (
        identity(claim=declared).canonical_digest()
        != identity(claim=claim()).canonical_digest()
    )


# --------------------------------------------------------------------------- #
# The co-requirement, exhaustively
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "kwargs",
    [
        dict(claim_ref="c", metric_ref="", unit="u", measurement_semantics_ref="s"),
        dict(claim_ref="", metric_ref="m", unit="u", measurement_semantics_ref="s"),
        dict(claim_ref="c", metric_ref="m", unit="u", measurement_semantics_ref="s"),
    ],
)
def test_applicable_accepts_claim_or_metric_or_both_with_full_units(kwargs):
    """Row 11 is 'claim **or** metric identity'; row 12 is co-required."""

    built = EvidenceClaimBinding(
        applicability=ApplicabilityDeclaration.APPLICABLE, **kwargs
    )
    assert built.applicability is ApplicabilityDeclaration.APPLICABLE


def test_applicable_without_a_claim_or_metric_is_refused():
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        EvidenceClaimBinding(
            applicability=ApplicabilityDeclaration.APPLICABLE,
            unit="u",
            measurement_semantics_ref="s",
        )
    assert "claim or a metric" in str(excinfo.value)


@pytest.mark.parametrize("missing", ["unit", "measurement_semantics_ref"])
def test_applicable_without_units_or_semantics_is_refused(missing):
    kwargs = dict(claim_ref="c", unit="u", measurement_semantics_ref="s")
    kwargs[missing] = ""
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        EvidenceClaimBinding(
            applicability=ApplicabilityDeclaration.APPLICABLE, **kwargs
        )
    assert "row 12" in str(excinfo.value)
    assert missing in str(excinfo.value)


def test_applicable_with_neither_units_nor_semantics_is_refused():
    with pytest.raises(TrustedEvidenceContractError):
        EvidenceClaimBinding(
            applicability=ApplicabilityDeclaration.APPLICABLE, claim_ref="c"
        )


@pytest.mark.parametrize("populated", GROUP)
def test_not_applicable_with_any_populated_coordinate_is_refused(populated):
    with pytest.raises(TrustedEvidenceContractError) as excinfo:
        EvidenceClaimBinding(
            applicability=ApplicabilityDeclaration.NOT_APPLICABLE, **{populated: "x"}
        )
    assert "NOT_APPLICABLE" in str(excinfo.value)
    assert populated in str(excinfo.value)


def test_every_partial_combination_fails_closed():
    """Exhaustive over the 16 populated/empty patterns of the group.

    Only two shapes are admissible: all-empty under ``NOT_APPLICABLE``, and a
    claim-or-metric with both unit coordinates under ``APPLICABLE``. Every other
    pattern is refused under both declarations.
    """

    admitted_applicable = 0
    for pattern in itertools.product([False, True], repeat=len(GROUP)):
        kwargs = {name: ("x" if flag else "") for name, flag in zip(GROUP, pattern)}
        has_identity = bool(kwargs["claim_ref"] or kwargs["metric_ref"])
        has_units = bool(kwargs["unit"] and kwargs["measurement_semantics_ref"])

        # APPLICABLE
        if has_identity and has_units:
            EvidenceClaimBinding(
                applicability=ApplicabilityDeclaration.APPLICABLE, **kwargs
            )
            admitted_applicable += 1
        else:
            with pytest.raises(TrustedEvidenceContractError):
                EvidenceClaimBinding(
                    applicability=ApplicabilityDeclaration.APPLICABLE, **kwargs
                )

        # NOT_APPLICABLE
        if any(pattern):
            with pytest.raises(TrustedEvidenceContractError):
                EvidenceClaimBinding(
                    applicability=ApplicabilityDeclaration.NOT_APPLICABLE, **kwargs
                )
        else:
            EvidenceClaimBinding(
                applicability=ApplicabilityDeclaration.NOT_APPLICABLE, **kwargs
            )

    # claim / metric / both, each with both unit coordinates present.
    assert admitted_applicable == 3


def test_none_is_not_accepted_as_not_applicable():
    """An absent value is not a decision — ``None`` is refused outright."""

    for name in GROUP:
        with pytest.raises(TrustedEvidenceContractError):
            claim(**{name: None})


def test_an_empty_string_under_applicable_is_not_read_as_not_applicable():
    with pytest.raises(TrustedEvidenceContractError):
        EvidenceClaimBinding(
            applicability=ApplicabilityDeclaration.APPLICABLE,
            claim_ref="",
            metric_ref="",
            unit="",
            measurement_semantics_ref="",
        )


def test_a_declaration_lookalike_is_refused():
    with pytest.raises(TrustedEvidenceContractError):
        EvidenceClaimBinding(applicability="APPLICABLE", claim_ref="c", unit="u",
                             measurement_semantics_ref="s")


def test_a_claim_binding_lookalike_cannot_enter_the_identity():
    @dataclasses.dataclass(frozen=True)
    class Lookalike:
        applicability: object = ApplicabilityDeclaration.APPLICABLE
        claim_ref: str = "c"
        metric_ref: str = ""
        unit: str = "u"
        measurement_semantics_ref: str = "s"

    with pytest.raises(TrustedEvidenceContractError):
        identity(claim=Lookalike())


# --------------------------------------------------------------------------- #
# Convenience constructors
# --------------------------------------------------------------------------- #

def test_the_applicable_constructor_requires_units_by_keyword():
    built = EvidenceClaimBinding.applicable(
        claim_ref="c", unit="ratio", measurement_semantics_ref="s"
    )
    assert built.unit == "ratio"
    with pytest.raises(TypeError):
        EvidenceClaimBinding.applicable(claim_ref="c")


def test_claim_identity_exposes_every_replay_relevant_coordinate():
    assert claim().claim_identity == (
        "APPLICABLE",
        "claim-1",
        "metric-resolution-rate",
        "ratio",
        "semantics-1",
    )
    assert EvidenceClaimBinding.not_applicable().claim_identity == (
        "NOT_APPLICABLE",
        "",
        "",
        "",
        "",
    )


def test_the_identity_coordinate_tuple_includes_the_claim():
    base = identity().coordinate_identity
    assert identity(claim=claim(unit="percent")).coordinate_identity != base
    assert identity(claim=EvidenceClaimBinding.not_applicable()).coordinate_identity != base


# --------------------------------------------------------------------------- #
# Nothing is calculated
# --------------------------------------------------------------------------- #

def test_the_contract_records_identity_and_semantics_but_computes_nothing():
    """ADR §18 assigns comparison to the consuming evaluation engine."""

    forbidden = {"convert", "normalize", "compare", "evaluate", "calculate",
                 "to_base_unit", "value", "measure", "result"}
    assert not (set(dir(EvidenceClaimBinding)) & forbidden)
    # There is no numeric measurement field at all — only identity and semantics.
    for field in dataclasses.fields(EvidenceClaimBinding):
        assert field.type in ("str", "ApplicabilityDeclaration"), field
