#!/usr/bin/env python3
"""derive_weak_labels.py — WEAK heuristic Guna/Vritti labels from prompt+response (+ optional ground truth).
Pre-reg: docs/CG_GUNA_VRITTI_LABEL_SOURCE_PREREG.md §5. CPU-only, deterministic, torch-free.

WEAK by design: labels are derived from TRANSPARENT SURFACE CUES of the text (the same cues the surface
baseline measures), NEVER from hidden states. Therefore a probe trained on these labels is expected to be
SURFACE_CONFOUNDED and CANNOT support a `LEARNS_SIGNAL` claim — these labels are for PLUMBING and a weak
upper bound only (-> CG_GUNA_VRITTI_SYNTHETIC_ONLY / LABELS_USABLE_WEAK_ONLY). Guna dims 4-6 stay null
(underdefined in the source docs). Bhava is NOT labelled.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))
from conscious_generation_training.surface_baseline import surface_features   # noqa: E402

_RECALL = ("earlier", "you mentioned", "you said", "previously", "as i said", "before,", "last time",
           "you asked", "we discussed")
_HEDGE_TAMAS = 0.03           # hedge density above this -> tamas
_MIN_WORDS = 8                # below this -> nidra (non-answer) / tamas

# Phase-3 audit findings used as a LESS-surface label source (the audit is a deterministic frame/factuality
# judgment over the trace, not a pure word-count cue). Still weak; cannot validate a LEARNS_SIGNAL alone.
_AUDIT_FACTUALITY = ("factuality_suspected",)          # audit flagged a factual problem -> viparyaya
_AUDIT_GENERIC = ("answer_too_generic",)               # audit judged it generic/low-signal -> tamas
_AUDIT_FRAME_OK = ("frame_compliant",)                 # audit passed the frame -> pramana / sattva


def _contains_false_claim(response: str, false_claims) -> bool:
    r = response.lower()
    return any(fc and fc.lower() in r for fc in (false_claims or []))


def derive_vritti(prompt: str, response: str, *, false_claims: Optional[List[str]] = None,
                  ground_truth_available: bool = False) -> str:
    """nidra > viparyaya(GT) > vikalpa > smriti > pramana. viparyaya only when ground truth is available."""
    f = surface_features(prompt, response)
    wc = len((response or "").split())
    if wc < _MIN_WORDS or f["refusal_density"] > 0:
        return "nidra"                                       # empty / evasive / refusal
    if ground_truth_available and _contains_false_claim(response, false_claims):
        return "viparyaya"                                   # contradicts ground truth
    if f["speculation_density"] > 0:
        return "vikalpa"                                     # speculative / hypothetical
    if any(m in (" " + (response or "").lower() + " ") for m in _RECALL):
        return "smriti"                                      # recalls prior context
    return "pramana"                                         # default: grounded assertion


def derive_guna(prompt: str, response: str) -> List[Optional[int]]:
    """[sattva, rajas, tamas, null, null, null] — multi-label 0/1; dims 4-6 underdefined -> null."""
    f = surface_features(prompt, response)
    wc = len((response or "").split())
    tamas = int(f["hedge_density"] >= _HEDGE_TAMAS or f["refusal_density"] > 0 or wc < _MIN_WORDS)
    rajas = int(f["imperative_density"] > 0 or f["list_markers"] >= 2)
    sattva = int(tamas == 0 and wc >= _MIN_WORDS and f["sentence_count"] >= 1)
    return [sattva, rajas, tamas, None, None, None]


def _audit_findings(row: dict):
    """Return (findings_set, needs_rewrite, has_audit). Reads Phase-3 audit fields (top-level or nested
    'audit'). NEVER reads hidden states."""
    src = row.get("audit") if isinstance(row.get("audit"), dict) else row
    findings = src.get("expected_findings", src.get("findings"))
    nr = src.get("expected_needs_rewrite", src.get("needs_rewrite"))
    has = findings is not None or nr is not None
    return set(findings or []), nr, has


def derive_vritti_audit(prompt: str, response: str, findings, needs_rewrite,
                        false_claims: Optional[List[str]] = None) -> str:
    """Vritti using audit findings as the (less-surface) factuality signal. The audit's own factuality
    judgment supplies viparyaya (no separate ground_truth flag needed); the remaining classes
    (nidra/vikalpa/smriti/pramana) fall back to surface cues the audit does not distinguish."""
    f = surface_features(prompt, response)
    wc = len((response or "").split())
    if wc < _MIN_WORDS or f["refusal_density"] > 0:
        return "nidra"                                       # empty / evasive / refusal
    if any(x in findings for x in _AUDIT_FACTUALITY) or _contains_false_claim(response, false_claims):
        return "viparyaya"                                   # audit flagged a factual problem
    if f["speculation_density"] > 0:
        return "vikalpa"
    if any(m in (" " + (response or "").lower() + " ") for m in _RECALL):
        return "smriti"
    return "pramana"


def derive_guna_audit(prompt: str, response: str, findings, needs_rewrite) -> List[Optional[int]]:
    """Guna using audit findings: tamas absorbs the audit's 'answer_too_generic'; sattva requires a
    frame-compliant, non-rewrite, non-tamas answer. rajas stays surface (audit doesn't measure it).
    Dims 4-6 underdefined -> null."""
    f = surface_features(prompt, response)
    wc = len((response or "").split())
    tamas = int(any(x in findings for x in _AUDIT_GENERIC)
                or f["hedge_density"] >= _HEDGE_TAMAS or f["refusal_density"] > 0 or wc < _MIN_WORDS)
    rajas = int(f["imperative_density"] > 0 or f["list_markers"] >= 2)
    frame_ok = any(x in findings for x in _AUDIT_FRAME_OK) and not needs_rewrite
    sattva = int(tamas == 0 and wc >= _MIN_WORDS and (frame_ok or f["sentence_count"] >= 1))
    return [sattva, rajas, tamas, None, None, None]


def derive_row(row: dict) -> dict:
    """Add weak labels + label_meta to a row. Accepts {prompt|query, response|answer, [false_claims],
    [expected_findings/expected_needs_rewrite|audit]}. If Phase-3 audit fields are present, labels are
    AUDIT-DERIVED (source='audit_derived', less surface-confounded for factuality); otherwise WEAK
    surface heuristic (source='weak_heuristic'). Never reads hidden states. Guna dims 4-6 stay null."""
    prompt = row.get("prompt") or row.get("query") or ""
    response = row.get("response") or row.get("answer") or ""
    findings, needs_rewrite, has_audit = _audit_findings(row)
    out = dict(row)
    out["prompt"], out["response"] = prompt, response        # normalize for the surface baseline
    if has_audit:
        vritti = derive_vritti_audit(prompt, response, findings, needs_rewrite,
                                     false_claims=row.get("false_claims"))
        guna = derive_guna_audit(prompt, response, findings, needs_rewrite)
        out["labels"] = {"vritti": vritti, "guna": guna}
        out["label_meta"] = {
            "source": "audit_derived", "guna_labelled_dims": ["sattva", "rajas", "tamas"],
            "audit_findings_used": sorted(findings & set(_AUDIT_FACTUALITY + _AUDIT_GENERIC + _AUDIT_FRAME_OK)),
            "needs_rewrite": needs_rewrite,
            "derived_from": "prompt+response+Phase3_audit_findings (NEVER hidden states)",
            "WARNING": "weak/audit-derived labels — less surface-confounded for factuality, but still "
                       "cannot validate a LEARNS_SIGNAL claim alone (see label-source pre-reg)"}
        return out
    gt_available = bool(row.get("ground_truth_available") or row.get("false_claims") is not None)
    vritti = derive_vritti(prompt, response, false_claims=row.get("false_claims"),
                           ground_truth_available=gt_available)
    guna = derive_guna(prompt, response)
    out["labels"] = {"vritti": vritti, "guna": guna}
    out["label_meta"] = {"source": "weak_heuristic", "guna_labelled_dims": ["sattva", "rajas", "tamas"],
                         "ground_truth_available": gt_available,
                         "derived_from": "prompt+response+ground_truth (NEVER hidden states)",
                         "WARNING": "weak/surface-derivable labels — plumbing + weak upper bound ONLY; "
                                    "cannot validate a LEARNS_SIGNAL claim (see label-source pre-reg)"}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Derive WEAK/audit Guna/Vritti labels + surface-baseline "
                                            "report (plumbing only, not validation).")
    ap.add_argument("--in", dest="inp", required=True,
                    help="JSONL with prompt/response (or query/answer + audit) rows")
    ap.add_argument("--out", required=True, help="JSONL with weak/audit labels added")
    ap.add_argument("--no-surface-baseline", action="store_true",
                    help="skip the surface-confounding guardrail report")
    args = ap.parse_args(argv)
    rows = [json.loads(l) for l in Path(args.inp).read_text().splitlines() if l.strip()]
    labelled = [derive_row(r) for r in rows]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for r in labelled:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    vd = Counter(r["labels"]["vritti"] for r in labelled)
    sources = Counter(r["label_meta"]["source"] for r in labelled)
    print(f"derived labels for {len(labelled)} rows -> {args.out}")
    print(f"  sources: {dict(sources)}   (NOT validation — see label-source pre-reg)")
    print(f"  vritti dist: {dict(vd)}")
    if not args.no_surface_baseline:
        from conscious_generation_training.surface_baseline import surface_baseline
        rep = surface_baseline(labelled)
        conf = rep["surface_confounded_labels"]
        print(f"  surface baseline (n={rep['n']}, threshold={rep['threshold']}):")
        print(f"    SURFACE_CONFOUNDED labels: {conf or '(none ≥ threshold)'}")
        if conf:
            print("    -> LABELS_SURFACE_CONFOUNDED: a hidden-state probe on these CANNOT claim "
                  "non-trivial signal (must beat surface by ≥0.05).")
        else:
            print("    -> no label crossed the surface threshold here; still NOT a LEARNS_SIGNAL claim "
                  "(needs a real hidden-state probe that beats surface).")
    print("  reminder: weak/audit labels are a weak upper bound -> probe capped at SYNTHETIC_ONLY/WEAK_ONLY.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
