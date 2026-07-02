"""Tests for the manifest loader / schema validator / readiness gate.

Uses only SYNTHETIC temporary frozen directories — no real data, no embeddings, no scores,
no network/LLM, no result files. Verifies the readiness gate returns NOT_READY for every
defective bundle and READY only for a fully-valid one, and that the runner stays NOT_RUN
even when READY.

    python3 experiments/primitive_sequence_recovery/test_manifest_gate.py
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
import tempfile

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import manifest as MF               # noqa: E402
import run_primitive_recovery as RUN  # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


# ---- synthetic artifact fixtures (no real content) ---------------------------
def _default_artifacts():
    assignment = {"schema_version": "1.0", "varnas": ["v0", "v1", "v2"],
                  "atoms": ["a0", "a1", "a2"],
                  "tau": {"v0": "a0", "v1": "a1", "v2": "a2"}}
    realizations = {}
    for rid, lang, src, kind in [("en", "en", "toy_en_lex", "gloss_text"),
                                 ("sa", "sa", "toy_sa_lex", "gloss_text"),
                                 ("concept", "concept", "toy_kb", "synset_id")]:
        realizations[f"realization_{rid}.json"] = {
            "schema_version": "1.0", "realization_id": rid, "language": lang,
            "source": src, "provenance": "synthetic", "version": "1",
            "atom_content": {"a0": f"{rid}:c0", "a1": f"{rid}:c1", "a2": f"{rid}:c2"},
            "meaning_encoder": {"kind": kind, "ref": f"{rid}_enc"}}
    word_list = {"schema_version": "1.0", "words": [
        {"word_id": "w0", "spelling": "v0v1", "varna_sequence": ["v0", "v1"],
         "family_id": "f0", "sense_id": "s0", "exclude_flag": False},
        {"word_id": "w1", "spelling": "v1v2", "varna_sequence": ["v1", "v2"],
         "family_id": "f1", "sense_id": "s0", "exclude_flag": False}]}
    meanings = {"schema_version": "1.0", "meanings": [
        {"word_id": "w0", "canonical_meaning": "m0",
         "realization_specific_reference": {"en": "e0", "sa": "s0", "concept": "c0"}},
        {"word_id": "w1", "canonical_meaning": "m1",
         "realization_specific_reference": {"en": "e1", "sa": "s1", "concept": "c1"}}]}
    distractors = {"schema_version": "1.0", "K": 2, "match_keys": ["freq"],
                   "sampling_seed": 0, "assignments": {"w0": ["w1"], "w1": ["w0"]}}
    realizer = {"schema_version": "1.0", "realizer_id": "r0", "status": "IMPLEMENTED",
                "deterministic": True, "offline_only": True, "execution_allowed": True,
                "implementation_present": True, "primary_realizer_type": "toy_vector",
                "robustness_realizers": [], "expected_input": "atom sequence",
                "expected_output": "ranking", "similarity_metric": "cosine",
                "normalization": "unit", "model_asset": "toy_asset",
                "model_sha256": "0" * 64, "concept_resolver": "toy_resolver",
                "concept_resolver_status": "IMPLEMENTED", "notes": "synthetic"}
    run_params = {"schema_version": "1.0", "experiment_id": "e0", "scoring_metric": "MRR",
                  "secondary_metric": "Top1", "K": 8, "scramble_seeds": 1000,
                  "bootstrap_iterations": 1000, "paired_test": "wilcoxon_signed_rank",
                  "confidence_interval": 0.95, "alpha": 0.05, "order_scramble_enabled": True,
                  "assignment_scramble_enabled": True, "family_bootstrap": True,
                  "run_enabled": True, "execution_status": "NOT_RUN"}
    return {"assignment": assignment, "realizations": realizations, "word_list": word_list,
            "meanings": meanings, "distractors": distractors, "realizer": realizer,
            "run_params": run_params}


def _write(path, obj):
    txt = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    path.write_text(txt, encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_bundle(tmp, arts, status="READY", independence=True):
    d = pathlib.Path(tmp)
    h = {}
    h["assignment"] = _write(d / "assignment.json", arts["assignment"])
    rhashes = {}
    for fname, rec in arts["realizations"].items():
        rhashes[rec["realization_id"]] = _write(d / fname, rec)
    h["word"] = _write(d / "word_list.json", arts["word_list"])
    h["meaning"] = _write(d / "meaning_reference.json", arts["meanings"])
    h["distractor"] = _write(d / "distractors.json", arts["distractors"])
    h["realizer"] = _write(d / "realizer.json", arts["realizer"])
    h["scramble"] = _write(d / "run_params.json", arts["run_params"])
    rids = sorted(r["realization_id"] for r in arts["realizations"].values())
    basis = {}
    pairs = [(rids[i], rids[j]) for i in range(len(rids)) for j in range(i + 1, len(rids))]
    for a, b in pairs:
        basis[f"{a}|{b}"] = "distinct source/language"
    if not independence and basis:
        basis.pop(next(iter(basis)))          # drop one pair -> independence not fully declared
    manifest = {"schema_version": "1.0", "design_doc_sha256": "x" * 64,
                "assignment_hash": h["assignment"], "realization_hashes": rhashes,
                "word_hash": h["word"], "meaning_hash": h["meaning"],
                "distractor_hash": h["distractor"], "realizer_hash": h["realizer"],
                "scramble_seed_hash": h["scramble"], "independence_basis": basis,
                "status": status}
    _write(d / "manifest.json", manifest)
    return d


# ---- tests -------------------------------------------------------------------
def test_missing_manifest():
    with tempfile.TemporaryDirectory() as t:
        r = MF.check_readiness(t)
        _check("missing manifest -> NOT_READY", r["status"] == "NOT_READY")
        _check("missing manifest -> reason", any("manifest" in x for x in r["reasons"]))


def test_fully_valid_ready():
    with tempfile.TemporaryDirectory() as t:
        write_bundle(t, _default_artifacts(), status="READY")
        r = MF.check_readiness(t)
        _check("valid bundle -> READY", r["status"] == "READY")
        _check("valid: schema_ok", r["schema_ok"])
        _check("valid: hashes_ok", r["hashes_ok"])
        _check("valid: references_ok", r["references_ok"])
        _check("valid: 3 realizations", r["realization_count"] == 3)
        _check("valid: independence_ok", r["realization_independence_ok"])
        _check("valid: no reasons", r["reasons"] == [])


def test_malformed_schema():
    a = _default_artifacts()
    del a["word_list"]["words"][0]["family_id"]     # required field removed
    with tempfile.TemporaryDirectory() as t:
        write_bundle(t, a)
        r = MF.check_readiness(t)
        _check("malformed schema -> NOT_READY", r["status"] == "NOT_READY")
        _check("malformed schema -> schema_ok False", r["schema_ok"] is False)


def test_assignment_forbidden_field():
    a = _default_artifacts()
    a["assignment"]["glosses"] = {"a0": "hope"}      # forbidden semantic field
    with tempfile.TemporaryDirectory() as t:
        write_bundle(t, a)
        r = MF.check_readiness(t)
        _check("forbidden field -> NOT_READY", r["status"] == "NOT_READY")
        _check("forbidden field -> schema_ok False", r["schema_ok"] is False)


def test_fewer_than_3_realizations():
    a = _default_artifacts()
    a["realizations"].pop("realization_concept.json")   # only 2 left
    with tempfile.TemporaryDirectory() as t:
        write_bundle(t, a)
        r = MF.check_readiness(t)
        _check("2 realizations -> NOT_READY", r["status"] == "NOT_READY")
        _check("2 realizations -> count 2", r["realization_count"] == 2)


def test_missing_realization_atom():
    a = _default_artifacts()
    del a["realizations"]["realization_en.json"]["atom_content"]["a2"]  # missing atom
    with tempfile.TemporaryDirectory() as t:
        write_bundle(t, a)
        r = MF.check_readiness(t)
        _check("missing realization atom -> NOT_READY", r["status"] == "NOT_READY")
        _check("missing realization atom -> references_ok False", r["references_ok"] is False)


def test_missing_word_meaning():
    a = _default_artifacts()
    a["meanings"]["meanings"] = [a["meanings"]["meanings"][0]]   # drop w1's meaning
    with tempfile.TemporaryDirectory() as t:
        write_bundle(t, a)
        r = MF.check_readiness(t)
        _check("missing meaning -> NOT_READY", r["status"] == "NOT_READY")
        _check("missing meaning -> references_ok False", r["references_ok"] is False)


def test_distractor_unknown_word():
    a = _default_artifacts()
    a["distractors"]["assignments"]["w0"] = ["wX"]   # unknown candidate
    with tempfile.TemporaryDirectory() as t:
        write_bundle(t, a)
        r = MF.check_readiness(t)
        _check("unknown distractor -> NOT_READY", r["status"] == "NOT_READY")
        _check("unknown distractor -> references_ok False", r["references_ok"] is False)


def test_hash_mismatch():
    with tempfile.TemporaryDirectory() as t:
        d = write_bundle(t, _default_artifacts(), status="READY")
        # tamper a file AFTER the manifest was written -> on-disk hash != manifest hash
        (d / "assignment.json").write_text(
            (d / "assignment.json").read_text() + "\n", encoding="utf-8")
        r = MF.check_readiness(t)
        _check("hash mismatch -> NOT_READY", r["status"] == "NOT_READY")
        _check("hash mismatch -> hashes_ok False", r["hashes_ok"] is False)


def test_realizer_not_deterministic_offline():
    a = _default_artifacts()
    a["realizer"]["deterministic"] = False
    a["realizer"]["offline_only"] = False
    with tempfile.TemporaryDirectory() as t:
        write_bundle(t, a)
        r = MF.check_readiness(t)
        _check("non-deterministic/offline realizer -> NOT_READY", r["status"] == "NOT_READY")
        _check("non-deterministic/offline -> schema_ok False", r["schema_ok"] is False)


def test_realizer_not_implemented_blocks():
    a = _default_artifacts()
    a["realizer"].update({"status": "NOT_IMPLEMENTED", "execution_allowed": False,
                          "implementation_present": False, "model_asset": None,
                          "model_sha256": None})
    with tempfile.TemporaryDirectory() as t:
        write_bundle(t, a, status="READY")
        r = MF.check_readiness(t)
        _check("unimplemented realizer -> NOT_READY (no implicit model)",
               r["status"] == "NOT_READY")
        _check("unimplemented realizer -> reason cites status",
               any("status is not IMPLEMENTED" in x for x in r["reasons"]))


def test_run_not_enabled_blocks():
    a = _default_artifacts()
    a["run_params"]["run_enabled"] = False
    with tempfile.TemporaryDirectory() as t:
        write_bundle(t, a, status="READY")
        r = MF.check_readiness(t)
        _check("run_enabled False -> NOT_READY", r["status"] == "NOT_READY")
        _check("run_enabled False -> reason", any("run_enabled" in x for x in r["reasons"]))


def test_concept_resolver_missing_blocks():
    a = _default_artifacts()   # includes a language='concept' / synset_id realization
    a["realizer"].update({"concept_resolver": None, "concept_resolver_status": "NOT_IMPLEMENTED"})
    with tempfile.TemporaryDirectory() as t:
        write_bundle(t, a, status="READY")
        r = MF.check_readiness(t)
        _check("no concept resolver -> NOT_READY", r["status"] == "NOT_READY")
        _check("no concept resolver -> reason",
               any("concept resolver" in x for x in r["reasons"]))


def test_independence_not_declared():
    with tempfile.TemporaryDirectory() as t:
        write_bundle(t, _default_artifacts(), status="READY", independence=False)
        r = MF.check_readiness(t)
        _check("independence missing -> NOT_READY", r["status"] == "NOT_READY")
        _check("independence missing -> independence_ok False",
               r["realization_independence_ok"] is False)


def test_status_not_ready_blocks():
    with tempfile.TemporaryDirectory() as t:
        write_bundle(t, _default_artifacts(), status="NOT_READY")
        r = MF.check_readiness(t)
        _check("declared NOT_READY -> NOT_READY", r["status"] == "NOT_READY")


def test_runner_not_run_even_when_ready():
    with tempfile.TemporaryDirectory() as t:
        write_bundle(t, _default_artifacts(), status="READY")
        # sanity: bundle really is READY
        _check("runner test: bundle READY", MF.check_readiness(t)["status"] == "READY")
        res = RUN.run(frozen_dir=t)
        _check("runner: NOT_RUN even when READY", res["status"] == "NOT_RUN")
        _check("runner: computed False", res["computed"] is False)
        _check("runner: no result", res["result"] is None)
        _check("runner: reason cites not-implemented", "not implemented" in res["reason"])
        _check("runner: readiness reported READY", res["readiness"]["status"] == "READY")


def test_stage_a_not_imported():
    _check("Stage A not imported by manifest/runner",
           not any(m.startswith("symbolu_neural") for m in sys.modules))


def main():
    print("primitive_sequence_recovery — manifest/readiness-gate tests (synthetic only)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll manifest/readiness-gate tests passed.")


if __name__ == "__main__":
    main()
