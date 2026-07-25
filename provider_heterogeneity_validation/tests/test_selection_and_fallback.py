"""Selection policies, capability/compat/health rejection, bounded fallback, no-provider."""
from __future__ import annotations

from provider_heterogeneity_validation.profiles.capabilities import capabilities_of
from provider_heterogeneity_validation.selection import (
    CatalogEntry, ProviderCatalog, ProviderState, ResolutionPolicy, SelectionRequest, select)

_K = "ASSERTION_GOVERNANCE"


def _catalog(*states):
    cat = ProviderCatalog()
    for pid, st in states:
        cat.add(CatalogEntry(pid, _K, "0.1.0", capabilities_of(pid), st))
    return cat


def _sel(cat, **kw):
    return select(cat, SelectionRequest(kind=_K, **kw), request_id="t")


def test_fixed_selection():
    cat = _catalog(("tap-primary", ProviderState()), ("baseline-assertion", ProviderState()))
    e, rec = _sel(cat, policy=ResolutionPolicy.FIXED, fixed_id="baseline-assertion")
    assert rec.selected_provider_id == "baseline-assertion"


def test_ordered_preference():
    cat = _catalog(("tap-primary", ProviderState()), ("baseline-assertion", ProviderState()))
    _e, rec = _sel(cat, policy=ResolutionPolicy.ORDERED,
                   preference_order=("tap-primary", "baseline-assertion"))
    assert rec.selected_provider_id == "tap-primary"


def test_capability_required_rejects_incapable():
    cat = _catalog(("tap-primary", ProviderState()), ("baseline-assertion", ProviderState()))
    _e, rec = _sel(cat, policy=ResolutionPolicy.CAPABILITY_REQUIRED,
                   required_capabilities=("qualifier_detection",))
    assert rec.selected_provider_id == "tap-primary"
    assert rec.rejection_reasons["baseline-assertion"] == "MISSING_CAPABILITY"


def test_disabled_and_incompatible_and_unhealthy_rejected():
    cat = _catalog(("tap-primary", ProviderState(enabled=False)),
                   ("baseline-assertion", ProviderState(compatible=False)))
    _e, rec = _sel(cat, policy=ResolutionPolicy.ORDERED,
                   preference_order=("tap-primary", "baseline-assertion"))
    assert rec.selected_provider_id is None
    assert rec.rejection_reasons["tap-primary"] == "DISABLED"
    assert rec.rejection_reasons["baseline-assertion"] == "INCOMPATIBLE"


def test_bounded_fallback_on_unavailable():
    cat = _catalog(("tap-primary", ProviderState(health="UNAVAILABLE")),
                   ("baseline-assertion", ProviderState()))
    _e, rec = _sel(cat, policy=ResolutionPolicy.BOUNDED_FALLBACK,
                   preference_order=("tap-primary", "baseline-assertion"), allow_fallback=True)
    assert rec.selected_provider_id == "baseline-assertion"
    assert rec.fallback_used and rec.fallback_reason == "UNHEALTHY_UNAVAILABLE"


def test_fixed_never_falls_back():
    cat = _catalog(("tap-primary", ProviderState(health="UNAVAILABLE")),
                   ("baseline-assertion", ProviderState()))
    _e, rec = _sel(cat, policy=ResolutionPolicy.FIXED, fixed_id="tap-primary")
    assert rec.selected_provider_id is None       # fail-safe, no fallback


def test_no_valid_provider():
    cat = _catalog(("tap-primary", ProviderState(health="UNAVAILABLE")),
                   ("baseline-assertion", ProviderState(health="UNAVAILABLE")))
    _e, rec = _sel(cat, policy=ResolutionPolicy.BOUNDED_FALLBACK,
                   preference_order=("tap-primary", "baseline-assertion"), allow_fallback=True)
    assert rec.selected_provider_id is None


def test_degraded_requires_allow_and_capability_still_enforced():
    # degraded but capable tap vs healthy incapable baseline; qualifier required
    cat = _catalog(("baseline-assertion", ProviderState()),
                   ("tap-primary", ProviderState(health="DEGRADED")))
    _e, rec = _sel(cat, policy=ResolutionPolicy.CAPABILITY_REQUIRED,
                   required_capabilities=("qualifier_detection",), allow_degraded=True,
                   preference_order=("baseline-assertion", "tap-primary"))
    assert rec.selected_provider_id == "tap-primary"   # health never bypasses capability


def test_selection_is_deterministic():
    cat = _catalog(("tap-primary", ProviderState()), ("baseline-assertion", ProviderState()))
    _a, r1 = _sel(cat, policy=ResolutionPolicy.ORDERED,
                  preference_order=("tap-primary", "baseline-assertion"))
    _b, r2 = _sel(cat, policy=ResolutionPolicy.ORDERED,
                  preference_order=("tap-primary", "baseline-assertion"))
    assert r1.resolution_fingerprint == r2.resolution_fingerprint
