"""Track D — Stage D0 LLM-scorer pilot HARNESS MECHANICS (synthetic dry-run only).

D0 is EXPLORATORY TRIAGE. This module implements only the *mechanics* around an LLM judge —
anonymization, arm randomization, Barnum max(I1..I4), JSON validation, contamination parsing,
pairwise metrics, and pilot-label assignment. It contains **no LLM call and no network**; a
judge response is passed *in*. The real pilot is intentionally NOT implemented
(`run_real_pilot` raises).

Guardrails: accepts ONLY inputs marked `toy_not_for_scoring=True` (no real-data path); emits only
LLM_PILOT_* labels; never EXPERIENTIAL_WEATHER_SIGNAL / ONTOLOGICAL_SIGNAL. No claim of signal.
Track B remains blocked. See TRACK_D_LLM_SCORER_PILOT_PLAN.md / TRACK_D_D0_HARNESS_STATUS.md.
"""
from __future__ import annotations

import json
import random

TOY_MARK = "toy_not_for_scoring"
LABELS = ("LLM_PILOT_SUGGESTIVE", "LLM_PILOT_NO_SIGNAL",
          "LLM_PILOT_INCONCLUSIVE", "LLM_PILOT_CONTAMINATED")
FORBIDDEN_LABELS = ("EXPERIENTIAL_WEATHER_SIGNAL", "ONTOLOGICAL_SIGNAL", "SANSKRIT_PRIVILEGE")
# reference tokens whose presence in judge output implies blinding was broken
BANNED_REFS = ("sanskrit", "varna", "varṇa", "vritti", "vṛtti", "devanagari",
               "chakra", "mantra", "spiritual", "hindu", "etymolog")
_ARMS = ("A", "B", "C")
_BARNUM = ("I1", "I2", "I3", "I4")


def _require_toy(case):
    if case.get(TOY_MARK) is not True:
        raise ValueError("D0 dry-run harness accepts only toy_not_for_scoring=True inputs "
                         "(no real-data / real-scoring path).")


# --------------------------------------------------- Stage-2 packet + hidden key ----
def build_packet(case, seed=0):
    """Anonymize + shuffle a toy case into a Stage-2 scoring packet + a HIDDEN key.

    Returns (packet, keys). packet exposes only comp_<n>/prof_<n> (no arm, no word, no meaning).
    keys maps comp_id->arm and prof_id->profile-name (target|I1..I4) and is NEVER shown to a judge.
    """
    _require_toy(case)
    rng = random.Random(seed)

    comps = [(a, case["compositions"][a]) for a in _ARMS]
    rng.shuffle(comps)
    comp_key, packet_comps = {}, []
    for i, (arm, text) in enumerate(comps, 1):
        cid = f"comp_{i}"
        comp_key[cid] = arm
        packet_comps.append({"comp_id": cid, "text": text})

    profs = [("target", case["profiles"]["target"])] + \
            [(k, case["profiles"][k]) for k in _BARNUM]
    rng.shuffle(profs)
    prof_key, packet_profs = {}, []
    for i, (name, desc) in enumerate(profs, 1):
        pid = f"prof_{i}"
        prof_key[pid] = name
        packet_profs.append({"profile_id": pid, "descriptors": desc})

    packet = {"compositions": packet_comps, "profiles": packet_profs}
    keys = {"comp": comp_key, "prof": prof_key}
    return packet, keys


def synthesize_response(judge_behavior, keys):
    """TEST HELPER — models a judge WITHOUT an LLM.

    judge_behavior is specified in NAMED terms {arm: {prof_name: score}}; this maps it onto the
    anonymized ids from `keys`, producing the JSON a blinded judge would return.
    """
    inv_comp = {arm: cid for cid, arm in keys["comp"].items()}
    inv_prof = {name: pid for pid, name in keys["prof"].items()}
    scores = {}
    for arm, profscores in judge_behavior.items():
        scores[inv_comp[arm]] = {inv_prof[pn]: float(sc) for pn, sc in profscores.items()}
    return {"scores": scores}


