"""The CLI and the three output files (CV-1, CV-3)."""
from __future__ import annotations

import io
import json
import os
from contextlib import redirect_stdout

import pytest

from conftest import FIXTURES
from ugence_workflow_converters.api import OUTPUT_FILES, convert, write_outputs
from ugence_workflow_converters.cli import main


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, json.loads(buf.getvalue())


def test_convert_writes_exactly_three_files_and_nothing_else(tmp_path):
    out = tmp_path / "out"
    code, summary = _run(["convert", "n8n", os.path.join(FIXTURES, "order_review.n8n.json"), "--out", str(out)])
    assert code == 0
    assert summary["refused"] is False
    assert summary["conversion_state"] == "PARTIAL"
    assert summary["pack_status"] == "DRAFT"
    assert summary["preview"] == "PREVIEW_UNAPPROVED"
    assert sorted(os.listdir(out)) == sorted(OUTPUT_FILES.values())
    report = json.loads((out / OUTPUT_FILES["report"]).read_text())
    assert report["schema"] == "ugence.workflow-converters.conversion-report.v1"
    assert report["report_digest"] == summary["report_digest"]
    pack = json.loads((out / OUTPUT_FILES["pack"]).read_text())
    assert pack["status"] == "DRAFT" and pack["pack_id"] == summary["pack_id"]
    preview = json.loads((out / OUTPUT_FILES["preview"]).read_text())
    assert preview["preview"]["pack_id"] == pack["pack_id"]
    assert preview["structural_digest"] == report["preview"]["preview_digest"]


def test_no_preview_writes_two_files(tmp_path):
    out = tmp_path / "out"
    code, summary = _run(["convert", "n8n", os.path.join(FIXTURES, "order_review.n8n.json"), "--out", str(out), "--no-preview"])
    assert code == 0 and summary["preview"] is None
    assert sorted(os.listdir(out)) == sorted([OUTPUT_FILES["pack"], OUTPUT_FILES["report"]])


def test_a_refusal_exits_two_and_writes_nothing(tmp_path):
    out = tmp_path / "out"
    code, summary = _run(["convert", "n8n", os.path.join(FIXTURES, "embedded_secret.n8n.json"), "--out", str(out)])
    assert code == 2
    assert summary == {"refused": True, "code": "EMBEDDED_SECRET", "message": summary["message"], "written": []}
    assert not out.exists()


def test_version_and_formats():
    code, info = _run(["version"])
    assert code == 0 and info["distribution_name"] == "ugence-workflow-converters"
    code, formats = _run(["formats"])
    assert code == 0
    assert formats["implemented"] == ["n8n", "bpmn-2.0"] and formats["next"] is None
    assert set(formats["deferred"]) == {"langgraph", "crewai", "autogen"}


def test_written_files_are_byte_stable_across_runs(tmp_path):
    outcome = convert("n8n", open(os.path.join(FIXTURES, "order_review.n8n.json"), "rb").read())
    first = write_outputs(outcome, str(tmp_path / "a"))
    second = write_outputs(outcome, str(tmp_path / "b"))
    for a, b in zip(first, second):
        assert open(a, "rb").read() == open(b, "rb").read()
    assert all(text.endswith("\n") for text in (open(p, encoding="utf-8").read() for p in first))


@pytest.mark.parametrize("argv", [["convert"], ["convert", "n8n"], ["nope"]])
def test_usage_errors_exit_nonzero(argv):
    with pytest.raises(SystemExit) as excinfo:
        main(argv)
    assert excinfo.value.code != 0


def test_bpmn_convert_writes_the_same_three_files(tmp_path):
    out = tmp_path / "out"
    code, summary = _run(["convert", "bpmn-2.0", os.path.join(FIXTURES, "purchase_approval.bpmn"), "--out", str(out)])
    assert code == 0 and summary["pack_status"] == "DRAFT" and summary["preview"] == "PREVIEW_UNAPPROVED"
    assert sorted(os.listdir(out)) == sorted(OUTPUT_FILES.values())
    report = json.loads((out / OUTPUT_FILES["report"]).read_text())
    assert report["source"]["format"] == "bpmn-2.0"
    assert report["converter"]["name"] == "bpmn-2.0"


def test_a_doctype_is_refused_before_parsing_and_writes_nothing(tmp_path):
    out = tmp_path / "out"
    code, summary = _run(["convert", "bpmn-2.0", os.path.join(FIXTURES, "doctype.bpmn"), "--out", str(out)])
    assert code == 2 and summary["code"] == "NOT_AN_EXPORT_OF_THIS_FORMAT"
    assert not out.exists()
