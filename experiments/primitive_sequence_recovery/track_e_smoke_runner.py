"""Track E smoke-pilot runner — DRY-RUN packet machinery + HARD refusal gates (no run).

Builds anonymized scorer packets for the six flat-design arms (A real boundary, B scrambled,
X context-only, F etymology-only, D dictionary-only, I Barnum), a SEPARATE hidden answer key, a
leak scanner, refusal gates, and validation for INGESTING externally-produced scorer JSON — then
reuses `track_e_harness` for the metrics/labels. It makes NO model/network calls and performs NO
real scoring. Real execution refuses unless an explicit, fully-approved config is supplied; the
smoke bundle ships `run_enabled:false` / `approval_status:"NOT_APPROVED"`, so it always refuses.

Guardrails: four-sphere JSON is never loaded/referenced. `frozen/manifest.json` is never touched.
Only the seven Track E `ALLOWED_LABELS` can ever be emitted; forbidden labels are asserted against.
Track B remains BLOCKED. See TRACK_E_SMOKE_*.md.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import random
import re

import track_e_harness as H   # metrics + labels + constants (ARMS_REQUIRED, ALLOWED_LABELS, ...)

HERE = pathlib.Path(__file__).resolve().parent

MANIFEST_NAME = "track_e_smoke_manifest.json"
SEEDS_NAME = "track_e_smoke_seeds.json"
REQUIRED_FILES = ("track_e_smoke_words.jsonl", "track_e_smoke_contexts.jsonl",
                  "track_e_smoke_candidates.jsonl", "track_e_smoke_etymology.jsonl",
                  "track_e_smoke_boundaries.jsonl", "track_e_smoke_barnum.json", SEEDS_NAME)
REQUIRED_SEEDS = ("candidate_shuffle", "boundary_scramble", "packet_order", "barnum_variant_order")

ARMS = H.ARMS_REQUIRED                      # ("A","B","X","F","D","I")
ARMS_WITH_CONTEXT = {"A", "B", "X", "F", "I"}
ARMS_WITH_CONSTRAINT = {"A", "B", "F", "I"}   # D uses a "reference meaning" instead; X has neither

# ---- leak vocabulary (scorer-facing fields must contain none of these) --------------
VARNA_KEYS = ("ka", "kha", "ga", "gha", "nga", "ca", "cha", "ja", "jha", "nya", "tta", "ttha",
              "dda", "ddha", "nna", "ta", "tha", "da", "dha", "na", "pa", "pha", "ba", "bha",
              "ma", "ya", "ra", "la", "va", "sha", "ssa", "sa", "ha", "ksha")
ROOT_NAMES = ("moha", "bhaya", "kama", "krodha", "sukha", "hrdaya", "shanti", "bala", "buddhi",
              "nadi", "parvata", "grha", "dharma", "trishna", "lobha", "moksha", "kshiti",
              "agni", "prana", "artha", "dhrti")
ROLE_MARKERS = ("context_correct", "hard_negative", "dict_valid_context_wrong",
                "barnum_compatible", "barnum", "dict_wrong")
ARM_TOKENS = ("boundary_real", "boundary_scrambled", "scrambled_boundary", "real_boundary",
              "etymology_only", "dictionary_only", "barnum_boundary", "context_only", "true_arm",
              "a_real_boundary", "b_scrambled")
FOUR_SPHERE_TOKENS = ("sphere", "four_sphere", "sphere_lexicon")

SCORER_INSTRUCTIONS = (
    "You are given a premise and a numbered list of candidate meanings. For each candidate, output "
    "a score in [0,1] for how well it fits the premise. Respond with JSON ONLY, no prose: "
    '{"packet_id": "<id>", "scores": {"opt_1": 0.0, ...}, "chosen": "opt_k"}.')


class RefusedRun(RuntimeError):
    """Raised (loudly) when a real execution path is attempted without full approval."""


class LeakDetected(ValueError):
    """Raised (loudly) when a scorer-facing field contains a forbidden token."""


class MalformedScorerOutput(ValueError):
    """Raised (loudly) for invalid / unknown / duplicate scorer output."""


# ======================================================================= loading =====
def _read_jsonl(path):
    return [json.loads(l) for l in pathlib.Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def load_manifest(bundle_dir=HERE, *, check_hashes=True):
    """Load + structurally validate the smoke manifest. Does NOT authorize any run."""
    bundle_dir = pathlib.Path(bundle_dir)
    man = json.loads((bundle_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    if man.get("bundle_type") != "track_e_smoke_input_bundle":
        raise ValueError("bundle_type mismatch")
    if man.get("representation") != "flat_boundary_constraint":
        raise ValueError("representation must be flat_boundary_constraint")
    if man.get("four_sphere_integrated") is not False:
        raise ValueError("four_sphere_integrated must be false")
    if "run_enabled" not in man or not isinstance(man["run_enabled"], bool):
        raise ValueError("run_enabled missing/!bool")
    if "approval_status" not in man:
        raise ValueError("approval_status missing")
    for f in REQUIRED_FILES + (MANIFEST_NAME,):
        if not (bundle_dir / f).exists():
            raise ValueError(f"missing bundle file: {f}")
    if check_hashes and man.get("hashes"):
        for name, want in man["hashes"].items():
            got = hashlib.sha256((bundle_dir / name).read_bytes()).hexdigest()
            if got != want:
                raise ValueError(f"hash mismatch for {name}")
    return man


def load_bundle(bundle_dir=HERE):
    bundle_dir = pathlib.Path(bundle_dir)
    man = load_manifest(bundle_dir)
    seeds = json.loads((bundle_dir / SEEDS_NAME).read_text(encoding="utf-8"))["seeds"]
    by = lambda rows: {r["word_id"]: r for r in rows}
    return {
        "dir": bundle_dir, "manifest": man, "seeds": seeds,
        "words": by(_read_jsonl(bundle_dir / "track_e_smoke_words.jsonl")),
        "contexts": by(_read_jsonl(bundle_dir / "track_e_smoke_contexts.jsonl")),
        "candidates": by(_read_jsonl(bundle_dir / "track_e_smoke_candidates.jsonl")),
        "etymology": by(_read_jsonl(bundle_dir / "track_e_smoke_etymology.jsonl")),
        "boundaries": by(_read_jsonl(bundle_dir / "track_e_smoke_boundaries.jsonl")),
        "barnum": json.loads((bundle_dir / "track_e_smoke_barnum.json").read_text(encoding="utf-8")),
    }


# ================================================================= dry-run packets ===
def _opaque_id(case, arm, variant, seed):
    h = hashlib.sha1(f"{seed}|{case}|{arm}|{variant}".encode()).hexdigest()
    return "pkt_" + h[:16]


def _shuffle_candidates(cands, case, arm, variant, seed):
    """Shuffle authored candidates; GUARANTEE the order differs from authored; return
    (packet_candidates[opt_*], authored_order, shuffled_order, opt_to_cand)."""
    authored = [c["candidate_id"] for c in cands]
    order = list(range(len(cands)))
    salt = 0
    while True:
        random.Random(f"{seed}|{case}|{arm}|{variant}|{salt}").shuffle(order)
        shuffled = [cands[k]["candidate_id"] for k in order]
        if shuffled != authored:
            break
        salt += 1
    packet_cands, opt_to_cand = [], {}
    for i, k in enumerate(order, 1):
        opt = f"opt_{i}"
        packet_cands.append({"candidate_id": opt, "text": cands[k]["gloss"]})
        opt_to_cand[opt] = cands[k]["candidate_id"]
    return packet_cands, authored, shuffled, opt_to_cand


def _premise(arm, word, ctx, boundary, etym, barnum_text):
    parts = []
    if arm in ARMS_WITH_CONTEXT:
        parts.append(ctx["context_sentence"])
    if arm == "A":
        parts.append("Consider this internal constraint: " + boundary["boundary_real_description"])
    elif arm == "B":
        parts.append("Consider this internal constraint: " + boundary["boundary_scrambled_description"])
    elif arm == "F":
        parts.append("Consider this internal constraint: " + etym["etymology_prior_description"])
    elif arm == "I":
        parts.append("Consider this internal constraint: " + barnum_text)
    elif arm == "D":
        parts.append("Consider this reference meaning: " + word["broad_gloss"])
    return " ".join(parts)


def build_packets(bundle):
    """Build anonymized scorer packets for all arms + a SEPARATE hidden key. No model calls."""
    seeds = bundle["seeds"]
    cshuffle, porder = seeds["candidate_shuffle"], seeds["packet_order"]
    barnum_family = sorted(bundle["barnum"]["family"].items())     # deterministic order
    packets, hidden = [], []
    for wid, word in bundle["words"].items():
        ctx = bundle["contexts"][wid]
        cands = bundle["candidates"][wid]["candidates"]
        etym = bundle["etymology"][wid]
        boundary = bundle["boundaries"][wid]
        correct = ctx["context_correct_candidate_id"]
        for arm in ARMS:
            variants = barnum_family if arm == "I" else [("_", None)]
            for vkey, vtext in variants:
                pc, authored, shuffled, o2c = _shuffle_candidates(cands, wid, arm, vkey, cshuffle)
                pid = _opaque_id(wid, arm, vkey, porder)
                premise = _premise(arm, word, ctx, boundary, etym, vtext)
                packet = {"packet_id": pid, "instructions": SCORER_INSTRUCTIONS,
                          "premise": premise, "candidates": pc}
                packets.append(packet)
                hidden.append({"packet_id": pid, "case_id": wid, "true_arm": arm,
                               "barnum_variant": (vkey if arm == "I" else None),
                               "correct_candidate_id": correct,
                               "authored_order": authored, "shuffled_order": shuffled,
                               "opt_to_cand": o2c,
                               "exploratory_only": bool(word.get("exploratory_only"))})
    return packets, hidden


# ===================================================================== leak scanner ==
def _scorer_facing_strings(packet):
    out = [packet.get("premise", ""), packet.get("instructions", "")]
    out += [c.get("text", "") for c in packet.get("candidates", [])]
    out += [c.get("candidate_id", "") for c in packet.get("candidates", [])]
    return [s for s in out if isinstance(s, str)]


def scan_packet(packet, *, surface_word=None, root_terms=(), authored_ids=()):
    """Hard-fail (LeakDetected) if any scorer-facing string leaks a forbidden token."""
    blob_cs = " \n ".join(_scorer_facing_strings(packet))     # case-sensitive view
    blob = blob_cs.lower()
    if surface_word and re.search(r"\b" + re.escape(surface_word.lower()) + r"\b", blob):
        raise LeakDetected(f"surface word leak: {surface_word!r}")
    for grp, toks in (("root", tuple(root_terms) + ROOT_NAMES), ("role", ROLE_MARKERS),
                      ("arm", ARM_TOKENS), ("four_sphere", FOUR_SPHERE_TOKENS)):
        for t in toks:
            if t and re.search(r"\b" + re.escape(t.lower()) + r"\b", blob):
                raise LeakDetected(f"{grp} token leak: {t!r}")
    for vk in VARNA_KEYS:
        if re.search(r"\b" + re.escape(vk) + r"\b", blob):
            raise LeakDetected(f"varna key leak: {vk!r}")
    for lab in H.BANNED_REAL + H.FORBIDDEN_LABELS:
        if lab.lower() in blob:
            raise LeakDetected(f"banned/forbidden token leak: {lab!r}")
    # authored candidate ids (cand_*) and the correct id must never appear (packets use opt_*)
    for cid in authored_ids:
        if re.search(r"\b" + re.escape(cid.lower()) + r"\b", blob):
            raise LeakDetected(f"authored candidate id leak: {cid!r}")
    # structured arm-code leak: an arm identifier next to a code, e.g. "arm A", "arm_b",
    # "true_arm: X" (precise, so prose like "inflated I-feeling" or "an army" does not trip it).
    if re.search(r"\b(?:true_)?arm[\s_:=-]*['\"]?[abxfdi]\b", blob):
        raise LeakDetected("arm-code leak")
    return True


def dry_run(bundle_dir=HERE, *, preview_path=None):
    """Full dry run: build packets + hidden key, leak-scan every packet, verify shuffles.
    Optionally write a redacted packet-preview report. NO model calls, NO scoring."""
    bundle = load_bundle(bundle_dir)
    packets, hidden = build_packets(bundle)
    hkey = {h["packet_id"]: h for h in hidden}
    leaks, shuffle_ok = 0, True
    for p in packets:
        h = hkey[p["packet_id"]]
        word = bundle["words"][h["case_id"]]
        # leak surface = the Sanskrit surface word (checked as a substring) + the global Sanskrit
        # ROOT_NAMES list (scanned inside scan_packet). The English dev_root gloss is a hidden dev
        # field, never packetized, so it is not a leak vocabulary.
        scan_packet(p, surface_word=word.get("dev_surface_word"),
                    authored_ids=[c["candidate_id"] for c in bundle["candidates"][h["case_id"]]["candidates"]])
        if h["shuffled_order"] == h["authored_order"]:
            shuffle_ok = False
    report = {"n_packets": len(packets), "n_cases": len(bundle["words"]), "arms": list(ARMS),
              "leak_scan": "clean", "all_shuffled_differ_from_authored": shuffle_ok,
              "model_calls": 0, "scored": False,
              "note": "dry-run preview only; no model calls; not a run; not scoring."}
    if preview_path:
        pathlib.Path(preview_path).write_text(json.dumps(
            {"report": report, "packets": packets}, ensure_ascii=False, indent=2), encoding="utf-8")
    return report, packets, hidden


# ===================================================================== refusal gates =
def gate_failures(manifest, seeds, approval, *, leak_ok, shuffle_ok):
    """Return the list of unmet gates. Empty list => a real run would be permitted."""
    f = []
    if manifest.get("run_enabled") is not True:
        f.append("run_enabled is not true")
    if manifest.get("approval_status") != "APPROVED":
        f.append("approval_status is not APPROVED")
    if not (approval or {}).get("generator_model"):
        f.append("generator_model not set")
    if not (approval or {}).get("scorer_model"):
        f.append("scorer_model not set")
    for s in REQUIRED_SEEDS:
        if not isinstance((seeds or {}).get(s), int):
            f.append(f"seed not set: {s}")
    if not leak_ok:
        f.append("leak scan did not pass")
    if not shuffle_ok:
        f.append("packet shuffle verification did not pass")
    if not ((approval or {}).get("approval_signature") and (approval or {}).get("approval_date")):
        f.append("approval signature/date missing")
    return f


def run_real_smoke_pilot(bundle_dir=HERE, approval=None):
    """Real entrypoint. REFUSES unless every gate passes. Never calls a model (scoring is external
    via ingest_scorer_outputs). As shipped the bundle refuses (run_enabled:false / NOT_APPROVED)."""
    bundle = load_bundle(bundle_dir)
    try:
        report, packets, hidden = dry_run(bundle_dir)
        leak_ok, shuffle_ok = True, report["all_shuffled_differ_from_authored"]
    except LeakDetected:
        leak_ok, shuffle_ok, packets, hidden = False, False, [], []
    fails = gate_failures(bundle["manifest"], bundle["seeds"], approval,
                          leak_ok=leak_ok, shuffle_ok=shuffle_ok)
    if fails:
        raise RefusedRun("real Track E smoke run refused; unmet gates: " + "; ".join(fails))
    # Gates satisfied (only under an explicit approved config): emit real packets for EXTERNAL
    # scoring. Still no model call here — scores are ingested via ingest_scorer_outputs().
    return {"status": "PACKETS_EMITTED_FOR_EXTERNAL_SCORING", "packets": packets, "hidden": hidden}


# =========================================================== scorer-output ingestion =
def validate_scorer_output(obj, *, packet_opts, seen):
    """Validate one external scorer JSON object. Raises MalformedScorerOutput loudly. No model call."""
    if not isinstance(obj, dict):
        raise MalformedScorerOutput("output is not an object")
    pid = obj.get("packet_id")
    if not isinstance(pid, str) or pid not in packet_opts:
        raise MalformedScorerOutput(f"unknown packet_id: {pid!r}")
    if pid in seen:
        raise MalformedScorerOutput(f"duplicate packet_id: {pid!r}")
    scores = obj.get("scores")
    opts = set(packet_opts[pid])
    if not isinstance(scores, dict) or set(scores) != opts:
        raise MalformedScorerOutput(f"scores keys must equal packet opts for {pid}")
    for k, v in scores.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not (0.0 <= v <= 1.0):
            raise MalformedScorerOutput(f"non-numeric/out-of-range score {k}={v!r} in {pid}")
    chosen = obj.get("chosen")
    if chosen not in opts:
        raise MalformedScorerOutput(f"chosen not a valid opt in {pid}")
    for s in (str(v) for v in obj.values() if isinstance(v, str)):
        low = s.lower()
        if any(b.lower() in low for b in H.BANNED_REAL + H.FORBIDDEN_LABELS) or "sphere" in low:
            raise MalformedScorerOutput(f"contamination text in {pid}: {s!r}")
    seen.add(pid)
    return True


def ingest_scorer_outputs(outputs, hidden):
    """Validate a list of external scorer outputs against the hidden key. Returns {pid: scores}."""
    hkey = {h["packet_id"]: h for h in hidden}
    packet_opts = {pid: list(h["opt_to_cand"].keys()) for pid, h in hkey.items()}
    seen, out = set(), {}
    for o in outputs:
        validate_scorer_output(o, packet_opts=packet_opts, seen=seen)
        out[o["packet_id"]] = o["scores"]
    return out


def _assemble_items(bundle, hidden, scores_by_pid):
    hkey = {h["packet_id"]: h for h in hidden}
    per_case = {}
    for pid, h in hkey.items():
        if pid not in scores_by_pid:
            raise MalformedScorerOutput(f"no scores for packet {pid}")
        cand_scores = {h["opt_to_cand"][opt]: v for opt, v in scores_by_pid[pid].items()}
        d = per_case.setdefault(h["case_id"], {"arms": {}, "correct": h["correct_candidate_id"]})
        if h["true_arm"] == "I":                       # arm I = max over Barnum variants
            agg = d["arms"].setdefault("I", {})
            for c, v in cand_scores.items():
                agg[c] = max(agg.get(c, 0.0), v)
        else:
            d["arms"][h["true_arm"]] = cand_scores
    items = []
    for wid, d in per_case.items():
        for a in ARMS:
            if a not in d["arms"]:
                raise MalformedScorerOutput(f"case {wid} missing arm {a}")
        cids = [c["candidate_id"] for c in bundle["candidates"][wid]["candidates"]]
        items.append({"candidates": [{"candidate_id": c} for c in cids],
                      "context_correct": d["correct"], "arm_scores": d["arms"]})
    return items


def score_from_outputs(bundle, hidden, outputs):
    """Ingest external scorer outputs and reuse track_e_harness for metrics + a label.
    Scores are supplied IN; this makes no model call and performs no real scoring itself."""
    scores_by_pid = ingest_scorer_outputs(outputs, hidden)
    items = _assemble_items(bundle, hidden, scores_by_pid)
    metrics = H.arm_metrics(items)
    label = H.decide(metrics)
    assert label in H.ALLOWED_LABELS and label not in H.FORBIDDEN_LABELS, label
    return {"label": label, "mrr": {a: round(metrics[a]["mrr"], 4) for a in ARMS},
            "top1": {a: round(metrics[a]["top1"], 4) for a in ARMS},
            "deltas": {k: round(v, 4) for k, v in H.deltas(metrics).items()},
            "n_cases": len(items),
            "note": "labels are MECHANICS over supplied scores; a real result requires an "
                    "approved run + bootstrap CIs + seed stability (not done here)."}


if __name__ == "__main__":
    r, _, _ = dry_run()
    print(json.dumps(r, indent=2))
    print("run_real_smoke_pilot would REFUSE:",
          "; ".join(gate_failures(load_manifest(), load_bundle()["seeds"], None,
                                  leak_ok=True, shuffle_ok=True)))
