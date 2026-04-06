"""
Structured Output — Schema-Enforced Responses (R6)

Provides schema-aware generation and validation on top of the existing
agent pipeline.  The LLM is prompted to return JSON matching a schema;
the response is parsed and validated at the runtime layer.

Supported schema targets:
- **dataclass** — fields introspected, instance constructed from parsed dict
- **dict schema** — ``{"field": type, ...}`` validated by key/type check
- **Pydantic model** — duck-typed via ``model_validate()``, no import needed

Usage::

    from dataclasses import dataclass

    @dataclass
    class City:
        name: str
        country: str
        population: int

    result = agent.run_structured("Capital of France?", schema=City)
    if result.success:
        print(result.parsed)  # City(name='Paris', ...)
"""

from __future__ import annotations

import dataclasses
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, Union


# ---------------------------------------------------------------------------
# Schema descriptor
# ---------------------------------------------------------------------------

# A schema target is either a type (dataclass / Pydantic model) or a
# dict mapping field names to expected Python types.
SchemaTarget = Union[Type[Any], Dict[str, type]]

# Alias requested by R6 spec — use either name interchangeably.
OutputSchema = SchemaTarget


def _schema_description(schema: SchemaTarget) -> str:
    """Build a human-readable JSON schema hint for the LLM prompt."""
    fields = _extract_fields(schema)
    lines = ["{"]
    for i, (name, type_name) in enumerate(fields):
        comma = "," if i < len(fields) - 1 else ""
        lines.append(f'  "{name}": <{type_name}>{comma}')
    lines.append("}")
    return "\n".join(lines)


def _extract_fields(schema: SchemaTarget) -> List[tuple[str, str]]:
    """Return ``[(field_name, type_label), ...]`` for any supported schema."""
    if isinstance(schema, dict):
        return [(k, _type_label(v)) for k, v in schema.items()]

    # dataclass
    if dataclasses.is_dataclass(schema) and isinstance(schema, type):
        return [
            (f.name, _type_label(f.type))
            for f in dataclasses.fields(schema)
        ]

    # Pydantic model (duck-typed)
    model_fields = getattr(schema, "model_fields", None)
    if model_fields and isinstance(model_fields, dict):
        return [
            (name, _type_label(getattr(info, "annotation", Any)))
            for name, info in model_fields.items()
        ]

    # Fallback: __annotations__
    annotations = getattr(schema, "__annotations__", {})
    if annotations:
        return [(k, _type_label(v)) for k, v in annotations.items()]

    return []


def _type_label(tp: Any) -> str:
    """Human-friendly type name for prompt hints."""
    if isinstance(tp, str):
        return tp
    if tp is Any:
        return "any"
    name = getattr(tp, "__name__", None)
    if name:
        return name
    return str(tp)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_SCHEMA_INSTRUCTION = """
Respond ONLY with valid JSON matching this exact schema — no markdown fences, no extra text:
{schema}
"""


def schema_name(schema: SchemaTarget) -> str:
    """Return a short human-readable name for *schema*."""
    if isinstance(schema, dict):
        return "dict_schema"
    return getattr(schema, "__name__", str(schema))


def build_schema_prompt(user_input: str, schema: SchemaTarget) -> str:
    """Augment *user_input* with a schema instruction suffix."""
    desc = _schema_description(schema)
    return user_input + _SCHEMA_INSTRUCTION.format(schema=desc)


