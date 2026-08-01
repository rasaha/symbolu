"""Tests for the ActionGate policy schema library: schemas are well-formed, all
cross-file $refs resolve, the worked example validates in both the flat and
seven-artifact package forms, and the schema rejects the classic authoring errors
(missing control, forbidden decision, absence=ALLOW, bad version, extra property).
"""

from __future__ import annotations

import copy
import json
import os

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
sys.path.insert(0, HERE)

import validate as V  # noqa: E402

REG = V.load_registry(HERE)
MASTER = REG["actiongate_policy.schema.json"]
EX_PATH = os.path.join(HERE, "examples", "prod_database_delete.policy.json")
PKG_PATH = os.path.join(HERE, "examples", "prod_database_delete.package.json")


def _policy():
    with open(EX_PATH) as fh:
        return json.load(fh)


def _errs(instance, schema=MASTER):
    return V.validate(instance, schema, REG, schema)


# --- schema library integrity ---------------------------------------------
def test_all_schema_files_are_valid_json_with_meta():
    assert REG, "no schema files loaded"
    for name, schema in REG.items():
        assert schema.get("$schema", "").endswith("2020-12/schema"), name
        assert schema.get("$id"), name
        assert schema.get("title"), name


def test_all_cross_file_refs_resolve():
    def walk(node, doc):
        if isinstance(node, dict):
            if "$ref" in node:
                target, _ = V._resolve(node["$ref"], doc, REG)
                assert target is not None
            for v in node.values():
                walk(v, doc)
        elif isinstance(node, list):
            for v in node:
                walk(v, doc)
    for schema in REG.values():
        walk(schema, schema)


def test_seven_package_artifacts_present():
    pkg = REG["policy_package.schema.json"]
    assert set(pkg["required"]) == {
        "canonical_action_schema", "authority_policy", "evidence_policy",
        "story_policy", "consequence_policy", "operational_clearance_policy",
        "audit_reconciliation_policy"}


# --- the worked example ----------------------------------------------------
def test_example_valid_flat_form():
    assert _errs(_policy()) == []


def test_example_valid_package_form():
    with open(PKG_PATH) as fh:
        pkg = json.load(fh)
    assert V.validate(pkg, REG["policy_package.schema.json"], REG,
                      REG["policy_package.schema.json"]) == []


def test_flat_and_package_carry_identical_content():
    p = _policy()
    with open(PKG_PATH) as fh:
        pkg = json.load(fh)
    assert pkg["authority_policy"]["authority"] == p["authority"]
    assert pkg["audit_reconciliation_policy"]["audit"] == p["audit"]


# --- the schema must reject classic authoring mistakes ---------------------
def test_missing_required_control_rejected():
    b = _policy(); del b["failure_behavior"]
    assert _errs(b)


def test_forbidden_decision_value_rejected():
    b = _policy(); b["consequences"]["hard_prohibition"]["decision"] = "ALLOW_ANYWAY"
    assert _errs(b)


def test_absence_behavior_cannot_be_allow():
    # a missing required control can never mean permission (§13)
    b = _policy(); b["required_evidence"][1]["absence_behavior"] = "ALLOW"
    assert _errs(b)


def test_bad_policy_version_rejected():
    b = _policy(); b["policy_identity"]["policy_version"] = "v1"
    assert _errs(b)


def test_additional_property_rejected():
    b = _policy(); b["surprise_field"] = True
    assert _errs(b)


def test_empty_action_types_rejected():
    b = _policy(); b["scope"]["action_types"] = []
    assert _errs(b)


def test_storygraph_completion_consequence_is_constrained():
    b = _policy()
    b["sequence_context"]["completing_action_behavior"][
        "WOULD_COMPLETE_PROHIBITED_CAPABILITY"]["consequence"] = "AUTHORIZE"
    assert _errs(b)   # 'AUTHORIZE' is not a valid consequence


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("jsonschema") is None,
    reason="jsonschema not installed (optional cross-check)")
def test_jsonschema_crosscheck_when_available():
    errs = V.validate_with_jsonschema(EX_PATH)
    assert errs == []
