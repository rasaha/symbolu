"""Adversarial tests for the M-3R.3 indicator catalogs.

Three questions are asked repeatedly, because they are the ones an untrusted
caller would attack:

1. Can a definition from one readiness family be passed off as another?
2. Can a catalog be made to say something a catalog must never say — that an
   indicator is *required*, weighted, scored, thresholded, or worth money?
3. Can a caller mutate, reorder or scalar-substitute their way past validation
   after construction?

The answer to each must be no, structurally.
"""

from __future__ import annotations

import dataclasses

import pytest

from ugence_uvi_policy_contracts.api import ReadinessTarget

from ugence_agent_value_readiness.api import (
    AdoptionDimension,
    AdoptionReadinessCatalog,
    AdoptionReadinessIndicatorDefinition,
    CapabilityDimension,
    CapabilityReadinessCatalog,
    CapabilityReadinessIndicatorDefinition,
    IntelligenceDimension,
    IntelligenceFitnessCatalog,
    IntelligenceFitnessIndicatorDefinition,
    ReadinessContractError,
    ReadinessIndicatorCatalogSet,
    ReadinessIndicatorClass,
)

PILOT = ReadinessTarget.PILOT
PROD = ReadinessTarget.PRODUCTION


def intel_def(indicator_id="i1", **kw):
    kw.setdefault("dimension", IntelligenceDimension.ACCURACY)
    kw.setdefault("metric_id", "accuracy")
    return IntelligenceFitnessIndicatorDefinition(indicator_id=indicator_id, **kw)


def cap_def(indicator_id="c1", **kw):
    kw.setdefault("dimension", CapabilityDimension.TOOL_READINESS)
    kw.setdefault("metric_id", "tool-coverage")
    return CapabilityReadinessIndicatorDefinition(indicator_id=indicator_id, **kw)


def ado_def(indicator_id="a1", **kw):
    kw.setdefault("dimension", AdoptionDimension.EXPECTED_UTILIZATION)
    kw.setdefault("metric_id", "expected-utilization")
    return AdoptionReadinessIndicatorDefinition(indicator_id=indicator_id, **kw)


# --------------------------------------------------------------------------- #
# Three distinct families
# --------------------------------------------------------------------------- #
def test_all_three_families_exist_and_report_their_own_class():
    assert intel_def().indicator_class is ReadinessIndicatorClass.INTELLIGENCE
    assert cap_def().indicator_class is ReadinessIndicatorClass.CAPABILITY
    assert ado_def().indicator_class is ReadinessIndicatorClass.ADOPTION

    assert (
        IntelligenceFitnessCatalog(catalog_id="k", catalog_version="1").family
        is ReadinessIndicatorClass.INTELLIGENCE
    )
    assert (
        CapabilityReadinessCatalog(catalog_id="k", catalog_version="1").family
        is ReadinessIndicatorClass.CAPABILITY
    )
    assert (
        AdoptionReadinessCatalog(catalog_id="k", catalog_version="1").family
        is ReadinessIndicatorClass.ADOPTION
    )


@pytest.mark.parametrize(
    "catalog_cls, foreign",
    [
        (IntelligenceFitnessCatalog, cap_def()),
        (IntelligenceFitnessCatalog, ado_def()),
        (CapabilityReadinessCatalog, intel_def()),
        (CapabilityReadinessCatalog, ado_def()),
        (AdoptionReadinessCatalog, intel_def()),
        (AdoptionReadinessCatalog, cap_def()),
    ],
)
def test_definitions_of_different_families_are_never_mixed(catalog_cls, foreign):
    with pytest.raises(ReadinessContractError):
        catalog_cls(catalog_id="k", catalog_version="1", entries=(foreign,))


@pytest.mark.parametrize(
    "factory, wrong_dimension",
    [
        (IntelligenceFitnessIndicatorDefinition, CapabilityDimension.TOOL_READINESS),
        (IntelligenceFitnessIndicatorDefinition, AdoptionDimension.TRUST_READINESS),
        (CapabilityReadinessIndicatorDefinition, IntelligenceDimension.ACCURACY),
        (CapabilityReadinessIndicatorDefinition, AdoptionDimension.TRUST_READINESS),
        (AdoptionReadinessIndicatorDefinition, IntelligenceDimension.ACCURACY),
        (AdoptionReadinessIndicatorDefinition, CapabilityDimension.TOOL_READINESS),
    ],
)
def test_a_dimension_from_another_family_is_rejected(factory, wrong_dimension):
    with pytest.raises(ReadinessContractError):
        factory(indicator_id="x", dimension=wrong_dimension, metric_id="m")


