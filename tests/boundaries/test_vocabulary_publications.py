"""A published ``LV-1`` vocabulary is immutable, and this is what makes that true.

``PUB-1`` publishes each vocabulary as a separate, immutable specification carrying an
authoritative content digest. Immutability is not a property a document can assert
about itself: the digest has to be recomputed by something, or an edit to a published
version goes unnoticed and the digest keeps reading correct about content that has
changed underneath it.

These tests assert the class of guarantee rather than the four files that exist today,
and the third one provokes each failure the gate exists to catch — a gate that cannot
fail is not a gate.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "check_vocabulary_publications.py"

sys.path.insert(0, str(REPO / "scripts"))
import check_vocabulary_publications as vocab  # noqa: E402


def _published() -> list[pathlib.Path]:
    return sorted(vocab.VOCABULARIES.rglob("*.json"))


def test_every_published_specification_is_intact():
    failures = vocab.violations()
    assert not failures, (
        "these published vocabularies fail PUB-1:\n  "
        + "\n  ".join(f"{spec} — {reason}" for spec, reason in failures))


def test_the_script_agrees_with_the_test_and_exits_zero():
    """The gate CI runs and the gate the suite runs are the same gate."""

    result = subprocess.run([sys.executable, str(SCRIPT)],
                            capture_output=True, text=True, cwd=str(REPO))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "VOCABULARY PUBLICATIONS OK" in result.stdout


def test_the_check_can_actually_fail(tmp_path):
    """Point the detector at deliberately broken publications and watch it catch them.

    Four failures, because four separate things would otherwise pass silently: content
    edited under a stale digest, a mutable ``latest``, a reserved minor version, and a
    specification claiming Policy Authority issuance.
    """

    good = json.loads(_intact_specification())
    real = vocab.VOCABULARIES
    try:
        vocab.VOCABULARIES = tmp_path

        edited = dict(good, scope="something else entirely")
        _write(tmp_path / "edited-under-a-stale-digest", "1.0.0", edited,
               recompute=False)

        _write(tmp_path / "mutable-alias", "1.0.0",
               dict(good, scope="resolve latest at read time"))

        _write(tmp_path / "reserved-minor", "1.1.0", dict(good, version="1.1.0"))

        claiming = dict(good, authority=dict(good["authority"],
                                             issued_by_policy_authority=True))
        _write(tmp_path / "claiming-issuance", "1.0.0", claiming)

        found: dict[str, list[str]] = {}
        for spec, reason in vocab.violations():
            found.setdefault(pathlib.Path(spec).parent.name, []).append(reason)
    finally:
        vocab.VOCABULARIES = real

    assert any("content digest does not match" in r
               for r in found["edited-under-a-stale-digest"])
    assert any("latest" in r for r in found["mutable-alias"])
    assert any("minor version" in r for r in found["reserved-minor"])
    assert any("issued_by_policy_authority" in r for r in found["claiming-issuance"])

    # and the real tree is still clean afterwards
    assert vocab.violations() == []


def test_no_published_version_carries_a_mutable_latest_alias():
    """``PUB-1`` creates none, and ``VV-E`` refuses ``"latest"`` at the record boundary.

    A ``latest`` file or symlink here would reintroduce by filesystem exactly what both
    refuse — a reference whose meaning changes when someone publishes.
    """

    for path in vocab.VOCABULARIES.rglob("*"):
        assert not path.is_symlink(), path
        assert "latest" not in path.name.lower(), path


def test_a_published_specification_never_claims_to_be_issued_policy():
    """Repository publication is canonical content. Issuance is a different act."""

    for path in _published():
        spec = json.loads(path.read_text(encoding="utf-8"))
        assert spec["authority"]["issued_by_policy_authority"] is False, path
        assert spec["authority"]["repository_published"] is True, path


def test_the_digest_covers_the_content_and_not_itself():
    """Changing any field must change the digest; the digest field must not feed itself.

    Both halves matter. If the digest did not cover the content, an edit would be
    invisible; if it covered itself, no value could ever be correct.
    """

    for path in _published():
        spec = json.loads(path.read_text(encoding="utf-8"))
        assert vocab.expected_digest(spec) == spec["content_digest"], path

        moved = dict(spec, scope=spec["scope"] + " (edited)")
        assert vocab.expected_digest(moved) != spec["content_digest"], path

        # The recorded digest is excluded from what is digested, so a wrong value
        # does not change what the correct value would have been.
        stale = dict(spec, content_digest="sha256:" + "0" * 64)
        assert vocab.expected_digest(stale) == spec["content_digest"], path


def test_a_closed_vocabulary_agrees_with_the_ballot_that_ratified_it():
    """Publication and ratification are two inventories of one set."""

    for path in _published():
        spec = json.loads(path.read_text(encoding="utf-8"))
        section = vocab.BALLOT_SECTIONS.get(spec["vocabulary"])
        if not section:
            continue
        ratified = vocab.ballot_members(section)
        assert ratified, f"ballot section {section} parsed to nothing"
        assert [m["member"] for m in spec["members"]] == ratified, path


def test_an_open_vocabulary_publishes_rules_rather_than_members():
    """``LV-E`` ratified a shape. A member list would close what was ruled open."""

    open_specs = [json.loads(p.read_text(encoding="utf-8")) for p in _published()]
    open_specs = [s for s in open_specs if s["shape"] == "open"]
    assert open_specs, "this test is pointless if no open vocabulary is published"
    for spec in open_specs:
        assert spec["members"] is None, spec["vocabulary"]
        assert spec["interpretation_rules"], spec["vocabulary"]


def _intact_specification() -> str:
    """A real published specification, used as the base for the failure cases."""
    return (vocab.VOCABULARIES / "data-classification" / "1.0.0.json").read_text(
        encoding="utf-8")


def _write(directory: pathlib.Path, version: str, spec: dict,
           recompute: bool = True) -> None:
    """Write a specification under its own directory, naming it after that directory.

    ``recompute`` re-derives the digest so a case provokes only the failure it means
    to; the stale-digest case leaves it alone, because a stale digest *is* the failure.
    """

    directory.mkdir(parents=True, exist_ok=True)
    spec = dict(spec, vocabulary=directory.name)
    if recompute:
        spec["content_digest"] = vocab.expected_digest(spec)
    (directory / f"{version}.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
