"""
Structure BCVF — Multi-Scale Constraint Energy Framework
=========================================================

BCVF evolved from token-level consistency to multi-scale constraint energy:

    Score(y) = log p(y|x)
             + λ_phoneme  · E_phoneme(y)     ← articulatory prior
             + λ_token    · E_token(y)        ← sf/sb consistency
             + λ_struct   · E_structure(y)    ← program structure
             + λ_value    · E_value(y)        ← outcome prediction

Each channel:
    - Measures a different invariance
    - Has different failure modes
    - Is independently toggleable

This module implements the structure and value channels for code generation.

Constraint energies (higher = better candidate):

    E_ast        = +0.3 if ast.parse succeeds, -0.15 otherwise
    E_unbound    = -0.1 per unbound variable
    E_runtime    = +0.05 if runs without exception on smoke input, -0.30 otherwise
    E_return     = +0.1 if has return, -0.15 if missing when expected
    E_params     = +0.05 per used param, -0.1 if none used
    E_complete   = -0.25 if placeholder code detected
    E_doctest    = +0.35 if docstring examples pass, -0.40 if they fail
    E_truncation = -0.20 if mid-statement truncation detected
    E_repetition = -0.25 * ratio if degenerate line repetition detected
    E_branch     = +0.10 if all branches return, -0.15 otherwise

Combined:
    S(y) = log p(y|x) + α · logit(clip(0.5 + ΣE, 0.01, 0.99))

Usage::

    from symbolu.ontological.structure_bcvf import StructureBCVF, StructureConfig

    bcvf = StructureBCVF(StructureConfig(
        use_ast=True, use_unbound=True, use_runtime=True,
        alpha=1.0,
    ))

    # Score a single candidate
    score = bcvf.score(prompt, candidate, base_logprob=-12.5)

    # Score multiple candidates and select best
    best_idx, scores, diagnostics = bcvf.rerank(prompt, candidates, logprobs)
"""

from __future__ import annotations

import ast
import math
import re
import sys
import textwrap
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# =========================================================================
# Configuration
# =========================================================================


@dataclass
class StructureConfig:
    """Configuration for structure BCVF constraint energies."""

    # --- Feature toggles ---
    use_ast: bool = True
    use_unbound: bool = True
    use_runtime: bool = False        # Disabled by default (exec is slow + risky)
    use_return_check: bool = True
    use_param_usage: bool = True
    use_placeholder_check: bool = True
    # --- Discriminative feature toggles (new) ---
    use_doctest: bool = True         # Extract & run >>> examples from docstring
    use_truncation_check: bool = True  # Detect mid-statement truncation
    use_repetition_check: bool = True  # Detect degenerate line repetition
    use_control_flow_check: bool = True  # Branch completeness analysis

    # --- Weights ---
    w_ast: float = 0.30              # AST parse success bonus
    w_ast_fail: float = -0.15        # AST parse failure penalty
    w_unbound: float = -0.10         # Per unbound variable penalty
    w_runtime_pass: float = 0.05     # Weak positive (most valid code runs on trivial input)
    w_runtime_fail: float = -0.30    # Strong negative (crash/timeout = real breakage)
    w_return_present: float = 0.10   # Return statement bonus
    w_return_missing: float = -0.15  # Missing return penalty
    w_param_used: float = 0.05       # Per parameter used bonus
    w_param_none: float = -0.10      # No params used penalty
    w_placeholder: float = -0.25     # Placeholder code penalty
    w_complete: float = 0.05         # Non-trivial body bonus
    # --- Discriminative feature weights (new) ---
    w_doctest_pass: float = 0.35     # Strong: passes a real functional test
    w_doctest_fail: float = -0.40    # Strong: fails a functional test
    w_truncated: float = -0.20       # Mid-statement truncation penalty
    w_repetition: float = -0.25      # Degenerate repetition penalty
    w_branch_complete: float = 0.10  # All branches return
    w_branch_incomplete: float = -0.15  # Dangling branches without return

    # --- Combination ---
    alpha: float = 1.0               # Weight of logit(utility) in final score
    utility_floor: float = 0.01      # Clamp utility above this
    utility_ceil: float = 0.99       # Clamp utility below this

    # --- Runtime smoke test ---
    runtime_timeout_s: float = 2.0   # Max seconds for smoke test
    runtime_trivial_inputs: int = 3  # Number of trivial inputs to try
    # --- Doctest ---
    doctest_timeout_s: float = 3.0   # Max seconds for doctest execution


