#!/usr/bin/env python3
"""B1.3 v3-authoritative judge RUNNER — reuses the B1.1 judge EXECUTION layer only.

Reuses from B1.1 (`run_b1_llm_judge.py`): the open-weight judge adapters (LlamaJudgeAdapter model loading /
call path + MockJudgeAdapter pattern), the declared open-weight panel + `validate_judge`, and the
structured-JSON/retry/refusal plumbing shape.

Does NOT reuse B1.1 arms, packet builder, prompt/choice vocabulary (output_1/output_2/tie/both_bad),
thresholds, terminal labels, or tie->0.5 semantics. B1.3 supplies its OWN blinded A/B packets, its OWN A/B
parser, and the FROZEN B1.3 scorer (`b1_3_revised_layer3/score_b1_3_concrete_object_llm.py`).

Hard guarantees:
  * NO model call unless `score-frozen` (real) or `probe-only --real` is explicitly requested on a model host.
  * `score-frozen` REFUSES unless the operator has explicitly declared EVIDENCE_FREEZE (a file this script
    never creates). It does not declare freeze, does not modify v3 stimuli, does not touch scorer thresholds,
    does not edit the authoritative lexicon, does not overwrite v2.
  * Track B stays BLOCKED. Structure, not validated meaning.

Modes:  probe-only (synthetic only) · freeze-check (hashes/config; no scoring) · score-frozen (post-freeze only)
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
B3 = HERE / "b1_3_revised_layer3"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(B3))

# ---- reuse the B1.1 judge EXECUTION plumbing (adapters / panel validation) ----
import run_b1_llm_judge as J   # LlamaJudgeAdapter, MockJudgeAdapter, validate_judge, DECLARED_JUDGES

DEFAULT_CONFIG = B3 / "b1_3_v3_b1_1_judge_runner_config.json"

# ---- B1.3 OWN judge prompt (forced A/B; NOT B1.1's output_1/output_2 vocabulary) ----
B13_SYSTEM = ("You are a careful annotator. Follow the instructions exactly. Answer with a single letter "
              "only, optionally followed by a confidence line. Do not explain.")
B13_PROMPT = (
    "Object: {target_word}\n"
    "Dictionary meaning: {dictionary_anchor}\n"
    "Context: {neutral_context}\n\n"
    "Option A: {option_A}\n"
    "Option B: {option_B}\n\n"
    "Question: Given the dictionary meaning of the object, which option gives a more fitting inner tendency "
    "or field around this object without changing what it is?\n\n"
    "Answer with exactly one letter: A or B. Optionally, on a second line, give a confidence from 1 (guess) "
    "to 5 (certain).")

# fields the judge may see; everything else (arms, keys, source, metadata, provenance) is hidden
JUDGE_FACING = ("target_word", "dictionary_anchor", "neutral_context", "option_A", "option_B")
FORBIDDEN_IN_PACKET = ("a_real", "r_deranged", "r_scrambled", "r_random", "x_neutral", "semantic_only",
                       "arm_left", "arm_right", "source_metadata", "deranged_source", "authoritative",
                       "_v2", "_v3", "generation_seed", "position_seed")
# B1.1 tie/preference vocabulary that the B1.3 parser must REJECT (no tie->0.5 reuse)
B1_1_CHOICE_TOKENS = ("output_1_better", "output_2_better", "tie_no_preference", "both_bad")


def sha256_file(p):
    try:
        return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
    except OSError:
        return None


def load_config(path=DEFAULT_CONFIG):
    return json.loads(pathlib.Path(path).read_text())


# ---------------------------------------------------------------- packets (B1.3 OWN, blinded) --------
def build_packets(stimuli_rows):
    """Return (public_packets, private_map). Public packet carries ONLY judge-facing fields + an opaque
    packet_id. Private map links packet_id -> scoring truth (arms, ids). Judge never sees the private map."""
    public, private = [], {}
    for r in stimuli_rows:
        pid = hashlib.sha256(f"{r['item_id']}|{r['comparison_id']}".encode()).hexdigest()[:16]
        public.append({
            "packet_id": pid,
            "target_word": r["target_word"],
            "dictionary_anchor": r["dictionary_anchor"],
            "neutral_context": r["neutral_context"],
            "option_A": r["option_left"],
            "option_B": r["option_right"],
        })
        private[pid] = {
            "item_id": r["item_id"], "comparison_id": r["comparison_id"], "target_word": r["target_word"],
            "primary_or_secondary_or_diagnostic": r.get("primary_or_secondary_or_diagnostic", "primary"),
            "object_family": r.get("object_family"), "deranged_stratum": r.get("deranged_stratum"),
            # arm_left/arm_right map to Option A / Option B respectively (option_left/right)
            "arm_left": r["arm_left"], "arm_right": r["arm_right"],
        }
    return public, private


def leak_scan(packet):
    """Return list of blinding violations in a public packet."""
    bad = []
    for k in packet:
        if k not in JUDGE_FACING and k != "packet_id":
            bad.append(f"unexpected_field:{k}")
    blob = json.dumps({k: packet[k] for k in packet if k != "packet_id"}).lower()
    for tok in FORBIDDEN_IN_PACKET:
        if tok in blob:
            bad.append(f"forbidden_substring:{tok}")
    return bad


def build_b13_prompt(packet):
    return B13_PROMPT.format(**{k: packet[k] for k in JUDGE_FACING})


# ---------------------------------------------------------------- B1.3 A/B parser --------------------
def parse_ab(text):
    """B1.3 parser: allowed choices A|B (+ optional confidence 1-5). Rejects B1.1 tie/preference vocabulary,
    malformed, refusals. NO tie->0.5. Returns dict(selected_option, confidence, parse_status, invalid_flag)."""
    if text is None:
        return {"selected_option": None, "confidence": None, "parse_status": "unparseable", "invalid_flag": True}
    low = text.strip().lower()
    if not low:
        return {"selected_option": None, "confidence": None, "parse_status": "unparseable", "invalid_flag": True}
    # explicit rejection of B1.1 tie/preference semantics
    if any(tok in low for tok in B1_1_CHOICE_TOKENS):
        return {"selected_option": None, "confidence": None, "parse_status": "malformed", "invalid_flag": True}
    # refusal heuristic
    if any(p in low for p in ("i can't", "i cannot", "i won't", "i will not", "as an ai", "i'm not able")):
        return {"selected_option": None, "confidence": None, "parse_status": "refused", "invalid_flag": True}
    # first standalone A or B token
    sel = None
    import re
    m = re.search(r"\b([ab])\b", low)
    if m:
        sel = m.group(1).upper()
    if sel not in ("A", "B"):
        return {"selected_option": None, "confidence": None, "parse_status": "malformed", "invalid_flag": True}
    conf = None
    mc = re.search(r"confidence\D*([1-5])", low) or re.search(r"\n\s*([1-5])\s*$", low)
    if mc:
        conf = int(mc.group(1))
    return {"selected_option": sel, "confidence": conf, "parse_status": "ok", "invalid_flag": False}


# ---------------------------------------------------------------- B1.3 mock adapter (no model) -------
class B13MockAdapter:
    """No-model adapter emitting B1.3-format A/B (reuses the adapter PATTERN, not B1.1 mock output)."""
    is_real = False

    def __init__(self, judge_id):
        self.judge_id = J.validate_judge(judge_id)   # reuse B1.1 panel-membership validation
        self.calls = 0

    def judge_raw(self, prompt, packet):
        self.calls += 1
        # deterministic, content-free: pick A. (No study inference; probe/tests only.)
        return "A\nconfidence: 3"


# ---------------------------------------------------------------- hash / freeze verification ---------
def verify_hashes(manifest_path):
    man = json.loads(pathlib.Path(manifest_path).read_text())
    bound = man.get("active_freeze_artifacts_sha256", {})
    mismatches = {}
    for name, expect in bound.items():
        actual = sha256_file(B3 / name)
        if actual != expect:
            mismatches[name] = {"expected": expect, "actual": actual}
    return (len(mismatches) == 0), mismatches, list(bound)


def freeze_declared():
    """The operator's explicit EVIDENCE_FREEZE declaration file. This script NEVER creates it."""
    decl = B3 / "b1_3_v3_EVIDENCE_FREEZE_DECLARED.json"
    if not decl.exists():
        return False, "no EVIDENCE_FREEZE declaration file present"
    try:
        d = json.loads(decl.read_text())
    except Exception as e:
        return False, f"declaration unreadable: {e}"
    if d.get("evidence_freeze_declared") is not True:
        return False, "declaration present but evidence_freeze_declared != true"
    return True, "operator declaration present"


