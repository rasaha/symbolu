#!/usr/bin/env python3
"""Phase C — CPU validators for the INT4 decode kernel contract (kernel_contract.json).

Two checks, both CPU-only (no GPU, no kernel):
  1. `validate_contract_file()` — the contract JSON conforms to kernel_contract.schema.json
     (structural: required keys, arg fields, invariant count). Uses `jsonschema` if present,
     else a built-in minimal checker so it runs with no extra deps.
  2. `validate_tensor_geometry(geom, tensors)` — a concrete set of {arg: (shape, dtype, contiguous)}
     satisfies the contract INVARIANTS: S = n_blocks*BS, packed last dim = D/2, H_q % H_kv == 0,
     compact protect (last dim = n_protect << D), K group = BS, D % v_group_size == 0, dtypes,
     bf16-dummy shape, output shape/dtype. Returns a list of violation strings (empty = valid).

This is the gate that a rebuilt/candidate kernel's inputs must pass before its numbers are
trusted (used in the K1 numerical-contract milestone). Pure functions; no side effects.

  python validate_kernel_contract.py            # validates the shipped contract file
  python validate_kernel_contract.py --demo     # + a good/bad geometry demo
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_CONTRACT = os.path.join(_HERE, "kernel_contract.json")
_SCHEMA = os.path.join(_HERE, "kernel_contract.schema.json")


# --------------------------------------------------------------- schema check ----
def validate_contract_file(contract_path=_CONTRACT, schema_path=_SCHEMA):
    contract = json.load(open(contract_path))
    schema = json.load(open(schema_path))
    try:
        import jsonschema  # type: ignore
        jsonschema.validate(contract, schema)
        return {"ok": True, "checker": "jsonschema", "violations": []}
    except ImportError:
        return _minimal_schema_check(contract, schema)


def _minimal_schema_check(contract, schema):
    """Dependency-free subset: required top-level keys, arg required fields, minItems/minProps."""
    v = []
    for k in schema.get("required", []):
        if k not in contract:
            v.append(f"missing required key: {k}")
    props = schema.get("properties", {})
    args = contract.get("arguments", [])
    if len(args) < props.get("arguments", {}).get("minItems", 0):
        v.append(f"arguments: {len(args)} < minItems {props['arguments']['minItems']}")
    arg_req = props.get("arguments", {}).get("items", {}).get("required", [])
    for i, a in enumerate(args):
        for rk in arg_req:
            if rk not in a:
                v.append(f"argument[{i}] ({a.get('name','?')}) missing '{rk}'")
    for key in ("invariants", "semantics"):
        need = props.get(key, {}).get("minProperties", 0)
        if len(contract.get(key, {})) < need:
            v.append(f"{key}: {len(contract.get(key, {}))} < minProperties {need}")
    out = contract.get("output", {})
    for rk in props.get("output", {}).get("required", []):
        if rk not in out:
            v.append(f"output missing '{rk}'")
    return {"ok": not v, "checker": "builtin-minimal", "violations": v}


# --------------------------------------------------------------- geometry check ----
def expected_shapes(geom):
    """The contract's concrete expected shapes for a given geometry dict."""
    B, Sq, H_q, H_kv, D = geom["B"], geom["S_q"], geom["H_q"], geom["H_kv"], geom["D"]
    BS, nprot, vgs = geom["BS"], geom["n_protect"], geom["v_group_size"]
    S = geom["n_blocks"] * BS
    DH = D // 2
    vng = D // vgs
    return {
        "q": ((B, Sq, H_q, D), "bfloat16"),
        "k_cache_dummy": ((1, S, H_kv, D), "bfloat16"),
        "cache_seqlens": ((B,), "int32"),
        "protect_mask": ((B, H_kv, D), "int8"),
        "k_packed_int4": ((B, S, H_kv, DH), "uint8"),
        "k_packed_scale": ((B, S, H_kv, D), "float16"),
        "k_packed_xmin": ((B, S, H_kv, D), "float16"),
        "k_packed_protect_bf16": ((B, S, H_kv, nprot), "bfloat16"),
        "k_packed_protect_slot": ((H_kv, D), "int"),
        "v_packed_int4": ((B, S, H_kv, DH), "uint8"),
        "v_packed_scale": ((B, S, H_kv, vng), "float16"),
        "v_packed_xmin": ((B, S, H_kv, vng), "float16"),
        "out": ((B, Sq, H_q, D), "bfloat16"),
    }


