#!/usr/bin/env python3
"""demo_unknown_term.py — scalable S with NO per-word dictionary.

Scores a term that is NOT in the demo gloss table ("cardiologist") using:
  * a definition_provider (a stand-in for a dictionary/KB/LLM — here a tiny inline lookup), and
  * embedding similarity (the built-in deterministic offline embedder; pass a real embed_fn in prod).

Shows that the term is scored (not auto-rejected), that S comes from semantic similarity (not a
curated table), and contrasts the lexical fallback (which over-rejects) with the embedding path.

Run: python scripts/cg_wrapper_ablation/csr_match_filter/demo_unknown_term.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from csr_match_filter import (  # noqa: E402
    DOMAIN_TEMPLATES,
    SemanticCoherenceAdapter,
    build_trace,
    hashing_embed,
)


# --- a stand-in for an external definition source (dictionary / KB / WordNet / LLM gloss) ----------
# NOT a curated per-word table baked into the wrapper — it models the definition_provider interface.
def definition_provider(term: str) -> str:
    kb = {
        # phrased with morphological variants (clinician/treatments/patients) so exact-token
        # overlap with the domain definitions is ~0 — that is what over-rejects under lexical.
        "surgeon": "a clinician who performs surgical operations and treatments on patients",
        "cardiologist": "a physician and medical specialist who treats heart disease",
    }
    return kb.get(term.lower(), term)


def main() -> int:
    term = "surgeon"   # NOT present in DEMO_TERM_GLOSSES / DEMO_CURATED_SEMANTIC
    query = f"Is a {term} more of a healer or a fruit?"
    domains = ["medicine", "care", "authority", "commerce", "fruit"]

    print(f"Unknown term (no curated gloss, no curated S): {term!r}")
    print(f"definition(term) from provider: {definition_provider(term)!r}\n")

    # 1) lexical fallback — exact-token overlap; over-rejects morphological variants
    lex = SemanticCoherenceAdapter(definition_provider=definition_provider, offline_backend="lexical")
    # 2) embedding path — deterministic offline embedder (stand-in for a real sentence model)
    emb = SemanticCoherenceAdapter(definition_provider=definition_provider, embed_fn=hashing_embed)

    print(f"{'domain':<10}{'S(lexical)':>12}{'S(embedding)':>14}")
    print("-" * 36)
    for d in domains:
        print(f"{d:<10}{lex.similarity(term, d):>12.3f}{emb.similarity(term, d):>14.3f}")

    trace = build_trace(query, [term], domains, adapter=emb)
    print("\nC/R/S trace (embedding S):")
    print(f"{'domain':<10}{'C':>7}{'R':>7}{'S':>7}{'MATCH':>8}   decision")
    for s in sorted(trace.scores, key=lambda x: -x.match):
        print(f"{s.domain:<10}{s.C:>7.3f}{s.R:>7.3f}{s.S:>7.3f}{s.match:>8.3f}   {s.decision}")
    print(f"\nframe: primary={trace.primary_domains} secondary={trace.secondary_domains} "
          f"rejected={trace.rejected_domains}")

    # the point: an unknown term is scored (medicine not auto-rejected) and fruit is vetoed by S.
    med = next(s for s in trace.scores if s.domain == "medicine")
    fruit = next(s for s in trace.scores if s.domain == "fruit")
    assert not med.decision.startswith("reject"), "unknown term should NOT be auto-rejected for medicine"
    assert fruit.decision.startswith("reject"), "fruit should be vetoed by the S firewall"
    print("\nOK: unknown term scored from its definition via embeddings; medicine kept, fruit vetoed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
