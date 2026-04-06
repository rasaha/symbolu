"""
Tests for Structured Output (R6)

Validates:
1. Successful structured parse/validation
2. Invalid output fails clearly
3. Raw text is preserved on failure
4. Existing run path unchanged
5. Schema-aware helper works with current adapters
6. Trace/event integration works
7. JSON-safe serialization of structured result
"""

import json
from dataclasses import dataclass

import pytest

from agentic.agentic_framework import AgenticLLMWrapper
from agentic.agentic_framework.llm_adapters import MockLLMAdapter
from agentic.agentic_framework.streaming_events import (
    RUN_COMPLETED,
    RUN_STARTED,
    STRUCTURED_VALIDATION,
)
from agentic.agentic_framework.structured_output import (
    OutputSchema,
    StructuredRunResult,
    build_schema_prompt,
    extract_json,
    schema_name as get_schema_name,
    validate_and_construct,
    _schema_description,
)


# ---------------------------------------------------------------------------
# Test schemas
# ---------------------------------------------------------------------------

@dataclass
class City:
    name: str
    country: str
    population: int


@dataclass
class WithDefaults:
    required_field: str
    optional_field: str = "default_value"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LONG = " " * 200  # padding to pass quality checks


def _make_agent(response_text, **kwargs):
    """Create agent that returns a specific text."""
    llm = MockLLMAdapter(default_response=response_text + _LONG)
    defaults = dict(
        use_llm_for_decomposition=False,
        max_revisions=0,
        quality_threshold=0.3,
    )
    defaults.update(kwargs)
    agent = AgenticLLMWrapper(llm, **defaults)
    agent.new_session()
    return agent


# ===================================================================
# 1. Successful structured parse/validation
# ===================================================================

class TestSuccessfulParse:
    def test_dataclass_schema(self):
        resp = '{"name": "Paris", "country": "France", "population": 2161000}'
        agent = _make_agent(resp)
        result = agent.run_structured("Capital of France?", schema=City)
        assert result.success is True
        assert isinstance(result.parsed_output, City)
        assert result.parsed_output.name == "Paris"
        assert result.parsed_output.country == "France"
        assert result.parsed_output.population == 2161000

    def test_dict_schema(self):
        resp = '{"color": "blue", "count": 5}'
        agent = _make_agent(resp)
        schema = {"color": str, "count": int}
        result = agent.run_structured("Pick a color", schema=schema)
        assert result.success is True
        assert result.parsed_output["color"] == "blue"
        assert result.parsed_output["count"] == 5

    def test_json_in_markdown_fences(self):
        resp = '```json\n{"name": "Tokyo", "country": "Japan", "population": 14000000}\n```'
        agent = _make_agent(resp)
        result = agent.run_structured("Capital of Japan?", schema=City)
        assert result.success is True
        assert result.parsed_output.name == "Tokyo"

    def test_json_with_preamble(self):
        resp = 'Here is the answer:\n{"name": "Berlin", "country": "Germany", "population": 3600000}\nThat is all.'
        agent = _make_agent(resp)
        result = agent.run_structured("Capital of Germany?", schema=City)
        assert result.success is True
        assert result.parsed_output.name == "Berlin"

    def test_dataclass_with_defaults(self):
        resp = '{"required_field": "hello"}'
        agent = _make_agent(resp)
        result = agent.run_structured("test", schema=WithDefaults)
        assert result.success is True
        assert result.parsed_output.required_field == "hello"
        assert result.parsed_output.optional_field == "default_value"

    def test_quality_score_propagated(self):
        resp = '{"name": "Rome", "country": "Italy", "population": 2873000}'
        agent = _make_agent(resp)
        result = agent.run_structured("Capital of Italy?", schema=City)
        assert result.quality_score > 0


# ===================================================================
# 2. Invalid output fails clearly
# ===================================================================

class TestInvalidOutput:
    def test_no_json_in_response(self):
        agent = _make_agent("I don't know the answer, sorry.")
        result = agent.run_structured("Capital?", schema=City)
        assert result.success is False
        assert result.validation_error is not None
        assert "JSON" in result.validation_error

    def test_missing_required_field(self):
        resp = '{"name": "Paris", "country": "France"}'  # missing population
        agent = _make_agent(resp)
        result = agent.run_structured("Capital?", schema=City)
        assert result.success is False
        assert "population" in result.validation_error.lower() or "missing" in result.validation_error.lower()

    def test_wrong_type_in_dict_schema(self):
        resp = '{"color": 123, "count": 5}'
        agent = _make_agent(resp)
        schema = {"color": str, "count": int}
        result = agent.run_structured("Pick", schema=schema)
        assert result.success is False
        assert "color" in result.validation_error

    def test_missing_field_in_dict_schema(self):
        resp = '{"color": "red"}'
        agent = _make_agent(resp)
        schema = {"color": str, "count": int}
        result = agent.run_structured("Pick", schema=schema)
        assert result.success is False
        assert "count" in result.validation_error.lower() or "missing" in result.validation_error.lower()

    def test_malformed_json(self):
        agent = _make_agent('{"name": "Paris", broken}')
        result = agent.run_structured("Capital?", schema=City)
        assert result.success is False


