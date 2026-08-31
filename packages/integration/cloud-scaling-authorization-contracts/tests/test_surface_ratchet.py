"""The surface allowlist cannot grow silently — measured, including on the parser itself.

``FROZEN_NON_FIELD_SURFACE`` names every public member of the candidate that is not a
digest-covered field. Growing that list is how R-11's guard would be defeated, and growing it
is cheap: the list and the class live in one tree and land in one commit. So the "before" comes
from repository history instead, exactly as the partition ratchet's does.

What this closes and what it does not
--------------------------------------
*Accidental drift* is closed by the completeness test alone — a contributor adding a
convenience attribute touches nothing here, and the enumeration fires.

*A contributor editing the class and the allowlist together* is *not* closed, and no test in
this tree can close it: the tests and the code share one trust domain. What the ratchet buys is
that the baseline cannot be edited by the commit that changes the current state, so widening
becomes a **disclosed** event rather than a silent one. It cannot make the disclosure true.
That residual is the same one D-5B1-3's third rule carries, and it is recorded rather than
repaired.
"""

from __future__ import annotations

import os
import pathlib

import pytest

from _surface_ratchet import (
    SurfaceRatchetBaselineUnavailable,
    allowlist_from_source,
    baseline_revision,
    ratchet_problems,
    sources_at_revision,
)
from test_digest_completeness import FROZEN_NON_FIELD_SURFACE


def _repo_root() -> "pathlib.Path | None":
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            return parent
    return None


REPO = _repo_root()
COMPLETENESS = pathlib.Path(__file__).with_name("test_digest_completeness.py")

_SYNTHETIC_BEFORE = 'FROZEN_NON_FIELD_SURFACE: frozenset[str] = frozenset({"trust_state"})'
_SYNTHETIC_AFTER = (
    'FROZEN_NON_FIELD_SURFACE: frozenset[str] = frozenset({"trust_state", "binding_summary"})'
)


# ======================================================================================
# The parser, measured against the imported truth before it is trusted on history
# ======================================================================================
def test_the_parser_reproduces_the_imported_allowlist():
    """A parser that silently returned nothing would leave this gate green and vacuous."""

    assert allowlist_from_source(COMPLETENESS.read_text(encoding="utf-8")) == (
        FROZEN_NON_FIELD_SURFACE
    )


def test_a_source_without_the_allowlist_is_refused_rather_than_read_as_empty():
    """Absent in the working tree means the guard was deleted. That is not "nothing exempt"."""

    with pytest.raises(SurfaceRatchetBaselineUnavailable):
        allowlist_from_source("SOMETHING_ELSE = frozenset({'x'})\n")


def test_a_baseline_predating_the_allowlist_reads_as_nothing_exempt():
    """Before the allowlist existed, no member was exempt — so introducing it discloses all.

    Granted to the baseline only. The asymmetry is the point: an absent "before" is a truthful
    empty set, an absent "after" is a deleted guard.
    """

    assert allowlist_from_source("X = 1\n", absent_is_empty=True) == frozenset()
    problems = ratchet_problems(
        baseline={"completeness": "X = 1\n", "changelog": "# Changelog\n"},
        current={"completeness": _SYNTHETIC_AFTER, "changelog": "# Changelog\n"},
    )
    assert sorted(p.split()[0] for p in problems) == ["binding_summary", "trust_state"]


# ======================================================================================
# The gate
# ======================================================================================
def test_an_undisclosed_addition_is_refused():
    problems = ratchet_problems(
        baseline={"completeness": _SYNTHETIC_BEFORE, "changelog": "# Changelog\n"},
        current={
            "completeness": _SYNTHETIC_AFTER,
            "changelog": "# Changelog\n\n- binding_summary is fine, honestly\n",
        },
    )
    assert problems and "binding_summary" in problems[0]


def test_a_disclosed_addition_passes():
    problems = ratchet_problems(
        baseline={"completeness": _SYNTHETIC_BEFORE, "changelog": "# Changelog\n"},
        current={
            "completeness": _SYNTHETIC_AFTER,
            "changelog": "# Changelog\n\n- surface: binding_summary — a constant label\n",
        },
    )
    assert problems == []


def test_prose_that_merely_mentions_the_name_does_not_count_as_disclosure():
    """The failure D-5B1-3's third rule already measured, refused here by construction."""

    problems = ratchet_problems(
        baseline={"completeness": _SYNTHETIC_BEFORE, "changelog": "# Changelog\n"},
        current={
            "completeness": _SYNTHETIC_AFTER,
            "changelog": "# Changelog\n\n- binding_summary stays digest-bound and unchanged\n",
        },
    )
    assert problems and "binding_summary" in problems[0]


