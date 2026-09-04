"""Torch runtime checks for the sibling arm (fixtures only). SKIPS (exit 0) when torch is unavailable.

ABS digest preservation: the constants below were recorded from build_model(seed) BEFORE the backbone
gained the opt-in positional flag; they must never change (the parent arm is byte-identical).
"""
from __future__ import annotations

ABS_DIGESTS = {
    883000: "9bde9d2043776c8bb14539180b70bc83addaf06c75f28c69de516e9acf20e2b1",
    883001: "0c2cdeeed8d1f92c5db905745e91eb0a13a68459bdb2fd92db6fb7475554eee2",
}


def _torch():
    try:
        import torch  # noqa: F401
        return True
    except ImportError:
        return False


def test_abs_build_byte_identical():
    from ..model import build_model, parameter_digest
    for seed, d in ABS_DIGESTS.items():
        assert parameter_digest(build_model(seed)) == d, seed
        assert parameter_digest(build_model(seed, "ABS")) == d, seed

def test_rope_runtime_param_count_and_no_position_table():
    from ..model import build_model
    m = build_model(883000, "ROPE")
    assert sum(p.numel() for p in m.parameters()) == 144_896
    assert m.pos is None and not any("pos" in n for n, _ in m.named_parameters())

def test_rotation_is_norm_preserving_and_position_dependent():
    import torch
    from symbolu_neural.clean_softmax.backbone import apply_rope, rope_cos_sin
    x = torch.randn(2, 4, 9, 16)
    cos, sin = rope_cos_sin(9, 16, 10000.0, "cpu", torch.float32)
    y = apply_rope(x, cos, sin)
    assert torch.allclose(x.norm(dim=-1), y.norm(dim=-1), atol=1e-5)
    assert torch.allclose(x[:, :, 0], y[:, :, 0])                       # position 0 is the identity
    same = x[:, :, 1:2].expand(-1, -1, 8, -1)                          # same vector at positions 1..8
    ys = apply_rope(same, cos[:, :, 1:], sin[:, :, 1:])
    assert not torch.allclose(ys[:, :, 0], ys[:, :, 1])                # rotated differently per position
    # relative property: q_m . k_n depends only on m - n
    q = torch.randn(1, 1, 1, 16); k = torch.randn(1, 1, 1, 16)
    def dot(m, n):
        c, s_ = rope_cos_sin(max(m, n) + 1, 16, 10000.0, "cpu", torch.float32)
        return (apply_rope(q, c[:, :, m:m+1], s_[:, :, m:m+1]) * apply_rope(k, c[:, :, n:n+1], s_[:, :, n:n+1])).sum()
    assert torch.allclose(dot(5, 2), dot(9, 6), atol=1e-4)

def test_rope_forward_at_max_seq_and_deterministic_build():
    import torch
    from ..config import MAX_SEQ_LEN, VOCAB_SIZE
    from ..model import build_model, parameter_digest
    m = build_model(883002, "ROPE").eval()
    ids = torch.randint(0, VOCAB_SIZE, (1, MAX_SEQ_LEN))
    with torch.no_grad():
        assert tuple(m(ids).shape) == (1, MAX_SEQ_LEN, VOCAB_SIZE)
    assert parameter_digest(build_model(883002, "ROPE")) == parameter_digest(m)
    assert parameter_digest(build_model(883002, "ROPE")) != parameter_digest(build_model(883002, "ABS"))

def test_rope_arm_end_to_end_on_fixture():
    from ..run import run_experiment
    r = run_experiment(883003, n_train=1, n_eval=1, max_updates=5, arm="ROPE")
    assert r["arm"] == "ROPE" and r["training"]["max_updates"] == 5 and len(r["training"]["loss_curve"]) == 1
    from ..trainer import train_checkpoint
    try:
        train_checkpoint(883003, [{"input": "x", "output": "y"}], max_updates=1, arm="NOPE"); assert False
    except KeyError:
        pass


def main() -> int:
    if not _torch():
        print("SKIP: torch not installed (runtime checks not run)")
        return 0
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p = f = 0
    for t in tests:
        try:
            t(); p += 1; print(f"PASS {t.__name__}")
        except Exception as exc:  # noqa: BLE001
            f += 1; print(f"FAIL {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{p} passed, {f} failed, {len(tests)} total")
    return 1 if f else 0


if __name__ == "__main__":
    raise SystemExit(main())
