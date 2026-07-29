"""
train.py — staged training protocol (§9).

    Stage 1  oracle-event event-reasoner validation   → train H2 (pool) and H3 (self-attn) on
             ORACLE events, base frozen. First prove H3 beats H2 where relation matters.
    Stage 2  predicted-event pipeline                  → (data-side) the extraction sim in
             datasets.py; measured as the H5−H6 gap at eval.
    Stage 3  external end-to-end                        → token arms H0/H1 (LM-pretrain then task).
    Stage 4  integrated adapter H7                      → base frozen, train event+bridge.
    Stage 5  limited LoRA H8                            → add trainable LoRA on the frozen base.

All training is seeded SGD on the pure-python autograd. Sizes are deliberately small (the object
under test — the K≤16 event operator — is tiny); the token stand-in is kept light.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from .autograd import Tensor, cross_entropy, add, scale
from ._common import RNG, SGD
from .datasets import DataCfg, build_dataset, N_CLASS, Instance, Vocab
from .mistral_adapter import TokenModel, perplexity
from .model_arms import EventArm, TokenArm, IntegratedArm, DeterministicArm

D = 24
MAX_LEN = 22
LORA_RANK = 4


# ---------------- generic supervised loop over event/integrated arms ----------------
def _train_arm(arm, train: List[Instance], source: str, epochs: int, lr: float, rng: RNG,
               use_lora: bool = False, log_every: int = 0, half: float = 8.0) -> None:
    opt = SGD(arm.trainable_params(), lr=lr, momentum=0.9, weight_decay=1e-5)
    idx = list(range(len(train)))
    for ep in range(epochs):
        opt.lr = lr * (0.5 ** (ep / half))     # exponential LR decay (stabilises attention/bridge)
        rng.shuffle(idx)
        tot = 0.0
        for step, i in enumerate(idx):
            inst = train[i]
            logits, _, _ = arm.logits(inst, source, use_lora=use_lora)
            loss = cross_entropy(logits, inst.gold_answer)
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += loss.data[0][0]
        if log_every and (ep % log_every == 0):
            print(f"    epoch {ep} mean_loss={tot/len(idx):.3f}")


# ---------------- Stage 1: event reasoner (oracle) ----------------
def train_event_arms(train: List[Instance], seed: int, epochs: int = 22) -> Tuple[EventArm, EventArm]:
    h3 = EventArm(D, seed, readout="attn")
    h2 = EventArm(D, seed, readout="pool")     # identical encoder+head init; only interaction differs
    _train_arm(h3, train, source="oracle", epochs=epochs, lr=0.05, rng=RNG(seed + 10))
    _train_arm(h2, train, source="oracle", epochs=epochs, lr=0.05, rng=RNG(seed + 11))
    return h3, h2


# ---------------- Stage 3: token base + token arms ----------------
def pretrain_token_base(train: List[Instance], vocab: Vocab, seed: int,
                        epochs: int = 3) -> Tuple[TokenModel, float]:
    base = TokenModel(len(vocab), D, MAX_LEN, N_CLASS, RNG(seed + 3), lora_rank=LORA_RANK)
    opt = SGD(base.base_params(), lr=0.05, momentum=0.9)
    texts = [vocab.encode(t.raw_text, MAX_LEN) for t in train]
    idx = list(range(len(texts)))
    rng = RNG(seed + 20)
    for ep in range(epochs):
        rng.shuffle(idx)
        for i in idx:
            loss, n = base.lm_loss(texts[i])
            if n == 0:
                continue
            loss = scale(loss, 1.0 / n)
            opt.zero_grad()
            loss.backward()
            opt.step()
    base_ppl = perplexity(base, texts[: min(200, len(texts))])
    return base, base_ppl


def train_token_arm(base: TokenModel, vocab: Vocab, train: List[Instance], use_retrieved: bool,
                    seed: int, epochs: int = 6) -> TokenArm:
    # clone the frozen base so task fine-tuning never mutates the shared LM-pretrained base
    arm = TokenArm(base.clone(), vocab, use_retrieved=use_retrieved, max_len=MAX_LEN)
    _train_arm(arm, train, source="predicted", epochs=epochs, lr=0.04, rng=RNG(seed + 30))
    return arm


# ---------------- Stage 4 / 5: integrated arms ----------------
def train_integrated(base: TokenModel, vocab: Vocab, train: List[Instance], seed: int,
                     use_lora: bool, epochs: int = 20) -> IntegratedArm:
    arm = IntegratedArm(base, vocab, D, RNG(seed + 4), MAX_LEN, use_lora=use_lora)
    # base is frozen: its params are simply not in trainable_params() (LoRA excepted for H8).
    # base hidden states are cached per-instance inside the arm → many epochs stay cheap.
    _train_arm(arm, train, source="oracle", epochs=epochs, lr=0.04, rng=RNG(seed + 40),
               use_lora=use_lora)
    return arm