def test_an_arbitrary_dimension_value_cannot_be_introduced_at_runtime():
    """The dimension enums are closed; extension goes through ``metric_id``."""

    for bad in ("ACCURACY", 1, None, object()):
        with pytest.raises(ReadinessContractError):
            IntelligenceFitnessIndicatorDefinition(
                indicator_id="x", dimension=bad, metric_id="m"
            )

    # The governed metric id is the extension point, and it is free-form.
    assert intel_def(metric_id="acme.custom.domain-metric").metric_id == (
        "acme.custom.domain-metric"
    )


# --------------------------------------------------------------------------- #
# Identity and metric normalization
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_a_blank_indicator_id_or_metric_id_is_rejected(blank):
    with pytest.raises(ReadinessContractError):
        intel_def(indicator_id=blank)
    with pytest.raises(ReadinessContractError):
        intel_def(metric_id=blank)


def test_identity_is_whitespace_normalized_and_equal_inputs_are_equal():
    a = intel_def(indicator_id="  i1  ", metric_id="  accuracy ")
    b = intel_def(indicator_id="i1", metric_id="accuracy")
    assert a.indicator_id == "i1" and a.metric_id == "accuracy"
    assert a == b
    assert a.canonical_digest() == b.canonical_digest()


def test_identity_is_not_unicode_folded():
    """The package folds no case and applies no NFC/NFKC anywhere.

    Two ids that differ by a code point are two different ids — catalogs do not
    introduce a second, inconsistent canonicalization rule.
    """

    assert intel_def(indicator_id="I1") != intel_def(indicator_id="i1")
    assert intel_def(indicator_id="é") != intel_def(indicator_id="é")


# --------------------------------------------------------------------------- #
# Applicability
# --------------------------------------------------------------------------- #
def test_applicable_targets_are_tuple_normalized_unique_and_deterministic():
    d = intel_def(applicable_targets=[PROD, PILOT])
    assert isinstance(d.applicable_targets, tuple)
    # Deterministic order regardless of how the caller supplied them.
    assert d.applicable_targets == intel_def(applicable_targets=(PILOT, PROD)).applicable_targets
    assert d.canonical_digest() == intel_def(applicable_targets=(PILOT, PROD)).canonical_digest()

    with pytest.raises(ReadinessContractError):
        intel_def(applicable_targets=(PROD, PROD))
    with pytest.raises(ReadinessContractError):
        intel_def(applicable_targets=("PRODUCTION",))


def test_empty_applicability_means_no_catalog_side_restriction():
    unrestricted = intel_def(applicable_targets=())
    assert unrestricted.applies_to(PILOT) and unrestricted.applies_to(PROD)

    pilot_only = intel_def(applicable_targets=(PILOT,))
    assert pilot_only.applies_to(PILOT)
    assert not pilot_only.applies_to(PROD)


# --------------------------------------------------------------------------- #
# Catalog invariants
# --------------------------------------------------------------------------- #
def test_duplicate_indicator_ids_within_a_catalog_are_rejected():
    with pytest.raises(ReadinessContractError):
        IntelligenceFitnessCatalog(
            catalog_id="k",
            catalog_version="1",
            entries=(intel_def("i1"), intel_def("i1", metric_id="other")),
        )


def test_duplicate_indicator_ids_across_a_catalog_set_are_rejected():
    with pytest.raises(ReadinessContractError):
        ReadinessIndicatorCatalogSet(
            intelligence=IntelligenceFitnessCatalog(
                catalog_id="k1", catalog_version="1", entries=(intel_def("shared"),)
            ),
            adoption=AdoptionReadinessCatalog(
                catalog_id="k2", catalog_version="1", entries=(ado_def("shared"),)
            ),
        )


def test_two_families_cannot_share_a_catalog_id():
    with pytest.raises(ReadinessContractError):
        ReadinessIndicatorCatalogSet(
            intelligence=IntelligenceFitnessCatalog(catalog_id="same", catalog_version="1"),
            capability=CapabilityReadinessCatalog(catalog_id="same", catalog_version="1"),
        )