def validate_tensor_geometry(geom, tensors):
    """`tensors`: {name: {"shape": tuple, "dtype": str, "contiguous": bool(optional)}}.
    Returns a list of violation strings (empty => valid). Checks structural invariants first,
    then per-arg shape/dtype/contiguity vs expected_shapes(geom)."""
    v = []
    # ---- structural invariants ----
    if geom["H_q"] % geom["H_kv"] != 0:
        v.append(f"H_q({geom['H_q']}) % H_kv({geom['H_kv']}) != 0 (GQA invariant)")
    if geom["D"] % 2 != 0:
        v.append(f"D({geom['D']}) not even (int4 packs 2 channels/byte)")
    if geom["D"] % geom["v_group_size"] != 0:
        v.append(f"D({geom['D']}) % v_group_size({geom['v_group_size']}) != 0")
    if geom["n_protect"] >= geom["D"]:
        v.append(f"n_protect({geom['n_protect']}) not << D({geom['D']}) — sidecar must be COMPACT")
    if geom.get("packed_group_size", geom["BS"]) != geom["BS"]:
        v.append(f"packed_group_size({geom.get('packed_group_size')}) != BS({geom['BS']}) (K is per-block)")
    if geom["S_q"] != 1:
        v.append(f"S_q({geom['S_q']}) != 1 (decode is single-token)")

    exp = expected_shapes(geom)
    for name, t in tensors.items():
        if name not in exp:
            continue  # unknown/optional arg — skip
        want_shape, want_dtype = exp[name]
        got_shape = tuple(t.get("shape", ()))
        if got_shape != tuple(want_shape):
            v.append(f"{name}: shape {got_shape} != expected {tuple(want_shape)}")
        gd = str(t.get("dtype", "")).replace("torch.", "")
        if want_dtype == "int":
            if not gd.startswith("int"):
                v.append(f"{name}: dtype {gd} not an int type (expected {want_dtype})")
        elif gd and gd != want_dtype:
            v.append(f"{name}: dtype {gd} != expected {want_dtype}")
        if t.get("contiguous") is False and name in (
                "q", "k_packed_int4", "v_packed_int4", "k_packed_protect_bf16"):
            v.append(f"{name}: must be contiguous (kernel assumes C-order)")
    return v


def default_qwen_geom(B=1, n_blocks=8):
    return {"B": B, "S_q": 1, "H_q": 28, "H_kv": 4, "D": 128, "BS": 32,
            "n_protect": 5, "v_group_size": 32, "n_blocks": n_blocks, "packed_group_size": 32}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate the INT4 kernel contract (CPU)")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args(argv)
    sc = validate_contract_file()
    print(f"[schema] contract file valid={sc['ok']} ({sc['checker']}) violations={sc['violations']}")
    rc = 0 if sc["ok"] else 1
    if a.demo:
        geom = default_qwen_geom()
        good = {k: {"shape": s, "dtype": d, "contiguous": True}
                for k, (s, d) in expected_shapes(geom).items()}
        gv = validate_tensor_geometry(geom, good)
        print(f"[geom] good inputs -> violations={gv}")
        bad = dict(good)
        bad["k_packed_int4"] = {"shape": (1, 256, 4, 128), "dtype": "uint8"}  # wrong: full D not D/2
        bad["k_packed_protect_bf16"] = {"shape": (1, 256, 4, 128), "dtype": "bfloat16"}  # not compact
        bv = validate_tensor_geometry(geom, bad)
        print(f"[geom] bad inputs  -> {len(bv)} violations (want >=2): {bv}")
        rc = rc or (0 if (not gv and len(bv) >= 2) else 1)
    return rc


if __name__ == "__main__":
    sys.exit(main())
