"""
Gold-free public loader for the TAP-E4 governance corpus.

Exposes only the public view of each case (situation + candidate authority names) — never
the ``expected_authority`` / disqualifier ground truth. A downstream consumer can obtain
governance inputs without touching evaluation labels.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from truth_assurance_pipeline.tap_e4_governance_truth.corpus import cases as corpus


def load_public(split: str) -> List[Dict[str, object]]:
    return [c.public_dict() for c in corpus.cases_for_split(split)]


def load_inputs(split: str) -> List[Tuple[object, object, object, object]]:
    """Return (intent_stub_id, retrieval_record, relationship_record, situation) per case —
    the exact inputs the governance layer consumes, with no gold attached."""
    out = []
    for c in corpus.cases_for_split(split):
        out.append((c.case_id, corpus.build_retrieval_record(c),
                    corpus.build_relationship_record(c), c.situation))
    return out


def splits() -> Tuple[str, ...]:
    return corpus.SPLITS