def test_removing_a_member_needs_no_ceremony():
    """Narrowing the exempt surface is not the direction this gate exists to catch."""

    assert (
        ratchet_problems(
            baseline={"completeness": _SYNTHETIC_AFTER, "changelog": "# Changelog\n"},
            current={"completeness": _SYNTHETIC_BEFORE, "changelog": "# Changelog\n"},
        )
        == []
    )


def test_an_unchanged_allowlist_is_not_asked_to_disclose_anything():
    assert (
        ratchet_problems(
            baseline={"completeness": _SYNTHETIC_BEFORE, "changelog": "# Changelog\n"},
            current={"completeness": _SYNTHETIC_BEFORE, "changelog": "# Changelog\n"},
        )
        == []
    )


# ======================================================================================
# Against real history
# ======================================================================================
@pytest.mark.skipif(REPO is None, reason="no checkout: there is no history to ratchet against")
def test_a_baseline_containing_head_is_refused_rather_than_compared():
    """The vacuous-pass hole the partition ratchet closed at 5B-3, closed here too.

    This module's version failed *open*: on every default-branch push the workflow
    computed ``git merge-base HEAD <default>`` — HEAD itself — injected it, and the gate
    passed green (measured on run 33317988694, whose environment shows
    ``UGENCE_RATCHET_BASE`` equal to the head SHA). Injecting ``HEAD`` must now be refused
    in the tested code, not only by the workflow's own guard.
    """

    previous = os.environ.get("UGENCE_RATCHET_BASE")
    os.environ["UGENCE_RATCHET_BASE"] = "HEAD"
    try:
        with pytest.raises(SurfaceRatchetBaselineUnavailable) as excinfo:
            baseline_revision(REPO)
    finally:
        if previous is None:
            os.environ.pop("UGENCE_RATCHET_BASE", None)
        else:
            os.environ["UGENCE_RATCHET_BASE"] = previous
    assert "vacuous" in str(excinfo.value)


@pytest.mark.skipif(REPO is None, reason="no checkout: there is no history to ratchet against")
def test_a_baseline_strictly_preceding_head_is_accepted():
    """The positive control, so the refusal above cannot be passing by refusing everything.

    ``HEAD^1`` is the exact baseline the fixed workflow injects on a default-branch push;
    it strictly precedes HEAD, so the guard must let it through unchanged. Skips only in a
    truncated clone where HEAD has no reachable parent to resolve.
    """

    import subprocess

    probe = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD^1^{commit}"],
        cwd=str(REPO), capture_output=True, text=True,
    )
    if probe.returncode != 0:
        pytest.skip("HEAD has no reachable parent in this clone")
    parent = probe.stdout.strip()

    previous = os.environ.get("UGENCE_RATCHET_BASE")
    os.environ["UGENCE_RATCHET_BASE"] = "HEAD^1"
    try:
        assert baseline_revision(REPO) == parent
    finally:
        if previous is None:
            os.environ.pop("UGENCE_RATCHET_BASE", None)
        else:
            os.environ["UGENCE_RATCHET_BASE"] = previous


@pytest.mark.skipif(REPO is None, reason="no checkout: there is no history to ratchet against")
def test_this_change_did_not_widen_the_surface_without_disclosing_it():
    """The gate itself. Skips only where there is no honest baseline, never silently passes."""

    try:
        revision = baseline_revision(REPO)
        baseline = sources_at_revision(REPO, revision)
    except SurfaceRatchetBaselineUnavailable as exc:
        # A gate that quietly skips where it is supposed to run is not a gate. CI sets
        # UGENCE_RATCHET_REQUIRED, which turns an unresolvable baseline into a failure; a bare
        # clone with no history to compare against still skips, and says why.
        if os.environ.get("UGENCE_RATCHET_REQUIRED"):
            pytest.fail(f"UGENCE_RATCHET_REQUIRED is set and there is no baseline: {exc}")
        pytest.skip(f"no baseline: {exc}")

    current = {
        "completeness": COMPLETENESS.read_text(encoding="utf-8"),
        "changelog": (REPO / "packages/integration/cloud-scaling-authorization-contracts"
                      / "CHANGELOG.md").read_text(encoding="utf-8"),
    }
    assert ratchet_problems(baseline=baseline, current=current) == []
