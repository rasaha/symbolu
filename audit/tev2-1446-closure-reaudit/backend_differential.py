"""Independent re-audit of closure finding F-02 against the MERGED head.

The package's own backend (authority/backend.py) signs and verifies with
`cryptography` (OpenSSL) and validates points with PyNaCl (libsodium). A
differential check that only compares the package against `cryptography`
proves nothing about `cryptography` itself — it is the same library the
package calls. This probe differentials against `nacl.signing`, a genuinely
separate Ed25519 implementation (libsodium, not OpenSSL) that neither
`backend.py` nor its own point-validation call uses for signing.

Run: python audit/tev2-1446-closure-reaudit/backend_differential.py <repo-root>
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "packages/trusted-evidence-authority/src"))

from ugence_trusted_evidence_authority.authority.backend import (
    TrustedEvidenceSigningKey, TrustedEvidenceVerificationKey, require_valid_ed25519_point)

import nacl.signing as nsign
import nacl.bindings as nb
import nacl.exceptions


def pkg_pub(seed):
    return TrustedEvidenceSigningKey(seed).verification_key.public_key_bytes


def pkg_sign(seed, msg):
    return TrustedEvidenceSigningKey(seed).sign(msg)


def pkg_verify(pk, msg, sig):
    try:
        return TrustedEvidenceVerificationKey(pk).verify(msg, sig)
    except Exception as e:
        return "EXC:" + type(e).__name__


def nacl_pub(seed):
    return bytes(nsign.SigningKey(seed).verify_key)


def nacl_sign(seed, msg):
    return nsign.SigningKey(seed).sign(msg).signature


def nacl_verify(pk, msg, sig):
    try:
        nb.crypto_sign_open(sig + msg, pk)
        return True
    except Exception:
        return False


rnd = random.Random(0x746576325F636C6F73757265)  # "tev2_closure" seed
seeds = [bytes([i]) * 32 for i in range(8)]
seeds += [rnd.randbytes(32) for _ in range(60)]
seeds += [b"\x00" * 32, b"\xff" * 32, bytes(range(32))]

msgs = [b"", b"\x00", b"a", b"\x00" * 32, bytes(range(256)),
        b"\xff" * 1, b"\xff" * 63, b"\xff" * 64, b"\xff" * 65,
        b"x" * 127, b"x" * 128, b"x" * 129, b"x" * 1023, b"x" * 4096,
        bytes(range(256)) * 40]
msgs += [rnd.randbytes(n) for n in (1, 2, 3, 7, 15, 16, 17, 31, 32, 33, 63, 64, 65, 100, 255, 256, 257, 1000, 5000)]

print(f"corpus: {len(seeds)} keys x {len(msgs)} messages = {len(seeds) * len(msgs)} sign/verify triples")

fails = []
n_sign = 0
for seed in seeds:
    p_pk, n_pk = pkg_pub(seed), nacl_pub(seed)
    if p_pk != n_pk:
        fails.append(("PUBKEY_MISMATCH", seed.hex()[:16], p_pk.hex(), n_pk.hex()))
    for m in msgs:
        n_sign += 1
        ps, ns = pkg_sign(seed, m), nacl_sign(seed, m)
        if ps != ns:
            fails.append(("SIG_MISMATCH", seed.hex()[:16], len(m)))
        if pkg_verify(p_pk, m, ns) is not True:
            fails.append(("NACL_SIG_REJECTED_BY_PKG", seed.hex()[:16], len(m)))
        if not nacl_verify(n_pk, m, ps):
            fails.append(("PKG_SIG_REJECTED_BY_NACL", seed.hex()[:16], len(m)))

print(f"cross-implementation agreement failures: {len(fails)}")
for f in fails[:20]:
    print("  ", f)

print()
print("=== point-validation cross-check: package's require_valid_ed25519_point ===")
print("=== vs nacl.bindings.crypto_core_ed25519_is_valid_point directly     ===")
# The package's own require_valid_ed25519_point *is* the libsodium call, so this
# checks it is wired correctly (no accidental "always True"/inverted logic)
# rather than differentialing two independent validators — noted as such.
candidates = [
    bytes.fromhex("01" + "00" * 31),                       # identity
    bytes.fromhex("01" + "00" * 30 + "80"),                 # identity, noncanonical
    bytes.fromhex("ec" + "ff" * 30 + "7f"),                 # order-2
    bytes(range(32)),                                       # off-curve/garbage
] + [nacl_pub(rnd.randbytes(32)) for _ in range(20)]        # genuine valid points

wiring_bugs = []
for pk in candidates:
    try:
        sodium_says_valid = nb.crypto_core_ed25519_is_valid_point(pk) is True
    except Exception:
        sodium_says_valid = False
    try:
        require_valid_ed25519_point(pk, "probe")
        pkg_says_valid = True
    except Exception:
        pkg_says_valid = False
    if sodium_says_valid != pkg_says_valid:
        wiring_bugs.append((pk.hex()[:16], sodium_says_valid, pkg_says_valid))
print(f"wiring mismatches: {len(wiring_bugs)}")
for w in wiring_bugs:
    print("  ", w)

print()
total_fail = len(fails) + len(wiring_bugs)
if total_fail:
    print(f"FAIL: {total_fail} disagreement(s) found")
    sys.exit(1)
print(f"PASS: {n_sign} sign/verify triples agree between the package (cryptography-backed) "
      "and an independent PyNaCl-backed implementation; point-validation wiring is correct "
      "(F-02 holds against the merged head, re-verified with a genuinely separate backend)")
