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

# ---- Stage-4 real-run gate (fail-closed) -------------------------------------------------------
APPROVED_ITEMS_FILE = FROZEN / "b1_10_control_ext_items_v3_qwen.json"   # ONLY approved items file
DEFAULT_DECL_FILE = FROZEN / "b1_10_control_ext_v3_EVIDENCE_FREEZE_DECLARED.json"
ALLOWED_JUDGE_IDS = ("meta-llama/Llama-3.1-8B-Instruct",
                     "meta-llama/Meta-Llama-3-8B-Instruct",
                     "google/gemma-2-9b-it")
FORBIDDEN_JUDGE_SUBSTRINGS = ("claude", "anthropic", "mistral", "qwen", "gpt", "gemini", "phi", "yi-")
DECLARED_SHUFFLE_SEEDS = (20260712, 20260713)
UNRESOLVED_REVS = {None, "", "main", "master", "HEAD", "latest"}
RUN_ROOT = HERE / "runs"                       # git-ignored (see repo .gitignore `runs/`)
EXPECTED_TOTAL_RATINGS = 216                   # 72 cells x 3 judges


class FreezeGateError(PermissionError):
    """Raised (fail-closed) when any real-run precondition fails; a subclass of PermissionError so
    existing `except PermissionError` handlers still catch it."""

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


def load_items(items_file: pathlib.Path = ITEMS_FILE) -> Dict:
    return json.loads(pathlib.Path(items_file).read_text())


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


# ------------------------------------------------------------------ Stage-4 fail-closed real-run gate
def _recompute_pins(decl: Dict, base_dir: pathlib.Path) -> List[str]:
    """Recompute every pinned input hash against the live file; return a list of mismatch keys (empty = OK)."""
    mism: List[str] = []
    pins = decl.get("pinned_input_hashes", {})
    for key, rec in pins.items():
        if "path" not in rec:
            continue
        p = base_dir / rec["path"]
        if not p.exists():
            mism.append(f"{key}:MISSING_FILE({rec['path']})")
            continue
        if _sha_file(p) != rec.get("sha256"):
            mism.append(f"{key}:HASH_MISMATCH({rec['path']})")
    # derived canonical 12-sentence block (from the approved context source file)
    cb, src = pins.get("approved_canonical_12_sentence_block"), pins.get("approved_context_source_file")
    if cb and src:
        md = (base_dir / src["path"]).read_text()
        try:
            block = md.split("```")[1].strip("\n") + "\n"
        except IndexError:
            mism.append("approved_canonical_12_sentence_block:NO_FENCED_BLOCK")
            block = ""
        if block and hashlib.sha256(block.encode("utf-8")).hexdigest() != cb.get("sha256"):
            mism.append("approved_canonical_12_sentence_block:HASH_MISMATCH")
    return mism


def _abort(reason: str):
    raise FreezeGateError("FREEZE_GATE_ABORT: " + reason)


