"""Documentation consistency for the Agentic Proposer's own documents.

**What this guard covers, and what it does not (G-8).** It checks the documents this
package owns, plus the readiness ADR, and it checks them for the properties that can go
wrong when several documents record one decision: a second competing account of an owner
decision, a restored *Open owner decisions* section, a cross-reference to a section that
does not exist, a status claim that has gone stale, and a relative link that does not
resolve.

Two repository-wide gates exist, and their coverage is stated exactly rather than
implied:

* ``scripts/check_doc_links.py`` runs over a **curated list**, and this package's
  documents are named in it, so its link coverage of them is real. The link check below
  is the same rule enforced package-locally, so a document added here is covered without
  waiting for the repository list to be edited.
* ``scripts/validate_terminology.py`` runs over a **different curated list**, and this
  package's documents are deliberately **not** in it. Its rules are specific to the
  Decision Governance terminology ADR — the umbrella phrasing, the Decision Authority
  naming, the control-plane optionality — and none of them applies to an advisory
  capability's contract specification. **No claim of terminology coverage is made for
  these documents**, here or in ``S1_ENFORCEMENT.md``.

A gate whose curated input does not name a document does not cover it, whatever the
gate's title suggests. That is why the coverage each gate genuinely provides is asserted
below rather than assumed.
"""
from __future__ import annotations

import pathlib
import re

import pytest

PKG_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = PKG_ROOT.parents[2]

README = PKG_ROOT / "README.md"
ENFORCEMENT = PKG_ROOT / "docs" / "S1_ENFORCEMENT.md"
SPECIFICATION = PKG_ROOT / "docs" / "S1_CONTRACT_AND_EQUATION_SPECIFICATION.md"
SCOPE = PKG_ROOT / "docs" / "S0_SCOPE.md"
CHANGELOG = PKG_ROOT / "CHANGELOG.md"
ADR = (REPO_ROOT / "docs" / "architecture"
       / "ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md")

#: Every document this guard governs.
DOCUMENTS = (README, ENFORCEMENT, SPECIFICATION, SCOPE, CHANGELOG, ADR)

#: The repository-wide link gate, and the curated list it actually reads.
LINK_GATE = REPO_ROOT / "scripts" / "check_doc_links.py"
TERMINOLOGY_GATE = REPO_ROOT / "scripts" / "validate_terminology.py"

LINK = re.compile(r"\[[^\]]*\]\((?!https?://)([^)#]+)(?:#[^)]*)?\)")


def _text(path):
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_the_document_exists(path):
    assert path.is_file(), f"missing governed document: {path}"


# --------------------------------------------------------------------------- #
# One account of OD-1 – OD-4, and no restored open decisions
# --------------------------------------------------------------------------- #

def test_there_is_exactly_one_owner_decision_record():
    """The ADR's OD-1 – OD-4 table is the single **decision record**.

    That is a narrower claim than "one account", and the narrower claim is the true one.
    The specification carries its own full per-decision statement under its
    *Owner decisions* section, and that is correct rather than a duplication to be
    removed: the specification is the implementation-ready document, OD-4 changed
    contract shape, and OD-1 and OD-2 carry riders an implementer must read where the
    contracts are stated. What the ADR alone carries is the **record** — the table that
    says, for each decision, that it is ratified, on what date, whether it bears on
    contract shape, and which guard enforces it.

    So this guard checks the property that actually matters: no document outside the ADR
    may carry a rival *ratification section* — a heading that reads as a second place a
    decision was made — and, because a second full statement is permitted, the two
    documents must not **disagree**. The divergence check is
    ``test_the_adr_and_the_specification_agree_on_every_owner_decision`` below; without
    it, narrowing this claim would trade a false sentence for an unguarded risk.
    """
    assert "## Owner decisions OD-1 – OD-4 — all resolved" in _text(ADR)
    competing = []
    for path in DOCUMENTS:
        if path == ADR:
            continue
        for heading in re.findall(r"^#{1,6}\s+(.*OD-[1-4].*)$", _text(path), re.M):
            competing.append(f"{path.name}: {heading}")
    assert not competing, (
        f"a rival OD-1 – OD-4 ratification heading exists outside the ADR: {competing}")


