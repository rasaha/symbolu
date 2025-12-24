# Test Coverage Analysis Report

## Executive Summary

This report analyzes the test coverage of the Symbol-U codebase and identifies areas for improvement. The codebase has **306 test files** covering a sophisticated deterministic AGI engine, but several critical modules lack adequate test coverage.

---

## Current Test Infrastructure

### Testing Framework
- **Framework**: pytest
- **Configuration**: `conftest.py` at project root
- **Coverage Tooling**: None configured (no `.coveragerc` or pytest-cov in `pyproject.toml`)

### Test Distribution Summary

| Location | Test Files | Coverage Quality |
|----------|-----------|------------------|
| `/tests/` (root) | 75 | Good - Phase validation, invariance audits |
| `/tests/integration/` | 6 | Good - Cross-module integration |
| `/symbolu/mechanical/pipeline/` | 70+ | Excellent - Comprehensive phase tests |
| `/symbolu/core/coherence/` | 8 | Good - Coherence v3 quality |
| `/symbolu/service/tests/` | 6 | Moderate - API server basics |
| **Total** | **306** | - |

---

## Critical Coverage Gaps

### Priority 1: Modules with No Tests

These modules have **zero test coverage** and contain critical functionality:

#### 1. `symbolu/llm/` - LLM Contract Validator
- **Files**: `types.py`, `validator.py`
- **Risk Level**: **HIGH**
- **What it does**: Validates LLM responses against Symbol-U contracts, enforces invariants (INV-1 through INV-7)
- **Why it matters**: This is a security-critical module that prevents unauthorized structure addition, governance overrides, and selection behavior from LLMs
- **Recommended tests**:
  - Unit tests for `validate_tokens()`, `validate_layers()`, `validate_forbidden_phrases()`
  - Integration tests with mock RenderRequest/RenderResponse objects
  - Edge cases: empty allowed_tokens, malformed responses, provenance hash validation
  - Contract violation detection tests

#### 2. `symbolu/api/` - Unified API Output
- **Files**: `unified_api.py`, `coherence_api.py`
- **Risk Level**: **HIGH**
- **What it does**: Assembles complete API output from 55+ pipeline phases, provides public-facing response schemas
- **Why it matters**: This is the primary external interface; bugs here corrupt all downstream consumers
- **Recommended tests**:
  - Unit tests for `build_unified_output()` with mock PipelineContext
  - Schema validation tests for `UnifiedOutput.to_dict()`
  - Helper function tests: `_remove_none_values()`, `_get_coherence_state_label()`
  - Public response trimming tests for session memory/recap

#### 3. `symbolu/safety/` - GCC Runtime Guards
- **Files**: `gcc_runtime_guard.py`, `gcc_ledger_invariant.py`, `gcc_static_scanner.py`
- **Risk Level**: **CRITICAL**
- **What it does**: Enforces Generative Containment Constraints, validates non-expressive values
- **Why it matters**: Safety-critical code that ensures fail-closed behavior; violations could allow expressive content leakage
- **Recommended tests**:
  - Unit tests for `is_non_expressive()` with all allowed types (int, bool, Enum, hex strings, tuples, frozensets, frozen dataclasses)
  - Violation tests for lists, dicts, free-form strings, mutable dataclasses
  - `@gcc_guarded` decorator tests
  - `GCCViolationError` exception handling tests

#### 4. `symbolu/hybrid/` - Hybrid Router & Prefilter
- **Files**: `router.py`, `prefilter.py`, `benchmark.py`, `attention.py`
- **Risk Level**: **MEDIUM-HIGH**
- **What it does**: Hybrid execution modes, prefiltering logic, attention mechanisms
- **Why it matters**: Affects routing decisions and response generation paths
- **Recommended tests**:
  - Router mode selection tests
  - Prefilter threshold tests
  - Benchmark determinism tests

#### 5. `symbolu/ppv/` - Phonetic Positional Vectors
- **Files**: `ppv_contract_v1.py`, `ppv_builder_v1.py`
- **Risk Level**: **MEDIUM**
- **What it does**: Builds phonetic positional vector representations
- **Why it matters**: Core acoustic processing used in early pipeline phases
- **Recommended tests**:
  - Contract validation tests
  - Builder output determinism tests
  - Edge cases with empty/special characters

#### 6. `symbolu/tools/` - Various Tools Lacking Tests

| Tool | Risk | Description |
|------|------|-------------|
| `heatmaps/` | LOW | Fusion/persona/mapper heatmap visualization |
| `boundary_enforcer/` | MEDIUM | Import scanning and boundary rules |
| `scenario_simulator/` | MEDIUM | Scenario what-if simulation |
| `coherence_dashboard/` | LOW | Dashboard report generation |
| `drift_dashboard/` | LOW | Drift visualization |

---

### Priority 2: Under-Tested Critical Modules

These modules have tests but need more comprehensive coverage:

