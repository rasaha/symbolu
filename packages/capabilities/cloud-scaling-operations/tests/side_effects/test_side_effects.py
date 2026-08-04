"""Import-time side-effect containment (isolated subprocess)."""

from __future__ import annotations

import os
import subprocess
import sys


def _probe(snippet: str) -> dict:
    import json
    src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
    adv = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                       "cloud-scaling-controller", "src"))
    prog = (
        "import sys, json\n"
        f"sys.path.insert(0, {src!r})\n"
        f"sys.path.insert(0, {adv!r})\n"
        "import socket, threading\n"
        "_orig_socket = socket.socket\n"
        "opened = {'socket': False, 'threads_before': threading.active_count()}\n"
        "class _Tracked(_orig_socket):\n"
        "    def __init__(self, *a, **k):\n"
        "        opened['socket'] = True\n"
        "        super().__init__(*a, **k)\n"
        "socket.socket = _Tracked\n"
        + snippet +
        "\nopened['threads_after'] = threading.active_count()\n"
        "forbidden = ['boto3','botocore','azure','google.cloud','kubernetes',"
        "'prometheus_client','opentelemetry','yaml','requests']\n"
        "opened['forbidden_loaded'] = [m for m in forbidden if m in sys.modules]\n"
        "print(json.dumps(opened))\n"
    )
    out = subprocess.run([sys.executable, "-I", "-c", prog], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_import_has_no_side_effects():
    res = _probe("import ugence_cloud_scaling_operations\n")
    assert res["socket"] is False, "import opened a socket"
    assert res["threads_after"] == res["threads_before"], "import started a thread"
    assert not res["forbidden_loaded"], f"import loaded {res['forbidden_loaded']}"


def test_facade_construction_has_no_side_effects():
    res = _probe(
        "from ugence_cloud_scaling_operations import ControlledScalingExecutor, OperationsConfig\n"
        "ControlledScalingExecutor(OperationsConfig())\n"
    )
    assert res["socket"] is False
    assert res["threads_after"] == res["threads_before"]
    assert not res["forbidden_loaded"]


def test_dry_run_execute_writes_no_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.iterdir())
    import ops_support as support
    from ugence_cloud_scaling_operations import (
        ControlledScalingExecutor, OperationsConfig)
    ControlledScalingExecutor(OperationsConfig()).execute(support.make_request(), tenant_id="t")
    assert set(tmp_path.iterdir()) == before
