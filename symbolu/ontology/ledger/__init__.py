"""
Ontological Ledger Package
==========================

Read-only ledger adapter for identity attestations.
"""

from symbolu.ontology.ledger.ledger_adapter import (
    LedgerSpan,
    LedgerSpanInput,
    generate_ledger_span,
    generate_ledger_span_full,
    verify_span_hash,
)

__all__ = [
    "LedgerSpan",
    "LedgerSpanInput",
    "generate_ledger_span",
    "generate_ledger_span_full",
    "verify_span_hash",
]
