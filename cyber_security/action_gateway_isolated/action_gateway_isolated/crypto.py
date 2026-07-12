"""Asymmetric signing for cross-domain authorization artifacts (Ed25519).

Replaces the shared-secret HMAC scheme *for every artifact that crosses a trust
boundary*: policy-root, gateway execution-token, human-approver, and audit-
checkpoint signatures. Verifiers receive PUBLIC keys only, so verification
authority is not signing authority — the core defect the adversarial review
identified.

Primitives come from the established ``ecdsa`` library (pure-Python, no manual
cryptography), PINNED to a known-good minimum version (N8). If it is unavailable —
or too old to provide Ed25519 — the deployment must report ISOLATION_NOT_PROVEN
rather than fall back to HMAC.

N8 — TRUST ROOT PINNING
-----------------------
Verifier keyrings do not blindly trust whatever public key happens to sit in the
directory. When a trust manifest is present (``trust_manifest.json``, written once
under offline-root custody at key genesis) every loaded public key must match its
pinned SHA-256 fingerprint; a key that is unpinned or whose fingerprint differs is
refused (fail closed). Trust establishment, rotation, and failure modes are
documented in the README.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

# pin a known-good ecdsa; older releases lack Ed25519. Treat an unmet pin as
# "asymmetric unavailable" -> the mechanical verdict becomes ISOLATION_NOT_PROVEN.
TRUSTED_ECDSA_MIN = (0, 18, 0)
ECDSA_VERSION = None
try:
    import ecdsa as _ecdsa
    from ecdsa import BadSignatureError, Ed25519, SigningKey, VerifyingKey
    ECDSA_VERSION = getattr(_ecdsa, "__version__", "0")
    _parsed = tuple(int(x) for x in ECDSA_VERSION.split(".")[:3] if x.isdigit())
    ASYMMETRIC_AVAILABLE = _parsed >= TRUSTED_ECDSA_MIN
except Exception:  # pragma: no cover - environment without the lib
    ASYMMETRIC_AVAILABLE = False

TRUST_MANIFEST_NAME = "trust_manifest.json"

# distinct signing purposes — each gets its own keypair and custody
PURPOSES = ("policy_root", "gateway", "approver:security-lead", "approver:sre-lead",
            "checkpoint")


class TrustError(Exception):
    """A public key failed to match its pinned trust-manifest fingerprint."""


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


def key_fingerprint(vk) -> str:
    """Stable SHA-256 fingerprint of a public key (over canonical DER)."""
    return hashlib.sha256(vk.to_der()).hexdigest()


def write_trust_manifest(pub_dir: str, purposes) -> dict:
    """Pin the fingerprint of each purpose's public key (offline-root custody)."""
    d = Path(pub_dir)
    keys = {p: key_fingerprint(load_public(str(d / f"{_fname(p)}.pub"))) for p in purposes}
    manifest = {"version": 1, "keys": keys}
    (d / TRUST_MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def sign(sk, obj) -> str:
    """Detached signature (hex) over the canonical bytes of ``obj``."""
    return sk.sign(canonical(obj)).hex()


def verify(vk, obj, signature_hex: str) -> bool:
    try:
        return vk.verify(bytes.fromhex(signature_hex), canonical(obj))
    except (BadSignatureError, ValueError, Exception):  # noqa: BLE001
        return False


class PublicKeyring:
    """Verifier-side keyring — PUBLIC keys only. Cannot sign anything.

    If a trust manifest is present the keyring is PINNED: a public key is trusted
    only when its fingerprint matches the pinned value (N8). Without a manifest it
    operates unpinned (used by primitive unit tests, never by the deployment, which
    always writes a manifest at key genesis).
    """

    def __init__(self, pub_dir: str):
        self.dir = Path(pub_dir)
        self._cache = {}
        mpath = self.dir / TRUST_MANIFEST_NAME
        self.pinned = mpath.exists()
        self._manifest = json.loads(mpath.read_text()).get("keys", {}) if self.pinned else {}

    def public(self, purpose: str):
        if purpose not in self._cache:
            vk = load_public(str(self.dir / f"{_fname(purpose)}.pub"))
            if self.pinned:
                expect = self._manifest.get(purpose)
                if expect is None:
                    raise TrustError(f"{purpose} not pinned in trust manifest")
                if key_fingerprint(vk) != expect:
                    raise TrustError(f"{purpose} public key fingerprint mismatch")
            self._cache[purpose] = vk
        return self._cache[purpose]

    def verify(self, purpose: str, obj, signature_hex: str) -> bool:
        try:
            return verify(self.public(purpose), obj, signature_hex)
        except (FileNotFoundError, TrustError):
            return False  # fail closed: unknown/untrusted/mispinned key never verifies

    def has_private_key(self) -> bool:
        """A verifier keyring must never contain a private key file."""
        return any(p.suffix == ".sk" or p.name.endswith(".sk.pem")
                   for p in self.dir.glob("*"))


def _fname(purpose: str) -> str:
    return purpose.replace(":", "__")
