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

The **strategy-authority scan** (OD-5) is stated here on the same terms, because it is
the one check in this module whose subject is a claim rather than a structure:

* It is a **heuristic spot-check over enumerated forms, and it does not cover the
  class.** It classifies sentences by actor, refusing a claim of selection, validation or
  binding whose subject is S1 or something inside it, and passing the same claim
  attributed to S2. What it is proven against is a named corpus — claims it must catch,
  including spellings successive audits found escaping earlier versions, and correct
  statements it must leave alone. That corpus is the whole of the guarantee.
* Two shapes it **does not reach**, both structural rather than lexical: a claim written
  **across two table cells**, where the actor sits in one column and the predicate in
  another and no sentence contains both; and a claim **split between a lead-in stem and a
  numbered item**, where the stem carries the actor and the item carries the predicate.
  Sentences are found within blocks, and a block boundary falls between both pairs.

A gate whose curated input does not name a document does not cover it, whatever the
gate's title suggests. That is why the coverage each gate genuinely provides is asserted
below rather than assumed.
"""
from __future__ import annotations

import importlib
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

#: Words that turn a heading citing a decision into a heading that reads as the place the
#: decision was *made*. A subordinate document may head a section with a decision id as
#: provenance — the specification states OD-5's consequences under four such headings, in
#: the sections an implementer reads — and that is not a rival ratification. A heading
#: that also announces ratification or resolution is.
_RATIFICATION_HEADING_WORDS = ("ratified", "resolved", "owner decision", "decision record")


def test_there_is_exactly_one_owner_decision_record():
    """The ADR's OD-1 – OD-6 table is the single **decision record**.

    That is a narrower claim than "one account", and the narrower claim is the true one.
    The specification carries its own full per-decision statement under its
    *Owner decisions* section, and that is correct rather than a duplication to be
    removed: the specification is the implementation-ready document, OD-4 changed
    contract shape, and OD-1 and OD-2 carry riders an implementer must read where the
    contracts are stated. The specification states, for each decision, that it is
    ratified, on what date, whether it bears on contract shape and what enforces it, and
    may legitimately do so. What the ADR alone carries is the **authority** — it is the
    place a decision is *made*, and the OD-1 – OD-4 table is that record.

    So this guard checks the property that actually matters: no document outside the ADR
    may carry a rival *ratification section* — a heading that reads as a second place a
    decision was made — and, because a second full statement is permitted, the two
    documents must not **disagree**. The divergence check is
    ``test_the_adr_and_the_specification_agree_on_every_owner_decision`` below; without
    it, narrowing this claim would trade a false sentence for an unguarded risk.
    """
    assert "## Owner decisions OD-1 – OD-6 — all resolved" in _text(ADR)
    competing = []
    for path in DOCUMENTS:
        if path == ADR:
            continue
        for heading in re.findall(r"^#{1,6}\s+(.*OD-[1-6]\b.*)$", _text(path), re.M):
            if any(w in heading.lower() for w in _RATIFICATION_HEADING_WORDS):
                competing.append(f"{path.name}: {heading}")
    assert not competing, (
        f"a rival OD-1 – OD-6 ratification heading exists outside the ADR: {competing}")


def test_the_rival_heading_scan_still_catches_a_rival_heading():
    """The scan above runs over clean documents, and a scan narrowed into inertness
    reports clean too. Both halves of the narrowing are exercised: a heading that merely
    cites a decision passes, and one that announces a ratification is caught."""
    def offenders(heading):
        return [heading] if any(
            w in heading.lower() for w in _RATIFICATION_HEADING_WORDS) else []

    for benign in ("### The four-way distinction (OD-5)",
                   "### `declared_strategy` — an assertion (OD-5)",
                   "### A reserved list, an allowlist later (OD-5)"):
        assert not offenders(benign), f"the scan flags a provenance heading: {benign}"
    for rival in ("## OD-5 — RATIFIED 2026-08-26",
                  "## Owner decisions OD-1 – OD-5 — all resolved",
                  "### OD-5 resolved here",
                  "## The OD-5 decision record"):
        assert offenders(rival), f"the scan no longer catches a rival heading: {rival}"


#: The six decisions, and the facts both documents must state identically about each.
#: OD-5 (2026-08-26) and OD-6 (2026-08-27) join OD-1 – OD-4 (2026-08-25); the dates
#: differ per decision and are compared per decision, so a sixth entry does not weaken
#: the agreement check.
OWNER_DECISIONS = (1, 2, 3, 4, 5, 6)
_DATE = r"(\d{4}-\d{2}-\d{2})"


def _normalised(path):
    """Whitespace-collapsed text. Both documents wrap these statements across lines, so
    a line-oriented match would miss them for a reason that has nothing to do with what
    they say."""
    return " ".join(_text(path).split())


def _ratification_dates(body, od):
    return set(re.findall(rf"OD-{od}\b[^|]{{0,200}}?RATIFIED[^.|]{{0,40}}?{_DATE}", body))


#: Any ``resolved (x)`` statement, wherever it stands. Written as a *tempered* match —
#: the gap may not contain another ``OD-<n>`` — so each statement is attributed to the
#: decision that actually introduces it rather than to whichever id appeared first.
_RESOLUTION = re.compile(r"OD-(\d)\b((?:(?!OD-\d).){0,300}?)resolved\s*\(([a-z])\)")

#: A bare ``resolved (x)``, used only to prove the attributed count above is the whole
#: population and not the subset one anchor happened to reach.
_BARE_RESOLUTION = re.compile(r"resolved\s*\(([a-z])\)")

#: How many resolution statements each document carries today. Pinned so that adding a
#: fourth, or deleting one, is a diff a reviewer sees rather than a silent change in what
#: the agreement check covers.
RESOLUTION_STATEMENTS = {"ADR": 3, "SPECIFICATION": 3}


def _resolutions(body):
    """Every ``(od, letter)`` resolution statement in ``body``.

    An earlier form of this helper anchored on ``RATIFIED`` and so matched exactly one
    statement per document. Both documents restate OD-4's resolution three times,
    including in Part D where an implementer reads contract shape, and those
    restatements were unguarded: flipping one to ``(b)`` left the whole suite green.
    """
    return [(int(od), letter) for od, _gap, letter in _RESOLUTION.findall(body)]


def _resolution_letters(body, od):
    return {letter for found, letter in _resolutions(body) if found == od}


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


@pytest.mark.parametrize("label,path", (("ADR", ADR), ("SPECIFICATION", SPECIFICATION)))
def test_every_resolution_statement_in_each_document_says_the_same_thing(label, path):
    """A document must not contradict itself, and a guard that reads one statement
    cannot see that it does.

    Every ``resolved (x)`` statement in the document is collected, not only the one an
    anchor reaches. Each must name OD-4 — no other decision is recorded with a
    resolution letter — and each must name ``(a)``. The count is pinned so a statement
    added or removed changes this test rather than quietly changing its coverage, and
    the attributed count is checked against the bare population so a statement standing
    too far from its ``OD-<n>`` anchor is reported instead of skipped.
    """
    body = _normalised(path)
    found = _resolutions(body)
    bare = _BARE_RESOLUTION.findall(body)
    assert len(found) == len(bare), (
        f"{label}: {len(bare)} resolution statements exist but only {len(found)} could "
        "be attributed to a decision; an unattributed statement is unguarded")
    assert len(found) == RESOLUTION_STATEMENTS[label], (
        f"{label} carries {len(found)} resolution statements, not "
        f"{RESOLUTION_STATEMENTS[label]}; if that is intended, update the pinned count "
        "so the change is reviewed rather than absorbed")
    assert {od for od, _ in found} == {4}, (
        f"{label} records a resolution letter for a decision other than OD-4: "
        f"{sorted({od for od, _ in found})}")
    assert {letter for _, letter in found} == {"a"}, (
        f"{label} does not say OD-4 is resolved (a) everywhere it says so at all: "
        f"{sorted({letter for _, letter in found})}")


def test_the_adr_and_the_specification_agree_on_od_4s_resolution():
    """OD-4 is the one decision that changed contract shape, so it is the one whose
    divergence would silently misdirect an implementer. Both documents must name the
    same resolution letter — at **every** place either states it, per the test above."""
    adr = _resolution_letters(_normalised(ADR), 4)
    spec = _resolution_letters(_normalised(SPECIFICATION), 4)
    assert adr == {"a"}, f"the ADR does not record OD-4 resolved (a): {adr}"
    assert spec == {"a"}, f"the specification does not record OD-4 resolved (a): {spec}"
    assert adr == spec, (
        f"the two documents disagree on OD-4's resolution: ADR {sorted(adr)}, "
        f"specification {sorted(spec)}")


def _shape_bearing_decisions():
    """The set of owner decisions the ADR table records as bearing on contract shape.

    Derived from the table rather than hard-coded, so the prose checks below follow the
    ruling instead of needing to be rewritten whenever one changes.
    """
    rows = re.findall(r"\| \*\*OD-([1-6])\*\* — \*\*RATIFIED[^|]*\|[^|]*\|([^|]*)\|",
                      _text(ADR))
    bears = {od: cell.strip().lower() for od, cell in rows}
    assert set(bears) == {"1", "2", "3", "4", "5", "6"}, (
        f"the ADR decision table does not carry all six rows: {sorted(bears)}")
    return bears, {od for od, cell in bears.items() if cell.startswith("**yes")}


def test_exactly_od_4_is_recorded_as_bearing_on_contract_shape():
    """The ADR table's third column is the load-bearing distinction between a decision
    about a guard and a decision about the contracts.

    OD-4 changed contract shape. OD-1 – OD-3 did not, and **OD-5 does not**: the owner
    deferred `permitted_reasoning_strategies` and its vocabulary together to S2, so no
    field is added and `CognitiveRoleContract`'s cardinality is unchanged at 10. If this
    column ever said ``yes`` for OD-5, a reader would go looking in Part D for a field
    that is deliberately absent; if it said ``no`` for OD-4, Part D's nesting would be
    downstream of a decision the table records as shape-neutral.
    """
    bears, bearing = _shape_bearing_decisions()
    # OD-1 – OD-3 carry a bare ``no``; OD-5 and OD-6 carry an emphasised ``**no**`` with
    # their reason, so the marker is stripped before comparing rather than each spelling
    # being matched separately.
    for od in ("1", "2", "3", "5", "6"):
        assert bears[od].lstrip("*").startswith("no"), (
            f"OD-{od} is recorded as bearing on contract shape: {bears[od]!r}")
    assert bears["4"].startswith("**yes"), (
        f"OD-4 must be recorded as bearing on contract shape: {bears['4']!r}")
    assert bearing == {"4"}, bearing
    spec = _normalised(SPECIFICATION)
    assert "OD-4 did change contract shape" in spec, (
        "the specification must agree that OD-4 changed contract shape")
    assert "does **not** bear on contract shape" in spec, (
        "the specification must agree that OD-5 does not bear on contract shape")
    assert "cardinality is unchanged at 10" in spec, (
        "the specification must state D2's cardinality is unchanged by OD-5")


#: The ADR's owner-decision section heading, and the italic cross-references to it that
#: the other documents and the ADR's own later sections carry.
_OD_SECTION_HEADING = re.compile(r"^#{1,6}\s+(Owner decisions OD-1 – OD-\d[^\n]*)$", re.M)
_OD_SECTION_REFERENCE = re.compile(r"\*(Owner decisions OD-1 – OD-\d)\*")

#: A claim that **one** decision bears on contract shape, in whatever words.
#:
#: Enumerating wordings does not work here. An earlier version listed six, and an audit
#: wrote six more that escaped every one of them: the claim is a *quantity*, and English
#: has unboundedly many ways to say "one". So the check is derived rather than listed — a
#: **singular quantifier within a bounded distance of the subject** — and whether it is an
#: offence at all is decided by the count the ADR table records, not by this pattern.
#:
#: The two halves are separate on purpose. This pattern says *a singular claim is being
#: made*; ``_shape_bearing_decisions`` says *how many decisions actually bear*. A singular
#: claim is true when the table records one bearer and false when it records several, and
#: only the second case is a defect.
_SHAPE_SUBJECT = (r"(?:contract[\s-]shape|contract's\s+shape|"
                  r"shape\s+of\s+an?\s+contract|shape\s+of\s+the\s+contract)")
#: Every way of saying "one", including the negative form — "no other decision bears on
#: contract shape" is the same claim with the quantifier moved onto the complement.
_SINGULAR_QUANTIFIER = (r"(?:the\s+only|only\s+one|just\s+one|exactly\s+one|"
                        r"a\s+single|the\s+sole|\bsole\b|no\s+other|none\s+other|"
                        r"the\s+one|one\s+alone|\balone\b)")
#: Either order, because the subject leads as often as the quantifier does — "Contract
#: shape is bore on by a single decision" puts the quantifier last.
_SOLE_SHAPE_BEARER_CLAIM = re.compile(
    rf"{_SINGULAR_QUANTIFIER}[^.]{{0,70}}?{_SHAPE_SUBJECT}"
    rf"|{_SHAPE_SUBJECT}[^.]{{0,70}}?{_SINGULAR_QUANTIFIER}", re.I)


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_every_owner_decision_section_cross_reference_resolves(path):
    """A renamed section must not leave cross-references pointing at the old name.

    This is the defect OD-5 introduced and an audit caught: renaming the ADR's table from
    *OD-1 – OD-4* to *OD-1 – OD-5* left three references to the old heading, and every
    guard stayed green because each read the table rather than the prose around it.
    Markdown does not resolve an italic cross-reference, so nothing else would notice.
    """
    headings = _OD_SECTION_HEADING.findall(_text(ADR))
    assert len(headings) == 1, f"the ADR carries {len(headings)} owner-decision headings"
    live = headings[0].split(" — ")[0].strip()
    dangling = [ref for ref in _OD_SECTION_REFERENCE.findall(_text(path)) if ref != live]
    assert not dangling, (
        f"{path.name} cross-references {dangling}, but the section is now {live!r}")


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_no_document_claims_one_decision_alone_bears_on_contract_shape(path):
    """The prose must not claim a sole shape-bearer while the table records several.

    **Gated on the table, not hard-coded.** When OD-5 was recorded as bearing on contract
    shape, a sole-bearer sentence was false and this scan caught two of them. The owner
    then deferred OD-5's field, making OD-4 the sole bearer again — at which point the
    same sentence became *true*, and a hard-coded bar would have forbidden the documents
    from stating a fact their own table asserts.

    So the offence is the **disagreement**, which is what the original defect actually
    was: prose claiming one bearer while the table records more than one. With a single
    bearer the scan stands down, and `test_exactly_od_4_is_recorded_as_bearing_on_contract
    _shape` holds the table itself.
    """
    _bears, bearing = _shape_bearing_decisions()
    if len(bearing) <= 1:
        pytest.skip(
            f"the table records {sorted(bearing)} as bearing on contract shape, so a "
            "sole-bearer sentence is true; nothing to contradict")
    offenders = _SOLE_SHAPE_BEARER_CLAIM.findall(_text(path))
    assert not offenders, f"{path.name}: {offenders}"


def test_the_cross_reference_and_sole_bearer_detectors_catch_a_planted_violation():
    """Both detectors above run over clean text and must be shown still capable of
    failing. The clean controls prove they are discriminating rather than inert."""
    live = _OD_SECTION_HEADING.findall(_text(ADR))[0].split(" — ")[0].strip()
    stale = "see *Owner decisions OD-1 – OD-4* above"
    found = [r for r in _OD_SECTION_REFERENCE.findall(stale) if r != live]
    assert found, "the cross-reference detector no longer sees a stale reference"
    assert not [r for r in _OD_SECTION_REFERENCE.findall(f"see *{live}* above")
                if r != live], "the cross-reference detector flags the live heading"

    # The claim is a quantity, not a wording. Both sets below were written by audits
    # rather than by the pattern's author: the first six defeated an enumeration of six
    # earlier spellings, which is the evidence that enumerating them cannot work.
    for claim in (
            # Spellings an enumeration caught.
            "OD-4, the only one bearing on contract shape, is resolved (a)",
            "OD-4 is the only one that bears on contract shape",
            "and with it the one open question that bore on contract shape",
            # Spellings that escaped it, and now do not.
            "OD-4 is the only ratified decision that changes a contract's shape",
            "Of the five, just one touches contract shape",
            "No other owner decision bears on contract shape",
            "Contract shape is bore on by a single decision, OD-4",
            "Exactly one owner decision affects the shape of a contract",
            "OD-4 remains the sole decision with a contract-shape consequence",
    ):
        assert _SOLE_SHAPE_BEARER_CLAIM.search(claim), (
            f"the sole-shape-bearer detector no longer matches {claim!r}")
    # Controls. A plural statement is not a singular claim, and neither is a sentence
    # that merely mentions contract shape — a detector that flagged those would fire on
    # every document that discusses the subject at all.
    for fine in (
            "Two decisions bear on contract shape, OD-4 and OD-5",
            "OD-4 and OD-5 both bear on contract shape.",
            "the question that had been open longest about contract shape",
            "OD-4 did change contract shape",
            "Part D of the specification is written for that contract shape.",
    ):
        assert not _SOLE_SHAPE_BEARER_CLAIM.search(fine), (
            f"the sole-shape-bearer detector flags {fine!r}, which is true as written")


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


def test_the_six_owner_decisions_are_each_recorded_as_ratified():
    body = _text(ADR)
    for od in ("OD-1", "OD-2", "OD-3", "OD-4", "OD-5", "OD-6"):
        assert re.search(rf"\*\*{od}\*\* — \*\*RATIFIED", body), od
    assert "All six owner decisions are resolved" in _text(SPECIFICATION)


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


#: The section-contradiction detector's own pattern, named so the self-test below can
#: exercise the same object the real check runs, rather than a copy that could drift.
SECTION_ABSENCE_CLAIM = re.compile(r"\*?([A-Z][^*\n]{3,60}?)\*?\s+section[^.\n]*?"
                                   r"(?:does not exist|no revision of this artifact "
                                   r"carried)")

#: An affirmative claim of terminology-gate coverage, in the three forms a document could
#: make one. Lifted out of the test body so the self-test can run the real patterns.
TERMINOLOGY_CLAIM_PATTERNS = (
    r"validate_terminology[^.\n]*\b(?:covers|governs|enforces|includes|applies to)\b",
    r"terminology (?:gate|validation|check)[^.\n]*\b(?:covers|governs|includes)\b",
    r"\bcovered by (?:the )?terminology\b",
)

#: OD-5: an **affirmative** claim that **S1** has authority over a reasoning strategy.
#:
#: S1 neither selects, validates nor cryptographically binds one — selection and
#: enforcement are S2's — and ``declared_strategy`` is metadata outside ``P_unsigned``
#: whose declaration establishes no conformance. The risk is that a later edit quietly
#: upgrades one of those denials into a claim, which would read as ratified authority this
#: stage does not have and would put an implementer to work on it.
#:
#: **This is a heuristic spot-check over English prose, not coverage of a class.** Two
#: audits found ordinary spellings passing earlier versions, and the second found the
#: reverse fault: two patterns named no actor, so a *true* statement about S2 doing what S2
#: is for was flagged. A regex cannot decide this question in general. The ADR and the
#: CHANGELOG state the reach as the forms below and as a named corpus, not as a guarantee.
#:
#: What this version adds is **discrimination by actor**, which is what the subject matter
#: turns on: the same sentence is a defect with S1 as its subject and correct with S2 as
#: its subject. What it keeps from the version before is **adjacency** — the actor must
#: stand within two words of its verb. Dropping adjacency was tried and reverted: with an
#: actor anywhere, a verb anywhere and the subject matter anywhere, four true sentences
#: tripped, and a guard that fires on correct prose is worse than one that misses, because
#: it fails every conformant document and gets deleted rather than fixed.
#:
#: A sentence offends when it makes one of three claims:
#:
#: * **authority over a strategy attributed to S1** — an S1 actor as the subject of an
#:   authority verb whose object is the subject matter, unnegated;
#: * **a binding claim** — ``declared_strategy`` placed inside an identity. Actor-free:
#:   identity construction is S1's by definition (G1), so there is no reading on which
#:   this is another stage's statement;
#: * **a conformance claim** — that declaring a method shows one was followed. Also
#:   actor-free: false at every stage, not merely unimplemented at this one.

#: Who is acting. ``S1`` names the stage; the builder, the validator and construction are
#: the things inside it a sentence would credit instead, and a claim about any of them is
#: a claim about S1. No S2 spelling appears here, which is what makes a correct statement
#: about S2 unreachable by the two authority patterns.
_S1_ACTOR = (r"(?:S1|stage\s+S1|the\s+S1\s+\w+|this\s+stage|the\s+(?:\w+\s+)?builder|"
             r"the\s+validator|build_proposer_advisory|(?:\w+\s+)?construction)")
#: The stage that legitimately does all of this.
_S2_ACTOR = re.compile(r"\bS2\b")
#: The subject matter, in every spelling. ``\b`` does not break at an underscore, so a
#: pattern anchored on ``\breasoning`` never reaches ``permitted_reasoning_strategies``;
#: the field names are therefore matched literally.
_STRATEGY_SUBJECT = (r"(?:reasoning\s+strateg(?:y|ies)|declared[\s_]strateg(?:y|ies)|"
                     r"permitted_reasoning_strategies|declared_strategy|"
                     r"strategy\s+conformance|(?:a|the|its|any|each|which)\s+strategy\b)")
#: Exercising authority over it: choosing, checking or refusing one.
#:
#: Deliberately **not** widened to ``permit``, ``admit``, ``allow``, ``require``,
#: ``govern`` or ``restrict``. A draft of this rebuild included them and flagged four true
#: sentences, among them "``declared_strategy`` is required and non-empty while
#: ``permitted_reasoning_strategies`` admits only ``[]``" — a sentence whose whole point is
#: that S1 has no authority here. Those verbs describe what a *field* does to a *value*,
#: which is what C5d says on every page; they do not describe a stage choosing a method.
#: ``verify`` is spelled separately. A ``-y`` stem does not inflect with the shared
#: suffix group — ``verify`` + ``s`` is not ``verifies`` and ``verify`` + ``ed`` is not
#: ``verified`` — so folding it in with the rest matched the bare infinitive only, and
#: "S1 verifies the declared strategy" escaped while "S1 verify" was caught. Any further
#: ``-y`` verb belongs in the second alternation, not the first.
_AUTHORITY_VERB = (r"(?:(?:select|validate|check|enforce|bind|reject|refuse|"
                   r"constrain|choose|match|compare|ensure|confirm|approve|authoris|"
                   r"authoriz|police|gate)(?:s|es|d|ed|ing|en)?"
                   r"|verif(?:y|ies|ied|ying))")
_AUTHORITY_PARTICIPLE = (r"(?:selected|validated|verified|checked|enforced|bound|"
                         r"rejected|refused|constrained|chosen|matched|compared|"
                         r"ensured|confirmed|approved|authorised|authorized)")

#: Active voice: an S1 actor is the subject of the verb, the subject matter its object.
#:
#: The separator is punctuation-tolerant. Requiring whitespace between the actor and its
#: verb meant an appositive split them and the claim escaped — "S1, at construction,
#: validates the declared strategy" was not caught, nor the parenthetical or em-dash forms
#: of the same sentence. Widening it to ``\W+`` with up to three intervening words costs
#: nothing: it flags no sentence in the negative corpus.
_ACTIVE_AUTHORITY = re.compile(
    rf"\b{_S1_ACTOR}\W+(?:\w+\W+){{0,3}}{_AUTHORITY_VERB}\b[^.]{{0,60}}?"
    rf"{_STRATEGY_SUBJECT}", re.I)
#: The same claim with the actor left to anaphora — "S1 does not select a strategy, but
#: **it** validates the declared strategy". Only ever applied to a clause of a sentence
#: that names an S1 actor elsewhere, so a bare "it" cannot conjure one.
_ANAPHORIC_AUTHORITY = re.compile(
    rf"\b(?:it|they)\W+(?:\w+\W+){{0,3}}{_AUTHORITY_VERB}\b[^.]{{0,60}}?"
    rf"{_STRATEGY_SUBJECT}", re.I)
#: Passive voice, with S1 named as the agent or the locus.
_PASSIVE_AUTHORITY = re.compile(
    rf"{_STRATEGY_SUBJECT}[^.]{{0,60}}?"
    rf"\b(?:is|are|was|were|must\s+be|may\s+be|can\s+be|will\s+be)\s+"
    rf"(?:\w+\s+){{0,1}}{_AUTHORITY_PARTICIPLE}\b[^.]{{0,40}}?"
    rf"\b(?:by|at|in|within|during)\s+{_S1_ACTOR}\b", re.I)
#: Placing the declaration inside an identity. Actor-free by design.
_BINDING_CLAIM = re.compile(
    r"\bdeclared_strategy\b[^.]{0,90}?\b(?:participates\s+in|is\s+inside|is\s+part\s+of|"
    r"is\s+covered\s+by|is\s+bound\s+into|contributes\s+to|is\s+included\s+in|"
    r"feeds\s+into)\b[^.]{0,50}?(?:P_unsigned|advisory_digest|digest|identity)", re.I)
#: Claiming a declaration evidences the method it names. Also actor-free.
_CONFORMANCE_CLAIM = re.compile(
    r"\b(?:declar\w+|the\s+record|the\s+process\s+record)\b[^.]{0,70}?"
    r"\b(?:establishes|demonstrates|proves|shows|evidences|attests)\b[^.]{0,70}?"
    r"\b(?:conformance|conformant|was\s+(?:used|followed)|it\s+did)\b", re.I)
#: A negation standing before the claim excuses it. The documents are *required* to carry
#: these denials, so a scan that flagged them would be unusable.
_NEGATION = re.compile(r"\b(?:not|never|neither|nor|without|cannot|nothing|none|no)\b",
                       re.I)
#: The reserved field's own emptiness rule is not a claim of authority over a strategy: it
#: is what C5d says, and the documents state it repeatedly.
_RESERVED_FIELD_RULE = re.compile(
    r"permitted_reasoning_strategies\b[^.]{0,60}?"
    r"\b(?:reject|admit|refuse|accept|is|are|stays?|remains?)\w*\b[^.]{0,80}?"
    r"(?:empty|non-empty|value|reserved|closed|C5d|list)", re.I)

#: Sentence-ish units, found in two steps because neither step alone is right.
#:
#: The documents wrap mid-sentence, so whitespace must be collapsed before splitting: a
#: line-oriented scan would separate an actor from its predicate and miss a real violation
#: for a reason unrelated to what the sentence says. But collapsing the *whole document*
#: merges list items, which frequently do not end in a full stop, into one run — and a run
#: spanning two bullets pairs an actor from one with a predicate from another and reports a
#: violation neither bullet makes.
#:
#: So blocks are cut first — at blank lines, at list markers, at headings and at table
#: rows — and only then is each block collapsed and split. A wrapped sentence stays inside
#: its block; two bullets never join.
_BLOCK_SPLIT = re.compile(r"\n\s*\n|\n(?=\s*(?:[-*+]\s|\d+\.\s|#{1,6}\s|\|))")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _strategy_sentences(body):
    found = []
    for block in _BLOCK_SPLIT.split(body):
        collapsed = " ".join(block.split())
        found.extend(part for part in _SENTENCE_SPLIT.split(collapsed) if part.strip())
    return found


def _stale_status_offenders(body, label="text"):
    """Every stale branch-status assertion in ``body``, located by line."""
    offenders = []
    for pattern in STALE_STATUS_PATTERNS:
        for match in re.finditer(pattern, body, re.I):
            line = body.count("\n", 0, match.start()) + 1
            offenders.append(f"{label}:{line}: {match.group(0)!r}")
    return offenders


def _sha_claims(body):
    """Every temporary SHA-based truth claim in ``body``."""
    return [match.group(0) for match in SHA_CLAIM.finditer(body)]


def _section_contradictions(body):
    """Every section this text both carries as a heading and declares absent."""
    claims = SECTION_ABSENCE_CLAIM.findall(body)
    headings = {h.strip().strip("*`") for h in re.findall(r"^#{1,6}\s+(.*)$", body, re.M)}
    return [claim for claim in claims if claim.strip().strip("*`") in headings]


def _terminology_coverage_claims(body):
    """Every affirmative terminology-gate coverage claim in ``body``."""
    found = []
    for pattern in TERMINOLOGY_CLAIM_PATTERNS:
        found.extend(re.findall(pattern, body, re.I))
    return found


#: Clause boundaries, used to scope a negation to the claim it actually denies.
#:
#: A negation searched over the whole sentence excuses any claim that follows *any*
#: denial, however unrelated. "Although no vocabulary is ratified, S1 validates the
#: declared strategy" escaped on the strength of a "no" in a subordinate clause about
#: something else, and "S1 does not select a strategy, but it validates the declared
#: strategy against the permitted set" escaped on its own first half. Both assert exactly
#: what the guard exists to refuse.
#:
#: Splitting on punctuation and on the contrastive conjunctions keeps a denial inside the
#: clause that makes it. It cannot be perfect on English prose and is not claimed to be;
#: it is the difference between a denial anywhere and a denial *here*.
_CLAUSE_SPLIT = re.compile(
    r"[,;:()\[\]—–]|\b(?:but|although|though|whereas|while|however|yet|except)\b", re.I)


def _clauses(sentence):
    """``(offset, text)`` for each clause of ``sentence``, in order."""
    found, last = [], 0
    for boundary in _CLAUSE_SPLIT.finditer(sentence):
        found.append((last, sentence[last:boundary.start()]))
        last = boundary.end()
    found.append((last, sentence[last:]))
    return [(offset, text) for offset, text in found if text.strip()]


def _negated_before(sentence, end):
    """Whether a negation stands before ``end`` **within its own clause**."""
    for start, clause in _clauses(sentence):
        if start <= end <= start + len(clause):
            return bool(_NEGATION.search(clause[:end - start]))
    return bool(_NEGATION.search(sentence[:end]))


def _sentence_offends(sentence):
    """Why this sentence claims S1 authority over a reasoning strategy, or ``None``."""
    if _RESERVED_FIELD_RULE.search(sentence):
        return None
    for claim, label in ((_BINDING_CLAIM, "binding"),
                         (_CONFORMANCE_CLAIM, "conformance")):
        found = claim.search(sentence)
        if found and not _negated_before(sentence, found.end()):
            return label
    # An anaphoric "it" may stand for an S1 actor only where the sentence names one.
    patterns = [_ACTIVE_AUTHORITY, _PASSIVE_AUTHORITY]
    if re.search(_S1_ACTOR, sentence, re.I):
        patterns.append(_ANAPHORIC_AUTHORITY)
    # Searched over the WHOLE sentence, not clause by clause. An appositive splits an
    # actor from its verb — "S1, at construction, validates …" — so a clause-by-clause
    # search would put them in different clauses and find neither; the punctuation-
    # tolerant separator exists precisely to cross that comma. Only the *negation* is
    # clause-scoped. Every match is examined rather than the first alone, so a denial in
    # one clause cannot hide a claim made in the next.
    for pattern in patterns:
        for found in pattern.finditer(sentence):
            if not _negated_before(sentence, found.end()):
                return "authority"
    return None


def _strategy_authority_claims(body, label="text"):
    """Every affirmative claim of S1 strategy authority in ``body``.

    Reported by sentence rather than by line: the classifier judges whole sentences, and a
    line number would point at whichever wrapped fragment happened to hold the match.
    """
    offenders = []
    for sentence in _strategy_sentences(body):
        kind = _sentence_offends(sentence)
        if kind:
            offenders.append(f"{label} [{kind}]: {sentence[:140]!r}")
    return offenders


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_no_stale_unmerged_branch_assertion_survives(path):
    offenders = _stale_status_offenders(_text(path), path.name)
    assert not offenders, offenders


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_no_temporary_sha_based_truth_survives(path):
    """The CHANGELOG may record history; a status claim may not rest on a SHA."""
    if path == CHANGELOG:
        pytest.skip("a changelog records what happened, including where")
    offenders = _sha_claims(_text(path))
    assert not offenders, f"{path.name}: {offenders}"


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_no_contradictory_section_does_not_exist_statement(path):
    """A document may not both carry a section and say that section is absent.

    This is the exact defect an automatic merge produced: the *What O-1 – O-4 changed*
    section was retained from one side while a sentence from the other side said the
    same section did not exist here.
    """
    contradictions = _section_contradictions(_text(path))
    assert not contradictions, f"{path.name}: {contradictions}"


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_no_document_claims_s1_has_authority_over_a_reasoning_strategy(path):
    """OD-5(iv). Strategy selection and enforcement are S2's, in whole.

    A document that said otherwise would not merely be inaccurate: `permitted_reasoning
    _strategies` is C5d and rejects every value, so there is nothing for S1 to validate a
    declaration against, and `declared_strategy` is outside ``P_unsigned``, so there is
    nothing for S1 to bind it into. A claim of authority here describes machinery that
    does not exist and cannot be written without a further ratification.
    """
    offenders = _strategy_authority_claims(_text(path), path.name)
    assert not offenders, offenders


# --------------------------------------------------------------------------- #
# The detectors above are self-tested against synthetic sources
# --------------------------------------------------------------------------- #
#
# Every check in this section runs over documents that are *clean*, and a clean document
# is exactly what a detector that has stopped matching also reports. The two outcomes are
# indistinguishable from a green run, so each detector is additionally run against text
# built to violate it. A pattern edited into inertness — a typo in an alternation, a
# character class that no longer matches, a regex whose group numbering shifted — fails
# here instead of quietly certifying every document in ``DOCUMENTS``.
#
# The synthetic sources are written inline rather than kept as fixture files: a fixture
# file under ``docs/`` would itself be scanned by the repository's own gates, and a
# deliberately violating document is the last thing those should be asked to accept.

#: One violating text per ``STALE_STATUS_PATTERNS`` entry, in the same order, so a dead
#: pattern is reported by name rather than hidden behind another pattern's match.
_STALE_STATUS_POSITIVES = (
    "The guard is **not merged** yet.",
    "The guard is not merged yet.",
    "It lives on an unmerged branch today.",
    "It lives at an unmerged head today.",
    "The rule is implemented on an unmerged branch.",
    "The rule is not merged, so the claim is provisional.",
    "This row is pending merged enforcement.",
    "The validator is implemented, not merged.",
    "The work is done and only the merge is outstanding.",
)


def test_every_stale_status_pattern_matches_a_text_built_to_violate_it():
    """Each ``STALE_STATUS_PATTERNS`` entry must still match something.

    Paired one-to-one with the pattern list and asserted pairwise, so a pattern that
    stopped matching is named. The clean control at the end proves the detector is
    discriminating rather than matching everything it is shown.
    """
    assert len(_STALE_STATUS_POSITIVES) == len(STALE_STATUS_PATTERNS), (
        f"{len(STALE_STATUS_PATTERNS)} stale-status patterns and "
        f"{len(_STALE_STATUS_POSITIVES)} synthetic violations; a pattern added without a "
        "violation to prove it is a pattern nothing tests")
    for pattern, text in zip(STALE_STATUS_PATTERNS, _STALE_STATUS_POSITIVES):
        assert re.search(pattern, text, re.I), (
            f"the stale-status pattern {pattern!r} no longer matches {text!r}; it would "
            "report every document in DOCUMENTS clean")
        assert _stale_status_offenders(text, "synthetic"), (
            f"the stale-status scan missed {text!r} even though {pattern!r} matches it")
    assert not _stale_status_offenders(
        "The guard is enforced by a named test, and production implementation is "
        "separately gated.", "synthetic"), (
        "the stale-status scan flags durable text; it is matching too much, not too "
        "little")


#: Claims the scan must catch, grouped by why each offends. Every one is a sentence a
#: future edit could plausibly write. No individual reasoning strategy is named in any of
#: them: the classifier turns on the actor and the verb, never on the method, and naming
#: one would seed a candidate member of an unratified vocabulary.
#:
#: Twelve of these are spellings two successive audits found passing earlier versions of
#: this guard. They are kept in the one corpus rather than in a separate regression list so
#: that a later rewrite cannot drop them while still looking thorough.
_STRATEGY_AUTHORITY_POSITIVES = (
    # Authority attributed to S1, active voice.
    "S1 validates the declared reasoning strategy against the role's permitted set.",
    "S1 checks `declared_strategy` against the role's permitted set.",
    "S1 validates `permitted_reasoning_strategies` against the declared strategy.",
    "S1 enforces the role's permitted_reasoning_strategies at construction.",
    "S1 rejects a declared strategy the role may not select.",
    "S1 ensures the declared reasoning strategy is one the role permits.",
    "S1 refuses a reasoning strategy outside the permitted set.",
    "S1 confirms the reasoning strategy named by the record.",
    "S1 constrains which strategy a role may use.",
    "Stage S1 validates the declared reasoning strategy.",
    # Authority attributed to something inside S1.
    "The builder selects a reasoning strategy before constructing the advisory.",
    "The advisory builder selects a reasoning strategy.",
    "This stage validates the declared reasoning strategy.",
    # Authority attributed to S1, passive voice.
    "The reasoning strategy is enforced at S1, before the advisory is constructed.",
    "The declared strategy is validated against the permitted set at S1.",
    "The reasoning strategy must be approved by S1 before use.",
    "A reasoning strategy is authorised at S1.",
    # Binding claims. Actor-free: identity construction is S1's by definition.
    "`declared_strategy` is covered by `advisory_digest`, so it cannot be altered.",
    "declared_strategy contributes to the advisory digest.",
    "declared_strategy participates in the advisory identity.",
    # Conformance claims. Actor-free: false at every stage, not merely unimplemented here.
    "Declaring a strategy establishes conformance with the method it names.",
    "The process record shows the reasoning strategy was used.",
    # A ``-y`` stem, which the shared suffix group cannot inflect. Both tenses, because
    # folding ``verify`` in with the rest matched the bare infinitive alone.
    "S1 verifies the declared reasoning strategy.",
    "S1 verified the declared reasoning strategy against the permitted set.",
    # An appositive between the actor and its verb, in the three forms English writes
    # one. Whitespace-only separators put the actor and the verb on opposite sides of a
    # comma and found neither.
    "S1, at construction, validates the declared strategy.",
    "S1 (the advisory builder) validates the declared strategy.",
    "S1 — the validator — validates the declared strategy.",
    # Construction named as the locus, which the actor docstring claimed and the pattern
    # did not carry.
    "The declared strategy is validated during advisory construction.",
    # A denial of something else, standing earlier in the sentence, must not excuse the
    # claim that follows it.
    "Although no vocabulary is ratified, S1 validates the declared strategy.",
    "S1 does not select a strategy, but it validates the declared strategy against the "
    "permitted set.",
)

#: Text the scan must leave alone. Four kinds, and the second is the one an audit had to
#: point out: a scan with no notion of *who* is acting flagged true statements about S2.
#:
#: * the documents' own denials, which are adjacent in wording and opposite in meaning,
#:   and which these documents are *required* to carry;
#: * correct statements about S2, the stage that legitimately selects, validates and
#:   enforces — the same sentence is a defect with S1 as its subject and correct with S2 as
#:   its subject, which is the whole reason the classifier discriminates by actor;
#: * the reserved field's own emptiness rule, which is what C5d says on every page;
#: * true sentences from the governed documents that a draft of this rebuild flagged when
#:   adjacency was dropped. They are the evidence for keeping it.
_STRATEGY_AUTHORITY_NEGATIVES = (
    # Denials.
    "S1 neither selects, validates nor cryptographically binds a reasoning strategy.",
    "Strategy selection and enforcement are S2's in whole.",
    "Declaration does not establish conformance.",
    "`declared_strategy` is not covered by `advisory_digest` and is outside "
    "`P_unsigned`.",
    "A reasoning strategy is a method label, not a process state.",
    "S1 does not select a reasoning strategy.",
    "No rule at this stage validates a declared strategy.",
    # Correct statements about S2.
    "S2 checks declared_strategy against permitted_reasoning_strategies.",
    "The permitted_reasoning_strategies list is compared against declared_strategy "
    "by S2.",
    "S2 validates the declared reasoning strategy against the role's permitted set.",
    "S2 selects a reasoning strategy and enforces the role's permitted set.",
    "Validation of a declared strategy is added by S2.",
    # The reserved field's own rule.
    "`permitted_reasoning_strategies` rejects every non-empty value at this stage.",
    "permitted_reasoning_strategies admits only the empty list.",
    "The C5d validator on permitted_reasoning_strategies refuses every value.",
    # True sentences an over-broad draft flagged.
    "Admitting any of them into `permitted_reasoning_strategies` would put a mechanism "
    "this stage enforces, or an outcome this stage constrains, into a list this stage "
    "deliberately refuses to validate.",
    "Selection of a strategy, validation of a declared one against a role's permitted "
    "set, and any binding of either into an identity are S2's in whole; S1 does none of "
    "them.",
    "D2 now states that `declared_strategy` is required and non-empty while "
    "`permitted_reasoning_strategies` admits only `[]`, so every conformant S1 pair "
    "declares a method the role is not permitted to select.",
)


@pytest.mark.parametrize("text", _STRATEGY_AUTHORITY_POSITIVES, ids=lambda t: t[:44])
def test_the_strategy_authority_scan_catches_each_claim(text):
    """Every claim in the corpus must be caught, reported by name.

    Parametrized rather than looped so a regression names the sentence that escaped
    instead of reporting one failure among twenty-two.
    """
    assert _strategy_authority_claims(text, "positive"), (
        f"the strategy-authority scan misses {text!r}")


@pytest.mark.parametrize("text", _STRATEGY_AUTHORITY_NEGATIVES, ids=lambda t: t[:44])
def test_the_strategy_authority_scan_leaves_correct_statements_alone(text):
    """A false positive here is worse than a miss: it fails every conformant document,
    and a guard that fires on correct prose gets deleted rather than fixed.

    The S2 cases matter most. An earlier version carried two patterns naming no actor, so
    a true statement of what S2 does — the thing these documents must be free to say — was
    reported as a violation of the rule it correctly states.
    """
    assert not _strategy_authority_claims(text, "negative"), (
        f"the strategy-authority scan flags {text!r}, which is correct as written; it is "
        "matching too much, not too little")


def test_the_strategy_classifier_turns_on_the_actor():
    """The distinction the rebuild exists for, asserted on one minimal pair.

    Same verb, same subject matter, different actor. If these two ever agree the
    classifier has stopped discriminating, and one of the corpora above is passing for the
    wrong reason.
    """
    s1 = "S1 validates the declared reasoning strategy against the permitted set."
    s2 = "S2 validates the declared reasoning strategy against the permitted set."
    assert _sentence_offends(s1) == "authority", "the S1 form is no longer caught"
    assert _sentence_offends(s2) is None, "the S2 form is flagged, and it is correct"
    assert _S2_ACTOR.search(s2) and not re.search(_S1_ACTOR, s2)


def test_every_authority_verb_inflects():
    """A stem that cannot take the shared suffix group is a verb matched in one tense.

    ``verify`` was folded in with the rest and so matched only the bare infinitive: the
    guard caught "S1 verify" — which nobody writes — and missed "S1 verifies", which is
    how the claim is actually written. Each stem is exercised in the tenses a document
    would use, so the next ``-y`` verb added to the wrong alternation fails here.
    """
    for verb in ("selects", "validates", "verifies", "verified", "checks", "enforces",
                 "binds", "rejects", "refuses", "constrains", "ensures", "confirms",
                 "approved", "authorised"):
        sentence = f"S1 {verb} the declared reasoning strategy."
        assert _sentence_offends(sentence) == "authority", (
            f"the authority verb {verb!r} does not inflect: {sentence!r} escapes")


def test_every_actor_the_docstring_names_is_matched():
    """The actor comment claims construction is an S1-internal actor; the pattern must
    carry it. It did not, so "validated during advisory construction" escaped while the
    comment said it would not — a guard documented as stronger than it was."""
    for actor, sentence in (
            ("S1", "S1 validates the declared strategy."),
            ("stage S1", "Stage S1 validates the declared strategy."),
            ("this stage", "This stage validates the declared strategy."),
            ("the builder", "The builder validates the declared strategy."),
            ("the advisory builder", "The advisory builder validates the declared "
                                     "strategy."),
            ("the validator", "The validator validates the declared strategy."),
            ("construction", "The declared strategy is validated during advisory "
                             "construction."),
    ):
        assert _sentence_offends(sentence) == "authority", (
            f"the actor {actor!r} is named in the comment but escapes: {sentence!r}")


def test_a_negation_excuses_only_its_own_clause():
    """A denial excuses the claim it denies, not every claim after it.

    Both halves are asserted. A denial standing in the clause that makes the claim must
    still excuse it — the documents are required to carry those — while a denial about
    something else, or about a different verb, must not.
    """
    assert _sentence_offends(
        "S1 neither selects, validates nor cryptographically binds a reasoning "
        "strategy.") is None
    assert _sentence_offends("S1 does not select a reasoning strategy.") is None
    assert _sentence_offends(
        "Although no vocabulary is ratified, S1 validates the declared strategy."
    ) == "authority"
    assert _sentence_offends(
        "S1 does not select a strategy, but it validates the declared strategy against "
        "the permitted set.") == "authority"


def test_the_anaphoric_actor_needs_an_s1_actor_in_the_same_sentence():
    """``it`` may stand for an S1 actor only where the sentence names one. Without this
    the pronoun would conjure an actor out of any sentence, including one whose subject
    is S2 — the exact failure the actor discrimination exists to prevent."""
    assert _sentence_offends(
        "S1 is bounded, and it validates the declared strategy.") == "authority"
    assert _sentence_offends(
        "S2 is bounded, and it validates the declared strategy.") is None


def test_the_documented_blind_spots_are_real_and_still_blind():
    """The module docstring names two shapes this scan does not reach. Both are asserted
    so the disclosure stays accurate: if a later change closed one, the docstring would
    be understating the guard, which is a defect in the other direction."""
    across_rows = ("| S1 | the stage |\n"
                   "| validates | the declared reasoning strategy |\n")
    assert not _strategy_authority_claims(across_rows, "rows"), (
        "the scan now reaches a claim split across two table rows; the docstring says it "
        "does not and must be corrected")
    for stem_and_item in (
            "S1 does the following:\n\n1. validates the declared strategy\n",
            "S1 does the following:\n\n* validates the declared strategy\n"):
        assert not _strategy_authority_claims(stem_and_item, "item"), (
            "the scan now reaches a claim split between a lead-in stem and a list item; "
            "the docstring says it does not and must be corrected")
    # The other half of the disclosure: a single row IS reached, so the docstring must
    # not overstate the blind spot either.
    one_row = "| S1 | validates the declared reasoning strategy |\n"
    assert _strategy_authority_claims(one_row, "row"), (
        "a claim inside one table row is no longer reached; the docstring says it is")


def test_the_strategy_classifier_reads_whole_sentences_not_lines():
    """The documents wrap mid-sentence. A line-oriented scan would separate an actor from
    its verb and miss a violation for a reason unrelated to what it says."""
    wrapped = ("S1 validates the declared reasoning\nstrategy against the role's\n"
               "permitted set.")
    assert _strategy_authority_claims(wrapped, "wrapped"), (
        "a violation split across three lines escapes the scan")


def test_the_strategy_classifier_does_not_join_two_list_items():
    """The converse hazard. Collapsing a whole document merges bullets that do not end in
    a full stop, pairing one item's actor with another's verb and reporting a violation
    neither item makes."""
    bullets = ("* S1 does none of this, and the field admits no value\n"
               "* A reasoning strategy is a method label, not a process state\n")
    assert not _strategy_authority_claims(bullets, "bullets"), (
        "two innocent list items were joined into one sentence and flagged")


def test_the_sha_claim_detector_matches_a_temporary_truth_and_not_durable_text():
    """``SHA_CLAIM`` must still find a SHA-anchored status claim.

    Both spellings the documents could carry — backticked and bare — and both a short
    and a full-length hexadecimal string, because the pattern's length bound is the part
    most easily broken by an edit.
    """
    for text in ("enforced at `eac5547`, per the guard",
                 "enforced at eac5547d, per the guard",
                 "enforced at `" + "a" * 40 + "`, per the guard"):
        assert _sha_claims(text), (
            f"SHA_CLAIM no longer matches {text!r}; a status claim resting on a commit "
            "would pass unreported")
    assert not _sha_claims("enforced at the point the validator is declared"), (
        "SHA_CLAIM matches prose carrying no commit identifier")


def test_the_section_contradiction_detector_matches_a_document_that_contradicts_itself():
    """The exact defect the real check exists for, reconstructed in miniature.

    A document that carries a heading and also states that the section it names does not
    exist. Both closing phrases the pattern admits are exercised, and a control document
    carrying the heading with no absence claim must come back clean — otherwise the
    detector would be reporting the heading rather than the contradiction.
    """
    sentences = (
        "See the *What O-1 – O-4 changed* section, which does not exist here.",
        "See the *What O-1 – O-4 changed* section, which no revision of this artifact "
        "carried.",
    )
    for sentence in sentences:
        document = f"## What O-1 – O-4 changed\n\n{sentence}\n"
        assert _section_contradictions(document), (
            f"the section-contradiction detector missed {sentence!r}; it would report a "
            "self-contradicting document clean")
    assert not _section_contradictions(
        "## What O-1 – O-4 changed\n\nThe four refinements are recorded above.\n"), (
        "the section-contradiction detector fires on a document that merely carries the "
        "heading")
    assert not _section_contradictions(f"## Ratified refinements\n\n{sentences[0]}\n"), (
        "the detector fires on an absence claim about a section the document really does "
        "not carry, which is a true statement rather than a contradiction")


def test_every_terminology_claim_pattern_matches_a_text_built_to_violate_it():
    """The G-8 half that asserts an absence, and so is the half most easily neutered.

    ``test_no_terminology_coverage_is_claimed_for_these_documents`` passes when no
    document makes an affirmative coverage claim **and** when the patterns have stopped
    recognising one. Each pattern is therefore paired with a claim it must catch, and the
    honest disclaiming form these documents actually use must come back clean.
    """
    positives = (
        # No period between the gate's name and the verb: the first pattern's gap is
        # sentence-bounded, and a synthetic claim written `validate_terminology.py covers`
        # would fail to match for a reason that says nothing about the pattern's health.
        "validate_terminology covers these documents.",
        "The terminology gate covers this package's documents.",
        "These documents are covered by the terminology gate.",
    )
    assert len(positives) == len(TERMINOLOGY_CLAIM_PATTERNS), (
        f"{len(TERMINOLOGY_CLAIM_PATTERNS)} terminology-claim patterns and "
        f"{len(positives)} synthetic claims; a pattern with no claim to prove it is a "
        "pattern nothing tests")
    for pattern, text in zip(TERMINOLOGY_CLAIM_PATTERNS, positives):
        assert re.search(pattern, text, re.I), (
            f"the terminology-claim pattern {pattern!r} no longer matches {text!r}")
        assert _terminology_coverage_claims(text), (
            f"the terminology-claim scan missed {text!r}")
    assert not _terminology_coverage_claims(
        "validate_terminology.py runs over a different curated list, and this package's "
        "documents are deliberately not in it. No claim of terminology coverage is made "
        "for these documents."), (
        "the terminology-claim scan flags the disclaiming form the documents use; it "
        "would make the honest statement unwritable")


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
    for path in DOCUMENTS:
        found = _terminology_coverage_claims(_text(path))
        assert not found, (
            f"{path.name} claims terminology-gate coverage it does not have: {found}")


# --------------------------------------------------------------------------- #
# The "named in no test file" row is derived from the tree, not written by hand
# --------------------------------------------------------------------------- #

#: Where the guard tests live, so the scan reads the real tree rather than a list.
TESTS_DIR = PKG_ROOT / "tests"

#: The row in ``S1_ENFORCEMENT.md`` this derivation keeps honest.
UNEXERCISED_ROW = re.compile(
    r"^\| \*\*((?:R-\d+[ab]?|L-\d+|S-\d+)(?:, (?:R-\d+[ab]?|L-\d+|S-\d+))*"
    r"(?:,? and (?:R-\d+[ab]?|L-\d+|S-\d+))?)\*\* \| \*\*named, not covered\*\*", re.M)

#: Rule ids as the specification states them: most as rows of the rule table, and S-1 and
#: S-2 as bold bullets under D6's *Locally decidable selection invariants*. Both forms are
#: matched, because a rule stated as prose is as ratified as one stated in a table and the
#: earlier pattern silently missed the two that are.
_RULE_ID = re.compile(
    r"^\| (R-\d+[ab]?|L-\d+|S-\d+) \||^\* \*\*(S-\d+|R-\d+[ab]?|L-\d+) — ", re.M)

#: The ratified rule ids, pinned by equality in the same form as
#: ``RATIFIED_DIGEST_FIELDS``: a rule added to or removed from the specification must fail
#: here rather than silently change what every derivation below is quantified over. A
#: derivation over a set that can shrink unnoticed proves nothing about what it omits.
RATIFIED_RULE_IDS = frozenset({
    "R-1a", "R-1b", "R-2", "R-3", "R-4", "R-5", "R-6", "R-7", "R-8", "R-9", "R-10",
    "L-1", "S-1", "S-2",
})

#: Modules carrying an explicit registry of the rules they work with, and the attribute
#: holding it. "A test works with this rule" is decided by these, never by a rule id
#: appearing in prose: a rule named only to say that nothing covers it is not coverage,
#: and treating a mention as an exercise is how R-4 came to be classified as covered by
#: the module that explicitly disclaims covering it.
RULE_REGISTRIES = (
    ("test_unenforced_local_rules", "UNENFORCED"),
    ("test_unenforced_local_rules", "ENFORCED"),
    ("test_process_ordering_obligation", "OBLIGATION_RULES"),
)


def _specified_rule_ids():
    """Every rule id the specification states, read from the document and pinned."""
    found = {table or bullet for table, bullet in _RULE_ID.findall(_text(SPECIFICATION))}
    assert found == set(RATIFIED_RULE_IDS), (
        f"the specification's rule set changed: spec-only {sorted(found - RATIFIED_RULE_IDS)}, "
        f"pinned-only {sorted(set(RATIFIED_RULE_IDS) - found)}. Update "
        "RATIFIED_RULE_IDS deliberately, so the change is reviewed rather than absorbed")
    return found


def _rule_mentions_under_tests():
    """``{rule: {module names that mention it}}`` across ``tests/``.

    Word-anchored on the right so ``R-1`` does not match ``R-10``. A mention is **not**
    coverage — see ``_rules_exercised_by_some_test`` — but it is what
    ``test_every_ratified_rule_is_named_somewhere_under_tests`` quantifies over.

    **This module is excluded from the scan.** It describes what the other modules do, and
    a rule named here only to say that nothing covers it is not coverage — left in, the
    derivation would read its own prose. The exclusion is also the safe direction: a
    mention here can only leave a rule *in* the unnamed set, never remove one from it.
    """
    rules = RATIFIED_RULE_IDS
    mentions = {rule: set() for rule in rules}
    this_module = pathlib.Path(__file__).resolve()
    for path in sorted(TESTS_DIR.glob("*.py")):
        if path.resolve() == this_module:
            continue
        body = path.read_text(encoding="utf-8")
        for rule in rules:
            if re.search(rf"{re.escape(rule)}(?![0-9a-z])", body):
                mentions[rule].add(path.name)
    return mentions


def _rules_exercised_by_some_test():
    """Rules some test actually works with, read from the registries that declare it.

    A rule counts as exercised when it appears in a registry of constructed cases —
    ``UNENFORCED``'s violating constructions or ``ENFORCED``'s rejecting ones — or in a
    module's declared list of named skip obligations. Textual mentions are deliberately
    **not** consulted: prose is where a module explains what it does *not* cover, so
    reading it as coverage inverts the meaning of the sentence it is reading.

    Registry labels may carry a clause or a derivation note — ``R-1b(vii)``,
    ``S-2 (via R-1b)`` — so a label is matched to a rule id by prefix rather than by
    equality. Exercising one clause of a rule counts as working with that rule; the row
    this feeds distinguishes *covered* from *named*, not *fully covered* from *partly*.
    """
    exercised = set()
    for module_name, attribute in RULE_REGISTRIES:
        registry = getattr(importlib.import_module(module_name), attribute)
        labels = [entry[0] if isinstance(entry, tuple) else entry for entry in registry]
        for label in labels:
            for rule in RATIFIED_RULE_IDS:
                if re.match(rf"{re.escape(rule)}(?![0-9a-z])", label):
                    exercised.add(rule)
    return exercised


def test_every_ratified_rule_is_named_somewhere_under_tests():
    """No ratified rule may sit in the specification unmentioned by every test module.

    A rule no test names is indistinguishable from a rule nobody has considered. This does
    **not** assert coverage — most of these rules cannot be covered at this stage — only
    that each has been written down somewhere a reader of the tests will meet it.
    """
    specified = _specified_rule_ids()
    assert specified, "no rule ids were read from the specification"
    unnamed = {rule for rule, where in _rule_mentions_under_tests().items() if not where}
    assert unnamed == set(), (
        f"these ratified rules are named in no test module: {sorted(unnamed)}. Record "
        "them where a reader will meet them, or explain the omission in "
        "docs/S1_ENFORCEMENT.md")


def test_the_named_but_unexercised_row_is_derived_from_the_test_tree():
    """The row listing rules that are named but not exercised must be recomputed.

    A hand-written list of what is *absent* rots the moment anything is added, and rots
    silently, because nothing fails when a claim about absence stops being true. An
    earlier version of this row was wrong in both directions at once: it named R-4, which
    ``test_process_ordering_obligation.py`` mentions five times, and omitted R-7, which
    nothing mentioned at all. Deriving membership from *mentions* then made the opposite
    error — it classified R-4 as covered by the module that disclaims covering it — so
    membership is now derived from the registries of constructed cases instead.
    """
    match = UNEXERCISED_ROW.search(_text(ENFORCEMENT))
    assert match, (
        "the 'named, not covered' row is missing or has been reworded; this derivation "
        "cannot check a row it cannot find")
    claimed = set(re.findall(r"R-\d+[ab]?|L-\d+|S-\d+", match.group(1)))

    derived = _specified_rule_ids() - _rules_exercised_by_some_test()
    assert claimed == derived, (
        f"the row claims {sorted(claimed)} are named but unexercised; the registries say "
        f"{sorted(derived)}. Row-only: {sorted(claimed - derived)} (each IS exercised). "
        f"Tree-only: {sorted(derived - claimed)} (each is only named and belongs in the "
        "row)")


def test_exercise_is_decided_by_a_registry_and_never_by_a_mention():
    """Control for the derivation, on the case that produced the earlier error.

    R-4 is mentioned in ``test_process_ordering_obligation.py``, which states in terms
    that it covers none of R-4. Under a mention-based rule that made R-4 "exercised". It
    counts as exercised now for a different and behavioural reason — a constructed case
    in ``ENFORCED`` (R-4 is now locally decidable and enforced, per
    ``ProposerProcessRecord``'s own validator) — and this test asserts that reason
    rather than the outcome, so deleting the case would fail here rather than pass on
    the mention.
    """
    mentions = _rule_mentions_under_tests()
    exercised = _rules_exercised_by_some_test()

    assert "test_process_ordering_obligation.py" in mentions["R-4"], (
        "precondition: the obligation module mentions R-4")
    registry = importlib.import_module("test_unenforced_local_rules").ENFORCED
    r4_cases = [entry for entry in registry if entry[0] == "R-4"]
    assert r4_cases, (
        "R-4 is exercised only by a constructed case; if that case is gone, R-4 belongs "
        "in the 'named, not covered' row and this assertion is the thing that says so")
    assert "R-4" in exercised

    obligation = importlib.import_module("test_process_ordering_obligation")
    assert "R-4" not in obligation.OBLIGATION_RULES, (
        "the obligation module must not claim R-4; it cites R-4 as a premise and covers "
        "none of it")
    assert "R-3" in obligation.OBLIGATION_RULES and "R-3" in exercised

    # A rule mentioned everywhere but in no registry is not exercised. R-2 is that case.
    assert mentions["R-2"], "precondition: R-2 is mentioned somewhere"
    assert "R-2" not in exercised, (
        "a textual mention must never make a rule exercised; that inversion is what this "
        "derivation exists to prevent")


#: The row whose headline counts the constructed violations, so the number cannot drift
#: away from the registry it describes. Matches either wordform: ``representative
#: shapes`` (while ``s1_specification_mirror.py`` built temporary duplicates) or
#: ``declared contracts`` (now that it returns the real ones), and either
#: singular/plural noun, since the count that matters is the captured numeral, not the
#: fossilized prose around it.
UNENFORCED_COUNT_ROW = re.compile(
    r"^\| \*\*([A-Za-z-]+) locally decidable violations? the "
    r"(?:representative shapes|declared contracts) accepts?\*\* \|", re.M)

#: Spelled numerals the row may use. Bounded rather than open: a row needing a number
#: outside this range is a row that should be reworded rather than extended again. The
#: upper end was raised when C4's per-field cases landed — C4 states its requirement of
#: each ``datetime`` field, so it contributes one case per field rather than one per
#: rule — and the range is deliberately left with headroom above the current count so a
#: single added case is a one-line diff rather than a table edit.
_NUMERALS = {
    "One": 1, "Nineteen": 19, "Twenty": 20, "Twenty-one": 21, "Twenty-two": 22,
    "Twenty-three": 23, "Twenty-four": 24, "Twenty-five": 25, "Twenty-six": 26,
    "Twenty-seven": 27, "Twenty-eight": 28, "Twenty-nine": 29, "Thirty": 30,
    "Thirty-one": 31, "Thirty-two": 32, "Thirty-three": 33, "Thirty-four": 34,
    "Thirty-five": 35, "Thirty-six": 36, "Thirty-seven": 37,
    "Thirty-eight": 38, "Thirty-nine": 39, "Forty": 40, "Forty-one": 41,
    "Forty-two": 42, "Forty-three": 43, "Forty-four": 44, "Forty-five": 45,
    "Forty-six": 46, "Forty-seven": 47, "Forty-eight": 48, "Forty-nine": 49,
    "Fifty": 50, "Fifty-one": 51, "Fifty-two": 52, "Fifty-three": 53,
    "Fifty-four": 54, "Fifty-five": 55,
}


def test_the_unenforced_row_counts_what_the_registry_actually_carries():
    """The headline count is checked against the registry, not trusted.

    A number written into prose is the part of a row most likely to go stale, because
    adding a case is a diff nobody reads back against the sentence. This reads both.
    """
    match = UNENFORCED_COUNT_ROW.search(_text(ENFORCEMENT))
    assert match, (
        "the locally-decidable row's headline no longer states a count in the expected "
        "form; either restore it or delete this check deliberately")
    spelled = match.group(1)
    assert spelled in _NUMERALS, (
        f"{spelled!r} is not a numeral this check knows; add it to _NUMERALS or reword "
        "the row")

    registry = importlib.import_module("test_unenforced_local_rules").UNENFORCED
    assert _NUMERALS[spelled] == len(registry), (
        f"the row says {spelled} ({_NUMERALS[spelled]}) locally decidable violations; "
        f"the registry carries {len(registry)}")



# --------------------------------------------------------------------------- #
# OD-8 / OD-9 / OD-10 — the ratified selection and no-selection meanings (2026-08-28)
# --------------------------------------------------------------------------- #
#
# These guard the four meanings the owner's ruling fixed, each of which a later edit
# could plausibly undo by reverting to the pre-ruling phrasing. They are document
# checks, not runtime assertions: no selector exists yet, so what can drift is the
# prose that the eventual implementation will be written from.
#
# Scope, stated exactly: each asserts the presence of a ratified statement, or the
# absence of the specific withdrawn one it replaces. None of them proves the documents
# say nothing else contradictory — that is the same ceiling the strategy-authority
# scan discloses above, and it is not narrowed here.


def test_od8_ratifies_fail_closed_uniqueness_not_an_outstanding_ranking_criterion():
    """OD-8 is decided. The pre-ruling text called it outstanding; a revert to that
    wording, or to any 'ranking criterion is not ratified' phrasing, fails here."""
    spec = _text(SPECIFICATION)
    assert "OD-8 — RATIFIED: selection-policy v1 is fail-closed uniqueness" in spec
    assert "exactly one** candidate is both" in spec
    assert "OD-8 (outstanding)" not in spec, (
        "OD-8 is ratified 2026-08-28; the outstanding-marker wording is withdrawn")
    assert "OD-8 must be ratified before" not in spec


def test_od8_bars_repurposing_existing_fields_as_merit_proxies():
    """The non-repurposing bar is the substance of OD-8's second half. Losing it would
    let an implementer rank on caller-supplied fields, which is exactly what the
    ruling forbids."""
    spec = _text(SPECIFICATION)
    assert "must not** be repurposed as merit proxies" in spec
    for field in ("uncertainties", "evaluated_at", "candidate_id"):
        assert field in spec


#: The three live assertions of tie-break decisiveness that stood before OD-8, one per
#: site. The phrase "always decisive" itself still occurs — quoted in the correction and
#: negated in the ADR — so the bare phrase cannot be the check: withdrawing a claim means
#: naming it. These are the predicate forms that assert it rather than retire it.
_WITHDRAWN_TIE_BREAK_PREDICATES = (
    "is therefore always decisive",
    "and so is always decisive",
    "always decisive on its own",
)


def test_the_candidate_id_tie_break_is_not_asserted_as_always_decisive():
    """OD-8's tie-break correction. Under fail-closed uniqueness the tie-break is
    unexercised, so no document may assert it resolves a substantive preference.

    Scope: this catches a revert to any of the three phrasings that carried the claim,
    not every sentence that could express it.
    """
    for path in (SPECIFICATION, ADR):
        body = _text(path)
        for predicate in _WITHDRAWN_TIE_BREAK_PREDICATES:
            assert predicate not in body, (
                f"{path.name}: {predicate!r} asserts the tie-break decisiveness OD-8 "
                f"withdrew")
    spec = _text(SPECIFICATION)
    assert "deliberately\nunexercised" in spec or "deliberately unexercised" in spec
    assert "Tie-break correction to OD-7" in spec


def test_od9_maps_inconclusive_to_abstain_per_candidate_not_run_wide():
    """OD-9 and its mixed-set scope — the ambiguity the ruling resolved. The run-wide
    reading is the one an implementer is most likely to restore by accident."""
    spec = _text(SPECIFICATION)
    assert "OD-9 — `INCONCLUSIVE` maps to `ABSTAIN`" in spec
    assert "does **not** poison the candidate set" in spec
    assert "OD-9 (outstanding)" not in spec, (
        "OD-9 is ratified 2026-08-28; the outstanding-marker wording is withdrawn")


def test_od10_covers_the_residual_completed_no_selection_run():
    """OD-10 exists so a completed run cannot fall through the fail-closed table with
    no ratified outcome. Both the ruling and its exclusion of the OD-7 rows matter."""
    spec = _text(SPECIFICATION)
    assert "OD-10 — the residual completed no-selection outcome" in spec
    assert "does **not** cover missing evidence" in spec


def test_the_fail_closed_table_carries_six_ordered_non_overlapping_rows():
    """The table is the operative statement of S2 MVP outcome order. A row silently
    dropped, or the ordering guarantee removed, is the drift this catches."""
    spec = _text(SPECIFICATION)
    assert "The rows are evaluated in the order given and do not overlap" in spec
    for row in ("| 1 |", "| 2 |", "| 3 |", "| 4 |", "| 5 |", "| 6 |"):
        assert row in spec, f"fail-closed table is missing row {row}"
    assert "**OD-8**" in spec and "**OD-9**" in spec and "**OD-10**" in spec


def test_no_owner_decision_is_recorded_as_outstanding():
    """After 2026-08-28 the outstanding set is empty; what remains is a *deferral*
    (substantive multi-candidate ranking), which is a different status and must not be
    relabelled as an outstanding ruling."""
    for path in (SPECIFICATION, ADR):
        body = _text(path)
        assert "OD-8 and OD-9 remain outstanding" not in body, path.name
    assert "substantive multi-candidate ranking" in _text(SPECIFICATION).lower() or (
        "Substantive multi-candidate ranking" in _text(SPECIFICATION))
