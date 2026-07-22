"""Determinism, A/D0 equivalence, inference invariance, architecture identity
(spec sections 13, 22 items 15-18)."""
import copy
import torch
from qgr import QuadConfig, build_model
from qgr.mqar import MQARConfig
from qgr.train import TrainConfig, train_arm


def _cfg():
    return QuadConfig(vocab_size=48, hidden_size=48, num_layers=2, num_heads=4,
                      ff_size=192, context_length=64)


def _mq():
    return MQARConfig(num_kv=6, num_queries=3, vocab_size=48)


def _short(arm, seed=0, steps=25):
    return TrainConfig(arm=arm, lambda_aux=1.0, steps=steps, batch_size=16, lr=3e-3,
                       seed=seed, eval_every=10**9, grad_diag_every=0, log_curves=False)


def test_arm_a_vs_d0_deterministic_equivalence():
    """Item 15 (spec 13): Arm A and Arm D0 (lambda=0) yield bit-identical final params."""
    rA = train_arm(_cfg(), _mq(), _short("A"))
    rD0 = train_arm(_cfg(), _mq(), _short("D0"))
    pA = dict(rA["model"].named_parameters())
    pD0 = dict(rD0["model"].named_parameters())
    assert set(pA) == set(pD0)
    for name in pA:
        assert torch.equal(pA[name], pD0[name]), f"param {name} differs between A and D0"
    assert abs(rA["final_val"]["task_loss"] - rD0["final_val"]["task_loss"]) == 0.0


def test_inference_invariance_when_aux_disabled():
    """Item 16: identical inference output with/without exposing aux-only objects."""
    m = build_model(_cfg(), 5).eval()
    toks = torch.randint(1, 48, (3, 24))
    with torch.no_grad():
        plain = m(toks)["logits"]
        with_quad = m(toks, expose_quad=True, expose_hidden=True)["logits"]
    assert torch.equal(plain, with_quad)  # exposing the score changes nothing


def test_identical_base_architecture_across_arms():
    """Item 17: Arms A, C, D share identical base model param names/shapes; the Arm-C
    relation head is a separate auxiliary object, absent from the base model."""
    names_shapes = lambda m: {n: tuple(p.shape) for n, p in m.named_parameters()}
    rA = train_arm(_cfg(), _mq(), _short("A", steps=3))
    rC = train_arm(_cfg(), _mq(), _short("C", steps=3))
    rD = train_arm(_cfg(), _mq(), _short("D", steps=3))
    assert names_shapes(rA["model"]) == names_shapes(rC["model"]) == names_shapes(rD["model"])
    # no relation-head params leaked into the base model
    assert not any("relation" in n.lower() for n in dict(rA["model"].named_parameters()))


def test_deterministic_repeat_under_same_seed():
    """Item 18: repeated training under the same seed is bit-identical."""
    r1 = train_arm(_cfg(), _mq(), _short("D", seed=7))
    r2 = train_arm(_cfg(), _mq(), _short("D", seed=7))
    p1 = dict(r1["model"].named_parameters())
    p2 = dict(r2["model"].named_parameters())
    for name in p1:
        assert torch.equal(p1[name], p2[name])
