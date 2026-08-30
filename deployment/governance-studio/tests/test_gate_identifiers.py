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
import re
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


RATIFIED_IDS = [f"P3E-CTR-{i:02d}" for i in range(1, 14)]
# the original five-way split of the positive runtime path, plus the appended §11 gate
RUNTIME_SPLIT = ["P3E-CTR-06", "P3E-CTR-07", "P3E-CTR-08", "P3E-CTR-09", "P3E-CTR-10"]
NON_COMPENSATORY = RUNTIME_SPLIT + ["P3E-CTR-13"]
RUNTIME_GATES = RUNTIME_SPLIT + ["P3E-CTR-13"]
STARTUP_CASES = {"missing certificate", "missing key", "certificate/key mismatch",
                 "missing credentials", "malformed password hash"}
OBLIGATIONS = {"runtime-package-inventory", "image-sbom", "evidence-manifest", "upload-evidence"}


@pytest.fixture(scope="module")
def family():
    return json.load(open(os.path.join(AUDIT, "CONTAINER_GATE_FAMILY.json"),
                          encoding="utf-8"))


def test_ratified_family_has_exactly_the_twelve_identities(family):
    assert family["status"] == "RATIFIED"
    assert list(family["gates"]) == RATIFIED_IDS
    assert family["gate_count"] == 13
    steps = [b["workflow_step"] for b in family["gates"].values()]
    # the four evidence steps are NOT gates
    assert OBLIGATIONS.isdisjoint(set(steps))


def test_every_ratified_gate_is_a_verification_gate(family):
    for gid, body in family["gates"].items():
        assert body["gate_kind"] == "verification", gid
        assert body["requirement"], gid
        assert body["workflow_step"], gid


def test_four_evidence_obligations_are_mandatory_and_not_gates(family):
    ob = family["evidence_obligations"]["obligations"]
    assert set(ob) == OBLIGATIONS
    for name, body in ob.items():
        assert body["mandatory"] is True, name
        assert name not in family["gates"], name
    assert ob["runtime-package-inventory"]["attached_to"] == ["P3E-CTR-04"]
    assert ob["image-sbom"]["attached_to"] == ["P3E-CTR-11"]
    assert ob["evidence-manifest"]["attached_to"] == "FAMILY_COMPLETION"
    assert ob["upload-evidence"]["attached_to"] == "FAMILY_COMPLETION"
    # missing evidence makes a run incomplete, it does not create a gate
    assert "INCOMPLETE" in family["evidence_obligations"]["rule"]


def test_runtime_verification_gates_are_distinct_and_non_compensatory(family):
    runtime = [g for g, b in family["gates"].items()
               if b["workflow_step"] == "container-runtime-verification"]
    assert runtime == RUNTIME_GATES
    # the original positive-path split is exactly five, unchanged
    assert [g for g in runtime if g != "P3E-CTR-13"] == RUNTIME_SPLIT
    sections = {family["gates"][g]["script_section"] for g in runtime}
    assert len(sections) == len(runtime), "each runtime gate must cover a distinct section"
    assert family["non_compensatory_rule"]["applies_to"] == NON_COMPENSATORY
    for g, b in family["gates"].items():
        assert b["non_compensatory"] is (g in NON_COMPENSATORY), g


def test_exactly_thirteen_canonical_gates(family):
    assert len(family["gates"]) == 13
    assert list(family["gates"]) == RATIFIED_IDS


def test_existing_identifiers_were_not_renumbered(family):
    """Appending P3E-CTR-13 must not disturb 01-12."""
    expected = {
        "P3E-CTR-01": "ratified-pin-conformance",
        "P3E-CTR-02": "base-image-digest-verification",
        "P3E-CTR-03": "container-build",
        "P3E-CTR-04": "image-inspection",
        "P3E-CTR-05": "image-layer-secret-scan",
        "P3E-CTR-06": "container-runtime-verification",
        "P3E-CTR-07": "container-runtime-verification",
        "P3E-CTR-08": "container-runtime-verification",
        "P3E-CTR-09": "container-runtime-verification",
        "P3E-CTR-10": "container-runtime-verification",
        "P3E-CTR-11": "container-vulnerability-scan",
        "P3E-CTR-12": "clean-checkout-reproducibility",
    }
    for gid, step in expected.items():
        assert family["gates"][gid]["workflow_step"] == step, gid


def test_startup_integrity_gate_is_complete_and_uniquely_mapped(family):
    g = family["gates"]["P3E-CTR-13"]
    assert g["non_compensatory"] is True
    assert g["requires_container_runtime"] is True
    assert g["script_section"] == "§11 startup-failure negatives"
    # uniquely mapped: no other gate claims §11
    others = [k for k, b in family["gates"].items()
              if k != "P3E-CTR-13" and b.get("script_section") == g["script_section"]]
    assert others == []
    assert set(g["required_cases"]) == STARTUP_CASES
    assert "before network binding" in g["case_requirement"]
    # the running-container claim is distinguished from in-process coverage
    cd = g["claim_distinction"]
    assert "running container" in cd["this_gate_claims"]
    assert "test_startup_integrity.py" in cd["in_process_coverage_claims"]
    assert "does not discharge" in cd["why_distinct"]