# ===================================================================
# 3. Raw text preserved on failure
# ===================================================================

class TestRawTextPreserved:
    def test_raw_text_on_failure(self):
        agent = _make_agent("This is not JSON at all.")
        result = agent.run_structured("Hello", schema=City)
        assert result.success is False
        assert "This is not JSON at all." in result.raw_text

    def test_raw_text_on_success(self):
        resp = '{"name": "Paris", "country": "France", "population": 2161000}'
        agent = _make_agent(resp)
        result = agent.run_structured("Capital?", schema=City)
        assert result.success is True
        assert resp in result.raw_text


# ===================================================================
# 4. Existing run path unchanged
# ===================================================================

class TestExistingPathUnchanged:
    def test_run_unchanged(self):
        agent = _make_agent("Normal response text")
        result = agent.run("Hello")
        assert "Normal response text" in result.response

    def test_run_stream_unchanged(self):
        agent = _make_agent("Stream response text")
        events = list(agent.run_stream("Hello"))
        types = [e.event_type for e in events]
        assert types[0] == RUN_STARTED
        assert types[-1] == RUN_COMPLETED


# ===================================================================
# 5. Schema-aware helper works with current adapters
# ===================================================================

class TestSchemaHelper:
    def test_build_schema_prompt_contains_fields(self):
        prompt = build_schema_prompt("What is the capital?", City)
        assert '"name"' in prompt
        assert '"country"' in prompt
        assert '"population"' in prompt
        assert "JSON" in prompt

    def test_build_schema_prompt_dict(self):
        prompt = build_schema_prompt("Pick", {"color": str, "count": int})
        assert '"color"' in prompt
        assert '"count"' in prompt

    def test_schema_description_dataclass(self):
        desc = _schema_description(City)
        assert '"name"' in desc
        assert '"country"' in desc
        assert '"population"' in desc

    def test_extract_json_plain(self):
        result = extract_json('{"a": 1}')
        assert result == {"a": 1}

    def test_extract_json_fenced(self):
        result = extract_json('```json\n{"a": 1}\n```')
        assert result == {"a": 1}

    def test_extract_json_none_on_failure(self):
        result = extract_json("no json here")
        assert result is None

    def test_validate_and_construct_dataclass(self):
        obj = validate_and_construct(
            {"name": "Paris", "country": "France", "population": 2161000},
            City,
        )
        assert isinstance(obj, City)
        assert obj.name == "Paris"

    def test_validate_and_construct_dict_schema(self):
        obj = validate_and_construct({"x": 1}, {"x": int})
        assert obj == {"x": 1}

    def test_validate_and_construct_raises_on_missing(self):
        with pytest.raises(ValueError, match="[Mm]issing"):
            validate_and_construct({"name": "Paris"}, City)


# ===================================================================
# 6. Trace/event integration
# ===================================================================

class TestTraceIntegration:
    def test_run_structured_with_trace_returns_trace(self):
        resp = '{"name": "Paris", "country": "France", "population": 2161000}'
        agent = _make_agent(resp)
        sr, trace = agent.run_structured_with_trace("Capital?", schema=City)
        assert sr.success is True
        assert trace.event_count > 0

    def test_structured_validation_event_in_trace(self):
        resp = '{"name": "Paris", "country": "France", "population": 2161000}'
        agent = _make_agent(resp)
        sr, trace = agent.run_structured_with_trace("Capital?", schema=City)
        assert trace.has_event_type(STRUCTURED_VALIDATION)
        val_events = trace.get_events(STRUCTURED_VALIDATION)
        assert len(val_events) == 1
        assert val_events[0].payload["success"] is True

    def test_validation_failure_in_trace(self):
        agent = _make_agent("Not JSON")
        sr, trace = agent.run_structured_with_trace("Hello", schema=City)
        assert sr.success is False
        val_events = trace.get_events(STRUCTURED_VALIDATION)
        assert len(val_events) == 1
        assert val_events[0].payload["success"] is False
        assert val_events[0].payload["validation_error"] is not None

    def test_trace_still_has_lifecycle_events(self):
        resp = '{"name": "Tokyo", "country": "Japan", "population": 14000000}'
        agent = _make_agent(resp)
        _, trace = agent.run_structured_with_trace("Capital?", schema=City)
        assert trace.has_event_type(RUN_STARTED)
        assert trace.has_event_type(RUN_COMPLETED)


