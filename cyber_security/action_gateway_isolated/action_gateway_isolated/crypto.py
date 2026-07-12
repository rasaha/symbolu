"""Asymmetric signing for cross-domain authorization artifacts (Ed25519).

Replaces the shared-secret HMAC scheme *for every artifact that crosses a trust
boundary*: policy-root, gateway execution-token, human-approver, and audit-
checkpoint signatures. Verifiers receive PUBLIC keys only, so verification
authority is not signing authority — the core defect the adversarial review
identified.

Primitives come from the established ``ecdsa`` library (pure-Python, no manual
cryptography). If it is unavailable the deployment must report
ISOLATION_NOT_PROVEN rather than fall back to HMAC.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

try:
    from ecdsa import BadSignatureError, Ed25519, SigningKey, VerifyingKey
    ASYMMETRIC_AVAILABLE = True
except Exception:  # pragma: no cover - environment without the lib
    ASYMMETRIC_AVAILABLE = False

# distinct signing purposes — each gets its own keypair and custody
PURPOSES = ("policy_root", "gateway", "approver:security-lead", "approver:sre-lead",
            "checkpoint")


def canonical(obj) -> bytes:
    """Deterministic bytes for signing (sorted keys, compact, UTF-8)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest_hex(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def generate_keypair():
    sk = SigningKey.generate(curve=Ed25519)
    return sk, sk.get_verifying_key()


def write_keypair(sk, priv_path: str, pub_path: str) -> None:
    Path(priv_path).write_bytes(sk.to_pem(format="pkcs8"))  # Ed25519 requires PKCS#8
    Path(pub_path).write_bytes(sk.get_verifying_key().to_pem())


def load_private(priv_path: str):
    return SigningKey.from_pem(Path(priv_path).read_bytes())


def load_public(pub_path: str):
    return VerifyingKey.from_pem(Path(pub_path).read_bytes())


def sign(sk, obj) -> str:
    """Detached signature (hex) over the canonical bytes of ``obj``."""
    return sk.sign(canonical(obj)).hex()


def verify(vk, obj, signature_hex: str) -> bool:
    try:
        return vk.verify(bytes.fromhex(signature_hex), canonical(obj))
    except (BadSignatureError, ValueError, Exception):  # noqa: BLE001
        return False


class PublicKeyring:
    """Verifier-side keyring — PUBLIC keys only. Cannot sign anything."""

    def __init__(self, pub_dir: str):
        self.dir = Path(pub_dir)
        self._cache = {}

    def public(self, purpose: str):
        if purpose not in self._cache:
            self._cache[purpose] = load_public(str(self.dir / f"{_fname(purpose)}.pub"))
        return self._cache[purpose]

    def verify(self, purpose: str, obj, signature_hex: str) -> bool:
        try:
            return verify(self.public(purpose), obj, signature_hex)
        except FileNotFoundError:
            return False

    def has_private_key(self) -> bool:
        """A verifier keyring must never contain a private key file."""
        return any(p.suffix == ".sk" or p.name.endswith(".sk.pem")
                   for p in self.dir.glob("*"))


def _fname(purpose: str) -> str:
    return purpose.replace(":", "__")