@pytest.mark.parametrize("blank", ["", "  "])
def test_a_catalog_needs_an_identity_and_a_version(blank):
    with pytest.raises(ReadinessContractError):
        IntelligenceFitnessCatalog(catalog_id=blank, catalog_version="1")
    with pytest.raises(ReadinessContractError):
        IntelligenceFitnessCatalog(catalog_id="k", catalog_version=blank)


def test_lookup_returns_the_definition_or_none_never_a_default():
    catalog = IntelligenceFitnessCatalog(
        catalog_id="k", catalog_version="1", entries=(intel_def("i1"),)
    )
    assert catalog.lookup("i1").indicator_id == "i1"
    assert catalog.lookup("i2") is None
    assert catalog.lookup("") is None
    assert catalog.lookup(None) is None


# --------------------------------------------------------------------------- #
# Canonicalization: input order is NOT digest-significant
# --------------------------------------------------------------------------- #
def test_entry_order_is_canonicalized_and_not_digest_significant():
    forward = IntelligenceFitnessCatalog(
        catalog_id="k", catalog_version="1", entries=(intel_def("a"), intel_def("b"))
    )
    reversed_ = IntelligenceFitnessCatalog(
        catalog_id="k", catalog_version="1", entries=(intel_def("b"), intel_def("a"))
    )
    assert forward.entries == reversed_.entries
    assert forward.indicator_ids == ("a", "b")
    assert forward == reversed_
    assert forward.canonical_digest() == reversed_.canonical_digest()


def test_a_list_and_an_equal_tuple_produce_equal_catalogs_and_digests():
    as_list = IntelligenceFitnessCatalog(
        catalog_id="k", catalog_version="1", entries=[intel_def("a")]
    )
    as_tuple = IntelligenceFitnessCatalog(
        catalog_id="k", catalog_version="1", entries=(intel_def("a"),)
    )
    assert as_list == as_tuple
    assert as_list.canonical_digest() == as_tuple.canonical_digest()


def test_two_different_catalogs_do_not_share_a_digest():
    base = IntelligenceFitnessCatalog(
        catalog_id="k", catalog_version="1", entries=(intel_def("a"),)
    )
    for other in (
        IntelligenceFitnessCatalog(catalog_id="k", catalog_version="2", entries=(intel_def("a"),)),
        IntelligenceFitnessCatalog(catalog_id="j", catalog_version="1", entries=(intel_def("a"),)),
        IntelligenceFitnessCatalog(
            catalog_id="k", catalog_version="1", entries=(intel_def("a", metric_id="other"),)
        ),
        IntelligenceFitnessCatalog(
            catalog_id="k", catalog_version="1", entries=(intel_def("a"),), tenant_id="t1"
        ),
    ):
        assert base.canonical_digest() != other.canonical_digest()


# --------------------------------------------------------------------------- #
# Immutability and scalar substitutes
# --------------------------------------------------------------------------- #
def test_a_caller_list_cannot_mutate_a_catalog_after_construction():
    entries = [intel_def("a")]
    catalog = IntelligenceFitnessCatalog(catalog_id="k", catalog_version="1", entries=entries)
    before = catalog.canonical_digest()

    entries.append(intel_def("b"))
    entries[0] = intel_def("z")
    del entries[0]

    assert catalog.indicator_ids == ("a",)
    assert catalog.canonical_digest() == before


def test_a_generator_is_materialized_exactly_once():
    catalog = IntelligenceFitnessCatalog(
        catalog_id="k",
        catalog_version="1",
        entries=(intel_def(i) for i in ("b", "a")),
    )
    assert catalog.indicator_ids == ("a", "b")
    # A second read of an exhausted generator would return nothing.
    assert catalog.indicator_ids == ("a", "b")


@pytest.mark.parametrize(
    "substitute", ["i1", b"i1", bytearray(b"i1"), {"i1": intel_def()}, 7, None, object()]
)
def test_scalar_and_mapping_substitutes_for_entries_are_rejected(substitute):
    with pytest.raises(ReadinessContractError):
        IntelligenceFitnessCatalog(catalog_id="k", catalog_version="1", entries=substitute)


@pytest.mark.parametrize("substitute", ["p", b"p", {"a": 1}, 7, object()])
def test_scalar_and_mapping_substitutes_for_applicability_are_rejected(substitute):
    with pytest.raises(ReadinessContractError):
        intel_def(applicable_targets=substitute)


