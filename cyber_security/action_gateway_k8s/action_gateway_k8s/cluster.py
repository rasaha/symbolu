"""Disposable local Kubernetes control-plane lifecycle + availability detection.

Wraps the ``scripts/cluster_*.sh`` provisioners (subprocess with argument lists —
never a shell string). Exposes ``is_available()`` so cluster-dependent tests skip
cleanly (never falsely pass) when no cluster is present, and a factory for an
admin ``KubeClient``.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

from .kubeclient import KubeClient

_PKG = pathlib.Path(__file__).resolve().parent
_SCRIPTS = _PKG.parent / "scripts"
RUN_DIR = pathlib.Path(os.environ.get("K8S_REF_RUN", "/tmp/k8sref"))
BIN_DIR = pathlib.Path(os.environ.get("K8S_REF_BIN", "/opt/k8s-ref/bin"))
KUBECONFIG = RUN_DIR / "admin.kubeconfig"
CA_CERT = RUN_DIR / "pki" / "ca.crt"
ADMIN_CERT = RUN_DIR / "pki" / "admin.crt"
ADMIN_KEY = RUN_DIR / "pki" / "admin.key"
SERVER = "https://127.0.0.1:6443"
PROTECTED_NS = "protected"
SANDBOX_NS = "sandbox"
CLUSTER_ID = "ref://127.0.0.1:6443"


def _run(script: str) -> str:
    res = subprocess.run(["bash", str(_SCRIPTS / script)], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"{script} failed:\n{res.stderr[-2000:]}")
    return res.stdout.strip()


def up() -> str:
    _run("cluster_up.sh")
    _run("cluster_fixtures.sh")
    return str(KUBECONFIG)


def down() -> None:
    _run("cluster_down.sh")


def is_available() -> bool:
    """True iff a real control plane is reachable AND admin PKI is present."""
    if not (CA_CERT.exists() and ADMIN_CERT.exists() and ADMIN_KEY.exists()):
        return False
    try:
        admin_client().get_healthz()
        return True
    except Exception:  # noqa: BLE001
        return False


def admin_client() -> "AdminKubeClient":
    return AdminKubeClient(SERVER, str(CA_CERT), client_cert=str(ADMIN_CERT),
                           client_key=str(ADMIN_KEY))


def status() -> dict:
    avail = is_available()
    out = {"available": avail, "server": SERVER, "protected_namespace": PROTECTED_NS,
           "kubeconfig": str(KUBECONFIG), "cluster_id": CLUSTER_ID}
    if avail:
        c = admin_client()
        try:
            cms = c.list_names("ConfigMap", PROTECTED_NS)
            out["protected_configmaps"] = cms
        except Exception:  # noqa: BLE001
            pass
    return out


class AdminKubeClient(KubeClient):
    """Admin client with a couple of convenience helpers used by the broker."""

    def get_healthz(self) -> str:
        status_code, _ = self._request("GET", "/healthz")
        return "ok"

    def list_names(self, kind: str, namespace: str) -> list:
        from .kubeclient import GVR
        out = self.list(GVR[kind], namespace)
        return [i["metadata"]["name"] for i in out.get("items", [])]
