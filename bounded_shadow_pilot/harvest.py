"""Phase 3 - Natural-artifact corpus harvest.

Harvests NATURALLY OCCURRING repository artifacts - module/class/function docstrings, markdown
documentation, and block comments - from REAL product/library code that was NOT authored for any
governance test corpus. Every candidate is routed through the Phase-2 intake protocol; only accepted,
de-identified, use-case-classified artifacts enter the frozen natural corpus.

Honesty guarantees:
  - Excludes every governance-corpus / pilot directory (see _EXCLUDED_ROOTS) so no artifact designed
    for the runtime's own corpora can leak in.
  - Reports the ACTUAL count of eligible natural artifacts. If it is below the target, the corpus
    freeze records NOT_ENOUGH_EVIDENCE rather than fabricating data.
  - Deterministic: sorted by artifact_id, no wall-clock, no randomness. Byte-reproducible.

This module reads repository source read-only and writes only under
`bounded_shadow_pilot/data/natural_pilot_v1/`.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Tuple

from bounded_shadow_pilot import intake_protocol as ip

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "natural_pilot_v1")

TARGET_MIN = 200          # Phase-3 evidence target; below this -> NOT_ENOUGH_EVIDENCE
MIN_CHARS = 80            # quality floor: skip trivial one-liners
MIN_WORDS = 12
MAX_PER_FILE = 6          # no single file may dominate the corpus
MAX_PER_ROOT = 60         # no single source root may dominate the corpus

# Real product/library roots whose natural text was written to document code, NOT for a governance
# corpus. Diverse domains so the corpus is not monoculture.
_SOURCE_ROOTS = [
    "cyber_security", "cloud_controller", "control_plane", "simulator", "sdk",
    "truth_assurance_pipeline", "ndol", "varna_lens", "robotics_reliability_bench",
    "resonant_model", "execution_gate", "execution_proposal_engine", "trading", "trading2",
    "agent_runtime_v2", "acp", "token_compression", "restoration",
]

# Never harvested: the governance corpora, their eval tracks, the frozen pilot, this pilot, tests,
# caches. Guarantees "not designed for its test corpora".
_EXCLUDED_ROOTS = {
    "assertion_governance", "assertion_gate_robustness", "evidence_assurance", "claim_integrity",
    "scope_integrity", "governed_inference_pilot", "customer_shadow_readiness", "bounded_shadow_pilot",
    "model_selection_reconciliation", "model_selection_pilot", "model_selection_experiment",
    "tests", "__pycache__", ".git", "eval_results", "results", "artifacts", "data",
}

_WORD = re.compile(r"\b\w+\b")
_MD_ATX = re.compile(r"^\s*#{1,6}\s+")


@dataclass
class NaturalArtifact:
    artifact_id: str
    source_path: str
    source_kind: str
    use_case: str
    artifact_class: str
    char_len: int
    word_len: int
    text: str            # redacted text (intake output)


def _quality(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < MIN_CHARS:
        return False
    if len(_WORD.findall(t)) < MIN_WORDS:
        return False
    # must contain sentence-like natural language, not pure code/symbols
    letters = sum(c.isalpha() for c in t)
    if letters < 0.5 * len(t):
        return False
    return True


def _iter_docstrings(path: str) -> Iterable[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except (SyntaxError, ValueError):
        return
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            ds = ast.get_docstring(node)
            if ds:
                yield ds


def _iter_markdown(path: str) -> Iterable[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return
    # group into blocks separated by blank lines; drop headings, code fences, tables
    block: List[str] = []
    in_fence = False
    for ln in lines:
        if ln.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not ln.strip():
            if block:
                yield " ".join(block); block = []
            continue
        if _MD_ATX.match(ln) or ln.lstrip().startswith(("|", ">")):
            if block:
                yield " ".join(block); block = []
            continue
        block.append(ln.strip())
    if block:
        yield " ".join(block)


def _iter_block_comments(path: str) -> Iterable[str]:
    """Contiguous runs of full-line `#` comments, joined into a natural block."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return
    run: List[str] = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("#") and not s.startswith("#!"):
            run.append(s.lstrip("#").strip())
        else:
            if len(run) >= 2:
                yield " ".join(run)
            run = []
    if len(run) >= 2:
        yield " ".join(run)


def _iter_root_files(root: str) -> Iterable[str]:
    base = os.path.join(_ROOT, root)
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in _EXCLUDED_ROOTS)
        for fn in sorted(filenames):
            if fn.endswith((".py", ".md")):
                yield os.path.join(dirpath, fn)


