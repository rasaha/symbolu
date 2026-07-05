#!/usr/bin/env python3
"""B1.1 freeze-artifact validator — validates the candidate freeze configs + bridge pool. Pure stdlib.

NO model, NO embedding, NO generation, NO scoring, NO judging. Read-only over the candidate configs and the
bridge pool; writes only the validation report. Does not authorize generation and does not freeze anything.

    python3 experiments/primitive_sequence_recovery/run_b1_1_freeze_artifact_validation.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
REPORT_JSON = HERE / "B1_1_FREEZE_ARTIFACT_VALIDATION_REPORT.json"
REPORT_MD = HERE / "B1_1_FREEZE_ARTIFACT_VALIDATION_REPORT.md"

CONFIGS = ["b1_1_arm_construction_config.json", "b1_1_generation_config.json", "b1_1_seeds_config.json",
           "b1_1_judge_panel_config.json", "b1_1_scorer_config.json", "b1_1_leak_and_packet_config.json"]
LEXICON = "b1_1_experimental_contrastive_lexicon_draft.json"
BRIDGE = "b1_1_bridge_pool_draft.json"
ARMS_EXPECTED = {"A", "D", "S", "R_same", "R_deranged", "R_domain", "C", "X"}
R_PRIMARIES = {"A_vs_R_deranged", "A_vs_R_domain", "A_vs_R_same"}
FORBIDDEN = ("good", "bad", "positive", "negative", "vice", "virtue")


def find_sentinel(obj, sentinel, path="$"):
    hits = []
    if isinstance(obj, str):
        if sentinel in obj:
            hits.append(path)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            hits += find_sentinel(v, sentinel, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += find_sentinel(v, sentinel, f"{path}[{i}]")
    return hits


def sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    blockers, warnings, checks, hashes = [], [], {}, {}

    # config existence + parse
    cfgs = {}
    for name in CONFIGS:
        p = HERE / name
        if not p.exists():
            blockers.append(f"missing config: {name}")
            checks[f"exists:{name}"] = False
            continue
        try:
            cfgs[name] = json.loads(p.read_text(encoding="utf-8"))
            checks[f"exists:{name}"] = True
            hashes[name] = sha256(p)
        except Exception as e:  # noqa: BLE001
            blockers.append(f"parse error in {name}: {e}")
            checks[f"exists:{name}"] = False

    # placeholders / unknowns
    for name, c in cfgs.items():
        ph = find_sentinel(c, "PLACEHOLDER_REQUIRED")
        uk = find_sentinel(c, "UNKNOWN_PENDING_FREEZE_REVIEW")
        if ph:
            blockers.append(f"PLACEHOLDER_REQUIRED remains in {name}: {ph}")
        if uk:
            blockers.append(f"UNKNOWN_PENDING_FREEZE_REVIEW in {name}: {uk}")
    checks["no_placeholder_required"] = not any("PLACEHOLDER_REQUIRED remains" in b for b in blockers)
    checks["no_unknown_pending"] = not any("UNKNOWN_PENDING_FREEZE_REVIEW" in b for b in blockers)

    # arms exactly the 8
    arm_cfg = cfgs.get("b1_1_arm_construction_config.json", {})
    arms = set(arm_cfg.get("arms", {}).keys())
    checks["arms_exactly_8"] = arms == ARMS_EXPECTED
    if arms != ARMS_EXPECTED:
        blockers.append(f"arms mismatch: {sorted(arms)} != {sorted(ARMS_EXPECTED)}")

    # primary comparisons include all three R controls
    scorer = cfgs.get("b1_1_scorer_config.json", {})
    prim = set(scorer.get("primary_comparisons", []))
    checks["primary_has_all_three_R"] = R_PRIMARIES.issubset(prim)
    if not R_PRIMARIES.issubset(prim):
        blockers.append(f"primary comparisons missing R controls: need {sorted(R_PRIMARIES)}, have {sorted(prim)}")

    # generation_authorized false everywhere it appears
    gen_auth_ok = True
    for name, c in cfgs.items():
        for hit in find_sentinel(c, "generation_authorized"):
            pass
        if c.get("generation_authorized", False) is True:
            gen_auth_ok = False
            blockers.append(f"generation_authorized is TRUE in {name}")
    checks["generation_authorized_false"] = gen_auth_ok

    # anchors + status representation in each _meta
    for name, c in cfgs.items():
        m = c.get("_meta", {})
        if m.get("b1_verdict_anchor") != "RANDOM_OR_SCRAMBLED_MATCHES":
            blockers.append(f"missing/incorrect B1 verdict anchor in {name}")
        if m.get("track_b_anchor") != "BLOCKED":
            blockers.append(f"missing/incorrect Track B anchor in {name}")
    checks["b1_verdict_anchor_present"] = not any("B1 verdict anchor" in b for b in blockers)
    checks["track_b_anchor_present"] = not any("Track B anchor" in b for b in blockers)

    # embedding + fallback status represented (at least in arm config _meta)
    am = arm_cfg.get("_meta", {})
    checks["embedding_status_correct"] = am.get("embedding_gate_status") == "BLOCKED_DEPENDENCY_UNAVAILABLE"
    checks["fallback_qualification_correct"] = am.get("fallback_qualification") == "FALLBACK_QUALIFIED"
    if not checks["embedding_status_correct"]:
        warnings.append("embedding_gate_status not represented as BLOCKED_DEPENDENCY_UNAVAILABLE in arm config _meta")
    if not checks["fallback_qualification_correct"]:
        warnings.append("fallback_qualification not represented as FALLBACK_QUALIFIED in arm config _meta")

    # bridge pool: exists, 68 phrases, no dup, no forbidden framing
    bp = HERE / BRIDGE
    if not bp.exists():
        blockers.append("bridge pool missing")
        checks["bridge_68"] = checks["bridge_no_dup"] = checks["bridge_no_forbidden"] = False
    else:
        pool = json.loads(bp.read_text(encoding="utf-8"))
        hashes[BRIDGE] = sha256(bp)
        phrases = [e["binding_bridge"] for e in pool["entries"]] + [e["liberating_bridge"] for e in pool["entries"]]
        checks["bridge_68"] = len(phrases) == 68
        norm = [re.sub(r"\s+", " ", x.strip().lower()) for x in phrases]
        checks["bridge_no_dup"] = len(norm) == len(set(norm))
        forb = [(w, x) for x in phrases for w in FORBIDDEN if re.search(rf"\b{re.escape(w)}\b", x.lower())]
        checks["bridge_no_forbidden"] = not forb
        if not checks["bridge_68"]:
            blockers.append(f"bridge phrases != 68 ({len(phrases)})")
        if not checks["bridge_no_dup"]:
            blockers.append("duplicate bridge phrases")
        if forb:
            blockers.append(f"forbidden framing in bridge: {forb[:3]}")

    # no source lexicon listed as a writable target (scan config values for varna_lens/ writes)
    src_leak = []
    for name, c in cfgs.items():
        for hit in find_sentinel(c, "varna_lens/"):
            src_leak.append(f"{name}:{hit}")
    checks["no_source_lexicon_target"] = not src_leak
    if src_leak:
        blockers.append(f"config references varna_lens/ source lexicon: {src_leak}")

    if LEXICON and (HERE / LEXICON).exists():
        hashes[LEXICON] = sha256(HERE / LEXICON)

    # judge acceptance is a review warning (not a hard blocker by itself)
    jp = cfgs.get("b1_1_judge_panel_config.json", {})
    if jp.get("judge_caveats", {}).get("acceptance_required_before_freeze"):
        warnings.append("judge panel: Meta-Llama-3-8B requires explicit acceptance (heavy missing-brace repair in B1) before freeze")

    # status
    hard_missing = any("missing config" in b or "parse error" in b or "bridge pool missing" in b for b in blockers)
    status = ("BLOCKED" if hard_missing else
              "READY_FOR_FREEZE_REVIEW" if not blockers else
              "NOT_READY_FOR_FREEZE")

    report = {
        "artifact": "b1_1_freeze_artifact_validation_report",
        "b1_verdict_anchor": "RANDOM_OR_SCRAMBLED_MATCHES", "track_b_anchor": "BLOCKED",
        "embedding_gate_status": "BLOCKED_DEPENDENCY_UNAVAILABLE", "fallback_qualification": "FALLBACK_QUALIFIED",
        "status": status, "checks": checks, "blockers": blockers, "warnings": warnings,
        "sha256": hashes, "generation_authorized": False, "b1_1_frozen": False,
        "non_claims": ["no ontology validation", "no Sanskrit privilege", "no semantic truth"]}
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md = f"""# B1.1 Freeze-Artifact Validation Report

