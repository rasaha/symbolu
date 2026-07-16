#!/usr/bin/env python3
"""CPU self-checks for the INT4 kernel contract validators (no GPU, no kernel).

  python test_contract_cpu.py     # -> "contract CPU checks: N/N PASS"
"""
from __future__ import annotations

import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("vkc", os.path.join(_HERE, "validate_kernel_contract.py"))
V = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(V)

_n = 0


def check(name, cond):
    global _n
    assert cond, f"FAIL: {name}"
    _n += 1
    print(f"  ok: {name}")


def _good(geom=None):
    geom = geom or V.default_qwen_geom()
    return geom, {k: {"shape": s, "dtype": d, "contiguous": True}
                  for k, (s, d) in V.expected_shapes(geom).items()}


def test_schema_file():
    r = V.validate_contract_file()
    check("shipped contract passes schema", r["ok"] is True)
    check("no schema violations", r["violations"] == [])


def test_good_geometry():
    geom, good = _good()
    check("good qwen geometry -> no violations", V.validate_tensor_geometry(geom, good) == [])
    # expected shapes: packed is D/2, protect is compact
    exp = V.expected_shapes(geom)
    check("packed K last dim = D/2", exp["k_packed_int4"][0][-1] == geom["D"] // 2)
    check("protect sidecar = n_protect", exp["k_packed_protect_bf16"][0][-1] == geom["n_protect"])
    check("S = n_blocks*BS", exp["k_packed_int4"][0][1] == geom["n_blocks"] * geom["BS"])
    check("v scale groups = D/vgs", exp["v_packed_scale"][0][-1] == geom["D"] // geom["v_group_size"])


def test_catches_bad_packed_dim():
    geom, bad = _good()
    bad["k_packed_int4"] = {"shape": (1, 256, 4, 128), "dtype": "uint8"}  # full D, not D/2
    viol = V.validate_tensor_geometry(geom, bad)
    check("full-D packed caught", any("k_packed_int4" in x and "shape" in x for x in viol))


def test_catches_noncompact_protect():
    geom, bad = _good()
    bad["k_packed_protect_bf16"] = {"shape": (1, 256, 4, 128), "dtype": "bfloat16"}  # full D
    viol = V.validate_tensor_geometry(geom, bad)
    check("non-compact protect caught (shape)", any("k_packed_protect_bf16" in x for x in viol))
    # and the structural invariant when n_protect==D
    g2 = V.default_qwen_geom(); g2["n_protect"] = 128
    check("n_protect==D structural caught", any("COMPACT" in x for x in V.validate_tensor_geometry(g2, {})))


def test_catches_structural():
    g = V.default_qwen_geom(); g["H_q"] = 30  # 30 % 4 != 0
    check("GQA divisibility caught", any("GQA" in x for x in V.validate_tensor_geometry(g, {})))
    g = V.default_qwen_geom(); g["v_group_size"] = 24  # 128 % 24 != 0
    check("v_group divisibility caught", any("v_group_size" in x for x in V.validate_tensor_geometry(g, {})))
    g = V.default_qwen_geom(); g["S_q"] = 2
    check("S_q!=1 caught", any("S_q" in x for x in V.validate_tensor_geometry(g, {})))
    g = V.default_qwen_geom(); g["packed_group_size"] = 16
    check("K per-block group caught", any("packed_group_size" in x for x in V.validate_tensor_geometry(g, {})))


def test_catches_dtype_and_contiguity():
    geom, bad = _good()
    bad["k_packed_int4"] = {"shape": V.expected_shapes(geom)["k_packed_int4"][0], "dtype": "float16"}
    check("wrong dtype caught", any("dtype" in x and "k_packed_int4" in x
                                    for x in V.validate_tensor_geometry(geom, bad)))
    geom, bad = _good()
    bad["q"] = {"shape": V.expected_shapes(geom)["q"][0], "dtype": "bfloat16", "contiguous": False}
    check("non-contiguous q caught", any("contiguous" in x for x in V.validate_tensor_geometry(geom, bad)))


def main():
    for t in (test_schema_file, test_good_geometry, test_catches_bad_packed_dim,
              test_catches_noncompact_protect, test_catches_structural,
              test_catches_dtype_and_contiguity):
        t()
    print(f"contract CPU checks: {_n}/{_n} PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
