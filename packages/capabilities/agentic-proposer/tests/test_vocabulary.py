"""The ratified D4 vocabulary — exactly these terms, and no authority claim.

D4 is an owner decision, so these are equality assertions, not membership
assertions: an added member is as much a violation as a removed one.
"""
from __future__ import annotations

import pathlib

import pytest

import ugence_agentic_proposer as ap
from ugence_agentic_proposer.vocabulary import (
    RESERVED_AUTHORITY_VOCABULARY,
    CandidateDisposition,
    SemanticAuditorFindingStatus,
    TerminalOutcome,
)

SRC = pathlib.Path(ap.__file__).resolve().parent


def test_terminal_outcomes_are_exactly_the_ratified_four():
    assert {m.value for m in TerminalOutcome} == {
        "PROPOSAL", "NEED_EVIDENCE", "ABSTAIN", "ESCALATE"}


def test_candidate_dispositions_are_exactly_the_ratified_four():
    assert {m.value for m in CandidateDisposition} == {
        "RECOMMEND_MATCHED_FOR_APPROVAL", "RECOMMEND_WITHHOLD",
        "REQUEST_EVIDENCE", "ESCALATE_EXCEPTION"}


def test_semantic_auditor_statuses_are_exactly_the_ratified_four():
    assert {m.value for m in SemanticAuditorFindingStatus} == {
        "CONSISTENT", "INCONSISTENT", "INDETERMINATE", "CONFLICTING"}


def test_reserved_vocabulary_is_the_ratified_prohibition():
    assert RESERVED_AUTHORITY_VOCABULARY == frozenset({
        "CLEAR", "HOLD", "BLOCK", "AUTHORIZED", "AUTHORIZED_WITH_CONSTRAINTS",
        "DENIED", "INDETERMINATE", "SUPPORTED", "UNSUPPORTED", "CONSTRAINED",
        "EXPIRED"})


def test_no_terminal_outcome_is_a_reserved_authority_claim():
    assert not {m.value for m in TerminalOutcome} & RESERVED_AUTHORITY_VOCABULARY


def test_no_candidate_disposition_is_a_reserved_authority_claim():
    assert not {m.value for m in CandidateDisposition} & RESERVED_AUTHORITY_VOCABULARY


def test_indeterminate_is_scoped_to_the_semantic_auditor_only():
    """The one term D4 both reserves and ratifies, split by position.

    INDETERMINATE is reserved where it would read as an authority claim — a terminal
    outcome or a candidate disposition — and ratified only as the semantic auditor's
    reading of documents.
    """
    assert "INDETERMINATE" in RESERVED_AUTHORITY_VOCABULARY
    assert SemanticAuditorFindingStatus.INDETERMINATE.value == "INDETERMINATE"
    assert "INDETERMINATE" not in {m.value for m in TerminalOutcome}
    assert "INDETERMINATE" not in {m.value for m in CandidateDisposition}


def test_abstain_is_not_a_denial():
    """ABSTAIN must never be an alias for, or convertible to, a denial.

    agent_runtime_migration/reasoning/reflection.py:31 maps a denied authorization to
    REPLAN. The proposer makes the inverse guarantee: it emits no denial at all, so
    there is no denial for anything downstream to bypass by replanning.
    """
    assert TerminalOutcome.ABSTAIN.value == "ABSTAIN"
    assert "DENIED" not in {m.value for m in TerminalOutcome}
    assert "DENY" not in {m.value for m in TerminalOutcome}


@pytest.mark.parametrize("term", sorted(RESERVED_AUTHORITY_VOCABULARY - {"INDETERMINATE"}))
def test_reserved_terms_appear_in_no_enum_anywhere_in_the_package(term):
    values = ({m.value for m in TerminalOutcome}
              | {m.value for m in CandidateDisposition}
              | {m.value for m in SemanticAuditorFindingStatus})
    assert term not in values


def test_source_declares_no_competing_policy_decision_point():
    """No ALLOW/DENY/DEFER triad and no confidence-to-outcome gate (audit findings).

    agentic/agentic_framework/governance_service.py:460-478 returns ALLOW/DENY/DEFER;
    confidence_gate.py:465-505 converts a confidence float into HALT/CONFIRM/BLOCKED.
    Neither shape may be reproduced here.
    """
    banned = ("ALLOW", "DENY", "DEFER", "HALT", "CONFIRM", "BLOCKED",
              "confidence_gate", "confidence_threshold", "REPLAN")
    for path in sorted(SRC.rglob("*.py")):
        body = path.read_text(encoding="utf-8")
        for term in banned:
            assert term not in body, f"{path.name} contains {term!r}"


def test_public_api_exports_only_the_vocabulary_and_version():
    assert set(ap.__all__) == {
        "TerminalOutcome", "CandidateDisposition", "SemanticAuditorFindingStatus",
        "RESERVED_AUTHORITY_VOCABULARY", "__version__"}