#: The four decisions, and the facts both documents must state identically about each.
OWNER_DECISIONS = (1, 2, 3, 4)
_DATE = r"(\d{4}-\d{2}-\d{2})"


def _normalised(path):
    """Whitespace-collapsed text. Both documents wrap these statements across lines, so
    a line-oriented match would miss them for a reason that has nothing to do with what
    they say."""
    return " ".join(_text(path).split())


def _ratification_dates(body, od):
    return set(re.findall(rf"OD-{od}\b[^|]{{0,200}}?RATIFIED[^.|]{{0,40}}?{_DATE}", body))


def _resolution_letters(body, od):
    return set(re.findall(
        rf"OD-{od}\b[^|]{{0,200}}?RATIFIED[^|]{{0,40}}?resolved\s*\(([a-z])\)", body))


@pytest.mark.parametrize("od", OWNER_DECISIONS)
def test_the_adr_and_the_specification_agree_on_every_owner_decision(od):
    """The divergence check the narrowed claim above depends on.

    Two documents stating one decision in full is only safe while they say the same
    thing. Markdown headings cannot see that: both documents could record OD-4 as
    ratified and disagree about *what was ratified*, and every heading-shaped guard
    would stay green. This reads the statements themselves.

    Compared, for each decision: that both documents record it as RATIFIED at all, and
    that they name the **same ratification date**. A date that drifts in one document is
    the cheapest early sign that the two accounts have been edited apart.
    """
    adr, spec = _normalised(ADR), _normalised(SPECIFICATION)
    adr_dates, spec_dates = _ratification_dates(adr, od), _ratification_dates(spec, od)
    assert adr_dates, f"the ADR records no ratification date for OD-{od}"
    assert spec_dates, f"the specification records no ratification date for OD-{od}"
    assert adr_dates == spec_dates, (
        f"OD-{od} is ratified {sorted(adr_dates)} in the ADR and {sorted(spec_dates)} "
        "in the specification; the two accounts have diverged")


def test_the_adr_and_the_specification_agree_on_od_4s_resolution():
    """OD-4 is the one decision that changed contract shape, so it is the one whose
    divergence would silently misdirect an implementer. Both documents must name the
    same resolution letter."""
    adr = _resolution_letters(_normalised(ADR), 4)
    spec = _resolution_letters(_normalised(SPECIFICATION), 4)
    assert adr == {"a"}, f"the ADR does not record OD-4 resolved (a): {adr}"
    assert spec == {"a"}, f"the specification does not record OD-4 resolved (a): {spec}"


def test_only_od_4_is_recorded_as_bearing_on_contract_shape():
    """The ADR table's third column is the load-bearing distinction between a decision
    about a guard and a decision about the contracts. OD-1 – OD-3 change no contract,
    field type, cardinality, vocabulary or equation term; OD-4 did. If that column ever
    said otherwise for one of the first three, the specification's Part D would be
    downstream of a decision nobody re-read it against."""
    rows = re.findall(r"\| \*\*OD-([1-4])\*\* — \*\*RATIFIED[^|]*\|[^|]*\|([^|]*)\|",
                      _text(ADR))
    bears = {od: cell.strip().lower() for od, cell in rows}
    assert set(bears) == {"1", "2", "3", "4"}, (
        f"the ADR decision table does not carry all four rows: {sorted(bears)}")
    for od in ("1", "2", "3"):
        assert bears[od] == "no", f"OD-{od} is recorded as bearing on contract shape"
    assert bears["4"].startswith("**yes"), (
        f"OD-4 must be recorded as bearing on contract shape: {bears['4']!r}")
    assert "OD-4 did change contract shape" in _normalised(SPECIFICATION), (
        "the specification must agree that OD-4 is the one that changed contract shape")