# ---------------------------------------------------------------- modes ------------------------------
SYNTHETIC_PROBE_PACKETS = [
    {"packet_id": "probe_widget_1", "target_word": "widget",
     "dictionary_anchor": "a small made-up gadget used only for testing",
     "neutral_context": "Consider the ordinary object \"widget\" in a plain, everyday sentence.",
     "option_A": "Within the fixed meaning, this object is modulated by alpha, beta, gamma, and delta.",
     "option_B": "Within the fixed meaning, this object is modulated by one, two, three, and four."},
    {"packet_id": "probe_gizmo_1", "target_word": "gizmo",
     "dictionary_anchor": "a made-up device with no real function",
     "neutral_context": "Consider the ordinary object \"gizmo\" in a plain, everyday sentence.",
     "option_A": "Within the fixed meaning, this object is modulated by north, south, east, and west.",
     "option_B": "Within the fixed meaning, this object is modulated by red, green, blue, and grey."},
]


def mode_probe_only(config, real=False, verbose=True):
    """Synthetic-only A/B compliance probe per declared judge. No real B1.3 items."""
    ids = config["judge_model_ids"]
    results = {}
    for jid in ids:
        adapter = J.LlamaJudgeAdapter(jid) if real else B13MockAdapter(jid)
        ok = mal = 0
        for pk in SYNTHETIC_PROBE_PACKETS:
            raw = adapter.judge_raw(build_b13_prompt(pk), pk)
            p = parse_ab(raw)
            if p["invalid_flag"]:
                mal += 1
            else:
                ok += 1
        results[jid] = {"family": config["judge_families"].get(jid, "unknown"),
                        "n": len(SYNTHETIC_PROBE_PACKETS), "compliant": ok, "invalid": mal,
                        "adapter": "real" if real else "mock"}
        if verbose:
            print(f"probe {jid}: compliant {ok}/{len(SYNTHETIC_PROBE_PACKETS)} invalid {mal}")
    return {"mode": "probe-only", "synthetic_only": True, "real_model_call": real, "results": results}


