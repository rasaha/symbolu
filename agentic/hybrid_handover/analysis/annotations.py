#!/usr/bin/env python3
"""
Per-case analysis annotations (authored), combined at runtime with the *computed*
oracle-counterfactual result in capability_isolation.py.

taxonomy levels:
  1 Pure Retrieval          — find a span that exists (or detect it is absent)
  2 Semantic Retrieval      — find a query-relevant span with no fixed keyword
  3 Relationship Resolution — record a typed relationship between spans
  4 Cross-document Governance — reconcile/authorise across documents
  5 Policy / Logical Reasoning — negation, contradiction, policy-over-contract
"""

from __future__ import annotations

ANNOTATIONS = {
    "later_amendment_override": {
        "level": 3, "category": "precedence reasoning", "graph_required": True,
        "why": "Needs supersession edge MSA §7.1 →superseded_by→ Amendment 4. Solved ONLY because the shared resolver hard-codes exactly this prohibition→grant pattern; not a general capability.",
    },
    "buried_exception": {
        "level": 2, "category": "semantic retrieval / missing retrieval", "graph_required": False,
        "why": "A low-salience exception carrying no fixed keyword. Query-conditioned retrieval surfaces the span; no relationship reasoning required to make it present.",
    },
    "conflicting_definitions": {
        "level": 2, "category": "definition ambiguity / semantic retrieval", "graph_required": False,
        "why": "Two governing definitions named in the query. Retrieval surfaces both; the benchmark scores their presence, which retrieval satisfies.",
    },
    "order_of_precedence": {
        "level": 3, "category": "precedence reasoning", "graph_required": True,
        "why": "Requires following an explicit 'Order Form governs over the MSA' edge. The clause can be retrieved, but the governing relationship must be recorded — not a span, an edge.",
    },
    "conflicting_versions": {
        "level": 4, "category": "version reasoning", "graph_required": True,
        "why": "Two documents both labelled 'Amendment 3' with opposite content. Requires version/authority selection (or abstention); retrieving both spans does not resolve which governs.",
    },
    "duplicate_amendment": {
        "level": 1, "category": "pure retrieval / duplicate handling", "graph_required": False,
        "why": "The decisive clause exists intact; retrieval finds it. Duplicate/truncated copy is ignorable.",
    },
    "ocr_corruption": {
        "level": 1, "category": "coverage / parse failure", "graph_required": False,
        "why": "Source is garbled; correct behaviour is abstain. Coverage validation detects it — an ingestion property, not relationship reasoning.",
    },
    "scanned_annex": {
        "level": 1, "category": "missing document / coverage", "graph_required": False,
        "why": "Decisive content exists only as an un-OCR'd image; correct behaviour is abstain. Coverage validation detects it.",
    },
    "hidden_negation": {
        "level": 5, "category": "logical contradiction / negation", "graph_required": False,
        "why": "Evidence is COMPLETE; the verdict inverts on a negation operator ('In no event'). No amount of retrieval fixes a polarity error — a logical, not retrieval, task.",
    },
    "conflicting_tables": {
        "level": 5, "category": "logical contradiction (prose vs table)", "graph_required": True,
        "why": "Prose (3 months) contradicts a table (6 months). Both spans retrievable; resolution needs a contradiction/precedence operator between representations.",
    },
    "cross_document_reference": {
        "level": 2, "category": "cross-document reference following", "graph_required": False,
        "why": "The decisive figure sits behind a resolvable reference (Schedule C is present). Retrieval that follows the reference surfaces the span; the value exists.",
    },
    "circular_reference": {
        "level": 4, "category": "cross-document reconciliation (circular)", "graph_required": True,
        "why": "A→defined_in→B→defined_in→A cycle with no ground term. Requires cycle detection → abstain; retrieving the pointer spans yields no value.",
    },
    "missing_appendix": {
        "level": 1, "category": "missing document / coverage", "graph_required": False,
        "why": "The decisive appendix is absent from the corpus; no retrieval can produce a span that does not exist. Coverage validation detects the dangling reference → abstain.",
    },
    "irrelevant_distractors": {
        "level": 1, "category": "pure retrieval", "graph_required": False,
        "why": "One decisive clause among unrelated documents; retrieval isolates it.",
    },
    "inconsistent_numbering": {
        "level": 3, "category": "precedence reasoning + numbering normalisation", "graph_required": True,
        "why": "Amendment renumbers 7.1 as 7.01 and supersedes it. Requires a normalisation edge (7.1≡7.01) plus a supersession edge; retrieving both clauses does not record the relationship.",
    },
    "policy_override": {
        "level": 5, "category": "policy reasoning / cross-document governance", "graph_required": True,
        "why": "A corporate policy overrides the contract ('notwithstanding any contract term'). Requires an overridden_by edge from clause to policy; the policy span is retrievable but the governing relationship is not a span.",
    },
}
