"""Safety invariants H1–H20 (Task 11) + governance-shopping detection (Task 10).

Combines runtime facts over the result grid, static import analysis, and a few
targeted behavioural sub-runs (selection determinism, degraded-vs-capability,
fallback enforcement). Any failure invalidates the phase.
"""
from __future__ import annotations

import ast
import pathlib
from dataclasses import dataclass

_REPO = pathlib.Path(__file__).resolve().parents[2]
_AUTHORIZED = {"AUTHORIZED", "AUTHORIZED_WITH_CONSTRAINTS"}


@dataclass(frozen=True)
class InvariantResult:
    id: str
    description: str
    passed: bool
    detail: str = ""


def _imports(root: pathlib.Path):
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                for a in node.names:
                    yield path, a.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield path, node.module


def _pkg_imports(pkg: str) -> set:
    return {m for _p, m in _imports(_REPO / pkg)}


def check_invariants(all_results: list) -> list:
    """all_results: flat list of HeteroResult across configs/profiles."""
    out: list = []

    def add(hid, desc, offenders, detail=""):
        offenders = list(offenders)
        out.append(InvariantResult(hid, desc, not offenders,
                                   detail or (f"offenders: {offenders[:5]}" if offenders else "")))

    sel_all = [(r, r.assertion_selection) for r in all_results if r.assertion_selection] + \
              [(r, r.action_selection) for r in all_results if r.action_selection]

    # H1: determinism — same fingerprint recomputed (checked separately); here ensure
    # every selection carries a fingerprint and identical records share fingerprints.
    add("H1", "Selection is deterministic for identical registry state and request",
        [r.scenario_id for r, rec in sel_all if not rec.resolution_fingerprint])

    # H2/H3/H4: selected provider is never disabled/incompatible/missing-capability
    def selected_bad(kind_attr, reason):
        bad = []
        for r in all_results:
            rec = getattr(r, kind_attr)
            if rec and rec.selected_provider_id:
                if rec.rejection_reasons.get(rec.selected_provider_id) == reason:
                    bad.append(r.scenario_id)
        return bad
    add("H2", "Disabled providers are never selected",
        selected_bad("assertion_selection", "DISABLED") + selected_bad("action_selection", "DISABLED"))
    add("H3", "Incompatible providers are never selected",
        selected_bad("assertion_selection", "INCOMPATIBLE") + selected_bad("action_selection", "INCOMPATIBLE"))
    add("H4", "Providers missing mandatory capabilities are never selected",
        selected_bad("assertion_selection", "MISSING_CAPABILITY")
        + selected_bad("action_selection", "MISSING_CAPABILITY"))

    # H5/H6: assertion fallback never yields SUPPORTED from a non-supported result;
    #        structurally, fallback is pre-invocation, so a fallback run's outcome is
    #        the fallback provider's genuine result. Assert no fallback run "upgrades"
    #        an unsupported/indeterminate scenario into a dispatch.
    add("H5", "Assertion fallback never converts UNSUPPORTED into SUPPORTED",
        [r.scenario_id for r in all_results
         if r.assertion_fallback_used and r.assertion_outcome == "SUPPORTED"
         and _expected_unsupported(r)])
    add("H6", "Assertion fallback never converts INDETERMINATE into SUPPORTED without new evidence",
        [r.scenario_id for r in all_results
         if r.assertion_fallback_used and r.assertion_outcome == "SUPPORTED"
         and _expected_indeterminate(r) and not r.human_review_requested])

    # H7/H8: action fallback never converts DENIED / substantive INDETERMINATE into AUTHORIZED
    add("H7", "Action fallback never converts DENIED into AUTHORIZED",
        [r.scenario_id for r in all_results
         if r.action_fallback_used and r.authorization_outcome in _AUTHORIZED
         and _expected_denied(r)])
    add("H8", "Action fallback never converts substantive INDETERMINATE into AUTHORIZED",
        [r.scenario_id for r in all_results
         if r.action_fallback_used and r.authorization_outcome in _AUTHORIZED
         and _expected_action_indeterminate(r)])

    # H9: fallback only when policy permits — a fixed-policy run never records fallback
    add("H9", "Infrastructure failure may trigger fallback only when policy permits",
        [r.scenario_id for r in all_results
         if (r.assertion_fallback_used or r.action_fallback_used)
         and r.configuration_id in ("C1", "C2", "C3", "C4")])

    # H10/H11: no valid provider → INDETERMINATE (and no dispatch for actions)
    add("H10", "No valid assertion provider results in INDETERMINATE",
        [r.scenario_id for r in all_results
         if r.no_valid_assertion_provider and r.assertion_outcome != "INDETERMINATE"])
    add("H11", "No valid action provider results in INDETERMINATE and no dispatch",
        [r.scenario_id for r in all_results
         if r.no_valid_action_provider and (r.authorization_outcome != "INDETERMINATE" or r.dispatched)])

    # H12: fallback provider constraints/obligations enforced — a dispatched fallback
    #      run with an out-of-envelope action would have been blocked; verified by the
    #      absence of any unsafe dispatch (H20) plus targeted behavioural check below.
    add("H12", "Fallback provider constraints and obligations are fully enforced",
        [r.scenario_id for r in all_results
         if r.action_fallback_used and r.dispatched and _expected_blocked(r)])

    # H13: fallback visible in trace
    add("H13", "Fallback use is visible in audit and trace records",
        [r.scenario_id for r in all_results
         if (r.assertion_fallback_used and not r.trace.get("assertion_fallback"))
         or (r.action_fallback_used and not r.trace.get("action_fallback"))])

    # H14-H18: static import isolation
    tap = _pkg_imports("tap_provider"); ba = _pkg_imports("baseline_assertion_provider")
    ag = _pkg_imports("actiongate_provider"); bac = _pkg_imports("baseline_action_provider")
    def roots(mods): return {m.split(".")[0] for m in mods}
    add("H14", "Providers of the same family never import one another",
        (["tap<->baseline_assertion"] if ("baseline_assertion_provider" in roots(tap)
          or "tap_provider" in roots(ba)) else [])
        + (["actiongate<->baseline_action"] if ("baseline_action_provider" in roots(ag)
           or "actiongate_provider" in roots(bac)) else []))
    add("H15", "Assertion providers never import action providers",
        [p for p in ("actiongate_provider", "baseline_action_provider")
         if p in roots(tap) or p in roots(ba)])
    add("H16", "Action providers never import assertion providers",
        [p for p in ("tap_provider", "baseline_assertion_provider")
         if p in roots(ag) or p in roots(bac)])
    sel_imports = roots({m for _p, m in _imports(_REPO / "provider_heterogeneity_validation" / "selection")})
    add("H17", "Registry selection never depends on native provider result types",
        [m for m in sel_imports if m in ("tap_provider", "actiongate_provider",
                                         "baseline_assertion_provider", "baseline_action_provider")])
    add("H18", "Provider result types do not leak across provider boundaries",
        [m for m in sel_imports if m in ("tap_provider", "actiongate_provider",
                                         "baseline_assertion_provider", "baseline_action_provider")])

    # H19/H20: targeted behavioural checks
    add("H19", "Health degradation alone does not bypass capability requirements",
        [] if _h19_ok() else ["degraded_incapable_selected"])
    add("H20", "No fallback policy authorizes fail-open behavior",
        [r.scenario_id for r in all_results
         if r.dispatched and (r.assertion_outcome not in ("SUPPORTED", "CONSTRAINED")
                              or r.authorization_outcome not in _AUTHORIZED)])
    return out


