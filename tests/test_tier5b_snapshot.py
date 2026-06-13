"""CPU tests for the TIER5B snapshot/restore PURE helpers.

The tensor ops (snapshot_block / restore_block / verify_roundtrip) need torch + a
live int4_protected writer and are gated by the built-in `verify_roundtrip` byte-gate
ON THE POD — not here. These tests cover the cheap preconditions that guard the
dangerous tensor mutation: the 1:1 restore plan, the geometry-compatibility check,
and the size summary. Loaded standalone (importlib) so the torch-heavy kv_policy
package __init__ is not triggered.
"""
from __future__ import annotations

import importlib.util
import os
import warnings

import pytest

_PATH = os.path.join(os.path.dirname(__file__), "..", "CTM_plus", "KVPolicy",
                     "kv_policy", "tier5b_snapshot.py")


def _load():
    spec = importlib.util.spec_from_file_location("tier5b_snapshot", os.path.abspath(_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


snap = _load()


# ------------------------------ plan_restore ------------------------------- #
def test_plan_restore_one_to_one_in_order():
    assert snap.plan_restore(3, 3) == [(0, 0), (1, 1), (2, 2)]


def test_plan_restore_refuses_count_mismatch():
    with pytest.raises(ValueError, match="1:1"):
        snap.plan_restore(4, 3)            # fewer targets than saved blocks -> would truncate


def test_plan_restore_refuses_empty():
    with pytest.raises(ValueError, match="empty"):
        snap.plan_restore(0, 0)


# -------------------------- check_meta_compatible -------------------------- #
def _meta(D=128, BS=32, n_protect=5, prot_format="bf16"):
    return {"D": D, "BS": BS, "H": 8, "n_protect": n_protect, "prot_format": prot_format}


def test_meta_compatible_passes_on_match():
    assert snap.check_meta_compatible(_meta(), _meta()) is True


@pytest.mark.parametrize("field,val", [("D", 64), ("BS", 16), ("n_protect", 4)])
def test_meta_geometry_mismatch_refuses(field, val):
    bad = _meta()
    bad[field] = val
    with pytest.raises(ValueError, match="incompatible geometry"):
        snap.check_meta_compatible(bad, _meta())


def test_meta_protect_format_mismatch_warns_but_allows():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        ok = snap.check_meta_compatible(_meta(prot_format="prot_int8_asym_static"), _meta())
    assert ok is True
    assert any("protect-format differs" in str(x.message) for x in w)


# --------------------------- summarize_snapshot ---------------------------- #
class _FakeT:
    """Minimal stand-in for a tensor with the nbytes interface summarize uses."""
    def __init__(self, n, esize):
        self._n, self._e = n, esize

    def numel(self):
        return self._n

    def element_size(self):
        return self._e


def test_summarize_counts_blocks_and_bytes():
    events = [{"packed_k": _FakeT(100, 1), "k_scale": _FakeT(50, 2), "block_id": 0},
              {"packed_k": _FakeT(100, 1), "k_scale": _FakeT(50, 2), "block_id": 1}]
    out = snap.summarize_snapshot({"meta": {"prot_format": "bf16"}, "events": events})
    assert out["n_blocks"] == 2
    assert out["approx_bytes"] == 2 * (100 * 1 + 50 * 2)        # 400; block_id ignored (no nbytes)
    assert out["prot_format"] == "bf16"
