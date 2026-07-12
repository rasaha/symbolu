"""Runtime layout: protection domains, key custody, sockets, and paths.

Nothing here is committed; the deployment materializes it under RUNTIME_DIR with
strict per-user ownership and permissions. The custody table is the security-
critical part: which Unix user may read which private key / credential.
"""

from __future__ import annotations

import os
from pathlib import Path

RUNTIME_DIR = Path(os.environ.get("AGW_ISO_RUN", "/tmp/agw-iso"))

# --- protection domains (separate Unix users) ---
AGENT_USER = "agentu"
GATEWAY_USER = "gwu"
BROKER_USER = "brokeru"

# --- key material (Ed25519). Private keys live only in their owning domain. ---
KEYS_DIR = RUNTIME_DIR / "keys"          # public keys world-readable; privates 0600
PUB_DIR = RUNTIME_DIR / "pub"            # verifier keyring: PUBLIC keys ONLY

# custody: purpose -> (owning user, may the gateway hold it?, may the broker hold it?)
KEY_CUSTODY = {
    "policy_root": {"private_owner": "root", "gateway": False, "broker": False},
    "gateway": {"private_owner": GATEWAY_USER, "gateway": True, "broker": False},
    "approver:security-lead": {"private_owner": "root", "gateway": False, "broker": False},
    "approver:sre-lead": {"private_owner": "root", "gateway": False, "broker": False},
    "checkpoint": {"private_owner": "root", "gateway": False, "broker": False},
}

# --- transport ---
SOCK_DIR = RUNTIME_DIR / "sock"
GATEWAY_SOCK = SOCK_DIR / "gateway.sock"       # agent -> gateway (Unix socket)
BROKER_HOST = "127.0.0.1"
BROKER_PORT = 8443                            # gateway -> broker (mTLS TCP)

# --- mTLS PKI ---
TLS_DIR = RUNTIME_DIR / "tls"
CA_CERT = TLS_DIR / "ca.crt"
BROKER_CERT = TLS_DIR / "broker.crt"
BROKER_KEY = TLS_DIR / "broker.key"           # owned by broker user
GATEWAY_CERT = TLS_DIR / "gateway.crt"
GATEWAY_KEY = TLS_DIR / "gateway.key"         # owned by gateway user

# --- durable stores (broker domain; agent/gateway cannot read) ---
DB_DIR = RUNTIME_DIR / "db"
REPLAY_DB = DB_DIR / "replay.sqlite"
AUDIT_DB = DB_DIR / "audit.sqlite"

# --- kubeconfig: broker domain ONLY ---
KUBECONFIG = Path(os.environ.get("K8S_REF_RUN", "/tmp/k8sref")) / "admin.kubeconfig"

GATEWAY_SPIFFE = "spiffe://agw.local/gateway"
BROKER_SPIFFE = "spiffe://agw.local/broker"
AGENT_SPIFFE = "spiffe://agw.local/agent"

PROTECTED_NS = "protected"


def priv_key_path(purpose: str) -> Path:
    return KEYS_DIR / f"{purpose.replace(':', '__')}.sk"


def pub_key_path(purpose: str) -> Path:
    return PUB_DIR / f"{purpose.replace(':', '__')}.pub"