def preflight_inputs(decl_path, items_file, seeds, expected_decl_sha: Optional[str] = None,
                     base_dir: pathlib.Path = HERE) -> Dict:
    """Checks 1-3 + 6 (declaration integrity, live input hashes, approved-items enforcement, seeds).
    No judge objects needed; usable as an operator preflight. Raises FreezeGateError; returns
    {decl, decl_sha, cells} on success."""
    # 1) declaration integrity
    dp = pathlib.Path(decl_path) if decl_path else None
    if dp is None or not dp.exists():
        _abort("real run requires the evidence-freeze declaration (declaration missing or not found)")
    decl_bytes = dp.read_bytes()
    decl_sha = hashlib.sha256(decl_bytes).hexdigest()
    if expected_decl_sha and decl_sha != expected_decl_sha:
        _abort(f"declaration SHA256 mismatch (expected {expected_decl_sha}, live {decl_sha})")
    decl = json.loads(decl_bytes)
    if decl.get("evidence_freeze_declared") is not True:
        _abort("declaration evidence_freeze_declared is not true")
    ei = decl.get("experiment_identity", {})
    if ei.get("mode") != MODE:
        _abort(f"declaration mode != {MODE}")
    if ei.get("mapping_era") != "fidelity_bundle_v1":
        _abort("declaration mapping_era != fidelity_bundle_v1")
    rv = (ei.get("representation_version") or "").lower()
    if "v3" not in rv or "qwen" not in rv:
        _abort("declaration representation_version is not the approved v3-Qwen control extension")
    if "B1.10" not in (ei.get("experiment_number") or ""):
        _abort("declaration experiment_number is not B1.10")

    # 2) live input hash verification (all pinned files, incl. runner + builder)
    mism = _recompute_pins(decl, base_dir)
    if mism:
        _abort("pinned input hash mismatch -> " + "; ".join(mism))

    # 3) approved item-file enforcement
    ip = pathlib.Path(items_file).resolve()
    if ip != APPROVED_ITEMS_FILE.resolve():
        _abort(f"wrong items file: only {APPROVED_ITEMS_FILE.name} is permitted (rejecting {ip.name})")
    if _sha_file(ip) != decl["pinned_input_hashes"]["rebuilt_v3_items_file"]["sha256"]:
        _abort("approved items file hash != declaration pin")
    if not seeds:
        _abort("no cell-shuffle seed provided")
    items = load_items(ip)
    cells = build_cells(items, seed=seeds[0])
    combos = {(c["word"], c["context_pole"], c["tier"], c["packet_pole"]) for c in cells}
    expected_combos = {(w, ctx, t, p) for w in TARGET_WORDS for ctx in POLES for t in TIERS for p in POLES}
    if len(cells) != 72 or len(combos) != 72:
        _abort(f"cell set is not 72 unique cells (n={len(cells)}, unique={len(combos)})")
    if combos != expected_combos:
        _abort("duplicate/missing cell combination detected")

    # 6) seed / order enforcement
    declared_seeds = tuple(decl.get("run_structure", {}).get("deterministic_cell_shuffle_seeds", ()))
    if declared_seeds != DECLARED_SHUFFLE_SEEDS:
        _abort(f"declaration seeds {declared_seeds} != canonical declared seeds {DECLARED_SHUFFLE_SEEDS}")
    for s in seeds:
        if s not in DECLARED_SHUFFLE_SEEDS:
            _abort(f"seed {s} is not one of the declared seeds {DECLARED_SHUFFLE_SEEDS}")
    return {"decl": decl, "decl_sha256": decl_sha, "cells": cells}


def verify_real_run_preconditions(decl_path, items_file, judges, seeds,
                                  expected_decl_sha: Optional[str] = None,
                                  base_dir: pathlib.Path = HERE) -> Dict:
    """Full fail-closed gate run BEFORE the first judge call (checks 1-6). Raises FreezeGateError on ANY
    violation; on success returns a validated plan. Performs NO model call. Returning == 'backend
    boundary' cleared to rate."""
    abort = _abort
    pf = preflight_inputs(decl_path, items_file, seeds, expected_decl_sha=expected_decl_sha, base_dir=base_dir)
    decl, decl_sha, cells = pf["decl"], pf["decl_sha256"], pf["cells"]
    ip = pathlib.Path(items_file).resolve()

    # 4) judge-panel enforcement
    judges = list(judges or [])
    if not judges:
        abort("real judge backend required (no judges supplied)")
    for j in judges:
        if getattr(j, "is_real", False) is not True:
            abort(f"real judge backend required (judge '{getattr(j, 'model_id', '?')}' is not a real backend)")
    ids = [getattr(j, "model_id", None) for j in judges]
    if any(i is None for i in ids):
        abort("a judge is missing model_id")
    for i in ids:
        if any(s in i.lower() for s in FORBIDDEN_JUDGE_SUBSTRINGS):
            abort(f"forbidden judge family: {i} (no Claude/Mistral/Qwen/etc.)")
    if sorted(ids) != sorted(ALLOWED_JUDGE_IDS):
        abort(f"judge panel must be EXACTLY {list(ALLOWED_JUDGE_IDS)}; got {ids}")
    if len(set(ids)) != 3:
        abort("judge panel must be three distinct model IDs")
    for j in judges:
        if getattr(j, "temperature", None) not in (0, 0.0):
            abort(f"judges must use greedy decoding (temperature 0); '{j.model_id}' is not temp 0")
        if tuple(getattr(j, "scale", (SCALE_MIN, SCALE_MAX))) != (SCALE_MIN, SCALE_MAX):
            abort(f"judge scale must be {SCALE_MIN}-{SCALE_MAX}; '{j.model_id}' differs")
        if getattr(j, "rubric", "b1_10_0_6") != "b1_10_0_6":
            abort(f"judge rubric must be the B1.10 0-6 rubric; '{j.model_id}' differs")

    # 5) judge revision handling (must be resolved; never silent 'main')
    revs = {}
    for j in judges:
        r = getattr(j, "revision_resolved", None)
        if r in UNRESOLVED_REVS:
            abort(f"unresolved judge revision for '{getattr(j, 'model_id', '?')}' (resolve the commit before rating)")
        revs[j.model_id] = r

    return {"cleared": True, "declaration_sha256": decl_sha, "n_cells": len(cells),
            "expected_total_ratings": len(judges) * len(cells), "judge_revisions": revs,
            "seeds": list(seeds), "approved_items_sha256": _sha_file(ip),
            "judge_ids": list(ALLOWED_JUDGE_IDS)}