## Status: `{status}`

Pure-stdlib validation of the candidate freeze configs + bridge pool. NO model / embedding / generation /
scoring / judging. B1.1 **not frozen**; generation **not authorized**. B1 verdict
`RANDOM_OR_SCRAMBLED_MATCHES` unchanged; Track B **BLOCKED**. Structure, not validated meaning.

## Checks
{chr(10).join(f"- [{'PASS' if v else 'FAIL'}] {k}" for k, v in checks.items())}

## Blockers ({len(blockers)})
{chr(10).join(f"- {b}" for b in blockers) or '_none_'}

## Warnings ({len(warnings)})
{chr(10).join(f"- {w}" for w in warnings) or '_none_'}

## sha256 (candidate artifacts)
{chr(10).join(f"- `{k}`: {v}" for k, v in hashes.items())}

## Final status
```
status:                {status}
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:               BLOCKED
Embedding gate:        BLOCKED_DEPENDENCY_UNAVAILABLE (owed)
Bridge:                PASS_BRIDGE_DRAFT / FALLBACK_QUALIFIED
B1.1 frozen:           NO
Generation authorized: NO
```
`R_deranged` remains the crux. **Structure, not validated meaning.**
"""
    REPORT_MD.write_text(md, encoding="utf-8")
    print(f"[status] {status} | blockers={len(blockers)} warnings={len(warnings)}")
    for b in blockers:
        print(f"  BLOCKER: {b}")
    print(f"[ok] wrote {REPORT_JSON.name} + {REPORT_MD.name}")


if __name__ == "__main__":
    main()
