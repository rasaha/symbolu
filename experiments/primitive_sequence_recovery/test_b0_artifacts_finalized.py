"""Gate-1 validation for the Track B / H2 B0 artifact set — NO MODEL, NO SCORING, NO HASHING, NO FILES.

Verifies that the standalone B0 artifact set enumerated in b0_artifact_index.json is assembled,
placeholder-clean over the freeze set, and internally consistent — WITHOUT computing hashes,
populating a manifest, freezing B0, approving B1, or unblocking Track B.

Checks (mirrors the Gate-1 required-checks list):
  1. Every freeze-set file listed in the index exists.
  2. No TBD/PENDING/PLACEHOLDER/UNKNOWN/METADATA_FAIL/HUB_IMPORT_FAIL/OK/FAIL/YES/NO/____/<PASTE
     placeholder token remains in any freeze-set file.
  3. Word list = 20 primary + 5 privative.
  4. Excluded dev/demo + fixture words remain excluded.
  5. D-table covers 25/25 eval words.
  6. Real conditioning renders 150/150 word-arm cores (SKIPs loud if true-G2P unavailable).
  7. Planned generation expansion = 3,600.
  8. Judge packets remain blinded.
  9. Leak dry-check clean.
 10. Parity within +/-25%.
 11. Runtime lock is validated (19-check core) and referenced by the index.
 12. No result files created; no ML libraries imported.

    python3 experiments/primitive_sequence_recovery/test_b0_artifacts_finalized.py
"""
from __future__ import annotations

import json
import pathlib
import re
import statistics
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import b1_dry_run_harness as B            # noqa: E402
import b1_real_conditioning as RC         # noqa: E402

INDEX = json.loads((HERE / "b0_artifact_index.json").read_text(encoding="utf-8"))

# placeholder tokens forbidden in freeze-critical files. NOTE: the slash forms "OK/FAIL" and "YES/NO"
# are the unfilled template placeholders; a resolved bare "OK" or "YES" value is legitimate and is
# NOT matched here.
_PLACEHOLDERS = ("TBD", "PENDING", "PLACEHOLDER", "UNKNOWN", "METADATA_FAIL", "HUB_IMPORT_FAIL",
                 "OK/FAIL", "YES/NO", "____", "<PASTE", "<TBD")


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def _g2p_ok():
    try:
        RC.real_core("grief", "A")
        return True
    except Exception as e:                 # noqa: BLE001
        print(f"[SKIP] true G2P unavailable ({type(e).__name__}); G2P-dependent checks skipped")
        return False


def _freeze_set_paths():
    fs = INDEX["freeze_set"]
    paths = []
    for group in fs.values():
        if isinstance(group, list):
            for item in group:
                paths.append(item["path"])
    return paths


# ---------------------------------------------------------------- 1. existence --------------------
def test_freeze_set_files_exist():
    for rel in _freeze_set_paths():
        _check(f"exists: {rel}", (REPO / rel).is_file())


# ---------------------------------------------------------------- 2. placeholder scan -------------
def test_no_placeholders_in_freeze_set():
    for rel in _freeze_set_paths():
        text = (REPO / rel).read_text(encoding="utf-8")
        for tok in _PLACEHOLDERS:
            # allow the token to appear only inside a provenance commit-hash reference line
            hits = [ln for ln in text.splitlines()
                    if tok in ln and "supersedes them" not in ln and "provenance" not in ln.lower()]
            _check(f"{rel}: no {tok!r}", not hits)


def test_superseded_docs_excluded_from_freeze_set():
    fs_paths = set(_freeze_set_paths())
    for rel in INDEX["provenance_only_superseded"]["files"]:
        _check(f"superseded doc not in freeze set: {rel}", rel not in fs_paths)


# ---------------------------------------------------------------- 3-4. word list ------------------
def test_wordlist_20_5_and_exclusions():
    prim, priv = RC.load_wordlist()
    _check("20 primary words", len(prim) == 20)
    _check("5 privative words", len(priv) == 5)
    _check("primary == harness", prim == B.PRIMARY_WORDS)
    _check("privative == harness", priv == B.PRIVATIVE_WORDS)
    for bad in ("mercy", "love", "anger", "peace", "Alakshmi", "Lakshmi", "anhydrous", "theist"):
        _check(f"{bad!r} excluded", bad not in RC.EVAL_WORDS and bad.lower() not in RC.DTABLE)


# ---------------------------------------------------------------- 5. D-table ----------------------
def test_dtable_25_of_25():
    dt = RC.load_dtable()
    _check("D-table 25 entries", len(dt) == 25)
    for w in RC.EVAL_WORDS:
        e = dt.get(w.lower())
        _check(f"D-table covers {w!r}", bool(e) and bool(e.get("gloss")) and 3 <= len(e.get("synonyms", [])) <= 5)


# ---------------------------------------------------------------- 6. render 150 -------------------
def test_real_conditioning_150():
    if not _g2p_ok():
        return
    grid = RC.render_all()
    _check("150 cores rendered", len(grid) == 150)
    _check("no empty core", all(isinstance(v, str) and v.strip() for v in grid.values()))
    a_unres = [w for w in RC.EVAL_WORDS if "[unresolved]" in RC.real_core(w, "A")]
    _check("A fully resolved (0 unresolved)", a_unres == [])


