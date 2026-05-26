"""Phase TIER5A — Orthogonality gate (G5 three-track + G6 defensive).

Per the TIER5A.1 proposal-of-record (Option 2 + bundle), G5 is
enforced via **three independent tracks**, all checked on every
run:

* **G5a — AST class fingerprint.** Parses
  ``phase5b_backend_install.py`` and extracts the structural
  shape of ``Int4ProtectedAttentionImpl`` +
  ``Int4ProtectedAttentionBackend``: class name, base classes,
  method names, decorator kinds (@staticmethod / @classmethod /
  plain). Compares to a frozen baseline. Catches renames, new
  methods, removed methods, base-class swaps. Ignores docstring
  edits, comment edits, method-body edits.

* **G5b — TIER5A modules AST walk.** Walks the source AST of
  the TIER5A modules (``swap_telemetry.py``,
  ``swap_restore_verifier.py``, ``bench_tier5a_swap_restore.py``)
  and confirms NONE of them reference forbidden symbols outside
  of docstrings. Catches accidental imports / attribute references
  / getattr-string lookups. Mirrors the Phase 4 A13 walk in
  ``test_extended_pinning.py``.

* **G5c — int4_protected Python SHA pin.** SHA-256s every file
  in ``_int4_protected_python_files()`` and compares to a frozen
  baseline. Catches ANY byte-level edit (including docstring,
  comment, whitespace). The broadest net of the three; the
  reviewer's specific request was that the SHA pin closes the
  gap between G5a (one class) and "no modification anywhere in
  the backend."

G6 is the **CTM_plus/CUDA defensive secondary check** at TIER5A.1:

* SHA-pins every ``.cu``, ``.cuh``, ``.cpp``, ``.h``, ``.hpp``
  under ``CTM_plus/CUDA/`` and compares to a frozen baseline.
* The **load-bearing G6 enforcement** (no vllm-flash-attn kernel
  modification at the kernel layer) is deferred to TIER5A.3 GPU
  smoke time, when the forked vllm wheel is actually installed.
  At runtime there: verify ``vllm.vllm_flash_attn.flash_attn_with_int4_kvcache``
  imports + the installed wheel SHA matches an expected value.
* TIER5A.1 retains the in-tree CTM+ kernel SHA pin as defensive
  belt-and-suspenders against changes to OUR OWN kernels
  (mostly the retired Phase 4 + TurboQuant CUDA, which should
  not change).

## Baseline lifecycle

Three baselines live next to this module:

* ``int4_protected_class_fingerprint_baseline.json`` (G5a)
* ``int4_protected_files_baseline.json`` (G5c)
* ``cuda_files_baseline.json`` (G6 defensive)

Each is regenerated **only** with explicit approval, recorded in
the JSON's ``note`` field for audit traceability. The CLI
exposes ``--regenerate-fingerprint``, ``--regenerate-int4-sha``,
``--regenerate-cuda-sha`` flags, each independent so a
one-baseline regen never accidentally regenerates the others.

## Pre-existing known issue (bundle item #3)

``runner_vllm_streaming._read_swap_counters_from_engine`` has a
documented limitation at lines 644-655 of that file: vLLM 0.7.3's
``CpuGpuBlockAllocator.get_and_reset_swaps()`` returns
``(src, dst)`` tuples without direction info, so ``swap_in_blocks``
is always reported as 0 there. TIER5A.1 does NOT fix this
(fixing it would change Phase 3 + 4 G2-relevant numbers).
Documented here so the limitation isn't forgotten; the TIER5A.4
finding doc will list it as an outstanding finding.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- #
# Repo layout — discovered from this file's own location so tests
# work in any clone of the repo.
# ---------------------------------------------------------------- #


_THIS_FILE = Path(__file__).resolve()
_SCRIPTS_DIR = _THIS_FILE.parent                       # ctm_bench/scripts
_CTM_BENCH_DIR = _SCRIPTS_DIR.parent                   # ctm_bench
_BENCH_DIR = _CTM_BENCH_DIR.parent                     # Bench
_CTM_PLUS_DIR = _BENCH_DIR.parent                      # CTM_plus
_REPO_ROOT = _CTM_PLUS_DIR.parent                      # symbolu (repo root)

_KV_POLICY_DIR = _CTM_PLUS_DIR / "KVPolicy" / "kv_policy"
_CUDA_DIR = _CTM_PLUS_DIR / "CUDA"

DEFAULT_FINGERPRINT_BASELINE_PATH = (
    _SCRIPTS_DIR / "int4_protected_class_fingerprint_baseline.json"
)
DEFAULT_INT4_SHA_BASELINE_PATH = (
    _SCRIPTS_DIR / "int4_protected_files_baseline.json"
)
DEFAULT_CUDA_SHA_BASELINE_PATH = (
    _SCRIPTS_DIR / "cuda_files_baseline.json"
)


# ---------------------------------------------------------------- #
# Protected file sets.
# ---------------------------------------------------------------- #


def _int4_protected_python_files() -> List[Path]:
    """G5c scope — int4_protected Python implementation files.

    Backend install, paged writer, streaming quantizer, native
    install probe, per-channel + K-channel helpers, fused-kernel
    Python wrappers. NOT included: calibration scripts (bench
    tooling, not backend); test files.
    """
    candidates = [
        _KV_POLICY_DIR / "phase5b_backend_install.py",
        _KV_POLICY_DIR / "phase5b_4c_paged_writer.py",
        _KV_POLICY_DIR / "phase5b_streaming_quantizer.py",
        _KV_POLICY_DIR / "phase5a_native_install.py",
        _KV_POLICY_DIR / "int4_protected.py",
        _KV_POLICY_DIR / "int4_protected_k_cache.py",
        _KV_POLICY_DIR / "int4_per_channel_kv.py",
        _KV_POLICY_DIR / "int4_fused_attention_kernel.py",
        _KV_POLICY_DIR / "int4_fused_attention_sketch.py",
    ]
    return [p for p in candidates if p.is_file()]


def _cuda_files() -> List[Path]:
    """G6 defensive scope — every ``.cu`` / ``.cuh`` / ``.cpp`` /
    ``.h`` / ``.hpp`` under ``CTM_plus/CUDA/``.

    Per the brief-correction landed at the start of TIER5A.1,
    the load-bearing vllm-flash-attn kernel lives in the forked
    vllm wheel (``vllm.vllm_flash_attn``), not in-tree. This pin
    therefore covers only CTM+'s own kernels; the GPU-smoke
    wheel-level check (TIER5A.3) is the load-bearing G6 gate.
    """
    if not _CUDA_DIR.is_dir():
        return []
    suffixes = {".cu", ".cuh", ".cpp", ".h", ".hpp"}
    out: List[Path] = []
    for p in sorted(_CUDA_DIR.rglob("*")):
        if p.is_file() and p.suffix in suffixes:
            out.append(p)
    return out


# Class names whose AST fingerprint G5a pins.
_PINNED_CLASS_NAMES: frozenset = frozenset({
    "Int4ProtectedAttentionImpl",
    "Int4ProtectedAttentionBackend",
})

# Files searched for the pinned class definitions.
def _class_fingerprint_source_files() -> List[Path]:
    candidates = [
        _KV_POLICY_DIR / "phase5b_backend_install.py",
    ]
    return [p for p in candidates if p.is_file()]


# ---------------------------------------------------------------- #
# SHA helpers
# ---------------------------------------------------------------- #


def sha256_of(path: Path) -> str:
    """Hex SHA-256 of ``path``'s file content (streamed)."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _relpath(p: Path) -> str:
    """Path relative to ``_CTM_PLUS_DIR`` as a POSIX string."""
    try:
        return p.resolve().relative_to(_CTM_PLUS_DIR).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def compute_sha_pin(files: Sequence[Path]) -> Dict[str, str]:
    """Return ``{relpath: sha256}`` for a file set."""
    return {_relpath(p): sha256_of(p) for p in files}