#### 1. `symbolu/service/security/` - API Security
- **Current state**: `test_api_security.py` exists but coverage is limited
- **Missing coverage**:
  - Rate limiter edge cases (burst handling, window expiration)
  - API key validation failure modes
  - Concurrent request handling
  - Security bypass attempts

#### 2. `symbolu/rag/` - Retrieval-Augmented Generation
- **Current state**: 3 test files exist
- **Missing coverage**:
  - Vector store operations (CRUD, similarity search)
  - Embedding generation edge cases
  - Ingestion pipeline failures
  - Context stitching with incomplete data

#### 3. `symbolu/ontology/` - Ontology System
- **Current state**: Basic freeze contract tests exist
- **Missing coverage**:
  - Ontology projection edge cases
  - Router determinism under edge conditions
  - Layer visibility policy enforcement
  - Checksum validation failures

---

### Priority 3: Test Infrastructure Improvements

#### 1. Add Coverage Tooling

Create `.coveragerc`:
```ini
[run]
source = symbolu
omit =
    */tests/*
    */__pycache__/*
    */conftest.py

[report]
exclude_lines =
    pragma: no cover
    raise NotImplementedError
    if TYPE_CHECKING:

show_missing = True
fail_under = 70
```

Update `pyproject.toml`:
```toml
[project.optional-dependencies]
test = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "pytest-xdist>=3.0",
]

[tool.pytest.ini_options]
addopts = "--cov=symbolu --cov-report=html --cov-report=term-missing"
```

#### 2. Add Integration Test Fixtures

Create shared fixtures for common test scenarios:
- Mock PipelineContext with all phase outputs
- Mock CoherenceState with history data
- Mock SessionStore for multi-turn tests
- Mock LLM responses for contract validation

#### 3. Add Property-Based Testing

For determinism-critical modules, use `hypothesis`:
```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1, max_size=100))
def test_is_hex_string_deterministic(s):
    result1 = _is_hex_string(s)
    result2 = _is_hex_string(s)
    assert result1 == result2
```

---

## Recommended Test Implementation Order

### Phase 1: Critical Safety (High Priority)

1. **`symbolu/safety/gcc_runtime_guard.py`** - 20+ tests
   - Non-expressive value validation
   - Violation exception handling
   - Decorator functionality

2. **`symbolu/llm/validator.py`** - 25+ tests
   - Token/layer validation
   - Forbidden phrase detection
   - Contract invariant enforcement

### Phase 2: Core API (High Priority)

3. **`symbolu/api/unified_api.py`** - 15+ tests
   - Output assembly
   - Schema validation
   - Public response trimming

4. **`symbolu/service/api_server.py`** - Expand existing tests
   - Session endpoints
   - Preference endpoints
   - Error handling edge cases

### Phase 3: Infrastructure (Medium Priority)

5. **`symbolu/hybrid/`** - 10+ tests per file
6. **`symbolu/ppv/`** - 10+ tests
7. **Coverage tooling setup**

### Phase 4: Tools & Utilities (Lower Priority)

8. **`symbolu/tools/heatmaps/`**
9. **`symbolu/tools/boundary_enforcer/`**
10. **`symbolu/tools/scenario_simulator/`**

---

## Specific Test Recommendations

### For `symbolu/llm/validator.py`

```python
# tests/test_llm_validator.py

import pytest
from symbolu.llm.validator import (
    validate_tokens,
    validate_layers,
    validate_forbidden_phrases,
    validate_provenance,
    validate_llm_response,
)
from symbolu.llm.types import (
    RenderRequest,
    RenderResponse,
    ContractViolationType,
)

class TestValidateTokens:
    def test_allows_valid_tokens(self):
        """Tokens in allowed_tokens should not raise violations."""
        # Create request with allowed_tokens = ["ka", "ga"]
        # Create response using those tokens
        # Assert no violations

    def test_rejects_unknown_tokens(self):
        """Tokens not in allowed_tokens should raise violations."""

    def test_empty_allowed_tokens_skips_validation(self):
        """Empty allowed_tokens should skip token validation."""

class TestValidateForbiddenPhrases:
    @pytest.mark.parametrize("phrase", [
        "ignore the constraint",
        "override the policy",
        "bypass validation",
        "skip phase 3",
    ])
    def test_detects_override_patterns(self, phrase):
        """Override patterns should trigger GOVERNANCE_OVERRIDE violation."""

    @pytest.mark.parametrize("phrase", [
        "best option is",
        "recommend that you",
        "should pick the",
    ])
    def test_detects_selection_patterns(self, phrase):
        """Selection patterns should trigger SELECTION violation."""
```

### For `symbolu/safety/gcc_runtime_guard.py`

