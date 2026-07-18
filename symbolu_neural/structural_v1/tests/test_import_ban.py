"""Import-ban / boundary test (hard gate).

Asserts the Stage A package imports NONE of the forbidden modules and pulls in no
network/API client, by statically scanning every source file under structural_v1
AND by checking sys.modules after importing the package.
"""
from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent.parent

FORBIDDEN_SUBSTRINGS = (
    # the v3/v4/policy line explicitly named in the authorization
    "llm",
    "judge",
    "policy",
    "policy_v4",
    "symbolu_state",
    # network / API clients
    "requests",
    "httpx",
    "urllib",
    "http.client",
    "socket",
    "aiohttp",
    "openai",
    "anthropic",
    "mistral",
)

# tokens that may legitimately appear as substrings inside allowed identifiers
ALLOWLIST_EXACT_OK = set()  # none needed; we match against import module paths only


def _iter_source_files():
    for p in PKG_DIR.rglob("*.py"):
        yield p


def _imported_modules(path: Path):
    tree = ast.parse(path.read_text(), filename=str(path))
    mods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.append(a.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            # relative imports (level>0) stay inside the package -> fine
            if node.level and not mod:
                continue
            mods.append(mod)
    return mods


def test_no_forbidden_static_imports():
    offenders = []
    for path in _iter_source_files():
        for mod in _imported_modules(path):
            base = mod.split(".")
            for bad in FORBIDDEN_SUBSTRINGS:
                # match a forbidden token as a full path component
                if bad in base or mod == bad or mod.endswith("." + bad):
                    # allow our own relative modules that merely contain a token? none do.
                    offenders.append((path.name, mod, bad))
    assert not offenders, f"forbidden imports found: {offenders}"


def test_package_pulls_no_network_client():
    before = set(sys.modules)
    importlib.import_module("symbolu_neural.structural_v1.gate")
    importlib.import_module("symbolu_neural.structural_v1.run")
    after = set(sys.modules)
    newly = after - before
    banned = {"requests", "httpx", "aiohttp", "openai", "anthropic", "urllib3"}
    hits = sorted(m for m in newly if m.split(".")[0] in banned)
    assert not hits, f"network/API modules imported at runtime: {hits}"


def test_no_forbidden_v3_v4_modules_loaded():
    importlib.import_module("symbolu_neural.structural_v1.gate")
    bad = [m for m in sys.modules
           if "internal_policy_controller" in m or m.endswith("symbolu_state")
           or m.endswith(".judge") or m.endswith(".llm") or m.endswith(".policy")]
    assert not bad, f"v3/v4/policy modules loaded: {bad}"


if __name__ == "__main__":
    test_no_forbidden_static_imports()
    test_package_pulls_no_network_client()
    test_no_forbidden_v3_v4_modules_loaded()
    print("test_import_ban: OK")