def test_sbom_is_not_attached_to_the_build_gate(family):
    sbom = family["evidence_obligations"]["obligations"]["image-sbom"]
    assert "P3E-CTR-03" not in sbom["attached_to"]
    assert sbom["attached_to"] == ["P3E-CTR-11"]


def test_sbom_provenance_role_can_never_read_as_sufficient(family):
    sbom = family["evidence_obligations"]["obligations"]["image-sbom"]
    role = sbom["family_evidence_role"]
    assert role["role"] == "IMAGE_PROVENANCE"
    assert role["sufficiency"] == "CONTRIBUTORY_NOT_SUFFICIENT"
    assert role["establishes_provenance"] is False
    # no field anywhere in the obligation may claim sufficiency
    blob = json.dumps(sbom).lower()
    for claim in ("sufficient provenance", '"sufficiency": "sufficient"',
                  "establishes provenance", "trusted-build provenance established"):
        assert claim not in blob, claim


def test_ratification_defines_requirements_and_executes_nothing(family, definition):
    assert "does NOT execute" in family["what_ratification_means"]
    for gid, body in family["gates"].items():
        assert body["execution_state"] == "NOT_EXECUTED", gid
    assert "executes no gate" in definition["retirement"][
        "what_ratification_of_the_successor_means"]


def test_historical_family_is_retired_but_preserved(definition):
    r = definition["retirement"]
    assert definition["status"] == "RETIRED_SUPERSEDED"
    assert r["status"] == "RETIRED_SUPERSEDED"
    assert r["superseded_by"]["family"] == "P3E-CTR"
    assert "IMMUTABLE" in r["register_preservation"]
    # the register itself is unchanged in substance
    assert definition["gates"]["C2"]["definition_status"] == "DEFINED_HISTORICAL_GATE"
    assert definition["gates"]["C4"]["definition_status"] == "DEFINED_HISTORICAL_GATE"
    for i in range(5, 20):
        assert definition["gates"][f"C{i}"]["definition_status"] == "UNDEFINED_HISTORICAL_GATE"
    assert definition["canonical_identifiers"] == EXPECTED


def test_no_correspondence_between_the_families(family, definition):
    rel = family["relationship_to_the_historical_C_family"]
    assert rel["correspondence_asserted"] is False
    assert definition["superseded_by"]["correspondence_to_this_family"] == "none asserted"
    assert "NONE ASSERTED" in definition["retirement"]["correspondence_to_the_ratified_family"]
    # no ratified gate body may name a historical C identifier
    for gid, body in family["gates"].items():
        assert not re.search(r"\bC\d+\b", json.dumps(body)), gid
    # nor may any obligation
    for name, body in family["evidence_obligations"]["obligations"].items():
        assert not re.search(r"\bC\d+\b", json.dumps(body)), name


def test_family_gate_and_obligation_definitions_may_not_name_a_historical_gate(
        verifier, tmp_path):
    """The disclaimer is enforced where a mapping could actually be smuggled in.

    A canonical C-identifier is legal everywhere else, so this is the one place the
    scanner rejects one: naming a historical gate inside a P3E-CTR gate body or an
    evidence obligation would assert exactly the correspondence the record denies.
    """
    family = os.path.join(AUDIT, "CONTAINER_GATE_FAMILY.json")
    for probe in (("gates", "P3E-CTR-06", "maps_to"),
                  ("evidence_obligations", "obligations", "image-sbom", "supersedes")):
        doc = json.load(open(family, encoding="utf-8"))
        node = doc
        for key in probe[:-1]:
            node = node[key]
        node[probe[-1]] = "C11"
        copy = tmp_path / "CONTAINER_GATE_FAMILY.json"
        json.dump(doc, open(copy, "w", encoding="utf-8"))
        assert verifier.main(DEFINITION, [str(copy)]) == 1, probe


def test_disclaimer_section_may_still_name_historical_gates(verifier, tmp_path):
    """The relationship section states the disclaimer; it must remain able to."""
    family = os.path.join(AUDIT, "CONTAINER_GATE_FAMILY.json")
    doc = json.load(open(family, encoding="utf-8"))
    statuses = doc["relationship_to_the_historical_C_family"]["historical_gate_statuses"]
    assert {"C2", "C4"} <= set(statuses), "fixture no longer exercises the allowance"
    copy = tmp_path / "CONTAINER_GATE_FAMILY.json"
    json.dump(doc, open(copy, "w", encoding="utf-8"))
    assert verifier.main(DEFINITION, [str(copy)]) == 0


def test_ratified_family_is_not_referenced_by_any_ci_step():
    """A defined requirement set must not be silently enforced as a CI gate."""
    wf = open(os.path.join(REPO, ".github", "workflows",
                           "governance-studio-p3e-private-hosted-ci.yml"), encoding="utf-8").read()
    assert "CONTAINER_GATE_FAMILY" not in wf


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