def test_no_competing_second_round_ratification_section_survives():
    """The fold rule: guard evidence is subordinate detail, not a rival ratification."""
    for path in DOCUMENTS:
        body = _text(path)
        assert "Ratified refinements, second round" not in body, path.name
        assert "## OD-1 —" not in body or path == ADR, path.name


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_no_open_owner_decisions_section_is_restored(path):
    """All four owner decisions are resolved. A section headed *Open owner decisions*
    reads as a live question whatever its body says, so none may exist."""
    headings = re.findall(r"^#{1,6}\s+(.*)$", _text(path), re.M)
    offenders = [h for h in headings if re.search(r"open\s+owner\s+decision", h, re.I)]
    assert not offenders, f"{path.name}: {offenders}"


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_no_owner_decision_is_described_as_outstanding(path):
    """A ruling is outstanding or it is not. None is."""
    body = _text(path)
    for phrase in ("owner decision remains open",
                   "owner decisions remain open",
                   "a ruling is outstanding",
                   "awaiting a ruling"):
        assert phrase.lower() not in body.lower(), f"{path.name}: {phrase}"


def test_the_four_owner_decisions_are_each_recorded_as_ratified():
    body = _text(ADR)
    for od in ("OD-1", "OD-2", "OD-3", "OD-4"):
        assert re.search(rf"\*\*{od}\*\* — \*\*RATIFIED", body), od
    assert "All four owner decisions are resolved" in _text(SPECIFICATION)


# --------------------------------------------------------------------------- #
# No stale branch-status or "section does not exist" claims
# --------------------------------------------------------------------------- #

#: Wording that asserts something about an unmerged branch or a temporary SHA. Durable
#: text may say a decision is ratified, that a named guard enforces it, and that
#: production implementation is separately gated. It may not say that a guard lives on a
#: branch that is not merged, because that is true only until it is not.
STALE_STATUS_PATTERNS = (
    r"\bis\s+\*\*not\s+merged\*\*",
    r"\bis\s+not\s+merged\b",
    r"\bunmerged\s+branch\b",
    r"\bunmerged\s+head\b",
    r"\bimplemented\s+on\s+an?\s+unmerged\b",
    r"\bnot\s+merged,\s+so\b",
    r"\bpending\s+merged\s+enforcement\b",
    r"\bimplemented,\s+not\s+merged\b",
    r"\bonly\s+the\s+merge\s+is\s+outstanding\b",
)

#: Commit identifiers whose truth was temporary. A SHA-based claim is a claim about a
#: moment, and a document that carries one states a fact that expires.
SHA_CLAIM = re.compile(r"\bat\s+`?[0-9a-f]{7,40}`?\b")


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_no_stale_unmerged_branch_assertion_survives(path):
    body = _text(path)
    offenders = []
    for pattern in STALE_STATUS_PATTERNS:
        for match in re.finditer(pattern, body, re.I):
            line = body.count("\n", 0, match.start()) + 1
            offenders.append(f"{path.name}:{line}: {match.group(0)!r}")
    assert not offenders, offenders


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_no_temporary_sha_based_truth_survives(path):
    """The CHANGELOG may record history; a status claim may not rest on a SHA."""
    if path == CHANGELOG:
        pytest.skip("a changelog records what happened, including where")
    offenders = [m.group(0) for m in SHA_CLAIM.finditer(_text(path))]
    assert not offenders, f"{path.name}: {offenders}"


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_no_contradictory_section_does_not_exist_statement(path):
    """A document may not both carry a section and say that section is absent.

    This is the exact defect an automatic merge produced: the *What O-1 – O-4 changed*
    section was retained from one side while a sentence from the other side said the
    same section did not exist here.
    """
    body = _text(path)
    claims = re.findall(r"\*?([A-Z][^*\n]{3,60}?)\*?\s+section[^.\n]*?"
                        r"(?:does not exist|no revision of this artifact carried)",
                        body)
    headings = {h.strip().strip("*`") for h in re.findall(r"^#{1,6}\s+(.*)$", body, re.M)}
    contradictions = [c for c in claims if c.strip().strip("*`") in headings]
    assert not contradictions, f"{path.name}: {contradictions}"


