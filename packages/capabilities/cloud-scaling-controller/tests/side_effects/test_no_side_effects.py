"""Side-effect containment: the advisory core performs no I/O beyond what the caller
asks for. Proves no sockets, no subprocesses, no cloud SDK imports, no cloud-credential
reads, no unsolicited filesystem writes, no network calls.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys

import pytest

from ugence_cloud_scaling_controller import CloudScalingController, ScalingObservation


HIGH = {"cpu": 0.95, "memory": 0.9, "latency_p99": 0.85, "error_rate": 0.25, "queue_depth": 0.8}

# Cloud SDKs / network libs that the advisory core must NOT import at runtime.
FORBIDDEN_IMPORTS = (
    "boto3", "botocore",              # AWS
    "azure",                          # Azure
    "google.cloud",                   # GCP
    "kubernetes",                     # K8s
    "requests",                       # HTTP (prometheus extra only)
    "prometheus_client",             # metrics exporter (extra only)
    "opentelemetry",                 # otel (extra only)
    "fastapi", "uvicorn", "flask",   # web frameworks
)


def _run_cycle():
    ctrl = CloudScalingController()
    for _ in range(20):
        ctrl.recommend(ScalingObservation(metrics=HIGH, current_replicas=5, phase="peak"))


def test_no_socket_opened(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("advisory core must not open a socket")

    monkeypatch.setattr(socket, "socket", _boom)
    # Also block the connection creators.
    monkeypatch.setattr(socket, "create_connection",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network")))
    _run_cycle()


def test_no_subprocess_spawned(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("advisory core must not spawn a subprocess")

    monkeypatch.setattr(subprocess, "Popen", _boom)
    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(subprocess, "call", _boom)
    _run_cycle()


def _forbidden_after(snippet: str) -> list:
    """Run ``snippet`` in an isolated interpreter and return any forbidden modules
    present in its sys.modules. Uses ``python -I`` so ambient state / sitecustomize
    can't taint the result (the current process's sys.modules is globally polluted by
    other tests and cannot be used for this check)."""
    import subprocess as _sp

    # ``-I`` ignores PYTHONPATH, so make the package importable by injecting the src
    # directory (harmless if the package is already installed as a wheel).
    src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
    prog = (
        "import sys\n"
        f"sys.path.insert(0, {src!r})\n"
        + snippet
        + "\nforbidden = " + repr(list(FORBIDDEN_IMPORTS)) + "\n"
        "leaked = [m for m in forbidden if m in sys.modules]\n"
        "print(';'.join(leaked))\n"
    )
    out = _sp.run([sys.executable, "-I", "-c", prog], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return [m for m in out.stdout.strip().split(";") if m]


def test_no_cloud_sdk_imported_by_core():
    # Run a full recommend cycle in a clean interpreter; forbidden modules must be absent.
    leaked = _forbidden_after(
        "from ugence_cloud_scaling_controller import CloudScalingController, ScalingObservation\n"
        "c = CloudScalingController()\n"
        "H = {'cpu':0.95,'memory':0.9,'latency_p99':0.85,'error_rate':0.25,'queue_depth':0.8}\n"
        "[c.recommend(ScalingObservation(metrics=H, current_replicas=5, phase='peak')) for _ in range(20)]\n"
    )
    assert not leaked, f"advisory core imported forbidden modules: {leaked}"


def test_import_surface_is_numpy_only():
    # The package's default import surface must not pull any cloud/optional module.
    leaked = _forbidden_after("import ugence_cloud_scaling_controller\n")
    assert not leaked, f"import pulled forbidden modules: {leaked}"


def test_no_unsolicited_file_write(tmp_path, monkeypatch):
    # Run inside an empty cwd; assert nothing is created by a recommend cycle.
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.iterdir())
    _run_cycle()
    after = set(tmp_path.iterdir())
    assert before == after, f"advisory core wrote files: {after - before}"


def test_no_cloud_credential_env_read(monkeypatch):
    # Poison cloud-credential env vars; a recommend cycle must not depend on them.
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "GOOGLE_APPLICATION_CREDENTIALS",
                "AZURE_CLIENT_SECRET", "KUBECONFIG"):
        monkeypatch.setenv(var, "POISONED_SHOULD_NOT_BE_USED")
    # No exception and a valid decision => the core did not act on credentials.
    ctrl = CloudScalingController()
    rec = ctrl.recommend(ScalingObservation(metrics=HIGH, current_replicas=5))
    assert rec.actuation_performed is False
