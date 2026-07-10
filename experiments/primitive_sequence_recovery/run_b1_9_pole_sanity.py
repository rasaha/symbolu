"""B1.9 POLE-LOGIC SANITY driver + freeze gate (gated; blinded; mock-tested). NO GENERATION — direct rating only.

For each target word W we take W's OWN correct-pole and flipped-pole varṇa facet packets (RAW text from the frozen
v2 table) and have blind judges rate 1-7 how DIRECTLY each packet describes each candidate word (W + synonyms, and
opposite/contrast words), under an anti-contrastive instruction (direct fit only; no credit for what the word
overcomes/resists/is free from/opposes/contrasts with). Primary statistic (at aggregation):

    D_target   = mean(correct fit to W/synonyms) − mean(flipped fit to W/synonyms)      # expect > 0 if coherent
    D_opposite = mean(correct fit to opposites)  − mean(flipped fit to opposites)        # expect < 0 if coherent
    INT = D_target − D_opposite                                                          # expect > 0 if coherent

Pole-label coherence ONLY. NOT ontology, Sanskrit privilege, semantic truth, generation utility, or word-specific
varṇa mapping. No Mistral/Qwen, no readings — the judges rate the raw facet text. Blind: a judge never learns
whether a packet is correct/flipped, nor whether a word is target/synonym/opposite. Anti-circularity: the WordNet
synonym/opposite table must be operator-APPROVED (word_groups_approved==true) before any real run — the gate
refuses otherwise. Consonant-only (inherited). NO real model here (mock only in tests). B1.4b′ = NULL_RETURN_BOTTOM.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
import re
from typing import Dict, List, Optional, Tuple

import run_b1_6_pilot_generation as G
import b1_6_llm_adapter as A

B1_4B_PRIME_STATUS = "NULL_RETURN_BOTTOM"
HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"

SCAFFOLD_FILE = FROZEN / "b1_9_pole_sanity_scaffold.json"
ITEMS_FILE = FROZEN / "b1_9_pole_sanity_items.json"
V2_TABLE_FILE = HERE / "track_g_varna_polarity_table_v2_named_vritti.json"
PREREG_FILE = HERE / "B1_9_POLE_SANITY_PREREG.md"

MODE = "b1_9_pole_sanity_probe"
REPRESENTATION = "B1.9_pole_sanity"
ATTESTATION = ("B1.9 pole-logic sanity probe only; direct rating (NO generation) of W's own correct/flipped varṇa "
               "facet packets against W+synonyms and opposite words; anti-contrastive; INT crossover = pole-label "
               "coherence only; no semantic-truth claim; no GENUTILITY terminal label; B1.4b′ = NULL_RETURN_BOTTOM.")

PACKET_POLES = ("correct", "flipped")
ROLE_GROUPS = {"target_synonyms": ("target", "synonym"), "opposites": ("opposite",)}
INT_STAT = ("INT = D_target − D_opposite; D_target = mean(correct fit to W/syn) − mean(flipped fit to W/syn); "
            "D_opposite = mean(correct fit to opp) − mean(flipped fit to opp)")
SHUFFLE_SEED = 20260712

HASH_INPUTS = {
    "prereg_sha256": PREREG_FILE, "items_sha256": ITEMS_FILE, "scaffold_sha256": SCAFFOLD_FILE,
    "v2_named_vritti_table_sha256": V2_TABLE_FILE,
}
REQUIRED_DECL_FIELDS = ("artifact", "evidence_freeze_declared", "mode", "representation_version",
                        "declared_by", "declared_at_utc", "attestation", *HASH_INPUTS.keys())
BAD_MODES = {"pilot_generation", "b1_8_context_resolved_generation_probe",
             "b1_9_content_level_semantic_distance", "b1_9_generation_corrected_control_probe",
             "b1_9_pole_sensitivity_probe", "b1_9_pole_did_probe", "b1_9_synonym_conformance_probe"}

JUDGE_INSTRUCTION = (
    "You will see a short PACKET of descriptor phrases and one WORD (with its meaning). Rate 1-7 how DIRECTLY the "
    "packet describes that word's own meaning (1 = does not describe it at all, 7 = describes it directly and "
    "centrally).\n"
    "IMPORTANT: Only DIRECT description counts. Do NOT give a high rating if the packet describes what the word "
    "overcomes, resists, is free from, opposes, or contrasts with — that is NOT a direct description and must be "
    "rated low.\n"
    "Also state whether the packet is describing the word itself (\"direct\") or its opposite / what it resists "
    "(\"contrastive\").\n"
    'Respond with ONLY a JSON object: {"fit": <integer 1-7>, "describes": "direct" | "contrastive"}.')

ALLOWED_JV_KEYS = {"rating_id", "packet", "word", "word_meaning"}


def _sha_file(p: pathlib.Path) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def leaked(text: str) -> List[str]:
    return list(G.leaked_tokens(text))


def word_groups_approved() -> bool:
    try:
        return json.loads(ITEMS_FILE.read_text()).get("word_groups_approved") is True
    except Exception:  # noqa: BLE001
        return False


def verify_freeze_gate(decl_path: pathlib.Path, expected_mode: str = MODE) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    if not pathlib.Path(decl_path).exists():
        return False, ["no EVIDENCE_FREEZE_DECLARED file (operator must create it)"]
    try:
        decl = json.loads(pathlib.Path(decl_path).read_text())
    except Exception as e:  # noqa: BLE001
        return False, [f"declaration not valid JSON: {e}"]
    for f in REQUIRED_DECL_FIELDS:
        if f not in decl:
            reasons.append(f"missing required field: {f}")
    if decl.get("artifact") != "b1_9_pole_sanity_EVIDENCE_FREEZE_DECLARED":
        reasons.append("artifact != b1_9_pole_sanity_EVIDENCE_FREEZE_DECLARED")
    if decl.get("evidence_freeze_declared") is not True:
        reasons.append("evidence_freeze_declared != true")
    if decl.get("mode") in BAD_MODES:
        reasons.append(f"refused: other-track mode supplied ({decl.get('mode')!r})")
    if decl.get("mode") != expected_mode:
        reasons.append(f"mode != {expected_mode} (got {decl.get('mode')!r})")
    if decl.get("representation_version") != REPRESENTATION:
        reasons.append(f"representation_version != {REPRESENTATION} (got {decl.get('representation_version')!r})")
    if decl.get("attestation") != ATTESTATION:
        reasons.append("attestation text mismatch")
    if not word_groups_approved():
        reasons.append("synonym/opposite table NOT approved (set word_groups_approved=true after operator sign-off "
                       "BEFORE any rating — anti-circularity requirement)")
    if reasons:
        return False, reasons
    for field, path in HASH_INPUTS.items():
        if not path.exists():
            reasons.append(f"frozen input missing: {path.name}")
        elif decl.get(field) != _sha_file(path):
            reasons.append(f"{field} mismatch (wrong-track/representation declaration is refused)")
    return (not reasons), reasons


def _packet_text(facets: List[Dict]) -> str:
    out, seen = [], set()
    for f in facets:
        t = f["text"]
        if t not in seen:
            seen.add(t); out.append(f"- {t}")
    return "\n".join(out) or "- (no descriptor)"


def load_scaffold() -> Dict:
    return json.loads(SCAFFOLD_FILE.read_text())


def build_rating_tasks(scaffold: Dict, limit_items: Optional[int] = None) -> List[Dict]:
    """One task per (item, packet_pole, candidate). Blind: no pole/role labels reach the judge-visible package."""
    items = scaffold["items"][:limit_items] if limit_items else scaffold["items"]
    tasks, n = [], 0
    for it in items:
        packets = {"correct": it["correct_packet"], "flipped": it["flipped_packet"]}
        for pole in PACKET_POLES:
            ptext = _packet_text(packets[pole])
            for cand in it["candidate_pool"]:
                n += 1
                tasks.append({
                    "rating_id": f"R{n:05d}", "item_id": it["item_id"], "packet_pole": pole,
                    "packet_text": ptext, "candidate_word": cand["word"], "candidate_gloss": cand.get("gloss", ""),
                    "candidate_role": cand["role"],
                })
    return tasks


def make_judge_visible(task: Dict) -> Dict:
    pkg = {"rating_id": task["rating_id"], "packet": task["packet_text"],
           "word": task["candidate_word"], "word_meaning": task["candidate_gloss"]}
    for k in ("packet", "word", "word_meaning"):
        lk = leaked(str(pkg[k]))
        if lk:
            raise ValueError(f"INVALID_LEAKAGE in {k}: {lk}")
    return pkg


def make_hidden(task: Dict) -> Dict:
    return {"rating_id": task["rating_id"], "item_id": task["item_id"], "packet_pole": task["packet_pole"],
            "candidate_role": task["candidate_role"], "candidate_word": task["candidate_word"],
            "representation_version": REPRESENTATION}


def assert_blind(judge_visible: List[Dict]) -> None:
    for i, pkg in enumerate(judge_visible):
        extra = set(pkg.keys()) - ALLOWED_JV_KEYS
        if extra:
            raise ValueError(f"INVALID_BLINDING [{i}]: unexpected keys {sorted(extra)}")
        if any(k in pkg for k in ("packet_pole", "candidate_role", "item_id")):
            raise ValueError(f"INVALID_BLINDING [{i}]: pole/role/item leaked")


def prepare(scaffold: Dict, out_dir: Optional[pathlib.Path] = None, write: bool = False,
            shuffle_seed: int = SHUFFLE_SEED, limit_items: Optional[int] = None) -> Dict:
    tasks = build_rating_tasks(scaffold, limit_items=limit_items)
    tasks.sort(key=lambda t: hashlib.sha256(f"{shuffle_seed}|{t['rating_id']}".encode()).hexdigest())
    judge_visible = [make_judge_visible(t) for t in tasks]
    hidden = [make_hidden(t) for t in tasks]
    assert_blind(judge_visible)
    n_items = len({t["item_id"] for t in tasks})
    manifest = {
        "artifact_type": "b1_9_pole_sanity_run_manifest", "representation_version": REPRESENTATION,
        "run_label": "B1_9_POLE_SANITY_PROBE", "primary_statistic": INT_STAT,
        "n_items": n_items, "n_rating_tasks": len(tasks),
        "per_role_task_counts": {r: sum(1 for t in tasks if t["candidate_role"] == r)
                                 for r in ("target", "synonym", "opposite")},
        "input_hashes": {k: _sha_file(v) for k, v in HASH_INPUTS.items()},
        "word_groups_approved": word_groups_approved(), "shuffle_seed": shuffle_seed,
        "judging_performed": False, "unblinded": False, "b1_4b_prime_status": B1_4B_PRIME_STATUS,
        "note": "Direct packet-rating sanity test (NO generation). Judge-visible carries no pole/role/item labels. "
                "Anti-contrastive instruction. INT crossover = pole-label coherence. No GENUTILITY_*.",
    }
    if write and out_dir:
        out_dir = pathlib.Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "panel_judge_visible_ratings.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in judge_visible) + "\n")
        (out_dir / "panel_hidden_metadata.json").write_text(json.dumps(hidden, ensure_ascii=False, indent=2))
        (out_dir / "panel_run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return {"label": "B1_9_POLE_SANITY_DRIVER_READY_MOCK_TESTED", "manifest": manifest,
            "judge_visible": judge_visible, "hidden": hidden}


# ---- rating parse + judge --------------------------------------------------------------
def judge_prompt(pkg: Dict) -> str:
    wm = f" — meaning: {pkg['word_meaning']}" if pkg.get("word_meaning") else ""
    return (f"{JUDGE_INSTRUCTION}\n\nPACKET:\n{pkg['packet']}\n\nWORD: {pkg['word']}{wm}\n")


def parse_rating(text: str) -> Tuple[Optional[Dict], List[str]]:
    """Extract {fit:int 1-7, describes: direct|contrastive}. Never edits."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None, ["no JSON object found"]
    try:
        raw = json.loads(m.group(0))
    except Exception as e:  # noqa: BLE001
        return None, [f"JSON parse error: {e}"]
    low = {str(k).strip().lower(): v for k, v in raw.items()}
    reasons = []
    try:
        fit = int(low.get("fit"))
    except Exception:  # noqa: BLE001
        return None, [f"non-integer/missing fit: {low.get('fit')!r}"]
    if not (1 <= fit <= 7):
        reasons.append(f"fit out of [1,7]: {fit}")
    desc = str(low.get("describes", "")).strip().lower()
    if desc not in ("direct", "contrastive"):
        reasons.append(f"describes not in {{direct,contrastive}}: {desc!r}")
    if reasons:
        return None, reasons
    return {"fit": fit, "describes": desc}, []


