#!/usr/bin/env python3
"""Blind conformance harness (§24).
Phase 1: expose ONLY the CandidateArtifact + ValidationRecord + descriptor envelope to
the verifier; hide expected/, derivations/, and every expected/metadata field embedded in
the corpus fixture. Enforce the blind boundary with an audit-open wrapper that records every
package path opened and hard-fails if expected/ or derivations/ is read during evaluation."""
import builtins, hashlib, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src"); sys.path.insert(0, SRC)
import verifier as V

PKG = sys.argv[1]
OUT = os.path.join(HERE, "..", "results")
os.makedirs(os.path.join(OUT, "produced"), exist_ok=True)

# ---- config fingerprint gate ----
sys.path.insert(0, HERE)
import recompute_config_fingerprint as CF
got, want = CF.recompute(PKG)
if got != want:
    print("CONFIG FINGERPRINT MISMATCH — stopping", got, want); sys.exit(2)

# ---- blind-read boundary: forbid expected/ and derivations/ during evaluation ----
_open = builtins.open
OPENED = []
BLIND = {"active": False}
def guarded_open(file, *a, **k):
    p = str(file)
    if PKG in p or p.startswith(("expected/", "derivations/")):
        OPENED.append(p)
        if BLIND["active"] and (os.sep + "expected" + os.sep in p or os.sep + "derivations" + os.sep in p):
            raise PermissionError("BLIND VIOLATION: verifier attempted to read " + p)
    return _open(file, *a, **k)
builtins.open = guarded_open

ver = V.Verifier(PKG)                                   # loads resources (allowed)
corpus_dir = os.path.join(PKG, "corpus")
manifest = json.load(_open(os.path.join(PKG, "manifest/corpus-manifest.json")))
authoritative = {}
for e in manifest["fixtures"]:
    fid = os.path.basename(e["path"])[:-5]
    authoritative[fid] = e.get("authoritative", True)

INPUT_FIELDS = ("modality", "validation_record", "artifact", "profile_ref", "release_ref")
def blind_submission(fixture_obj):
    """Strip everything except the true verifier inputs (drop expected/phenomenon/purpose/etc.)."""
    return {k: fixture_obj[k] for k in INPUT_FIELDS if k in fixture_obj}

produced = {}
timings = {}
for fn in sorted(os.listdir(corpus_dir)):
    fid = fn[:-5]
    obj = json.load(_open(os.path.join(corpus_dir, fn)))
    sub = blind_submission(obj)
    BLIND["active"] = True
    t0 = time.perf_counter()
    rec = ver.evaluate(sub)
    trace_full = ver.trace(sub, rec, redacted=False)
    trace_red = ver.trace(sub, rec, redacted=True)
    dt = time.perf_counter() - t0
    BLIND["active"] = False
    timings[fid] = dt
    out = {"fixture_id": fid, "authoritative": authoritative.get(fid, True),
           "assurance_record": rec, "trace": trace_full, "redacted_trace": trace_red}
    json.dump(out, _open(os.path.join(OUT, "produced", fid + ".json"), "w"), sort_keys=True, indent=1)
    produced[fid] = out

builtins.open = _open
# proof of blind boundary
expected_reads = [p for p in OPENED if (os.sep + "expected" + os.sep in p or os.sep + "derivations" + os.sep in p)]
proof = {"fixtures_evaluated": len(produced),
         "expected_or_derivation_reads_during_blind": expected_reads,
         "blind_boundary_intact": len(expected_reads) == 0,
         "config_fingerprint_recomputed": got, "config_fingerprint_match": got == want}
json.dump(proof, _open(os.path.join(OUT, "blind-proof.json"), "w"), indent=1)
json.dump(timings, _open(os.path.join(OUT, "timings.json"), "w"), indent=1)
print("phase1 blind: evaluated", len(produced), "| blind boundary intact:", proof["blind_boundary_intact"],
      "| fingerprint match:", got == want)