# ===================================================================
# 7. JSON-safe serialization
# ===================================================================

class TestSerialization:
    def test_structured_result_to_dict(self):
        resp = '{"name": "Paris", "country": "France", "population": 2161000}'
        agent = _make_agent(resp)
        result = agent.run_structured("Capital?", schema=City)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["success"] is True
        assert d["parsed_output"]["name"] == "Paris"

    def test_structured_result_json_serializable(self):
        resp = '{"name": "Paris", "country": "France", "population": 2161000}'
        agent = _make_agent(resp)
        result = agent.run_structured("Capital?", schema=City)
        json_str = json.dumps(result.to_dict())
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["success"] is True

    def test_failure_result_to_dict(self):
        agent = _make_agent("No JSON here")
        result = agent.run_structured("Hello", schema=City)
        d = result.to_dict()
        assert d["success"] is False
        assert d["parsed_output"] is None
        assert d["validation_error"] is not None

    def test_dict_schema_result_serializable(self):
        resp = '{"x": 1, "y": 2}'
        agent = _make_agent(resp)
        result = agent.run_structured("Numbers", schema={"x": int, "y": int})
        json_str = json.dumps(result.to_dict())
        parsed = json.loads(json_str)
        assert parsed["parsed_output"]["x"] == 1


# ===================================================================
# 8. Extra fields in response are handled gracefully
# ===================================================================

class TestExtraFields:
    def test_extra_fields_ignored_for_dataclass(self):
        resp = '{"name": "Paris", "country": "France", "population": 2161000, "extra": true}'
        agent = _make_agent(resp)
        result = agent.run_structured("Capital?", schema=City)
        assert result.success is True
        assert result.parsed_output.name == "Paris"
        assert not hasattr(result.parsed_output, "extra")


# ===================================================================
# 9. schema_name populated correctly
# ===================================================================

class TestSchemaName:
    def test_schema_name_dataclass(self):
        resp = '{"name": "Paris", "country": "France", "population": 2161000}'
        agent = _make_agent(resp)
        result = agent.run_structured("Capital?", schema=City)
        assert result.schema_name == "City"

    def test_schema_name_dict(self):
        resp = '{"color": "blue", "count": 5}'
        agent = _make_agent(resp)
        result = agent.run_structured("Pick", schema={"color": str, "count": int})
        assert result.schema_name == "dict_schema"

    def test_schema_name_on_failure(self):
        agent = _make_agent("no json")
        result = agent.run_structured("Hello", schema=City)
        assert result.schema_name == "City"

    def test_schema_name_in_trace_event(self):
        resp = '{"name": "Paris", "country": "France", "population": 2161000}'
        agent = _make_agent(resp)
        _, trace = agent.run_structured_with_trace("Capital?", schema=City)
        val_events = trace.get_events(STRUCTURED_VALIDATION)
        assert val_events[0].payload["schema_name"] == "City"

    def test_schema_name_in_to_dict(self):
        resp = '{"name": "Paris", "country": "France", "population": 2161000}'
        agent = _make_agent(resp)
        result = agent.run_structured("Capital?", schema=City)
        d = result.to_dict()
        assert d["schema_name"] == "City"

    def test_get_schema_name_helper(self):
        assert get_schema_name(City) == "City"
        assert get_schema_name({"x": int}) == "dict_schema"


# ===================================================================
# 10. OutputSchema alias
# ===================================================================

class TestOutputSchema:
    def test_output_schema_is_schema_target(self):
        from agentic.agentic_framework.structured_output import SchemaTarget
        assert OutputSchema is SchemaTarget


# ===================================================================
# 11. JSON extraction: bracket-matching handles nested/tricky cases
# ===================================================================

class TestJsonExtractionAdvanced:
    def test_nested_objects(self):
        text = 'Here: {"a": {"b": 1}, "c": 2} done'
        result = extract_json(text)
        assert result == {"a": {"b": 1}, "c": 2}

    def test_string_with_braces(self):
        text = '{"msg": "use { and } carefully", "ok": true}'
        result = extract_json(text)
        assert result == {"msg": "use { and } carefully", "ok": True}

    def test_json_after_long_preamble(self):
        text = "Let me think about this.\nThe answer is:\n" + '{"name": "Paris", "country": "France", "population": 2161000}'
        result = extract_json(text)
        assert result["name"] == "Paris"

    def test_fenced_preferred_over_inline(self):
        # If fenced block exists, prefer it
        text = 'Inline: {"a": 1}\n```json\n{"a": 2}\n```'
        result = extract_json(text)
        assert result == {"a": 2}  # fenced wins
