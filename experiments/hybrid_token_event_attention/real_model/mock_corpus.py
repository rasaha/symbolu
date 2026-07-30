"""
mock_corpus.py — deterministic MockBackend responders for the wiring smoke and unit tests.

STRICTLY non-scientific: this simulates a token model well enough to exercise the harness end to
end (extraction JSON → validation → routing → event attention → explanation → faithfulness). It is
never written out as a real-model result. Real-model numbers come only from `HFBackend`.

The extraction responder quotes REAL source spans (verbatim lines of the document) but proposes the
lossy `predicted_records` interpretation, so span verification passes while identity/version noise
flows through the deterministic validator exactly as it would for a real model.
"""
from __future__ import annotations

import json
from typing import Callable

from ..event_schema import RELATION_TYPES, STATUSES
from ..datasets import _verbalize, PHRASE, CLASS_NAMES


def make_mock_responder(inst) -> Callable[[str], str]:
    pred_by_eid = {p.evidence_id: p for p in inst.predicted_records}
    lex = PHRASE["heldout"]

    def _extraction_json() -> str:
        items = []
        for o in inst.oracle_records:
            p = pred_by_eid.get(o.evidence_id)
            if p is None:                      # extraction miss (dropped by the pipeline)
                continue
            items.append({
                "subject": f"ent_{p.subject_id}",
                "relation": RELATION_TYPES[p.relation_type],
                "object": f"ent_{p.object_id_or_value}",
                "normalized_value": p.normalized_value,
                "version": p.version,
                "status": STATUSES[p.status],
                "source_document_id": "DOC-0",
                "source_span": _verbalize(o, lex),   # verbatim quote of a real document line
                "confidence": round(p.confidence, 2),
                "ambiguous": False,
            })
        return json.dumps(items)

    def responder(prompt: str) -> str:
        if "JSON array:" in prompt:            # extraction prompt
            return _extraction_json()
        if "Explanation:" in prompt:           # explanation prompt
            return _explanation(prompt)
        # direct-answer prompt (RM0/RM1/RM2): a naive token model that cannot govern from raw text
        return '{"answer": "ABSTAIN"}'

    return responder


def _explanation(prompt: str) -> str:
    import re
    # cite the first evidence id present in the prompt; add a negation qualifier for negative outcomes
    ids = re.findall(r'"evidence_id":\s*(\d+)', prompt)
    cite = f"[EV-{ids[0]}]" if ids else ""
    decision = ""
    m = re.search(r'"decision":\s*"([^"]+)"', prompt)
    if m:
        decision = m.group(1)
    neg = ""
    if any(k in prompt for k in ('"boolean_outcome": false', '"abstained": true',
                                 '"material_conflict": true')):
        neg = " No valid supporting grant was found."
    return f"The governed decision is {decision}. It is supported by evidence {cite}.{neg}"
