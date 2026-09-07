"""PWC-P3C — deterministic offline simulation.

The tests assert **properties** rather than a chosen terminal label: that traversal
is deterministic and replayable, that different facts take different paths, that a
requirement is observed and never resolved, and that nothing here can execute. A
test that pinned a preferred outcome would invite tuning the rules until they
produced it, which is the opposite of what a simulator is for.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import ugence_policy_workflow_compiler.api as api
from ugence_policy_workflow_compiler.models.assurance import (
    ExpectedOutcome,
    TestCategory,
    TestScenario,
)
from ugence_policy_workflow_compiler.reference.procurement import (
    build_procurement_approval_fixture,
    build_procurement_policy_pack,
)
from ugence_policy_workflow_compiler.semantics import compile_workflow_v2
from ugence_policy_workflow_compiler.simulation import (
    NodeOutcome,
    SimulationRun,
    simulate,
    simulate_all,
)

PINNED_V1_RELEASE_DIGEST = "sha256:fb9fd4b934cb94425a67b0f6b469ca0bbc198b356cd265822c3550ad9938158a"
PINNED_V2_FINGERPRINT = "sha256:2e031c78918f5d62378d460a6e1efd311f823ba234576f33ba8097739b29a0d7"

SRC = (
    pathlib.Path(__file__).resolve().parent.parent
    / "src"
    / "ugence_policy_workflow_compiler"
    / "simulation"
)

FACTS = {
    "supplier_id": "S-1",
    "budget_id": "B-1",
    "required_fields_complete": True,
    "amount": 500_000,
    "total_amount": 500_000,
    "assessment_blocked": False,
    "supplier_known": True,
    "budget_known": True,
}


@pytest.fixture(scope="module")
def package():
    pack = build_procurement_policy_pack()
    return api.compile_policy_pack(pack, build_procurement_approval_fixture(pack)).compiled_package


def _scenario(facts, name="scn.sim"):
    pack = build_procurement_policy_pack()
    return TestScenario(
        object_id=name,
        name=name,
        category=TestCategory.POSITIVE,
        provenance_refs=(pack.source_documents[0].object_id,),
        initial_facts=facts,
        expected_outcome=ExpectedOutcome(terminal_state="ADVANCE_AUTHORIZED"),
    )


# -- determinism and replay ----------------------------------------------------


def test_replay_is_digest_equality(package):
    first = simulate(package, _scenario(FACTS))
    second = simulate(package, _scenario(FACTS))
    assert first.run_digest == second.run_digest
    assert first.model_dump(mode="python") == second.model_dump(mode="python")


def test_the_run_digest_recomputes(package):
    run = simulate(package, _scenario(FACTS))
    assert run.run_digest == run.logical_digest()


def test_different_facts_take_different_paths(package):
    clear = simulate(package, _scenario(FACTS))
    blocked = simulate(package, _scenario(dict(FACTS, assessment_blocked=True)))
    missing = simulate(package, _scenario({k: v for k, v in FACTS.items() if k != "budget_id"}))
    digests = {clear.run_digest, blocked.run_digest, missing.run_digest}
    assert len(digests) == 3
    # A missing fact reaches fewer nodes than a complete one.
    assert len(missing.trace) < len(clear.trace)


def test_the_run_binds_the_release_it_simulated(package):
    run = simulate(package, _scenario(FACTS))
    assert run.release_digest == package.structural_digest


def test_every_scenario_the_release_ships_simulates(package):
    runs = simulate_all(package)
    assert len(runs) == len(package.assurance_manifest.scenarios) + len(
        package.assurance_manifest.replay_cases
    )
    assert len({r.run_digest for r in runs}) == len(runs)


# -- it observes; it never decides ---------------------------------------------


def test_an_authority_requirement_is_observed_not_resolved(package):
    run = simulate(package, _scenario(FACTS))
    authority = [o for o in run.trace if o.node_kind == "AUTHORITY_CHECK"]
    assert authority, "the reference workflow must exercise an authority check"
    for observation in authority:
        assert observation.outcome is NodeOutcome.REQUIREMENT_OBSERVED
        assert observation.observed_requirements
        # Requirements are described, never granted.
        assert all("requires" in r or "states a requirement" in r
                   for r in observation.observed_requirements)


def test_continuing_past_a_requirement_is_stated_not_assumed(package):
    run = simulate(package, _scenario(FACTS))
    assert run.conditional_on_requirements
    # Everything downstream is conditional on those, and the run says so.
    for requirement in run.conditional_on_requirements:
        assert requirement in run.reason_codes


def test_audit_events_are_described_not_emitted(package):
    run = simulate(package, _scenario(FACTS))
    for observation in run.trace:
        assert isinstance(observation.described_audit_events, tuple)
    assert set(run.described_audit_events) >= {
        e for o in run.trace for e in o.described_audit_events
    }


def test_a_run_carries_no_field_that_could_grant_anything():
    forbidden = ("grant", "approval_record", "clearance", "token", "credential",
                 "authorization", "signature")
    fields = set(SimulationRun.model_fields)
    assert not any(any(word in f for word in forbidden) for f in fields), fields


def test_an_unmodelled_constraint_is_not_a_failure(package):
    # Treating "I cannot evaluate this" as "this failed" would deny every workflow
    # using a membership or once-only constraint — a fabricated answer dressed as a
    # conservative one.
    run = simulate(package, _scenario(FACTS))
    kinds = {o.outcome for o in run.trace if o.node_kind == "ACTION_CONSTRAINT"}
    assert NodeOutcome.NOT_EVALUABLE in kinds


# -- the oracle (ruling P3C-2) -------------------------------------------------


def test_a_contradicted_oracle_is_a_field_on_the_run(package):
    run = simulate(package, _scenario(FACTS))
    assert run.oracle.expected_terminal_state == "ADVANCE_AUTHORIZED"
    assert run.oracle.observed_terminal_state == run.terminal_state
    # A disagreement is recorded, not raised, and not a validation diagnostic.
    assert isinstance(run.oracle.agrees, bool)


def test_the_oracle_agrees_when_the_observation_matches(package):
    run = simulate(package, _scenario(FACTS))
    matching = _scenario(FACTS)
    matching = matching.model_copy(
        update={"expected_outcome": ExpectedOutcome(terminal_state=run.terminal_state)}
    )
    assert simulate(package, matching).oracle.agrees is True


# -- the four boundary rules, by AST -------------------------------------------


def _trees():
    return [(m.name, ast.parse(m.read_text())) for m in sorted(SRC.glob("*.py"))]


def test_no_io_surface():
    banned_modules = {"os", "io", "socket", "urllib", "requests", "secrets",
                      "random", "time", "datetime", "pathlib", "subprocess"}
    banned_calls = {"open", "now", "utcnow", "urandom", "getenv", "system"}
    offenders = []
    for name, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in banned_modules:
                        offenders.append(f"{name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".")[0] in banned_modules:
                    offenders.append(f"{name}: from {node.module}")
            elif isinstance(node, ast.Call):
                called = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if called in banned_calls:
                    offenders.append(f"{name}: {called}()")
    assert offenders == [], offenders


def test_no_provider_import():
    banned = ("ugence_tap_provider", "ugence_decision_authority", "ugence_actiongate",
              "ugence_action_clearance", "ugence_policy_authority")
    for name, _tree in _trees():
        text = (SRC / name).read_text()
        assert not any(b in text for b in banned), name


def test_no_port_through_which_a_provider_could_be_supplied():
    # A port is the seam through which a simulator becomes a runtime.
    for name, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = {getattr(b, "id", "") or getattr(b, "attr", "") for b in node.bases}
                assert not ({"Protocol", "ABC", "ABCMeta"} & bases), f"{name}:{node.name}"


def test_simulation_gates_nothing(package):
    # Ruling P3C-1: no compiler entry point accepts a simulation result.
    import inspect

    for func in (api.compile_policy_pack, api.validate_policy_pack,
                 api.validate_compiled_release):
        signature = inspect.signature(func)
        assert not any(
            "simulat" in parameter.lower() for parameter in signature.parameters
        ), func.__name__


# -- nothing moves -------------------------------------------------------------


def test_simulation_moves_no_digest():
    pack = build_procurement_policy_pack()
    approval = build_procurement_approval_fixture(pack)
    assert api.compile_policy_pack(pack, approval).logical_digest == PINNED_V1_RELEASE_DIGEST
    assert compile_workflow_v2(pack, approval).workflow_fingerprint == PINNED_V2_FINGERPRINT


def test_maturity_reports_p3c():
    info = api.version_info().to_dict()
    assert info["offline_simulation_implemented"] is True
    assert info["deterministic_replay_of_simulation_verified"] is True
    for never in ("simulation_grants_authorization", "runtime_deployment_implemented",
                  "runtime_execution_implemented", "action_authorization_implemented"):
        assert info[never] is False, never
