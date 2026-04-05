"""
Drift guard for the symbolu/llm <-> agentic/llm migration mirror.

Context
-------
Commit 654b3b8 ("Extract 18 SUPPLY modules to symbolu_core/, create
agentic/ package") created a second copy of the LLM interface layer at
``agentic/llm/`` while keeping the original at ``symbolu/llm/``.
Production deployment still runs through ``symbolu/llm/*`` (see
nixpacks.toml). The extraction target is ``agentic/llm/*``.

Until the migration completes, the two trees MUST stay in sync:

  * providers.py   — byte-identical
  * types.py       — byte-identical
  * validator.py   — differs only in the namespace import prefix
                     (``symbolu.llm`` vs ``agentic.llm``)
  * __init__.py    — differs only in the namespace import prefix

This test pins those invariants. Any intentional drift must update
both sides (and, if the diff is no longer namespace-only, update this
test to describe the new invariant).
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SYMBOLU_LLM = REPO_ROOT / "symbolu" / "llm"
AGENTIC_LLM = REPO_ROOT / "agentic" / "llm"


def _read(path: Path) -> str:
    assert path.is_file(), f"mirror file missing: {path}"
    return path.read_text(encoding="utf-8")


def _namespace_normalize(text: str) -> str:
    """Collapse the namespace prefix so that namespace-only diffs vanish."""
    return text.replace("agentic.llm", "symbolu.llm")


class TestLLMMirrorNoByteDrift:
    """providers.py and types.py must be byte-identical across mirrors."""

    def test_providers_byte_identical(self):
        a = _read(SYMBOLU_LLM / "providers.py")
        b = _read(AGENTIC_LLM / "providers.py")
        assert a == b, (
            "symbolu/llm/providers.py and agentic/llm/providers.py have "
            "drifted. Both mirrors must stay byte-identical until the "
            "migration completes. Update both sides together."
        )

    def test_types_byte_identical(self):
        a = _read(SYMBOLU_LLM / "types.py")
        b = _read(AGENTIC_LLM / "types.py")
        assert a == b, (
            "symbolu/llm/types.py and agentic/llm/types.py have drifted. "
            "Both mirrors must stay byte-identical until the migration "
            "completes. Update both sides together."
        )


class TestLLMMirrorNamespaceOnlyDrift:
    """validator.py and __init__.py may differ ONLY in the namespace prefix."""

    def test_validator_namespace_only_diff(self):
        a = _read(SYMBOLU_LLM / "validator.py")
        b = _read(AGENTIC_LLM / "validator.py")
        assert a != b, (
            "symbolu/llm/validator.py and agentic/llm/validator.py became "
            "byte-identical. Expected them to differ by the namespace "
            "import prefix. Update this test if that changed."
        )
        assert _namespace_normalize(a) == _namespace_normalize(b), (
            "validator.py mirrors diverged beyond the expected "
            "namespace-only diff (symbolu.llm <-> agentic.llm). Update "
            "both sides together, or update this test if the allowed "
            "diff has changed."
        )

    def test_init_namespace_only_diff(self):
        a = _read(SYMBOLU_LLM / "__init__.py")
        b = _read(AGENTIC_LLM / "__init__.py")
        assert a != b, (
            "symbolu/llm/__init__.py and agentic/llm/__init__.py became "
            "byte-identical. Expected them to differ by the namespace "
            "import prefix. Update this test if that changed."
        )
        assert _namespace_normalize(a) == _namespace_normalize(b), (
            "__init__.py mirrors diverged beyond the expected "
            "namespace-only diff (symbolu.llm <-> agentic.llm). Update "
            "both sides together, or update this test if the allowed "
            "diff has changed."
        )
