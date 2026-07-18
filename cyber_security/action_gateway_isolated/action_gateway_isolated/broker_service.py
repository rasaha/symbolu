"""Broker / execution service — runs in the privileged domain (broker user).

Listens on mTLS TCP. Only a client presenting the gateway certificate (CN=gateway)
may call. Holds the admin Kubernetes credential (broker-only copy) and the durable
stores; exposes state/dry-run (reads) and execute (the sole mutation path). Never
returns a bearer credential.
"""

from __future__ import annotations

import os
import sys

from . import bootstrap, layout, rpc
from .broker_core import BrokerError

# N10: the broker authenticates the gateway by its certificate SAN, never the CN.
_GATEWAY_SAN = (f"DNS:gateway", f"URI:{layout.GATEWAY_SPIFFE}")


def _admin_client():
    from action_gateway_k8s.cluster import AdminKubeClient
    ca = os.environ.get("AGW_BROKER_CA", str(layout.KUBECONFIG.parent / "pki" / "ca.crt"))
    cert = os.environ.get("AGW_BROKER_ADMIN_CERT", str(layout.KUBECONFIG.parent / "pki" / "admin.crt"))
    key = os.environ.get("AGW_BROKER_ADMIN_KEY", str(layout.KUBECONFIG.parent / "pki" / "admin.key"))
    server = "https://127.0.0.1:6443"
    return AdminKubeClient(server, ca, client_cert=cert, client_key=key), server, ca


def build_core():
    from action_gateway.clock import RealClock
    admin, server, ca = _admin_client()
    return bootstrap.make_broker_core(admin, RealClock(), server=server, ca_cert=ca)


def make_handler(core):
    def handler(req):
        # transport identity: only a cert carrying the gateway SAN may drive the broker
        if not rpc.peer_has_identity(req.get("_peer_san"), *_GATEWAY_SAN):
            return {"error": "E_TLS_IDENTITY", "peer": req.get("_peer_san")}
        method = req.get("method")
        a = req.get("args", {})
        try:
            if method == "state":
                return {"ok": True, "result": core.state(a["namespace"], a["kind"], a["name"])}
            if method == "dry_run":
                return {"ok": True, "result": core.dry_run(a["namespace"], a["kind"], a["name"],
                                                           a.get("manifest"), a["verb"])}
            if method == "backup_exists":
                return {"ok": True, "result": core.backup_exists(a["ref"])}
            if method == "execute":
                return {"ok": True, "result": core.execute(a["authz"])}
            if method == "verify_audit":
                return {"ok": True, "result": core.verify_audit()}
            if method == "reconcile":
                return {"ok": True, "result": core.reconcile()}
            if method == "detect_divergence":
                return {"ok": True, "result": core.detect_divergence()}
            return {"error": "E_UNKNOWN_METHOD"}
        except BrokerError as e:
            return {"error": e.code, "message": str(e)}
        except Exception as e:  # noqa: BLE001
            return {"error": "E_BROKER", "message": str(e)}
    return handler


def main():  # pragma: no cover - long-running service
    core = build_core()
    ctx = rpc.mtls_server_ctx(str(layout.CA_CERT), str(layout.BROKER_CERT), str(layout.BROKER_KEY))
    sys.stderr.write(f"[broker] listening mTLS on {layout.BROKER_HOST}:{layout.BROKER_PORT}\n")
    sys.stderr.flush()
    rpc.serve_mtls(layout.BROKER_HOST, layout.BROKER_PORT, ctx, make_handler(core))


if __name__ == "__main__":
    main()