def test_the_enforcement_document_carries_the_section_it_points_at():
    """The specific cross-reference the merge broke, asserted directly in both
    directions: the section exists, and nothing claims it does not."""
    body = _text(ENFORCEMENT)
    assert "## What O-1 – O-4 changed" in body
    assert "which does not exist here" not in body


def test_the_ratified_refinements_section_lives_in_the_adr():
    assert "## Ratified refinements (O-1 – O-4)" in _text(ADR)


# --------------------------------------------------------------------------- #
# The registry is a mirror, and the documents say so
# --------------------------------------------------------------------------- #

def test_the_specification_is_named_as_the_governing_authority():
    for path in (README, ENFORCEMENT):
        assert "S1_CONTRACT_AND_EQUATION_SPECIFICATION.md" in _text(path), path.name


def test_the_enforcement_document_states_the_registry_is_a_mirror():
    body = " ".join(_text(ENFORCEMENT).split())
    assert "exact mirror" in body or "enforcement mirror" in body
    assert "originates no contract field" in body or "originate a contract field" in body


# --------------------------------------------------------------------------- #
# Internal links resolve
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_every_relative_link_resolves(path):
    broken = []
    for match in LINK.finditer(_text(path)):
        target = match.group(1).strip()
        if not (path.parent / target).resolve().exists():
            broken.append(target)
    assert not broken, f"{path.name}: {broken}"


# --------------------------------------------------------------------------- #
# G-8 — the coverage claims made about the repository gates are true
# --------------------------------------------------------------------------- #

def test_the_repository_link_gate_actually_names_these_documents():
    """The claim of link coverage is only true if the curated list names the files."""
    assert LINK_GATE.is_file()
    listed = _text(LINK_GATE)
    for path in (ADR, README, ENFORCEMENT, SPECIFICATION, SCOPE):
        rel = path.resolve().relative_to(REPO_ROOT).as_posix()
        assert f'"{rel}"' in listed, (
            f"{rel} is not in check_doc_links.py's curated list, so no link coverage "
            "may be claimed for it")


def test_no_terminology_coverage_is_claimed_for_these_documents():
    """The other half of G-8, and the honest one.

    ``validate_terminology.py`` enforces Decision Governance terminology rules over its
    own curated set. These documents are not in it and must not be added to it: they
    would fail rules that do not apply to them, and passing them by weakening those
    rules would damage the gate for the documents it does govern. So no terminology
    claim is made — asserted here so a later edit cannot introduce one quietly.
    """
    assert TERMINOLOGY_GATE.is_file()
    governed = _text(TERMINOLOGY_GATE)
    for path in (ADR, README, ENFORCEMENT, SPECIFICATION, SCOPE):
        rel = path.resolve().relative_to(REPO_ROOT).as_posix()
        assert f'"{rel}"' not in governed, (
            f"{rel} was added to validate_terminology.py's curated set; either its "
            "rules now genuinely apply, or the addition is a false coverage claim")
    # A document may NAME the gate in order to disclaim it — that is the honest form,
    # and it is what these documents do. What may not appear is an affirmative claim.
    claims = (
        r"validate_terminology[^.\n]*\b(?:covers|governs|enforces|includes|applies to)\b",
        r"terminology (?:gate|validation|check)[^.\n]*\b(?:covers|governs|includes)\b",
        r"\bcovered by (?:the )?terminology\b",
    )
    for path in DOCUMENTS:
        body = _text(path)
        for pattern in claims:
            found = re.findall(pattern, body, re.I)
            assert not found, (
                f"{path.name} claims terminology-gate coverage it does not have: {found}")
