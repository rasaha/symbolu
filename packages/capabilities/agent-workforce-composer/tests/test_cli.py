"""Offline CLI tests (§21)."""
from __future__ import annotations

import json

import pytest

from ugence_agent_workforce_composer import fixtures
from ugence_agent_workforce_composer.canonical import to_canonical_obj
from ugence_agent_workforce_composer.cli import main


def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(to_canonical_obj(obj)), encoding="utf-8")
    return str(p)


@pytest.fixture()
def files(tmp_path):
    wf = _write(tmp_path, "wf.json", fixtures.procurement_workflow())
    snap = fixtures.registry_snapshot()
    reg = _write(tmp_path, "reg.json", {
        "snapshot_id": snap.snapshot_id, "registry_version": snap.registry_version,
        "logical_time": snap.logical_time, "synthetic": True,
        "agent_profiles": [to_canonical_obj(p) for p in snap.agent_profiles],
        "capability_evidence": [to_canonical_obj(e) for e in snap.capability_evidence]})
    ent = _write(tmp_path, "ent.json", fixtures.enterprise_policy())
    elig = _write(tmp_path, "elig.json", fixtures.eligibility_policy())
    return wf, reg, ent, elig


def test_version(capsys):
    assert main(["version"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["contract_version"] == "awc.v1"
    assert out["production_certified"] is False


def test_validate_workflow(capsys, files):
    wf, *_ = files
    assert main(["validate-workflow", wf]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] and out["accounting_holds"]


def test_adapt_workflow(capsys, files):
    wf, *_ = files
    assert main(["adapt-workflow", wf]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["workflow_identity"] == "synthetic_procurement"


def test_validate_registry(capsys, files):
    _, reg, *_ = files
    assert main(["validate-registry", reg]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] and out["digest_matches"]


def test_validate_policy(capsys, files):
    _, _, ent, elig = files
    assert main(["validate-policy", ent, elig]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"]


def test_eligibility_and_explain_and_replay(capsys, files):
    wf, reg, ent, elig = files
    assert main(["eligibility", wf, reg, ent, elig]) == 0
    r1 = capsys.readouterr().out
    assert main(["eligibility", wf, reg, ent, elig]) == 0
    r2 = capsys.readouterr().out
    assert r1 == r2  # deterministic
    assert main(["explain", wf, reg, ent, elig]) == 0
    assert "explanations" in json.loads(capsys.readouterr().out)
    assert main(["replay", wf, reg, ent, elig]) == 0
    assert "replay_records" in json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("name", ["procurement", "support", "security"])
def test_demo(capsys, name):
    assert main(["demo", name]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["accounting_holds"] is True
    assert out["workflow_fingerprint"].startswith("sha256:")


# -- P2 CLI --

def test_rank(capsys, files):
    wf, reg, ent, elig = files
    assert main(["rank", wf, reg, ent, elig]) == 0
    out = json.loads(capsys.readouterr().out)
    assert isinstance(out, list) and out and "ranked_candidates" in out[0]


def test_compose_and_explain_and_replay(capsys, files):
    wf, reg, ent, elig = files
    assert main(["compose", wf, reg, ent, elig]) == 0
    r1 = capsys.readouterr().out
    assert main(["compose", wf, reg, ent, elig]) == 0
    assert r1 == capsys.readouterr().out          # deterministic
    plan = json.loads(r1)
    assert plan["plan_state"] == "COMPLETE" and plan["plan_fingerprint"].startswith("sha256:")
    assert main(["explain-plan", wf, reg, ent, elig]) == 0
    assert "role_explanations" in json.loads(capsys.readouterr().out)
    assert main(["replay-plan", wf, reg, ent, elig]) == 0
    assert json.loads(capsys.readouterr().out)["reproduced"] is True


def test_compare_plans(tmp_path, capsys, files):
    wf, reg, ent, elig = files
    assert main(["compose", wf, reg, ent, elig]) == 0
    plan_json = capsys.readouterr().out
    a = tmp_path / "a.json"; a.write_text(plan_json)
    b = tmp_path / "b.json"; b.write_text(plan_json)
    assert main(["compare-plans", str(a), str(b)]) == 0
    diff = json.loads(capsys.readouterr().out)
    assert diff["same_workflow"] is True and diff["assignment_changes"] == []


@pytest.mark.parametrize("name", ["procurement", "support", "security"])
def test_demo_compose(capsys, name):
    assert main(["demo", name, "--compose"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["plan_fingerprint"].startswith("sha256:")
    assert out["plan_state"] in ("COMPLETE", "NO_FEASIBLE_TEAM")
