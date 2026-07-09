#!/usr/bin/env python3
"""Tests for the B1.4b′ McRae Y-preparation. Terms-compliant: asserts NO raw McRae data is
tracked. Logic + guard tests run without the private files; an integration test runs only if
the operator-provided McRae source dir is available (env MCRAE_SRC_DIR or a discoverable path).

    python3 test_b1_4b_prime_prepare_mcrae_y.py
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import b1_4b_prime_prepare_mcrae_y as P


def _find_source():
    env = os.environ.get("MCRAE_SRC_DIR")
    cands = [env] if env else []
    # discover a dir that contains a *CONCS_brm.txt file
    for base in ("/root/.claude/uploads",):
        b = pathlib.Path(base)
        if b.exists():
            for p in b.rglob("*CONCS_brm.txt"):
                cands.append(str(p.parent)); break
    for c in cands:
        if c and pathlib.Path(c).exists():
            try:
                P._resolve(pathlib.Path(c), "CONCS_brm.txt"); return pathlib.Path(c)
            except Exception:
                continue
    return None


def test_tag_strip_rule():
    assert P._base("bat_(animal)") == "bat"
    assert P._base("BOARD_(black)") == "board"
    assert P._base("accordion") == "accordion"


def test_hash_determinism():
    assert P._sha_text("x") == P._sha_text("x")
    assert P._sha_json({"a": 1, "b": 2}) == P._sha_json({"b": 2, "a": 1})


def test_no_raw_mcrae_data_is_tracked():
    # Terms of Use: raw McRae files / derived Y / full lists must NEVER be tracked in git
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True).stdout
    tracked = out.splitlines()
    for pat in P.RAW_PATTERNS:
        offenders = [t for t in tracked if pat in pathlib.Path(t).name]
        assert not offenders, f"raw pattern {pat!r} is tracked: {offenders}"


def test_private_dir_is_gitignored():
    priv = "experiments/primitive_sequence_recovery/frozen/private_mcrae/x.npz"
    r = subprocess.run(["git", "check-ignore", priv], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, "private_mcrae dir must be git-ignored"


def test_prep_config_frozen_shape():
    assert P.PREP_CONFIG["min_retained_concepts"] == 100
    assert P.PREP_CONFIG["homograph_rule"] == "exclude_all_collapsed_members"
    assert P.PREP_CONFIG["false_collision_rule"] == "exclude_all_collapsed_members"


def test_integration_if_source_available():
    src = _find_source()
    if src is None:
        print("  (skip integration: McRae source dir not available)"); return
    res = P.prepare(src, HERE / "frozen" / "private_mcrae", HERE / "frozen", write=False)
    assert res["label"] == "B1_4B_PRIME_Y_PREP_READY", res["checks"]
    assert res["retained"] >= 100
    assert res["retained"] == 521, res["retained"]           # 541 - 18 homographs - 2 false-collision
    assert res["features"] > 0
    # cloak/clock false collision excluded; homographs excluded
    assert "cloak" in res["excluded"]["false_collision"]
    assert "clock" in res["excluded"]["false_collision"]
    assert "bat_(animal)" in res["excluded"]["homograph"]
    # all checks green + deterministic (re-run same hashes)
    assert all(res["checks"].values())
    res2 = P.prepare(src, HERE / "frozen" / "private_mcrae", HERE / "frozen", write=False)
    assert res2["manifest"]["y_matrix_sha256"] == res["manifest"]["y_matrix_sha256"]
    assert res2["manifest"]["derived_concept_list_sha256"] == res["manifest"]["derived_concept_list_sha256"]


def test_manifest_has_no_raw_values():
    # the tracked manifest/exclusions must carry hashes/counts/labels only, no feature values
    mani = HERE / "frozen" / "b1_4b_prime_mcrae_y_prep_manifest.json"
    if mani.exists():
        txt = mani.read_text()
        assert "Prod_Freq" not in txt        # no raw column data
        assert "sha256" in txt
    exc = HERE / "frozen" / "b1_4b_prime_mcrae_exclusions.json"
    if exc.exists():
        t = exc.read_text().lower()
        assert "no mcrae feature values" in t and "prod_freq" not in t


def run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t(); print("PASS", t.__name__)
    print(f"\n{len(tests)}/{len(tests)} tests passed  (no raw data tracked; no run)")
    return True


if __name__ == "__main__":
    sys.exit(0 if run_all() else 1)