def load_sha_baseline(path: Path) -> Dict[str, str]:
    """Read a SHA pin baseline. Returns ``{}`` when missing."""
    if not path.is_file():
        return {}
    data = json.loads(path.read_text())
    return dict(data.get("files", {}))


def save_sha_baseline(
    baseline: Dict[str, str], *, path: Path, note: str = "",
) -> None:
    """Atomic write-then-rename of a SHA pin baseline JSON."""
    payload = {
        "schema_version": 1,
        "note": note,
        "files": dict(sorted(baseline.items())),
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    tmp.replace(path)


def _verify_sha_pin(
    baseline: Dict[str, str],
    current: Dict[str, str],
    paths_in_scope: Sequence[Path],
) -> Dict[str, Dict[str, str]]:
    """Diff baseline vs current for a defined scope of files.

    Files in ``paths_in_scope`` but missing from baseline →
    ``status=not_in_baseline``. Files in baseline but missing
    from current → ``status=missing``. SHA mismatch →
    ``status=modified``.
    """
    in_scope_relpaths = {_relpath(p) for p in paths_in_scope}
    violations: Dict[str, Dict[str, str]] = {}
    for relpath in sorted(in_scope_relpaths):
        expected = baseline.get(relpath)
        actual = current.get(relpath)
        if expected is None:
            violations[relpath] = {
                "status": "not_in_baseline",
                "expected": "",
                "actual": actual or "",
            }
            continue
        if actual is None:
            violations[relpath] = {
                "status": "missing",
                "expected": expected,
                "actual": "",
            }
            continue
        if actual != expected:
            violations[relpath] = {
                "status": "modified",
                "expected": expected,
                "actual": actual,
            }
    return violations


# ---------------------------------------------------------------- #
# G5a — AST class fingerprint
# ---------------------------------------------------------------- #


def _decorator_kind(node: ast.AST) -> str:
    """Identify which built-in decorator (if any) a FunctionDef
    has applied. Returns ``"staticmethod"``, ``"classmethod"``,
    ``"property"``, or ``"plain"``. We only care about the
    method's binding kind, not arbitrary decorators."""
    for dec in getattr(node, "decorator_list", []) or []:
        # ``@staticmethod`` parses as ``ast.Name(id="staticmethod")``.
        if isinstance(dec, ast.Name):
            if dec.id == "staticmethod":
                return "staticmethod"
            if dec.id == "classmethod":
                return "classmethod"
            if dec.id == "property":
                return "property"
        # ``@x.property`` etc. is ignored; we only key on the bare
        # built-in decorators by intent.
    return "plain"


def _bases_to_strs(class_node: ast.ClassDef) -> List[str]:
    """Render a ClassDef's base-class list as deterministic strings.

    Handles ``Name`` (``FlashAttentionImpl``) and ``Attribute``
    (``module.Class``). Anything more exotic falls through to
    ``ast.dump`` so the fingerprint still records SOMETHING (any
    change to the base-list still trips the check)."""
    out: List[str] = []
    for b in class_node.bases:
        if isinstance(b, ast.Name):
            out.append(b.id)
        elif isinstance(b, ast.Attribute):
            parts: List[str] = [b.attr]
            cur: Any = b.value
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            out.append(".".join(reversed(parts)))
        else:
            out.append(ast.dump(b))
    return out


def _class_fingerprint(class_node: ast.ClassDef) -> Dict[str, Any]:
    """Structural fingerprint of one ClassDef.

    Captured: class name; base classes (rendered as strings,
    order preserved); method list (name + decorator kind, sorted
    by name). Method signatures and bodies are NOT captured —
    the chosen Option for G5 strictness is "class shape + method
    names + base classes", which deliberately ignores body /
    param-list edits so partner-credible internal refactors
    (renaming an internal-only argument; tightening a body)
    don't false-positive the gate. Renames, additions, removals,
    base-class swaps DO trip the gate.
    """
    methods: List[Dict[str, str]] = []
    for stmt in class_node.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append({
                "name": stmt.name,
                "kind": _decorator_kind(stmt),
                "async": isinstance(stmt, ast.AsyncFunctionDef),
            })
    # Sort by name for stable comparison across cosmetic reorders.
    methods.sort(key=lambda m: m["name"])
    return {
        "class_name": class_node.name,
        "bases": _bases_to_strs(class_node),
        "methods": methods,
    }


def compute_class_fingerprints(
    files: Optional[Sequence[Path]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Parse the source files and return
    ``{relpath: [fingerprint, ...]}`` for every ClassDef whose
    name matches ``_PINNED_CLASS_NAMES``.

    Because the protected classes may be defined inside
    conditional ``if/else`` blocks (a fallback stub when vLLM
    isn't importable), we walk the FULL AST, not just module-
    level body. Each matching ClassDef contributes one
    fingerprint entry; the list preserves source order so a
    reorganisation that moves the real class after the stub
    still trips the check.
    """
    paths = (
        list(files)
        if files is not None
        else _class_fingerprint_source_files()
    )
    out: Dict[str, List[Dict[str, Any]]] = {}
    for p in paths:
        src = p.read_text()
        tree = ast.parse(src)
        prints: List[Dict[str, Any]] = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ClassDef)
                and node.name in _PINNED_CLASS_NAMES
            ):
                prints.append(_class_fingerprint(node))
        out[_relpath(p)] = prints
    return out


def load_fingerprint_baseline(
    path: Path,
) -> Dict[str, List[Dict[str, Any]]]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text())
    return dict(data.get("classes", {}))


def save_fingerprint_baseline(
    baseline: Dict[str, List[Dict[str, Any]]], *, path: Path,
    note: str = "",
) -> None:
    payload = {
        "schema_version": 1,
        "note": note,
        "classes": dict(sorted(baseline.items())),
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    tmp.replace(path)


def _verify_fingerprint(
    baseline: Dict[str, List[Dict[str, Any]]],
    current: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Dict[str, Any]]:
    """Diff fingerprints by relpath.

    Files in baseline but missing from current → ``missing``.
    Files in current but missing from baseline → ``not_in_baseline``.
    Same file with differing fingerprint list →
    ``modified`` with ``expected`` / ``actual`` deltas.
    """
    violations: Dict[str, Dict[str, Any]] = {}
    all_relpaths = set(baseline) | set(current)
    for relpath in sorted(all_relpaths):
        expected = baseline.get(relpath)
        actual = current.get(relpath)
        if expected is None:
            violations[relpath] = {
                "status": "not_in_baseline",
                "expected": None,
                "actual": actual,
            }
            continue
        if actual is None:
            violations[relpath] = {
                "status": "missing",
                "expected": expected,
                "actual": None,
            }
            continue
        if expected != actual:
            violations[relpath] = {
                "status": "modified",
                "expected": expected,
                "actual": actual,
            }
    return violations


# ---------------------------------------------------------------- #
# G5b — TIER5A modules AST walk
# ---------------------------------------------------------------- #


_FORBIDDEN_SYMBOLS: frozenset = frozenset({
    "Int4ProtectedAttentionImpl",
    "Int4ProtectedAttentionBackend",
    "Int4ProtectedLLM",
    "phase5b_backend_install",
    "phase5b_4c_paged_writer",
    "phase5b_streaming_quantizer",
    "phase5a_native_install",
    "int4_protected_k_cache",
    "int4_fused_attention_kernel",
    "int4_fused_attention_sketch",
    "int4_per_channel_kv",
    "vllm_flash_attn_int4",
    "install_int4_protected_backend",
    "flash_attn_with_int4_kvcache",
})


def _tier5a_module_paths() -> List[Path]:
    """Modules whose AST gets walked for G5b.

    ``tier5a_orthogonality_gate.py`` (this file) is excluded by
    design: it must enumerate ``_FORBIDDEN_SYMBOLS`` to do its
    job, which would tautologically violate G5b. Any edit to
    this file is caught by code review + by the SHA pin if it
    happens to live in a pinned location.
    """
    candidates = [
        _KV_POLICY_DIR / "swap_telemetry.py",
        _CTM_BENCH_DIR / "swap_restore_verifier.py",
        _SCRIPTS_DIR / "bench_tier5a_swap_restore.py",
    ]
    return [p for p in candidates if p.is_file()]


def _ast_executable_references(src: str) -> set:
    """Collect identifier references from executable AST nodes
    (Name / Attribute / ImportFrom / Import) and EXACT-match
    string constants outside of docstrings. Substring matches
    inside long string constants are intentionally NOT collected
    — docstrings legitimately mention the orthogonality contract,
    and a substring filter would false-positive on documentation.

    Exact-match string constants ARE collected because a
    ``getattr(x, "Int4ProtectedAttentionImpl")`` is a real
    executable reference even though it's stringly-typed.
    """
    tree = ast.parse(src)
    refs: set = set()

    # Identify docstring AST nodes so we can exclude them from
    # Constant-string collection.
    docstring_nodes: set = set()
    if (
        isinstance(tree, ast.Module)
        and tree.body
        and isinstance(tree.body[0], ast.Expr)
        and isinstance(tree.body[0].value, ast.Constant)
        and isinstance(tree.body[0].value.value, str)
    ):
        docstring_nodes.add(id(tree.body[0].value))
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstring_nodes.add(id(body[0].value))

    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            refs.add(node.id)
        elif isinstance(node, ast.Attribute):
            refs.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for piece in node.module.split("."):
                    refs.add(piece)
            for alias in node.names:
                refs.add(alias.name)
                for piece in alias.name.split("."):
                    refs.add(piece)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                for piece in alias.name.split("."):
                    refs.add(piece)
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstring_nodes
        ):
            # Only collect EXACT short string constants — they
            # represent real executable references via getattr /
            # similar dynamic lookup. Long strings (full docstring
            # text accidentally caught here, etc.) won't match a
            # forbidden symbol via exact equality.
            refs.add(node.value)
    return refs


def ast_gate_violations(
    files: Optional[Sequence[Path]] = None,
) -> Dict[str, List[str]]:
    """Run G5b. Returns ``{relpath: [forbidden_symbols_found]}``.
    Empty dict means the gate passed."""
    paths = (
        list(files) if files is not None else _tier5a_module_paths()
    )
    violations: Dict[str, List[str]] = {}
    for p in paths:
        src = p.read_text()
        refs = _ast_executable_references(src)
        found = sorted(_FORBIDDEN_SYMBOLS & refs)
        if found:
            violations[_relpath(p)] = found
    return violations


# ---------------------------------------------------------------- #
# Gate report + entry point
# ---------------------------------------------------------------- #


@dataclass
class GateReport:
    """G5 three-track + G6 defensive verdict + supporting evidence."""

    passed: bool

    g5a_fingerprint_passed: bool
    g5b_ast_passed: bool
    g5c_sha_passed: bool
    g6_passed: bool

    fingerprint_baseline_path: str
    int4_sha_baseline_path: str
    cuda_sha_baseline_path: str

    fingerprint_baseline_missing: bool
    int4_sha_baseline_missing: bool
    cuda_sha_baseline_missing: bool

    g5a_violations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    g5b_violations: Dict[str, List[str]] = field(default_factory=dict)
    g5c_violations: Dict[str, Dict[str, str]] = field(default_factory=dict)
    g6_violations: Dict[str, Dict[str, str]] = field(default_factory=dict)

    pinned_class_count: int = 0
    int4_python_file_count: int = 0
    cuda_file_count: int = 0
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def verify_orthogonality(
    *,
    fingerprint_baseline_path: Path = DEFAULT_FINGERPRINT_BASELINE_PATH,
    int4_sha_baseline_path: Path = DEFAULT_INT4_SHA_BASELINE_PATH,
    cuda_sha_baseline_path: Path = DEFAULT_CUDA_SHA_BASELINE_PATH,
) -> GateReport:
    """Run G5 (three tracks) + G6 (defensive SHA). Returns a
    populated GateReport. Does not raise on failure — the caller
    decides what to do with the verdict.
    """
    # G5a — class fingerprint.
    fp_baseline = load_fingerprint_baseline(fingerprint_baseline_path)
    fp_baseline_missing = not fp_baseline
    fp_current = compute_class_fingerprints()
    g5a_violations = (
        _verify_fingerprint(fp_baseline, fp_current)
        if not fp_baseline_missing else {}
    )

    # G5b — TIER5A modules AST walk (no baseline needed).
    g5b_violations = ast_gate_violations()

    # G5c — int4_protected python SHA pin.
    int4_paths = _int4_protected_python_files()
    int4_baseline = load_sha_baseline(int4_sha_baseline_path)
    int4_baseline_missing = not int4_baseline
    int4_current = compute_sha_pin(int4_paths)
    g5c_violations = (
        _verify_sha_pin(int4_baseline, int4_current, int4_paths)
        if not int4_baseline_missing else {}
    )

    # G6 — CTM_plus/CUDA defensive SHA pin.
    cuda_paths = _cuda_files()
    cuda_baseline = load_sha_baseline(cuda_sha_baseline_path)
    cuda_baseline_missing = not cuda_baseline
    cuda_current = compute_sha_pin(cuda_paths)
    g6_violations = (
        _verify_sha_pin(cuda_baseline, cuda_current, cuda_paths)
        if not cuda_baseline_missing else {}
    )

    g5a_passed = not fp_baseline_missing and not g5a_violations
    g5b_passed = not g5b_violations
    g5c_passed = not int4_baseline_missing and not g5c_violations
    g6_passed = not cuda_baseline_missing and not g6_violations

    pinned_class_count = sum(len(v) for v in fp_current.values())

    overall_passed = g5a_passed and g5b_passed and g5c_passed and g6_passed

    parts: List[str] = []
    parts.append(
        f"g5a={'pass' if g5a_passed else 'FAIL'} "
        f"({pinned_class_count} classes)"
    )
    parts.append(
        f"g5b={'pass' if g5b_passed else 'FAIL'} "
        f"({len(g5b_violations)} violations)"
    )
    parts.append(
        f"g5c={'pass' if g5c_passed else 'FAIL'} "
        f"({len(int4_paths)} files)"
    )
    parts.append(
        f"g6={'pass' if g6_passed else 'FAIL'} "
        f"({len(cuda_paths)} files)"
    )
    if (
        fp_baseline_missing
        or int4_baseline_missing
        or cuda_baseline_missing
    ):
        missing = []
        if fp_baseline_missing:
            missing.append("g5a")
        if int4_baseline_missing:
            missing.append("g5c")
        if cuda_baseline_missing:
            missing.append("g6")
        parts.append(f"baselines_missing={','.join(missing)}")
    summary = "; ".join(parts)

    return GateReport(
        passed=overall_passed,
        g5a_fingerprint_passed=g5a_passed,
        g5b_ast_passed=g5b_passed,
        g5c_sha_passed=g5c_passed,
        g6_passed=g6_passed,
        fingerprint_baseline_path=str(fingerprint_baseline_path),
        int4_sha_baseline_path=str(int4_sha_baseline_path),
        cuda_sha_baseline_path=str(cuda_sha_baseline_path),
        fingerprint_baseline_missing=fp_baseline_missing,
        int4_sha_baseline_missing=int4_baseline_missing,
        cuda_sha_baseline_missing=cuda_baseline_missing,
        g5a_violations=g5a_violations,
        g5b_violations=g5b_violations,
        g5c_violations=g5c_violations,
        g6_violations=g6_violations,
        pinned_class_count=pinned_class_count,
        int4_python_file_count=len(int4_paths),
        cuda_file_count=len(cuda_paths),
        summary=summary,
    )


# ---------------------------------------------------------------- #
# CLI
# ---------------------------------------------------------------- #


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="tier5a_orthogonality_gate",
        description=(
            "Phase TIER5A orthogonality gate. G5 three-track + G6 "
            "defensive. Verifies the int4_protected backend has "
            "not been modified on this branch."
        ),
    )
    p.add_argument(
        "--fingerprint-baseline-path", type=Path,
        default=DEFAULT_FINGERPRINT_BASELINE_PATH,
    )
    p.add_argument(
        "--int4-sha-baseline-path", type=Path,
        default=DEFAULT_INT4_SHA_BASELINE_PATH,
    )
    p.add_argument(
        "--cuda-sha-baseline-path", type=Path,
        default=DEFAULT_CUDA_SHA_BASELINE_PATH,
    )
    p.add_argument(
        "--regenerate-fingerprint", action="store_true",
        help="Recompute the G5a class-fingerprint baseline. ONLY "
             "use after explicit approval of an int4_protected "
             "class-shape change.",
    )
    p.add_argument(
        "--regenerate-int4-sha", action="store_true",
        help="Recompute the G5c int4_protected python SHA "
             "baseline. ONLY use after explicit approval of an "
             "int4_protected file edit.",
    )
    p.add_argument(
        "--regenerate-cuda-sha", action="store_true",
        help="Recompute the G6 CUDA-fork defensive SHA baseline. "
             "ONLY use after explicit approval of an in-tree "
             "kernel edit.",
    )
    p.add_argument(
        "--regen-note", type=str, default="",
        help="Audit note recorded in the regenerated baseline.",
    )
    p.add_argument(
        "--json", action="store_true",
        help="Emit the GateReport as JSON instead of human prose. "
             "Exit code still reflects the verdict.",
    )
    return p.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)

    if args.regenerate_fingerprint:
        fp = compute_class_fingerprints()
        save_fingerprint_baseline(
            fp, path=args.fingerprint_baseline_path,
            note=args.regen_note or "regenerated via CLI",
        )
        print(
            f"G5a fingerprint baseline regenerated at "
            f"{args.fingerprint_baseline_path} "
            f"({sum(len(v) for v in fp.values())} classes pinned)"
        )

    if args.regenerate_int4_sha:
        pin = compute_sha_pin(_int4_protected_python_files())
        save_sha_baseline(
            pin, path=args.int4_sha_baseline_path,
            note=args.regen_note or "regenerated via CLI",
        )
        print(
            f"G5c int4_protected SHA baseline regenerated at "
            f"{args.int4_sha_baseline_path} ({len(pin)} files)"
        )

    if args.regenerate_cuda_sha:
        pin = compute_sha_pin(_cuda_files())
        save_sha_baseline(
            pin, path=args.cuda_sha_baseline_path,
            note=args.regen_note or "regenerated via CLI",
        )
        print(
            f"G6 CUDA defensive SHA baseline regenerated at "
            f"{args.cuda_sha_baseline_path} ({len(pin)} files)"
        )

    if (
        args.regenerate_fingerprint
        or args.regenerate_int4_sha
        or args.regenerate_cuda_sha
    ):
        return 0

    report = verify_orthogonality(
        fingerprint_baseline_path=args.fingerprint_baseline_path,
        int4_sha_baseline_path=args.int4_sha_baseline_path,
        cuda_sha_baseline_path=args.cuda_sha_baseline_path,
    )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"verdict: {'PASS' if report.passed else 'FAIL'}")
        print(f"summary: {report.summary}")
        print(
            f"  g5a (class fingerprint): "
            f"{'pass' if report.g5a_fingerprint_passed else 'fail'} "
            f"({len(report.g5a_violations)} violations)"
        )
        print(
            f"  g5b (tier5a ast):        "
            f"{'pass' if report.g5b_ast_passed else 'fail'} "
            f"({len(report.g5b_violations)} violations)"
        )
        print(
            f"  g5c (int4 python sha):   "
            f"{'pass' if report.g5c_sha_passed else 'fail'} "
            f"({len(report.g5c_violations)} violations)"
        )
        print(
            f"  g6  (cuda fork sha):     "
            f"{'pass' if report.g6_passed else 'fail'} "
            f"({len(report.g6_violations)} violations)"
        )
        for label, vio in (
            ("g5a", report.g5a_violations),
            ("g5b", report.g5b_violations),
            ("g5c", report.g5c_violations),
            ("g6", report.g6_violations),
        ):
            if vio:
                print(f"  {label} violations:")
                for path, info in sorted(vio.items()):
                    if isinstance(info, dict):
                        print(f"    {path}: {info.get('status', info)}")
                    else:
                        print(f"    {path}: {info}")

    return 0 if report.passed else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