# =========================================================================
# Constraint Feature Functions
# =========================================================================


def check_ast(full_code: str) -> Tuple[bool, Optional[str]]:
    """Check if code parses as valid Python AST.

    Returns (success, error_message).
    """
    try:
        ast.parse(full_code)
        return True, None
    except SyntaxError as e:
        return False, str(e)


def find_unbound_variables(full_code: str, function_name: str) -> List[str]:
    """Find variables used but never defined in the function body.

    Uses AST analysis to track Name loads vs stores within the
    target function. Ignores builtins and imports.
    """
    try:
        tree = ast.parse(full_code)
    except SyntaxError:
        return []

    # Python builtins that don't need definition
    builtins = set(dir(__builtins__)) if isinstance(__builtins__, dict) else set(dir(__builtins__))
    builtins.update({
        'True', 'False', 'None', 'print', 'len', 'range', 'enumerate',
        'zip', 'map', 'filter', 'sorted', 'reversed', 'list', 'dict',
        'set', 'tuple', 'str', 'int', 'float', 'bool', 'type', 'isinstance',
        'issubclass', 'hasattr', 'getattr', 'setattr', 'abs', 'min', 'max',
        'sum', 'any', 'all', 'round', 'pow', 'divmod', 'hash', 'id', 'ord',
        'chr', 'hex', 'oct', 'bin', 'format', 'repr', 'input', 'open',
        'super', 'property', 'staticmethod', 'classmethod', 'ValueError',
        'TypeError', 'IndexError', 'KeyError', 'AttributeError',
        'RuntimeError', 'StopIteration', 'Exception', 'NotImplementedError',
        'AssertionError', 'ZeroDivisionError', 'OverflowError',
        'math', 'sys', 'os', 're', 'collections', 'itertools', 'functools',
        'operator', 'string', 'copy', 'heapq', 'bisect',
        'defaultdict', 'Counter', 'deque', 'OrderedDict',
    })

    # Find the target function
    target_func = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == function_name:
                target_func = node
                break

    if target_func is None:
        return []

    # Collect defined names (stores) and used names (loads)
    defined = set()
    used = set()

    # Parameters count as defined
    for arg in target_func.args.args:
        defined.add(arg.arg)
    if target_func.args.vararg:
        defined.add(target_func.args.vararg.arg)
    if target_func.args.kwarg:
        defined.add(target_func.args.kwarg.arg)
    for arg in target_func.args.kwonlyargs:
        defined.add(arg.arg)

    # Walk the function body
    for node in ast.walk(target_func):
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Store):
                defined.add(node.id)
            elif isinstance(node.ctx, ast.Load):
                used.add(node.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                defined.add(alias.asname or alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                defined.add(alias.asname or alias.name)
        # For loops define their target variable
        elif isinstance(node, ast.For):
            if isinstance(node.target, ast.Name):
                defined.add(node.target.id)
            elif isinstance(node, ast.Tuple):
                for elt in node.target.elts:
                    if isinstance(elt, ast.Name):
                        defined.add(elt.id)
        # Comprehension variables
        elif isinstance(node, ast.comprehension):
            if isinstance(node.target, ast.Name):
                defined.add(node.target.id)
        # With-as
        elif isinstance(node, ast.withitem):
            if node.optional_vars and isinstance(node.optional_vars, ast.Name):
                defined.add(node.optional_vars.id)
        # Nested function defs
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node is not target_func:
                defined.add(node.name)

    unbound = used - defined - builtins
    return sorted(unbound)


def check_runtime(
    full_code: str,
    function_name: str,
    timeout_s: float = 2.0,
) -> Tuple[bool, Optional[str]]:
    """Run the code and call the function with trivial inputs.

    Returns (success, error_message).
    Catches all exceptions. Returns False on timeout or error.
    """
    import signal as signal_mod

    # Build test harness
    test_code = f"""
{full_code}

# Smoke test with trivial inputs
import inspect
sig = inspect.signature({function_name})
n_params = len([p for p in sig.parameters.values()
                if p.default is inspect.Parameter.empty
                and p.name != 'self'])

# Try calling with minimal arguments
trivial_args = []
for p in sig.parameters.values():
    if p.name == 'self':
        continue
    if p.default is not inspect.Parameter.empty:
        continue
    ann = p.annotation
    if ann is int or ann == 'int':
        trivial_args.append(0)
    elif ann is str or ann == 'str':
        trivial_args.append("")
    elif ann is float or ann == 'float':
        trivial_args.append(0.0)
    elif ann is bool or ann == 'bool':
        trivial_args.append(False)
    elif ann is list or ann == 'list' or str(ann).startswith('List'):
        trivial_args.append([])
    elif ann is dict or ann == 'dict' or str(ann).startswith('Dict'):
        trivial_args.append({{}})
    else:
        trivial_args.append(0)

try:
    result = {function_name}(*trivial_args)
    _SMOKE_OK = True
except (TypeError, NameError, AttributeError) as e:
    # These indicate real code problems (wrong args, undefined vars, bad attrs)
    _SMOKE_OK = False
    _SMOKE_ERR = str(e)
except Exception:
    _SMOKE_OK = True  # Value errors, index errors on trivial input are OK
"""

    class TimeoutError(Exception):
        pass

    def handler(signum, frame):
        raise TimeoutError("Smoke test timed out")

    try:
        # Set alarm (Unix only)
        old_handler = signal_mod.signal(signal_mod.SIGALRM, handler)
        signal_mod.alarm(int(timeout_s) + 1)

        exec_globals: Dict[str, Any] = {}
        exec(test_code, exec_globals)

        signal_mod.alarm(0)
        signal_mod.signal(signal_mod.SIGALRM, old_handler)

        # Check if the function call itself failed
        if not exec_globals.get("_SMOKE_OK", True):
            return False, exec_globals.get("_SMOKE_ERR", "unknown")
        return True, None

    except TimeoutError:
        signal_mod.alarm(0)
        return False, "timeout"
    except Exception as e:
        try:
            signal_mod.alarm(0)
        except Exception:
            pass
        return False, str(e)[:200]


# =========================================================================
# Discriminative Feature Functions
# =========================================================================


def extract_doctests(prompt: str) -> List[Tuple[str, str]]:
    """Extract (input_expr, expected_output) pairs from ``>>>`` examples in docstrings.

    Parses Python doctest-style examples found in HumanEval prompts::

        >>> func(1, 2)
        3
        >>> func("a")
        'a'

    Returns list of (call_expression, expected_result_repr) tuples.
    """
    pairs: List[Tuple[str, str]] = []
    lines = prompt.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith(">>>"):
            expr = line[3:].strip()
            # Collect expected output (next non->>> non-empty lines)
            expected_lines: List[str] = []
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if not next_line or next_line.startswith(">>>"):
                    break
                # Stop at docstring closing delimiter
                if next_line in ('"""', "'''"):
                    break
                # Skip continuation lines (... prefix)
                if next_line.startswith("..."):
                    expr += "\n" + next_line[3:].strip()
                else:
                    expected_lines.append(next_line)
                j += 1
            if expected_lines:
                expected = "\n".join(expected_lines)
                pairs.append((expr, expected))
            i = j
        else:
            i += 1
    return pairs


def run_doctests(
    full_code: str,
    doctests: List[Tuple[str, str]],
    timeout_s: float = 3.0,
) -> Tuple[int, int]:
    """Run extracted doctests against assembled code.

    Returns (n_passed, n_total).
    """
    if not doctests:
        return 0, 0

    import signal as signal_mod

    n_passed = 0
    n_total = len(doctests)

    class _Timeout(Exception):
        pass

    def _handler(signum, frame):
        raise _Timeout()

    for expr, expected in doctests:
        test_script = f"""{full_code}

_result = {expr}
_expected_repr = repr(_result)
"""
        try:
            old_handler = signal_mod.signal(signal_mod.SIGALRM, _handler)
            signal_mod.alarm(int(timeout_s) + 1)

            exec_globals: Dict[str, Any] = {}
            exec(test_script, exec_globals)

            signal_mod.alarm(0)
            signal_mod.signal(signal_mod.SIGALRM, old_handler)

            actual_repr = exec_globals.get("_expected_repr", "")
            # Compare repr strings (handles ints, strings, lists, etc.)
            if actual_repr.strip() == expected.strip():
                n_passed += 1
            else:
                # Also try direct str comparison (some doctests use print-style output)
                actual_str = str(exec_globals.get("_result", ""))
                if actual_str.strip() == expected.strip():
                    n_passed += 1
        except _Timeout:
            try:
                signal_mod.alarm(0)
            except Exception:
                pass
        except Exception:
            try:
                signal_mod.alarm(0)
                signal_mod.signal(signal_mod.SIGALRM, old_handler)
            except Exception:
                pass

    return n_passed, n_total


def detect_truncation(candidate: str) -> bool:
    """Detect if a candidate was truncated mid-statement.

    Looks for signs of incomplete code at the end:
    - Trailing open parenthesis/bracket/brace
    - Incomplete string literal
    - Line ending with an operator
    - Unmatched delimiters
    """
    if not candidate.strip():
        return False

    # Get last non-empty line
    lines = [l for l in candidate.rstrip().split("\n") if l.strip()]
    if not lines:
        return False
    last_line = lines[-1].strip()

    # Obvious truncation: ends with operator, comma, or open delimiter
    truncation_endings = (
        '(', '[', '{', ',', '+', '-', '*', '/', '=', ':', '\\',
        'and', 'or', 'not', 'in', 'is', 'if', 'else',
    )
    for ending in truncation_endings:
        if last_line.endswith(ending):
            return True

    # Unmatched delimiters in the whole candidate
    opens = sum(candidate.count(c) for c in '([{')
    closes = sum(candidate.count(c) for c in ')]}')
    if opens > closes + 1:  # Allow 1 mismatch (common in function bodies)
        return True

    # Unterminated string (odd number of quotes)
    for q in ('"""', "'''", '"', "'"):
        # Don't count escaped quotes
        count = candidate.count(q)
        if q in ('"""', "'''"):
            if count % 2 != 0:
                return True

    return False


def detect_repetition(candidate: str) -> float:
    """Detect degenerate line repetition in a candidate.

    Returns ratio of repeated non-trivial lines (0.0 = no repetition, 1.0 = all repeated).
    """
    lines = [l.strip() for l in candidate.split("\n") if l.strip()]
    if len(lines) < 3:
        return 0.0

    # Skip trivial lines (single tokens, common patterns)
    trivial = {'', 'pass', 'return', 'else:', 'try:', 'except:', 'finally:'}
    meaningful = [l for l in lines if l not in trivial and len(l) > 8]

    if len(meaningful) < 3:
        return 0.0

    from collections import Counter
    counts = Counter(meaningful)
    repeated = sum(c - 1 for c in counts.values() if c > 1)
    return repeated / len(meaningful)


def check_branch_completeness(full_code: str, function_name: str) -> Tuple[int, int]:
    """Check if all if/elif/else branches in a function end with return.

    Returns (branches_with_return, total_branches).
    Uses AST analysis for accuracy.
    """
    try:
        tree = ast.parse(full_code)
    except SyntaxError:
        return 0, 0

    # Find the target function
    target_func = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == function_name:
                target_func = node
                break

    if target_func is None:
        return 0, 0

    def _block_returns(stmts: List[Any]) -> bool:
        """Check if a block of statements definitely returns."""
        if not stmts:
            return False
        last = stmts[-1]
        if isinstance(last, ast.Return):
            return True
        if isinstance(last, ast.If):
            # Both branches must return
            if_returns = _block_returns(last.body)
            else_returns = _block_returns(last.orelse) if last.orelse else False
            return if_returns and else_returns
        return False

    total_branches = 0
    branches_with_return = 0

    for node in ast.walk(target_func):
        if isinstance(node, ast.If):
            # Count the if branch
            total_branches += 1
            if _block_returns(node.body):
                branches_with_return += 1
            # Count each elif/else
            if node.orelse:
                total_branches += 1
                if _block_returns(node.orelse):
                    branches_with_return += 1

    return branches_with_return, total_branches


# =========================================================================
# Structure BCVF
# =========================================================================


@dataclass
class ConstraintDiagnostics:
    """Per-candidate constraint diagnostics."""
    ast_ok: bool = False
    ast_error: Optional[str] = None
    n_unbound: int = 0
    unbound_vars: List[str] = field(default_factory=list)
    runtime_ok: Optional[bool] = None
    runtime_error: Optional[str] = None
    has_return: bool = False
    return_expected: bool = False
    params_used: int = 0
    params_total: int = 0
    has_placeholder: bool = False
    body_length: int = 0
    # --- Discriminative features (new) ---
    doctest_passed: Optional[bool] = None   # Did extracted doctests pass?
    doctest_total: int = 0                  # Number of doctests found
    doctest_ok: int = 0                     # Number that passed
    is_truncated: bool = False              # Mid-statement truncation detected
    repetition_ratio: float = 0.0           # Fraction of repeated lines
    branches_total: int = 0                 # Number of if/elif/else branches
    branches_with_return: int = 0           # Branches that end with return
    branch_complete: Optional[bool] = None  # All branches return?
    # Individual energy contributions
    e_ast: float = 0.0
    e_unbound: float = 0.0
    e_runtime: float = 0.0
    e_return: float = 0.0
    e_params: float = 0.0
    e_placeholder: float = 0.0
    e_complete: float = 0.0
    e_doctest: float = 0.0
    e_truncation: float = 0.0
    e_repetition: float = 0.0
    e_branch: float = 0.0
    # Combined
    utility: float = 0.5
    utility_logit: float = 0.0


class StructureBCVF:
    """
    Structure-level BCVF constraint energy for code generation.

    Implements the "evolved BCVF" where constraint satisfaction
    produces discriminative signal orthogonal to likelihood.

    S(y) = log p(y|x) + α · logit(V(x,y))

    Where V(x,y) = clip(0.5 + ΣE_i, floor, ceil) and each E_i
    is a constraint energy (AST, unbound, runtime, etc.).
    """

    def __init__(self, config: Optional[StructureConfig] = None):
        self.config = config or StructureConfig()

    def compute_energies(
        self, prompt: str, candidate: str,
    ) -> ConstraintDiagnostics:
        """Compute all constraint energies for one candidate."""
        cfg = self.config
        diag = ConstraintDiagnostics()

        body = _extract_function_body(candidate)
        full_code = prompt + body
        fn_name = _extract_function_name(prompt) or ""

        diag.body_length = len(body.strip())

        # (A) AST
        if cfg.use_ast:
            ok, err = check_ast(full_code)
            diag.ast_ok = ok
            diag.ast_error = err
            diag.e_ast = cfg.w_ast if ok else cfg.w_ast_fail

        # (B) Unbound variables
        if cfg.use_unbound and fn_name:
            unbound = find_unbound_variables(full_code, fn_name)
            diag.n_unbound = len(unbound)
            diag.unbound_vars = unbound
            diag.e_unbound = cfg.w_unbound * len(unbound)

        # (C) Runtime smoke test
        if cfg.use_runtime and fn_name and diag.ast_ok:
            ok, err = check_runtime(full_code, fn_name, cfg.runtime_timeout_s)
            diag.runtime_ok = ok
            diag.runtime_error = err
            diag.e_runtime = cfg.w_runtime_pass if ok else cfg.w_runtime_fail

        # (D) Return statement
        if cfg.use_return_check and fn_name:
            diag.return_expected = _likely_needs_return(prompt)
            diag.has_return = _has_return(body)
            if diag.return_expected:
                diag.e_return = (
                    cfg.w_return_present if diag.has_return
                    else cfg.w_return_missing
                )

        # (E) Parameter usage
        if cfg.use_param_usage:
            params = _extract_param_names(prompt)
            diag.params_total = len(params)
            diag.params_used = sum(1 for p in params if p in body)
            if params:
                if diag.params_used == 0:
                    diag.e_params = cfg.w_param_none
                else:
                    diag.e_params = cfg.w_param_used * diag.params_used

        # (F) Placeholder detection
        if cfg.use_placeholder_check:
            diag.has_placeholder = _has_placeholder(body)
            if diag.has_placeholder:
                diag.e_placeholder = cfg.w_placeholder

        # (G) Completeness
        if diag.body_length > 20 and not diag.has_placeholder:
            diag.e_complete = cfg.w_complete

        # (H) Doctest execution — extract >>> examples and run them
        if cfg.use_doctest and fn_name and diag.ast_ok:
            doctests = extract_doctests(prompt)
            if doctests:
                n_ok, n_total = run_doctests(
                    full_code, doctests, cfg.doctest_timeout_s,
                )
                diag.doctest_total = n_total
                diag.doctest_ok = n_ok
                if n_ok == n_total:
                    diag.doctest_passed = True
                    diag.e_doctest = cfg.w_doctest_pass
                elif n_ok > 0:
                    # Partial pass: proportional bonus
                    diag.doctest_passed = False
                    ratio = n_ok / n_total
                    diag.e_doctest = (
                        cfg.w_doctest_pass * ratio
                        + cfg.w_doctest_fail * (1 - ratio)
                    )
                else:
                    diag.doctest_passed = False
                    diag.e_doctest = cfg.w_doctest_fail

        # (I) Truncation detection
        if cfg.use_truncation_check:
            diag.is_truncated = detect_truncation(body)
            if diag.is_truncated:
                diag.e_truncation = cfg.w_truncated

        # (J) Repetition detection
        if cfg.use_repetition_check:
            diag.repetition_ratio = detect_repetition(body)
            if diag.repetition_ratio > 0.3:
                diag.e_repetition = cfg.w_repetition * diag.repetition_ratio

        # (K) Branch completeness
        if cfg.use_control_flow_check and fn_name and diag.ast_ok:
            br_ret, br_total = check_branch_completeness(full_code, fn_name)
            diag.branches_total = br_total
            diag.branches_with_return = br_ret
            if br_total > 0:
                if br_ret == br_total:
                    diag.branch_complete = True
                    diag.e_branch = cfg.w_branch_complete
                else:
                    diag.branch_complete = False
                    diag.e_branch = cfg.w_branch_incomplete

        # --- Combined utility ---
        total_energy = (
            diag.e_ast + diag.e_unbound + diag.e_runtime +
            diag.e_return + diag.e_params + diag.e_placeholder +
            diag.e_complete + diag.e_doctest + diag.e_truncation +
            diag.e_repetition + diag.e_branch
        )
        raw = 0.5 + total_energy
        diag.utility = float(np.clip(raw, cfg.utility_floor, cfg.utility_ceil))
        diag.utility_logit = math.log(
            diag.utility / (1.0 - diag.utility)
        )

        return diag

    def score(
        self, prompt: str, candidate: str, base_logprob: float,
    ) -> float:
        """Score a single candidate: logprob + α · logit(utility)."""
        diag = self.compute_energies(prompt, candidate)
        return base_logprob + self.config.alpha * diag.utility_logit

    def rerank(
        self,
        prompt: str,
        candidates: List[str],
        logprobs: List[float],
    ) -> Tuple[int, np.ndarray, List[ConstraintDiagnostics]]:
        """Rerank candidates using structure BCVF.

        Returns:
            best_idx: index of best candidate
            scores: array of combined scores
            diagnostics: per-candidate constraint diagnostics
        """
        diagnostics = []
        scores = np.zeros(len(candidates))

        for i, (cand, lp) in enumerate(zip(candidates, logprobs)):
            diag = self.compute_energies(prompt, cand)
            diagnostics.append(diag)
            scores[i] = lp + self.config.alpha * diag.utility_logit

        best_idx = int(np.argmax(scores))
        return best_idx, scores, diagnostics

    def summary(self, diagnostics: List[ConstraintDiagnostics]) -> Dict[str, Any]:
        """Summarize diagnostics across candidates."""
        n = len(diagnostics)
        if n == 0:
            return {}

        utilities = [d.utility for d in diagnostics]
        result = {
            "n_candidates": n,
            "ast_pass_rate": sum(d.ast_ok for d in diagnostics) / n,
            "mean_unbound": np.mean([d.n_unbound for d in diagnostics]),
            "max_unbound": max(d.n_unbound for d in diagnostics),
            "runtime_pass_rate": (
                sum(1 for d in diagnostics if d.runtime_ok is True) / n
                if any(d.runtime_ok is not None for d in diagnostics) else None
            ),
            "return_present_rate": sum(d.has_return for d in diagnostics) / n,
            "placeholder_rate": sum(d.has_placeholder for d in diagnostics) / n,
            # --- Discriminative features ---
            "doctest_rate": (
                sum(1 for d in diagnostics if d.doctest_passed is True) / n
                if any(d.doctest_total > 0 for d in diagnostics) else None
            ),
            "truncation_rate": sum(d.is_truncated for d in diagnostics) / n,
            "mean_repetition": float(np.mean([d.repetition_ratio for d in diagnostics])),
            "branch_complete_rate": (
                sum(1 for d in diagnostics if d.branch_complete is True) / n
                if any(d.branches_total > 0 for d in diagnostics) else None
            ),
            # --- Utilities ---
            "utility_mean": float(np.mean(utilities)),
            "utility_std": float(np.std(utilities)),
            "utility_min": float(np.min(utilities)),
            "utility_max": float(np.max(utilities)),
            "utility_spread": float(np.max(utilities) - np.min(utilities)),
        }
        return result


# =========================================================================
# Multi-Channel BCVF Compositor
# =========================================================================


@dataclass
class ChannelScore:
    """Score from one BCVF channel."""
    name: str
    energy: float
    weight: float
    weighted: float  # weight * energy


@dataclass
class MultiChannelConfig:
    """Configuration for multi-channel BCVF composition.

    Final score:
        S(y) = log p(y|x) + Σ_c λ_c · E_c(y)

    Each channel provides an energy E_c and is weighted by λ_c.
    """
    # Channel weights (0 = disabled)
    lambda_phoneme: float = 0.0   # Phoneme articulatory prior
    lambda_token: float = 0.0     # Token-level sf/sb consistency
    lambda_struct: float = 1.0    # Structure constraint energy
    lambda_value: float = 0.0     # Learned value head


class MultiChannelBCVF:
    """
    Multi-scale constraint energy compositor.

    Combines independently computed BCVF channels into a single score:

        S(y) = log p(y|x) + Σ_c λ_c · E_c(y)

    Channels are pluggable — each provides compute_energy(context) -> float.
    """

    def __init__(self, config: Optional[MultiChannelConfig] = None):
        self.config = config or MultiChannelConfig()
        self._channels: Dict[str, Any] = {}

    def register_channel(self, name: str, scorer: Any) -> None:
        """Register a constraint channel.

        The scorer must implement: score(prompt, candidate, logprob) -> float
        or compute_energies(prompt, candidate) -> diagnostics with .utility_logit
        """
        self._channels[name] = scorer

    def score(
        self,
        prompt: str,
        candidate: str,
        base_logprob: float,
        **channel_kwargs,
    ) -> Tuple[float, List[ChannelScore]]:
        """Score one candidate across all channels.

        Returns (total_score, per_channel_scores).
        """
        channels = []
        total = base_logprob

        # Structure channel
        if self.config.lambda_struct > 0 and "structure" in self._channels:
            s = self._channels["structure"]
            diag = s.compute_energies(prompt, candidate)
            energy = diag.utility_logit
            weighted = self.config.lambda_struct * energy
            channels.append(ChannelScore("structure", energy, self.config.lambda_struct, weighted))
            total += weighted

        # Value head channel
        if self.config.lambda_value > 0 and "value" in self._channels:
            v = self._channels["value"]
            energy = v.score(prompt, candidate, 0.0)  # raw energy, no logprob
            weighted = self.config.lambda_value * energy
            channels.append(ChannelScore("value", energy, self.config.lambda_value, weighted))
            total += weighted

        return total, channels


# =========================================================================
# Helper Functions (shared with ValueReranker)
# =========================================================================


def _extract_function_body(candidate: str) -> str:
    """Extract just the function body from a candidate continuation."""
    lines = candidate.split("\n")
    body_lines: List[str] = []
    seen_content = False

    for line in lines:
        if not line.strip():
            body_lines.append(line)
            continue
        if seen_content and line and not line[0].isspace():
            break
        body_lines.append(line)
        seen_content = True

    while body_lines and not body_lines[-1].strip():
        body_lines.pop()

    return "\n".join(body_lines)


def _extract_function_name(prompt: str) -> Optional[str]:
    """Extract function name from HumanEval-style prompt."""
    match = re.search(r"def\s+(\w+)\s*\(", prompt)
    return match.group(1) if match else None


def _extract_param_names(prompt: str) -> List[str]:
    """Extract parameter names from the function signature in prompt."""
    match = re.search(r"def\s+\w+\s*\(([^)]*)\)", prompt)
    if not match:
        return []
    params_str = match.group(1)
    names: List[str] = []
    for part in params_str.split(","):
        part = part.strip()
        if not part or part == "self":
            continue
        name = part.split(":")[0].split("=")[0].strip()
        if name:
            names.append(name)
    return names


def _likely_needs_return(prompt: str) -> bool:
    """Heuristic: does this problem likely expect a return value?"""
    lower = prompt.lower()
    if "-> none" in lower or "print(" in lower:
        return False
    if "->" in prompt or "return" in lower or "returns" in lower:
        return True
    return True


def _has_return(candidate: str) -> bool:
    """Check if candidate has a return or yield statement."""
    for line in candidate.split("\n"):
        stripped = line.strip()
        if stripped.startswith("return ") or stripped == "return":
            return True
        if stripped.startswith("yield "):
            return True
    return False


def _has_placeholder(candidate: str) -> bool:
    """Detect placeholder/incomplete code patterns."""
    stripped = candidate.strip()
    if stripped == "pass" or stripped.endswith("\n    pass"):
        return True
    for pattern in ("TODO", "raise NotImplementedError", "..."):
        if pattern in candidate:
            if pattern == "...":
                for line in candidate.split("\n"):
                    ls = line.strip()
                    if ls == "..." or ls == "Ellipsis":
                        return True
            else:
                return True
    return False
