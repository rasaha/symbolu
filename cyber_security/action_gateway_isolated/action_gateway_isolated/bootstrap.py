"""Key generation, policy signing, and core factories (shared by services + tests).

Keys are written once with strict layout: private keys under ``keys/`` (each meant
to be chmod/chown-ed to its owning domain by the deploy script) and PUBLIC keys
under ``pub/`` (the verifier keyring). The Ed25519-signed policy identity is what
the broker independently trusts.
"""

from __future__ import annotations

from pathlib import Path

from . import crypto, layout
from .broker_core import BrokerCore
from .gateway_core import GatewayCore

POLICY_DOC = {"name": "isolated-k8s", "version": "1.0.0",
              "allowed_namespaces": ["protected"],
              "checks": ["namespace_scope", "cluster_scope_rbac", "wildcard_rbac",
                         "dangerous_verb", "powerful_rolebinding", "host_namespaces",
                         "host_path", "secret_mount", "secret_env", "privileged",
                         "image_provenance", "public_service", "protected_resource"],
              "destructive_requires": ["dual_control_ed25519", "verified_rollback",
                                       "server_dry_run"]}


def policy_identity():
    ph = crypto.digest_hex(POLICY_DOC)
    return ph, f"1.0.0+ed25519:{ph[:16]}"


def generate_keys(force=False):
    layout.KEYS_DIR.mkdir(parents=True, exist_ok=True)
    layout.PUB_DIR.mkdir(parents=True, exist_ok=True)
    for purpose in crypto.PURPOSES:
        priv = layout.priv_key_path(purpose)
        pub = layout.pub_key_path(purpose)
        if priv.exists() and not force:
            continue
        sk, vk = crypto.generate_keypair()
        priv.write_bytes(sk.to_pem(format="pkcs8"))  # Ed25519 requires PKCS#8
        pub.write_bytes(vk.to_pem())
    return list(crypto.PURPOSES)


def public_keyring():
    return crypto.PublicKeyring(str(layout.PUB_DIR))


def load_private(purpose):
    return crypto.load_private(str(layout.priv_key_path(purpose)))


def make_broker_core(admin, clock, *, server, ca_cert):
    ph, _ = policy_identity()
    return BrokerCore(admin_client=admin, keyring=public_keyring(), active_policy_hash=ph,
                      replay_db=str(layout.REPLAY_DB), audit_db=str(layout.AUDIT_DB),
                      server=server, ca_cert=ca_cert, clock=clock,
                      gateway_identity=layout.GATEWAY_SPIFFE)


def make_gateway_core(broker, clock):
    ph, pv = policy_identity()
    return GatewayCore(gateway_sk=load_private("gateway"), keyring=public_keyring(),
                       broker=broker, clock=clock, policy_hash=ph, policy_version=pv,
                       gateway_identity=layout.GATEWAY_SPIFFE)


def build_approval(purpose, *, action_hash, policy_hash, clock, nonce):
    from . import authz
    return authz.build_approval(purpose, load_private(purpose), action_hash=action_hash,
                                policy_hash=policy_hash, issued_at=clock.now(),
                                expiry=clock.plus(3600), nonce=nonce)
