"""Tests for the Track G scorer step (`run_track_g_smoke_mistral.py`) — NO MODEL, NO SCORING.

Exercises the full label path via the PURE functions (`parse_scorer_json`, `assemble_and_score`,
`_result`) with synthetic scorer output, and proves the guardrails: the env token + separate
approved config are required; the base smoke manifest stays run_enabled:false / NOT_APPROVED; the
dry-run/gate paths make zero model calls and import no ML libs; malformed/contaminated scorer output
is rejected; incomplete cases are dropped; a non-frozen polarity assignment yields
INVALID_POSTHOC_POLARITY; only the 8 allowed labels are ever emitted; the scorer prompt leaks no
hidden fields (arm, target, case_id, surface word, varṇa, polarity direction); and no output
artifact is written by the tests.

    python3 experiments/primitive_sequence_recovery/test_run_track_g_smoke_mistral.py
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import run_track_g_smoke_mistral as M    # noqa: E402
import track_g_smoke_runner as GR        # noqa: E402
import track_g_harness as HG             # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


# ------------------------------------------------------------- synthetic inputs -----
def _make_inputs(per_arm):
    """Build (bundle, hidden, scores_by_pid) for 2 cases x 6 arms, 3 candidates each.
    `per_arm[arm]` = (target_score, nontarget_score); one packet per (case, arm)."""
    cases = ["g000", "g001"]
    cands = ["c_t", "c_a", "c_b"]            # c_t is the target
    bundle = {"assignments": {}, "candidates": {}}
    hidden, scores = {}, {}
    for cid in cases:
        bundle["assignments"][cid] = {"assigned_before_scoring": True, "frozen": True}
        bundle["candidates"][cid] = {"candidates": [{"candidate_id": c} for c in cands],
                                     "target": "c_t"}
        for arm, (ts, ns) in per_arm.items():
            pid = f"pkt_{cid}_{arm}"
            o2c = {"opt_1": "c_t", "opt_2": "c_a", "opt_3": "c_b"}
            hidden[pid] = {"case_id": cid, "true_arm": arm, "opt_to_cand": o2c}
            scores[pid] = {"opt_1": ts, "opt_2": ns, "opt_3": ns}
    return bundle, hidden, scores


_A_WINS = {"A": (1.0, 0.0), "R": (0.0, 1.0), "B": (0.0, 1.0), "I": (0.0, 1.0),
           "X": (0.0, 1.0), "D": (0.0, 1.0)}
_A_EQ_R = {"A": (1.0, 0.0), "R": (1.0, 0.0), "B": (0.0, 1.0), "I": (0.0, 1.0),
           "X": (0.0, 1.0), "D": (0.0, 1.0)}
_A_EQ_X = {"A": (1.0, 0.0), "R": (0.0, 1.0), "B": (0.0, 1.0), "I": (0.0, 1.0),
           "X": (1.0, 0.0), "D": (0.0, 1.0)}
_ALL_EQ = {a: (0.5, 0.5) for a in HG.ARMS_REQUIRED}


# ---------------------------------------------------------------- gates -------------
def test_env_token_required():
    old = os.environ.pop(M.GR.APPROVAL_ENV, None)
    try:
        GR.run_real_smoke_pilot(approval_config=str(_HERE / "track_g_smoke_approved_run_config.json"))
    except GR.RefusedRun:
        _check("no env token -> RefusedRun", True)
    else:
        _check("no env token -> RefusedRun", False)
    finally:
        if old is not None:
            os.environ[M.GR.APPROVAL_ENV] = old


def test_approved_config_required():
    os.environ[GR.APPROVAL_ENV] = GR.APPROVAL_TOKEN
    try:
        GR.run_real_smoke_pilot(approval_config=None)
    except GR.RefusedRun:
        _check("env token but no approval config -> RefusedRun", True)
    else:
        _check("env token but no approval config -> RefusedRun", False)
    finally:
        os.environ.pop(GR.APPROVAL_ENV, None)


def test_base_manifest_stays_not_approved():
    man = json.loads((_HERE / "track_g_smoke_manifest.json").read_text())
    _check("base manifest run_enabled:false", man.get("run_enabled") is False)
    _check("base manifest NOT_APPROVED", man.get("approval_status") == "NOT_APPROVED")
    _check("base manifest four_sphere not integrated", man.get("four_sphere_integrated") is False)


# ------------------------------------------------------------ scorer parsing --------
def test_parse_valid():
    r = M.parse_scorer_json('{"packet_id":"p","scores":{"opt_1":0.9,"opt_2":0.1},"chosen":"opt_1"}',
                            ["opt_1", "opt_2"])
    _check("valid scorer JSON parsed", r["scores"] == {"opt_1": 0.9, "opt_2": 0.1} and r["chosen"] == "opt_1")


def test_parse_recovers_chosen_from_argmax():
    r = M.parse_scorer_json('{"scores":{"opt_1":0.2,"opt_2":0.8}}', ["opt_1", "opt_2"])
    _check("missing/invalid chosen -> argmax", r["chosen"] == "opt_2")


def test_parse_malformed_rejected():
    bad = ['not json at all',
           '{"scores":{"opt_1":0.5}}',                       # wrong key set
           '{"scores":{"opt_1":2.0,"opt_2":0.1}}',           # out of range
           '{"scores":{"opt_1":true,"opt_2":0.1}}',          # bool, not numeric
           '{"scores":{"opt_1":"hi","opt_2":0.1}}']          # non-numeric
    for b in bad:
        try:
            M.parse_scorer_json(b, ["opt_1", "opt_2"])
        except ValueError:
            continue
        _check(f"malformed rejected: {b[:30]!r}", False)
    _check("all malformed scorer outputs rejected", True)


def test_parse_rejects_contamination():
    contaminated = '{"scores":{"opt_1":0.9,"opt_2":0.1},"chosen":"opt_1","why":"the varna fits"}'
    try:
        M.parse_scorer_json(contaminated, ["opt_1", "opt_2"])
    except ValueError:
        _check("contaminated scorer text rejected", True); return
    _check("contaminated scorer text rejected", False)


# ------------------------------------------------------- assemble + label -----------
def test_assemble_polarity_boundary_signal():
    b, h, s = _make_inputs(_A_WINS)
    r = M.assemble_and_score(b, h, s)
    _check("A beats all arms -> POLARITY_BOUNDARY_SIGNAL", r["primary_label"] == "POLARITY_BOUNDARY_SIGNAL")
    _check("co-primary flag set", r["A_vs_R_and_A_vs_X_are_co_primary"] is True)
    _check("tasks_judged == 2", r["tasks_judged"] == 2)


def test_assemble_random_polarity_explains():
    b, h, s = _make_inputs(_A_EQ_R)
    r = M.assemble_and_score(b, h, s)
    _check("A == R -> RANDOM_POLARITY_EXPLAINS", r["primary_label"] == "RANDOM_POLARITY_EXPLAINS")


def test_assemble_context_only_explains():
    b, h, s = _make_inputs(_A_EQ_X)
    r = M.assemble_and_score(b, h, s)
    _check("A == X -> CONTEXT_ONLY_EXPLAINS", r["primary_label"] == "CONTEXT_ONLY_EXPLAINS")


def test_assemble_inconclusive_when_flat():
    b, h, s = _make_inputs(_ALL_EQ)
    r = M.assemble_and_score(b, h, s)
    _check("flat arms -> INCONCLUSIVE", r["primary_label"] == "INCONCLUSIVE")


def test_assemble_posthoc_invalid():
    b, h, s = _make_inputs(_A_WINS)
    b["assignments"]["g000"]["frozen"] = False       # break the pre-registration freeze
    r = M.assemble_and_score(b, h, s)
    _check("non-frozen assignment -> INVALID_POSTHOC_POLARITY",
           r["primary_label"] == "INVALID_POSTHOC_POLARITY")


def test_assemble_drops_incomplete_cases():
    b, h, s = _make_inputs(_A_WINS)
    # remove the D-arm packet for g001 -> that case is incomplete and must be dropped, not crash.
    del s["pkt_g001_D"]; del h["pkt_g001_D"]
    r = M.assemble_and_score(b, h, s)
    _check("incomplete case dropped", r["tasks_dropped_by_judge"] == ["g001"])
    _check("remaining complete case still judged", r["tasks_judged"] == 1)


def test_assemble_all_incomplete_inconclusive():
    b, h, s = _make_inputs(_A_WINS)
    for cid in ("g000", "g001"):                     # drop one arm from every case
        del s[f"pkt_{cid}_D"]; del h[f"pkt_{cid}_D"]
    r = M.assemble_and_score(b, h, s)
    _check("no complete cases -> INCONCLUSIVE", r["primary_label"] == "INCONCLUSIVE")


def test_arm_I_takes_max_over_barnum_variants():
    b, h, s = _make_inputs(_A_WINS)
    # add a second Barnum variant for g000 that would, alone, put the target on top; max rule should
    # keep arm I strong. Confirm it still assembles a complete case (no crash, arm I present).
    h["pkt_g000_I2"] = {"case_id": "g000", "true_arm": "I",
                        "opt_to_cand": {"opt_1": "c_t", "opt_2": "c_a", "opt_3": "c_b"}}
    s["pkt_g000_I2"] = {"opt_1": 1.0, "opt_2": 0.0, "opt_3": 0.0}
    r = M.assemble_and_score(b, h, s)
    _check("arm I max-aggregation still yields a valid label", r["primary_label"] in HG.ALLOWED_LABELS)


def test_only_allowed_labels_emitted():
    for per_arm in (_A_WINS, _A_EQ_R, _A_EQ_X, _ALL_EQ):
        b, h, s = _make_inputs(per_arm)
        lab = M.assemble_and_score(b, h, s)["primary_label"]
        _check(f"label {lab} in allowed set", lab in HG.ALLOWED_LABELS)
        _check(f"label {lab} not forbidden", lab not in HG.FORBIDDEN_LABELS)


# ------------------------------------------------------- prompt leak-safety ---------
def test_prompt_has_no_hidden_fields():
    bundle = GR.load_bundle()
    packets, hidden = GR.build_packets(bundle)
    p = packets[0]
    h = hidden[p["packet_id"]]
    text = " ".join(m["content"] for m in M._prompt(p)).lower()
    # scorer prompt must not carry any hidden routing/answer field
    for bad in ("true_arm", "target_id", "opt_to_cand", "case_id", "expected_pole",
                "expected_relation", "assigned_before_scoring", "sphere"):
        _check(f"prompt omits hidden token {bad!r}", bad not in text)
    _check("prompt omits case_id value", h["case_id"].lower() not in text)
    surf = bundle["words"][h["case_id"].split("-")[0]].get("dev_surface_word")
    if surf:
        _check("prompt omits surface word", surf.lower() not in text)
    for vk in GR.VARNA_KEYS:
        import re
        _check(f"prompt omits varṇa key {vk!r}", re.search(r"\b" + re.escape(vk) + r"\b", text) is None)


# --------------------------------------------------------- no model / no writes -----
def test_no_ml_libs_imported():
    _check("no torch/transformers imported by dry/pure paths",
           not any(m in sys.modules for m in ("torch", "transformers", "openai", "anthropic")))


def test_no_output_artifact_written_by_tests():
    _check("no track_g_smoke_outputs.json written by tests", not M.OUTPUTS_JSON.exists())
    _check("no TRACK_G_SMOKE_RESULT.md written by tests", not M.RESULT_MD.exists())


def test_constants_are_conservative():
    _check("temp is 0.0 (deterministic)", M.TEMPERATURE == 0.0)
    _check("malformed abort rate sane", 0.0 < M.MALFORMED_ABORT_RATE <= 0.5)
    _check("default model is Mistral", "Mistral" in M.DEFAULT_MODEL)


def main():
    print("run_track_g_smoke_mistral — scorer-step tests (no LLM, no scoring, no writes)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll Track G scorer-step tests passed.")


if __name__ == "__main__":
    main()
