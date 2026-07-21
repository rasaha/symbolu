"""
Gold-free public loader for the TAP-E5 packet corpus.

Exposes only the public view of each case and the compiled upstream records — never the
gold minimal-complete set. A downstream consumer can obtain assembly inputs without touching
evaluation labels.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from truth_assurance_pipeline.tap_e5_evidence_assembly.corpus import cases as corpus


def load_public(split: str) -> List[Dict[str, object]]:
    return [c.public_dict() for c in corpus.cases_for_split(split)]


def load_inputs(split: str) -> List[Tuple[object, object, object, object]]:
    """Return (intent, retrieval, relationship, governance) per case — the exact records the
    assembler consumes, with no gold attached."""
    return [corpus.build_records(c) for c in corpus.cases_for_split(split)]


def splits() -> Tuple[str, ...]:
    return corpus.SPLITS