def _mock_rating(pkg: Dict, judge_id: str) -> Dict:
    h = int(hashlib.sha256(f"{judge_id}|{pkg['rating_id']}|{pkg['word']}".encode()).hexdigest(), 16)
    return {"fit": 1 + (h % 7), "describes": "direct" if h % 3 else "contrastive"}


def run_judge(judge_visible_path: pathlib.Path, judge_id: str, adapter=None, mock: bool = False,
              settings=None, decl_path: Optional[pathlib.Path] = None,
              out_dir: Optional[pathlib.Path] = None, write: bool = False) -> Dict:
    if not mock:
        if decl_path is None:
            raise PermissionError("real rating run requires a B1.9 pole-sanity evidence-freeze declaration path")
        ok, reasons = verify_freeze_gate(pathlib.Path(decl_path))
        if not ok:
            raise PermissionError("EVIDENCE_FREEZE gate refused: " + "; ".join(reasons))
    pkgs = [json.loads(l) for l in pathlib.Path(judge_visible_path).read_text().splitlines() if l.strip()]
    settings = settings or A.GenerationSettings(temperature=0.0, max_tokens=128)
    ratings, errors = [], []
    for pkg in pkgs:
        if mock:
            r = _mock_rating(pkg, judge_id)
        else:
            from b1_6_llm_adapter import generate_with_retry
            text, status, rs = generate_with_retry(
                adapter, judge_prompt(pkg), settings, validate=True,
                validator=lambda t: (parse_rating(t)[0] is not None, parse_rating(t)[1]))
            if status != "ok" or text is None:
                errors.append({"rating_id": pkg["rating_id"], "status": status, "reasons": rs}); continue
            r, rs = parse_rating(text)
            if r is None:
                errors.append({"rating_id": pkg["rating_id"], "status": "parse", "reasons": rs}); continue
        ratings.append({"rating_id": pkg["rating_id"], "judge_id": judge_id, **r})
    part = {"artifact_type": "b1_9_pole_sanity_judge_part", "judge_id": judge_id, "mode": "MOCK" if mock else "REAL",
            "n_ratings": len(ratings), "n_errors": len(errors), "errors": errors, "ratings": ratings,
            "b1_4b_prime_status": B1_4B_PRIME_STATUS}
    if write and out_dir:
        out_dir = pathlib.Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "b1_9_pole_sanity_judge_part.json").write_text(json.dumps(part, ensure_ascii=False, indent=2))
    return part


