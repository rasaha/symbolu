"""
model_arms.py — the nine experimental arms H0–H8 (§6).

Every arm exposes the same interface:

    logits(inst, source, use_lora=False) -> (Tensor 1xN_CLASS, attn_matrix, attribution_ids)
    trainable_params() -> Dict[str, Tensor]

`source` selects the event view: 'oracle' (ceiling) or 'predicted' (realistic, post-normalization).
The event view is always passed through the deterministic normalization/validation gate first, so
unauthorized / tampered records never reach any learned arm and the exact evidence_ids ride into
the slots (attribution).

    H0  vanilla token model over raw text            (no events)
    H1  token model + retrieved text packet          (no normalized events)
    H2  events + mean pooling                         (no slot-to-slot interaction)
    H3  events + FULL event self-attention           (primary external reasoner)
    H4  deterministic event reasoning                (no learned event attention)
    H5  ORACLE events + full event attention         (construction ceiling)
    H6  PREDICTED events + full event attention       (realistic; == H3 on predicted source)
    H7  integrated event adapter inside frozen token model
    H8  H7 + limited LoRA on the token model
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .autograd import Tensor, matmul, add_bias, concat_cols, relu
from ._common import RNG, param, zeros_param
from .event_schema import EventRecord, Query, Slot
from .event_encoder import EventEncoder
from .event_attention import EventSelfAttention, MeanPool
from .token_event_bridge import CrossBridge
from .mistral_adapter import TokenModel
from .normalization_bridge import build_working_set, ValidationReport
from .deterministic_event_reasoner import reason
from .datasets import N_CLASS, Vocab


class Head:
    """Shared linear output head. (A non-linear MLP head was evaluated and discarded: at these
    tiny sizes it destabilised optimisation and collapsed several families to a single class.)"""

    def __init__(self, d_in: int, rng: RNG):
        self.Wc = param(d_in, N_CLASS, rng)
        self.bc = zeros_param(1, N_CLASS)

    def params(self, prefix="head") -> Dict[str, Tensor]:
        return {f"{prefix}.Wc": self.Wc, f"{prefix}.bc": self.bc}

    def forward(self, x: Tensor) -> Tensor:
        return add_bias(matmul(x, self.Wc), self.bc)


def _admit(inst, source: str, K: int) -> Tuple[List[Slot], ValidationReport]:
    recs = inst.oracle_records if source == "oracle" else inst.predicted_records
    return build_working_set(recs, inst.query, K)


# ---------------- event arms (H2 / H3 / H5 / H6) ----------------
class EventArm:
    def __init__(self, d: int, seed: int, readout: str, K: int = 8):
        # component-specific sub-seeds: the encoder and output head are init-IDENTICAL to the
        # pooling arm built from the same `seed`, so H3 − H2 isolates ONLY the gated interaction.
        self.d = d
        self.K = K
        self.readout_kind = readout            # 'attn' or 'pool'
        self.enc = EventEncoder(d, RNG(seed * 100 + 1))
        self.attn = EventSelfAttention(d, RNG(seed * 100 + 2))
        self.pool = MeanPool(d)
        self.head = Head(d, RNG(seed * 100 + 3))

    def trainable_params(self) -> Dict[str, Tensor]:
        p = dict(self.enc.params())
        if self.readout_kind == "attn":
            p.update(self.attn.params())
        p.update(self.head.params())
        return p

    def logits(self, inst, source: str, use_lora: bool = False, K: Optional[int] = None,
               override_slots: Optional[List[Slot]] = None):
        if override_slots is not None:
            slots = override_slots
        else:
            slots, _ = _admit(inst, source, K or self.K)
        recs = [s.record for s in slots]
        E = self.enc.encode(recs, inst.query)
        if self.readout_kind == "attn":
            ctx, A = self.attn.readout(E)
        else:
            ctx, A = self.pool.readout(E)
        logits = self.head.forward(ctx)
        attribution = [s.evidence_id for s in slots]
        return logits, A, attribution


# ---------------- token arms (H0 / H1) ----------------
class TokenArm:
    def __init__(self, base: TokenModel, vocab: Vocab, use_retrieved: bool, max_len: int):
        self.base = base
        self.vocab = vocab
        self.use_retrieved = use_retrieved
        self.max_len = max_len

    def trainable_params(self) -> Dict[str, Tensor]:
        # H0/H1 fine-tune the whole token model on the task (vanilla model doing the task)
        p = dict(self.base.base_params())
        p.update(self.base.task_params())
        return p

    def _ids(self, inst) -> List[int]:
        text = inst.raw_text
        if self.use_retrieved:
            text = inst.retrieved_text + " . " + inst.raw_text
        return self.vocab.encode(text, self.max_len)

    def logits(self, inst, source: str = "predicted", use_lora: bool = False, **kw):
        ids = self._ids(inst)
        pooled = self.base.pooled(ids)
        return self.base.task_logits_from_pooled(pooled), [], []


# ---------------- deterministic arm (H4) ----------------
class DeterministicArm:
    def __init__(self, K: int = 8):
        self.K = K

    def trainable_params(self) -> Dict[str, Tensor]:
        return {}

    def predict(self, inst, source: str, K: Optional[int] = None) -> Tuple[int, List[int]]:
        slots, _ = _admit(inst, source, K or self.K)
        recs = [s.record for s in slots]
        return reason(recs, inst.query.task_family, inst.query.subject_id)


# ---------------- integrated arms (H7 / H8) ----------------
class IntegratedArm:
    """Frozen token base + event encoder + event self-attention + token↔event bridge (§5 Level B)."""

    def __init__(self, base: TokenModel, vocab: Vocab, d: int, rng: RNG, max_len: int,
                 use_lora: bool = False, K: int = 8):
        self.base = base
        self.vocab = vocab
        self.d = d
        self.K = K
        self.max_len = max_len
        self.use_lora = use_lora
        self.enc = EventEncoder(d, rng)
        self.attn = EventSelfAttention(d, rng)
        self.bridge = CrossBridge(d, rng)
        self.head = Head(2 * d, rng)
        self.t2e_on = True
        self.e2t_on = True
        self._hcache: Dict[int, Tensor] = {}     # frozen base hidden per instance (pre-LoRA)

    def trainable_params(self) -> Dict[str, Tensor]:
        p = dict(self.enc.params())
        p.update(self.attn.params())
        p.update(self.bridge.params())
        p.update(self.head.params("ihead"))
        if self.use_lora:
            p.update(self.base.lora_params())     # only LoRA of the base is trainable (H8)
        return p

    def logits(self, inst, source: str, use_lora: Optional[bool] = None, K: Optional[int] = None,
               override_slots: Optional[List[Slot]] = None):
        lora = self.use_lora if use_lora is None else use_lora
        from .autograd import row_mean, matmul as _mm, add as _add
        # frozen base hidden is CONSTANT across epochs → cache it once (base never trains here).
        key = id(inst)
        if key not in self._hcache:
            ids = self.vocab.encode(inst.raw_text, self.max_len)
            Hb = self.base.hidden(ids, use_lora=False)
            self._hcache[key] = Tensor([row[:] for row in Hb.data])   # detached constant
        Hbase = self._hcache[key]
        if lora:                                            # trainable low-rank delta on top (H8)
            Htok = _add(Hbase, _mm(_mm(Hbase, self.base.lora_A), self.base.lora_B))
        else:
            Htok = Hbase
        tok_ctx = row_mean(Htok)                            # 1 x d
        slots = override_slots if override_slots is not None else _admit(inst, source, K or self.K)[0]
        recs = [s.record for s in slots]
        E = self.enc.encode(recs, inst.query)
        if self.t2e_on:
            E = self.bridge.token_to_event(E, Htok)         # token → event
        event_ctx, A = self.attn.readout(E)                 # 1 x d : pool + gated interaction
        if self.e2t_on:
            tok_ctx = self.bridge.event_to_token(tok_ctx, E)   # event → token (over event rows)
        fused = concat_cols(tok_ctx, event_ctx)             # 1 x 2d
        logits = self.head.forward(fused)
        attribution = [s.evidence_id for s in slots]
        return logits, A, attribution
