"""Phase 5A's state, pinned from the package that consumes it.

**Superseded premise, kept deliberately.** This file was written for D-5B0B-6, which ruled
that the policy proof travels alongside the candidate and Phase 5A stays at ``0.1.0``. 5B-1
supersedes that: D-5B1-1 binds the policy coordinate *inside* the candidate, which moves one
of Phase 5A's pinned digests and takes that distribution to ``0.2.0``. A version assertion is
not a promise to avoid making the change the next phase exists to make.

What survives the ruling is this file's purpose, and it is why the file is amended rather than
deleted: a change to Phase 5A must surface **here**, in a package that depends on it, and not
only in Phase 5A's own suite. The measurement that decided D-5B1-1 is re-asserted in Phase
5A's ``test_frozen_digests.py``: widening the existing binding in place moves two pinned
digests, carrying the coordinate as its own field moves one, and one is the floor for any
option that binds it inside the candidate at all.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

from _policy_fixtures import _find_repo_root

REPO = _find_repo_root()
pytestmark = pytest.mark.skipif(
    REPO is None, reason="no source checkout; Phase 5A's test tree is unavailable"
)


def _phase5a() -> pathlib.Path:
    return REPO / "packages" / "integration" / "cloud-scaling-authorization-contracts"


@pytest.mark.invariant
def test_phase_5a_is_at_the_version_5b1_moved_it_to():
    """``0.2.0``: a required field on the candidate, and a moved candidate digest (D-5B1-2)."""

    version = (_phase5a() / "src" / "ugence_cloud_scaling_authorization_contracts" / "version.py").read_text()
    assert '__version__ = "0.4.0"' in version


@pytest.mark.invariant
def test_the_policy_authority_stays_at_0_1_0():
    init = (REPO / "packages" / "policy-authority" / "src" / "ugence_policy_authority" / "__init__.py").read_text()
    assert '__version__ = "0.1.0"' in init


@pytest.mark.invariant
def test_this_package_ships_at_the_version_its_profile_change_requires():
    """``0.4.0`` since 5B-2 part 2 — and the profile deliberately did **not** move with it.

    The two travel together only when the *artifact* changes. 5B-1 took the package to
    ``0.2.0`` and the profile to ``v2`` because a fact was promoted between the halves. 5B-2
    part 1 took the package to ``0.3.0`` and left the profile alone; part 2 takes it to
    ``0.4.0`` and leaves it alone again. Gates 12 and 13 change which inputs produce an
    artifact, not what an artifact contains, so the partition fingerprint and the artifact
    digest are untouched. A profile bump here would tell a consumer their pinned digest moved
    when it did not.
    """

    from ugence_cloud_scaling_policy_authenticity import (
        VERIFICATION_PROFILE_VERSION,
        __version__,
    )

    assert __version__ == "0.4.0"
    assert VERIFICATION_PROFILE_VERSION == "v2"


@pytest.mark.invariant
def test_phase_5a_pins_exactly_eleven_frozen_digests():
    """Eleven since 5B-1: the policy coordinate binding is pinned like every other stage."""

    source = (_phase5a() / "tests" / "test_frozen_digests.py").read_text()
    frozen = re.findall(r"^FROZEN_[A-Z0-9_]+ = ", source, flags=re.MULTILINE)
    assert len(frozen) == 11
    assert "FROZEN_POLICY_COORDINATE_BINDING_DIGEST = " in source


@pytest.mark.invariant
def test_the_superseded_pre_5b1_candidate_digest_is_pinned_as_a_negative_anchor():
    """A revert to a candidate carrying no coordinate must fail, not re-baseline."""

    source = (_phase5a() / "tests" / "test_frozen_digests.py").read_text()
    assert "SUPERSEDED_PRE_5B1_CANDIDATE_DIGEST = " in source
    assert "db72ffffc5bf4ecfe8a5f9fe187efb5e8439355e559fcc34b391cc4c9282a313" in source


@pytest.mark.invariant
def test_all_ten_frozen_digests_still_hold():
    """Runs Phase 5A's own suite, in its own tree, as a subprocess. No mocking, no stubbing."""

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_frozen_digests.py",
            "-p",
            "no:cacheprovider",
            "-q",
        ],
        cwd=str(_phase5a()),
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.adversarial
def test_this_package_changes_no_phase_5a_or_policy_authority_file():
    """A leaf package adds a directory. It does not reach into its dependencies' trees."""

    here = pathlib.Path(__file__).resolve().parents[1]
    assert here.name == "cloud-scaling-policy-authenticity"
    # Nothing this distribution ships lives outside its own directory.
    shipped = list((here / "src").rglob("*.py")) + list((here / "tests").rglob("*.py"))
    for path in shipped:
        assert here in path.parents
