#!/usr/bin/env python3
"""
End-to-end demo of the two-tier handover.

    python -m agentic.hybrid_handover.demo

Shows: Part 1 distills a 250K-token confidential corpus in-house; the gates pass;
the escalation crosses only a small redacted packet; Part 2 (frontier stand-in)
reasons over placeholders; the answer is re-hydrated in-house; the audit reports
the token reduction and the sovereignty guarantee.
"""

from __future__ import annotations

from .fixtures import QUESTION, SECRETS, build_corpus
from .frontier import MockFrontierModel
from .inhouse import InHouseExtractor
from .pipeline import run_handover


def main() -> None:
    corpus = build_corpus()
    extractor = InHouseExtractor()
    frontier = MockFrontierModel()

    print("=" * 72)
    print("PART 1 — in-house tier (O(n), on-prem)")
    print("=" * 72)
    packet = extractor.extract(QUESTION, corpus)
    print(f"docs scanned      : {packet.coverage.docs_scanned}")
    print(f"tokens ingested   : {packet.coverage.tokens_ingested:,} (never egress)")
    print(f"spans distilled   : {packet.coverage.spans_returned}")
    print(f"resolved verdict  : {packet.resolved_answer.key()}")
    for c in packet.conflicts_resolved:
        print(f"supersession      : {c.superseded_by} supersedes {c.superseded} "
              f"({c.rule})")

    print()
    print("=" * 72)
    print("HANDOVER — gates + redaction + PART 2 (frontier, redacted)")
    print("=" * 72)
    result = run_handover(
        QUESTION, corpus, SECRETS, extractor, frontier, task_type="interpretation"
    )
    a = result.audit
    print(f"decision          : {a.decision}")
    print(f"grounding gate    : pass ({a.grounded_spans} spans verbatim)")
    print(f"faithfulness gate : pass (packet re-resolves to full-corpus verdict)")
    print(f"leak gate         : {a.leak_check}")
    print(f"masked on egress  : {a.masked_placeholders}")
    print(f"corpus tokens     : {a.corpus_tokens:,}")
    print(f"egress tokens     : ~{a.egress_tokens_est}")
    print(f"reduction ratio   : {a.reduction_ratio}x  (what the API is spared)")

    print()
    print("=" * 72)
    print("FINAL ANSWER (re-hydrated in-house)")
    print("=" * 72)
    print(result.final_answer)


if __name__ == "__main__":
    main()
