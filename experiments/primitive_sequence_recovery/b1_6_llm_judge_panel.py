"""B1.6-v2 automated LLM-as-judge panel (gated inputs; mock-tested only).

Runs a 3-judge panel over the BLIND judge-visible package only. Each judge rates every blind output on the
frozen 1-7 rubric and returns strict JSON; the runner parses/validates it into rating rows compatible with the
existing scorer (`judge_b1_6_pilot_outputs`). It reads ONLY the blind judge-visible file — never the hidden
arm/generator metadata — so judging cannot unblind. Judges must differ (model + family) from the generators.

Mirrors the generation adapter pattern (`b1_6_llm_adapter`): OpenAI-compatible local endpoints for real judges,
a deterministic FakeJudgeAdapter for tests. Performs NO real judging and NO external API call in tests. Supports
sequential single-GPU judging (one judge server at a time) + a merge that refuses an incomplete/duplicated grid.

No ratings freeze created here. No unblinding. No GENUTILITY_* label. B1.4b' remains NULL_RETURN_BOTTOM.
Structure, not validated meaning.
"""
from __future__ import annotations
import hashlib
import json
import pathlib
from typing import Callable, Dict, List, Optional, Tuple

import b1_6_llm_adapter as A
import judge_b1_6_pilot_outputs as J

B1_4B_PRIME_STATUS = "NULL_RETURN_BOTTOM"
MOCK_MARK = "MOCK_JUDGING_ONLY_DO_NOT_INTERPRET"

POSITIVE_DIMS = J.POSITIVE_DIMS
PENALTY_DIMS = J.PENALTY_DIMS
ALL_DIMS = (*POSITIVE_DIMS, *PENALTY_DIMS)
SCALE_MIN, SCALE_MAX = J.SCALE_MIN, J.SCALE_MAX

# Only these fields of the blind package are ever shown to a judge (no hidden metadata, no arm/generator).
JUDGE_INPUT_KEYS = ("blinded_output_id", "target_text", "neutral_context", "generation_text")

REFERENCE_JUDGES = [
    {"id": "meta-llama/Llama-3.1-8B-Instruct", "family": "Llama"},
    {"id": "meta-llama/Meta-Llama-3-8B-Instruct", "family": "Llama"},
    {"id": "google/gemma-2-9b-it", "family": "Gemma"},
]


