"""The demo export refuses to write anything from a tree whose verifiers do not hold.

The export carries no boundary verifier of its own: the authority plane's verifier binds
to the worker's committed contract, and that contract stays in this repository. So the
only thing standing between an unverified tree and a published demo is this refusal, and
it is worth a test of its own.
"""

from __future__ import annotations

import importlib.util
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC = importlib.util.spec_from_file_location(
    "export_demo", os.path.join(REPO, "tools", "export_demo.py"))
export_demo = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(export_demo)

FAILING = (("a verifier that does not hold", (sys.executable, "-c", "raise SystemExit(3)")),)
PASSING = (("a verifier that holds", (sys.executable, "-c", "print('ok')")),)


def test_a_failing_verifier_refuses_the_export_and_writes_nothing(tmp_path, monkeypatch):
    out = tmp_path / "demo"
    monkeypatch.setattr(export_demo, "VERIFIERS", FAILING)

    assert export_demo.export(str(out), repo=REPO) == 1
    assert not out.exists(), "a refused export must leave no output behind"


def test_a_failing_verifier_refuses_even_when_an_output_already_exists(tmp_path, monkeypatch):
    out = tmp_path / "demo"
    out.mkdir()
    (out / "from-a-previous-export.txt").write_text("kept")
    monkeypatch.setattr(export_demo, "VERIFIERS", FAILING)

    assert export_demo.export(str(out), repo=REPO) == 1
    assert (out / "from-a-previous-export.txt").read_text() == "kept", \
        "a refused export must not clear the previous one"


def test_the_export_writes_provenance_and_a_readme_when_the_verifiers_hold(tmp_path, monkeypatch):
    out = tmp_path / "demo"
    monkeypatch.setattr(export_demo, "VERIFIERS", PASSING)

    assert export_demo.export(str(out), repo=REPO) == 0
    provenance = out / "EXPORT_PROVENANCE.json"
    assert provenance.is_file() and (out / "README.md").is_file()

    import json
    record = json.loads(provenance.read_text())
    assert record["source_repository"] == "rasaha/symbolu"
    assert record["verifiers_skipped"] is False
    assert all(entry["passed"] for entry in record["verifiers_run_in_the_source_repository"])
    assert record["file_count"] > 0


def test_the_export_carries_no_governance_record(tmp_path, monkeypatch):
    out = tmp_path / "demo"
    monkeypatch.setattr(export_demo, "VERIFIERS", PASSING)
    assert export_demo.export(str(out), repo=REPO) == 0
    assert export_demo.denied_files(str(out)) == []


@pytest.mark.parametrize("planted", [
    "apps/console/ADR_SOMETHING.md",
    "apps/console/CONTAINER_GATE_SET.json",
    "docs/audits/whatever.json",
])
def test_a_planted_governance_record_is_detected(tmp_path, planted):
    root = tmp_path / "demo"
    target = root / planted
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}")
    assert export_demo.denied_files(str(root)) == [planted]


def test_the_plane_keeps_what_it_needs_to_serve_and_loses_what_it_cannot_run(tmp_path, monkeypatch):
    """The proxy and its manifest travel; the verifier that binds to the worker does not."""
    out = tmp_path / "demo"
    monkeypatch.setattr(export_demo, "VERIFIERS", PASSING)
    assert export_demo.export(str(out), repo=REPO) == 0

    assert (out / "apps/authority-plane/server.mjs").is_file()
    assert (out / "apps/authority-plane/security/approved-operations.json").is_file()
    assert not (out / "apps/authority-plane/scripts/verify-boundary.mjs").exists()
    assert not (out / "apps/authority-plane/tests").exists()
    assert not (out / "apps/ugence-governance-studio/frontend/e2e").exists()
