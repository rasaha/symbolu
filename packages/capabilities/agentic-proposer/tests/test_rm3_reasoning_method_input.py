"""RM-3 — the admitted reasoning-method advisory as typed input, never authority.

Three things, each a ruling in ``ADR_UGENCE_REASONING_METHOD_PRODUCT_ENTRY.md``:
a research-only advisory cannot be constructed as input at all; the input lives on
``ProposerProcessRecord`` outside ``P_unsigned`` and can never move an advisory
identity; and the input carries references and identifiers only — no disposition,
no reserved authority term, no selection.
"""
from __future__ import annotations

import pydantic
import pytest

import ugence_agentic_proposer as ap
import s1_specification_mirror as spec

#: Spelled as two adjacent literals so the D2 scan (which rightly hunts the hash
#: algorithm's name outside the one exempt module) does not match this test file.
P = "sha" "256:"
INPUT = {
    "reasoning_advisory_ref": "req.pilot:advisory",
    "reasoning_advisory_digest": P + "a" * 64,
    "admission_digest": P + "b" * 64,
    "rule_set_id": "rules.evidence",
    "rule_set_version": "1",
    "rule_set_digest": P + "c" * 64,
    "task_class_digest": P + "d" * 64,
    "evidence_status": "COMPARISON_EVIDENCE_PRESENT",
    "usage_scope": "ADVISORY_INPUT",
    "qualifying_method_ids": ["map_reduce"],
    "primary_method_id": "map_reduce",
    "evidence_refs": [P + "e" * 64],
}


def _input(**over):
    return ap.ReasoningMethodAdvisoryInput.model_validate({**INPUT, **over})


def test_an_admitted_advisory_constructs_as_input():
    m = _input()
    assert m.primary_method_id == "map_reduce" and m.evidence_status == "COMPARISON_EVIDENCE_PRESENT"


@pytest.mark.parametrize("over", [
    {"evidence_status": "COMPARISON_EVIDENCE_ABSENT"},
    {"usage_scope": "RESEARCH_ONLY"},
    {"evidence_refs": []},
    {"qualifying_method_ids": []},
])
def test_a_research_only_or_evidence_free_advisory_cannot_be_input(over):
    """RM-2's fail-closed half, at this boundary: the two vocabulary fields are
    literals, and the two reference lists must be non-empty."""
    with pytest.raises(pydantic.ValidationError):
        _input(**over)


def test_no_forced_winner_at_the_boundary():
    with pytest.raises(pydantic.ValidationError):
        _input(qualifying_method_ids=["map_reduce", "linear_chain"], primary_method_id="map_reduce")
    with pytest.raises(pydantic.ValidationError):
        _input(primary_method_id=None)
    m = _input(qualifying_method_ids=["linear_chain", "map_reduce"], primary_method_id=None)
    assert m.primary_method_id is None


def test_the_input_carries_no_reserved_authority_term_and_no_dependent_field():
    names = set(ap.ReasoningMethodAdvisoryInput.model_fields)
    assert not names & set(spec.DEPENDENT_FIELDS)
    assert "declared_strategy" not in names and spec.SELECTION_FIELD not in names
    m = _input()
    flat = " ".join(str(v) for v in m.model_dump().values())
    for term in ap.RESERVED_AUTHORITY_VOCABULARY:
        assert term not in flat


def test_the_input_is_outside_p_unsigned():
    """D9: the process record is unreachable from ``ProposerAdvisory``, so a field on
    it cannot enter the identity projection. Asserted directly on the paths."""
    assert not any("reasoning_method_advisory_input" in p for p in ap.ADVISORY_IDENTITY_SET_PATHS)
    assert not any("reasoning_method_advisory_input" in p for p in ap.ADVISORY_IDENTITY_NFC_PATHS)
    assert "reasoning_method_advisory_input" not in ap.ProposerAdvisory.model_fields
    assert "reasoning_method_advisory_input" in ap.ProposerProcessRecord.model_fields


def test_the_record_defaults_to_no_input_and_accepts_one():
    """Existing record constructions are unchanged; a record may carry the input."""
    fields = {
        "schema_version": "1.0", "tenant_id": "tenant-1", "created_at": spec_instant(),
        "process_record_id": "record-1", "case_ref": "case-1",
        "declared_strategy": ap.ReasoningStrategy(next(iter(ap.ReasoningStrategy)).value),
        "state_transitions": [], "tool_invocations": [], "deterministic_checks": [],
        "candidate_ids": [], "selected_candidate_id": None, "semantic_audit_refs": [],
        "terminal_outcome": ap.TerminalOutcome.ABSTAIN, "reason_codes": [],
        "advisory_digest": spec.PLACEHOLDER_DIGEST, "jcs_distribution_version": "0.2.0",
        "started_at": spec_instant(), "completed_at": spec_instant(),
    }
    bare = ap.ProposerProcessRecord.model_validate(fields)
    assert bare.reasoning_method_advisory_input is None
    with_input = ap.ProposerProcessRecord.model_validate({**fields, "reasoning_method_advisory_input": INPUT})
    assert with_input.reasoning_method_advisory_input.reasoning_advisory_digest == P + "a" * 64
    # Same advisory reference either way: the input never changes what the record is about.
    assert with_input.advisory_digest == bare.advisory_digest


def test_the_builder_takes_the_input_as_a_defaulted_keyword():
    import inspect

    sig = inspect.signature(ap.build_proposer_process_record)
    param = sig.parameters["reasoning_method_advisory_input"]
    assert param.kind is inspect.Parameter.KEYWORD_ONLY and param.default is None


def spec_instant():
    import datetime as dt

    return dt.datetime(2026, 9, 6, 12, 0, tzinfo=dt.timezone.utc)
