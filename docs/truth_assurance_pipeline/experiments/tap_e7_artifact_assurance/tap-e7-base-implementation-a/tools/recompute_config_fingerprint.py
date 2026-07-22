#!/usr/bin/env python3
"""Independently recompute the runtime config fingerprint from published package data.
Recipe is reconstructed from the release-manifest (target ids, canonicalization, note that
corpus_root is excluded), the frozen thresholds, and the resource-manifest outcome_affecting
flags. If our computed value differs from the package value, execution must stop."""
import hashlib, json, os, sys
def canon(o): return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def sha(b): return "sha-256:" + hashlib.sha256(b).hexdigest()

def recompute(pkg):
    rel = json.load(open(os.path.join(pkg, "manifest/release-manifest.json")))
    rm = json.load(open(os.path.join(pkg, "manifest/resource-manifest.json")))
    runtime = [e for e in rm["resources"] if e.get("outcome_affecting")]
    obj = {"target_spec": rel["target_specification"],
           "target_profile": rel["target_profile"],
           "canonicalization": rel["canonicalization"],
           "thresholds": {"T_accept": 0.85, "T_reject": 0.35},
           "runtime_resources": [{"path": e["path"], "sha256": e["sha256"]} for e in runtime]}
    return sha((canon(obj) + "\n").encode()), rel["roots"]["config_fingerprint"]

if __name__ == "__main__":
    pkg = sys.argv[1]
    got, want = recompute(pkg)
    print("recomputed:", got)
    print("package   :", want)
    print("MATCH" if got == want else "MISMATCH")
    sys.exit(0 if got == want else 2)