# ------------------------------------------------------ validation + contamination --
def validate_response(response, packet):
    """Structured-JSON validation. Returns list of error strings ([] = valid)."""
    errors = []
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except Exception as e:  # noqa: BLE001
            return [f"malformed JSON: {e}"]
    if not isinstance(response, dict) or "scores" not in response:
        return ["missing 'scores'"]
    scores = response["scores"]
    if not isinstance(scores, dict):
        return ["'scores' not an object"]
    comp_ids = [c["comp_id"] for c in packet["compositions"]]
    prof_ids = [p["profile_id"] for p in packet["profiles"]]
    for cid in comp_ids:
        if cid not in scores:
            errors.append(f"missing scores for {cid}")
            continue
        for pid in prof_ids:
            v = scores[cid].get(pid)
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                errors.append(f"{cid}/{pid}: non-numeric score")
            elif not (0.0 <= float(v) <= 1.0):
                errors.append(f"{cid}/{pid}: score out of [0,1]")
    return errors


def detect_contamination(response):
    """Flag if the judge output identifies the word or references out-of-prompt knowledge.
    Returns (contaminated: bool, reasons: list)."""
    reasons = []
    if isinstance(response, dict):
        if response.get("contamination_identified") is True:
            reasons.append("judge identified target in word-id probe")
        notes = str(response.get("judge_notes", "")).lower()
        for tok in BANNED_REFS:
            if tok in notes:
                reasons.append(f"judge output references '{tok}'")
    return (bool(reasons), reasons)


# -------------------------------------------------------------- metrics + label -----
def score_case(response, keys):
    """Compute the D0 pairwise metrics from a validated response + hidden key."""
    if isinstance(response, str):
        response = json.loads(response)
    s = response["scores"]
    inv_comp = {arm: cid for cid, arm in keys["comp"].items()}
    inv_prof = {name: pid for pid, name in keys["prof"].items()}
    A, B, C = inv_comp["A"], inv_comp["B"], inv_comp["C"]
    tgt = inv_prof["target"]
    barnum_pids = [inv_prof[k] for k in _BARNUM]

    sA_t, sB_t, sC_t = s[A][tgt], s[B][tgt], s[C][tgt]
    best_barnum = max(s[A][b] for b in barnum_pids)
    # rank of the target profile among all profiles by composition A's scores (1 = best)
    ranked = sorted([tgt] + barnum_pids, key=lambda p: (-s[A][p], p))
    target_rank = ranked.index(tgt) + 1

    return {"s_A_target": sA_t, "A_vs_B": sA_t - sB_t, "A_vs_C": sA_t - sC_t,
            "best_barnum_for_A": best_barnum, "A_vs_maxBarnum": sA_t - best_barnum,
            "target_profile_rank_under_A": target_rank}


def assign_label(errors, contaminated, scored):
    """Assign a D0 pilot label. Never returns a forbidden/strict label."""
    if contaminated:
        return "LLM_PILOT_CONTAMINATED"          # overrides everything
    if errors:
        return "LLM_PILOT_INCONCLUSIVE"           # malformed / invalid response
    if scored is None:
        return "LLM_PILOT_INCONCLUSIVE"
    # failing Barnum alone forces NO_SIGNAL; also require beating scrambled + decoy
    if scored["A_vs_maxBarnum"] <= 0 or scored["A_vs_B"] <= 0 or scored["A_vs_C"] <= 0:
        return "LLM_PILOT_NO_SIGNAL"
    return "LLM_PILOT_SUGGESTIVE"


def process_case(case, seed=0):
    """Full per-case dry-run pipeline on TOY data. Returns a record; makes no LLM call."""
    _require_toy(case)
    packet, keys = build_packet(case, seed=seed)
    if "raw_response" in case:                    # e.g. malformed-JSON toy case
        response = case["raw_response"]
    else:
        response = synthesize_response(case["judge_behavior"], keys)
        # model a judge whose output leaked out-of-prompt knowledge (toy contamination case)
        if "inject_judge_notes" in case:
            response["judge_notes"] = case["inject_judge_notes"]
        if case.get("inject_contamination_identified"):
            response["contamination_identified"] = True
    errors = validate_response(response, packet)
    contaminated, reasons = detect_contamination(response if isinstance(response, dict) else {})
    scored = None if errors else score_case(response, keys)
    label = assign_label(errors, contaminated, scored)
    assert label in LABELS and label not in FORBIDDEN_LABELS
    return {"target_id": case.get("target_id"), TOY_MARK: True, "label": label,
            "errors": errors, "contamination": reasons, "metrics": scored}


def run_real_pilot(*args, **kwargs):
    """Intentionally NOT implemented — no real scoring path."""
    raise NotImplementedError(
        "Real D0 pilot requires explicit approval and an LLM-judge adapter (offline/pinned "
        "preferred). Not implemented. This module runs synthetic dry-runs only.")
