"""Composition root, provider resolution, and manifest validation."""
from __future__ import annotations

from enterprise_validation_pilot.composition import (
    PilotComposition, load_config, validate_manifest)
from enterprise_validation_pilot.composition.config import (
    action_provider_id, assertion_provider_id)
from enterprise_validation_pilot.datasets.build_dataset import build
from governance_providers.api import ProviderKind


def _scenario():
    return build().by_id("procurement-001")


def test_config_declares_both_provider_kinds():
    cfg = load_config()
    assert assertion_provider_id(cfg) == "tap-primary"
    assert action_provider_id(cfg) == "actiongate-primary"


def test_composition_resolves_both_providers_via_registry():
    comp = PilotComposition(_scenario())
    tap, tap_rec = comp.resolve_assertion_provider()
    ag, ag_rec = comp.resolve_action_provider()
    assert tap_rec.selected_id == "tap-primary"
    assert ag_rec.selected_id == "actiongate-primary"
    assert tap_rec.selection_rule.value != "UNRESOLVED"
    # kinds are peers, distinct
    kinds = {d.kind for d in comp.registry.list_by_kind()}
    assert {ProviderKind.ASSERTION_GOVERNANCE, ProviderKind.ACTION_GOVERNANCE} <= kinds


def test_provider_resolution_is_deterministic():
    comp = PilotComposition(_scenario())
    a1 = comp.resolve_assertion_provider()[1].selected_id
    a2 = comp.resolve_assertion_provider()[1].selected_id
    assert a1 == a2 == "tap-primary"


def test_manifest_validates_against_installed_versions():
    v = validate_manifest()
    assert v.ok, v.failures
