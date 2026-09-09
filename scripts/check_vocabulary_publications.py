#!/usr/bin/env python3
"""Hold the published ``LV-1`` vocabularies to what ``PUB-1`` says they are.

``PUB-1`` publishes each vocabulary as a *separate, immutable specification*
identified by six elements, one of which is an authoritative content digest. A digest
nothing recomputes is decoration: it records that somebody once hashed something, and
it goes on reading correct after the file it describes has been edited. So the digest
is recomputed here, and an edit to a published version fails this gate. That is the
whole mechanism by which "immutable" is a property of the repository rather than a
sentence in a document.

**What is checked.**

1. Every published file carries all six identity elements, and a closed vocabulary
   has normative members while an open one has interpretation rules.
2. The recorded ``content_digest`` equals the digest recomputed over the rest of the
   file. This is the immutability guard.
3. The version is ``MAJOR.MINOR.PATCH`` with no ``v`` prefix, matches its filename,
   and has a zero minor — ``PUB-1`` reserves minor versions until an
   additive-compatibility rule is separately established.
4. No mutable ``latest`` exists: not as a filename, not as a symlink, not as a value
   any field carries. ``PUB-1`` refuses one, and ``VV-E`` refuses ``"latest"``
   semantics at the record boundary; a ``latest`` here would reintroduce by file what
   both refuse.
5. No file claims Policy Authority issuance. ``PUB-1`` is explicit that repository
   publication establishes canonical content and nothing more.
6. A closed vocabulary's members are exactly the members its ratified ballot section
   lists. Publication and ratification are two inventories of the same set, and the
   only thing worth checking about two inventories is that they agree.

**What is not checked.** Whether the content is *right* — whether ``HIGH_RISK`` is
well defined, whether Article 6 is the correct citation. Those are owner rulings and
legal determinations, settled in ``LV1_VOCABULARY_PUBLICATION_RULINGS.md`` and not by
a script.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
VOCABULARIES = REPO / "docs" / "vocabularies"
BALLOT = REPO / "docs" / "architecture" / "GOVERNANCE_LABEL_VOCABULARY_BALLOT.md"

VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

#: The six identity elements ``PUB-1`` requires, mapped to the field carrying each.
IDENTITY = {
    "identifier": "vocabulary",
    "version": "version",
    "content digest": "content_digest",
    "scope": "scope",
    "governing ruling": "governing_ruling",
    "members or interpretation rules": None,  # shape-dependent; checked separately
}

#: Ballot section holding each closed vocabulary's ratified members. An open
#: vocabulary has no member table to agree with, so it is absent by design.
BALLOT_SECTIONS = {
    "eu-ai-act-system-classification": "3.1",
    "data-classification": "3.2",
    "vendor-dependency-assessment-state": "3.4",
    "incident-severity": "3.5",
}

FORBIDDEN_CLAIMS = ("issued by policy authority", "signed policy", "policy authority issued")


def canonical(payload: dict) -> bytes:
    """The bytes a content digest is taken over: the specification minus the digest."""
    without = {key: value for key, value in payload.items() if key != "content_digest"}
    return json.dumps(without, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def expected_digest(payload: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical(payload)).hexdigest()


def ballot_members(section: str) -> list[str]:
    """The members a ballot section's table lists, in order.

    The tables are ``| `MEMBER` | meaning |``. Header and separator rows carry no
    backticked first cell, so they fall out without being special-cased.
    """
    text = BALLOT.read_text(encoding="utf-8")
    start = text.find(f"### {section} ")
    if start < 0:
        return []
    end = text.find("\n### ", start + 1)
    body = text[start:end if end > 0 else len(text)]
    members = []
    for line in body.splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 3:
            continue
        match = re.fullmatch(r"`([A-Z][A-Z0-9_]*)`", cells[1])
        if match:
            members.append(match.group(1))
    return members


def _check_one(path: pathlib.Path) -> list[str]:
    problems: list[str] = []
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"is not valid JSON: {exc}"]

    for element, field in IDENTITY.items():
        if field and not spec.get(field):
            problems.append(f"carries no {element} (field {field!r})")

    shape = spec.get("shape")
    if shape == "closed":
        if not spec.get("members"):
            problems.append("is closed but lists no normative members")
    elif shape == "open":
        if not spec.get("interpretation_rules"):
            problems.append("is open but states no interpretation rules")
        if spec.get("members"):
            problems.append("is open but lists normative members, which would close it")
    else:
        problems.append(f"declares no usable shape ({shape!r}); expected 'closed' or 'open'")

    version = str(spec.get("version", ""))
    match = VERSION.fullmatch(version)
    if not match:
        problems.append(f"version {version!r} is not MAJOR.MINOR.PATCH without a 'v' prefix")
    else:
        if path.stem != version:
            problems.append(f"version {version!r} does not match its filename {path.name!r}")
        if match.group(2) != "0":
            problems.append(
                f"version {version!r} uses a minor version, which PUB-1 reserves until an "
                "additive-compatibility rule is separately established")

    recorded = spec.get("content_digest", "")
    expected = expected_digest(spec)
    if recorded != expected:
        problems.append(
            f"content digest does not match its content.\n      recorded: {recorded}\n"
            f"      expected: {expected}\n      A published version is immutable: restore "
            "the content, or publish a new version.")

    if spec.get("immutable") is not True:
        problems.append("does not declare itself immutable")

    authority = spec.get("authority") or {}
    if authority.get("issued_by_policy_authority") is not False:
        problems.append(
            "must record authority.issued_by_policy_authority = false — repository "
            "publication establishes canonical content, never issuance (PUB-1)")

    lowered = path.read_text(encoding="utf-8").lower()
    for claim in FORBIDDEN_CLAIMS:
        if claim in lowered and "not issuance" not in lowered:
            problems.append(f"appears to claim Policy Authority issuance ({claim!r})")

    if "latest" in lowered:
        problems.append("mentions 'latest'; PUB-1 creates no mutable latest reference")

    section = BALLOT_SECTIONS.get(spec.get("vocabulary"))
    if section:
        ratified = ballot_members(section)
        published = [member["member"] for member in spec.get("members") or []]
        if not ratified:
            problems.append(f"ballot section {section} lists no members to agree with")
        elif ratified != published:
            problems.append(
                f"members disagree with ratified ballot section {section}.\n"
                f"      ballot:    {ratified}\n      published: {published}")

    return problems


def _name(path: pathlib.Path) -> str:
    """A path to report, whichever root ``VOCABULARIES`` currently points at.

    The failure-mode test repoints it at a temporary directory, which is the only way
    to prove the gate catches anything; naming a file must not crash when it does.
    """
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.relative_to(VOCABULARIES.parent).as_posix()


def violations() -> list[tuple[str, str]]:
    """Every (specification, reason) pair failing the gate, sorted by path."""
    found: list[tuple[str, str]] = []
    if not VOCABULARIES.is_dir():
        return [("docs/vocabularies", "no published vocabularies directory")]

    for path in sorted(VOCABULARIES.rglob("*")):
        if path.is_symlink():
            found.append((_name(path),
                          "is a symlink; a published version is a file, and a symlink is "
                          "the mutable alias PUB-1 refuses"))
    for path in sorted(VOCABULARIES.rglob("*.json")):
        relative = _name(path)
        if path.parent.name != path.parent.name.lower() or path.parent == VOCABULARIES:
            found.append((relative, "must live in docs/vocabularies/<identifier>/<version>.json"))
            continue
        spec_name = json.loads(path.read_text(encoding="utf-8")).get("vocabulary")
        if spec_name != path.parent.name:
            found.append((relative, f"declares identifier {spec_name!r} under directory "
                                    f"{path.parent.name!r}"))
        for problem in _check_one(path):
            found.append((relative, problem))
    return found


def main() -> int:
    published = sorted(VOCABULARIES.rglob("*.json")) if VOCABULARIES.is_dir() else []
    failures = violations()
    if not failures:
        print(f"VOCABULARY PUBLICATIONS OK — {len(published)} published specification(s), "
              "each with an intact content digest and members agreeing with the ballot")
        return 0
    print(f"{len(failures)} problem(s) across {len(published)} published specification(s):")
    for spec, reason in failures:
        print(f"  {spec} — {reason}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
