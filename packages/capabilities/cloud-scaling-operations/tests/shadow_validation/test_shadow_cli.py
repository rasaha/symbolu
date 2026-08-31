"""Shadow CLI: every command is non-mutating and clearly fake-labelled."""
from __future__ import annotations

import io
import json
import tempfile
from contextlib import redirect_stdout, redirect_stderr

from shadow_validation import cli


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli.main(argv)
    return rc, out.getvalue(), err.getvalue()


def test_validate_config_default_fixture():
    rc, out, _ = _run(["validate-config"])
    assert rc == 0 and json.loads(out)["valid"] is True


def test_inspect_harness_reports_no_real_access():
    rc, out, _ = _run(["inspect-harness"])
    d = json.loads(out)
    assert rc == 0 and d["real_cluster_accessed"] is False
    assert "POST" in d["blocked_methods"] and "GET" in d["allowed_methods"]


def test_mutation_canaries_command_all_blocked():
    rc, out, _ = _run(["mutation-canaries"])
    assert rc == 0 and json.loads(out)["all_blocked"] is True


def test_source_scan_clean():
    rc, out, _ = _run(["source-scan"])
    assert rc == 0 and json.loads(out)["clean"] is True


def test_evidence_schema_lists_and_loads():
    rc, out, _ = _run(["evidence-schema"])
    assert rc == 0 and len(json.loads(out)["schemas"]) == 11
    rc, out, _ = _run(["evidence-schema", "--name", "shadow_decision"])
    assert rc == 0 and json.loads(out)["title"] == "ShadowDecision"


def test_run_fixture_then_verify_fixture():
    d = tempfile.mkdtemp(prefix="shadow-cli-")
    rc, out, err = _run(["run-fixture", "--out", d])
    assert rc == 0, err
    assert "NO REAL CLUSTER ACCESSED" in err
    agg = json.loads(out)
    assert agg["verdict"].endswith("FIXTURE_OK")
    rc, out, _ = _run(["verify-fixture", "--dir", d])
    assert rc == 0 and json.loads(out)["ok"] is True