```python
# tests/test_gcc_runtime_guard.py

import pytest
from dataclasses import dataclass
from enum import Enum
from symbolu.safety.gcc_runtime_guard import (
    is_non_expressive,
    assert_non_expressive,
    GCCViolationError,
    gcc_guarded,
)

class SampleEnum(Enum):
    VALUE_A = 1
    VALUE_B = 2

@dataclass(frozen=True)
class FrozenData:
    count: int
    flag: bool

class TestIsNonExpressive:
    def test_none_is_allowed(self):
        assert is_non_expressive(None) is True

    def test_int_is_allowed(self):
        assert is_non_expressive(42) is True
        assert is_non_expressive(0) is True
        assert is_non_expressive(-100) is True

    def test_bool_is_allowed(self):
        assert is_non_expressive(True) is True
        assert is_non_expressive(False) is True

    def test_enum_is_allowed(self):
        assert is_non_expressive(SampleEnum.VALUE_A) is True

    def test_hex_string_is_allowed(self):
        assert is_non_expressive("deadbeef") is True
        assert is_non_expressive("0123456789abcdef") is True

    def test_invariant_key_is_allowed(self):
        assert is_non_expressive("NON_EXPRESSIVE") is True
        assert is_non_expressive("PHASE_1B") is True

    def test_tuple_of_allowed_is_allowed(self):
        assert is_non_expressive((1, 2, 3)) is True
        assert is_non_expressive((True, False)) is True

    def test_frozen_dataclass_is_allowed(self):
        assert is_non_expressive(FrozenData(count=5, flag=True)) is True

    # Violation tests
    def test_list_is_violation(self):
        assert is_non_expressive([1, 2, 3]) is False

    def test_dict_is_violation(self):
        assert is_non_expressive({"key": "value"}) is False

    def test_free_text_is_violation(self):
        assert is_non_expressive("Hello world") is False
        assert is_non_expressive("This is a sentence.") is False

class TestAssertNonExpressive:
    def test_raises_on_list(self):
        with pytest.raises(GCCViolationError) as exc_info:
            assert_non_expressive([1, 2, 3])
        assert exc_info.value.reason == GCCViolationError.REASON_MUTABLE_CONTAINER

    def test_raises_on_free_text(self):
        with pytest.raises(GCCViolationError) as exc_info:
            assert_non_expressive("Hello world")
        assert exc_info.value.reason == GCCViolationError.REASON_FREE_TEXT
```

### For `symbolu/api/unified_api.py`

```python
# tests/test_unified_api.py

import pytest
from unittest.mock import MagicMock
from symbolu.api.unified_api import (
    build_unified_output,
    get_unified_json,
    get_public_response,
    _remove_none_values,
    _get_coherence_state_label,
)

class TestRemoveNoneValues:
    def test_removes_none_at_top_level(self):
        d = {"a": 1, "b": None, "c": 3}
        result = _remove_none_values(d)
        assert result == {"a": 1, "c": 3}

    def test_removes_none_nested(self):
        d = {"outer": {"a": 1, "b": None}}
        result = _remove_none_values(d)
        assert result == {"outer": {"a": 1}}

    def test_handles_lists(self):
        d = {"items": [1, None, 3]}
        result = _remove_none_values(d)
        assert result == {"items": [1, None, 3]}  # None in lists preserved

class TestGetCoherenceStateLabel:
    @pytest.mark.parametrize("score,expected", [
        (0.90, "Excellent"),
        (0.85, "Excellent"),
        (0.75, "Good"),
        (0.70, "Good"),
        (0.60, "Fair"),
        (0.50, "Fair"),
        (0.40, "Poor"),
        (0.0, "Poor"),
    ])
    def test_score_to_label(self, score, expected):
        assert _get_coherence_state_label(score) == expected

class TestBuildUnifiedOutput:
    def test_handles_minimal_context(self):
        ctx = MagicMock()
        ctx.fusion = None
        ctx.dha = None
        ctx.mlcr = None
        ctx.coherence_report = None
        ctx.coherence_state = None
        ctx.request = None

        output = build_unified_output("test text", ctx)
        assert output.text == "test text"
        assert output.symbolic == {}
        assert output.practical == {}
```

---

## Summary of Recommendations

| Priority | Module | Estimated Tests | Effort |
|----------|--------|-----------------|--------|
| Critical | `safety/gcc_runtime_guard.py` | 25+ | Medium |
| Critical | `llm/validator.py` | 30+ | Medium |
| High | `api/unified_api.py` | 20+ | Medium |
| High | `hybrid/router.py` | 15+ | Medium |
| Medium | `ppv/ppv_builder_v1.py` | 10+ | Low |
| Medium | `tools/boundary_enforcer/` | 10+ | Low |
| Low | `tools/heatmaps/` | 5+ | Low |
| Infrastructure | Coverage tooling | - | Low |

**Total estimated new tests: ~120+**

---

## Next Steps

1. Set up pytest-cov and establish baseline coverage metrics
2. Create shared test fixtures for mock objects
3. Implement Priority 1 tests (safety, LLM validation)
4. Implement Priority 2 tests (API, service layer)
5. Add CI/CD coverage thresholds
6. Consider property-based testing for determinism-critical modules

---

*Report generated: 2025-12-20*
*Codebase version: 0.1.0*
