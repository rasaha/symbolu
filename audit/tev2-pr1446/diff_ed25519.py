"""Audit-owned differential test: PR Ed25519 vs pyca/cryptography (OpenSSL) and libsodium."""
import sys, hashlib, itertools, os
SRC = "/tmp/claude-0/-home-user-symbolu/d3fc5d47-2faa-523b-8b2b-984ef2d9ae2b/scratchpad/tev2head/packages/trusted-evidence-authority/src"
sys.path.insert(0, SRC)
from ugence_trusted_evidence_authority.authority.ed25519 import (
    TrustedEvidenceSigningKey, TrustedEvidenceVerificationKey)

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey)
from cryptography.exceptions import InvalidSignature
import nacl.bindings as nb
import nacl.exceptions

def oss_pub(seed):
    return Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes_raw()
def oss_sign(seed, msg):
    return Ed25519PrivateKey.from_private_bytes(seed).sign(msg)
def oss_verify(pk, msg, sig):
    try:
        Ed25519PublicKey.from_public_bytes(pk).verify(sig, msg); return True
    except Exception:
        return False
def nacl_verify(pk, msg, sig):
    try:
        nb.crypto_sign_open(sig + msg, pk); return True
    except Exception:
        return False

def pr_pub(seed):
    return TrustedEvidenceSigningKey(seed).verification_key.public_key_bytes
def pr_sign(seed, msg):
    return TrustedEvidenceSigningKey(seed).sign(msg)
def pr_verify(pk, msg, sig):
    try:
        return TrustedEvidenceVerificationKey(pk).verify(msg, sig)
    except Exception as e:
        return "EXC:" + type(e).__name__

# ---------------------------------------------------------------- corpus
import random
rnd = random.Random(20260818)
seeds = [bytes([i])*32 for i in range(8)]
seeds += [rnd.randbytes(32) for _ in range(40)]
seeds += [b"\x00"*32, b"\xff"*32, bytes(range(32))]

msgs = [b"", b"\x00", b"a", b"\x00"*32, bytes(range(256)),
        b"\xff"*1, b"\xff"*63, b"\xff"*64, b"\xff"*65,
        b"x"*127, b"x"*128, b"x"*129, b"x"*1023, b"x"*4096,
        bytes(range(256))*40]
msgs += [rnd.randbytes(n) for n in (1,2,3,7,15,16,17,31,32,33,63,64,65,100,255,256,257,1000,5000)]

fails = []
n_sign = 0
for seed in seeds:
    p_pk, o_pk = pr_pub(seed), oss_pub(seed)
    if p_pk != o_pk:
        fails.append(("PUBKEY_MISMATCH", seed.hex(), p_pk.hex(), o_pk.hex()))
    for m in msgs:
        n_sign += 1
        ps, os_ = pr_sign(seed, m), oss_sign(seed, m)
        if ps != os_:
            fails.append(("SIG_MISMATCH", seed.hex()[:16], len(m), ps.hex(), os_.hex()))
        # cross verify both directions
        if not oss_verify(o_pk, m, ps):
            fails.append(("PR_SIG_REJECTED_BY_OPENSSL", seed.hex()[:16], len(m)))
        if pr_verify(p_pk, m, os_) is not True:
            fails.append(("OPENSSL_SIG_REJECTED_BY_PR", seed.hex()[:16], len(m)))
        if not nacl_verify(o_pk, m, ps):
            fails.append(("PR_SIG_REJECTED_BY_LIBSODIUM", seed.hex()[:16], len(m)))

print(f"corpus: {len(seeds)} keys x {len(msgs)} messages = {n_sign} sign/verify triples")
print(f"agreement failures: {len(fails)}")
for f in fails[:20]: print("  ", f)
