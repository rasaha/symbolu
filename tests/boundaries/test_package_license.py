"""A package may not ship without a LICENSE, or with one its metadata contradicts.

Thirty-two of seventy-two packages had no LICENSE file when this was written, while
all seventy-two declared ``license = { text = "Proprietary" }``. The declaration was
uniform and the files were not, so the presence of a LICENSE recorded nothing about
the package's licensing — only whether whoever added it happened to copy one in.

The thirty-two were normalized first and this gate added afterwards, so it has never
been a gate that fails on work nobody has done. These tests assert the class.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "check_package_license.py"

sys.path.insert(0, str(REPO / "scripts"))
import check_package_license as licensing  # noqa: E402


def test_every_package_ships_a_license_consistent_with_its_metadata():
    failures = licensing.violations()
    assert not failures, (
        "these packages have no LICENSE, or one contradicting their pyproject.toml:\n  "
        + "\n  ".join(f"{package} — {reason}" for package, reason in failures))


def test_the_script_agrees_with_the_test_and_exits_zero():
    """The gate CI runs and the gate the suite runs are the same gate."""

    result = subprocess.run([sys.executable, str(SCRIPT)],
                            capture_output=True, text=True, cwd=str(REPO))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PACKAGE LICENSE OK" in result.stdout


def test_the_check_can_actually_fail(tmp_path):
    """A gate that cannot fail is not a gate.

    Rather than trusting the report, this points the detector at a package that
    declares a license and ships a LICENSE naming a different one, and asserts it is
    caught. A missing file and a contradicting file are separate failures, so both
    are provoked.
    """

    real = licensing.PACKAGES
    try:
        licensing.PACKAGES = tmp_path

        missing = tmp_path / "no-license-file"
        missing.mkdir()
        (missing / "pyproject.toml").write_text(
            '[project]\nname = "x"\nlicense = { text = "Proprietary" }\n')

        contradicting = tmp_path / "wrong-license-text"
        contradicting.mkdir()
        (contradicting / "pyproject.toml").write_text(
            '[project]\nname = "y"\nlicense = { text = "Proprietary" }\n')
        (contradicting / "LICENSE").write_text("MIT License\n")

        found = dict(licensing.violations())
    finally:
        licensing.PACKAGES = real

    assert "no LICENSE file" in found["no-license-file"]
    assert "does not match" in found["wrong-license-text"]
    # and the real tree is still clean afterwards
    assert licensing.violations() == []


def test_a_longer_license_text_is_permitted_when_it_names_the_same_license():
    """Five distinct LICENSE texts exist, from a bare word to a twelve-line notice.

    All five name the same license and differ only in how much they say about it, so
    the gate requires agreement, not byte-equality. A package may say more; it may
    not say something else.
    """

    texts = {
        (package / "LICENSE").read_text(encoding="utf-8")
        for package in (p.parent for p in licensing.PACKAGES.rglob("pyproject.toml"))
        if (package / "LICENSE").exists()
    }
    assert len(texts) > 1, "this test is pointless if every LICENSE is identical"
    for text in texts:
        assert text.lstrip().startswith("Proprietary"), text[:60]


def test_no_package_is_exempt_without_a_stated_reason():
    """``EXEMPT`` is a place to defend a decision, not to park a package."""

    for package, reason in licensing.EXEMPT.items():
        assert reason.strip(), package
        assert (REPO / package).is_dir(), f"{package} is exempt but does not exist"
