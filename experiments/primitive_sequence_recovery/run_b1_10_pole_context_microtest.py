"""B1.10 pole-context sanity MICRO-TEST driver (no-generation rating; gated; blinded; mock-tested).

Design (prereg 95d08dc, approved for MOCK implementation only): 3 words {happy, peace, love}, each in two
contexts (binding / other-conditioned; liberating / self-grounded). Each word has two CONTEXT-INVARIANT packets
(binding / liberating), fixed by its varṇas. The judge rates, per cell, on a 0–6 scale:

    "How well does this packet describe the inner experiential weather or source-condition underlying this word
     in this context?"

2 contexts × 2 packets × 3 words = 12 rating cells. NO text is generated; the judge only rates existing packets.
No synonyms/opposites; no dictionary-fit question.

Primary statistic (per prereg §5), computed at aggregation from cell-mean scores:
    binding_direction_margin(w)    = fit(Pb|Cb) - fit(Pl|Cb)
    liberating_direction_margin(w) = fit(Pl|Cl) - fit(Pb|Cl)
    context_pole_margin(w)         = binding_direction_margin(w) + liberating_direction_margin(w)
    aggregate mean margin          = mean over words of context_pole_margin
where Pb/Pl = binding/liberating packet, Cb/Cl = binding/liberating context.

Blinding: the judge sees ONLY the word, the context sentence, and the packet's plain facet text — never a pole
label, varṇa tag, expected-answer indicator, or any system name. Cell order is deterministically shuffled under a
seed. A compliance one-liner is captured for AUDIT only (never scored).

**No result label is emitted.** The driver reports margins/cell means; interpretation is deferred to the operator
(prereg §9). A positive margin would show only source-condition / resonance legibility to judges — NOT ontology,
semantic truth, Sanskrit privilege, generation utility, or word-specific varṇa mapping. A null means the
pole-context distinction is not legible under this rating design.

Real judges require a gated EVIDENCE_FREEZE_DECLARED (like the other B1.9 drivers); NO real model call happens in
mock mode or in tests (FakeJudge only). Resonance / phonetic-fidelity refinement only — no GENUTILITY_*, no
ONTOLOGICAL_SIGNAL, no semantic-truth/ontology/Sanskrit-privilege claim. B1.4b′ remains NULL_RETURN_BOTTOM.
Original B1.4b + Track B remain blocked. Structure, not validated meaning.
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
ITEMS_FILE = FROZEN / "b1_10_pole_context_microtest_items.json"
V3_TABLE_FILE = FROZEN / "varna_polarity_table_v3.json"
BRIDGE_MANIFEST_FILE = FROZEN / "varna_polarity_bridge_v3.json"
DECOMPOSER_FILE = HERE / "stage_a_prime_coverage.py"
PREREG_FILE = HERE / "POLE_CONTEXT_MICROTEST_PREREG.md"

B1_4B_PRIME_STATUS = "NULL_RETURN_BOTTOM"
MODE = "b1_10_pole_context_microtest"
REPRESENTATION = "B1.10_pole_context"
DEFAULT_SEED = 20260712
SCALE_MIN, SCALE_MAX = 0, 6

ATTESTATION = ("B1.10 pole-context micro-test; no-generation packet rating; 3 words x 2 contexts x 2 packets; "
               "source-condition fit only; no dictionary-fit, no synonyms/opposites; no semantic-truth claim; "
               "no GENUTILITY terminal label; B1.4b′ remains NULL_RETURN_BOTTOM.")

HASH_INPUTS = {
    "prereg_sha256": PREREG_FILE, "items_sha256": ITEMS_FILE, "v3_table_sha256": V3_TABLE_FILE,
    "bridge_manifest_sha256": BRIDGE_MANIFEST_FILE, "decomposer_sha256": DECOMPOSER_FILE,
}
REQUIRED_DECL_FIELDS = ("artifact", "evidence_freeze_declared", "mode", "representation_version",
                        "declared_by", "declared_at_utc", "attestation", *HASH_INPUTS.keys())
BAD_MODES = {"b1_9_pole_did_probe", "b1_9_pole_sanity", "pilot_generation",
             "b1_8_context_resolved_generation_probe", "b1_9_content_level_semantic_distance"}

# The one question the judge is asked (no other question is posed).
JUDGE_QUESTION = ("How well does this packet describe the inner experiential weather or source-condition "
                  "underlying this word in this context?")
HEADER = ("You are rating a short description against a word used in a sentence, as a heuristic exercise - NOT as "
          "truth. Do NOT claim this proves meaning, is true, ancient, or authoritative. Do NOT mention any system "
          "name. Answer only the question asked.")
SCALE_LINE = ("Rate on an integer scale from 0 to 6 (0 = not at all, 6 = extremely well). "
              "Respond in EXACTLY this format:\nScore: <integer 0-6>\nWhy: <one short sentence>")

# ---- Blinding: STRUCTURAL tokens only (pole field-names, varṇa terms, system names, expected-answer markers).
# NOTE: natural words like "spiritual"/"worldly" can appear inside facet CONTENT for other words and are NOT
# forbidden here (verified absent for happy/peace/love); we forbid only structural leak tokens + the bare pole
# labels + varṇa-tag brackets that the render never inserts.
FORBIDDEN_JUDGE_TOKENS = (
    "worldly_binding_distortion", "spiritual_liberating_reading", "binding_packet", "liberating_packet",
    "context_pole", "packet_pole", "correct_pole", "flipped_pole", "expected_pole", "packet_role",
    "binding", "liberating", "SYMBOLU", "Symbol-U", "varṇa", "varna", "KCPR", "fidelity_bundle",
    "worldly_binding", "spiritual_liberating",
)
_FORBIDDEN_RE = re.compile(
    r"(?<![\w-])(?:" + "|".join(re.escape(t) for t in FORBIDDEN_JUDGE_TOKENS) + r")(?![\w-])", re.IGNORECASE)
_VARNA_TAG_RE = re.compile(r"\[[^\]]{1,6}\]")   # bracketed varṇa tags like [pa], [dda]; never inserted by render


def leaked_judge_tokens(text: str) -> List[str]:
    seen, out = set(), []
    for m in _FORBIDDEN_RE.finditer(text or ""):
        low = m.group(0).lower()
        if low not in seen:
            seen.add(low); out.append(m.group(0))
    for m in _VARNA_TAG_RE.finditer(text or ""):
        if m.group(0) not in out:
            out.append(m.group(0))
    return out


def _sha_file(p: pathlib.Path) -> str:
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def load_items() -> Dict:
    return json.loads(ITEMS_FILE.read_text())


# ------------------------------------------------------------------ cell construction (12 cells)
def build_cells(items: Dict, seed: int = DEFAULT_SEED) -> List[Dict]:
    """The 12 rating cells (3 words x 2 contexts x 2 packets), deterministically shuffled under `seed`.

    Each cell carries hidden truth fields (context_pole, packet_pole, word) for later scoring and a judge-visible
    prompt that contains NONE of them.
    """
    raw: List[Dict] = []
    for wd in items["words"]:
        w = wd["word"]
        for ctx_pole in ("binding", "liberating"):
            for pkt_pole in ("binding", "liberating"):
                facets = wd["packets"][pkt_pole]
                cell = {
                    "word": w, "context_pole": ctx_pole, "packet_pole": pkt_pole,
                    "context_text": wd["contexts"][ctx_pole], "packet_facets": [f["text"] for f in facets],
                }
                raw.append(cell)
    # deterministic shuffle: sort by a seeded hash of the cell identity (no Math.random / no wall clock)
    raw.sort(key=lambda c: hashlib.sha256(
        f"{seed}|{c['word']}|{c['context_pole']}|{c['packet_pole']}".encode()).hexdigest())
    for i, c in enumerate(raw, 1):
        c["cell_id"] = f"C{i:02d}"
        c["prompt"] = render_rating_prompt(c)
    return raw


def _packet_block(facets: List[str]) -> str:
    return "\n".join(f"- {t}" for t in facets) or "- (no description)"


def render_rating_prompt(cell: Dict) -> str:
    """Judge-visible prompt: word + context sentence + packet facet TEXT + the one question + scale.
    Contains no pole label, no varṇa tag, no expected-answer indicator, no system name."""
    prompt = (f"{HEADER}\n\n"
              f"Word: {cell['word']}\n"
              f"Sentence: {cell['context_text']}\n\n"
              f"Description:\n{_packet_block(cell['packet_facets'])}\n\n"
              f"Question: {JUDGE_QUESTION}\n\n{SCALE_LINE}")
    return prompt


def make_judge_visible(cell: Dict) -> Dict:
    """Strip to judge-safe fields and assert no structural leak."""
    pkg = {"cell_id": cell["cell_id"], "prompt": cell["prompt"]}
    lk = leaked_judge_tokens(cell["prompt"])
    if lk:
        raise ValueError(f"INVALID_BLINDING [{cell['cell_id']}]: leaked structural tokens {lk}")
    hidden_keys = {"context_pole", "packet_pole", "word"} & set(pkg.keys())
    if hidden_keys:
        raise ValueError(f"INVALID_BLINDING [{cell['cell_id']}]: hidden keys present {sorted(hidden_keys)}")
    return pkg


# ------------------------------------------------------------------ scoring / parsing
_SCORE_RE = re.compile(r"score\s*:\s*([0-6])\b", re.IGNORECASE)
_WHY_RE = re.compile(r"why\s*:\s*(.+)", re.IGNORECASE)


def parse_rating(text: str) -> Tuple[Optional[int], str, List[str]]:
    """Parse 'Score: N' + 'Why: ...'. Returns (score|None, why_oneliner, reasons)."""
    reasons = []
    m = _SCORE_RE.search(text or "")
    if not m:
        return None, "", ["no parseable Score: <0-6>"]
    score = int(m.group(1))
    if not (SCALE_MIN <= score <= SCALE_MAX):
        reasons.append(f"score {score} out of range")
    wm = _WHY_RE.search(text or "")
    why = (wm.group(1).strip() if wm else "").splitlines()[0][:200] if wm else ""
    return (score if not reasons else None), why, reasons


# ------------------------------------------------------------------ deterministic FakeJudge (NO model, NO network)
class FakeJudge:
    """Deterministic mock judge. Returns a well-formed 'Score: N / Why: ...' with N derived from a hash of the
    prompt. NO model and NO network. For the statistic test we do NOT rely on these values — the aggregation is
    unit-tested with hand-set scores; FakeJudge only exercises the plumbing."""
    is_real = False
    backend = "fake_judge"

    def rate(self, prompt: str) -> str:
        h = int(hashlib.sha256(prompt.encode()).hexdigest(), 16)
        score = h % (SCALE_MAX + 1)
        return f"Score: {score}\nWhy: a fixed mock rating for plumbing only."


# ------------------------------------------------------------------ freeze gate (real runs only)
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
    if decl.get("artifact") != "b1_10_pole_context_EVIDENCE_FREEZE_DECLARED":
        reasons.append("artifact != b1_10_pole_context_EVIDENCE_FREEZE_DECLARED")
    if decl.get("evidence_freeze_declared") is not True:
        reasons.append("evidence_freeze_declared != true")
    if decl.get("mode") in BAD_MODES:
        reasons.append(f"refused: other-track mode supplied ({decl.get('mode')!r})")
    if decl.get("mode") != expected_mode:
        reasons.append(f"mode != {expected_mode} (got {decl.get('mode')!r})")
    if decl.get("representation_version") != REPRESENTATION:
        reasons.append(f"representation_version != {REPRESENTATION}")
    if decl.get("attestation") != ATTESTATION:
        reasons.append("attestation text mismatch")
    if reasons:
        return False, reasons
    for field, path in HASH_INPUTS.items():
        if not path.exists():
            reasons.append(f"frozen input missing: {path.name}")
        elif decl.get(field) != _sha_file(path):
            reasons.append(f"{field} mismatch")
    return (not reasons), reasons


# ------------------------------------------------------------------ run (mock or gated real)
def run(mock: bool = True, judge=None, decl_path: Optional[pathlib.Path] = None, seed: int = DEFAULT_SEED,
        out_dir: Optional[pathlib.Path] = None, write: bool = False) -> Dict:
    if not mock:
        if decl_path is None:
            raise PermissionError("real run requires a B1.10 pole-context evidence-freeze declaration path")
        ok, reasons = verify_freeze_gate(pathlib.Path(decl_path))
        if not ok:
            raise PermissionError("EVIDENCE_FREEZE gate refused: " + "; ".join(reasons))
        if judge is None or getattr(judge, "is_real", False) is not True:
            raise PermissionError("real run requires a real judge backend (none supplied)")
    judge = judge or FakeJudge()
    items = load_items()
    cells = build_cells(items, seed=seed)
    judge_visible = [make_judge_visible(c) for c in cells]        # asserts blinding

    ratings, failures = [], []
    for c in cells:
        text = judge.rate(c["prompt"])
        score, why, rs = parse_rating(text)
        if score is None:
            failures.append({"cell_id": c["cell_id"], "reasons": rs})
            continue
        ratings.append({
            "cell_id": c["cell_id"], "word": c["word"], "context_pole": c["context_pole"],
            "packet_pole": c["packet_pole"], "score": score,
            "compliance_note": why,                                # AUDIT ONLY — never scored
        })

    part = {
        "artifact_type": "b1_10_pole_context_part", "mode": "MOCK" if mock else "REAL",
        "representation_version": REPRESENTATION, "seed": seed, "judge_backend": getattr(judge, "backend", "custom"),
        "judge_is_real": bool(getattr(judge, "is_real", False)),
        "n_cells": len(cells), "n_rated": len(ratings), "n_failures": len(failures), "failures": failures,
        "primary_statistic": ("context_pole_margin = (fit(Pb|Cb)-fit(Pl|Cb)) + (fit(Pl|Cl)-fit(Pb|Cl)); "
                              "aggregate = mean over words"),
        "input_hashes": {k: _sha_file(v) for k, v in HASH_INPUTS.items()},
        "declaration_sha256": _sha_file(pathlib.Path(decl_path)) if (decl_path and not mock) else None,
        "b1_4b_prime_status": B1_4B_PRIME_STATUS, "track_b_status": "BLOCKED",
        "no_verdict_note": "No result label emitted. Margins are descriptive; interpretation deferred to operator "
                           "(prereg §9). A positive margin = source-condition/resonance legibility only.",
        "ratings": ratings,
    }
    if write and out_dir:
        out_dir = pathlib.Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "b1_10_pole_context_part.json").write_text(json.dumps(part, ensure_ascii=False, indent=2))
        (out_dir / "b1_10_judge_visible_cells.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in judge_visible) + "\n")
    return part


# ------------------------------------------------------------------ aggregation (pure; prereg §5)
def _cell_mean(rows: List[Dict], word: str, ctx: str, pkt: str) -> Optional[float]:
    vals = [r["score"] for r in rows if r["word"] == word and r["context_pole"] == ctx and r["packet_pole"] == pkt]
    return (sum(vals) / len(vals)) if vals else None


def aggregate(ratings: List[Dict]) -> Dict:
    """Compute cell means + margins per prereg §5. Pure function of the rating rows (unit-tested with hand-set
    scores). Emits NO verdict/label."""
    words = []
    seen = []
    for r in ratings:
        if r["word"] not in seen:
            seen.append(r["word"])
    per_word = {}
    margins = []
    for w in seen:
        b_cb = _cell_mean(ratings, w, "binding", "binding")       # fit(Pb|Cb)
        l_cb = _cell_mean(ratings, w, "binding", "liberating")    # fit(Pl|Cb)
        l_cl = _cell_mean(ratings, w, "liberating", "liberating")  # fit(Pl|Cl)
        b_cl = _cell_mean(ratings, w, "liberating", "binding")    # fit(Pb|Cl)
        if None in (b_cb, l_cb, l_cl, b_cl):
            per_word[w] = {"incomplete": True,
                           "cell_means": {"Pb|Cb": b_cb, "Pl|Cb": l_cb, "Pl|Cl": l_cl, "Pb|Cl": b_cl}}
            continue
        binding_dir = b_cb - l_cb
        liberating_dir = l_cl - b_cl
        margin = binding_dir + liberating_dir
        margins.append(margin)
        per_word[w] = {
            "cell_means": {"Pb|Cb": b_cb, "Pl|Cb": l_cb, "Pl|Cl": l_cl, "Pb|Cl": b_cl},
            "binding_direction_margin": binding_dir,
            "liberating_direction_margin": liberating_dir,
            "context_pole_margin": margin,
        }
    return {
        "representation_version": REPRESENTATION,
        "per_word": per_word,
        "aggregate_mean_margin": (sum(margins) / len(margins)) if margins else None,
        "n_words_complete": len(margins),
        "b1_4b_prime_status": B1_4B_PRIME_STATUS, "track_b_status": "BLOCKED",
        "no_verdict_note": "Descriptive statistics only; no accept/reject or positive/null verdict label emitted here. "
                           "Interpretation deferred to operator per prereg §9. Positive margin = source-condition "
                           "/ resonance legibility only; NOT ontology / semantic-truth / Sanskrit-privilege / "
                           "generation-utility / word-specific varṇa mapping.",
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="B1.10 pole-context micro-test (no-generation rating; gated; mock-tested).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    dp = sub.add_parser("dry-check", help="build cells + FakeJudge + aggregate; NO real judge, writes to --out if given")
    dp.add_argument("--seed", type=int, default=DEFAULT_SEED)
    dp.add_argument("--out")
    rp = sub.add_parser("run", help="gated real run (requires EVIDENCE_FREEZE_DECLARED + real judge backend)")
    rp.add_argument("--decl", required=True)
    rp.add_argument("--seed", type=int, default=DEFAULT_SEED)
    rp.add_argument("--out", required=True)

    args = ap.parse_args(argv)
    if args.cmd == "dry-check":
        part = run(mock=True, seed=args.seed, out_dir=pathlib.Path(args.out) if args.out else None,
                   write=bool(args.out))
        agg = aggregate(part["ratings"])
        print(json.dumps({"mode": part["mode"], "n_cells": part["n_cells"], "n_rated": part["n_rated"],
                          "judge_backend": part["judge_backend"], "judge_is_real": part["judge_is_real"],
                          "aggregate_mean_margin": agg["aggregate_mean_margin"],
                          "note": "MOCK plumbing only — FakeJudge scores are not meaningful; no verdict."}, indent=2))
        return
    if args.cmd == "run":
        # No real judge backend is wired in this environment; the gate will refuse without one.
        raise SystemExit("real run requires a real judge backend to be supplied programmatically; refusing "
                         "(mock-only environment). Use dry-check for plumbing.")


if __name__ == "__main__":
    main()
