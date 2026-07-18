#!/usr/bin/env python3
"""Phase 1 — preflight for the native word-specificity evaluator run. ZERO model calls.

Verifies: git commit; every frozen artifact hash; trials count; answer-key SEPARATION (collector cannot import
the key; evaluator-facing trials carry no answer); position balance (from the hash-pinned position_balance.json,
no key access); protocol completeness; model-manifest syntax + family policy; output dir empty or --resume.

Exits NONZERO on any failure. Does not read the internal answer key.
"""
from __future__ import annotations
import argparse
import json
import pathlib
import subprocess
import sys

import native_ws_runlib as R

HERE = pathlib.Path(__file__).resolve().parent
V2 = R.V2
POSBAL = V2 / "position_balance.json"
# the paraphrase-authoring family the evaluators must be disjoint from (v2 isolated authoring ran on this assistant)
AUTHORING_FAMILY_TOKENS = ("anthropic", "claude")
COLLECTOR_SOURCES = ("run_native_word_specificity_evaluators.py", "native_ws_runlib.py")
REQUIRED_PROTOCOL_FIELDS = ("literal_prompt_template", "response_schema", "invalid_output_handling",
                            "retry_policy", "timeout_policy", "duplicate_response_policy",
                            "missing_response_policy", "model_family_policy", "scoring_rule",
                            "repetitions_per_base_trial", "temperature")
MANIFEST_REQUIRED = ("evaluator_id", "model_id", "family", "revision", "backend")


def _ok(checks, name, cond, detail=""):
    checks.append({"check": name, "pass": bool(cond), "detail": detail})
    return bool(cond)


def run(expected_packet_commit, expected_audit_commit, manifest_path, output_root, resume):
    checks = []

    # --- git commit ---
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(HERE)).decode().strip()
    except Exception as e:                                      # noqa: BLE001
        head = f"UNKNOWN({e})"
    for label, exp in (("packet", expected_packet_commit), ("audit", expected_audit_commit)):
        if not exp:
            continue
        try:
            inhist = subprocess.run(["git", "merge-base", "--is-ancestor", exp, "HEAD"],
                                    cwd=str(HERE)).returncode == 0
        except Exception:                                      # noqa: BLE001
            inhist = False
        _ok(checks, f"git_{label}_commit_in_history", inhist, f"expected {exp} ancestor of {head}")

    # --- frozen artifact hashes (v2 self-consistency) ---
    fi = json.loads((V2 / "packet_freeze_index.json").read_text(encoding="utf-8"))
    hashes_ok = True
    for f, want in fi["frozen_hashes"].items():
        got = R.sha256_file(V2 / f)
        if got != want:
            hashes_ok = False
    _ok(checks, "v2_frozen_hashes_match", hashes_ok, f"{len(fi['frozen_hashes'])} artifacts")

    # --- trials count ---
    trials = R.load_trials()
    _ok(checks, "trials_count_720", len(trials) == 720, f"n={len(trials)}")
    _ok(checks, "trial_ids_unique", len({t["trial_id"] for t in trials}) == len(trials), "")

    # --- answer-key separation ---
    key_never_in_collector = True
    for src in COLLECTOR_SOURCES:
        txt = (HERE / src).read_text(encoding="utf-8")
        if "answer_key" in txt or "internal/answer_key" in txt:
            key_never_in_collector = False
    _ok(checks, "collector_never_references_answer_key", key_never_in_collector, "static source scan")
    trials_have_no_answer = not any(k in json.dumps(trials) for k in ("correct_label", "target_word", '"arm"'))
    _ok(checks, "evaluator_facing_has_no_answer_fields", trials_have_no_answer, "")

    # --- position balance (from hash-pinned position_balance.json; NO key access) ---
    pb = json.loads(POSBAL.read_text(encoding="utf-8"))
    per_arm_uniform = all(v["chi2"] == 0 for k, v in pb["per_set_arm"].items())
    sims_no_edge = all(s["primary_contrast_delta"] <= 0 for s in pb["position_bias_simulation"].values())
    _ok(checks, "position_per_set_arm_uniform_chi2_zero", per_arm_uniform, "")
    _ok(checks, "position_bias_agents_no_primary_edge", sims_no_edge,
        f"max Δ={pb.get('max_delta_across_position_policies')}")

    # --- protocol completeness ---
    proto = R.load_protocol()
    proto_ok = all(proto.get(f) not in (None, "") for f in REQUIRED_PROTOCOL_FIELDS)
    _ok(checks, "protocol_fields_present", proto_ok, "")
    _ok(checks, "protocol_temperature_zero", proto.get("temperature") == 0, "")
    _ok(checks, "protocol_repeats_six", proto.get("repetitions_per_base_trial") == 6, "")
    _ok(checks, "protocol_no_placeholder", "N>=?" not in json.dumps(proto), "")
    _ok(checks, "protocol_choice_enum_W1_W6", proto["response_schema"]["properties"]["choice"]["enum"]
        == list(R.VALID_LABELS), "")

    # --- model manifest syntax + family policy ---
    manifest_ok = True
    fam_detail = ""
    try:
        man = R.load_manifest(manifest_path)
        evs = man.get("evaluators", [])
        n = len(evs)
        fields_ok = all(all(k in e for k in MANIFEST_REQUIRED) for e in evs)
        families = [str(e.get("family", "")).lower() for e in evs]
        distinct_families = len(set(families)) == len(families) and all(families)
        disjoint = not any(any(tok in fam for tok in AUTHORING_FAMILY_TOKENS) for fam in families)
        placeholders = [e["model_id"] for e in evs if not e.get("model_id") or "..." in str(e.get("model_id"))
                        or str(e.get("model_id")).startswith("REPLACE")]
        manifest_ok = n >= 3 and fields_ok and distinct_families and disjoint and not placeholders
        fam_detail = (f"n={n} families={families} distinct={distinct_families} "
                      f"disjoint_from_authoring={disjoint} unresolved_model_ids={placeholders}")
    except Exception as e:                                      # noqa: BLE001
        manifest_ok = False
        fam_detail = f"manifest error: {e}"
    _ok(checks, "manifest_valid_ge3_distinct_disjoint_resolved", manifest_ok, fam_detail)

    # --- output dir empty or resume ---
    root = pathlib.Path(output_root)
    nonempty = root.exists() and any(root.rglob("*.jsonl"))
    _ok(checks, "output_dir_empty_or_resume", (not nonempty) or resume,
        f"root={root} has_existing_evidence={nonempty} resume={resume}")

    all_pass = all(c["pass"] for c in checks)
    report = {"phase": "preflight", "head_commit": head, "all_pass": all_pass, "checks": checks,
              "no_model_calls": True}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all_pass else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expected-packet-commit", default="42f38d57")
    ap.add_argument("--expected-audit-commit", default="fc15a0d8")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--output-root", default=str(HERE / "native_ws_raw_evidence"))
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    sys.exit(run(a.expected_packet_commit, a.expected_audit_commit, a.manifest, a.output_root, a.resume))


if __name__ == "__main__":
    main()
