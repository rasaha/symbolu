"""Provenance manifest: source hashes of BTRR modules + the frozen amendment chain. Torch-free."""
from __future__ import annotations

import hashlib
import pathlib

PROVENANCE = {
    "original_preregistration": "626a897a513eb7e415cde6fbaff10e9e922b8abb",
    "implementation_blocker": "f8dd65c5e734bc1f31eaf100e4069c050d014e8c",
    "amendment_001": "9e6168f93c850acbf2bc134d5226aad1572c1add",
    "amendment_002": "a84cc8eef848e7081764deb894593f7b270f32ba",
}

_MODULES = ("config.py", "tokenizer.py", "schema_ext.py", "serializer.py", "output.py",
            "generator.py", "base_capability.py", "metrics.py", "shortcuts.py", "gates.py",
            "verdict.py", "execution.py", "model.py", "eval.py", "trainer.py")


def source_hashes() -> dict:
    here = pathlib.Path(__file__).resolve().parent
    out = {}
    for name in _MODULES:
        p = here / name
        if p.exists():
            out[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def build_manifest() -> dict:
    return {"provenance": PROVENANCE, "source_hashes": source_hashes(),
            "execution": "BTRR_EXECUTION_NOT_AUTHORIZED"}
