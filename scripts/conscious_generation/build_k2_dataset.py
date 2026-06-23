#!/usr/bin/env python3
"""Build the depth-varied K2 query set for the Kosha quality eval. Pre-reg:
docs/KOSHA_K2_QUALITY_EVAL_PREREG.md.

The existing C×R×S eval set is depth-uniform, so it cannot exercise Kosha. This generates depth-varied
queries: per topic, one query variant per Kosha depth level + mixed-cue + negative-control. Each row
carries a C×R×S-computable frame (term + domains in the engine's 23-domain registry) and an
`intended_depth` label authored from the TEMPLATE INTENT — independently of the Kosha selector output, so
depth-conformance scoring is not circular.

CPU-only, deterministic. No model, no embeddings. NO Guna/Vritti/Bhava fields.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

# (term, primary_domain[registry], secondary[registry], rejected[registry], high_stakes, must_include)
_TOPICS = [
    ("doctor", "medicine", "care", "finance", True, ["medical"]),
    ("vaccine", "medicine", "biology", "finance", True, ["immune"]),
    ("lawsuit", "law", "authority", "finance", True, ["legal"]),
    ("contract", "law", "commerce", "medicine", True, ["agreement"]),
    ("mortgage", "finance", "commerce", "medicine", True, ["loan"]),
    ("budget", "finance", "commerce", "medicine", True, ["money"]),
    ("database", "technology", "programming", "agriculture", False, ["data"]),
    ("firewall", "security", "technology", "fruit", False, ["network"]),
    ("algorithm", "programming", "technology", "nature", False, ["steps"]),
    ("backup", "technology", "security", "nature", False, ["copy"]),
    ("telescope", "astronomy", "technology", "commerce", False, ["light"]),
    ("fertilizer", "agriculture", "chemistry", "law", False, ["soil"]),
    ("photosynthesis", "biology", "education", "finance", False, ["light"]),
    ("cathedral", "religion", "construction", "finance", False, ["building"]),
    ("invoice", "finance", "commerce", "medicine", False, ["bill"]),
]

# depth templates: intended_depth -> (slice, query template). Labels are template-intent (independent).
_LEVEL_TEMPLATES = {
    "annamaya": ("annamaya", "What is a {term}? Explain it simply and briefly."),
    "pranamaya": ("pranamaya", "How do I work with a {term} step by step? Give me a checklist."),
    "manomaya": ("manomaya", "I'm worried and confused about this {term}. Can you help me understand?"),
    "vijnanamaya": ("vijnanamaya", "Compare the options for a {term} and explain the tradeoffs."),
    "anandamaya": ("anandamaya", "Synthesize the big picture and deeper meaning of a {term}."),
}
_MIXED_TEMPLATE = ("mixed", "I feel overwhelmed about this {term} — should I compare my options?",
                   "manomaya")   # intended: address concern first (manomaya), reasoning secondary
_NEGCTRL_TEMPLATE = ("negative_control", "Yesterday someone mentioned a {term} in passing.", "annamaya")


def build():
    rows = []
    for term, pri, sec, rej, hs, must in _TOPICS:
        frame = {"term": term, "primary_domain": pri, "secondary_domains": [sec],
                 "rejected_domains": [rej], "must_include": must, "high_stakes": hs}
        for intended, (slc, tmpl) in _LEVEL_TEMPLATES.items():
            rows.append({"id": f"{term}_{intended}", "query": tmpl.format(term=term),
                         "intended_depth": intended, "slice": slc, **frame})
        mslc, mtmpl, mintended = _MIXED_TEMPLATE
        rows.append({"id": f"{term}_mixed", "query": mtmpl.format(term=term),
                     "intended_depth": mintended, "slice": mslc, **frame})
        nslc, ntmpl, nintended = _NEGCTRL_TEMPLATE
        rows.append({"id": f"{term}_negctrl", "query": ntmpl.format(term=term),
                     "intended_depth": nintended, "slice": nslc, **frame})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the depth-varied K2 query set (CPU, deterministic).")
    ap.add_argument("--out", default="scripts/conscious_generation/data/kosha_k2_queries.json")
    args = ap.parse_args(argv)
    rows = build()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    by_level = dict(Counter(r["intended_depth"] for r in rows))
    by_slice = dict(Counter(r["slice"] for r in rows))
    out.write_text(json.dumps({
        "_about": "depth-varied K2 query set; intended_depth = template intent (independent of the Kosha "
                  "selector); all domains in the C×R×S registry. NO Guna/Vritti/Bhava.",
        "n": len(rows), "by_intended_depth": by_level, "by_slice": by_slice,
        "queries": rows}, indent=2), encoding="utf-8")
    print(f"n={len(rows)}  by_intended_depth={by_level}")
    print(f"by_slice={by_slice}\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
