"""
event_encoder.py — learned event embeddings from EXACT typed fields (§3).

E ∈ R^(K × d): one learned row per admitted slot. The row is built ONLY from the record's exact
typed fields — structural categoricals via embedding tables, bounded value fields via a small value
table, and continuous fields (authority, confidence, version) via a linear projection.

Entity identifiers (subject_id / vendor / contract) are intentionally NOT embedded by identity —
they enter only as a matched-subject flag relative to the query — so held-out UNSEEN entity ids do
not break generalization. Answer-determining information lives in the value / status / authority
fields, whose ranges are shared across splits.

Crucially: the exact record travels beside its row (via the Slot), so an attention weight over a
row resolves to an exact `evidence_id`. Learning shapes the row; it never edits the record.
"""
from __future__ import annotations

import math
from typing import Dict, List

from .autograd import Tensor, index_rows, matmul, add_bias, tanh, add
from ._common import RNG, param, zeros_param
from .event_schema import (EventRecord, Query, N_RELATION, N_STATUS, N_INTERP, N_SUBJECT_TYPE,
                           N_OBJECT_TYPE, ACTIVE, SUPERSEDED)

VALUE_CAP = 26          # bounded value vocabulary (roles, tiers, small amounts, versions)
N_NUMERIC = 7


def _val_bucket(v: int) -> int:
    if v < 0:
        return 0
    return v if v < VALUE_CAP else VALUE_CAP - 1


class EventEncoder:
    def __init__(self, d: int, rng: RNG):
        self.d = d
        self.emb_rel = param(N_RELATION, d, rng)
        self.emb_status = param(N_STATUS, d, rng)
        self.emb_interp = param(N_INTERP, d, rng)
        self.emb_subj = param(N_SUBJECT_TYPE, d, rng)
        self.emb_obj = param(N_OBJECT_TYPE, d, rng)
        self.emb_val = param(VALUE_CAP, d, rng)
        self.emb_norm = param(VALUE_CAP, d, rng)
        self.W_num = param(N_NUMERIC, d, rng)
        self.b = zeros_param(1, d)

    def params(self, prefix: str = "enc") -> Dict[str, Tensor]:
        return {f"{prefix}.emb_rel": self.emb_rel, f"{prefix}.emb_status": self.emb_status,
                f"{prefix}.emb_interp": self.emb_interp, f"{prefix}.emb_subj": self.emb_subj,
                f"{prefix}.emb_obj": self.emb_obj, f"{prefix}.emb_val": self.emb_val,
                f"{prefix}.emb_norm": self.emb_norm, f"{prefix}.W_num": self.W_num,
                f"{prefix}.b": self.b}

    def _numeric_row(self, r: EventRecord, q: Query) -> List[float]:
        return [
            r.authority,
            r.confidence,
            r.version / 4.0,
            1.0 if r.status == ACTIVE else 0.0,
            1.0 if r.status == SUPERSEDED else 0.0,
            r.normalized_value / 6.0,
            1.0 if r.subject_id == q.subject_id else 0.0,
        ]

    def encode(self, records: List[EventRecord], q: Query) -> Tensor:
        """Return E (len(records) x d). Empty → a single zero row so downstream shapes hold."""
        if not records:
            return Tensor([[0.0] * self.d])
        rel_idx = [r.relation_type for r in records]
        st_idx = [r.status for r in records]
        it_idx = [r.interpretation_status for r in records]
        sj_idx = [r.subject_type for r in records]
        ob_idx = [r.object_type for r in records]
        vl_idx = [_val_bucket(r.object_id_or_value) for r in records]
        nm_idx = [_val_bucket(r.normalized_value) for r in records]
        num = Tensor([self._numeric_row(r, q) for r in records])

        e = index_rows(self.emb_rel, rel_idx)
        e = add(e, index_rows(self.emb_status, st_idx))
        e = add(e, index_rows(self.emb_interp, it_idx))
        e = add(e, index_rows(self.emb_subj, sj_idx))
        e = add(e, index_rows(self.emb_obj, ob_idx))
        e = add(e, index_rows(self.emb_val, vl_idx))
        e = add(e, index_rows(self.emb_norm, nm_idx))
        e = add(e, matmul(num, self.W_num))
        return tanh(add_bias(e, self.b))
