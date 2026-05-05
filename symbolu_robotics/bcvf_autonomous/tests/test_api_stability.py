"""Tests for the public-API stability commitment (``API_STABILITY.md``).

The post-v0.7 0.4.0 release ratifies a tiered API:

* :data:`STABLE_API` — long-term commitment (38 symbols).
* :data:`PROVISIONAL_API` — supported, may evolve in a minor (14 symbols).

The tests below pin every load-bearing invariant the policy relies
on, so a future PR that quietly renames a stable symbol or adds a
provisional one without acknowledging it fails the suite loudly.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import symbolu_robotics.bcvf_autonomous as bcvf
from symbolu_robotics.bcvf_autonomous._api import (
    PROVISIONAL_API,
    STABLE_API,
    is_provisional,
    is_stable,
    resolve_qualified,
    stable_top_level_names,
)
from symbolu_robotics.bcvf_autonomous._version import (
    VERSION_INFO,
    __version__,
)


# Pinned counts. A PR that adds / removes a stable or provisional
# symbol must update these, which forces the reviewer to acknowledge
# the contract change in the diff.
EXPECTED_STABLE_COUNT = 38
EXPECTED_PROVISIONAL_COUNT = 20
EXPECTED_VERSION = "0.4.0"
EXPECTED_VERSION_INFO = (0, 4, 0)


# --------------------------------------------------------------------------- #
# Version
# --------------------------------------------------------------------------- #


def test_version_string_pinned():
    """The 0.4.0 release ratifies the API stability policy. Subsequent
    bumps follow ``API_STABILITY.md`` §3."""
    assert __version__ == EXPECTED_VERSION


def test_version_string_follows_semver():
    """``MAJOR.MINOR.PATCH`` with optional pre-release / build suffix."""
    pattern = (
        r"^\d+\.\d+\.\d+"
        r"(?:-[0-9A-Za-z.-]+)?"
        r"(?:\+[0-9A-Za-z.-]+)?$"
    )
    assert re.match(pattern, __version__), (
        f"{__version__!r} is not a valid semver string"
    )


def test_version_info_tuple_matches_string():
    """``VERSION_INFO`` and ``__version__`` must agree — both are
    sourced from ``_version.py`` so a bump can't update one and miss
    the other."""
    assert VERSION_INFO == EXPECTED_VERSION_INFO
    head = ".".join(str(p) for p in VERSION_INFO)
    assert __version__.startswith(head)


def test_top_level_exposes_version_and_info():
    assert hasattr(bcvf, "__version__")
    assert hasattr(bcvf, "VERSION_INFO")
    assert bcvf.__version__ == __version__
    assert bcvf.VERSION_INFO == VERSION_INFO


# --------------------------------------------------------------------------- #
# Registry shape
# --------------------------------------------------------------------------- #


def test_stable_api_count_locked():
    """Pinned: every change to ``STABLE_API`` must update the count
    here so the PR review notices the contract change."""
    assert len(STABLE_API) == EXPECTED_STABLE_COUNT, (
        f"STABLE_API has {len(STABLE_API)} entries; expected "
        f"{EXPECTED_STABLE_COUNT}. Update API_STABILITY.md §6 + this "
        "test if the change is intentional."
    )


def test_provisional_api_count_locked():
    assert len(PROVISIONAL_API) == EXPECTED_PROVISIONAL_COUNT, (
        f"PROVISIONAL_API has {len(PROVISIONAL_API)} entries; expected "
        f"{EXPECTED_PROVISIONAL_COUNT}."
    )


def test_stable_and_provisional_are_disjoint():
    """No symbol may be both stable and provisional — a graduation
    from provisional to stable is a delete-from-one + add-to-other
    diff, not an additive duplicate."""
    overlap = set(STABLE_API) & set(PROVISIONAL_API)
    assert overlap == set(), f"overlap: {overlap}"


def test_stable_api_has_no_internal_underscores():
    """No symbol with a leading underscore is stable. Internal
    surfaces (e.g. ``_evaluate_thresholds``) carry no commitment."""
    for q in STABLE_API:
        symbol = q.rsplit(".", 1)[1]
        assert not symbol.startswith("_"), (
            f"{q} begins with '_' — internal surfaces cannot be stable"
        )


def test_stable_and_provisional_entries_are_qualified():
    """Every entry must be ``submodule.Symbol`` (at least one dot)."""
    for q in tuple(STABLE_API) + tuple(PROVISIONAL_API):
        assert "." in q, f"{q!r} must use submodule.Symbol form"


def test_stable_and_provisional_entries_are_unique_within_their_tier():
    """Defensive: a copy-paste duplicate in either tuple would
    inflate counts and confuse the registry."""
    assert len(STABLE_API) == len(set(STABLE_API))
    assert len(PROVISIONAL_API) == len(set(PROVISIONAL_API))


# --------------------------------------------------------------------------- #
# Resolution — every entry must point at a live symbol
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("qualified", STABLE_API)
def test_every_stable_api_symbol_resolves(qualified):
    """Every entry must import + look up cleanly. A renamed module
    or removed symbol fails this parametrized test with the offending
    qualified name in the failure message."""
    obj = resolve_qualified(qualified)
    assert obj is not None


@pytest.mark.parametrize("qualified", PROVISIONAL_API)
def test_every_provisional_api_symbol_resolves(qualified):
    obj = resolve_qualified(qualified)
    assert obj is not None


def test_resolve_qualified_rejects_unqualified_input():
    with pytest.raises(ValueError):
        resolve_qualified("just_a_name")


def test_resolve_qualified_raises_on_unknown_symbol():
    with pytest.raises(AttributeError) as exc_info:
        resolve_qualified("core.this_symbol_does_not_exist")
    assert "stale" in str(exc_info.value)


def test_resolve_qualified_raises_on_unknown_submodule():
    with pytest.raises(ImportError):
        resolve_qualified("not_a_real_submodule.Symbol")


def test_resolve_qualified_rejects_empty_string():
    """Defensive pin caught in the post-v0.7 audit pass — an empty
    qualified name should fail loud rather than fall through to the
    ``submodule.Symbol`` parser."""
    with pytest.raises((ValueError, AttributeError, ImportError)):
        resolve_qualified("")


def test_resolve_qualified_rejects_trailing_dot():
    """Trailing-dot input parses to an empty symbol; ``hasattr`` then
    fails. Pinned as a defensive sanity check on the parser."""
    with pytest.raises((AttributeError, ImportError)):
        resolve_qualified("core.")


def test_resolve_qualified_rejects_leading_dot():
    """Leading-dot input parses to an empty submodule path; the
    import then fails. Pinned alongside the trailing-dot case."""
    with pytest.raises((ImportError, AttributeError, ValueError)):
        resolve_qualified(".BCVFConfig")


# --------------------------------------------------------------------------- #
# Top-level reachability — `from bcvf_autonomous import X` works for stable X
# --------------------------------------------------------------------------- #


def test_every_stable_symbol_is_top_level_reachable():
    """Per ``API_STABILITY.md`` §2.1, every stable symbol is reachable
    both via its canonical submodule path and via the top-level
    package re-export. A post-v0.7 audit caught 8 stable symbols
    that weren't yet re-exported at the top level — this test pins
    the fix."""
    missing = [
        name for name in stable_top_level_names()
        if not hasattr(bcvf, name)
    ]
    assert missing == [], (
        f"missing top-level re-exports for stable symbols: {missing}"
    )


def test_every_stable_symbol_is_in_top_level_dunder_all():
    """``__all__`` advertises the public surface. Every stable symbol
    must appear so ``from bcvf_autonomous import *`` covers the
    contract."""
    missing = [
        name for name in stable_top_level_names()
        if name not in bcvf.__all__
    ]
    assert missing == [], (
        f"missing entries in bcvf_autonomous.__all__: {missing}"
    )


def test_top_level_reexport_resolves_to_same_object_as_submodule():
    """``from bcvf_autonomous import X`` must yield the same object
    as ``from bcvf_autonomous.<sub> import X``. Object identity here
    is the contract — a top-level re-export that wraps / copies
    breaks ``isinstance`` checks downstream."""
    for q in STABLE_API:
        canonical = resolve_qualified(q)
        name = q.rsplit(".", 1)[1]
        top_level = getattr(bcvf, name)
        assert canonical is top_level, (
            f"top-level {name} is not the same object as canonical "
            f"submodule path {q}"
        )


# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #


def test_is_stable_and_is_provisional_predicates():
    sample_stable = "core.compute_bcvf_cost"
    sample_provisional = "pilot.run_pilot"
    sample_unknown = "core.does_not_exist"
    assert sample_stable in STABLE_API   # sanity
    assert sample_provisional in PROVISIONAL_API
    assert is_stable(sample_stable)
    assert not is_stable(sample_provisional)
    assert not is_stable(sample_unknown)
    assert is_provisional(sample_provisional)
    assert not is_provisional(sample_stable)
    assert not is_provisional(sample_unknown)


def test_stable_top_level_names_returns_only_symbol_names():
    """The helper must strip the submodule prefix; otherwise downstream
    callers using ``getattr(pkg, name)`` on the result would break."""
    names = stable_top_level_names()
    assert len(names) == len(STABLE_API)
    for name in names:
        assert "." not in name, f"top-level name {name!r} carries a dot"


# --------------------------------------------------------------------------- #
# Policy doc — ships in the package root
# --------------------------------------------------------------------------- #


def test_api_stability_policy_doc_exists():
    """``API_STABILITY.md`` ships next to ``__init__.py`` so a buyer
    reading the source tree finds the contract immediately."""
    pkg_root = Path(bcvf.__file__).parent
    doc = pkg_root / "API_STABILITY.md"
    assert doc.exists(), f"missing policy doc at {doc}"
    text = doc.read_text(encoding="utf-8")
    # Spot-check that the four section headers a buyer expects are present.
    for header in (
        "API Stability Policy",
        "Three tiers",
        "Semver mapping",
        "Deprecation cycle",
        "Machine-checked",
    ):
        assert header in text, f"policy missing section: {header}"
