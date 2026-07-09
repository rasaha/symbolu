"""B1.6 pilot BLIND judging harness (two-phase; mock-tested only).

Phase A (blind rating package): reads the generation driver's judge-visible outputs,
verifies blindness (no arm names / Symbol-U / KCPR / scaffold / hidden-metadata fields),
and exports a rating template. NO arm identity is available in Phase A.

Phase B (post-rating aggregation): ONLY after a ratings-freeze declaration exists and
its hashes match, joins frozen ratings with the hidden arm metadata, computes arm-level
raw + penalty-adjusted composites, pairwise preferences, and a pilot summary.

This module performs NO real judging and makes NO external API call. Mock mode produces
deterministic fake ratings marked MOCK_JUDGING_ONLY_DO_NOT_INTERPRET.

The pilot emits ONLY plumbing labels — NEVER a prereg GENUTILITY_* terminal verdict.
B1.4b' remains NULL_RETURN_BOTTOM. Structure, not validated meaning.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import pathlib
from typing import Dict, List, Optional, Tuple

HERE = pathlib.Path(__file__).resolve().parent
GEN_OUT = HERE / "run_out" / "b1_6_pilot_generation"
JUDGE_OUT = HERE / "run_out" / "b1_6_pilot_judging"

JUDGE_VISIBLE_FILE = GEN_OUT / "judge_visible_outputs.jsonl"
HIDDEN_META_FILE = GEN_OUT / "hidden_arm_metadata.json"
RATINGS_FROZEN_FILE = GEN_OUT / "b1_6_pilot_RATINGS_FROZEN.json"

# Filenames differ by orchestration: single-model driver vs multi-model / sequential panel.
PACKAGE_FILENAMES = {
    "panel": {"judge_visible": "panel_judge_visible_outputs.jsonl",
              "hidden": "panel_hidden_arm_generator_metadata.json",
              "manifest": "panel_run_manifest.json"},
    "single": {"judge_visible": "judge_visible_outputs.jsonl",
               "hidden": "hidden_arm_metadata.json",
               "manifest": "generation_run_manifest.json"},
}


def locate_generation_package(gen_dir: pathlib.Path) -> Dict:
    """Detect a panel (b1_6_model_panel / sequential) or single-model generation package in gen_dir.
    Returns {kind, judge_visible, hidden, manifest, representation_version} or {kind: None} if absent."""
    for kind, names in PACKAGE_FILENAMES.items():
        jv = gen_dir / names["judge_visible"]
        if jv.exists():
            man = gen_dir / names["manifest"]
            rep = None
            if man.exists():
                try:
                    rep = json.loads(man.read_text()).get("representation_version")
                except Exception:                       # pragma: no cover - defensive
                    rep = None
            return {"kind": kind, "judge_visible": jv, "hidden": gen_dir / names["hidden"],
                    "manifest": man, "representation_version": rep}
    return {"kind": None, "judge_visible": None, "hidden": None, "manifest": None,
            "representation_version": None}

MODE = "pilot_judging"
B1_4B_PRIME_STATUS = "NULL_RETURN_BOTTOM"
MOCK_MARK = "MOCK_JUDGING_ONLY_DO_NOT_INTERPRET"

POSITIVE_DIMS = (
    "coherence", "specificity_to_target", "interpretive_richness", "practical_usefulness",
    "non_genericity", "creativity_aesthetic", "internal_consistency", "caution_epistemic_humility",
)
PENALTY_DIMS = ("overclaim_penalty", "hallucination_penalty")
SCALE_MIN, SCALE_MAX = 1, 7

# allowed keys in a judge-visible package; anything else -> blindness failure
ALLOWED_JUDGE_KEYS = {"item_id", "target_text", "neutral_context",
                      "blinded_output_id", "generation_text", "output_format"}
# keys that would reveal the arm / scaffold / hidden mapping
FORBIDDEN_JUDGE_KEYS = {"arm", "true_arm", "prompt", "prompt_sha256", "scaffold", "scaffold_hash",
                        "VARNA_PROFILE_TABLE", "VARNA_SEQUENCE", "KCPR_DUAL_POLE_FRAME",
                        "randomization_seed", "profile_from"}
# tokens that must not appear in generation_text
FORBIDDEN_TOKENS = ("SYMBOLU", "Symbol-U", "varṇa", "varna", "KCPR", "scaffold",
                    "RANDOMIZED_SYMBOLU", "polarity", "dual-pole", "worldly/binding")

PILOT_LABELS = (
    "B1_6_PILOT_JUDGING_HARNESS_READY_MOCK_TESTED",
    "B1_6_PILOT_JUDGING_BLOCKED_NO_GENERATED_OUTPUTS",
    "B1_6_PILOT_JUDGING_BLOCKED_RATINGS_NOT_FROZEN",
    "B1_6_PILOT_JUDGING_INVALID_BLINDING",
    "B1_6_PILOT_JUDGING_INVALID_LEAKAGE",
)

RATINGS_ATTESTATION = ("B1.6 pilot ratings frozen before unblinding; pilot only; "
                       "no terminal GENUTILITY verdict; no semantic truth claim.")
REQUIRED_FREEZE_FIELDS = (
    "artifact", "ratings_frozen", "mode", "judge_visible_outputs_sha256",
    "ratings_file_sha256", "declared_by", "declared_at_utc", "attestation",
)


def _sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha_file(p: pathlib.Path) -> str:
    return _sha_bytes(p.read_bytes())


def _read_jsonl(p: pathlib.Path) -> List[Dict]:
    return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]


# ======================================================================================
# Phase A — blindness verification + rating template
# ======================================================================================
def check_blindness(judge_visible: List[Dict]) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    for i, pkg in enumerate(judge_visible):
        extra = set(pkg.keys()) - ALLOWED_JUDGE_KEYS
        forb = set(pkg.keys()) & FORBIDDEN_JUDGE_KEYS
        if forb:
            reasons.append(f"[{i}] forbidden key(s): {sorted(forb)}")
        elif extra:
            reasons.append(f"[{i}] unexpected key(s) (possible metadata leak): {sorted(extra)}")
        if not pkg.get("target_text"):
            reasons.append(f"[{i}] target_text missing (must be visible for specificity scoring)")
        if "neutral_context" not in pkg:
            reasons.append(f"[{i}] neutral_context missing")
        gen = str(pkg.get("generation_text", ""))
        for tok in FORBIDDEN_TOKENS:
            if tok in gen:
                reasons.append(f"[{i}] forbidden token {tok!r} in generation_text")
    return (not reasons), reasons


def make_rating_template_rows(judge_visible: List[Dict]) -> List[Dict]:
    rows = []
    for pkg in judge_visible:
        row = {"blinded_output_id": pkg["blinded_output_id"], "item_id": pkg["item_id"],
               "target_text": pkg["target_text"]}
        for d in POSITIVE_DIMS:
            row[d] = ""      # judge fills 1-7
        for d in PENALTY_DIMS:
            row[d] = ""      # judge fills 1-7 (higher = worse)
        rows.append(row)
    return rows


def write_rating_template_csv(rows: List[Dict]) -> str:
    buf = io.StringIO()
    fields = ["blinded_output_id", "item_id", "target_text", *POSITIVE_DIMS, *PENALTY_DIMS]
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def phase_a_blind_package(judge_visible_file: pathlib.Path = JUDGE_VISIBLE_FILE,
                          out_dir: pathlib.Path = JUDGE_OUT,
                          write: bool = True) -> Dict:
    if not judge_visible_file.exists():
        return {"label": "B1_6_PILOT_JUDGING_BLOCKED_NO_GENERATED_OUTPUTS",
                "reasons": [f"missing {judge_visible_file.name}"]}
    jv = _read_jsonl(judge_visible_file)
    ok, reasons = check_blindness(jv)
    report = {"n_outputs": len(jv), "blind_ok": ok, "reasons": reasons,
              "b1_4b_prime_status": B1_4B_PRIME_STATUS}
    if not ok:
        report["label"] = "B1_6_PILOT_JUDGING_INVALID_BLINDING"
        return report
    rows = make_rating_template_rows(jv)
    report["label"] = "B1_6_PILOT_JUDGING_BLIND_PACKAGE_OK"
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "judge_rating_template.csv").write_text(write_rating_template_csv(rows))
        (out_dir / "blindness_check_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    report["_rows"] = rows
    return report


# ======================================================================================
# Ratings schema validation
# ======================================================================================
def validate_rating(rating: Dict) -> Tuple[bool, List[str]]:
    reasons = []
    for d in (*POSITIVE_DIMS, *PENALTY_DIMS):
        if d not in rating or rating[d] in (None, ""):
            reasons.append(f"missing dimension: {d}")
            continue
        try:
            v = float(rating[d])
        except (TypeError, ValueError):
            reasons.append(f"non-numeric {d}: {rating[d]!r}")
            continue
        if not (SCALE_MIN <= v <= SCALE_MAX):
            reasons.append(f"{d} out of 1-7 range: {v}")
    if "blinded_output_id" not in rating:
        reasons.append("missing blinded_output_id")
    return (not reasons), reasons


def composites(rating: Dict) -> Tuple[float, float]:
    """raw = mean of positives; penalty-adjusted = raw - mean(penalties) shift.
    Penalty dims are 1-7 where higher = worse; we subtract (penalty-1) averaged so a
    penalty of 1 (none) leaves raw unchanged and 7 subtracts the max."""
    pos = [float(rating[d]) for d in POSITIVE_DIMS]
    raw = sum(pos) / len(pos)
    pen = [float(rating[d]) - 1.0 for d in PENALTY_DIMS]     # 0..6
    adj = raw - (sum(pen) / len(pen))
    return raw, adj


# ======================================================================================
# Ratings-freeze gate
# ======================================================================================
def verify_ratings_freeze(freeze_path: pathlib.Path,
                          judge_visible_file: pathlib.Path,
                          ratings_file: pathlib.Path) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    if not freeze_path.exists():
        return False, ["no RATINGS_FROZEN declaration (operator must create it before unblinding)"]
    decl = json.loads(freeze_path.read_text())
    for f in REQUIRED_FREEZE_FIELDS:
        if f not in decl:
            reasons.append(f"missing field: {f}")
    if decl.get("artifact") != "b1_6_pilot_RATINGS_FROZEN":
        reasons.append("artifact != b1_6_pilot_RATINGS_FROZEN")
    if decl.get("ratings_frozen") is not True:
        reasons.append("ratings_frozen != true")
    if decl.get("mode") != MODE:
        reasons.append(f"mode != {MODE}")
    if decl.get("attestation") != RATINGS_ATTESTATION:
        reasons.append("attestation text mismatch")
    if reasons:
        return False, reasons
    if judge_visible_file.exists() and decl.get("judge_visible_outputs_sha256") != _sha_file(judge_visible_file):
        reasons.append("judge_visible_outputs_sha256 mismatch")
    if ratings_file.exists() and decl.get("ratings_file_sha256") != _sha_file(ratings_file):
        reasons.append("ratings_file_sha256 mismatch")
    elif not ratings_file.exists():
        reasons.append(f"ratings file missing: {ratings_file.name}")
    return (not reasons), reasons


# ======================================================================================
# Phase B — post-rating aggregation (only after freeze)
# ======================================================================================
PAIRWISE = [
    ("SYMBOLU_SCAFFOLD", "PLAIN_PROMPT_BASELINE"),
    ("SYMBOLU_SCAFFOLD", "GENERIC_STRUCTURED_PROMPT_BASELINE"),
    ("SYMBOLU_SCAFFOLD", "RANDOMIZED_SYMBOLU_CONTROL"),
    ("SYMBOLU_SCAFFOLD", "SEMANTIC_LLM_BASELINE"),
]


def _mean(xs): return sum(xs) / len(xs) if xs else float("nan")


def _bootstrap_ci(xs, n=200, seed=0):
    """Deterministic percentile bootstrap CI of the mean (no external deps)."""
    if len(xs) < 2:
        return [float("nan"), float("nan")]
    # deterministic LCG (Date/Math.random unavailable in some contexts; keep pure)
    state = seed + 1
    means = []
    k = len(xs)
    for _ in range(n):
        s = 0.0
        for _ in range(k):
            state = (1103515245 * state + 12345) & 0x7FFFFFFF
            s += xs[state % k]
        means.append(s / k)
    means.sort()
    lo = means[int(0.025 * n)]
    hi = means[min(int(0.975 * n), n - 1)]
    return [round(lo, 4), round(hi, 4)]


def aggregate(ratings: List[Dict], hidden_meta: List[Dict],
              freeze_path: pathlib.Path = RATINGS_FROZEN_FILE,
              judge_visible_file: pathlib.Path = JUDGE_VISIBLE_FILE,
              ratings_file: pathlib.Path = None,
              require_freeze: bool = True,
              out_dir: pathlib.Path = JUDGE_OUT,
              write: bool = False,
              representation_version: Optional[str] = None) -> Dict:
    if require_freeze:
        ok, reasons = verify_ratings_freeze(freeze_path, judge_visible_file,
                                            ratings_file or freeze_path)
        if not ok:
            return {"label": "B1_6_PILOT_JUDGING_BLOCKED_RATINGS_NOT_FROZEN", "reasons": reasons}

    for r in ratings:
        ok, reasons = validate_rating(r)
        if not ok:
            raise ValueError(f"incomplete/invalid rating {r.get('blinded_output_id')!r}: {reasons}")

    # unblind ONLY here
    arm_of = {m["blinded_output_id"]: m["true_arm"] for m in hidden_meta}
    by_arm_raw: Dict[str, List[float]] = {}
    by_arm_adj: Dict[str, List[float]] = {}
    raw_by_id: Dict[str, float] = {}
    adj_by_id: Dict[str, float] = {}
    item_of: Dict[str, str] = {m["blinded_output_id"]: m["item_id"] for m in hidden_meta}
    pen_by_arm: Dict[str, Dict[str, List[float]]] = {}
    for r in ratings:
        bid = r["blinded_output_id"]
        arm = arm_of.get(bid)
        if arm is None:
            continue
        raw, adj = composites(r)
        raw_by_id[bid] = raw; adj_by_id[bid] = adj
        by_arm_raw.setdefault(arm, []).append(raw)
        by_arm_adj.setdefault(arm, []).append(adj)
        pen_by_arm.setdefault(arm, {p: [] for p in PENALTY_DIMS})
        for p in PENALTY_DIMS:
            pen_by_arm[arm][p].append(float(r[p]))

    arm_summary = {}
    for arm in by_arm_raw:
        arm_summary[arm] = {
            "n": len(by_arm_raw[arm]),
            "mean_raw_composite": round(_mean(by_arm_raw[arm]), 4),
            "raw_ci95": _bootstrap_ci(by_arm_raw[arm]),
            "mean_penalty_adjusted_composite": round(_mean(by_arm_adj[arm]), 4),
            "adj_ci95": _bootstrap_ci(by_arm_adj[arm]),
            "mean_penalties": {p: round(_mean(v), 4) for p, v in pen_by_arm[arm].items()},
        }

    # pairwise preference by item (paired on item_id), using penalty-adjusted composite
    id_by_item_arm: Dict[Tuple[str, str], str] = {}
    for bid, arm in arm_of.items():
        id_by_item_arm[(item_of[bid], arm)] = bid
    pairwise = {}
    for a, b in PAIRWISE:
        win = tie = loss = 0
        items = {item_of[bid] for bid in adj_by_id}
        for it in items:
            ba = id_by_item_arm.get((it, a)); bb = id_by_item_arm.get((it, b))
            if ba in adj_by_id and bb in adj_by_id:
                da, db = adj_by_id[ba], adj_by_id[bb]
                if da > db: win += 1
                elif da < db: loss += 1
                else: tie += 1
        n = win + tie + loss
        pairwise[f"{a}_vs_{b}"] = {"win": win, "tie": tie, "loss": loss,
                                   "win_rate": round(win / n, 4) if n else None, "n": n}

    # generator dimension (present only when hidden metadata carries generator_code, i.e. panel/sequential)
    gen_of = {m["blinded_output_id"]: m.get("generator_code") for m in hidden_meta}
    has_gen = any(gen_of.values())
    by_gen_raw: Dict[str, List[float]] = {}
    by_gen_adj: Dict[str, List[float]] = {}
    by_armgen_adj: Dict[Tuple[str, str], List[float]] = {}
    if has_gen:
        for bid, adj in adj_by_id.items():
            g = gen_of.get(bid); arm = arm_of.get(bid)
            if not g or arm is None:
                continue
            by_gen_raw.setdefault(g, []).append(raw_by_id[bid])
            by_gen_adj.setdefault(g, []).append(adj)
            by_armgen_adj.setdefault((arm, g), []).append(adj)
    generator_summary = {
        g: {"n": len(by_gen_adj[g]),
            "mean_raw_composite": round(_mean(by_gen_raw[g]), 4),
            "mean_penalty_adjusted_composite": round(_mean(by_gen_adj[g]), 4),
            "adj_ci95": _bootstrap_ci(by_gen_adj[g])}
        for g in by_gen_adj
    } if has_gen else None
    arm_x_generator_summary = {
        f"{arm}|{g}": {"n": len(v), "mean_penalty_adjusted_composite": round(_mean(v), 4)}
        for (arm, g), v in by_armgen_adj.items()
    } if has_gen else None

    summary = {
        "artifact_type": "b1_6_pilot_judging_summary",
        "pilot_label": "B1_6_PILOT_JUDGING_HARNESS_READY_MOCK_TESTED",
        "note": "PILOT PLUMBING ONLY. No prereg GENUTILITY_* terminal verdict is emitted from the pilot.",
        "terminal_genutility_label_emitted": False,
        "representation_version": representation_version,
        "b1_4b_prime_status": B1_4B_PRIME_STATUS,
        "arm_summary": arm_summary,
        "generator_summary": generator_summary,                 # None for single-model packages
        "arm_x_generator_summary": arm_x_generator_summary,     # None for single-model packages
        "item_level_variance": {
            arm: round(_variance(by_arm_adj[arm]), 4) for arm in by_arm_adj
        },
    }
    pairwise_summary = {"pairwise_penalty_adjusted": pairwise,
                        "note": "pairwise preference is descriptive plumbing; NOT a terminal verdict."}
    unblinded = {"arm_of_blinded_id": arm_of, "mark": MOCK_MARK}
    if has_gen:
        unblinded["generator_of_blinded_id"] = {bid: g for bid, g in gen_of.items() if g}

    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "pilot_judging_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        (out_dir / "pairwise_preference_summary.json").write_text(json.dumps(pairwise_summary, indent=2, ensure_ascii=False))
        (out_dir / "unblinded_arm_summary.json").write_text(json.dumps(unblinded, indent=2, ensure_ascii=False))

    return {"label": "B1_6_PILOT_JUDGING_HARNESS_READY_MOCK_TESTED",
            "summary": summary, "pairwise": pairwise_summary, "unblinded": unblinded}


def _variance(xs):
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


# ======================================================================================
# Mock helpers (deterministic; tests only)
# ======================================================================================
def mock_ratings(judge_visible: List[Dict], hidden_meta: Optional[List[Dict]] = None) -> List[Dict]:
    """Deterministic fake ratings. NOT evidence; marked MOCK. Independent of true arm."""
    out = []
    for pkg in judge_visible:
        bid = pkg["blinded_output_id"]
        h = int(hashlib.sha256(bid.encode()).hexdigest(), 16)
        base = 3 + (h % 5)                      # 3..7
        r = {"blinded_output_id": bid, "_mock": MOCK_MARK}
        for j, d in enumerate(POSITIVE_DIMS):
            r[d] = SCALE_MIN + ((base + j + (h >> j)) % SCALE_MAX)
            r[d] = max(SCALE_MIN, min(SCALE_MAX, r[d]))
        for d in PENALTY_DIMS:
            r[d] = 1 + (h % 3)                  # 1..3
        out.append(r)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="B1.6 blind judging harness (two-phase; mock-tested).")
    ap.add_argument("--phase", choices=["a", "A", "b", "B"], required=True)
    ap.add_argument("--gen-out", default=str(GEN_OUT))
    args = ap.parse_args(argv)
    gen = pathlib.Path(args.gen_out)
    if args.phase.lower() == "a":
        rep = phase_a_blind_package(gen / "judge_visible_outputs.jsonl")
        rep.pop("_rows", None)
        print(json.dumps(rep, indent=2, ensure_ascii=False))
    else:
        raise SystemExit("Phase B requires an operator ratings file + RATINGS_FROZEN declaration; "
                         "not runnable from CLI without them. Use the test suite for mock validation.")


if __name__ == "__main__":
    main()
