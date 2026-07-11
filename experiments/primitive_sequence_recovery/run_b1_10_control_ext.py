"""B1.10 CONTROL EXTENSION driver (three-tier; no-generation rating; gated; blinded; mock-tested).

Reuses the B1.10 pole-context method with THREE packet tiers per word (valence / source_condition / specific).
6 words x 2 contexts x (3 tiers x 2 poles) = 72 blinded rating cells. Judge rates source-condition fit 0-6; blind
to tier, pole, and packet provenance. No generation. NO result/verdict label emitted.

Statistics (per word W, tier T in {specific, valence, source_condition}):
    margin_T(W) = [fit(Pb_T|Cb) - fit(Pl_T|Cb)] + [fit(Pl_T|Cl) - fit(Pb_T|Cl)]
    specific_margin(W)                 = margin_specific(W)
    valence_margin(W)                  = margin_valence(W)
    generic_source_condition_margin(W) = margin_source_condition(W)
    increment_over_valence(W)          = specific_margin(W) - valence_margin(W)          # Comparison A
    increment_over_source_condition(W) = specific_margin(W) - generic_source_condition_margin(W)  # Comparison B
Aggregate = mean over complete words. Both directional halves of every margin are reported.

Real judges require a gated EVIDENCE_FREEZE_DECLARED (NOT created yet) + a real judge backend; refuses otherwise.
NO real model call in mock mode or tests (FakeJudge only). Resonance / phonetic-fidelity refinement only — no
GENUTILITY_*, no ONTOLOGICAL_SIGNAL, no semantic-truth/ontology/Sanskrit-privilege claim. B1.4b′ remains
NULL_RETURN_BOTTOM. Original B1.4b + Track B blocked. Structure, not validated meaning.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
import re
from typing import Dict, List, Optional, Tuple

HERE = pathlib.Path(__file__).resolve().parent
FROZEN = HERE / "frozen"
ITEMS_FILE = FROZEN / "b1_10_control_ext_items.json"
V3_TABLE_FILE = FROZEN / "varna_polarity_table_v3.json"
BRIDGE_MANIFEST_FILE = FROZEN / "varna_polarity_bridge_v3.json"
DECOMPOSER_FILE = HERE / "stage_a_prime_coverage.py"

B1_4B_PRIME_STATUS = "NULL_RETURN_BOTTOM"
MODE = "b1_10_control_ext"
REPRESENTATION = "B1.10_control_ext"
DEFAULT_SEED = 20260712
SCALE_MIN, SCALE_MAX = 0, 6
MAX_REDRAWS = 2                 # missing-data: drop + re-draw up to k times
MISSING_INCONCLUSIVE_FRAC = 0.15   # >15% missing cells -> inconclusive
TIERS = ("valence", "source_condition", "specific")
POLES = ("binding", "liberating")
TARGET_WORDS = ("pride", "freedom", "patience", "courage", "control", "doubt")

JUDGE_QUESTION = ("How well does this description describe the inner experiential weather or source-condition "
                  "underlying this word in this context?")
HEADER = ("You are rating a short description against a word used in a sentence, as a heuristic exercise - NOT as "
          "truth. Do NOT claim this proves meaning, is true, ancient, or authoritative. Do NOT mention any system "
          "name. Answer only the question asked.")
SCALE_LINE = ("Rate on an integer scale from 0 to 6 (0 = not at all, 6 = extremely well). "
              "Respond in EXACTLY this format:\nScore: <integer 0-6>\nWhy: <one short sentence>")

# ---- Blinding: structural pole/varṇa/system tokens + ALL target words (packets must never name any target word).
FORBIDDEN_JUDGE_TOKENS = (
    "worldly_binding_distortion", "spiritual_liberating_reading", "binding_packet", "liberating_packet",
    "context_pole", "packet_pole", "correct_pole", "flipped_pole", "expected_pole",
    "binding", "liberating", "SYMBOLU", "Symbol-U", "varṇa", "varna", "KCPR", "fidelity_bundle",
    "worldly_binding", "spiritual_liberating",
)
_FORBIDDEN_RE = re.compile(
    r"(?<![\w-])(?:" + "|".join(re.escape(t) for t in FORBIDDEN_JUDGE_TOKENS) + r")(?![\w-])", re.IGNORECASE)
_VARNA_TAG_RE = re.compile(r"\[[^\]]{1,6}\]")
# Sanskrit / diacritic guard: any non-ASCII letter in judge-visible packet text is a leak (Sanskrit terms carry them)
_NONASCII_RE = re.compile(r"[^\x00-\x7f]")


def packet_leaks(text: str) -> List[str]:
    out = []
    for m in _FORBIDDEN_RE.finditer(text or ""):
        out.append(m.group(0))
    for m in _VARNA_TAG_RE.finditer(text or ""):
        out.append(m.group(0))
    if _NONASCII_RE.search(text or ""):
        out.append("NON_ASCII(diacritic/Sanskrit)")
    for w in TARGET_WORDS:
        if re.search(r"(?<![\w-])" + re.escape(w) + r"(?![\w-])", text or "", re.IGNORECASE):
            out.append(f"target:{w}")
    return out


def _sha_file(p: pathlib.Path) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def load_items() -> Dict:
    return json.loads(ITEMS_FILE.read_text())


# ------------------------------------------------------------------ 72 cells
def build_cells(items: Dict, seed: int = DEFAULT_SEED) -> List[Dict]:
    raw: List[Dict] = []
    for wd in items["words"]:
        w = wd["word"]
        for ctx_pole in POLES:
            for tier in TIERS:
                for pkt_pole in POLES:
                    facets = [f["text"] for f in wd["packets"][tier][pkt_pole]]
                    raw.append({"word": w, "context_pole": ctx_pole, "tier": tier, "packet_pole": pkt_pole,
                                "context_text": wd["contexts"][ctx_pole], "packet_facets": facets})
    raw.sort(key=lambda c: hashlib.sha256(
        f"{seed}|{c['word']}|{c['context_pole']}|{c['tier']}|{c['packet_pole']}".encode()).hexdigest())
    for i, c in enumerate(raw, 1):
        c["cell_id"] = f"E{i:02d}"
        c["prompt"] = render_rating_prompt(c)
    return raw


def _packet_block(facets: List[str]) -> str:
    return "\n".join(f"- {t}" for t in facets) or "- (no description)"


def render_rating_prompt(cell: Dict) -> str:
    return (f"{HEADER}\n\nWord: {cell['word']}\nSentence: {cell['context_text']}\n\n"
            f"Description:\n{_packet_block(cell['packet_facets'])}\n\n"
            f"Question: {JUDGE_QUESTION}\n\n{SCALE_LINE}")


def make_judge_visible(cell: Dict) -> Dict:
    pkg = {"cell_id": cell["cell_id"], "prompt": cell["prompt"]}
    for f in cell["packet_facets"]:
        lk = packet_leaks(f)
        if lk:
            raise ValueError(f"INVALID_BLINDING [{cell['cell_id']}]: packet leak {lk}")
    for hk in ("tier", "packet_pole", "context_pole"):
        if hk in pkg:
            raise ValueError(f"INVALID_BLINDING [{cell['cell_id']}]: hidden key {hk}")
    return pkg


# ------------------------------------------------------------------ parse / FakeJudge
_SCORE_RE = re.compile(r"score\s*:\s*([0-6])\b", re.IGNORECASE)
_WHY_RE = re.compile(r"why\s*:\s*(.+)", re.IGNORECASE)


def parse_rating(text: str) -> Tuple[Optional[int], str, List[str]]:
    m = _SCORE_RE.search(text or "")
    if not m:
        return None, "", ["no parseable Score: <0-6>"]
    score = int(m.group(1))
    if not (SCALE_MIN <= score <= SCALE_MAX):
        return None, "", [f"score {score} out of range"]
    wm = _WHY_RE.search(text or "")
    why = (wm.group(1).splitlines()[0].strip()[:200]) if wm else ""
    return score, why, []


class FakeJudge:
    """Deterministic mock judge. NO model, NO network. Score derived from a hash of the prompt (plumbing only;
    the aggregation is unit-tested separately with hand-set scores)."""
    is_real = False
    backend = "fake_judge"

    def rate(self, prompt: str) -> str:
        h = int(hashlib.sha256(prompt.encode()).hexdigest(), 16)
        return f"Score: {h % (SCALE_MAX + 1)}\nWhy: fixed mock rating for plumbing only."


# ------------------------------------------------------------------ freeze gate (real runs only; no decl exists yet)
def run(mock: bool = True, judge=None, decl_path: Optional[pathlib.Path] = None, seed: int = DEFAULT_SEED,
        out_dir: Optional[pathlib.Path] = None, write: bool = False) -> Dict:
    if not mock:
        if decl_path is None or not pathlib.Path(decl_path).exists():
            raise PermissionError("real run requires a B1.10 control-ext evidence-freeze declaration (none exists yet)")
        if judge is None or getattr(judge, "is_real", False) is not True:
            raise PermissionError("real run requires a real judge backend (none supplied)")
    judge = judge or FakeJudge()
    items = load_items()
    cells = build_cells(items, seed=seed)
    _ = [make_judge_visible(c) for c in cells]        # asserts blinding on all 72

    ratings, failures = [], []
    for c in cells:
        score = why = None
        for _ in range(MAX_REDRAWS + 1):              # missing-data: drop + re-draw up to k
            s, w, rs = parse_rating(judge.rate(c["prompt"]))
            if s is not None:
                score, why = s, w
                break
        if score is None:
            failures.append({"cell_id": c["cell_id"], "word": c["word"], "tier": c["tier"]})
            continue
        ratings.append({"cell_id": c["cell_id"], "word": c["word"], "context_pole": c["context_pole"],
                        "tier": c["tier"], "packet_pole": c["packet_pole"], "score": score,
                        "compliance_note": why})
    part = {
        "artifact_type": "b1_10_control_ext_part", "mode": "MOCK" if mock else "REAL",
        "representation_version": REPRESENTATION, "seed": seed,
        "judge_backend": getattr(judge, "backend", "custom"), "judge_is_real": bool(getattr(judge, "is_real", False)),
        "n_cells": len(cells), "n_rated": len(ratings), "n_failures": len(failures), "failures": failures,
        "input_hashes": {"items": _sha_file(ITEMS_FILE), "v3_table": _sha_file(V3_TABLE_FILE),
                         "bridge_manifest": _sha_file(BRIDGE_MANIFEST_FILE), "decomposer": _sha_file(DECOMPOSER_FILE)},
        "b1_4b_prime_status": B1_4B_PRIME_STATUS, "track_b_status": "BLOCKED",
        "no_verdict_note": "Descriptive statistics only; no accept/reject or positive/null verdict label emitted.",
        "ratings": ratings,
    }
    if write and out_dir:
        out_dir = pathlib.Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "b1_10_control_ext_part.json").write_text(json.dumps(part, ensure_ascii=False, indent=2))
    return part


# ------------------------------------------------------------------ aggregation (pure; all 5 statistics)
def _cell_mean(rows, word, ctx, tier, pole) -> Optional[float]:
    vals = [r["score"] for r in rows if r["word"] == word and r["context_pole"] == ctx
            and r["tier"] == tier and r["packet_pole"] == pole]
    return (sum(vals) / len(vals)) if vals else None


def _tier_margin(rows, word, tier):
    b_cb = _cell_mean(rows, word, "binding", tier, "binding")     # fit(Pb_T|Cb)
    l_cb = _cell_mean(rows, word, "binding", tier, "liberating")  # fit(Pl_T|Cb)
    l_cl = _cell_mean(rows, word, "liberating", tier, "liberating")  # fit(Pl_T|Cl)
    b_cl = _cell_mean(rows, word, "liberating", tier, "binding")  # fit(Pb_T|Cl)
    cells = {"Pb|Cb": b_cb, "Pl|Cb": l_cb, "Pl|Cl": l_cl, "Pb|Cl": b_cl}
    if None in (b_cb, l_cb, l_cl, b_cl):
        return {"cell_means": cells, "incomplete": True}
    bind_dir = b_cb - l_cb
    lib_dir = l_cl - b_cl
    return {"cell_means": cells, "binding_direction_margin": bind_dir,
            "liberating_direction_margin": lib_dir, "margin": bind_dir + lib_dir}


def aggregate(ratings: List[Dict], n_total_cells: int = 72) -> Dict:
    words = []
    for r in ratings:
        if r["word"] not in words:
            words.append(r["word"])
    per_word, complete_words = {}, []
    for w in words:
        m = {t: _tier_margin(ratings, w, t) for t in TIERS}
        incomplete = any(m[t].get("incomplete") for t in TIERS)
        entry = {"tiers": m, "incomplete": incomplete}
        if not incomplete:
            spec, val, sc = m["specific"]["margin"], m["valence"]["margin"], m["source_condition"]["margin"]
            entry.update({
                "specific_margin": spec, "valence_margin": val, "generic_source_condition_margin": sc,
                "increment_over_valence": spec - val,
                "increment_over_source_condition": spec - sc,
            })
            complete_words.append(w)
        per_word[w] = entry

    def _mean(key):
        vals = [per_word[w][key] for w in complete_words]
        return (sum(vals) / len(vals)) if vals else None

    n_missing = n_total_cells - len(ratings)
    status = "inconclusive_missing_data" if (n_missing / n_total_cells) > MISSING_INCONCLUSIVE_FRAC else "complete"
    return {
        "representation_version": REPRESENTATION,
        "per_word": per_word,
        "complete_words": complete_words,
        "excluded_incomplete_words": [w for w in words if per_word[w]["incomplete"]],
        "aggregate": {
            "specific_margin": _mean("specific_margin"),
            "valence_margin": _mean("valence_margin"),
            "generic_source_condition_margin": _mean("generic_source_condition_margin"),
            "increment_over_valence": _mean("increment_over_valence"),
            "increment_over_source_condition": _mean("increment_over_source_condition"),
        },
        "n_cells_expected": n_total_cells, "n_rated": len(ratings), "n_missing": n_missing, "status": status,
        "b1_4b_prime_status": B1_4B_PRIME_STATUS, "track_b_status": "BLOCKED",
        "no_verdict_note": ("Descriptive statistics only; no verdict label. increment_over_source_condition is the "
                            "demanding comparison. Positive = source-condition/resonance legibility to judges only; "
                            "NOT ontology / semantic-truth / Sanskrit-privilege / generation-utility / word-specific "
                            "varṇa mapping."),
    }


# ------------------------------------------------------------------ tier-identifiability diagnostic (style only)
def _style_features(facet: str) -> Dict:
    words = facet.split()
    return {"n_words": len(words), "n_chars": len(facet), "n_commas": facet.count(","),
            "starts_a_an": 1 if words and words[0].lower() in ("a", "an") else 0,
            "has_that": 1 if re.search(r"\bthat\b", facet) else 0}


def tier_identifiability(items: Dict) -> Dict:
    """Diagnostic ONLY (never alters scores): can the tier be guessed from SUPERFICIAL STYLE (length/syntax/
    punctuation), ignoring topical content? Reports per-tier style-feature means + a crude nearest-centroid
    leave-one-out accuracy on style features (chance = 1/3). High accuracy => a style tell to fix before freeze."""
    feats = {t: [] for t in TIERS}
    for wd in items["words"]:
        for t in TIERS:
            for pole in POLES:
                for f in wd["packets"][t][pole]:
                    feats[t].append(_style_features(f["text"]))
    keys = ("n_words", "n_chars", "n_commas", "starts_a_an", "has_that")
    means = {t: {k: round(sum(x[k] for x in feats[t]) / len(feats[t]), 3) for k in keys} for t in TIERS}
    # crude leave-one-out nearest-centroid on style features (n_words, n_chars, n_commas only — the continuous ones)
    cont = ("n_words", "n_chars", "n_commas")
    allpts = [(t, x) for t in TIERS for x in feats[t]]
    correct = 0
    for i, (true_t, x) in enumerate(allpts):
        cent = {}
        for t in TIERS:
            pts = [p for j, (tt, p) in enumerate(allpts) if tt == t and j != i]
            cent[t] = {k: sum(p[k] for p in pts) / len(pts) for k in cont}
        guess = min(TIERS, key=lambda t: sum((x[k] - cent[t][k]) ** 2 for k in cont))
        correct += (guess == true_t)
    acc = round(correct / len(allpts), 3)
    return {"per_tier_style_means": means, "style_only_loo_accuracy": acc, "chance": round(1 / 3, 3),
            "note": ("Diagnostic only; does NOT alter scores. Accuracy near chance => tiers are not separable by "
                     "superficial style (content differs by design). Well-above-chance => a style tell to fix.")}


def main(argv=None):
    ap = argparse.ArgumentParser(description="B1.10 control-ext (three-tier; no-generation; gated; mock-tested).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    dp = sub.add_parser("dry-check")
    dp.add_argument("--seed", type=int, default=DEFAULT_SEED); dp.add_argument("--out")
    rp = sub.add_parser("run")
    rp.add_argument("--decl", required=True); rp.add_argument("--seed", type=int, default=DEFAULT_SEED)
    rp.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "dry-check":
        part = run(mock=True, seed=args.seed, out_dir=pathlib.Path(args.out) if args.out else None, write=bool(args.out))
        agg = aggregate(part["ratings"])
        diag = tier_identifiability(load_items())
        print(json.dumps({"mode": part["mode"], "n_cells": part["n_cells"], "n_rated": part["n_rated"],
                          "judge_is_real": part["judge_is_real"], "status": agg["status"],
                          "aggregate": agg["aggregate"], "tier_style_loo_accuracy": diag["style_only_loo_accuracy"],
                          "chance": diag["chance"],
                          "note": "MOCK plumbing only — FakeJudge scores are not meaningful; no verdict."}, indent=2))
        return
    if args.cmd == "run":
        raise SystemExit("real run requires a real judge backend + an evidence-freeze declaration (none exists yet); "
                         "refusing. Use dry-check for plumbing.")


if __name__ == "__main__":
    main()