def mode_freeze_check(config, verbose=True):
    man_path = B3 / config["v3_freeze_manifest"]
    hashes_ok, mismatches, bound = verify_hashes(man_path)
    src = json.loads((B3 / "b1_3_v3_authoritative_source_audit.json").read_text())
    src_ok = (src.get("decision") == "V3_AUTHORITATIVE_SOURCE_AUDIT_PASS")
    judges_declared = list(J.DECLARED_JUDGES)
    ids_ok = all(j in judges_declared for j in config["judge_model_ids"])
    scorer_present = (B3 / "score_b1_3_concrete_object_llm.py").exists()
    out = {"mode": "freeze-check", "hashes_ok": hashes_ok, "n_bound": len(bound),
           "hash_mismatches": mismatches, "v3_source_audit_pass": src_ok,
           "judge_ids_in_declared_panel": ids_ok, "declared_panel": judges_declared,
           "scorer_present": scorer_present, "scored": False,
           "ready": bool(hashes_ok and src_ok and ids_ok and scorer_present)}
    if verbose:
        print(json.dumps({k: out[k] for k in ("hashes_ok", "v3_source_audit_pass",
                          "judge_ids_in_declared_panel", "scorer_present", "ready")}, indent=1))
    return out


def mode_score_frozen(config, real=False):
    ok, why = freeze_declared()
    if not ok:
        raise SystemExit(f"score-frozen REFUSED: {why}. EVIDENCE_FREEZE not declared by operator. "
                         "This runner never declares freeze. Nothing run or scored. Track B BLOCKED.")
    # (post-freeze path — not reachable in this repo; no declaration file exists)
    hashes_ok, mismatches, _ = verify_hashes(B3 / config["v3_freeze_manifest"])
    if not hashes_ok:
        raise SystemExit(f"score-frozen REFUSED: artifact hash mismatch after freeze: {mismatches}")
    raise SystemExit("score-frozen path guarded: refusing to auto-run the 371-comparison study in this "
                     "environment. Run on a model host with the runbook after an explicit operator freeze.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="B1.3 v3-authoritative runner (B1.1 judge execution layer).")
    ap.add_argument("--mode", choices=["probe-only", "freeze-check", "score-frozen"], default="probe-only")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--real", action="store_true", help="use real models (probe-only/score-frozen on a model host)")
    a = ap.parse_args(argv)
    config = load_config(a.config)
    if a.mode == "probe-only":
        r = mode_probe_only(config, real=a.real)
    elif a.mode == "freeze-check":
        r = mode_freeze_check(config)
    else:
        r = mode_score_frozen(config, real=a.real)
    print(json.dumps({"mode": a.mode, "evidence_freeze_declared": False, "track_b": "BLOCKED"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
