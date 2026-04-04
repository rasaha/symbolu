"""
Tests for agentic.ontology.safety (O2)
=======================================

Verifies the portable runtime safety validators extracted from
the projection engine's validator layer.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from unittest import mock

import pytest

from agentic.ontology.safety import (
    FORBIDDEN_MODULES,
    TIMESTAMP_WORDS,
    check_no_forbidden_modules,
    check_no_timestamp_words,
)


# =========================================================================
# FORBIDDEN_MODULES constant
# =========================================================================

class TestForbiddenModulesConstant:
    """Verify the forbidden modules registry."""

    def test_is_tuple(self) -> None:
        assert isinstance(FORBIDDEN_MODULES, tuple)

    def test_contains_known_nlp_libs(self) -> None:
        for lib in ("nltk", "spacy", "transformers", "langchain", "gensim", "textblob"):
            assert lib in FORBIDDEN_MODULES

    def test_contains_known_llm_clients(self) -> None:
        for lib in ("openai", "anthropic"):
            assert lib in FORBIDDEN_MODULES

    def test_does_not_contain_stdlib(self) -> None:
        for lib in ("hashlib", "json", "math", "re", "sys", "os"):
            assert lib not in FORBIDDEN_MODULES


# =========================================================================
# check_no_forbidden_modules
# =========================================================================

class TestCheckNoForbiddenModules:
    """Verify runtime forbidden-module scanning."""

    def test_clean_environment_passes(self) -> None:
        passed, violations = check_no_forbidden_modules()
        # We cannot guarantee no test runner loads forbidden modules,
        # but we can verify the return structure.
        assert isinstance(passed, bool)
        assert isinstance(violations, list)
        if passed:
            assert violations == []

    def test_detects_forbidden_module(self) -> None:
        """Simulate a forbidden module being loaded."""
        fake_modules = dict(sys.modules)
        fake_modules["nltk"] = mock.MagicMock()
        fake_modules["nltk.tokenize"] = mock.MagicMock()

        with mock.patch.dict(sys.modules, fake_modules):
            passed, violations = check_no_forbidden_modules()
            assert not passed
            assert "nltk" in violations
            assert "nltk.tokenize" in violations

    def test_detects_openai_module(self) -> None:
        fake_modules = dict(sys.modules)
        fake_modules["openai"] = mock.MagicMock()

        with mock.patch.dict(sys.modules, fake_modules):
            passed, violations = check_no_forbidden_modules()
            assert not passed
            assert "openai" in violations

    def test_detects_anthropic_module(self) -> None:
        fake_modules = dict(sys.modules)
        fake_modules["anthropic"] = mock.MagicMock()

        with mock.patch.dict(sys.modules, fake_modules):
            passed, violations = check_no_forbidden_modules()
            assert not passed
            assert "anthropic" in violations

    def test_allowed_modules_not_flagged(self) -> None:
        """Standard library and non-forbidden packages are fine."""
        passed, violations = check_no_forbidden_modules()
        for v in violations:
            assert v not in ("hashlib", "json", "dataclasses", "enum", "sys")

    def test_return_types(self) -> None:
        passed, violations = check_no_forbidden_modules()
        assert isinstance(passed, bool)
        assert isinstance(violations, list)
        for v in violations:
            assert isinstance(v, str)


# =========================================================================
# TIMESTAMP_WORDS constant
# =========================================================================

class TestTimestampWordsConstant:
    """Verify the timestamp words registry."""

    def test_is_tuple(self) -> None:
        assert isinstance(TIMESTAMP_WORDS, tuple)

    def test_contains_known_words(self) -> None:
        for word in ("timestamp", "time.time", "datetime.now", "uuid"):
            assert word in TIMESTAMP_WORDS


# =========================================================================
# check_no_timestamp_words
# =========================================================================

class TestCheckNoTimestampWords:
    """Verify timestamp word scanning in object repr."""

    def test_clean_object_passes(self) -> None:
        passed, violations = check_no_timestamp_words({"key": "value", "count": 42})
        assert passed
        assert violations == []

    def test_detects_timestamp_in_string(self) -> None:
        passed, violations = check_no_timestamp_words("recorded at timestamp 12345")
        assert not passed
        assert "timestamp" in violations

    def test_detects_uuid_in_dict(self) -> None:
        passed, violations = check_no_timestamp_words({"id": "uuid-1234"})
        assert not passed
        assert "uuid" in violations

    def test_detects_datetime_now(self) -> None:
        @dataclass
        class FakeRecord:
            created: str
        record = FakeRecord(created="datetime.now()")
        passed, violations = check_no_timestamp_words(record)
        assert not passed
        assert "datetime.now" in violations

    def test_case_insensitive_detection(self) -> None:
        passed, violations = check_no_timestamp_words("TIMESTAMP field")
        assert not passed
        assert "timestamp" in violations

    def test_numeric_values_pass(self) -> None:
        passed, violations = check_no_timestamp_words(42)
        assert passed
        assert violations == []

    def test_none_passes(self) -> None:
        passed, violations = check_no_timestamp_words(None)
        assert passed
        assert violations == []

    def test_return_types(self) -> None:
        passed, violations = check_no_timestamp_words("clean text")
        assert isinstance(passed, bool)
        assert isinstance(violations, list)


# =========================================================================
# Equivalence with projection/validators.py
# =========================================================================

class TestEquivalenceWithProjectionValidators:
    """
    Verify that the safety module produces identical results to the
    original functions in projection/validators.py.
    """

    def test_forbidden_modules_match_projection(self) -> None:
        from agentic.ontology.projection.validators import (
            FORBIDDEN_MODULES as PROJ_FORBIDDEN,
        )
        assert set(FORBIDDEN_MODULES) == set(PROJ_FORBIDDEN)

    def test_timestamp_words_match_projection(self) -> None:
        from agentic.ontology.projection.validators import (
            TIMESTAMP_WORDS as PROJ_TIMESTAMPS,
        )
        assert set(TIMESTAMP_WORDS) == set(PROJ_TIMESTAMPS)

    def test_forbidden_check_same_result(self) -> None:
        from agentic.ontology.projection.validators import (
            check_no_forbidden_modules as proj_check,
        )
        safety_passed, safety_v = check_no_forbidden_modules()
        proj_passed, proj_v = proj_check()
        assert safety_passed == proj_passed
        assert set(safety_v) == set(proj_v)

    def test_timestamp_check_same_result(self) -> None:
        from agentic.ontology.projection.validators import (
            check_no_timestamp_words as proj_check,
        )
        obj = {"test": "clean_data", "count": 7}
        safety_passed, safety_v = check_no_timestamp_words(obj)
        proj_passed, proj_v = proj_check(obj)
        assert safety_passed == proj_passed
        assert safety_v == proj_v
