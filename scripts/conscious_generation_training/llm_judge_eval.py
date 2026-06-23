#!/usr/bin/env python3
"""llm_judge_eval.py — WEAK LLM-judge evaluation harness for Conscious Generation / Mistral outputs.
Doc: docs/CG_TRAINING_LLM_JUDGE_EVAL.md.

LLM-judge labels are a WEAK SCREENING signal for iteration — NOT human labels and NOT a validation of
Conscious Generation training. Every emitted label is marked `source = llm_judge_weak_label` (or
`llm_judge_ensemble_weak_label` for the multi-judge consensus). This harness:
  * does NOT import or modify the C×R×S wrapper, Kosha/Guna/Vritti/Bhava, or any runtime path;
  * does NOT override the Phase-3 audit (it can only COMPARE against it);
  * is CPU-safe in `--mock` mode (deterministic, no model calls) for tests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import llm_judge_rubric as R                                  # noqa: E402
import llm_judge_agreement as AG                              # noqa: E402

WEAK_SOURCE = "llm_judge_weak_label"
ENSEMBLE_SOURCE = "llm_judge_ensemble_weak_label"
HUMAN_SOURCE_FORBIDDEN = "human_label"                        # NEVER emitted by this harness

DECISIONS = ("CG_LLM_JUDGE_EVAL_READY", "CG_LLM_JUDGE_MOCK_ONLY", "CG_LLM_JUDGE_WEAK_LABELS_GENERATED",
             "CG_LLM_JUDGE_AGREEMENT_LOW", "CG_LLM_JUDGE_AGREEMENT_ACCEPTABLE",
             "CG_LLM_JUDGE_AUDIT_DISAGREEMENT_HIGH", "CG_LLM_JUDGE_ENV_UNAVAILABLE",
             "CG_LLM_JUDGE_INVALID_JSON_RATE_HIGH")

INVALID_JSON_MAX = 0.10
AGREEMENT_LOW = 0.60
AGREEMENT_OK = 0.70
AUDIT_DISAGREEMENT_MAX = 0.40                                 # >40% rewrite_needed disagreement = high

# audit findings -> the binary notions used for the audit comparison overlap
_FRAME_FAIL = frozenset({"primary_frame_missing", "secondary_promoted_to_primary"})
_REJECTED_LEAK = frozenset({"rejected_domain_promoted", "rejected_domain_mentioned_as_refutation"})
_SECONDARY_OVERPROMO = frozenset({"secondary_promoted_to_primary"})


# ==================================================================================================
# Providers
# ==================================================================================================
class JudgeProvider:
    """Provider interface. Real providers call a local/remote model; mock is deterministic + CPU-safe."""
    def judge(self, prompt: str) -> str:                      # pragma: no cover - interface
        raise NotImplementedError


class MockProvider(JudgeProvider):
    """Deterministic, CPU-only fake judge. Derives labels from transparent surface cues in the prompt and
    adds a small judge-specific perturbation (so multi-judge agreement is non-degenerate). NOT a model."""
    def __init__(self, judge_id: str = "mock"):
        self.judge_id = judge_id

    def judge(self, prompt: str) -> str:
        return json.dumps(_mock_labels(prompt, self.judge_id))


class OllamaProvider(JudgeProvider):                          # pragma: no cover - needs a local server
    def __init__(self, model: str, host: str = "http://localhost:11434"):
        self.model, self.host = model, host

    def judge(self, prompt: str) -> str:
        import urllib.request
        body = json.dumps({"model": self.model, "prompt": prompt, "stream": False,
                           "format": "json",                # force valid JSON (cuts invalid-JSON rate)
                           "options": {"temperature": 0.0}}).encode()
        req = urllib.request.Request(self.host.rstrip("/") + "/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode()).get("response", "")


class OpenAICompatibleProvider(JudgeProvider):                # pragma: no cover - needs a server + key
    def __init__(self, model: str, base_url: str, api_key: str = "not-needed"):
        self.model, self.base_url, self.api_key = model, base_url.rstrip("/"), api_key

    def judge(self, prompt: str) -> str:
        import urllib.request
        body = json.dumps({"model": self.model, "temperature": 0.0,
                           "response_format": {"type": "json_object"},   # force valid JSON
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request(self.base_url + "/chat/completions", data=body,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            out = json.loads(resp.read().decode())
            return out["choices"][0]["message"]["content"]


def make_provider(judge_id: str, *, mock: bool, provider: Optional[str], model: Optional[str],
                  host: Optional[str]) -> JudgeProvider:
    if mock:
        return MockProvider(judge_id)
    if provider == "ollama":
        return OllamaProvider(model or judge_id, host or "http://localhost:11434")
    if provider in ("openai", "openai-compatible"):
        return OpenAICompatibleProvider(model or judge_id, host or "http://localhost:8000/v1")
    raise RuntimeError(f"no provider configured for judge '{judge_id}' "
                       f"(use --mock, or --provider ollama|openai-compatible)")


def _mock_labels(prompt: str, judge_id: str) -> Dict:
    """Transparent surface heuristics over the prompt's Answer/Rejected/Must-include sections, with a small
    deterministic judge-specific flip. Deterministic given (prompt, judge_id)."""
    def _section(name, nxt):
        try:
            seg = prompt.split(name, 1)[1]
            for stop in nxt:
                seg = seg.split(stop, 1)[0]
            return seg.strip()
        except IndexError:
            return ""
    answer = _section("Answer to evaluate:\n", ["\nReturn STRICT JSON"])
    rejected = _section("Rejected frames:\n", ["\n\n"])
    must = _section("Must-include concepts:\n", ["\n\n"])
    a_low = answer.lower()
    wc = len(answer.split())
    rej_tokens = [t.strip().lower() for t in rejected.replace("/", ",").split(",")
                  if t.strip() and t.strip() != "(none provided)"]
    rej_tokens = [t for t in rej_tokens for t in [t.split()[0]] if len(t) > 2]
    leak = any(t in a_low for t in rej_tokens)
    must_tokens = [t.strip().lower() for t in must.split(",")
                   if t.strip() and t.strip() != "(none provided)"]
    recall = 1.0 if not must_tokens else round(sum(1 for t in must_tokens if t in a_low) / len(must_tokens), 4)
    frame_ok = (not leak) and wc >= 6
    generic = wc < 6 or recall < 0.34
    clarity = 4 if wc >= 20 else (3 if wc >= 8 else 2)
    rewrite = leak or (recall < 0.5) or (not frame_ok) or generic
    labels = {"primary_frame_correct": frame_ok, "rejected_domain_leak": leak,
              "secondary_overpromotion": False, "factuality_preserved": not generic,
              "must_include_recall_score": recall, "clarity_usefulness_score": clarity,
              "generic_low_signal": generic, "overconfident_or_overstated": False,
              "answer_acceptable": not rewrite, "rewrite_needed": rewrite,
              "short_reason": "mock surface heuristic (NOT a real model judgment)"}
    # small judge-specific perturbation on borderline fields -> non-degenerate agreement
    seed = int(hashlib.md5((judge_id + "|" + prompt).encode()).hexdigest(), 16) % (2 ** 32)
    rng = random.Random(seed)
    if 6 <= wc <= 12 and rng.random() < 0.30:
        labels["clarity_usefulness_score"] = min(5, max(1, labels["clarity_usefulness_score"] + rng.choice([-1, 1])))
    if 0.34 <= recall <= 0.66 and rng.random() < 0.25:
        labels["generic_low_signal"] = not labels["generic_low_signal"]
    return labels


# ==================================================================================================
# Input loading / normalization
# ==================================================================================================
def _audit_from_row(row: Dict) -> Optional[Dict]:
    if not any(k in row for k in ("expected_needs_rewrite", "expected_passed", "expected_findings")):
        return None
    findings = set(row.get("expected_findings") or [])
    acceptable = bool(row.get("expected_passed")) if "expected_passed" in row \
        else (not bool(row.get("expected_needs_rewrite")))
    return {"primary_frame_correct": not bool(findings & _FRAME_FAIL),
            "rejected_domain_leak": bool(findings & _REJECTED_LEAK),
            "secondary_overpromotion": bool(findings & _SECONDARY_OVERPROMO),
            "answer_acceptable": acceptable,
            "rewrite_needed": bool(row.get("expected_needs_rewrite")) if "expected_needs_rewrite" in row
            else (not acceptable)}


def normalize_record(row: Dict, *, allow_missing_optional: bool, idx: int) -> Dict:
    rid = row.get("id") or row.get("item_id") or f"ex_{idx:04d}"
    query = row.get("query") or row.get("prompt")
    answer = row.get("answer") or row.get("response")
    fix = row.get("csr_trace_fixture") or {}
    primary = row.get("primary_domain")
    if primary is None:
        pds = fix.get("primary_domains") or row.get("primary_domains") or []
        primary = pds[0] if pds else None
    if not query or not answer or not primary:
        raise ValueError(f"record {rid}: missing required field (need query, answer, primary_domain)")
    secondary = row.get("secondary_domains", fix.get("secondary_domains"))
    rejected = row.get("rejected_domains", fix.get("rejected_domains"))
    must = row.get("must_include")
    if not allow_missing_optional:
        for name, val in (("secondary_domains", secondary), ("rejected_domains", rejected),
                          ("must_include", must)):
            if val is None:
                raise ValueError(f"record {rid}: missing optional field '{name}' "
                                 f"(pass --allow-missing-optional to default it to [])")
    return {"id": rid, "arm": row.get("arm"), "query": query, "answer": answer,
            "primary_domain": primary, "secondary_domains": list(secondary or []),
            "rejected_domains": list(rejected or []), "must_include": list(must or []),
            "expected_frame": row.get("expected_frame"),
            "metadata": row.get("metadata"), "_audit": _audit_from_row(row)}


def _flatten_four_arm(per_example: List[Dict]) -> List[Dict]:
    """Expand a four-arm per_example list into one answer record per arm. Requires answer TEXT per arm
    (scores[arm]['answer'] or answers[arm]); arm identity is retained internally but never shown to judges."""
    out = []
    for pe in per_example:
        answers = pe.get("answers") or {a: sc.get("answer") for a, sc in (pe.get("scores") or {}).items()}
        if not any(answers.values()):
            raise ValueError(f"four-arm row {pe.get('id')} has no answer text per arm "
                             "(cannot judge; re-run the eval with answer caching)")
        for arm, ans in answers.items():
            if not ans:
                continue
            out.append({"id": f"{pe.get('id')}::{arm}", "arm": arm, "query": pe.get("query"),
                        "answer": ans, "primary_domain": pe.get("primary_domain"),
                        "secondary_domains": pe.get("secondary_domains"),
                        "rejected_domains": pe.get("rejected_domains"),
                        "must_include": pe.get("must_include")})
    return out


def load_records(path: Path, *, allow_missing_optional: bool) -> List[Dict]:
    text = path.read_text()
    if path.suffix == ".jsonl":
        rows = [json.loads(l) for l in text.splitlines() if l.strip()]
    else:
        blob = json.loads(text)
        if isinstance(blob, list):
            rows = blob
        elif isinstance(blob, dict) and "per_example" in blob:
            rows = _flatten_four_arm(blob["per_example"])
        elif isinstance(blob, dict):
            rows = blob.get("records") or blob.get("rows") or blob.get("queries") or []
        else:
            rows = []
    return [normalize_record(r, allow_missing_optional=allow_missing_optional, idx=i)
            for i, r in enumerate(rows)]


# ==================================================================================================
# Judging + decision
# ==================================================================================================
def judge_records(records: List[Dict], judges: List[str], providers: Dict[str, JudgeProvider],
                  *, allow_missing_optional: bool) -> Tuple[List[Dict], Dict[str, Dict]]:
    """Returns (label_rows, labels_by_judge[judge][id]=labels for VALID rows only)."""
    label_rows: List[Dict] = []
    labels_by_judge: Dict[str, Dict] = {j: {} for j in judges}
    for j in judges:
        prov = providers[j]
        for rec in records:
            prompt = R.build_judge_prompt(rec, allow_missing_optional=allow_missing_optional)
            raw = prov.judge(prompt)
            labels, valid = R.parse_judge_json(raw)
            row = {"id": rec["id"], "judge": j, "source": WEAK_SOURCE,
                   "labels": labels if valid else {}, "raw_response": raw[:2000],
                   "valid_json": valid, "rubric_version": R.RUBRIC_VERSION}
            if rec.get("arm") is not None:
                row["arm"] = rec["arm"]                       # for analysis only; NOT in the judge prompt
            label_rows.append(row)
            if valid:
                labels_by_judge[j][rec["id"]] = labels
    return label_rows, labels_by_judge


def ensemble_rows(labels_by_judge: Dict[str, Dict]) -> List[Dict]:
    """Majority-vote binary + mean numeric consensus across judges (>=2). source=ENSEMBLE_SOURCE."""
    judges = sorted(labels_by_judge)
    if len(judges) < 2:
        return []
    ids = set(labels_by_judge[judges[0]])
    for j in judges[1:]:
        ids &= set(labels_by_judge[j])
    rows = []
    for i in sorted(ids):
        cons = {}
        for f in R.BINARY_FIELDS:
            votes = sum(1 for j in judges if labels_by_judge[j][i].get(f))
            cons[f] = votes > len(judges) / 2
        for f in R.NUMERIC_FIELDS:
            vals = [labels_by_judge[j][i].get(f) for j in judges]
            cons[f] = round(sum(vals) / len(vals), 4)
        rows.append({"id": i, "judge": "ENSEMBLE", "source": ENSEMBLE_SOURCE,
                     "labels": cons, "raw_response": "", "valid_json": True,
                     "rubric_version": R.RUBRIC_VERSION})
    return rows


def decide(*, mock_only: bool, invalid_json_rate: float, n_judges: int,
           agreement_avg: Optional[float], audit_agreement: Optional[float]) -> Tuple[str, Dict]:
    notes = {"invalid_json_rate": round(invalid_json_rate, 4), "n_judges": n_judges,
             "agreement_avg": agreement_avg, "audit_agreement": audit_agreement}
    if mock_only:
        return "CG_LLM_JUDGE_MOCK_ONLY", notes
    if invalid_json_rate > INVALID_JSON_MAX:
        return "CG_LLM_JUDGE_INVALID_JSON_RATE_HIGH", notes
    if n_judges >= 2 and agreement_avg is not None:
        if agreement_avg < AGREEMENT_LOW:
            return "CG_LLM_JUDGE_AGREEMENT_LOW", notes
        if agreement_avg >= AGREEMENT_OK:
            return "CG_LLM_JUDGE_AGREEMENT_ACCEPTABLE", notes
    return "CG_LLM_JUDGE_WEAK_LABELS_GENERATED", notes


def assert_no_human_labels(label_rows: List[Dict]) -> None:
    for row in label_rows:
        if row.get("source") == HUMAN_SOURCE_FORBIDDEN:
            raise AssertionError(f"row {row.get('id')} marked '{HUMAN_SOURCE_FORBIDDEN}' — forbidden")
        if row.get("source") not in (WEAK_SOURCE, ENSEMBLE_SOURCE):
            raise AssertionError(f"row {row.get('id')} has non-weak source '{row.get('source')}'")


# ==================================================================================================
# Orchestration + reports
# ==================================================================================================
def run(records: List[Dict], judges: List[str], providers: Dict[str, JudgeProvider], *,
        mock_only: bool, allow_missing_optional: bool) -> Dict:
    label_rows, labels_by_judge = judge_records(records, judges, providers,
                                                allow_missing_optional=allow_missing_optional)
    ens = ensemble_rows(labels_by_judge)
    all_rows = label_rows + ens
    assert_no_human_labels(all_rows)
    n = len(label_rows)
    invalid_rate = (sum(1 for r in label_rows if not r["valid_json"]) / n) if n else 0.0
    agreement = AG.agreement_report(labels_by_judge) if len(judges) >= 2 else \
        {"n_judges": len(judges), "computable": False, "note": "single-judge run; agreement N/A"}
    agreement_avg = agreement.get("avg_percent_agreement") if agreement.get("computable") else None
    records_by_id = {r["id"]: r for r in records}
    audit = AG.audit_comparison(records_by_id, labels_by_judge[judges[0]]) if judges else None
    audit_agreement = audit.get("agreement_with_audit") if audit else None
    decision, notes = decide(mock_only=mock_only, invalid_json_rate=invalid_rate, n_judges=len(judges),
                             agreement_avg=agreement_avg, audit_agreement=audit_agreement)
    flags = []
    if audit and audit.get("n") and audit["audit_disagreement_count"] / audit["n"] > AUDIT_DISAGREEMENT_MAX:
        flags.append("CG_LLM_JUDGE_AUDIT_DISAGREEMENT_HIGH")
    return {"n_records": len(records), "judges": judges, "mock_only": mock_only,
            "invalid_json_rate": round(invalid_rate, 4), "decision": decision, "decision_notes": notes,
            "flags": flags, "agreement": agreement, "audit_comparison": audit,
            "ensemble_used": bool(ens), "decision_labels": list(DECISIONS),
            "label_rows": all_rows}


def to_markdown(rep: Dict) -> str:
    L = ["# Conscious Generation — weak LLM-judge evaluation", "",
         f"- records: **{rep['n_records']}**  ·  judges: `{rep['judges']}`  ·  mock_only: "
         f"**{rep['mock_only']}**",
         f"- **DECISION: `{rep['decision']}`**  ·  invalid_json_rate: **{rep['invalid_json_rate']}**",
         f"- flags: `{rep['flags']}`", "",
         "> LLM-judge labels are WEAK screening labels (`llm_judge_weak_label`), NOT human labels, and do",
         "> not validate Conscious Generation training. The Phase-3 audit is never overridden.", ""]
    ag = rep.get("agreement") or {}
    if ag.get("computable"):
        L += ["## Inter-judge agreement",
              f"- avg percent agreement: **{ag.get('avg_percent_agreement')}**  ·  common items: "
              f"{ag.get('n_common_items')}", "", "| field | %agree | Cohen κ |", "|---|---|---|"]
        for f, v in ag["binary"].items():
            L.append(f"| {f} | {v['percent_agreement']} | {v.get('cohen_kappa_firstpair')} |")
        L += [""]
        for f, v in ag["numeric"].items():
            L.append(f"- {f}: MAD `{v['mean_abs_diff_firstpair']}` · Pearson `{v['pearson_firstpair']}`")
        L += [""]
    else:
        L += [f"## Inter-judge agreement\n- {ag.get('note', 'N/A')}", ""]
    au = rep.get("audit_comparison")
    if au:
        L += ["## vs Phase-3 audit (comparison only — audit is authoritative)",
              f"- agreement_with_audit: **{au['agreement_with_audit']}** (n={au['n']})",
              f"- judge more lenient: {au['llm_judge_more_lenient_count']} · "
              f"more strict: {au['llm_judge_more_strict_count']} · "
              f"disagreements: {au['audit_disagreement_count']}", ""]
    L += ["---", "*LLM-judge evaluation is an assisted weak-evaluation layer for screening and iteration. "
          "It is not human evaluation and cannot by itself validate Conscious Generation training. Strong "
          "validation requires human labels or at least a human-calibrated subset.*"]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Weak LLM-judge evaluation for Conscious Generation outputs.")
    ap.add_argument("--input", required=True, help="JSONL/JSON answer records or four-arm eval JSON")
    ap.add_argument("--out-dir", default="runs/cg_training/llm_judge_eval")
    ap.add_argument("--judges", default="mock", help="comma list, e.g. llama,qwen (or mock)")
    ap.add_argument("--mock", action="store_true", help="CPU-safe deterministic judge, no model calls")
    ap.add_argument("--provider", choices=("ollama", "openai", "openai-compatible"), default=None)
    ap.add_argument("--model", default=None, help="model name for the provider (e.g. llama3.1)")
    ap.add_argument("--host", default=None, help="provider host/base url")
    ap.add_argument("--allow-missing-optional", action="store_true")
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    judges = [j.strip() for j in args.judges.split(",") if j.strip()]
    mock_only = args.mock or judges == ["mock"]

    try:
        records = load_records(Path(args.input), allow_missing_optional=args.allow_missing_optional)
    except (ValueError, KeyError) as e:
        print(f"INPUT ERROR: {e}")
        return 2

    try:
        providers = {j: make_provider(j, mock=mock_only, provider=args.provider, model=args.model,
                                      host=args.host) for j in judges}
    except RuntimeError as e:
        rep = {"decision": "CG_LLM_JUDGE_ENV_UNAVAILABLE", "note": str(e),
               "decision_labels": list(DECISIONS)}
        (out_dir / "llm_judge_eval.json").write_text(json.dumps(rep, indent=2))
        (out_dir / "llm_judge_eval.md").write_text(
            f"# Weak LLM-judge eval — ENV UNAVAILABLE\n\n- {e}\n")
        print(f"DECISION: CG_LLM_JUDGE_ENV_UNAVAILABLE ({e})")
        return 0

    try:
        rep = run(records, judges, providers, mock_only=mock_only,
                  allow_missing_optional=args.allow_missing_optional)
    except Exception as e:                                    # real provider call failed -> env unavailable
        if mock_only:
            raise
        rep = {"decision": "CG_LLM_JUDGE_ENV_UNAVAILABLE", "note": f"judge call failed: {e}",
               "decision_labels": list(DECISIONS)}
        (out_dir / "llm_judge_eval.json").write_text(json.dumps(rep, indent=2))
        (out_dir / "llm_judge_eval.md").write_text(f"# Weak LLM-judge eval — ENV UNAVAILABLE\n\n- {e}\n")
        print(f"DECISION: CG_LLM_JUDGE_ENV_UNAVAILABLE ({e})")
        return 0

    label_rows = rep.pop("label_rows")
    with open(out_dir / "llm_judge_labels.jsonl", "w", encoding="utf-8") as fh:
        for row in label_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out_dir / "llm_judge_eval.json").write_text(json.dumps(rep, indent=2))
    (out_dir / "llm_judge_eval.md").write_text(to_markdown(rep))
    print(f"n={rep['n_records']} judges={judges} DECISION: {rep['decision']} "
          f"(invalid_json_rate={rep['invalid_json_rate']})")
    print(f"wrote {out_dir}/llm_judge_labels.jsonl + llm_judge_eval.json + .md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
