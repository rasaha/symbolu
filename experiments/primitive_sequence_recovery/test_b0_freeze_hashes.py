"""Gate-2 hash-validation for the Track B / H2 B0 freeze set — NO MODEL, NO SCORING, NO FREEZE.

Verifies that every sha256 recorded in b0_freeze_hashes.json still matches the current bytes of the
enumerated freeze-set file, that the recorded set equals exactly what b0_artifact_index.json
enumerates, and that the manifest asserts the non-freeze boundary. Recomputes hashes read-only;
does NOT freeze B0, sign a record, approve B1, or unblock Track B.

    python3 experiments/primitive_sequence_recovery/test_b0_freeze_hashes.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = json.loads((HERE / "b0_freeze_hashes.json").read_text(encoding="utf-8"))
INDEX = json.loads((HERE / "b0_artifact_index.json").read_text(encoding="utf-8"))


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def _sha(rel):
    h = hashlib.sha256()
    h.update((REPO / rel).read_bytes())
    return h.hexdigest()


def _index_enumerated_paths():
    paths = []
    for group in INDEX["freeze_set"].values():
        if isinstance(group, list):
            for it in group:
                if it["path"] not in paths:
                    paths.append(it["path"])
    return paths


def test_manifest_covers_exactly_the_enumerated_set():
    manifest_paths = [a["path"] for a in MANIFEST["artifacts"]]
    _check("manifest set == index-enumerated freeze set",
           sorted(manifest_paths) == sorted(_index_enumerated_paths()))
    _check("no duplicate paths in manifest", len(manifest_paths) == len(set(manifest_paths)))


def test_every_hash_matches_current_bytes():
    for a in MANIFEST["artifacts"]:
        _check(f"exists: {a['path']}", (REPO / a["path"]).is_file())
        _check(f"sha256 matches: {a['path'].split('/')[-1]}", _sha(a["path"]) == a["sha256"])
        _check(f"byte size matches: {a['path'].split('/')[-1]}",
               (REPO / a["path"]).stat().st_size == a["bytes"])


def test_manifest_asserts_non_freeze_boundary():
    m = MANIFEST["_meta"]
    _check("b0_frozen false", m["b0_frozen"] is False)
    _check("b0_freeze_signed false", m["b0_freeze_signed"] is False)
    _check("b1_approved false", m["b1_approved"] is False)
    _check("track_b BLOCKED", m["track_b"] == "BLOCKED")
    _check("hash_algo sha256", m["hash_algo"] == "sha256")
    _check("git_head recorded", isinstance(m.get("git_head"), str) and len(m["git_head"]) >= 10)


def main():
    print("test_b0_freeze_hashes — Gate-2 hash validation (no model, no scoring, no freeze)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll Gate-2 hash-validation checks passed (B0 still NOT frozen).")


if __name__ == "__main__":
    main()
