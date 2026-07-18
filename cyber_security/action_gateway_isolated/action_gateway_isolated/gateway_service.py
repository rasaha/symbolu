"""Gateway service — runs in the gateway domain (gwu user).

Listens on a Unix socket for the agent. Holds ONLY the gateway signing key and a
gateway mTLS client certificate. Reaches the broker over mTLS; has no Kubernetes
credential, no approver/policy/checkpoint private key. Decision + execution happen
in one gateway-side transaction; the agent never receives an authorization artifact.
"""

from __future__ import annotations

import sys

from . import bootstrap, layout, rpc


class BrokerRPCClient:
    """Implements the BrokerCore read/execute surface over mTLS (gateway identity)."""

    def __init__(self):
        self._ctx = rpc.mtls_client_ctx(str(layout.CA_CERT), str(layout.GATEWAY_CERT),
                                        str(layout.GATEWAY_KEY))

    def _call(self, method, args):
        resp = rpc.mtls_call(layout.BROKER_HOST, layout.BROKER_PORT, self._ctx,
                             {"method": method, "args": args})
        if "error" in resp:
            raise _BrokerRPCError(resp["error"], resp.get("message", ""))
        return resp["result"]

    def state(self, namespace, kind, name):
        return self._call("state", {"namespace": namespace, "kind": kind, "name": name})

    def dry_run(self, namespace, kind, name, manifest, verb):
        return self._call("dry_run", {"namespace": namespace, "kind": kind, "name": name,
                                      "manifest": manifest, "verb": verb})

    def backup_exists(self, ref):
        return self._call("backup_exists", {"ref": ref})

    def execute(self, authz_doc):
        return self._call("execute", {"authz": authz_doc})


class _BrokerRPCError(Exception):
    def __init__(self, code, message=""):
        self.code = code
        super().__init__(f"{code}: {message}")


def build_core():
    from action_gateway.clock import RealClock
    return bootstrap.make_gateway_core(BrokerRPCClient(), RealClock())


def make_handler(core):
    def handler(req):
        try:
            return core.handle(req)
        except Exception as e:  # noqa: BLE001
            return {"outcome": "DENY", "reason_codes": [getattr(e, "code", type(e).__name__)],
                    "message": str(e), "executable": False}
    return handler


def main():  # pragma: no cover - long-running service
    core = build_core()
    sys.stderr.write(f"[gateway] listening on unix://{layout.GATEWAY_SOCK}\n")
    sys.stderr.flush()
    rpc.serve_unix(str(layout.GATEWAY_SOCK), make_handler(core))


if __name__ == "__main__":
    main()
