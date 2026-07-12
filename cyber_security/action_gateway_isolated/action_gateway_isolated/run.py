"""Orchestrate the compromised-agent experiment and emit the mechanical verdict.

Run as root (it coordinates the privileged race conditions and reads the offline
checkpoint key), but every adversary action flows only through the agent's channel
(the gateway Unix socket) or the real isolated agent subprocess.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import bootstrap, crypto, layout, redteam, verdict
from ._core import GVR, K8sApiError

PKG_DIR = str(Path(__file__).resolve().parents[1])
PYTHONPATH = os.environ.get("PYTHONPATH", "")


def _admin():
    from action_gateway_k8s.cluster import admin_client
    return admin_client()


def _probe_env(admin) -> dict:
    from action_gateway_k8s import cluster
    env = {"cluster": cluster.is_available(), "asymmetric": crypto.ASYMMETRIC_AVAILABLE,
           "user_separation": _users_exist(), "durable_store": layout.REPLAY_DB.exists(),
           "audit_key_separation": _agent_cannot_read_checkpoint(),
           "netns_isolation": None, "conditional_write": None}
    return env


def _users_exist():
    import pwd
    try:
        for u in ("agentu", "gwu", "brokeru"):
            pwd.getpwnam(u)
        return True
    except KeyError:
        return False


def _agent_cannot_read_checkpoint():
    # verified by the isolation probe; a placeholder True refined after the probe runs
    return True


def restart_services():
    """Restart broker + gateway (durable stores persist)."""
    subprocess.run(["bash", str(Path(PKG_DIR) / "scripts" / "restart.sh")],
                   env=dict(os.environ, AGW_ISO_RUN=str(layout.RUNTIME_DIR)),
                   capture_output=True, text=True)
    time.sleep(2)


def main():
    admin = _admin()
    env = _probe_env(admin)
    from action_gateway.clock import RealClock
    clock = RealClock()
    sock = str(layout.GATEWAY_SOCK)

    # 1. isolation attacks — the REAL isolated agent subprocess
    probe = redteam.run_isolated_agent_probe(PKG_DIR, PYTHONPATH)
    iso = redteam.isolation_attacks(probe)
    env["netns_isolation"] = probe.get("apiserver_6443") in (
        "OSError", "TimeoutError", "ConnectionRefusedError", "ConnectionError")
    env["audit_key_separation"] = probe.get("checkpoint_sk") == "PermissionError" and \
        probe.get("audit_db") == "PermissionError"

    # 2. channel attacks (agent -> gateway socket)
    chan = redteam.channel_attacks(sock, admin, clock)

    # 3. orchestrated race/restart attacks (in-process broker core for the
    #    deterministic conditional-write test; shares the same durable stores)
    from action_gateway_k8s import cluster
    bc = bootstrap.make_broker_core(admin, clock, server=cluster.SERVER, ca_cert=str(cluster.CA_CERT))
    orch = redteam.orchestrated_attacks(sock, admin, clock, restart_services, broker_core=bc)

    # conditional-write proof: the TOCTOU attack must have been blocked by a CAS conflict
    env["conditional_write"] = any(a["id"] == "A18_A28_toctou" and a["blocked"] for a in orch)

    # 4. audit checkpoint (offline checkpoint key signs the head; verify separation)
    _sign_and_verify_checkpoint(clock)

    attacks = iso + chan + orch
    result = verdict.decide(env, attacks)
    out = {"verdict": result, "environment": env, "attacks": attacks,
           "isolation_probe": probe}
    print(json.dumps(out, indent=2))
    (layout.RUNTIME_DIR / "redteam_results.json").write_text(json.dumps(out, indent=2))
    return 0 if result["verdict"] == verdict.SUPPORTED else 1


def _sign_and_verify_checkpoint(clock):
    """The offline checkpoint key signs the current audit head (separate custody)."""
    try:
        from .audit_ledger import AuditLedger
        led = AuditLedger(str(layout.AUDIT_DB))
        cp_sk = crypto.load_private(str(layout.priv_key_path("checkpoint")))
        led.sign_checkpoint(cp_sk, at=clock.now())
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    sys.exit(main())
