#!/usr/bin/env python3
"""Core instrumentation for the BindingSlots value-path / gradient-conflict diagnosis.

Design invariants (see preregistration.md and §4/§6/§15 of the phase spec):

* The frozen S architecture, BindingSlots equations, tasks, tokenizer, corpus and the committed
  training runners are NEVER edited. This module imports them read-only and adds:
    - a deterministic reproduction driver that runs the EXACT frozen runner and, via a pure
      observer (deepcopy at checkpoint boundaries), extracts frozen model snapshots WITHOUT
      adding, removing, or altering any optimizer step;
    - an instrumented BindingSlots.forward that (mode=None) is byte-identical to the frozen
      forward and, when asked, captures internal tensors or applies a single isolated oracle
      intervention. This instrumented forward is bound ONLY to frozen snapshots for analysis;
      training reproduction always uses the stock frozen forward.

* No diagnostic performs an optimizer step. Gradients are cleared after every measurement.
  Snapshot model hashes are checked to be unchanged across all diagnostics.

Requires torch.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import pathlib
import random
import sys
import types

import torch
import torch.nn.functional as F

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
SBS = REPO / "hybrid_llm_vnext_lab" / "experiments" / "slot_formation_stabilization"
NEURAL = REPO / "hybrid_llm_vnext_lab" / "experiments" / "neural_slots_only"
PERS = REPO / "experiments" / "bindingslots_persistence"
FR = REPO / "experiments" / "bindingslots_functional_routing"
for p in (str(HERE), str(SBS), str(NEURAL), str(PERS), str(FR)):
    if p not in sys.path:
        sys.path.insert(0, p)

CAPTURE_CHECKPOINTS = [600, 700, 900, 1200]


# ======================================================================= model hashing / state
def model_state_hash(model) -> str:
    """Order-stable sha256 over all named parameters + buffers (fp32 bytes)."""
    h = hashlib.sha256()
    for name, p in sorted(model.named_parameters(), key=lambda kv: kv[0]):
        h.update(name.encode())
        h.update(p.detach().cpu().contiguous().numpy().tobytes())
    for name, b in sorted(model.named_buffers(), key=lambda kv: kv[0]):
        h.update(name.encode())
        h.update(b.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


# ======================================================================= reproduction + snapshots
class _SnapshotState:
    def __init__(self, targets):
        self.targets = set(targets)
        self.step_count = 0
        self.snaps = {}       # step -> deepcopy(model)

    def maybe_snapshot(self, model):
        s = self.step_count
        if s in self.targets and s not in self.snaps:
            # Null the transient capture attributes before deepcopy. alignment_loss / h2_loss run a
            # GRAD-ENABLED forward with capture on and leave grad-attached _sfs_wlogit/_sfs_rlogit on
            # the slot modules (enable_capture(False) only clears waddr/raddr/gate). Those non-leaf
            # tensors break deepcopy. They are never read by the training forward/loss (each capture
            # user re-enables and re-computes them), so clearing them perturbs nothing. This is the
            # same clean state the frozen H2 teacher deepcopy relies on.
            for sm in model.slot_mixers():
                for a in ("_sfs_wlogit", "_sfs_rlogit", "_sfs_waddr", "_sfs_raddr", "_sfs_gate"):
                    if hasattr(sm, a):
                        setattr(sm, a, None)
            # pure observer: deepcopy consumes no torch global RNG and touches no optimizer state
            self.snaps[s] = copy.deepcopy(model).eval()


@contextlib.contextmanager
def _instrumented_runtime(state):
    """Wrap AdamW.step to count optimizer steps, and patch the two diagnostic entry points the
    frozen record() calls (routing_diagnostics for slot arms, stabilize._needle_at for every arm)
    so we can deepcopy the live model at checkpoint boundaries. Restores everything on exit.

    IMPORTANT: the snapshot is taken at the TOP of a checkpoint iteration (before that iteration's
    optimizer step), exactly where the frozen record(step) runs, so snapshot at target S == the
    model after S completed optimizer steps == the state the committed record(S) measured.
    """
    import diagnostics as DIAG
    import stabilize as SB

    orig_step = torch.optim.AdamW.step
    orig_routing = DIAG.routing_diagnostics
    orig_needle = SB._needle_at

    def counting_step(self, *a, **k):
        out = orig_step(self, *a, **k)
        state.step_count += 1
        return out

    def snap_routing(model, *a, **k):
        state.maybe_snapshot(model)
        return orig_routing(model, *a, **k)

    def snap_needle(model, *a, **k):
        state.maybe_snapshot(model)
        return orig_needle(model, *a, **k)

    torch.optim.AdamW.step = counting_step
    DIAG.routing_diagnostics = snap_routing
    SB._needle_at = snap_needle
    try:
        yield
    finally:
        torch.optim.AdamW.step = orig_step
        DIAG.routing_diagnostics = orig_routing
        SB._needle_at = orig_needle


def reproduce_run(arm, seed, steps=1200, targets=CAPTURE_CHECKPOINTS):
    """Deterministically reproduce a committed run via the FROZEN runner, capturing frozen model
    snapshots at `targets` checkpoints. Returns (record, {step: frozen_model}). The record is the
    exact object the frozen runner returns and is compared against committed evidence by the gate.
    No optimizer step is added, removed, or altered; snapshots are deepcopies (pure observers)."""
    import persistence_arms as PA
    state = _SnapshotState(targets)
    with _instrumented_runtime(state):
        rec = PA.run_arm(arm, seed, steps=steps)
    return rec, state.snaps, state.step_count


# ======================================================================= instrumented forward
def _instrumented_forward(self, x):
    """Byte-identical to legacy_phase_lc_slots.BindingSlots.forward when
    self._diag_mode is None and self._diag_capture is False. Otherwise captures internal tensors
    and/or applies exactly one isolated oracle intervention on the READ at the query positions.

    Oracle modes (per-example fact_pos/query_pos supplied via module attrs), applied per layer with
    that layer's own s* = argmax write-address at fact_pos:
      'oracle_address'   : read[b, qpos] = slots[b, qpos, s*]      via one-hot read distribution
      'oracle_read_query': read[b, qpos] = m_query[s*]  = slots[b, qpos, s*]  (direct target read)
      'oracle_postwrite' : read[b, qpos] = m_postwrite[s*] = slots[b, fpos, s*] (restore written value)
    Only the READ vector at the query position is replaced; W_o, the residual add, backbone and
    decoder are untouched. Everything else in the batch/sequence is unchanged.
    """
    B, N, D = x.shape
    xn = self.norm(x)
    waddr = self._route(self.W_wk(xn))
    g = torch.sigmoid(self.gate(xn))
    v = self.W_wv(xn)
    w = (g * waddr)
    weighted = w.unsqueeze(-1) * v.unsqueeze(2)
    num = torch.cumsum(weighted, dim=1)
    den = torch.cumsum(w, dim=1).unsqueeze(-1) + 1e-6
    slots = num / den
    if self.ablate == 'zero':
        slots = torch.zeros_like(slots)
    elif self.ablate == 'shuffle_val':
        slots = slots[:, :, torch.randperm(self.M, device=x.device)]
    raddr = self._route(self.W_rq(xn))
    if self.ablate == 'rand_keys':
        raddr = torch.rand_like(raddr).softmax(-1)
    read = torch.einsum('bnm,bnmd->bnd', raddr, slots)

    mode = getattr(self, "_diag_mode", None)
    if mode is not None:
        fpos = self._diag_fact_pos          # [B] long
        qpos = self._diag_query_pos         # [B] long
        idx = torch.arange(B)
        sstar = waddr[idx, fpos].argmax(-1)                 # [B] per-example written slot (this layer)
        read = read.clone()
        if mode == 'oracle_address':
            oh = F.one_hot(sstar, num_classes=self.M).to(slots.dtype)  # [B, M]
            read[idx, qpos] = torch.einsum('bm,bmd->bd', oh, slots[idx, qpos])
        elif mode == 'oracle_read_query':
            read[idx, qpos] = slots[idx, qpos, sstar]       # m_query[s*]
        elif mode == 'oracle_postwrite':
            read[idx, qpos] = slots[idx, fpos, sstar]       # m_postwrite[s*]
        else:
            raise ValueError(f"unknown oracle mode {mode}")

    if getattr(self, "_diag_capture", False):
        fpos = getattr(self, "_diag_fact_pos", None)
        qpos = getattr(self, "_diag_query_pos", None)
        if fpos is not None and qpos is not None:
            # compact per-example capture (avoids materializing the full [B,N,M,D] slots tensor
            # in stored form): only the tensors the value-path diagnostics need.
            idx = torch.arange(B)
            sstar = waddr[idx, fpos].argmax(-1)                    # [B]
            self._cap = {
                "sstar": sstar.detach(),
                "v_fact": v[idx, fpos].detach(),                  # written fact representation [B,D]
                "waddr_fact": waddr[idx, fpos].detach(),          # write addr at fact [B,M]
                "raddr_query": raddr[idx, qpos].detach(),         # read addr at query [B,M]
                "read_query": read[idx, qpos].detach(),           # u_read at query [B,D]
                "c_mem_query": self.W_o(read[idx, qpos]).detach(),# projected mem contribution [B,D]
                "m_postwrite": slots[idx, fpos, sstar].detach(),  # target slot after write [B,D]
                "m_query": slots[idx, qpos, sstar].detach(),      # target slot at query time [B,D]
                "read_prob_on_sstar": raddr[idx, qpos, sstar].detach(),  # [B]
                "w_to_sstar": w.gather(2, sstar.view(B, 1, 1).expand(B, N, 1)).squeeze(2).detach(),
                "gate_fact": g[idx, fpos, 0].detach(),            # write gate at fact [B]
            }
        else:
            # full capture (small-batch no-op verification only)
            self._cap = {
                "xn": xn.detach(), "waddr": waddr.detach(), "v": v.detach(),
                "slots": slots.detach(), "raddr": raddr.detach(), "read": read.detach(),
                "c_mem": self.W_o(read).detach(),
            }
    with torch.no_grad():
        util = waddr.mean(dim=(0, 1))
        self.diag = {
            'slot_write_gate_mean': g.mean().item(),
            'slot_util_entropy': float(-(util * (util + 1e-9).log()).sum().item()),
            'slot_util_max': util.max().item(),
            'read_addr_max_mean': raddr.max(-1).values.mean().item(),
            'num_slots': self.M,
        }
    return self.W_o(read)


@contextlib.contextmanager
def instrumented_model(model, mode=None, capture=False, fact_pos=None, query_pos=None):
    """Bind the instrumented forward to every slot module for the duration; restore stock forward
    on exit. mode/capture/positions are applied uniformly to all slot layers."""
    slots = model.slot_mixers()
    originals = []
    for sm in slots:
        originals.append(sm.forward)
        sm.forward = types.MethodType(_instrumented_forward, sm)
        sm._diag_mode = mode
        sm._diag_capture = capture
        sm._diag_fact_pos = fact_pos
        sm._diag_query_pos = query_pos
    try:
        yield slots
    finally:
        for sm, f in zip(slots, originals):
            sm.forward = f
            for a in ("_diag_mode", "_diag_capture", "_diag_fact_pos", "_diag_query_pos", "_cap"):
                if hasattr(sm, a):
                    delattr(sm, a)


# ======================================================================= needle examples w/ spans
def needle_examples(vocab, T, seed, n, distance):
    """Regenerate the EXACT needle eval examples used by the committed ledger
    (make_eval_set('needle', N=256, vocab, seed, n, distance)) while ALSO recovering, per example,
    the fact value-token position (write position) and the query position (N-2, predicts the value
    at N-1). Identical RNG draws => identical sequences; we only additionally compute the spans."""
    N = 256
    rng = random.Random(seed)
    xs, fps, qps, tgts = [], [], [], []
    S = vocab.stoi
    for _ in range(n):
        e = rng.choice(vocab.ent)
        v = rng.choice(vocab.val)
        fact = [S['the'], S['code'], S['for'], e, S['is'], v, S['.']]
        tail = [S['the'], S['code'], S['for'], e, S['is'], v]
        body = N - len(tail)
        gap = min(distance, body - len(fact))
        before = body - len(fact) - gap
        ids = _filler(vocab, before, rng) + fact + _filler(vocab, gap, rng) + tail
        ids = ids[:N]
        while len(ids) < N:
            ids = [vocab.pad] + ids
        xs.append(torch.tensor(ids, dtype=torch.long))
        fps.append(before + 5)   # value token position inside the fact (0-based in the full seq)
        qps.append(N - 2)        # position whose logits predict the value at N-1
        tgts.append(v)
    return torch.stack(xs), torch.tensor(fps), torch.tensor(qps), torch.tensor(tgts)


def _filler(vocab, n, rng):
    return [vocab.filler[rng.randrange(len(vocab.filler))] for _ in range(n)]


def verify_needle_examples_match_ledger(vocab, T, seed, n, distance):
    """Prove the regenerated examples are byte-identical to make_eval_set's X (spans added only)."""
    import tasks_adapter as TA
    X_ref, P_ref, Tg_ref, _ = TA.make_eval_set('needle', 256, vocab, seed, n=n, distance=distance)
    X, fp, qp, tg = needle_examples(vocab, T, seed, n, distance)
    return {
        "X_identical": bool(torch.equal(X, X_ref)),
        "target_identical": bool(torch.equal(tg, Tg_ref)),
        "answer_pos_all_N_minus_1": bool(torch.equal(P_ref, torch.full_like(P_ref, 255))),
    }


