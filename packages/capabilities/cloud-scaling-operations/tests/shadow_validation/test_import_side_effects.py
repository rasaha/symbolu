"""Importing any shadow-validation module has no side effects (isolated subprocess)."""
from __future__ import annotations

import json
import os
import subprocess
import sys


def _advisory_src(pkg_root: str) -> str:
    """The controller's src, located through the checkout rather than by `..` hops.

    The sibling hop only resolves inside the repository; the guard sweep runs this suite
    from a disposable copy outside it (guard-coverage ADR §7.1/§9.d — a test that counts
    directory levels measures the wrong tree the moment it is copied). `UGENCE_REPO_ROOT`
    is how the sweep tells a copy where the real checkout is; the sibling hop stays as
    the in-repo fallback.
    """

    injected = os.environ.get("UGENCE_REPO_ROOT")
    if injected:
        return os.path.join(
            injected, "packages", "capabilities", "cloud-scaling-controller", "src"
        )
    return os.path.abspath(os.path.join(pkg_root, "..", "cloud-scaling-controller", "src"))


def _probe(snippet: str) -> dict:
    here = os.path.dirname(__file__)
    pkg_root = os.path.abspath(os.path.join(here, "..", ".."))
    ops = os.path.join(pkg_root, "src")
    adv = _advisory_src(pkg_root)
    prog = (
        "import sys, json\n"
        f"sys.path.insert(0, {pkg_root!r})\n"
        f"sys.path.insert(0, {ops!r})\n"
        f"sys.path.insert(0, {adv!r})\n"
        "import socket, threading\n"
        "_orig = socket.socket\n"
        "opened = {'socket': False, 'threads_before': threading.active_count()}\n"
        "class _Tracked(_orig):\n"
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


def test_import_package_has_no_side_effects():
    res = _probe("import shadow_validation\n")
    assert res["socket"] is False
    assert res["threads_after"] == res["threads_before"]
    assert not res["forbidden_loaded"], res["forbidden_loaded"]


def test_import_every_submodule_has_no_side_effects():
    mods = ("config", "contracts", "transport", "observer", "allowlist",
            "authorization_scenarios", "stale_state", "hpa_analysis", "evidence",
            "redaction", "session", "integrity", "cli")
    snippet = "".join(f"import shadow_validation.{m}\n" for m in mods)
    res = _probe(snippet)
    assert res["socket"] is False
    assert res["threads_after"] == res["threads_before"]
    assert not res["forbidden_loaded"], res["forbidden_loaded"]
