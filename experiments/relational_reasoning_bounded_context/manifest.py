"""Provenance manifest + replay binding (drift detection). Torch-free.

Binds the full chain a future authorized replay must reproduce: protocol/amendment provenance, config
digest, tokenizer vocabulary digest, schema/serializer version, seed/phase, and (mock in tests) checkpoint
/prediction/metric/verdict digests. verify_replay_binding() DETECTS drift rather than regenerating.
"""
from __future__ import annotations

import hashlib
import json
import pathlib

from . import config as C
from .tokenizer import LEXEMES

SCHEMA_SERIALIZER_VERSION = "btrr-schema/serializer/v1"

PROVENANCE = {
    "original_preregistration": "626a897a513eb7e415cde6fbaff10e9e922b8abb",
    "implementation_blocker": "f8dd65c5e734bc1f31eaf100e4069c050d014e8c",
    "amendment_001": "9e6168f93c850acbf2bc134d5226aad1572c1add",
    "amendment_002": "a84cc8eef848e7081764deb894593f7b270f32ba",
}

_MODULES = ("config.py", "tokenizer.py", "schema_ext.py", "serializer.py", "output.py",
            "generator.py", "base_capability.py", "metrics.py", "shortcuts.py", "gates.py",
            "verdict.py", "execution.py", "model.py", "eval.py", "trainer.py", "driver.py", "replay.py")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_hashes() -> dict:
    here = pathlib.Path(__file__).resolve().parent
    return {n: hashlib.sha256((here / n).read_bytes()).hexdigest()
            for n in _MODULES if (here / n).exists()}


def config_digest() -> str:
    payload = {
        "vocab_size": C.VOCAB_SIZE, "input_token_limit": C.INPUT_TOKEN_LIMIT,
        "output_token_limit": C.OUTPUT_TOKEN_LIMIT, "max_seq_len": C.MAX_SEQ_LEN,
        "expected_total_params": C.EXPECTED_TOTAL_PARAMS,
        "expected_reasoning_block_params": C.EXPECTED_REASONING_BLOCK_PARAMS,
        "caps": dict(C.CAPS), "numeric_gates": dict(C.NUMERIC_GATES),
        "reserved": {"smoke": sorted(C.SMOKE_SEEDS), "dev": sorted(C.DEVELOPMENT_SEEDS),
                     "final": sorted(C.FINAL_SEEDS)},
    }
    return _sha(json.dumps(payload, sort_keys=True))


def tokenizer_vocab_digest() -> str:
    return _sha(json.dumps(list(LEXEMES)))


def build_manifest() -> dict:
    return {
        "provenance": PROVENANCE,
        "schema_serializer_version": SCHEMA_SERIALIZER_VERSION,
        "config_digest": config_digest(),
        "tokenizer_vocab_digest": tokenizer_vocab_digest(),
        "source_hashes": source_hashes(),
        "execution": "BTRR_EXECUTION_NOT_AUTHORIZED",
    }


def build_replay_binding(*, seed: int, phase: str, checkpoint_digest: str,
                         prediction_digest: str, metric_digest: str, verdict_digest: str) -> dict:
    """Record everything a future authorized replay must bit-for-bit reproduce."""
    return {
        "provenance": PROVENANCE,
        "schema_serializer_version": SCHEMA_SERIALIZER_VERSION,
        "config_digest": config_digest(),
        "tokenizer_vocab_digest": tokenizer_vocab_digest(),
        "seed": int(seed),
        "phase": phase,
        "checkpoint_digest": checkpoint_digest,
        "prediction_digest": prediction_digest,
        "metric_digest": metric_digest,
        "verdict_digest": verdict_digest,
    }


_BIND_KEYS = ("provenance", "schema_serializer_version", "config_digest", "tokenizer_vocab_digest",
              "seed", "phase", "checkpoint_digest", "prediction_digest", "metric_digest",
              "verdict_digest")


def verify_replay_binding(recorded: dict, current: dict) -> dict:
    """Detect drift between a recorded binding and a fresh one. Returns per-field match + overall bool."""
    mismatches = {k: (recorded.get(k), current.get(k)) for k in _BIND_KEYS
                  if recorded.get(k) != current.get(k)}
    return {"matches": not mismatches, "mismatched_fields": sorted(mismatches.keys()),
            "detail": mismatches}