def _verify_gitignored(path: pathlib.Path) -> bool:
    """True iff `git check-ignore` says the path is ignored (output-dir gating)."""
    import subprocess
    try:
        r = subprocess.run(["git", "check-ignore", "-q", str(path)], cwd=str(HERE),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except Exception:
        return False


def run_real_gated(decl_path, judges, seed: int = DEFAULT_SEED, run_id: Optional[str] = None,
                   items_file: pathlib.Path = APPROVED_ITEMS_FILE, expected_decl_sha: Optional[str] = None,
                   run_root: pathlib.Path = RUN_ROOT) -> Dict:
    """Fully-gated real run. Verifies preconditions (fail-closed), then rates all 72 cells with each of
    the three judges, writing raw outputs / parsed ratings / per-judge manifests / aggregation inputs to a
    UNIQUE, git-ignored run directory. Emits NO verdict label. Requires real judges (runs on the pod)."""
    plan = verify_real_run_preconditions(decl_path, items_file, judges, [seed],
                                         expected_decl_sha=expected_decl_sha)
    if run_id is None:
        abort_msg = "run_id is required (unique; never overwrite a prior run)"
        raise FreezeGateError("FREEZE_GATE_ABORT: " + abort_msg)
    run_dir = pathlib.Path(run_root) / f"b1_10_control_ext_v3_run_{run_id}"
    if not _verify_gitignored(run_dir):
        raise FreezeGateError("FREEZE_GATE_ABORT: run directory is not git-ignored (refusing to write outputs)")
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FreezeGateError(f"FREEZE_GATE_ABORT: run directory already exists and is non-empty: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)

    items = load_items(items_file)
    cells = build_cells(items, seed=seed)
    _ = [make_judge_visible(c) for c in cells]        # re-assert blinding on all 72 before any rating

    all_ratings, per_judge = [], []
    for j in judges:
        jdir = run_dir / j.model_id.replace("/", "__")
        jdir.mkdir(parents=True, exist_ok=True)
        jr = []
        for c in cells:
            raw = j.rate(c["prompt"])              # <-- the ONLY model call; real judges only
            (jdir / f"{c['cell_id']}.raw.txt").write_text(raw, encoding="utf-8")
            score, why, errs = parse_rating(raw)
            row = {"cell_id": c["cell_id"], "word": c["word"], "context_pole": c["context_pole"],
                   "tier": c["tier"], "packet_pole": c["packet_pole"], "score": score,
                   "why": why, "parse_errors": errs}
            jr.append(row)
            all_ratings.append({"judge": j.model_id, **row})
        (jdir / "parsed_ratings.json").write_text(json.dumps(jr, ensure_ascii=False, indent=2))
        (jdir / "per_judge_manifest.json").write_text(json.dumps({
            "model_id": j.model_id, "revision_resolved": plan["judge_revisions"][j.model_id],
            "decoding": "greedy", "temperature": 0, "scale": [SCALE_MIN, SCALE_MAX], "rubric": "b1_10_0_6",
            "seed": seed, "n_cells": len(cells), "n_rated": sum(1 for r in jr if r["score"] is not None),
        }, ensure_ascii=False, indent=2))
        per_judge.append({"model_id": j.model_id, "n_rated": sum(1 for r in jr if r["score"] is not None)})
        getattr(j, "close", lambda: None)()          # free this judge's VRAM before the next (one model at a time)

    run_manifest = {
        "artifact": "b1_10_control_ext_v3_real_run", "run_id": run_id, "mode": "REAL",
        "declaration_sha256": plan["declaration_sha256"], "approved_items_sha256": plan["approved_items_sha256"],
        "judge_revisions": plan["judge_revisions"], "seed": seed,
        "n_cells": len(cells), "n_judges": len(judges), "expected_total_ratings": plan["expected_total_ratings"],
        "n_ratings_collected": len(all_ratings), "per_judge": per_judge,
        "no_verdict_note": "Raw ratings + aggregation inputs only; NO accept/reject or positive/null verdict emitted here.",
        "b1_4b_prime_status": B1_4B_PRIME_STATUS, "track_b_status": "BLOCKED",
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(run_manifest, ensure_ascii=False, indent=2))
    (run_dir / "aggregation_inputs.json").write_text(json.dumps(all_ratings, ensure_ascii=False, indent=2))
    return run_manifest


# ------------------------------------------------------------------ mock harness (dry-check only)
def run(mock: bool = True, judge=None, decl_path: Optional[pathlib.Path] = None, seed: int = DEFAULT_SEED,
        out_dir: Optional[pathlib.Path] = None, write: bool = False,
        items_file: pathlib.Path = ITEMS_FILE, judges=None, expected_decl_sha: Optional[str] = None) -> Dict:
    if not mock:
        # route real runs through the fail-closed gate (replaces the old presence-only check)
        panel = judges if judges is not None else ([judge] if judge is not None else [])
        verify_real_run_preconditions(decl_path, items_file, panel, [seed], expected_decl_sha=expected_decl_sha)
        # gate cleared; the actual real rating is performed by run_real_gated (pod driver), never here.
        raise FreezeGateError("FREEZE_GATE_ABORT: gate cleared but run() is mock-only; use run_real_gated() "
                              "with real judges on the GPU host.")
    judge = judge or FakeJudge()
    items = load_items(items_file)
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
        "input_hashes": {"items": _sha_file(items_file), "v3_table": _sha_file(V3_TABLE_FILE),
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
    dp.add_argument("--items", default=None, help="items file to dry-check (default: original excluded-context file)")
    rp = sub.add_parser("run")
    rp.add_argument("--decl", required=True); rp.add_argument("--seed", type=int, default=DEFAULT_SEED)
    rp.add_argument("--out", required=True)
    rp.add_argument("--items", default=None, help="approved items file for the real run")
    pf = sub.add_parser("preflight", help="operator preflight: declaration+hashes+items+seed (no judges, no model)")
    pf.add_argument("--decl", default=str(DEFAULT_DECL_FILE))
    pf.add_argument("--items", default=str(APPROVED_ITEMS_FILE))
    pf.add_argument("--seed", type=int, default=DEFAULT_SEED)
    pf.add_argument("--expect-decl-sha", default=None)
    args = ap.parse_args(argv)
    if args.cmd == "dry-check":
        items_file = pathlib.Path(args.items) if args.items else ITEMS_FILE
        part = run(mock=True, seed=args.seed, out_dir=pathlib.Path(args.out) if args.out else None,
                   write=bool(args.out), items_file=items_file)
        agg = aggregate(part["ratings"])
        diag = tier_identifiability(load_items(items_file))
        print(json.dumps({"mode": part["mode"], "n_cells": part["n_cells"], "n_rated": part["n_rated"],
                          "items_file": items_file.name,
                          "judge_is_real": part["judge_is_real"], "status": agg["status"],
                          "aggregate": agg["aggregate"], "tier_style_loo_accuracy": diag["style_only_loo_accuracy"],
                          "chance": diag["chance"],
                          "note": "MOCK plumbing only — FakeJudge scores are not meaningful; no verdict."}, indent=2))
        return
    if args.cmd == "preflight":
        items_file = pathlib.Path(args.items)
        pfres = preflight_inputs(pathlib.Path(args.decl), items_file, [args.seed],
                                 expected_decl_sha=args.expect_decl_sha)
        print(json.dumps({"preflight": "PASS", "declaration_sha256": pfres["decl_sha256"],
                          "items_file": items_file.name, "n_cells": len(pfres["cells"]),
                          "expected_total_ratings": EXPECTED_TOTAL_RATINGS, "seed": args.seed,
                          "note": "inputs consistent with the declaration; judge panel + revisions are checked "
                                  "by verify_real_run_preconditions at real-run time. NO model call."}, indent=2))
        return
    if args.cmd == "run":
        # The CLI cannot construct pod judge backends; the real run is driven by run_real_gated() on the
        # GPU host (see B1_10_STAGE4_RUN_RUNBOOK.md). Here we run the fail-closed preflight and then refuse.
        items_file = pathlib.Path(args.items) if args.items else APPROVED_ITEMS_FILE
        preflight_inputs(pathlib.Path(args.decl), items_file, [args.seed])   # aborts on any mismatch
        raise SystemExit("preflight passed; real judges must be supplied on the GPU host via run_real_gated() "
                         "(see B1_10_STAGE4_RUN_RUNBOOK.md). Refusing to fabricate a backend.")


if __name__ == "__main__":
    main()
