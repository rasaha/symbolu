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
    """The ADR's OD-1 – OD-5 table is the single **decision record**.

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
    assert "## Owner decisions OD-1 – OD-5 — all resolved" in _text(ADR)
    competing = []
    for path in DOCUMENTS:
        if path == ADR:
            continue
        for heading in re.findall(r"^#{1,6}\s+(.*OD-[1-5].*)$", _text(path), re.M):
            if any(w in heading.lower() for w in _RATIFICATION_HEADING_WORDS):
                competing.append(f"{path.name}: {heading}")
    assert not competing, (
        f"a rival OD-1 – OD-5 ratification heading exists outside the ADR: {competing}")


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


#: The five decisions, and the facts both documents must state identically about each.
#: OD-5 (2026-08-26) joins OD-1 – OD-4 (2026-08-25); the dates differ per decision and
#: are compared per decision, so a fifth entry does not weaken the agreement check.
OWNER_DECISIONS = (1, 2, 3, 4, 5)
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


def test_exactly_od_4_and_od_5_are_recorded_as_bearing_on_contract_shape():
    """The ADR table's third column is the load-bearing distinction between a decision
    about a guard and a decision about the contracts. OD-1 – OD-3 change no contract,
    field type, cardinality, vocabulary or equation term; OD-4 and OD-5 do. If that
    column ever said otherwise for one of the first three, the specification's Part D
    would be downstream of a decision nobody re-read it against — and if it said ``no``
    for OD-5, D2's eleventh field would be carried by a decision the table records as
    shape-neutral."""
    rows = re.findall(r"\| \*\*OD-([1-5])\*\* — \*\*RATIFIED[^|]*\|[^|]*\|([^|]*)\|",
                      _text(ADR))
    bears = {od: cell.strip().lower() for od, cell in rows}
    assert set(bears) == {"1", "2", "3", "4", "5"}, (
        f"the ADR decision table does not carry all five rows: {sorted(bears)}")
    for od in ("1", "2", "3"):
        assert bears[od] == "no", f"OD-{od} is recorded as bearing on contract shape"
    for od in ("4", "5"):
        assert bears[od].startswith("**yes"), (
            f"OD-{od} must be recorded as bearing on contract shape: {bears[od]!r}")
    spec = _normalised(SPECIFICATION)
    assert "OD-4 did change contract shape" in spec, (
        "the specification must agree that OD-4 changed contract shape")
    assert "OD-5, ratified 2026-08-26, also bears on contract shape" in spec, (
        "the specification must agree that OD-5 bears on contract shape too")


#: The ADR's owner-decision section heading, and the italic cross-references to it that
#: the other documents and the ADR's own later sections carry.
_OD_SECTION_HEADING = re.compile(r"^#{1,6}\s+(Owner decisions OD-1 – OD-\d[^\n]*)$", re.M)
_OD_SECTION_REFERENCE = re.compile(r"\*(Owner decisions OD-1 – OD-\d)\*")

#: A claim that exactly one decision bears on contract shape. True while OD-4 was the only
#: one; false since OD-5. Written as a pattern rather than a fixed sentence because the
#: claim appears in the ADR's prose in a different wording from the table it contradicts.
_SOLE_SHAPE_BEARER_CLAIM = re.compile(
    r"\bthe\s+only\s+one\s+(?:bearing|that\s+bears)\s+on\s+contract\s+shape", re.I)


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
    """Two decisions bear on contract shape, OD-4 and OD-5.

    The table column is checked elsewhere; this reads the prose, which is where the stale
    claim survived. A document whose narrative says one thing and whose table says another
    misdirects the reader who does not reach the table.
    """
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

    assert _SOLE_SHAPE_BEARER_CLAIM.search(
        "OD-4, the only one bearing on contract shape, is resolved (a)")
    assert _SOLE_SHAPE_BEARER_CLAIM.search(
        "OD-4 is the only one that bears on contract shape")
    assert not _SOLE_SHAPE_BEARER_CLAIM.search(
        "Two bear on contract shape, OD-4 and OD-5.")


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


def test_the_five_owner_decisions_are_each_recorded_as_ratified():
    body = _text(ADR)
    for od in ("OD-1", "OD-2", "OD-3", "OD-4", "OD-5"):
        assert re.search(rf"\*\*{od}\*\* — \*\*RATIFIED", body), od
    assert "All five owner decisions are resolved" in _text(SPECIFICATION)


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

#: OD-5: an **affirmative** claim that S1 has authority over a reasoning strategy.
#:
#: S1 neither selects, validates nor cryptographically binds one — selection and
#: enforcement are S2's — and ``declared_strategy`` is metadata outside ``P_unsigned``
#: whose declaration establishes no conformance. Those are the statements the documents
#: make, and the risk is that a later edit quietly upgrades one of them: a sentence
#: saying S1 checks a declared strategy against a role's permitted set, or that the
#: declaration is inside the digest, would read as ratified authority this stage does not
#: have and would put an implementer to work on it.
#:
#: Every pattern is **adjacency-anchored on the affirmative form**, so the documents' own
#: negations — "S1 neither selects, validates nor cryptographically binds…", "declaration
#: does not establish conformance", "is not covered by ``advisory_digest``" — do not match
#: them. A scan that flagged the denial along with the claim would be unusable here, since
#: the denial is exactly what these documents are required to say.
#: The subject an affirmative claim gives the authority to. ``S1`` names the stage; the
#: builder and the validator are the two things inside it that a sentence would credit
#: instead, and a claim about them is a claim about S1.
_S1_ACTOR = r"(?:S1|the\s+S1\s+\w+|the\s+builder|the\s+validator)"
#: Any spelling of the subject matter: the prose phrase, the two field names, and the
#: bare noun. ``\b`` does not break at an underscore, so ``permitted_reasoning_strategies``
#: is NOT reached by a pattern anchored on ``\breasoning``; the field names are matched
#: literally for that reason.
_STRATEGY_NOUN = (r"(?:reasoning\s+strateg(?:y|ies)|declared[\s_]strateg(?:y|ies)|"
                  r"permitted_reasoning_strategies|declared_strategy|"
                  r"(?:a|the|its|any|each)\s+strategy|strategy\s+conformance)")
#: Verbs that assert authority over it. Selection, validation and binding as the task
#: names them, plus the spellings each is naturally written in.
_AUTHORITY_VERB = (r"(?:select|selects|validate|validates|verify|verifies|check|checks|"
                   r"enforce|enforces|bind|binds|reject|rejects|constrain|constrains|"
                   r"choose|chooses|match|matches|compare|compares)")
_AUTHORITY_PARTICIPLE = (r"(?:selected|validated|verified|checked|enforced|bound|"
                         r"rejected|constrained|chosen|matched|compared)")

STRATEGY_AUTHORITY_CLAIM_PATTERNS = (
    # Active voice: an S1 actor is the subject of an authority verb over a strategy.
    rf"\b{_S1_ACTOR}\s+{_AUTHORITY_VERB}\b[^.\n]{{0,80}}?{_STRATEGY_NOUN}",
    # Passive voice: the strategy is acted on, S1 named as the agent or the locus.
    rf"{_STRATEGY_NOUN}[^.\n]{{0,80}}?\b(?:is|are|was|were)\s+{_AUTHORITY_PARTICIPLE}"
    rf"\b[^.\n]{{0,60}}?\b(?:by|at|in|within|during)\s+{_S1_ACTOR}\b",
    # The cross-field check, in either order and without naming S1 at all: the whole of
    # what S2 adds is a comparison between the declaration and the permitted set.
    r"\bdeclared[\s_]strateg(?:y|ies)\b[^.\n]{0,60}?\b(?:against|with|to)\b"
    r"[^.\n]{0,40}?(?:permitted_reasoning_strategies|permitted\s+(?:set|strateg))",
    r"\bpermitted_reasoning_strategies\b[^.\n]{0,60}?\b(?:against|with|to)\b"
    r"[^.\n]{0,40}?declared[\s_]strateg",
    # The binding claim stated in field terms rather than in S1's name.
    r"\bdeclared_strategy\b[^.\n]{0,80}?\b(?:participates\s+in|is\s+inside|"
    r"is\s+part\s+of|is\s+covered\s+by|is\s+bound\s+into)\b[^.\n]{0,40}?"
    r"(?:P_unsigned|advisory_digest|digest|identity)",
    # The conformance claim: that declaring a strategy shows one was followed.
    r"\bdeclar(?:ation|ing|ed\s+strategy)\b[^.\n]{0,60}?\bestablishes\s+"
    r"(?:conformance|that)\b",
)


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


def _strategy_authority_claims(body, label="text"):
    """Every affirmative claim of S1 strategy authority in ``body``, located by line."""
    offenders = []
    for pattern in STRATEGY_AUTHORITY_CLAIM_PATTERNS:
        for match in re.finditer(pattern, body, re.I):
            line = body.count("\n", 0, match.start()) + 1
            offenders.append(f"{label}:{line}: {match.group(0)!r}")
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


#: One violating text per ``STRATEGY_AUTHORITY_CLAIM_PATTERNS`` entry, in the same order.
#:
#: Each is a sentence a future edit could plausibly write, and each is refused. No
#: individual reasoning strategy is named in any of them — none needs to be, because
#: every pattern turns on the *authority verb* and not on the method, and naming one here
#: would seed a candidate member of a vocabulary that is not ratified.
_STRATEGY_AUTHORITY_POSITIVES = (
    "S1 validates the declared reasoning strategy against the role's permitted set.",
    "The reasoning strategy is enforced at S1, before the advisory is constructed.",
    "A declared_strategy is checked against permitted_reasoning_strategies here.",
    "The permitted_reasoning_strategies list is compared against declared_strategy.",
    "`declared_strategy` is covered by `advisory_digest`, so it cannot be altered.",
    "Declaring a strategy establishes conformance with the method it names.",
)

#: The spellings an independent audit found passing an earlier, narrower version of this
#: scan. Kept as a named regression set rather than folded into the list above, because
#: the failure they exposed was not a dead pattern — every pattern matched the sentence it
#: was written from — but a scan whose reach was **narrower than the coverage the ADR and
#: the CHANGELOG claimed for it**. That gap is invisible to a per-pattern self-test, so it
#: needs cases nobody wrote a pattern from.
#:
#: The specific defect: ``\b`` does not break at an underscore, so a pattern anchored on
#: ``\breasoning\s+strateg`` never reaches ``permitted_reasoning_strategies``; and the
#: subject of a sentence claiming this authority is as often "the builder" as "S1".
_STRATEGY_AUTHORITY_REGRESSIONS = (
    "S1 validates `permitted_reasoning_strategies` against the declared strategy.",
    "S1 checks `declared_strategy` against the role's permitted set.",
    "The builder selects a reasoning strategy before constructing the advisory.",
    "S1 enforces the role's permitted_reasoning_strategies at construction.",
    "The declared strategy is validated against the permitted set at S1.",
    "S1 binds the declared strategy into the advisory digest.",
    "S1 rejects a declared strategy the role may not select.",
    "Strategy conformance is enforced by the S1 builder.",
)


@pytest.mark.parametrize("text", _STRATEGY_AUTHORITY_REGRESSIONS,
                         ids=lambda t: t[:40])
def test_the_strategy_authority_scan_catches_the_spellings_that_once_escaped(text):
    """Each sentence an audit found passing the narrower scan must now be caught.

    Parametrized so a regression is named rather than reported as one failure among
    eight, and kept separate from the paired self-test above so that widening the scan
    later cannot quietly drop one of them.
    """
    assert _strategy_authority_claims(text, "regression"), (
        f"the strategy-authority scan misses {text!r}; the ADR and the CHANGELOG claim "
        "it refuses ANY affirmative claim of S1 authority over a reasoning strategy, and "
        "a scan narrower than its stated coverage overstates what the documents are "
        "guarded against")

#: Text the scan must leave alone: the documents' own denials, which are adjacent to the
#: claims in wording and opposite in meaning. Without this control the scan could be
#: "fixed" by broadening a pattern until it matched the denial too, which would make
#: every conformant document fail and the guard useless.
_STRATEGY_AUTHORITY_NEGATIVES = (
    "S1 neither selects, validates nor cryptographically binds a reasoning strategy.",
    "Strategy selection and enforcement are S2's in whole.",
    "Declaration does not establish conformance.",
    "`declared_strategy` is not covered by `advisory_digest` and is outside "
    "`P_unsigned`.",
    "A reasoning strategy is a method label, not a process state.",
    "`permitted_reasoning_strategies` rejects every non-empty value at this stage.",
)


def test_every_strategy_authority_pattern_matches_a_text_built_to_violate_it():
    """The scan runs over documents that deny S1 has this authority, and a pattern
    edited into inertness reports exactly the same green.

    Paired one-to-one with the pattern list and asserted pairwise, so a dead pattern is
    named rather than hidden behind another pattern's match. The negative controls then
    prove the scan discriminates: it must catch the claim and leave the denial standing,
    and a scan that cannot tell those apart is not usable on these documents at all.
    """
    assert len(_STRATEGY_AUTHORITY_POSITIVES) == len(STRATEGY_AUTHORITY_CLAIM_PATTERNS), (
        f"{len(STRATEGY_AUTHORITY_CLAIM_PATTERNS)} strategy-authority patterns and "
        f"{len(_STRATEGY_AUTHORITY_POSITIVES)} synthetic violations; a pattern added "
        "without a violation to prove it is a pattern nothing tests")
    for pattern, text in zip(STRATEGY_AUTHORITY_CLAIM_PATTERNS,
                             _STRATEGY_AUTHORITY_POSITIVES):
        assert re.search(pattern, text, re.I), (
            f"the strategy-authority pattern {pattern!r} no longer matches {text!r}; it "
            "would report every document in DOCUMENTS clean")
        assert _strategy_authority_claims(text, "synthetic"), (
            f"the strategy-authority scan missed {text!r} even though {pattern!r} "
            "matches it")
    for text in _STRATEGY_AUTHORITY_NEGATIVES:
        assert not _strategy_authority_claims(text, "synthetic"), (
            f"the strategy-authority scan flags the denial {text!r}; it is matching too "
            "much, not too little, and would fail every conformant document")


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
    counts as exercised now for a different and behavioural reason — a constructed case in
    ``UNENFORCED`` — and this test asserts that reason rather than the outcome, so
    deleting the case would fail here rather than pass on the mention.
    """
    mentions = _rule_mentions_under_tests()
    exercised = _rules_exercised_by_some_test()

    assert "test_process_ordering_obligation.py" in mentions["R-4"], (
        "precondition: the obligation module mentions R-4")
    registry = importlib.import_module("test_unenforced_local_rules").UNENFORCED
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
#: away from the registry it describes.
UNENFORCED_COUNT_ROW = re.compile(
    r"^\| \*\*([A-Za-z-]+) locally decidable violations the representative shapes "
    r"accept\*\* \|", re.M)

#: Spelled numerals the row may use. Bounded rather than open: a row needing a number
#: outside this range is a row that should be reworded rather than extended again. The
#: upper end was raised when C4's per-field cases landed — C4 states its requirement of
#: each ``datetime`` field, so it contributes one case per field rather than one per
#: rule — and the range is deliberately left with headroom above the current count so a
#: single added case is a one-line diff rather than a table edit.
_NUMERALS = {
    "Nineteen": 19, "Twenty": 20, "Twenty-one": 21, "Twenty-two": 22,
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

