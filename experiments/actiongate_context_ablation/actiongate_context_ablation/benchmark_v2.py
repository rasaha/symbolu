"""V2 benchmark fingerprint manifest.

Produces a self-describing V2 fingerprint from independently-hashed components:
task-suite version, prompt hash, scorer hash, normalization-rules hash, corpus hash,
compressor hash, ActionGate/policy hash, and the V2 source-file hashes. Any change to a
component changes its sub-hash and therefore the full V2 fingerprint — the integrity
tests enforce this, and that the V2 fingerprint can NEVER equal the V1 fingerprint
(the component set is disjoint: V2 hashes the V2 task/scorer/normalization surface,
which V1 does not include, and stamps a distinct benchmark id + task-suite version).
"""

from __future__ import annotations

import hashlib
import json
import pathlib

from . import llm_tasks_v2 as T
from . import scoring_v2 as S
from . import normalize_v2 as NZ
from . import real_llm_bench_v2 as R2

_PKG = pathlib.Path(__file__).resolve().parent

# V2 source surface (the files that define V2 semantics). Disjoint from V1's frozen set.
_V2_FILES = ["llm_tasks_v2.py", "scoring_v2.py", "normalize_v2.py",
             "real_llm_bench_v2.py", "benchmark_v2.py"]


def _sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _prompt_hash() -> str:
    return "sha256:" + hashlib.sha256(R2.SYSTEM_V2.encode("utf-8")).hexdigest()


def _corpus_hash() -> str:
    from .corpus import manifest as CM
    return CM.build_manifest()["manifest_hash"]


def _compressor_hash() -> str:
    p = _PKG / "compressor.py"
    return _sha256_file(p) if p.exists() else "MISSING"


def _policy_id() -> str:
    from . import adapter
    try:
        sp = adapter.default_signed_policy()
        return f"{adapter.REF_VERSION}:{sp.get('policy_hash', '')[:16]}"
    except Exception as exc:  # pragma: no cover - env dependent
        return f"ERR:{exc.__class__.__name__}"


def components() -> dict:
    return {
        "benchmark_id": R2.BENCHMARK_ID,
        "task_suite_version": T.TASK_SUITE_VERSION,
        "prompt_hash": _prompt_hash(),
        "scorer_hash": S.scorer_hash(),
        "normalization_hash": NZ.rules_hash(),
        "corpus_hash": _corpus_hash(),
        "compressor_hash": _compressor_hash(),
        "actiongate_policy": _policy_id(),
        "v2_source_hashes": {rel: _sha256_file(_PKG / rel) for rel in _V2_FILES},
        "budgets": R2.BUDGETS,
        "methods": R2.METHODS,
        "task_types": T.TASK_TYPES,
    }


def fingerprint() -> dict:
    comp = components()
    digest = hashlib.sha256(json.dumps(comp, sort_keys=True).encode()).hexdigest()
    return {"benchmark_id": R2.BENCHMARK_ID, "fingerprint": "sha256:" + digest,
            "policy": comp["actiongate_policy"], "components": comp}