# ======================================================================= answer-logit measurement
@torch.no_grad()
def answer_metrics(model, X, query_pos, target, bs=64):
    """Return per-example needle-correct (argmax==target) and the correct-answer logit margin
    (target logit minus max non-target logit) at the query position, plus the mean c_mem-vs-answer
    alignment is computed separately. Uses whatever forward is currently bound (stock or oracle)."""
    model.eval()
    n = len(X)
    correct = torch.zeros(n, dtype=torch.bool)
    margin = torch.zeros(n)
    tgt_logit = torch.zeros(n)
    for i in range(0, n, bs):
        xb = X[i:i + bs]
        qp = query_pos[i:i + bs]
        tb = target[i:i + bs]
        lo = model(xb)                                    # [b, N, V]
        j = torch.arange(len(xb))
        al = lo[j, qp]                                    # [b, V] answer-position logits
        pred = al.argmax(-1)
        correct[i:i + bs] = (pred == tb)
        tl = al[j, tb]
        al2 = al.clone()
        al2[j, tb] = float('-inf')
        margin[i:i + bs] = tl - al2.max(-1).values
        tgt_logit[i:i + bs] = tl
    return {
        "needle_acc": correct.float().mean().item(),
        "answer_logit_margin_mean": margin.mean().item(),
        "target_logit_mean": tgt_logit.mean().item(),
        "n": n,
    }