def _candidates(path: str) -> Iterable[Tuple[str, str]]:
    if path.endswith(".py"):
        for ds in _iter_docstrings(path):
            yield ("docstring", ds)
        for cm in _iter_block_comments(path):
            yield ("comment", cm)
    elif path.endswith(".md"):
        for md in _iter_markdown(path):
            yield ("doc", md)


def harvest() -> Dict:
    """Harvest, intake-filter, dedup, and bound. Returns a manifest dict (not yet written)."""
    seen_ids: set = set()
    seen_norm: set = set()
    artifacts: List[NaturalArtifact] = []
    rejected = {"provenance": 0, "excluded": 0, "prohibited": 0, "unclassifiable": 0,
                "quality": 0, "duplicate": 0, "other": 0}
    per_root_count: Dict[str, int] = {}
    total_eligible_seen = 0     # accepted-by-intake before per-root/per-file bounding

    for root in _SOURCE_ROOTS:
        per_root = 0
        for path in _iter_root_files(root):
            if per_root >= MAX_PER_ROOT:
                break
            rel = os.path.relpath(path, _ROOT)
            per_file = 0
            for kind, text in _candidates(path):
                if per_root >= MAX_PER_ROOT or per_file >= MAX_PER_FILE:
                    break
                if not _quality(text):
                    rejected["quality"] += 1
                    continue
                rec = ip.intake_natural(text, rel, kind)
                if not rec.accepted:
                    code = rec.reason_codes[0] if rec.reason_codes else ""
                    if "PROVENANCE" in code:
                        rejected["provenance"] += 1
                    elif "EXCLUDED" in code:
                        rejected["excluded"] += 1
                    elif "PROHIBITED" in code:
                        rejected["prohibited"] += 1
                    elif "UNCLASSIFIABLE" in code:
                        rejected["unclassifiable"] += 1
                    else:
                        rejected["other"] += 1
                    continue
                total_eligible_seen += 1
                norm = re.sub(r"\s+", " ", rec.redacted_text.strip().lower())
                if rec.artifact_id in seen_ids or norm in seen_norm:
                    rejected["duplicate"] += 1
                    continue
                seen_ids.add(rec.artifact_id)
                seen_norm.add(norm)
                artifacts.append(NaturalArtifact(
                    artifact_id=rec.artifact_id, source_path=rec.source_path,
                    source_kind=rec.source_kind, use_case=rec.use_case,
                    artifact_class=rec.artifact_class,
                    char_len=rec.char_len, word_len=len(_WORD.findall(rec.redacted_text)),
                    text=rec.redacted_text))
                per_root += 1
                per_file += 1
        if per_root:
            per_root_count[root] = per_root

    artifacts.sort(key=lambda a: a.artifact_id)
    by_kind: Dict[str, int] = {}
    by_use_case: Dict[str, int] = {}
    for a in artifacts:
        by_kind[a.source_kind] = by_kind.get(a.source_kind, 0) + 1
        by_use_case[a.use_case] = by_use_case.get(a.use_case, 0) + 1

    count = len(artifacts)
    corpus_hash = hashlib.sha256(
        json.dumps([asdict(a) for a in artifacts], sort_keys=True).encode()).hexdigest()

    return {
        "corpus_id": "natural_pilot_v1",
        "count": count,
        "target_min": TARGET_MIN,
        "evidence_status": "SUFFICIENT" if count >= TARGET_MIN else "NOT_ENOUGH_EVIDENCE",
        "total_eligible_seen_before_bounding": total_eligible_seen,
        "bounding": {"max_per_file": MAX_PER_FILE, "max_per_root": MAX_PER_ROOT},
        "source_roots": _SOURCE_ROOTS,
        "excluded_roots": sorted(_EXCLUDED_ROOTS),
        "per_root_count": per_root_count,
        "by_source_kind": by_kind,
        "by_use_case": by_use_case,
        "rejected": rejected,
        "quality_floor": {"min_chars": MIN_CHARS, "min_words": MIN_WORDS},
        "corpus_sha256": corpus_hash,
        "artifacts": [asdict(a) for a in artifacts],
    }


def freeze() -> Dict:
    manifest = harvest()
    os.makedirs(_OUT_DIR, exist_ok=True)
    out = os.path.join(_OUT_DIR, "corpus.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return manifest


if __name__ == "__main__":
    m = freeze()
    print(f"natural corpus: count={m['count']} status={m['evidence_status']} "
          f"eligible_seen={m['total_eligible_seen_before_bounding']}")
    print("by_source_kind:", m["by_source_kind"])
    print("by_use_case:", m["by_use_case"])
    print("per_root_count:", m["per_root_count"])
    print("rejected:", m["rejected"])
    print("corpus_sha256:", m["corpus_sha256"][:16])
