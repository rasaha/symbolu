"""Track G smoke runner — DRY-RUN packet machinery + hard refusal gates (no model calls).

Builds anonymized scorer packets for the six polarity arms (A real / R random-flip / B scrambled /
I Barnum / X context-only / D dictionary-only), a SEPARATE hidden key, and a leak scanner. It makes
NO model calls and performs NO scoring. A real run refuses unless a separate approved run config and
env token are supplied; the base smoke manifest ships run_enabled:false / NOT_APPROVED, so it always
refuses. Scoring is external (fed back through track_g_harness). Four-sphere JSON is never loaded.
Track B remains BLOCKED. See TRACK_G_* docs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import random
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import track_g_harness as HG   # noqa: E402

MANIFEST = HERE / "track_g_smoke_manifest.json"
CONFIG_PATH = HERE / "track_g_smoke_approved_run_config.json"
APPROVAL_ENV = "TRACK_G_SMOKE_RUN_APPROVED"
APPROVAL_TOKEN = "I_APPROVE_TRACK_G_SMOKE"
ARMS = HG.ARMS_REQUIRED
ARMS_WITH_CONTEXT = {"A", "R", "B", "I", "X"}      # D is dictionary-only (no context)

VARNA_KEYS = ("ka", "kha", "ga", "gha", "nga", "ca", "cha", "ja", "jha", "nya", "tta", "ttha",
              "dda", "ddha", "nna", "ta", "tha", "da", "dha", "na", "pa", "pha", "ba", "bha",
              "ma", "ya", "ra", "la", "va", "sha", "ssa", "sa", "ha", "ksha")
ROOT_NAMES = ("moha", "bhaya", "kama", "krodha", "sukha", "shanti", "bala", "buddhi", "moksha",
              "raga", "prabha", "shama", "trishna", "lobha", "dharma")
ROLE_MARKERS = ("target", "opposite_pole", "hard_negative", "barnum_compatible",
                "dict_valid_polarity_wrong")
POLARITY_DIRECTION_TOKENS = ("expected_pole", "expected_relation", "assigned_before_scoring")
INSTRUCTIONS = ('For each candidate meaning, output a score in [0,1] for how well it fits. Respond '
                'with JSON ONLY: {"packet_id": "<id>", "scores": {"opt_1": 0.0, ...}, "chosen": "opt_k"}.')


class LeakDetected(ValueError):
    pass


class RefusedRun(RuntimeError):
    pass


def _read_jsonl(p):
    return [json.loads(l) for l in pathlib.Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def load_bundle(bundle_dir=HERE):
    bundle_dir = pathlib.Path(bundle_dir)
    man = json.loads((bundle_dir / "track_g_smoke_manifest.json").read_text(encoding="utf-8"))
    if man.get("bundle_type") != "track_g_input_bundle" or man.get("four_sphere_integrated") is not False:
        raise ValueError("bad Track G manifest")
    by = lambda rows, k: {r[k]: r for r in rows}
    return {"dir": bundle_dir, "manifest": man, "seeds": man["seeds"],
            "words": by(_read_jsonl(bundle_dir / "track_g_smoke_words.jsonl"), "word_id"),
            "contexts": by(_read_jsonl(bundle_dir / "track_g_smoke_contexts.jsonl"), "context_id"),
            "candidates": by(_read_jsonl(bundle_dir / "track_g_smoke_candidates.jsonl"), "case_id"),
            "assignments": by(_read_jsonl(bundle_dir / "track_g_polarity_assignments.jsonl"), "case_id"),
            "boundaries": by(_read_jsonl(bundle_dir / "track_g_smoke_boundaries.jsonl"), "case_id"),
            "barnum": json.loads((bundle_dir / "track_g_barnum_polarity.json").read_text(encoding="utf-8"))}


# ---------------------------------------------------------- dry-run packets ---------
def _pid(case_id, arm, variant, seed):
    return "gpkt_" + hashlib.sha1(f"{seed}|{case_id}|{arm}|{variant}".encode()).hexdigest()[:16]


def _shuffle(cands, case_id, arm, variant, seed):
    order = list(range(len(cands)))
    salt = 0
    authored = [c["candidate_id"] for c in cands]
    while True:
        random.Random(f"{seed}|{case_id}|{arm}|{variant}|{salt}").shuffle(order)
        shuffled = [cands[i]["candidate_id"] for i in order]
        if shuffled != authored:
            break
        salt += 1
    pc, o2c = [], {}
    for i, k in enumerate(order, 1):
        pc.append({"candidate_id": f"opt_{i}", "gloss": cands[k]["gloss"]})
        o2c[f"opt_{i}"] = cands[k]["candidate_id"]
    return pc, authored, shuffled, o2c


def _premise(arm, ctx, boundary, dict_desc, barnum_text):
    parts = []
    if arm in ARMS_WITH_CONTEXT:
        parts.append(ctx["context_sentence"])
    if arm == "A":
        parts.append(boundary["polarity_real_desc"])
    elif arm == "B":
        parts.append(boundary["polarity_scrambled_desc"])
    elif arm == "R":
        parts.append(boundary["polarity_random_flip_desc"])
    elif arm == "I":
        parts.append(barnum_text)
    elif arm == "D":
        parts.append(dict_desc)
    return " ".join(parts)


def build_packets(bundle):
    seeds = bundle["seeds"]
    barnum_family = sorted(bundle["barnum"]["family"].items())
    packets, hidden = [], []
    for cid, cand in bundle["candidates"].items():
        ctx = bundle["contexts"][cid]
        boundary = bundle["boundaries"][cid]
        cands = cand["candidates"]
        for arm in ARMS:
            variants = barnum_family if arm == "I" else [("_", None)]
            for vkey, vtext in variants:
                pc, authored, shuffled, o2c = _shuffle(cands, cid, arm, vkey, seeds["candidate_shuffle"])
                pid = _pid(cid, arm, vkey, seeds["packet_order"])
                packets.append({"packet_id": pid, "instructions": INSTRUCTIONS,
                                "premise": _premise(arm, ctx, boundary, boundary["dictionary_only_desc"], vtext),
                                "candidates": pc})
                hidden.append({"packet_id": pid, "case_id": cid, "true_arm": arm,
                               "barnum_variant": (vkey if arm == "I" else None),
                               "target_id": cand["target"], "authored_order": authored,
                               "shuffled_order": shuffled, "opt_to_cand": o2c})
    rng = random.Random(seeds["packet_order"])
    idx = list(range(len(packets)))
    rng.shuffle(idx)
    packets = [packets[i] for i in idx]
    return packets, {h["packet_id"]: h for h in hidden}


def _facing(packet):
    out = [packet.get("premise", ""), packet.get("instructions", "")]
    out += [c.get("gloss", "") for c in packet.get("candidates", [])]
    out += [c.get("candidate_id", "") for c in packet.get("candidates", [])]
    return [s for s in out if isinstance(s, str)]


def scan_packet(packet, surface_word, authored_ids):
    blob = " \n ".join(_facing(packet)).lower()
    if surface_word and re.search(r"\b" + re.escape(surface_word.lower()) + r"\b", blob):
        raise LeakDetected(f"surface leak {surface_word!r}")
    for grp, toks in (("root", ROOT_NAMES), ("role", ROLE_MARKERS),
                      ("polarity_dir", POLARITY_DIRECTION_TOKENS)):
        for t in toks:
            if re.search(r"\b" + re.escape(t) + r"\b", blob):
                raise LeakDetected(f"{grp} leak {t!r}")
    for vk in VARNA_KEYS:
        if re.search(r"\b" + re.escape(vk) + r"\b", blob):
            raise LeakDetected(f"varna leak {vk!r}")
    if "sphere" in blob:
        raise LeakDetected("four-sphere reference")
    for lab in HG.BANNED_REAL + HG.FORBIDDEN_LABELS:
        if lab.lower() in blob:
            raise LeakDetected(f"banned/forbidden {lab!r}")
    for cid in authored_ids:
        if re.search(r"\b" + re.escape(cid.lower()) + r"\b", blob):
            raise LeakDetected(f"authored candidate id leak {cid!r}")
    if re.search(r"\b(?:true_)?arm[\s_:=-]*['\"]?[arbixd]\b", blob):
        raise LeakDetected("arm-label leak")
    return True


def dry_run(bundle_dir=HERE, preview_path=None):
    bundle = load_bundle(bundle_dir)
    packets, hidden = build_packets(bundle)
    shuffle_ok = True
    for p in packets:
        h = hidden[p["packet_id"]]
        surf = bundle["words"][h["case_id"].split("-")[0]].get("dev_surface_word")
        scan_packet(p, surf, [c["candidate_id"] for c in bundle["candidates"][h["case_id"]]["candidates"]])
        if h["shuffled_order"] == h["authored_order"]:
            shuffle_ok = False
    arms_seq = [hidden[p["packet_id"]]["true_arm"] for p in packets]
    report = {"n_packets": len(packets), "n_cases": len(bundle["candidates"]), "arms": list(ARMS),
              "leak_scan": "clean", "all_shuffled_differ_from_authored": shuffle_ok,
              "arm_randomized": arms_seq != sorted(arms_seq),
              "no_hidden_labels_in_packets": all(not (set(p) & {"true_arm", "target_id", "opt_to_cand"})
                                                 for p in packets),
              "no_four_sphere_reference": not any("sphere" in " ".join(_facing(p)).lower() for p in packets),
              "model_calls": 0, "scored": False,
              "note": "dry-run preview only; no model calls; not a run; not scoring."}
    if preview_path:
        pathlib.Path(preview_path).write_text(json.dumps({"report": report, "packets": packets},
                                              ensure_ascii=False, indent=2), encoding="utf-8")
    return report, packets, hidden


# ---------------------------------------------------------------- gates -------------
def load_approval_config(path):
    cfg = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    bad = []
    if cfg.get("config_type") != "track_g_smoke_approved_run_config": bad.append("config_type")
    if cfg.get("run_enabled") is not True: bad.append("run_enabled!=true")
    if cfg.get("approval_status") != "APPROVED": bad.append("approval_status!=APPROVED")
    if not cfg.get("scorer_model"): bad.append("scorer_model unset")
    if cfg.get("four_sphere_integrated") is not False: bad.append("four_sphere_integrated!=false")
    rec = cfg.get("approval_record") or {}
    if not rec.get("date") or not rec.get("signature"): bad.append("approval signature/date")
    if bad:
        raise RefusedRun("invalid approval config: " + "; ".join(bad))
    return cfg


def run_real_smoke_pilot(bundle_dir=HERE, approval_config=None):
    """Emit packets for EXTERNAL scoring. REFUSES without a valid separate approved config + env
    token. Never calls a model. Base smoke manifest is never edited."""
    if os.environ.get(APPROVAL_ENV) != APPROVAL_TOKEN:
        raise RefusedRun(f"env {APPROVAL_ENV}={APPROVAL_TOKEN!r} required")
    if approval_config is None:
        raise RefusedRun("no approval config supplied")
    load_approval_config(approval_config)
    report, packets, hidden = dry_run(bundle_dir)
    if json.loads(MANIFEST.read_text())["run_enabled"] is not False:
        raise RefusedRun("base smoke manifest must stay run_enabled:false")
    return {"status": "PACKETS_EMITTED_FOR_EXTERNAL_SCORING", "packets": packets, "hidden": hidden}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-check", action="store_true")
    ap.add_argument("--approval-config", default=None)
    args = ap.parse_args()
    r, _, _ = dry_run()
    print(f"[dry-run] packets={r['n_packets']} leak={r['leak_scan']} "
          f"shuffled_ok={r['all_shuffled_differ_from_authored']} arm_randomized={r['arm_randomized']} "
          f"no_hidden_labels={r['no_hidden_labels_in_packets']} no_four_sphere={r['no_four_sphere_reference']} "
          f"model_calls={r['model_calls']}")
    if args.dry_check:
        print("[dry-check] OK; no models, no run.")
    elif args.approval_config:
        try:
            res = run_real_smoke_pilot(approval_config=args.approval_config)
            print(f"approval accepted: {res['status']} ({len(res['packets'])} packets; no model call)")
        except (RefusedRun, ValueError) as e:
            print("REFUSED:", e)
    else:
        print("run_real_smoke_pilot would REFUSE without env token + approval config.")
