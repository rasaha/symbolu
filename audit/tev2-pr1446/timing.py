"""Secret-dependence audit of the signing path — structural first, measurement second."""
import sys, time, statistics, hashlib
P="/tmp/claude-0/-home-user-symbolu/d3fc5d47-2faa-523b-8b2b-984ef2d9ae2b/scratchpad/tev2head/packages/trusted-evidence-authority"
sys.path.insert(0,P+"/src")
import ugence_trusted_evidence_authority.authority.ed25519 as m

print("=== STRUCTURAL: secret-dependent control flow ===")
print("  _scalarmult(_B, a)   a = pruned secret scalar  -> `if e & 1` branch per bit  [SECRET-DEPENDENT BRANCH]")
print("  _scalarmult(_B, r)   r = secret nonce, UNREDUCED (~512-bit) ->")
print("                       `while e > 0` loop count == bitlength(r)  [SECRET-DEPENDENT LOOP COUNT]")
print("  s = (r + k*a) % L    CPython bigint mul/mod, operand-size dependent  [SECRET-DEPENDENT]")

# demonstrate the loop-count leak: bitlength(r) varies with the secret nonce
counts=[]
for i in range(2000):
    seed = hashlib.sha256(i.to_bytes(4,"big")).digest()
    h = m._sha512(seed)
    r = int.from_bytes(m._sha512(h[32:64] + b"msg"), "little")
    counts.append(r.bit_length())
print(f"\n  observed bitlength(r) over 2000 secrets: min={min(counts)} max={max(counts)} "
      f"spread={max(counts)-min(counts)} distinct={len(set(counts))}")
print(f"  => point-addition count in the nonce scalarmult varies by up to "
      f"{max(counts)-min(counts)} doublings across secrets")

print("\n=== MEASUREMENT (indicative only; noise does NOT prove constant time) ===")
# pick two seeds whose nonce bitlength differs a lot, same message
cand={}
for i in range(5000):
    seed = hashlib.sha256(i.to_bytes(4,"big")).digest()
    h=m._sha512(seed); r=int.from_bytes(m._sha512(h[32:64]+b"msg"),"little")
    cand.setdefault(r.bit_length(), seed)
lo=min(cand); hi=max(cand)
def bench(seed,n=60):
    k=m.TrustedEvidenceSigningKey(seed); ts=[]
    for _ in range(n):
        t=time.perf_counter(); k.sign(b"msg"); ts.append(time.perf_counter()-t)
    return statistics.median(ts)
a=bench(cand[lo]); b=bench(cand[hi])
print(f"  nonce bitlength {lo}: median {a*1000:.3f} ms")
print(f"  nonce bitlength {hi}: median {b*1000:.3f} ms")
print(f"  median delta: {(b-a)*1000:.3f} ms  ({(b/a-1)*100:+.1f}%)")

print("\n=== key-material escape surface ===")
k=m.TrustedEvidenceSigningKey(bytes(range(32)))
print("  repr:", repr(k))
print("  str :", str(k))
import copy, pickle
print("  seed reachable via attribute .seed:", hasattr(k,"seed"), "->", k.seed[:4].hex()+"...")
print("  copy.deepcopy preserves seed:", copy.deepcopy(k).seed == k.seed)
try:
    print("  pickle round-trip preserves seed:", pickle.loads(pickle.dumps(k)).seed == k.seed)
except Exception as e: print("  pickle:", type(e).__name__)
try:
    k.sign("not bytes")
except Exception as e:
    print("  exception text on bad input leaks seed:", bytes(range(32)).hex() in str(e))
import dataclasses
print("  dataclasses.asdict exposes seed:", dataclasses.asdict(k)["seed"][:4].hex()+"...")