def test_every_catalog_shape_is_frozen():
    catalog = IntelligenceFitnessCatalog(
        catalog_id="k", catalog_version="1", entries=(intel_def("a"),)
    )
    for obj, field, value in (
        (catalog, "catalog_id", "other"),
        (catalog, "entries", ()),
        (catalog.entries[0], "indicator_id", "other"),
        (catalog.entries[0], "metric_id", "other"),
    ):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(obj, field, value)


def test_nested_reachable_state_is_immutable():
    catalog = IntelligenceFitnessCatalog(
        catalog_id="k", catalog_version="1", entries=(intel_def("a", applicable_targets=(PROD,)),)
    )
    assert isinstance(catalog.entries, tuple)
    assert isinstance(catalog.entries[0].applicable_targets, tuple)
    with pytest.raises(TypeError):
        catalog.entries[0].applicable_targets[0] = PILOT


# --------------------------------------------------------------------------- #
# What a catalog must never carry
# --------------------------------------------------------------------------- #
FORBIDDEN_FIELD_TOKENS = (
    "required",
    "mandatory",
    "requirement",
    "weight",
    "multiplier",
    "score",
    "threshold",
    "benchmark",
    "tier",
    "classification",
    "money",
    "currency",
    "cost",
    "benefit",
    "revenue",
    "roi",
    "attestation",
    "attribution",
    "verification",
    "evidence",
)


@pytest.mark.parametrize(
    "cls",
    [
        IntelligenceFitnessIndicatorDefinition,
        CapabilityReadinessIndicatorDefinition,
        AdoptionReadinessIndicatorDefinition,
        IntelligenceFitnessCatalog,
        CapabilityReadinessCatalog,
        AdoptionReadinessCatalog,
        ReadinessIndicatorCatalogSet,
    ],
)
def test_no_catalog_shape_can_state_a_requirement_a_weight_or_money(cls):
    for field in dataclasses.fields(cls):
        lowered = field.name.lower()
        for token in FORBIDDEN_FIELD_TOKENS:
            assert token not in lowered, (cls.__name__, field.name)


@pytest.mark.parametrize(
    "cls",
    [
        IntelligenceFitnessIndicatorDefinition,
        CapabilityReadinessIndicatorDefinition,
        AdoptionReadinessIndicatorDefinition,
    ],
)
def test_a_definition_cannot_be_marked_required(cls):
    with pytest.raises(TypeError):
        cls(indicator_id="x", dimension=None, metric_id="m", required=True)


# --------------------------------------------------------------------------- #
# The catalog set does not require all three families
# --------------------------------------------------------------------------- #
def test_an_empty_catalog_set_is_valid():
    empty = ReadinessIndicatorCatalogSet()
    assert empty.is_empty
    assert empty.catalogs == ()
    assert empty.families_present == ()
    for family in ReadinessIndicatorClass:
        assert empty.catalog_for(family) is None


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"intelligence": IntelligenceFitnessCatalog(catalog_id="k", catalog_version="1")},
         (ReadinessIndicatorClass.INTELLIGENCE,)),
        ({"capability": CapabilityReadinessCatalog(catalog_id="k", catalog_version="1")},
         (ReadinessIndicatorClass.CAPABILITY,)),
        ({"adoption": AdoptionReadinessCatalog(catalog_id="k", catalog_version="1")},
         (ReadinessIndicatorClass.ADOPTION,)),
    ],
)
def test_any_single_family_may_be_bound_alone(kwargs, expected):
    assert ReadinessIndicatorCatalogSet(**kwargs).families_present == expected


def test_a_catalog_cannot_be_bound_under_another_familys_slot():
    with pytest.raises(ReadinessContractError):
        ReadinessIndicatorCatalogSet(
            intelligence=AdoptionReadinessCatalog(catalog_id="k", catalog_version="1")
        )


def test_the_catalog_set_reports_families_in_fixed_order_not_caller_order():
    catalogs = ReadinessIndicatorCatalogSet(
        adoption=AdoptionReadinessCatalog(catalog_id="k3", catalog_version="1"),
        intelligence=IntelligenceFitnessCatalog(catalog_id="k1", catalog_version="1"),
        capability=CapabilityReadinessCatalog(catalog_id="k2", catalog_version="1"),
    )
    assert catalogs.families_present == (
        ReadinessIndicatorClass.INTELLIGENCE,
        ReadinessIndicatorClass.CAPABILITY,
        ReadinessIndicatorClass.ADOPTION,
    )