def _sha_obj(o) -> str:
    return hashlib.sha256(json.dumps(o, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# --------------------------------------------------------------------------------------
# No-same-model rule (judge vs generator)
# --------------------------------------------------------------------------------------
def detect_judge_generator_conflicts(judges: List[Dict], generators: List[Dict]) -> List[Dict]:
    gen_ids = {g.get("id") for g in generators}
    gen_fams = {g.get("family") for g in generators}
    out = []
    for j in judges:
        if j.get("id") in gen_ids:
            out.append({"type": "SAME_MODEL", "judge": j.get("id"),
                        "detail": "a judge must not be one of the generators"})
        elif j.get("family") in gen_fams:
            out.append({"type": "SAME_FAMILY", "judge": j.get("id"), "family": j.get("family"),
                        "detail": "judge family matches a generator family; flagged"})
    return out


# --------------------------------------------------------------------------------------
# Judge prompt (rubric) + strict JSON parsing
# --------------------------------------------------------------------------------------
def build_judge_prompt(item: Dict) -> str:
    dims = ", ".join(POSITIVE_DIMS)
    pens = ", ".join(PENALTY_DIMS)
    return (
        "You are a blind evaluator. Rate the interpretation of the target on each dimension using an INTEGER "
        f"from {SCALE_MIN} to {SCALE_MAX} (never 0, never blank). Do NOT guess which method/system/model "
        "produced it; do not mention any system. Reward specific, coherent, useful, non-generic readings; "
        "penalize overclaiming and hallucination.\n"
        f"Target: {item['target_text']}\nContext: {item.get('neutral_context','')}\n"
        f"Interpretation:\n{item['generation_text']}\n\n"
        f"Positive dimensions, {SCALE_MIN}-{SCALE_MAX} ({SCALE_MAX}=best): {dims}\n"
        f"Penalty dimensions, {SCALE_MIN}-{SCALE_MAX} ({SCALE_MIN}=none/best, {SCALE_MAX}=worst; "
        f"use {SCALE_MIN} when absent, NEVER 0): {pens}\n"
        f"Output ONLY a single JSON object containing ALL {len(ALL_DIMS)} keys below, each an integer "
        f"{SCALE_MIN}-{SCALE_MAX} — no prose, no code fence. Begin with '{{' and end with '}}':\n"
        "{" + ", ".join(f'\"{d}\": <{SCALE_MIN}-{SCALE_MAX}>' for d in ALL_DIMS) + "}"
    )


def parse_judge_json(text: str) -> Tuple[Optional[Dict], List[str]]:
    """Parse a judge's strict-JSON rating. Returns (dims|None, reasons). Never guesses/repairs values."""
    reasons: List[str] = []
    s = text.strip()
    i, k = s.find("{"), s.rfind("}")
    if i < 0 or k < 0 or k < i:
        return None, ["no JSON object found"]
    try:
        obj = json.loads(s[i:k + 1])
    except Exception as e:                               # noqa: BLE001
        return None, [f"invalid JSON: {e}"]
    out = {}
    for d in ALL_DIMS:
        if d not in obj:
            reasons.append(f"missing dimension: {d}")
            continue
        try:
            v = int(obj[d])
        except (TypeError, ValueError):
            reasons.append(f"non-integer {d}: {obj[d]!r}")
            continue
        if not (SCALE_MIN <= v <= SCALE_MAX):
            reasons.append(f"{d} out of 1-7 range: {v}")
            continue
        out[d] = v
    if reasons:
        return None, reasons
    return out, []


# --------------------------------------------------------------------------------------
# Fake judge adapter (tests only) — deterministic, no model, no network
# --------------------------------------------------------------------------------------
class FakeJudgeAdapter:
    is_real = False
    backend = "fake"

    def __init__(self, judge_id="FAKE_JUDGE", malformed=False):
        self.judge_id = judge_id
        self.malformed = malformed

    def generate(self, prompt: str, settings=None) -> str:
        if self.malformed:
            return "not json"
        h = int(hashlib.sha256(f"{self.judge_id}|{prompt}".encode()).hexdigest(), 16)
        dims = {d: SCALE_MIN + ((h >> (3 * i)) % SCALE_MAX) for i, d in enumerate(POSITIVE_DIMS)}
        for i, d in enumerate(PENALTY_DIMS):
            dims[d] = 1 + ((h >> (2 * i)) % 3)          # 1..3
        dims = {d: max(SCALE_MIN, min(SCALE_MAX, v)) for d, v in dims.items()}
        return json.dumps(dims)


# --------------------------------------------------------------------------------------
# Run a single judge over the blind package (reads ONLY blind judge-visible file)
# --------------------------------------------------------------------------------------
def _read_blind(judge_visible_file: pathlib.Path) -> List[Dict]:
    rows = [json.loads(ln) for ln in pathlib.Path(judge_visible_file).read_text().splitlines() if ln.strip()]
    ok, reasons = J.check_blindness(rows)               # reuse the harness blindness verifier
    if not ok:
        raise ValueError(f"INVALID_BLINDING: judge-visible package not blind: {reasons[:3]}")
    # judges receive ONLY the whitelisted fields
    return [{k: r[k] for k in JUDGE_INPUT_KEYS if k in r} for r in rows]


def run_single_judge(judge: Dict, judge_visible_file: pathlib.Path,
                     adapter=None, settings=None, limit_outputs: Optional[int] = None,
                     out_dir: pathlib.Path = None, write: bool = False) -> Dict:
    """Run ONE judge over the blind outputs. Returns a partial ratings package (per-output ratings + errors).
    Never reads hidden metadata."""
    items = _read_blind(judge_visible_file)
    items = sorted(items, key=lambda r: r["blinded_output_id"])   # deterministic ordering
    if limit_outputs:
        items = items[:limit_outputs]
    settings = settings or A.GenerationSettings(model_id=judge["id"], max_tokens=512, temperature=0.0,
                                                max_attempts=5)
    ratings: List[Dict] = []
    errors: List[Dict] = []
    def _json_ok(t):                       # retry on unparseable/out-of-range judge JSON (varied seed)
        dims, rs = parse_judge_json(t)
        return dims is not None, rs
    for it in items:
        prompt = build_judge_prompt(it)
        if adapter is None:
            raise ValueError("run_single_judge requires an adapter (FakeJudgeAdapter in tests; real on a host)")
        text, status, rs = A.generate_with_retry(adapter, prompt, settings, validate=True, validator=_json_ok)
        dims, preasons = (None, ["adapter error"]) if text is None else parse_judge_json(text)
        if dims is None:
            errors.append({"blinded_output_id": it["blinded_output_id"], "reasons": (rs or []) + preasons})
            continue
        row = {"blinded_output_id": it["blinded_output_id"], "judge_id": judge["id"], **dims}
        ratings.append(row)
    part = {
        "artifact_type": "b1_6_llm_judge_part",
        "judge_id": judge["id"], "judge_family": judge.get("family"),
        "judge_visible_sha256": J._sha_file(pathlib.Path(judge_visible_file)),
        "n_items": len(items), "n_ratings": len(ratings), "n_errors": len(errors),
        "ratings": ratings, "errors": errors,
        "unblinded": False, "reads_hidden_metadata": False,
        "b1_4b_prime_status": B1_4B_PRIME_STATUS, "mark": MOCK_MARK,
    }
    if write and out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"judge_part_{_safe(judge['id'])}.json").write_text(
            json.dumps(part, ensure_ascii=False, indent=2))
    return part


def _safe(s: str) -> str:
    return s.replace("/", "_").replace(":", "_")


# --------------------------------------------------------------------------------------
# Merge the 3 judge parts + emit scorer-ready ratings
# --------------------------------------------------------------------------------------
def merge_judge_parts(parts: List[Dict], out_dir: pathlib.Path = None, write: bool = False) -> Dict:
    """Merge judge parts. Refuses on duplicate judge ids, judge-visible-hash mismatch, or an incomplete grid
    (any (judge x blinded_output_id) rating missing). Emits scorer-compatible ratings (one row per rating)."""
    reasons: List[str] = []
    if len(parts) < 1:
        return {"label": "B1_6_V2_LLM_JUDGE_PANEL_BLOCKED_RATINGS_FORMAT", "reasons": ["no judge parts"]}
    judge_ids = [p["judge_id"] for p in parts]
    if len(set(judge_ids)) != len(judge_ids):
        reasons.append(f"duplicate judge_id across parts: {judge_ids}")
    jv_hashes = {p.get("judge_visible_sha256") for p in parts}
    if len(jv_hashes) != 1:
        reasons.append(f"judge parts rated different judge-visible packages: {jv_hashes}")
    if any(p.get("n_errors", 0) for p in parts):
        reasons.append("some judge parts have unresolved errors (missing ratings); rerun before merge")
    # completeness grid: every judge must have rated every output id
    all_ids = set()
    for p in parts:
        all_ids |= {r["blinded_output_id"] for r in p["ratings"]}
    for p in parts:
        rated = {r["blinded_output_id"] for r in p["ratings"]}
        missing = all_ids - rated
        if missing:
            reasons.append(f"judge {p['judge_id']} missing {len(missing)} ratings")
    if reasons:
        return {"label": "B1_6_V2_LLM_JUDGE_PANEL_BLOCKED_RATINGS_FORMAT", "reasons": reasons}

    merged_rows: List[Dict] = []
    for p in parts:
        merged_rows.extend(p["ratings"])
    manifest = {
        "artifact_type": "b1_6_llm_judge_panel_manifest",
        "n_judges": len(parts), "judge_ids": judge_ids,
        "n_outputs": len(all_ids), "n_ratings": len(merged_rows),
        "expected_ratings": len(all_ids) * len(parts),
        "judge_visible_sha256": next(iter(jv_hashes)),
        "unblinded": False, "reads_hidden_metadata": False,
        "b1_4b_prime_status": B1_4B_PRIME_STATUS,
        "note": "Ratings for the existing scorer's ratings-freeze gate. No unblinding here. No GENUTILITY_* label.",
    }
    if write and out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "llm_judge_ratings_raw.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in merged_rows) + "\n")
        (out_dir / "ratings_for_freeze.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in merged_rows) + "\n")
        (out_dir / "llm_judge_panel_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return {"label": "B1_6_V2_LLM_JUDGE_PANEL_READY_MOCK_TESTED",
            "manifest": manifest, "ratings": merged_rows}


def load_part(path: pathlib.Path) -> Dict:
    return json.loads(pathlib.Path(path).read_text())
