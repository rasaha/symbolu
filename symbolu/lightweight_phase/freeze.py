"""
freeze.py — reproducibility command and freeze-gate generator.

Run as a module to (re)generate the frozen manifest and golden vectors:

    python -m symbolu.lightweight_phase.freeze          # verify against frozen values
    python -m symbolu.lightweight_phase.freeze --write  # regenerate (a version bump)

The manifest records, per stage: source-file SHA-256 hashes, the config hash,
golden input/output/state fingerprints, test count, and environment details.
``tests/test_golden.py`` uses these golden vectors as the freeze gate: any silent
change to frozen forward behavior fails the gate.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Dict

import torch

from .config import PhaseConfig, TransformerConfig
from .phase_core import LightweightPhaseAttention
from .phase_block import LightweightPhaseTransformerLM

PKG_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = PKG_DIR / "frozen_manifest.json"
GOLDEN_PATH = PKG_DIR / "golden_vectors.pt"

# Files owned by each frozen stage (for source hashing).
STAGE_SOURCES = {
    "v1.0-phase-core": ["config.py", "phase_core.py", "invariants.py", "reference_equations.md"],
    "v1.1-streaming": ["streaming.py"],
    "v1.2-decay": ["phase_core.py", "config.py"],
    "v1.3-transformer": ["phase_block.py"],
    "v1.4-local-phase": ["local_window.py", "phase_block.py"],
    "v1.5-binding": ["binding_slots.py"],
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprint(t: torch.Tensor) -> Dict:
    t = t.detach().float().reshape(-1)
    return {
        "shape": list(t.shape),
        "sum": round(t.sum().item(), 6),
        "mean": round(t.mean().item(), 6),
        "absmax": round(t.abs().max().item(), 6),
        "sha256": hashlib.sha256(
            t.numpy().round(5).tobytes()
        ).hexdigest(),
    }


def build_golden() -> Dict:
    """Deterministic golden vectors for the frozen stages."""
    golden = {}

    # Stage 1 — Phase Core (no decay)
    torch.manual_seed(1234)
    cfg1 = PhaseConfig(embed_dim=32, num_heads=4)
    layer1 = LightweightPhaseAttention(cfg1).eval()
    torch.manual_seed(0)
    x1 = torch.randn(2, 6, 32)
    out1 = layer1(x1, return_state=True)
    golden["v1.0-phase-core"] = {
        "config_hash": cfg1.hash,
        "input": _fingerprint(x1),
        "output": _fingerprint(out1.output),
        "state_complex_real": _fingerprint(out1.state.complex_memory.real),
        "state_amplitude": _fingerprint(out1.state.amplitude_sum),
        "raw": {"x1": x1, "out1": out1.output,
                "state_real": out1.state.complex_memory.real,
                "state_amp": out1.state.amplitude_sum},
    }

    # Stage 3 — Decay (learned per head)
    torch.manual_seed(1234)
    cfg3 = PhaseConfig(embed_dim=32, num_heads=4, decay_mode="learned_per_head",
                       gamma_min=0.9, gamma_max=0.999, initial_gamma=0.95)
    layer3 = LightweightPhaseAttention(cfg3).eval()
    torch.manual_seed(0)
    x3 = torch.randn(2, 10, 32)
    out3 = layer3(x3)
    golden["v1.2-decay"] = {
        "config_hash": cfg3.hash,
        "input": _fingerprint(x3),
        "output": _fingerprint(out3),
        "raw": {"x3": x3, "out3": out3},
    }

    # Stage 5 — Phase Transformer LM
    torch.manual_seed(1234)
    tcfg = TransformerConfig(vocab_size=48, phase=PhaseConfig(embed_dim=32, num_heads=4),
                             num_layers=2, max_seq_len=64)
    lm = LightweightPhaseTransformerLM(tcfg).eval()
    ids = torch.arange(2 * 12).reshape(2, 12) % 48
    logits, _ = lm(ids)
    golden["v1.3-transformer"] = {
        "config_hash": tcfg.hash,
        "param_count": lm.num_parameters(),
        "logits": _fingerprint(logits),
        "raw": {"ids": ids, "logits": logits},
    }
    return golden


def build_manifest(golden: Dict, test_count: int | None = None) -> Dict:
    stages = {}
    for stage, files in STAGE_SOURCES.items():
        stages[stage] = {
            "sources": {f: sha256_file(PKG_DIR / f) for f in files},
            "config_hash": golden.get(stage, {}).get("config_hash"),
        }
    manifest = {
        "package": "symbolu.lightweight_phase",
        "canonical": True,
        "reproduce": "python -m symbolu.lightweight_phase.freeze",
        "environment": {
            "python": sys.version.split()[0],
            "torch": torch.__version__,
            "platform": platform.platform(),
        },
        "stages": stages,
        "golden": {k: {kk: vv for kk, vv in v.items() if kk != "raw"} for k, v in golden.items()},
        "test_count": test_count,
    }
    return manifest


# Total tests in symbolu/lightweight_phase/tests (kept in sync with the suite).
TEST_COUNT = 98


def write() -> None:
    golden = build_golden()
    raw = {}
    for stage, g in golden.items():
        for k, v in g.pop("raw", {}).items():
            raw[f"{stage}::{k}"] = v
    torch.save(raw, GOLDEN_PATH)
    manifest = build_manifest(golden, test_count=TEST_COUNT)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"wrote {MANIFEST_PATH} and {GOLDEN_PATH}")


def verify() -> bool:
    if not MANIFEST_PATH.exists():
        print("no manifest — run with --write first")
        return False
    manifest = json.loads(MANIFEST_PATH.read_text())
    golden = build_golden()
    ok = True
    # source hashes
    for stage, files in STAGE_SOURCES.items():
        for f in files:
            cur = sha256_file(PKG_DIR / f)
            rec = manifest["stages"][stage]["sources"].get(f)
            if rec != cur:
                print(f"[source drift] {stage}/{f}: manifest {rec[:12]} != current {cur[:12]}")
                ok = False
    # golden fingerprints
    for stage, g in golden.items():
        for key, val in g.items():
            if key == "raw":
                continue
            if key in ("config_hash", "param_count"):
                if manifest["golden"][stage].get(key) != val:
                    print(f"[golden drift] {stage}/{key}")
                    ok = False
                continue
            if manifest["golden"][stage][key]["sha256"] != val["sha256"]:
                print(f"[golden drift] {stage}/{key}")
                ok = False
    print("FREEZE OK" if ok else "FREEZE DRIFT DETECTED")
    return ok


if __name__ == "__main__":
    if "--write" in sys.argv:
        write()
    else:
        sys.exit(0 if verify() else 1)