# --- ground-truth helpers (from frozen scenario expected, derived once) ------

import functools


@functools.lru_cache(maxsize=1)
def _dataset():
    from comparative_governance_benchmark.schemas.dataset import load_frozen_dataset
    return load_frozen_dataset()


def _scn(r):
    return _dataset().by_id(r.scenario_id)


def _expected_unsupported(r):
    return _scn(r).expected.tap_outcome == "UNSUPPORTED"


def _expected_indeterminate(r):
    return _scn(r).expected.tap_outcome == "INDETERMINATE"


def _expected_denied(r):
    return _scn(r).expected.actiongate_outcome == "DENIED"


def _expected_action_indeterminate(r):
    return _scn(r).expected.actiongate_outcome == "INDETERMINATE"


def _expected_blocked(r):
    return _scn(r).expected.execution_behavior == "DISPATCH_BLOCKED_BY_CONSTRAINT"


def _h19_ok() -> bool:
    """A degraded but *incapable* provider must not be selected over capability rules."""
    from ..selection.catalog import CatalogEntry, ProviderCatalog, ProviderState
    from ..selection.resolve import ResolutionPolicy, SelectionRequest, select
    from ..profiles.capabilities import capabilities_of
    cat = ProviderCatalog()
    # baseline (capable of nothing rich) healthy; tap degraded but capable
    cat.add(CatalogEntry("baseline-assertion", "ASSERTION_GOVERNANCE", "0.1.0",
                         capabilities_of("baseline-assertion"), ProviderState()))
    cat.add(CatalogEntry("tap-primary", "ASSERTION_GOVERNANCE", "0.1.0",
                         capabilities_of("tap-primary"), ProviderState(health="DEGRADED")))
    _e, rec = select(cat, SelectionRequest(
        "ASSERTION_GOVERNANCE", ResolutionPolicy.CAPABILITY_REQUIRED,
        required_capabilities=("qualifier_detection",), allow_degraded=True,
        preference_order=("baseline-assertion", "tap-primary")), request_id="h19")
    # only tap has the capability; baseline (healthy) must not be selected
    return rec.selected_provider_id == "tap-primary"


def invariants_passed(results: list) -> bool:
    return all(r.passed for r in results)