def aggregate(judge_parts: List[Dict], hidden: List[Dict]) -> Dict:
    """Cells + INT crossover. Unblinds ONLY here. Cells averaged over judges; per-item INT for CI + sign test."""
    import statistics as st, random
    meta = {h["rating_id"]: h for h in hidden}
    # gather fit by (item, pole, role_group) and contrastive flags
    cellvals: Dict[tuple, List[float]] = {}
    contr: Dict[tuple, List[int]] = {}
    for jp in judge_parts:
        for r in jp["ratings"]:
            h = meta.get(r["rating_id"])
            if not h:
                continue
            grp = "target_synonyms" if h["candidate_role"] in ROLE_GROUPS["target_synonyms"] else "opposites"
            key = (h["item_id"], h["packet_pole"], grp)
            cellvals.setdefault(key, []).append(r["fit"])
            contr.setdefault(key, []).append(1 if r.get("describes") == "contrastive" else 0)

    def cell_mean(item, pole, grp):
        v = cellvals.get((item, pole, grp))
        return st.mean(v) if v else None

    items = sorted({k[0] for k in cellvals})
    # 4 reported quantities (means over items)
    def group_mean(pole, grp):
        vals = [cell_mean(it, pole, grp) for it in items]
        vals = [x for x in vals if x is not None]
        return round(st.mean(vals), 3) if vals else None

    cells = {
        "1_correct_fit_to_target_synonyms": group_mean("correct", "target_synonyms"),
        "2_flipped_fit_to_target_synonyms": group_mean("flipped", "target_synonyms"),
        "3_flipped_fit_to_opposites": group_mean("flipped", "opposites"),
        "4_correct_fit_to_opposites": group_mean("correct", "opposites"),
    }
    # per-item D_target, D_opposite, INT (only items with all four cells present)
    per_item = []
    for it in items:
        c_t, f_t = cell_mean(it, "correct", "target_synonyms"), cell_mean(it, "flipped", "target_synonyms")
        c_o, f_o = cell_mean(it, "correct", "opposites"), cell_mean(it, "flipped", "opposites")
        if None in (c_t, f_t, c_o, f_o):
            continue
        d_t, d_o = c_t - f_t, c_o - f_o
        per_item.append({"item_id": it, "D_target": d_t, "D_opposite": d_o, "INT": d_t - d_o})
    d_target = [p["D_target"] for p in per_item]
    d_opp = [p["D_opposite"] for p in per_item]
    ints = [p["INT"] for p in per_item]

    def boot(x, n=2000, seed=7):
        if not x:
            return (None, None)
        r = random.Random(seed)
        ms = sorted(sum(r.choice(x) for _ in range(len(x))) / len(x) for _ in range(n))
        return round(ms[int(.025 * n)], 3), round(ms[int(.975 * n)], 3)

    def contr_rate(pole, grp):
        num = den = 0
        for it in items:
            v = contr.get((it, pole, grp))
            if v:
                num += sum(v); den += len(v)
        return round(num / den, 3) if den else None

    return {
        "label": "B1_9_POLE_SANITY_AGGREGATE", "representation_version": REPRESENTATION, "primary_statistic": INT_STAT,
        "reported_cells": cells,
        "mean_D_target": round(st.mean(d_target), 3) if d_target else None,
        "mean_D_opposite": round(st.mean(d_opp), 3) if d_opp else None,
        "mean_INT": round(st.mean(ints), 3) if ints else None,
        "INT_bootstrap_CI95": boot(ints), "n_items_paired": len(per_item),
        "INT_sign": {"pos": sum(1 for x in ints if x > 0), "neg": sum(1 for x in ints if x < 0)},
        "anti_contrastive_audit": {
            "correct_target_synonyms": contr_rate("correct", "target_synonyms"),
            "flipped_target_synonyms": contr_rate("flipped", "target_synonyms"),
            "flipped_opposites": contr_rate("flipped", "opposites"),
            "correct_opposites": contr_rate("correct", "opposites"),
        },
        "interpretation": ("Coherent pole logic => D_target>0, D_opposite<0, INT>0 (robust). INT≈0 (CI straddles 0) "
                           "=> pole labels do no directional work (informative). Pole-label coherence ONLY: no "
                           "ontology/truth/privilege/GENUTILITY; no word-specific mapping claim."),
        "b1_4b_prime_status": B1_4B_PRIME_STATUS,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="B1.9 pole-logic sanity driver (NO generation; gated; mock-tested).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("prepare")
    pp.add_argument("--limit-items", type=int); pp.add_argument("--out", required=True)

    jp = sub.add_parser("judge")
    jp.add_argument("--judge-visible", required=True); jp.add_argument("--judge-id", required=True)
    jp.add_argument("--mock", action="store_true"); jp.add_argument("--decl")
    jp.add_argument("--backend", default="transformers"); jp.add_argument("--base-url"); jp.add_argument("--revision")
    jp.add_argument("--out", required=True)

    ag = sub.add_parser("aggregate")
    ag.add_argument("--judge-parts", nargs="+", required=True); ag.add_argument("--hidden", required=True)

    args = ap.parse_args(argv)
    if args.cmd == "prepare":
        res = prepare(load_scaffold(), out_dir=pathlib.Path(args.out), write=True, limit_items=args.limit_items)
        print(json.dumps(res["manifest"], indent=2))
        return
    if args.cmd == "judge":
        adapter = None
        if not args.mock:
            adapter = A.build_adapter(A.GenerationSettings(model_id=args.judge_id, backend=args.backend,
                                      base_url=args.base_url, revision=args.revision, temperature=0.0, max_tokens=128))
        part = run_judge(pathlib.Path(args.judge_visible), args.judge_id, adapter=adapter, mock=args.mock,
                         decl_path=pathlib.Path(args.decl) if args.decl else None,
                         out_dir=pathlib.Path(args.out), write=True)
        print(json.dumps({"judge_id": part["judge_id"], "n_ratings": part["n_ratings"],
                          "n_errors": part["n_errors"]}, indent=2))
        return
    if args.cmd == "aggregate":
        jps = [json.loads(pathlib.Path(p if p.endswith(".json") else pathlib.Path(p) / "b1_9_pole_sanity_judge_part.json").read_text())
               for p in args.judge_parts]
        hidden = json.loads(pathlib.Path(args.hidden).read_text())
        print(json.dumps(aggregate(jps, hidden), indent=2))


if __name__ == "__main__":
    main()
