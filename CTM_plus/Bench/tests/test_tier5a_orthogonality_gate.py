"""Phase TIER5A.1 CPU tests for the orthogonality gate.

Covers the G5 three-track + G6 defensive enforcement:

* G5a — AST class fingerprint of Int4ProtectedAttentionImpl +
  Int4ProtectedAttentionBackend passes against the baseline that
  was generated at TIER5A.1 design freeze.
* G5a — fingerprint computer captures class name, base classes,
  method names + kinds; ignores method bodies.
* G5b — TIER5A modules don't reference forbidden symbols
  (executable references — docstring mentions are allowed).
* G5b — synthetic forbidden reference IS detected.
* G5c — int4_protected python file SHA pin passes against the
  baseline; synthetic byte-level modification fails.
* G6 — CUDA defensive SHA pin passes.
* Combined verdict aggregation in GateReport.
* Baseline missing → corresponding sub-track reports failure
  with ``baseline_missing`` flag set.
* Independent baseline regenerator paths don't cross-affect.

The tests use the **real** baselines committed at TIER5A.1
freeze. The test for "synthetic modification" creates a
temporary baseline that intentionally differs and verifies the
gate detects it; it does NOT modify the committed baselines.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ctm_bench.scripts.tier5a_orthogonality_gate import (
    DEFAULT_CUDA_SHA_BASELINE_PATH,
    DEFAULT_FINGERPRINT_BASELINE_PATH,
    DEFAULT_INT4_SHA_BASELINE_PATH,
    _ast_executable_references,
    _class_fingerprint,
    _FORBIDDEN_SYMBOLS,
    _PINNED_CLASS_NAMES,
    _cuda_files,
    _int4_protected_python_files,
    _tier5a_module_paths,
    ast_gate_violations,
    compute_class_fingerprints,
    compute_sha_pin,
    load_fingerprint_baseline,
    load_sha_baseline,
    save_fingerprint_baseline,
    save_sha_baseline,
    sha256_of,
    verify_orthogonality,
)


# ---------------------------------------------------------------- #
# Top-of-tree: the committed baselines should pass against the
# current source tree. This is the load-bearing "TIER5A.1 freeze"
# regression check.
# ---------------------------------------------------------------- #


def test_orthogonality_gate_passes_on_clean_tree():
    """Default invocation (all three committed baselines) should
    PASS at TIER5A.1 freeze."""
    report = verify_orthogonality()
    assert report.passed is True, (
        f"orthogonality gate failed unexpectedly: {report.summary}; "
        f"g5a={report.g5a_violations}; "
        f"g5b={report.g5b_violations}; "
        f"g5c={report.g5c_violations}; "
        f"g6={report.g6_violations}"
    )
    assert report.g5a_fingerprint_passed
    assert report.g5b_ast_passed
    assert report.g5c_sha_passed
    assert report.g6_passed


def test_baseline_file_counts_are_sensible():
    """Sanity: each baseline pins more than zero files."""
    fp = load_fingerprint_baseline(DEFAULT_FINGERPRINT_BASELINE_PATH)
    int4 = load_sha_baseline(DEFAULT_INT4_SHA_BASELINE_PATH)
    cuda = load_sha_baseline(DEFAULT_CUDA_SHA_BASELINE_PATH)
    assert sum(len(v) for v in fp.values()) >= 2   # at least the
    # two pinned class names
    assert len(int4) >= 5    # at least 5 int4_protected files
    assert len(cuda) >= 1


def test_pinned_class_names_present_in_baseline():
    fp = load_fingerprint_baseline(DEFAULT_FINGERPRINT_BASELINE_PATH)
    found_names: set = set()
    for class_list in fp.values():
        for c in class_list:
            found_names.add(c["class_name"])
    for expected in _PINNED_CLASS_NAMES:
        assert expected in found_names, (
            f"expected class {expected} not in fingerprint baseline"
        )


# ---------------------------------------------------------------- #
# G5a — class fingerprint computation
# ---------------------------------------------------------------- #


def _first_classdef(src: str):
    """Parse ``src`` and return its first ClassDef AST node. Used
    by the unit tests below so they don't need to use class names
    from the production pinned set."""
    import ast as _ast
    tree = _ast.parse(src)
    for node in _ast.walk(tree):
        if isinstance(node, _ast.ClassDef):
            return node
    raise AssertionError("no ClassDef found in source")


def test_class_fingerprint_captures_name_bases_methods():
    src = '''
class Sample(BaseA, mod.BaseB):
    """Docstring should NOT affect the fingerprint."""

    a_attr = 1     # ignored — not a method

    def method_one(self):
        # body is ignored
        return 1

    @staticmethod
    def static_two():
        pass

    @classmethod
    def class_three(cls):
        pass

    @property
    def prop_four(self):
        return self.a_attr
'''
    fp = _class_fingerprint(_first_classdef(src))
    assert fp["class_name"] == "Sample"
    assert fp["bases"] == ["BaseA", "mod.BaseB"]
    names = [m["name"] for m in fp["methods"]]
    assert sorted(names) == [
        "class_three", "method_one", "prop_four", "static_two",
    ]
    kinds = {m["name"]: m["kind"] for m in fp["methods"]}
    assert kinds["method_one"] == "plain"
    assert kinds["static_two"] == "staticmethod"
    assert kinds["class_three"] == "classmethod"
    assert kinds["prop_four"] == "property"


def test_class_fingerprint_ignores_method_body_changes():
    """Body edits MUST NOT change the fingerprint — that's the
    G5 strictness contract we chose."""
    src_a = '''
class Sample:
    def m(self):
        return 1
'''
    src_b = '''
class Sample:
    def m(self):
        return 2       # body different; signature same
'''
    fp_a = _class_fingerprint(_first_classdef(src_a))
    fp_b = _class_fingerprint(_first_classdef(src_b))
    assert fp_a == fp_b


def test_class_fingerprint_detects_method_rename():
    src_a = '''
class Sample:
    def alpha(self): pass
'''
    src_b = '''
class Sample:
    def beta(self): pass      # renamed!
'''
    fp_a = _class_fingerprint(_first_classdef(src_a))
    fp_b = _class_fingerprint(_first_classdef(src_b))
    assert fp_a != fp_b


def test_class_fingerprint_detects_base_class_swap():
    src_a = "class Sample(FlashAttentionImpl): pass\n"
    src_b = "class Sample(SomeOtherImpl): pass\n"
    fp_a = _class_fingerprint(_first_classdef(src_a))
    fp_b = _class_fingerprint(_first_classdef(src_b))
    assert fp_a != fp_b


def test_class_fingerprint_detects_added_method():
    """Adding a method changes the fingerprint."""
    src_a = "class Sample:\n    def m(self): pass\n"
    src_b = "class Sample:\n    def m(self): pass\n    def n(self): pass\n"
    fp_a = _class_fingerprint(_first_classdef(src_a))
    fp_b = _class_fingerprint(_first_classdef(src_b))
    assert fp_a != fp_b


def test_class_fingerprint_detects_decorator_change():
    """Promoting an instance method to staticmethod changes the
    method 'kind' and therefore the fingerprint."""
    src_a = "class Sample:\n    def m(self): pass\n"
    src_b = "class Sample:\n    @staticmethod\n    def m(): pass\n"
    fp_a = _class_fingerprint(_first_classdef(src_a))
    fp_b = _class_fingerprint(_first_classdef(src_b))
    assert fp_a != fp_b


def test_class_fingerprint_handles_nested_class_defs(tmp_path):
    """Pinned classes inside if/else blocks (the real
    phase5b_backend_install pattern) must both be captured."""
    src = '''
import sys

if True:
    class Int4ProtectedAttentionImpl:
        def real_method(self): pass
else:
    class Int4ProtectedAttentionImpl:
        def stub(self): pass
'''
    f = tmp_path / "x.py"
    f.write_text(src)
    out = compute_class_fingerprints([f])
    classes = list(out.values())[0]
    # Both copies captured.
    assert len(classes) == 2
    names_by_position = [c["class_name"] for c in classes]
    assert names_by_position == [
        "Int4ProtectedAttentionImpl", "Int4ProtectedAttentionImpl",
    ]


# ---------------------------------------------------------------- #
# G5b — TIER5A modules AST walk
# ---------------------------------------------------------------- #


def test_tier5a_modules_are_clean_today():
    """The TIER5A modules under source control today must not
    reference forbidden symbols. Same gate test_extended_pinning
    has for Phase 4 A13."""
    vio = ast_gate_violations()
    assert vio == {}, (
        f"tier5a modules reference forbidden symbols: {vio}"
    )


def test_ast_walk_detects_synthetic_forbidden_import(tmp_path):
    src = '''
from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl

def x():
    return Int4ProtectedAttentionImpl()
'''
    f = tmp_path / "bad.py"
    f.write_text(src)
    vio = ast_gate_violations([f])
    assert vio, "expected forbidden-symbol detection"
    found = list(vio.values())[0]
    assert "Int4ProtectedAttentionImpl" in found
    assert "phase5b_backend_install" in found


def test_ast_walk_allows_docstring_mention_of_forbidden_symbols(tmp_path):
    """Docstring text mentioning a forbidden symbol is allowed —
    every TIER5A module mentions the orthogonality contract in
    its module docstring."""
    src = '''"""Documentation that says we DO NOT touch
