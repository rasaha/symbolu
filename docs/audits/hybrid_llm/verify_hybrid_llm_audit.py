#!/usr/bin/env python3
"""Audit-integrity verifier for the Hybrid LLM vNext architecture audit.

Scope (deliberately narrow): this script validates the AUDIT ARTIFACTS themselves --
JSON well-formedness, controlled vocabularies, primary-source coverage, decision-matrix
arithmetic reproducibility, doc-link resolution, and the two integrity invariants
(no quadratic path recorded as linear; no full-prefix replay recorded as constant-time
decode). It does NOT test model performance and does NOT search product source code for
strings -- that anti-pattern is exactly what the internal evidence ledger flags as a
"documentation test". Run: python docs/audits/hybrid_llm/verify_hybrid_llm_audit.py
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ART = HERE / "artifacts"
FAILS: list[str] = []
CHECKS = 0


def check(cond: bool, msg: str) -> None:
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILS.append(msg)


def load(p: Path):
    check(p.exists(), f"missing artifact: {p.name}")
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:  # pragma: no cover - failure path
        FAILS.append(f"invalid JSON in {p.name}: {e}")
        return None


# ---- 1. All JSON artifacts validate ----
artifacts = {
    "inventory": ART / "hybrid_llm_implementation_inventory.json",
    "evidence": ART / "hybrid_llm_internal_evidence_ledger.json",
    "matrix": ART / "hybrid_llm_external_architecture_matrix.json",
    "sources": ART / "hybrid_llm_primary_source_registry.json",
    "decision": ART / "hybrid_llm_decision_matrix.json",
    "disposition": ART / "hybrid_llm_component_disposition.json",
    "thresholds": ART / "hybrid_llm_acceptance_thresholds.json",
}
data = {k: load(v) for k, v in artifacts.items()}

# ---- 2. Evidence tiers use the allowed vocabulary ----
if data["evidence"]:
    vocab = set(data["evidence"]["tier_vocabulary"])
    for c in data["evidence"]["claims"]:
        # a claim tier may combine allowed tokens with '+' or '/'
        toks = re.split(r"[+/]", c["tier"])
        for t in toks:
            t = t.strip()
            # allow RESOURCE_BLOCKED as an explicit environment tier
            check(
                t in vocab or t == "RESOURCE_BLOCKED",
                f"evidence claim {c['id']} uses non-vocabulary tier '{t}'",
            )

# ---- 3. Disposition vocabulary ----
if data["disposition"]:
    dvocab = set(data["disposition"]["disposition_vocabulary"])
    for comp in data["disposition"]["components"]:
        toks = [x.strip() for x in re.split(r"[+/]", comp["disposition"])]
        for t in toks:
            base = t.split(" (")[0].strip()  # strip parentheticals like "(if slots retained)"
            check(
                base in dvocab,
                f"component '{comp['component']}' uses non-vocabulary disposition '{base}'",
            )

# ---- 4. Every external architecture cites a primary source that exists ----
if data["matrix"] and data["sources"]:
    src_ids = {s["id"] for s in data["sources"]["sources"]}
    for a in data["matrix"]["architectures"]:
        check("source" in a and a["source"] in src_ids,
              f"external architecture '{a.get('name')}' missing/unknown primary source ref")
    # every source records a publication date
    for s in data["sources"]["sources"]:
        check(bool(s.get("publication_date")), f"source {s['id']} missing publication_date")
        check(bool(s.get("primary_url")), f"source {s['id']} missing primary_url")

# ---- 5. Integrity invariant: no quadratic path recorded as linear ----
# The 'quadratic reader' MUST be flagged materializes_NxN true somewhere.
if data["inventory"]:
    quad = [c for c in data["inventory"]["components"] if c["name"] == "BindingCacheQuadQuery"]
    check(len(quad) == 1 and quad[0].get("materializes_NxN") is True,
          "integrity: BindingCacheQuadQuery must be recorded as materializes_NxN=true (quadratic)")
    # production LocalWindowAttention must also be flagged
    lwa = [c for c in data["inventory"]["components"] if c["name"].startswith("LocalWindowAttention (production")]
    check(any(c.get("materializes_NxN") is True for c in lwa),
          "integrity: production LocalWindowAttention must be recorded as materializes_NxN=true")

# ---- 6. Integrity invariant: no full-prefix replay recorded as constant-time decode ----
if data["inventory"]:
    hpt = [c for c in data["inventory"]["components"] if c["name"].startswith("HybridAttentionLayer")]
    check(len(hpt) == 1 and "FULL-PREFIX REPLAY" in hpt[0].get("decode", "").upper(),
          "integrity: HybridPhaseTransformer decode must be recorded as full-prefix replay, not O(1)")

# ---- 7. Decision-matrix arithmetic is reproducible ----
if data["decision"]:
    weights = data["decision"]["weights"]
    wsum = sum(weights.values())
    check(wsum == 100, f"decision weights must sum to 100, got {wsum}")
    for name, cand in data["decision"]["candidates"].items():
        recomputed = sum(weights[k] * cand["scores"][k] for k in weights)
        check(recomputed == cand["weighted_total"],
              f"decision arithmetic mismatch for {name}: stated {cand['weighted_total']} != recomputed {recomputed}")
        # scores in range 1-5
        for k, v in cand["scores"].items():
            check(1 <= v <= 5, f"{name}.{k} score {v} out of range 1-5")
    # KDA must be the balanced winner and Phase must not be a candidate
    totals = {n: c["weighted_total"] for n, c in data["decision"]["candidates"].items()}
    winner = max(totals, key=totals.get)
    check(winner.startswith("KDA"), f"expected KDA balanced winner, got {winner}")
    check(not any("phase" in n.lower() for n in totals),
          "integrity: Phase must NOT appear as a scored decision candidate")

# ---- 8. Phase exclusion consistency ----
if data["decision"]:
    v = data["decision"]["verdict"]
    check(v["primary"] == "SELECT_KDA_HYBRID", f"unexpected primary verdict {v['primary']}")
    for banned in ("RETAIN_CURRENT_PHASE_CORE", "MODERNIZE_PHASE_CORE", "PHASE_AS_OPTIONAL_AUXILIARY", "PHASE_PLUS_DELTA_CORE"):
        check(banned in v.get("excluded_by_directive", []),
              f"banned Phase verdict '{banned}' not listed as excluded")

# ---- 9. Documentation links resolve (relative links in the audit docs) ----
LINK = re.compile(r"\]\((?!https?://)([^)#]+)")
for md in sorted(HERE.glob("*.md")):
    for rel in LINK.findall(md.read_text()):
        target = (md.parent / rel).resolve()
        check(target.exists(), f"broken relative link in {md.name}: {rel}")

# ---- 10. Saved-result hashes recorded for reproducibility of THIS audit ----
# (the audit records that no Phase/Hybrid checkpoints exist; assert the ledger states it)
if data["evidence"]:
    orient = data["evidence"]["orientation"].lower()
    check("no phase/hybrid checkpoints" in orient or "no checkpoints" in orient,
          "evidence ledger must record the no-committed-checkpoints fact")

# ---- report ----
print(f"hybrid-llm audit verifier: {CHECKS} checks, {len(FAILS)} failures")
for f in FAILS:
    print(f"  FAIL: {f}")
sys.exit(1 if FAILS else 0)
