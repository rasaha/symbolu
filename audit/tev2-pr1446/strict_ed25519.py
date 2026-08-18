"""Audit-owned strict/malformed corpus: PR vs OpenSSL vs libsodium acceptance policy."""
import sys
SRC = "/tmp/claude-0/-home-user-symbolu/d3fc5d47-2faa-523b-8b2b-984ef2d9ae2b/scratchpad/tev2head/packages/trusted-evidence-authority/src"
sys.path.insert(0, SRC)
from ugence_trusted_evidence_authority.authority.ed25519 import (
    TrustedEvidenceSigningKey, TrustedEvidenceVerificationKey)
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
import nacl.bindings as nb

Q = 2**255 - 19
L = 2**252 + 27742317777372353535851937790883648493

def pr_v(pk, m, s):
    try: return TrustedEvidenceVerificationKey(pk).verify(m, s)
    except Exception as e: return "ERR:"+type(e).__name__
def oss_v(pk, m, s):
    try:
        Ed25519PublicKey.from_public_bytes(pk).verify(s, m); return True
    except Exception as e: return False
def na_v(pk, m, s):
    try:
        nb.crypto_sign_open(s+m, pk); return True
    except Exception: return False

seed = bytes(range(32))
sk = TrustedEvidenceSigningKey(seed)
pk = sk.verification_key.public_key_bytes
msg = b"audit-message"
sig = sk.sign(msg)
assert pr_v(pk, msg, sig) is True

# canonical low-order points (the 8 points of the torsion subgroup), standard list
LOW_ORDER = [bytes.fromhex(h) for h in [
 "0100000000000000000000000000000000000000000000000000000000000000", # identity
 "ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f", # order2 (y=p-1,x=0) canonical? sign bit set
 "0000000000000000000000000000000000000000000000000000000000000000", # order4
 "0000000000000000000000000000000000000000000000000000000000000080", # order4
 "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05", # order8
 "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac03fa", # order8
 "ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff", # y=p-1 noncanon-ish
 "edffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f", # y=p  noncanonical
 "eeffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f", # y=p+1 noncanonical
]]

cases = []
def add(name, pk_, m_, s_):
    cases.append((name, pk_, m_, s_))

add("baseline valid", pk, msg, sig)
add("modified message", pk, msg+b"!", sig)
add("modified R (flip bit0)", pk, msg, bytes([sig[0]^1])+sig[1:])
add("modified S (flip bit0)", pk, msg, sig[:32]+bytes([sig[32]^1])+sig[33:])
add("modified pubkey", bytes([pk[0]^1])+pk[1:], msg, sig)
add("truncated sig (63)", pk, msg, sig[:63])
add("extended sig (65)", pk, msg, sig+b"\x00")
add("empty sig", pk, msg, b"")
s_int = int.from_bytes(sig[32:], "little")
add("S == L", pk, msg, sig[:32]+L.to_bytes(32,"little"))
add("S = s+L (malleable)", pk, msg, sig[:32]+((s_int+L)%(2**256)).to_bytes(32,"little"))
add("S = L+1", pk, msg, sig[:32]+(L+1).to_bytes(32,"little"))
add("S = 2^255 (high bit)", pk, msg, sig[:32]+(2**255).to_bytes(32,"little"))
add("S all-ff", pk, msg, sig[:32]+b"\xff"*32)
# non-canonical y >= p in R
add("R y=p (noncanonical)", pk, msg, bytes.fromhex("edffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f")+sig[32:])
add("R y=p+1", pk, msg, bytes.fromhex("eeffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f")+sig[32:])
add("pubkey y=p (noncanonical)", bytes.fromhex("edffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f"), msg, sig)
# THE non-canonical identity: y=1 with sign bit set -> x=0 & x_0=1, RFC 8032 5.1.3 says decoding MUST fail
NC_ID = bytes.fromhex("0100000000000000000000000000000000000000000000000000000000000080")
add("pubkey = noncanonical identity (y=1,x0=1)", NC_ID, msg, sig)
add("R = noncanonical identity (y=1,x0=1)", pk, msg, NC_ID+sig[32:])
NC_ORD2 = bytes.fromhex("ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f")
NC_ORD2B = bytes.fromhex("ecfffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff f".replace(" ",""))
add("pubkey y=p-1 sign0 (x=0,x0=0 canonical)", NC_ORD2, msg, sig)
add("pubkey y=p-1 sign1 (x=0,x0=1 NONCANON)", NC_ORD2B, msg, sig)
# invalid / off-curve
add("pubkey off-curve (y=2)", (2).to_bytes(32,"little"), msg, sig)
add("all-zero pubkey", b"\x00"*32, msg, sig)
add("all-ff pubkey", b"\xff"*32, msg, sig)
for i, lo in enumerate(LOW_ORDER):
    add(f"low-order pubkey[{i}]", lo, msg, sig)
    add(f"low-order R[{i}]", pk, msg, lo+sig[32:])
# zero signature
add("all-zero signature", pk, msg, b"\x00"*64)
add("R=identity,S=0", pk, msg, bytes.fromhex("01"+"00"*31)+b"\x00"*32)

print(f"{'case':46s} {'PR':>8s} {'OpenSSL':>8s} {'sodium':>8s}   verdict")
print("-"*90)
div = []
for name, pk_, m_, s_ in cases:
    p, o, n = pr_v(pk_, m_, s_), oss_v(pk_, m_, s_), na_v(pk_, m_, s_)
    mark = ""
    if p is not o: mark = " <== PR/OpenSSL DIVERGE"; div.append((name,p,o,n))
    elif p is not n: mark = " (sodium stricter)"
    print(f"{name:46s} {str(p):>8s} {str(o):>8s} {str(n):>8s}  {mark}")
print()
print(f"PR vs OpenSSL divergences: {len(div)}")
for d in div: print("  ", d)