Int4ProtectedAttentionImpl or phase5b_backend_install in this
module — the orthogonality contract."""

def hello():
    """Same constraint applies to phase5b_4c_paged_writer."""
    return None
'''
    f = tmp_path / "doc_only.py"
    f.write_text(src)
    vio = ast_gate_violations([f])
    assert vio == {}, (
        f"docstring-only mentions should not violate the gate: {vio}"
    )


def test_ast_walk_detects_getattr_string_lookup(tmp_path):
    """Stringly-typed dynamic lookups are still executable
    references and should be flagged."""
    src = '''
def smuggle():
    import kv_policy
    return getattr(kv_policy, "Int4ProtectedAttentionImpl")
'''
    f = tmp_path / "string_lookup.py"
    f.write_text(src)
    vio = ast_gate_violations([f])
    assert vio
    assert "Int4ProtectedAttentionImpl" in list(vio.values())[0]


def test_forbidden_symbol_set_covers_core_int4_protected():
    """Belt-and-suspenders: ensure the forbidden set covers the
    headline symbols and import paths the brief calls out."""
    expected = {
        "Int4ProtectedAttentionImpl",
        "Int4ProtectedAttentionBackend",
        "phase5b_backend_install",
        "phase5b_4c_paged_writer",
        "flash_attn_with_int4_kvcache",
    }
    assert expected.issubset(_FORBIDDEN_SYMBOLS)


# ---------------------------------------------------------------- #
# G5c — int4_protected SHA pin
# ---------------------------------------------------------------- #


def test_int4_sha_baseline_matches_current_tree():
    int4_paths = _int4_protected_python_files()
    baseline = load_sha_baseline(DEFAULT_INT4_SHA_BASELINE_PATH)
    current = compute_sha_pin(int4_paths)
    # Every file in scope must be in baseline AND match its SHA.
    for p in int4_paths:
        from ctm_bench.scripts.tier5a_orthogonality_gate import _relpath
        relpath = _relpath(p)
        assert relpath in baseline, f"{relpath} missing from int4 baseline"
        assert baseline[relpath] == current[relpath]


def test_sha_pin_detects_synthetic_modification(tmp_path):
    """Synthesise a baseline+current with one diff; verify the
    verifier reports it as ``modified``."""
    from ctm_bench.scripts.tier5a_orthogonality_gate import (
        _verify_sha_pin, _relpath,
    )
    f1 = tmp_path / "a.py"
    f2 = tmp_path / "b.py"
    f1.write_text("original")
    f2.write_text("orig2")
    baseline = {_relpath(f1): sha256_of(f1), _relpath(f2): sha256_of(f2)}

    # Modify f1.
    f1.write_text("MODIFIED")
    current = compute_sha_pin([f1, f2])
    vio = _verify_sha_pin(baseline, current, [f1, f2])
    assert len(vio) == 1
    only = list(vio.values())[0]
    assert only["status"] == "modified"


def test_sha_pin_detects_missing_file(tmp_path):
    from ctm_bench.scripts.tier5a_orthogonality_gate import (
        _verify_sha_pin, _relpath,
    )
    f1 = tmp_path / "a.py"
    f1.write_text("original")
    baseline = {_relpath(f1): sha256_of(f1)}
    # Pretend current pin is empty.
    current: dict = {}
    vio = _verify_sha_pin(baseline, current, [f1])
    assert _relpath(f1) in vio
    assert vio[_relpath(f1)]["status"] == "missing"


# ---------------------------------------------------------------- #
# G6 — CUDA defensive SHA pin
# ---------------------------------------------------------------- #


def test_cuda_baseline_matches_current_tree():
    cuda_paths = _cuda_files()
    baseline = load_sha_baseline(DEFAULT_CUDA_SHA_BASELINE_PATH)
    current = compute_sha_pin(cuda_paths)
    from ctm_bench.scripts.tier5a_orthogonality_gate import _relpath
    for p in cuda_paths:
        relpath = _relpath(p)
        assert relpath in baseline, f"{relpath} missing from cuda baseline"
        assert baseline[relpath] == current[relpath]


def test_cuda_file_count_matches_expectation():
    """The brief-correction landed at TIER5A.1 freeze: only CTM+'s
    own kernels live in CTM_plus/CUDA/. We expect ~15 files."""
    cuda_paths = _cuda_files()
    assert len(cuda_paths) >= 1
    # Each path should be one of the standard CUDA / C++ suffixes.
    for p in cuda_paths:
        assert p.suffix in {".cu", ".cuh", ".cpp", ".h", ".hpp"}


# ---------------------------------------------------------------- #
# verify_orthogonality + baseline-missing semantics
# ---------------------------------------------------------------- #


def test_verify_orthogonality_reports_missing_baseline(tmp_path):
    """When a baseline file is missing, the corresponding sub-track
    reports a structured failure and overall_passed is False."""
    # Create empty paths (no baseline file on disk).
    fp_path = tmp_path / "no_fp.json"
    int4_path = tmp_path / "no_int4.json"
    cuda_path = tmp_path / "no_cuda.json"
    report = verify_orthogonality(
        fingerprint_baseline_path=fp_path,
        int4_sha_baseline_path=int4_path,
        cuda_sha_baseline_path=cuda_path,
    )
    assert report.passed is False
    assert report.fingerprint_baseline_missing
    assert report.int4_sha_baseline_missing
    assert report.cuda_sha_baseline_missing
    # G5b is baseline-less so it can still pass even with the
    # other baselines missing.
    assert report.g5b_ast_passed is True


def test_baseline_regeneration_is_independent(tmp_path):
    """Each baseline can be regenerated independently."""
    paths = [
        tmp_path / "fp_a.json",
        tmp_path / "sha_a.json",
    ]
    # Generate the fingerprint baseline only.
    fp = compute_class_fingerprints()
    save_fingerprint_baseline(fp, path=paths[0], note="t")
    assert paths[0].exists()
    assert not paths[1].exists()

    # Generate the SHA baseline separately.
    pin = compute_sha_pin(_int4_protected_python_files())
    save_sha_baseline(pin, path=paths[1], note="t")
    assert paths[1].exists()


def test_baseline_round_trip_preserves_data(tmp_path):
    """Save then load returns the same content (within JSON
    round-tripping)."""
    pin = compute_sha_pin(_int4_protected_python_files())
    path = tmp_path / "round_trip.json"
    save_sha_baseline(pin, path=path, note="rt-test")
    loaded = load_sha_baseline(path)
    assert loaded == pin


def test_fingerprint_baseline_round_trip(tmp_path):
    fp = compute_class_fingerprints()
    path = tmp_path / "fp_rt.json"
    save_fingerprint_baseline(fp, path=path, note="rt")
    loaded = load_fingerprint_baseline(path)
    assert loaded == fp


# ---------------------------------------------------------------- #
# AST executable-reference helper
# ---------------------------------------------------------------- #


def test_ast_executable_references_picks_up_imports_and_constants():
    src = '''
from foo.bar import Baz
import x.y

def fn():
    return getattr(z, "DangerousSymbol")
'''
    refs = _ast_executable_references(src)
    assert "Baz" in refs
    assert "foo" in refs and "bar" in refs
    assert "x" in refs and "y" in refs
    assert "DangerousSymbol" in refs


def test_ast_executable_references_excludes_module_docstring():
    src = '''"""ModuleDocstringContainsForbiddenSymbol — should NOT
be collected as an executable reference."""

def fn():
    pass
'''
    refs = _ast_executable_references(src)
    # The docstring TEXT shouldn't appear in refs.
    assert "ModuleDocstringContainsForbiddenSymbol" not in refs


def test_tier5a_module_paths_returns_only_existing_files():
    paths = _tier5a_module_paths()
    for p in paths:
        assert p.is_file()