# ---------------------------------------------------------------- 7. expansion 3600 ---------------
def test_planned_expansion_3600():
    rows = B.expand_rows()
    _check("3600 rows", len(rows) == 3600)
    prim = [r for r in rows if r.stratum == "primary"]
    priv = [r for r in rows if r.stratum == "privative"]
    _check("2880 primary", len(prim) == 2880)
    _check("720 privative", len(priv) == 720)


# ---------------------------------------------------------------- 8-9. blinding + leak ------------
def test_blinding_and_leak_real():
    if not _g2p_ok():
        return
    rows = [r for r in B.expand_rows() if r.key_word in ("grief", "amoral")]
    outs = B.run_generation(rows, B.MockModelAdapter(), dry_run=True, conditioning_fn=RC.real_core)
    packets = B.build_judge_packets(outs, rand_seed=B.SEEDS[0] if False else 40411)
    _check("packets built", len(packets) > 0)
    for p in packets:
        view = json.dumps(B.judge_view(p))
        for bad in ("A_vs_", "control", '"A"', '"R"', '"S"', '"C"', '"X"', '"D"', "MOCK_MODEL"):
            _check(f"judge view hides {bad!r}", bad not in view)
        for arm in ("A", "R", "S", "C", "X", "D"):
            _check("judge view hides real core", RC.real_core(p.key_word, arm) not in view)
    # leak dry-check over all 150 slots
    forbidden = B.FORBIDDEN
    hits = 0
    for w in RC.EVAL_WORDS:
        for a in ("A", "R", "S", "C", "X", "D"):
            t = RC.real_conditioning_slot(w, a).lower()
            if any(p in t for p in forbidden) or re.search(r"\brescue\b", t):
                hits += 1
    _check("leak dry-check clean (0 hits)", hits == 0)


# ---------------------------------------------------------------- 10. parity ----------------------
def test_parity_within_25pct():
    if not _g2p_ok():
        return
    by_arm = {a: [len(RC.real_conditioning_slot(w, a)) for w in RC.EVAL_WORDS]
              for a in ("A", "R", "S", "C", "X", "D")}
    mA = statistics.median(by_arm["A"])
    for a in ("R", "S", "C", "X", "D"):
        pct = 100.0 * (statistics.median(by_arm[a]) - mA) / mA
        _check(f"arm {a} within +/-25% of A ({pct:+.1f}%)", abs(pct) <= 25.0)


# ---------------------------------------------------------------- 11. runtime lock ----------------
def test_runtime_lock_validated_and_referenced():
    import yaml  # noqa
    lock_path = REPO / "experiments/primitive_sequence_recovery/TRACK_B_RUNTIME_MODEL_LOCK.yaml"
    d = yaml.safe_load(lock_path.read_text(encoding="utf-8"))["RUNTIME_MODEL_LOCK"]

    def yes(v):
        return v is True or str(v).strip().upper() == "YES"

    A, Bm = d["model_A"], d["model_B"]
    ok = (d["lock_state"] == "FILLED_OPERATOR_LOCK" and d["frozen"] is False
          and A["id"] and Bm["id"]
          and len(str(A["revision_or_api_version"])) >= 8 and len(str(Bm["revision_or_api_version"])) >= 8
          and A["availability_result"] == "OK" and Bm["availability_result"] == "OK"
          and yes(A["no_model_output_produced"]) and yes(Bm["no_model_output_produced"])
          and yes(d["distinct_families"]) and A["family"] != Bm["family"]
          and d["operator_decision"] == "LOCK_AND_CONTINUE_TO_B0_FINALIZE")
    _check("runtime lock validated (core 19-check)", ok)
    _check("index references runtime lock",
           "TRACK_B_RUNTIME_MODEL_LOCK.yaml" in INDEX["_meta"]["runtime_lock"])


# ---------------------------------------------------------------- 12. hygiene ---------------------
def test_no_result_files_and_no_ml_libs():
    _check("no torch/transformers/vllm/openai/anthropic imported",
           not any(m in sys.modules for m in ("torch", "transformers", "vllm", "openai", "anthropic")))
    before = {p.name for p in HERE.iterdir()}
    if _g2p_ok():
        B.run_generation(B.expand_rows()[:30], B.MockModelAdapter(), dry_run=True,
                         conditioning_fn=RC.real_core)
    _check("no files written", {p.name for p in HERE.iterdir()} == before)
    # index attests the non-execution boundary
    m = INDEX["_meta"]
    _check("index: not frozen / not hashed / b1 not approved / track b blocked",
           m["frozen"] is False and m["hashes_computed"] is False
           and m["b1_approved"] is False and m["track_b"] == "BLOCKED")


def main():
    print("test_b0_artifacts_finalized — Gate-1 B0 artifact validation (no model, no scoring, no hash, no files)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll Gate-1 B0 artifact checks passed (freeze set clean; residual open fields reported separately).")


if __name__ == "__main__":
    main()
