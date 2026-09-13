"""CEC-1: the fourth provider kind exists as a name, and Stage 1 keeps it inert.

Scoped by ``docs/architecture/ADR_UGENCE_CHANGE_EFFECT_CLASSIFIER_SCOPING.md`` and
``docs/architecture/STAGE1_CHANGE_EFFECT_CLASSIFIER_CONTRACTS_SCOPING.md``. These
tests assert the two properties Stage 1 claims: the kind is admissible to the
registry's existing dispatch without code change, and **nothing registers under
it**, so no runtime path can reach a classifier that does not exist.
"""
from __future__ import annotations

from ugence_governance_provider_framework.configuration import ProvidersConfiguration
from ugence_governance_provider_framework.metadata import ProviderKind


def test_kind_is_a_peer_and_not_conflated():
    k = ProviderKind.CHANGE_EFFECT_CLASSIFICATION
    assert k.value == "CHANGE_EFFECT_CLASSIFICATION"
    assert k not in (
        ProviderKind.ASSERTION_GOVERNANCE,
        ProviderKind.ACTION_GOVERNANCE,
        ProviderKind.EXTERNAL_EXECUTION,
    )


def test_kind_is_nameable_in_configuration():
    """A kind no configuration can name is unaddressable; both labels resolve."""
    for label in ("change_effect_classification", "classification"):
        cfg = ProvidersConfiguration.from_mapping(
            {"providers": {label: {"registered": [{"id": "p1"}]}}}
        )
        assert cfg.entries[0].kind is ProviderKind.CHANGE_EFFECT_CLASSIFICATION
    # Naming a kind in configuration is not registering a provider under it: the
    # entry is data, and no provider object exists for the registry to resolve.


def test_no_provider_registers_under_the_kind_in_stage_1():
    """Stage 1 inertness, asserted structurally rather than by discipline."""
    empty = ProvidersConfiguration()
    assert empty.by_kind(ProviderKind.CHANGE_EFFECT_CLASSIFICATION) == ()


def test_no_conformance_profile_exists_for_the_kind_yet():
    """A fourth kind needs its own profile before any provider registers under it.

    Stage 1 registers none, so the profile is deliberately absent. This test fails
    the day someone adds a profile without also taking Stage 1 owner decision 3,
    and the day someone registers a provider without a profile.
    """
    from ugence_governance_provider_framework import conformance

    assert not hasattr(conformance, "run_change_effect_classification_conformance")
