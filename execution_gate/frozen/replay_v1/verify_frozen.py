"""Verify the replay_v1 freeze has not drifted: recompute every artifact SHA-256 and the
aggregate hash, and compare to MANIFEST.json. Exit non-zero on any mismatch.

Run: python3 execution_gate/frozen/replay_v1/verify_frozen.py
"""
import hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "artifacts")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    man = json.load(open(os.path.join(HERE, "MANIFEST.json")))
    problems = []
    for f in man["files"]:
        p = os.path.join(ART, f["frozen_name"])
        if not os.path.exists(p):
            problems.append(f"MISSING {f['frozen_name']}"); continue
        actual = sha256(p)
        if actual != f["sha256"]:
            problems.append(f"DRIFT {f['frozen_name']}: {actual[:12]} != {f['sha256'][:12]}")
    agg = hashlib.sha256("".join(f["sha256"] for f in sorted(man["files"], key=lambda x: x["frozen_name"])).encode()).hexdigest()
    if agg != man["aggregate_manifest_hash"]:
        problems.append(f"AGGREGATE DRIFT: {agg[:16]} != {man['aggregate_manifest_hash'][:16]}")
    if problems:
        print("FROZEN REPLAY_V1 VERIFICATION FAILED:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print(f"replay_v1 OK: {len(man['files'])} artifacts verified; aggregate {man['aggregate_manifest_hash'][:16]}")
    sys.exit(0)


if __name__ == "__main__":
    main()
