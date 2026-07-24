"""Foundation tests for Phases 1-4: prior-artifact guard, natural-artifact intake, corpus harvest
determinism + sufficiency, and blinded ground truth. Read-only; deterministic; non-enforcing.
"""
import ast
import os

from bounded_shadow_pilot import verify_prior_artifacts as guard
from bounded_shadow_pilot import intake_protocol as ip
from bounded_shadow_pilot import harvest
from bounded_shadow_pilot import ground_truth as gt


# ---- Phase 1: guard ------------------------------------------------------------------------------

def test_prior_artifacts_intact():
    assert guard.verify() is True
    assert len(guard.FROZEN) == 22


# ---- Phase 2: intake protocol ------------------------------------------------------------------

def test_intake_accepts_natural_doc():
    r = ip.intake_natural("This module documents the deployment rollback and monitoring runbook.",
                          "cloud_controller/x.md", "doc")
    assert r.accepted and r.use_case in ip.ELIGIBLE_USE_CASES


def test_intake_rejects_unknown_provenance():
    assert not ip.intake_natural("text", "x.md", "spreadsheet").accepted


def test_intake_rejects_excluded_use_case():
    r = ip.intake_natural("This step will revoke access and terminate employ of the user.",
                          "a.py", "comment")
    assert not r.accepted and r.reason_codes == ["INTAKE.EXCLUDED_USE_CASE"]


def test_intake_fails_closed_on_pii():
    r = ip.intake_natural("Patient ssn 123-45-6789 must be recorded here for the chart.",
                          "a.py", "docstring")
    assert not r.accepted and r.reason_codes == ["INTAKE.PROHIBITED_DATA"]


# ---- Phase 3: corpus ---------------------------------------------------------------------------

def test_corpus_sufficient_and_deterministic():
    m1 = harvest.harvest()
    m2 = harvest.harvest()
    assert m1["evidence_status"] == "SUFFICIENT"
    assert m1["count"] >= harvest.TARGET_MIN
    assert m1["corpus_sha256"] == m2["corpus_sha256"]        # byte-reproducible


def test_corpus_excludes_governance_dirs():
    m = harvest.harvest()
    for a in m["artifacts"]:
        top = a["source_path"].split(os.sep)[0]
        assert top not in harvest._EXCLUDED_ROOTS, a["source_path"]


# ---- Phase 4: ground truth ---------------------------------------------------------------------

def test_ground_truth_is_blinded():
    # the labeler must not import or invoke the runtime / orchestrator / ActionGate
    src = open(os.path.join(os.path.dirname(gt.__file__), "ground_truth.py")).read()
    tree = ast.parse(src)
    mods = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    mods += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    banned = ("orchestrat", "action_gate", "actiongate", "governed_inference")
    assert not [m for m in mods if m and any(b in m for b in banned)]


def test_ground_truth_two_class_and_deterministic():
    a = gt.build(); b = gt.build()
    assert a["ground_truth_sha256"] == b["ground_truth_sha256"]
    assert set(a["distribution_expected_class"]) <= {"ALLOW", "REVIEW"}
    assert a["count"] == harvest.harvest()["count"]
