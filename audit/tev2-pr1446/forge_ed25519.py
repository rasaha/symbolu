"""Crafted forgeries: exercise the acceptance policy where it actually bites."""
import sys, hashlib
SRC = "/tmp/claude-0/-home-user-symbolu/d3fc5d47-2faa-523b-8b2b-984ef2d9ae2b/scratchpad/tev2head/packages/trusted-evidence-authority/src"
sys.path.insert(0, SRC)
import ugence_trusted_evidence_authority.authority.ed25519 as prm
from ugence_trusted_evidence_authority.authority.ed25519 import TrustedEvidenceVerificationKey as VK
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
import nacl.bindings as nb

Q, L = prm._Q, prm._L
def pr_v(pk,m,s):
    try: return VK(pk).verify(m,s)
    except Exception as e: return "ERR:"+type(e).__name__
def oss_v(pk,m,s):
    try: Ed25519PublicKey.from_public_bytes(pk).verify(s,m); return True
    except Exception: return False
def na_v(pk,m,s):
    try: nb.crypto_sign_open(s+m,pk); return True
    except Exception: return False

msg = b"audit forgery target"
results = []

# ---- 1. Universal forgery under the IDENTITY public key -------------------
# A = identity  =>  [k]A = identity  =>  equation reduces to [S]B = R.
# So (R=[s]B, S=s) verifies for ANY message.
s = 12345
R = prm._encode_point(prm._scalarmult(prm._B, s))
sig_id = R + s.to_bytes(32, "little")
ID_CANON = bytes.fromhex("01"+"00"*31)
ID_NONCANON = bytes.fromhex("01"+"00"*30+"80")   # y=1, x=0, x_0=1 -> RFC 8032 5.1.3 MUST fail
results.append(("forgery under CANONICAL identity pubkey", ID_CANON, msg, sig_id))
results.append(("forgery under NONCANONICAL identity pubkey (x=0,x_0=1)", ID_NONCANON, msg, sig_id))

# y = p-1, x = 0 (order-2 point). [k]A = A if k odd, identity if k even.
ORD2_CANON   = bytes.fromhex("ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f")
ORD2_NONCANON= bytes.fromhex("ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff")
# craft: need [s]B = R + [k]A. pick R = [s]B - [k]A. k depends on R -> search over parity.
def craft_ord2(pkbytes, msg):
    A = prm._decode_point(pkbytes)
    for parity in (0,1):
        # guess k parity: if even -> [k]A = identity ; if odd -> [k]A = A
        kA = prm._IDENTITY if parity==0 else A
        sB = prm._scalarmult(prm._B, s)
        # R = sB - kA
        negkA = ((-kA[0]) % Q, kA[1], kA[2], (-kA[3]) % Q)
        Rp = prm._point_add(sB, negkA)
        Rb = prm._encode_point(Rp)
        k = int.from_bytes(hashlib.sha512(Rb+pkbytes+msg).digest(), "little")
        if (k % 2) == parity:
            return Rb + s.to_bytes(32,"little")
    return None
f2 = craft_ord2(ORD2_CANON, msg)
if f2: results.append(("forgery under CANONICAL order-2 pubkey (y=p-1,x_0=0)", ORD2_CANON, msg, f2))
f2n = craft_ord2(ORD2_NONCANON, msg) if True else None
if f2n: results.append(("forgery under NONCANONICAL order-2 pubkey (x=0,x_0=1)", ORD2_NONCANON, msg, f2n))

# ---- 2. unreduced-k vs reduced-k divergence, order-8 torsion pubkey -------
ORD8 = bytes.fromhex("26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05")
T = prm._decode_point(ORD8)
def craft_torsion(pkbytes, msg, reduce_k):
    Tp = prm._decode_point(pkbytes)
    for j in range(8):   # guess j = (k or k mod L) mod 8
        jT = prm._scalarmult(Tp, j)
        sB = prm._scalarmult(prm._B, s)
        neg = ((-jT[0])%Q, jT[1], jT[2], (-jT[3])%Q)
        Rp = prm._point_add(sB, neg)
        Rb = prm._encode_point(Rp)
        k = int.from_bytes(hashlib.sha512(Rb+pkbytes+msg).digest(), "little")
        kk = (k % L) if reduce_k else k
        if kk % 8 == j:
            return Rb + s.to_bytes(32,"little")
    return None
fu = craft_torsion(ORD8, msg, reduce_k=False)
fr = craft_torsion(ORD8, msg, reduce_k=True)
if fu: results.append(("order-8 pubkey forgery crafted for UNREDUCED k (spec text)", ORD8, msg, fu))
if fr: results.append(("order-8 pubkey forgery crafted for REDUCED k (RFC ref code)", ORD8, msg, fr))
if fu and fr: print(f"[note] unreduced-craft == reduced-craft ? {fu==fr}")

print()
print(f"{'crafted case':60s} {'PR':>7s} {'OpenSSL':>8s} {'sodium':>7s}")
print("-"*88)
div=[]
for name, pk_, m_, s_ in results:
    p,o,n = pr_v(pk_,m_,s_), oss_v(pk_,m_,s_), na_v(pk_,m_,s_)
    if p is not o: div.append((name,p,o,n))
    print(f"{name:60s} {str(p):>7s} {str(o):>8s} {str(n):>7s}")
print()
print(f"PR vs OpenSSL divergences: {len(div)}")
for d in div: print("   DIVERGENCE:", d)
