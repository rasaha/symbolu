"""Perturbation correctness: semantic equivalence, canonical alignment, view-O identity."""
import torch

import qpc  # noqa: F401
from qgr.experiment import FrozenConfig
from qgr.mqar import generate_batch, split_seed
from qpc.perturbations import make_aligned_pair, decode_sample, AugConfig


def _fc():
    fc = FrozenConfig(); fc.bounded = True; fc.bound_alpha = 4.0
    return fc


def test_view_o_equals_base():
    fc = _fc(); mq = fc.base_mqar()
    base = generate_batch(mq, split_seed(0, "train", 0), 32)
    pair = make_aligned_pair(base, mq, AugConfig(), seed=1)
    assert torch.equal(pair.tokens_o, base.tokens)
    assert torch.equal(pair.targets_o, base.targets)


def test_decode_recovers_associations():
    fc = _fc(); mq = fc.base_mqar()
    base = generate_batch(mq, split_seed(3, "train", 5), 8)
    for b in range(8):
        core = decode_sample(base, b)
        # every query's answer equals the value of its correct key
        for qtok, ktok, answer in core["queries"]:
            assert core["val_for_key"][ktok] == answer


def test_alignment_by_identity():
    """Canonical key/query axes hold identical tokens across the two views (semantic equivalence)."""
    fc = _fc(); mq = fc.base_mqar()
    base = generate_batch(mq, split_seed(2, "train", 1), 16)
    pair = make_aligned_pair(base, mq, AugConfig(), seed=9)
    for b in range(16):
        ko = pair.tokens_o[b][pair.k_idx_o[b]].tolist()
        kp = pair.tokens_p[b][pair.k_idx_p[b]].tolist()
        qo = pair.tokens_o[b][pair.q_idx_o[b]].tolist()
        qp = pair.tokens_p[b][pair.q_idx_p[b]].tolist()
        assert ko == kp and qo == qp


def test_perturbation_changes_surface_not_answers():
    fc = _fc(); mq = fc.base_mqar()
    base = generate_batch(mq, split_seed(4, "train", 2), 16)
    pair = make_aligned_pair(base, mq, AugConfig(extra_distractors=6, max_pos_shift=3), seed=11)
    # the perturbed view differs in surface form for at least some samples ...
    assert pair.tokens_p.shape[1] >= pair.tokens_o.shape[1]
    differ = 0
    for b in range(16):
        o = pair.tokens_o[b].tolist()
        p = pair.tokens_p[b].tolist()
        if o != p[:len(o)] or len(p) != len(o):
            differ += 1
    assert differ >= 12  # most samples visibly perturbed


def test_shuffled_control_permutes_key_axis():
    fc = _fc(); mq = fc.base_mqar()
    base = generate_batch(mq, split_seed(0, "train", 0), 32)
    real = make_aligned_pair(base, mq, AugConfig(), seed=7, shuffled_control=False)
    ctrl = make_aligned_pair(base, mq, AugConfig(), seed=7, shuffled_control=True)
    K = real.key_perm.shape[1]
    assert torch.equal(real.key_perm, torch.arange(K).expand_as(real.key_perm))
    # control has at least some non-identity permutations
    non_identity = (ctrl.key_perm != torch.arange(K)).any(dim=1).sum().item()
    assert non_identity >= 20
