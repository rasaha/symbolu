"""
_common.py — shared harness for the Phase-guidance diagnostics.

Everything here is DIAGNOSTIC and READ-ONLY with respect to the frozen Phase core:
it imports symbolu.lightweight_phase unmodified, constructs the same GuidedSlotLM
arms as the production experiment, and exposes helpers to (a) train/cache the small
arm models, (b) extract per-token local (h) and Phase-readout (g) features, and
(c) recompute the frozen Phase internals (numerator/denominator per source token)
WITHOUT touching the frozen implementation.

Frozen contract observed:
  * PhaseConfig used by the experiment is embed_dim=96, num_heads=4, all other
    fields default → bounded_phase=True, amp_floor=0.0, amp_scale=1.0,
    denom_eps=0.1, detach_denominator=True, decay_mode="none" (NO decay), aux_scale=1.0.
  * The Phase *code* is frozen; the Phase *layer weights* inside each arm are
    randomly initialised and trained jointly with the rest of the arm (they are in
    model.parameters()). "Frozen Phase" therefore means frozen equations, not
    frozen weights.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

torch.set_num_threads(4)

from experiments.phase_guided_slots.datasets_pressure import (
    build_pressure_tokenizer, generate_pressure, PressureGenerator,
)
from experiments.phase_guided_slots.guided_models import GCfg, build, GuidedSlotLM
from experiments.phase_guided_slots.train_eval import TCfg, train, evaluate
from symbolu.lightweight_phase.config import PhaseConfig

HERE = Path(__file__).resolve().parent
CKPT = HERE / "results" / "ckpt"
RAW = HERE / "results" / "raw"
CKPT.mkdir(parents=True, exist_ok=True)
RAW.mkdir(parents=True, exist_ok=True)

# Canonical experiment settings (match run_study.STUDY / GCfg defaults).
EMBED_DIM = 96
NUM_HEADS = 4
HEAD_DIM = EMBED_DIM // NUM_HEADS
LOCAL_WINDOW = 16
NUM_SLOTS = 8
TOP_K = 4
TARGET_LEN = 180
STEPS = 350
BATCH = 16
LR = 1e-3
PRESSURE_CAND = {"1x": 8, "3x": 24}


def make_tok():
    return build_pressure_tokenizer()


def make_cfg(tok) -> GCfg:
    return GCfg(vocab_size=tok.vocab_size, embed_dim=EMBED_DIM, num_heads=NUM_HEADS,
                local_window=LOCAL_WINDOW, num_slots=NUM_SLOTS, top_k=TOP_K,
                max_seq_len=TARGET_LEN * 3)


def data_for(tok, ncand: int, seed: int, n_train=400, n_val=60, n_test=100):
    tr = generate_pressure(tok, "train", seed, n_train, ncand, TARGET_LEN)
    va = generate_pressure(tok, "val", 500 + seed, n_val, ncand, TARGET_LEN)
    te = generate_pressure(tok, "test", 1000 + seed, n_test, ncand, TARGET_LEN)
    return tr, va, te


def train_or_load(arm: str, pressure: str, seed: int = 0, steps: int = STEPS,
                  force: bool = False) -> Tuple[GuidedSlotLM, GCfg, object, dict]:
    """Train (and cache) an arm at a given pressure, or load the cached checkpoint."""
    tok = make_tok()
    cfg = make_cfg(tok)
    ncand = PRESSURE_CAND[pressure]
    path = CKPT / f"{arm}_p{pressure}_s{seed}.pt"
    meta_path = CKPT / f"{arm}_p{pressure}_s{seed}.json"
    m = build(cfg, arm, seed)
    if path.exists() and not force:
        m.load_state_dict(torch.load(path, map_location="cpu"))
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        return m, cfg, tok, meta
    tr, va, te = data_for(tok, ncand, seed)
    trlog = train(m, tr, tok.pad_id, TCfg(steps=steps, batch_size=BATCH, lr=LR,
                                          seed=seed, eval_every=100), val=va)
    metrics = evaluate(m, te, tok.pad_id)
    torch.save(m.state_dict(), path)
    meta = {"arm": arm, "pressure": pressure, "seed": seed, "steps": steps,
            "train": trlog, "metrics": metrics}
    meta_path.write_text(json.dumps(meta, indent=2))
    return m, cfg, tok, meta


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------
@torch.no_grad()
def encode_features(model: GuidedSlotLM, ids: torch.Tensor):
    """Return (h, g) exactly as the arm computes them. h:[B,N,D], g:[B,N,D]."""
    return model.encode(ids)


def collate_ids(examples, pad_id: int):
    maxlen = max(len(e.tokens) for e in examples)
    B = len(examples)
    ids = torch.full((B, maxlen), pad_id, dtype=torch.long)
    for i, e in enumerate(examples):
        ids[i, :len(e.tokens)] = torch.tensor(e.tokens)
    return ids


# ---------------------------------------------------------------------------
# Frozen Phase internals — recomputed read-only (numerator/denominator per token)
# ---------------------------------------------------------------------------
@torch.no_grad()
def phase_internals(phase_layer, h: torch.Tensor):
    """Recompute the frozen Phase kernel intermediates for read-only diagnostics.

    Mirrors LightweightPhaseAttention.forward exactly (no decay path, since the
    experiment config uses decay_mode='none'): returns per-token, per-head, per-dim
    contributions so we can attribute the normalized readout to individual source
    tokens. Reads the (trained) frozen-code layer's weights; modifies nothing.

    Returns dict with:
      kv    : [B,N,H,Dh] complex   per-token phasor*value (numerator increments)
      a_k   : [B,N,H,Dh] float     per-token key amplitude (denominator increments)
      S     : [B,N,H,Dh] complex   cumulative state
      A     : [B,N,H,Dh] float     cumulative amplitude
      a_q,phi_q : query amp/phase  [B,N,H,Dh]
    """
    cfg: PhaseConfig = phase_layer.config
    assert cfg.decay_mode == "none", "diagnostic assumes frozen experiment config (no decay)"
    x_norm = phase_layer.norm(h)
    B, N, _ = x_norm.shape
    H, Dh = phase_layer.num_heads, phase_layer.head_dim

    def split(lin):
        return lin(x_norm).view(B, N, H, Dh)

    phi_q_raw = split(phase_layer.W_phi_q)
    phi_k_raw = split(phase_layer.W_phi_k)
    a_q = cfg.amp_floor + cfg.amp_scale * torch.sigmoid(split(phase_layer.W_a_q))
    a_k = cfg.amp_floor + cfg.amp_scale * torch.sigmoid(split(phase_layer.W_a_k))
    v = split(phase_layer.W_v)
    if cfg.bounded_phase:
        phi_q = math.pi * torch.sin(phi_q_raw)
        phi_k = math.pi * torch.sin(phi_k_raw)
    else:
        phi_q, phi_k = phi_q_raw, phi_k_raw
    phi_q, a_q, phi_k, a_k, v = phi_q.float(), a_q.float(), phi_k.float(), a_k.float(), v.float()

    k_phasor = torch.polar(a_k, -phi_k)
    v_complex = torch.complex(v, torch.zeros_like(v))
    kv = k_phasor * v_complex                    # numerator increments [B,N,H,Dh]
    S = torch.cumsum(kv, dim=1)
    A = torch.cumsum(a_k, dim=1)
    return {"kv": kv, "a_k": a_k, "S": S, "A": A, "a_q": a_q, "phi_q": phi_q,
            "phi_k": phi_k, "v": v}


@torch.no_grad()
def readout_contrib_from_token(internals, query_pos, source_pos):
    """Contribution of a single source token j to the (unnormalized) Phase readout
    n_t = Re(q_t ⊙ S_t) at query position t, i.e. Re(q_t ⊙ kv_j), summed over
    head/dim. Plus the denominator increment a_k_j and the full denominator Z_t.

    query_pos, source_pos : [B] long. Returns dict of [B] tensors.
    """
    a_q = internals["a_q"]; phi_q = internals["phi_q"]
    kv = internals["kv"]; A = internals["A"]; a_k = internals["a_k"]
    B = a_q.shape[0]
    ar = torch.arange(B)
    q_phasor = torch.polar(a_q[ar, query_pos], phi_q[ar, query_pos])   # [B,H,Dh]
    kv_j = kv[ar, source_pos]                                          # [B,H,Dh]
    contrib = (q_phasor * kv_j).real.sum(dim=(-1, -2))                 # [B]
    denom_incr = a_k[ar, source_pos].sum(dim=(-1, -2))                 # [B]
    Z = (a_q[ar, query_pos] * A[ar, query_pos]).clamp(min=0.1).sum(dim=(-1, -2))
    return {"num_contrib": contrib, "denom_incr": denom_incr, "Z": Z}


# ---------------------------------------------------------------------------
# Position helpers on a PExample (topic token, topic-fact value token, distractors)
# ---------------------------------------------------------------------------
def locate_positions(ex, tok) -> Dict:
    """Find useful token positions in an example: the topic-declaration token, the
    topic-fact value token (write label==1), distractor value tokens (label==0),
    and the query/answer positions."""
    toks = ex.tokens
    wl = ex.write_labels
    topic_val_positions = [i for i, l in enumerate(wl) if l == 1]
    distractor_positions = [i for i, l in enumerate(wl) if l == 0]
    # topic declaration: header is ["TOPIC","vendor",topic,"<sep>"] at the start.
    topic_id = toks[2]  # header position 2 is the topic entity token
    return {
        "topic_id": topic_id,
        "topic_decl_pos": 2,
        "topic_val_pos": topic_val_positions[0] if topic_val_positions else None,
        "distractor_pos": distractor_positions,
        "answer_pos": ex.answer_pos,
        "answer_id": ex.answer_id,
    }


# ---------------------------------------------------------------------------
# Lightweight multinomial logistic-regression probe (the "diagnostic probe")
# ---------------------------------------------------------------------------
def fit_linear_probe(X: torch.Tensor, y: torch.Tensor, num_classes: int,
                     Xte: torch.Tensor, yte: torch.Tensor, steps=300, lr=0.05,
                     wd=1e-3) -> Dict:
    """Train a linear (softmax) probe ŷ = W x. Returns top-1/top-k acc + calibration."""
    d = X.shape[1]
    W = nn.Linear(d, num_classes)
    opt = torch.optim.Adam(W.parameters(), lr=lr, weight_decay=wd)
    # standardize
    mu, sd = X.mean(0, keepdim=True), X.std(0, keepdim=True) + 1e-6
    Xn, Xten = (X - mu) / sd, (Xte - mu) / sd
    for _ in range(steps):
        opt.zero_grad()
        loss = F.cross_entropy(W(Xn), y)
        loss.backward(); opt.step()
    with torch.no_grad():
        logits = W(Xten)
        prob = logits.softmax(-1)
        pred = logits.argmax(-1)
        top1 = (pred == yte).float().mean().item()
        k = min(3, num_classes)
        topk = (logits.topk(k, -1).indices == yte[:, None]).any(-1).float().mean().item()
        conf = prob.max(-1).values
        correct = (pred == yte).float()
        # simple calibration: mean confidence vs accuracy
        ece = (conf.mean().item() - top1)
    return {"top1": top1, "topk": topk, "k": k, "mean_conf": conf.mean().item(),
            "conf_gap": ece, "n_train": len(y), "n_test": len(yte),
            "num_classes": num_classes}


def base_name_label_map():
    """Deterministic map base-name string -> class index (over all BASE_NAMES)."""
    from experiments.lightweight_phase_natural_language.datasets import BASE_NAMES
    return {b: i for i, b in enumerate(BASE_NAMES)}


def save_json(name: str, obj: dict):
    p = RAW / name
    p.write_text(json.dumps(obj, indent=2, default=float))
    return p