# ---------------------------------------------------------------------------
# JSON extraction + validation
# ---------------------------------------------------------------------------


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort extraction of a JSON object from LLM text.

    Strategy (ordered):
      a. Prefer fenced ``json`` blocks if present.
      b. Locate the first valid JSON object substring via bracket-matching.
      c. Regex fallback for the outermost ``{ ... }``.
    """
    # --- (a) fenced json blocks ---
    fence_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)```", text)
    if fence_match:
        try:
            obj = json.loads(fence_match.group(1).strip())
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError):
            pass

    # Try full text as-is (covers bare JSON responses)
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, ValueError):
        pass

    # --- (b) bracket-matching: find first balanced { ... } substring ---
    result = _find_json_object(text)
    if result is not None:
        return result

    # --- (c) regex fallback for outermost { ... } ---
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            obj = json.loads(match.group())
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def _find_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Scan *text* for the first balanced ``{…}`` substring and parse it.

    Uses bracket counting rather than regex so it handles nested objects
    and strings containing braces correctly.
    """
    i = text.find("{")
    while i != -1:
        depth = 0
        in_string = False
        escape = False
        for j in range(i, len(text)):
            ch = text[j]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[i : j + 1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            return obj
                    except (json.JSONDecodeError, ValueError):
                        break  # this opening brace didn't lead to valid JSON
        # Try next opening brace
        i = text.find("{", i + 1)
    return None


def validate_and_construct(
    data: Dict[str, Any],
    schema: SchemaTarget,
) -> Any:
    """Validate *data* against *schema* and return a constructed instance.

    Raises ``ValueError`` on validation failure.
    """
    # --- dict schema ---
    if isinstance(schema, dict):
        missing = [k for k in schema if k not in data]
        if missing:
            raise ValueError(f"Missing fields: {missing}")
        for key, expected_type in schema.items():
            val = data[key]
            if expected_type is Any:
                continue
            if not isinstance(val, expected_type):
                # Allow int where float expected and vice-versa
                if expected_type in (int, float) and isinstance(val, (int, float)):
                    continue
                raise ValueError(
                    f"Field '{key}': expected {expected_type.__name__}, "
                    f"got {type(val).__name__}"
                )
        return data

    # --- Pydantic model (duck-typed) ---
    model_validate = getattr(schema, "model_validate", None)
    if callable(model_validate):
        return model_validate(data)

    # --- dataclass ---
    if dataclasses.is_dataclass(schema) and isinstance(schema, type):
        field_names = {f.name for f in dataclasses.fields(schema)}
        filtered = {k: v for k, v in data.items() if k in field_names}
        missing = field_names - set(filtered.keys())
        # Allow missing fields that have defaults
        for f in dataclasses.fields(schema):
            if f.name in missing:
                if (
                    f.default is not dataclasses.MISSING
                    or f.default_factory is not dataclasses.MISSING  # type: ignore[arg-type]
                ):
                    missing.discard(f.name)
        if missing:
            raise ValueError(f"Missing required fields: {sorted(missing)}")
        return schema(**filtered)

    # --- fallback: just return data ---
    return data


# ---------------------------------------------------------------------------
# Structured result model
# ---------------------------------------------------------------------------


@dataclass
class StructuredRunResult:
    """Result of a structured-output agent run.

    Fields:
        success: Whether parsing and validation succeeded.
        raw_text: The raw LLM response text (always present).
        parsed_output: The validated/constructed output, or ``None`` on failure.
        validation_error: Human-readable error string on failure.
        schema_name: Name of the target schema (for diagnostics/logging).
        quality_score: Quality score from the underlying generation.
        revision_count: Revision count from the underlying generation.
    """

    success: bool
    raw_text: str
    parsed_output: Any = None
    validation_error: Optional[str] = None
    schema_name: Optional[str] = None
    quality_score: float = 0.0
    revision_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-safe dict.

        ``parsed_output`` is converted via ``dataclasses.asdict`` if it
        is a dataclass, or left as-is if it is already a dict.
        """
        parsed_serialised: Any = None
        if self.parsed_output is not None:
            if dataclasses.is_dataclass(self.parsed_output) and not isinstance(self.parsed_output, type):
                parsed_serialised = dataclasses.asdict(self.parsed_output)
            elif hasattr(self.parsed_output, "model_dump"):
                parsed_serialised = self.parsed_output.model_dump()
            else:
                parsed_serialised = self.parsed_output
        return {
            "success": self.success,
            "raw_text": self.raw_text,
            "parsed_output": parsed_serialised,
            "validation_error": self.validation_error,
            "schema_name": self.schema_name,
            "quality_score": self.quality_score,
            "revision_count": self.revision_count,
        }
