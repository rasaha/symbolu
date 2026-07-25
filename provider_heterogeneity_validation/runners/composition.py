"""Provider catalog composition (imports every provider — composition only).

Builds assertion/action catalogs from a configuration + scenario + failure effect.
This is the only module that imports concrete providers; the selection and
evaluation layers stay provider-neutral. Baseline engines are derived from the same
scenario policy TAP/ActionGate use, with capability-requiring outcomes honestly
downgraded to INDETERMINATE/UNKNOWN.
"""
from __future__ import annotations

import dataclasses

from actiongate_provider.configuration import ActionGateSettings, build_actiongate_provider
from baseline_action_provider.api import (
    BaselineActionConstraint, BaselineActionEngine, BaselineActionObligation,
    build_baseline_action_provider)
from baseline_action_provider.core import ConstrainedRule as BaselineActionRule
from baseline_assertion_provider.api import (
    BaselineAssertionEngine, BaselineAssertionOutcome, BaselineRule,
    build_baseline_assertion_provider)
from enterprise_validation_pilot.composition.engines import (
    build_actiongate_engine, build_tap_engine)
from tap_provider.configuration import TapSettings, build_tap_provider

from ..profiles.capabilities import capabilities_of
from ..selection.catalog import CatalogEntry, ProviderCatalog, ProviderState

_ASSERT = "ASSERTION_GOVERNANCE"
_ACTION = "ACTION_GOVERNANCE"

_BASELINE_ASSERT_OUTCOME = {
    "SUPPORTED": BaselineAssertionOutcome.SUPPORTED,
    "UNSUPPORTED": BaselineAssertionOutcome.UNSUPPORTED,
    "INDETERMINATE": BaselineAssertionOutcome.INDETERMINATE,
    "CONSTRAINED": BaselineAssertionOutcome.INDETERMINATE,   # capability-limited downgrade
}


def _state_for(provider_id, effect) -> ProviderState:
    st = ProviderState()
    if effect and effect.get("target") == provider_id and effect.get("state"):
        st = dataclasses.replace(st, **effect["state"])
    if effect and effect.get("special") == "NO_COMPATIBLE_PROVIDER":
        st = dataclasses.replace(st, compatible=False)
    return st


def _engine_fail(provider_id, effect):
    if effect and effect.get("target") == provider_id:
        return effect.get("engine_fail")
    return None


# --- assertion providers ----------------------------------------------------

def _tap_builder(scenario, fail):
    policy = dataclasses.replace(scenario.tap_policy, fail=fail) if fail else scenario.tap_policy
    engine = build_tap_engine(scenario.assertion, policy)
    return lambda: build_tap_provider(
        engine, settings=TapSettings(provider_id="tap-primary", mode="in_process"))


def _baseline_assertion_builder(scenario, fail):
    if fail:
        engine = BaselineAssertionEngine(fail=fail)
    else:
        rule = BaselineRule(
            outcome=_BASELINE_ASSERT_OUTCOME.get(scenario.tap_policy.outcome,
                                                 BaselineAssertionOutcome.INDETERMINATE),
            reason_codes=("baseline",))
        engine = BaselineAssertionEngine(rules={scenario.assertion: rule})
    return lambda: build_baseline_assertion_provider(engine)


# --- action providers -------------------------------------------------------

def _actiongate_builder(scenario, fail):
    policy = (dataclasses.replace(scenario.action_policy, fail=fail) if fail
              else scenario.action_policy)
    engine = build_actiongate_engine(scenario.proposed_action.action_type, policy)
    return lambda: build_actiongate_provider(
        engine, settings=ActionGateSettings(provider_id="actiongate-primary", mode="in_process"))


def _baseline_action_builder(scenario, fail):
    ap = scenario.action_policy
    at = scenario.proposed_action.action_type
    if fail:
        engine = BaselineActionEngine(fail=fail)
    elif ap.mode == "deny":
        engine = BaselineActionEngine(denied=frozenset({at}))
    elif ap.mode == "unknown":
        engine = BaselineActionEngine(unknown=frozenset({at}))
    elif ap.mode == "constrained":
        rule = BaselineActionRule(
            constraints=tuple(BaselineActionConstraint(t, v) for t, v in ap.constraints),
            obligations=tuple(BaselineActionObligation(t, v) for t, v in ap.obligations))
        engine = BaselineActionEngine(constrained={at: rule})
    else:
        engine = BaselineActionEngine()
    return lambda: build_baseline_action_provider(engine)


_ASSERTION_BUILDERS = {"tap-primary": _tap_builder, "baseline-assertion": _baseline_assertion_builder}
_ACTION_BUILDERS = {"actiongate-primary": _actiongate_builder, "baseline-action": _baseline_action_builder}


def _catalog(kind, provider_ids, builders, scenario, effect) -> ProviderCatalog:
    cat = ProviderCatalog()
    for pid in provider_ids:
        fail = _engine_fail(pid, effect)
        cat.add(CatalogEntry(
            provider_id=pid, kind=kind, version="0.1.0",
            capabilities=capabilities_of(pid), state=_state_for(pid, effect),
            build=builders[pid](scenario, fail)))
    if effect and effect.get("special") == "REGISTRY_DUPLICATE_ID" and provider_ids:
        pid = provider_ids[0]
        cat.add(CatalogEntry(pid, kind, "0.1.0", capabilities_of(pid),
                             ProviderState(), builders[pid](scenario, None)))
    return cat


def build_assertion_catalog(scenario, config, effect) -> ProviderCatalog:
    return _catalog(_ASSERT, config.assertion_providers, _ASSERTION_BUILDERS, scenario, effect)


def build_action_catalog(scenario, config, effect) -> ProviderCatalog:
    return _catalog(_ACTION, config.action_providers, _ACTION_BUILDERS, scenario, effect)
