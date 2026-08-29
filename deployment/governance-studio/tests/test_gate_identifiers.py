"""Canonical P3E container-gate identifier conformance.

The P3E audit records once disagreed on the gate list: one spelled two gates
``C16-image``/``C17-image``, the other omitted them entirely. The canonical set
now lives in ``docs/audits/ugence_governance_studio_p3e/CONTAINER_GATE_DEFINITION.json``
and these tests keep the records from drifting away from it again.

They assert identifier hygiene and the definition/result separation. They do not
execute, and cannot execute, any container gate.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil

import pytest

from depaths import REPO

AUDIT = os.path.join(REPO, "docs", "audits", "ugence_governance_studio_p3e")
DEFINITION = os.path.join(AUDIT, "CONTAINER_GATE_DEFINITION.json")
RUNTIME_CAPABILITY = os.path.join(AUDIT, "CONTAINER_RUNTIME_CAPABILITY.json")
COMPLETION = os.path.join(AUDIT, "CONTAINER_COMPLETION_LIVE_STATE.json")
MIRROR_DECISION = os.path.join(AUDIT, "BASE_IMAGE_MIRROR_DECISION.json")
RECORDS = [RUNTIME_CAPABILITY, COMPLETION, MIRROR_DECISION]

CI = os.path.join(REPO, "deployment", "governance-studio", "ci")
EXPECTED = ["C2"] + [f"C{i}" for i in range(4, 20)]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(CI, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def verifier():
    return _load("verify_gate_identifiers")


@pytest.fixture(scope="module")
def definition():
    return json.load(open(DEFINITION, encoding="utf-8"))


def test_canonical_set_is_exactly_c2_and_c4_through_c19(definition):
    assert definition["canonical_identifiers"] == EXPECTED
    assert definition["canonical_identifier_count"] == 17
    assert "C1" not in definition["canonical_identifiers"]
    assert "C3" not in definition["canonical_identifiers"]


def test_image_suffixed_spellings_are_deprecated_aliases_not_gates(definition):
    aliases = definition["deprecated_aliases"]
    assert aliases["C16-image"]["canonical"] == "C16"
    assert aliases["C17-image"]["canonical"] == "C17"
    for alias in aliases.values():
        assert alias["status"] == "DEPRECATED_NONCANONICAL_ALIAS"
    # aliases are not additional gates
    assert set(aliases) & set(definition["canonical_identifiers"]) == set()


def test_every_gate_records_the_required_fields(definition):
    required = {
        "definition_status", "requirement", "workflow_step",
        "supporting_test_or_script", "requires_container_runtime",
        "evidence_required_before_passed",
    }
    for gate, body in definition["gates"].items():
        assert required <= set(body), f"{gate} is missing {required - set(body)}"
        assert body["definition_status"] in {
            "DEFINED_HISTORICAL_GATE", "UNDEFINED_HISTORICAL_GATE"}


def test_defined_gates_cite_a_source_and_assert_no_invented_mapping(definition):
    """C2 and C4 are DEFINED from the audit records; nothing else is."""
    defined = {g for g, b in definition["gates"].items()
               if b["definition_status"] == "DEFINED_HISTORICAL_GATE"}
    assert defined == {"C2", "C4"}
    for gate in sorted(defined):
        body = definition["gates"][gate]
        assert body["requirement"], gate
        assert body["definition_source"], gate
        assert body["definition_quote"], gate
        # a name-matched candidate step is a lead, never an asserted mapping
        assert body["workflow_step"] is None, gate
        assert body["candidate_workflow_step"]["asserted"] is False, gate


def test_group_defined_gates_carry_only_the_group_property(definition):
    """C5-C19 are defined collectively, never individually."""
    for i in range(5, 20):
        body = definition["gates"][f"C{i}"]
        assert body["definition_status"] == "UNDEFINED_HISTORICAL_GATE", f"C{i}"
        assert "group_property" in body, f"C{i}"
        assert body["requirement"] is None, f"C{i}"


def test_pull_request_history_search_is_recorded_negative(definition):
    """The PR-history search is recorded so it is not repeated."""
    s = definition["reconstruction_method"]["pull_request_history_search"]
    assert s["status"] == "NEGATIVE"
    assert s["searched_on"] and s["findings"]


def test_replacement_family_asserts_no_correspondence():
    """The proposed family must never imply a mapping onto the C identifiers."""
    import json as _json
    proposal = _json.load(open(
        os.path.join(AUDIT, "CONTAINER_GATE_FAMILY_PROPOSAL.json"), encoding="utf-8"))
    rel = proposal["relationship_to_the_historical_C_family"]
    assert rel["correspondence_asserted"] is False
    assert proposal["status"] == "PROPOSED_AWAITING_OWNER_RATIFICATION"
    assert proposal["nature"].startswith("DOCUMENTATION_ONLY")
    # no proposed gate may name a C identifier
    import re as _re
    for gid, body in proposal["gates"].items():
        assert gid.startswith("P3E-CTR-"), gid
        assert not _re.search(r"\bC\d+\b", _json.dumps(body)), gid


def test_proposal_is_not_referenced_by_any_ci_step():
    """A proposal must not be enforced as though ratified."""
    wf = open(os.path.join(REPO, ".github", "workflows",
                           "governance-studio-p3e-private-hosted-ci.yml"), encoding="utf-8").read()
    assert "CONTAINER_GATE_FAMILY_PROPOSAL" not in wf


def test_completion_specification_is_recorded_absent(definition):
    """The negative is recorded so the search is not repeated."""
    spec = definition["reconstruction_method"]["completion_specification"]
    assert spec["status"] == "ABSENT_FROM_REPOSITORY"
    assert spec["searched_on"]


def test_unknown_gates_assert_no_requirement_or_mapping(definition):
    """An UNKNOWN gate must not carry an invented requirement or mapping."""
    for gate, body in definition["gates"].items():
        if body["definition_status"] == "UNDEFINED_HISTORICAL_GATE":
            assert body["requirement"] is None, gate
            assert body["workflow_step"] is None, gate
            assert body["supporting_test_or_script"] is None, gate


def test_definition_carries_no_execution_result(definition):
    """Gate definitions stay separate from gate execution state."""
    for gate, body in definition["gates"].items():
        assert not {"state", "status", "executed", "passed", "result"} & set(body), gate


@pytest.mark.parametrize("record", RECORDS, ids=lambda p: os.path.basename(p))
def test_audit_records_use_only_canonical_identifiers(record, verifier, definition):
    canonical = set(definition["canonical_identifiers"])
    aliases = set(definition["deprecated_aliases"])
    doc = json.load(open(record, encoding="utf-8"))
    for ident, where, historical in verifier._walk(doc):
        if ident in canonical:
            continue
        assert ident in aliases and historical, (
            f"{os.path.basename(record)} uses '{ident}' at {where}"
        )


def test_every_container_gate_is_still_not_executed():
    runtime = json.load(open(RUNTIME_CAPABILITY, encoding="utf-8"))
    completion = json.load(open(COMPLETION, encoding="utf-8"))
    assert runtime["blocked_gates"] == EXPECTED
    assert completion["not_executed"] == EXPECTED
    assert runtime["container_gates_executable"] is False


def test_verifier_passes_on_the_committed_records(verifier):
    assert verifier.main(DEFINITION, RECORDS) == 0


@pytest.mark.parametrize(
    "mutate, why",
    [
        (lambda d: d["blocked_gates"].__setitem__(13, "C16-image"), "reintroduced alias"),
        (lambda d: d["blocked_gates"].append("C23"), "invented identifier"),
        (lambda d: d.__setitem__("nested", {"a": [{"b": "C17-image"}]}), "alias nested deep"),
        (lambda d: d.__setitem__("notes", {"C16-image": "x"}), "alias as a dict key"),
    ],
    ids=["alias", "invented", "nested", "key"],
)
def test_verifier_rejects_noncanonical_identifiers(mutate, why, verifier, tmp_path):
    record = tmp_path / "CONTAINER_RUNTIME_CAPABILITY.json"
    shutil.copy(RUNTIME_CAPABILITY, record)
    doc = json.load(open(record, encoding="utf-8"))
    mutate(doc)
    json.dump(doc, open(record, "w", encoding="utf-8"))
    assert verifier.main(DEFINITION, [str(record)]) == 1, why


def test_deprecated_alias_is_allowed_only_in_a_historical_field(verifier, tmp_path):
    """Provenance may quote the superseded spelling; live data may not."""
    record = tmp_path / "CONTAINER_RUNTIME_CAPABILITY.json"
    shutil.copy(RUNTIME_CAPABILITY, record)
    doc = json.load(open(record, encoding="utf-8"))
    doc["gate_identifier_reconciliation"]["previous_blocked_gates"] = ["C16-image"]
    json.dump(doc, open(record, "w", encoding="utf-8"))
    assert verifier.main(DEFINITION, [str(record)]) == 0

    doc["blocked_gates"] = ["C16-image"]
    json.dump(doc, open(record, "w", encoding="utf-8"))
    assert verifier.main(DEFINITION, [str(record)]) == 1


def test_ratified_pin_conformance_holds_on_the_committed_tree():
    """The guard added with the mirror ratification still passes as committed."""
    pins = _load("verify_ratified_pins")
    cwd = os.getcwd()
    os.chdir(REPO)
    try:
        assert pins.main() == 0
    finally:
        os.chdir(cwd)
