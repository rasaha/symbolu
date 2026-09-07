"""The intake gate every converter runs before it reads a construct (CV-4).

Same figures as the Bring Your Workflow surface (BW-2): 1 MiB, depth 32, 200
constructs. The secret scan is the compiler's own shape (validation/provenance.py)
plus the token shapes the studio gate refuses, applied to the whole export before
conversion: an export carrying a secret is refused outright, with no output, rather
than converted with the secret dropped. Nothing here fetches, executes or stores.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Any, List, Mapping, Tuple

from ugence_policy_workflow_compiler.serialization import hashing

from .report import ConversionRefused, RefusalCode

MAX_INPUT_BYTES = 1024 * 1024
MAX_DEPTH = 32
MAX_CONSTRUCTS = 200
MAX_ELEMENTS = 50_000

SECRET_KEY = re.compile(
    r"(password|passwd|secret|api[_-]?key|access[_-]?key|private[_-]?key|bearer[_-]?token|"
    r"client[_-]?secret|auth[_-]?token|refresh[_-]?token)s?$",
    re.IGNORECASE,
)
SECRET_VALUE = (
    re.compile(r"-----BEGIN[^-]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bBearer\s+ey[A-Za-z0-9._-]{10,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\b(password|secret|api[_-]?key|token)\s*[:=]\s*\S+", re.IGNORECASE),
)


def parse_export(data: bytes) -> tuple[dict, str]:
    """Bytes in; a parsed object and its digest out, or a typed refusal."""
    if len(data) > MAX_INPUT_BYTES:
        raise ConversionRefused(RefusalCode.TOO_LARGE, f"{len(data)} bytes exceed {MAX_INPUT_BYTES}")
    try:
        text = data.decode("utf-8")
        parsed = json.loads(text)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ConversionRefused(RefusalCode.NOT_JSON, f"not UTF-8 JSON: {exc}; YAML, code and archives are never accepted")
    if not isinstance(parsed, dict):
        raise ConversionRefused(RefusalCode.NOT_AN_OBJECT, "an export is a JSON object")
    measure(parsed)
    scan_secrets(parsed)
    return parsed, hashing.digest_bytes(data)


#: A document type declaration or an entity declaration is refused before the parser
#: sees the bytes: the stdlib parser expands internal entities, so an export carrying
#: one could inflate or smuggle content. A BPMN export needs neither.
XML_DECLARATION = re.compile(rb"<!\s*(DOCTYPE|ENTITY)\b", re.IGNORECASE)


def parse_xml_export(data: bytes) -> Tuple[ET.Element, str]:
    """Bytes in; an element tree root and its digest out, or a typed refusal."""
    if len(data) > MAX_INPUT_BYTES:
        raise ConversionRefused(RefusalCode.TOO_LARGE, f"{len(data)} bytes exceed {MAX_INPUT_BYTES}")
    if XML_DECLARATION.search(data):
        raise ConversionRefused(RefusalCode.NOT_AN_EXPORT_OF_THIS_FORMAT, "a document type or entity declaration is never accepted")
    try:
        text = data.decode("utf-8")
        root = ET.fromstring(text)
    except (UnicodeDecodeError, ET.ParseError) as exc:
        raise ConversionRefused(RefusalCode.NOT_XML, f"not UTF-8 XML: {exc}; YAML, code and archives are never accepted")
    measure_xml(root)
    scan_xml_secrets(root)
    return root, hashing.digest_bytes(data)


def measure_xml(root: ET.Element) -> dict:
    depth = elements = 0
    stack: List[Tuple[ET.Element, int]] = [(root, 1)]
    while stack:
        element, level = stack.pop()
        elements += 1
        if elements > MAX_ELEMENTS:
            raise ConversionRefused(RefusalCode.TOO_LARGE, f"more than {MAX_ELEMENTS} elements")
        depth = max(depth, level)
        if depth > MAX_DEPTH:
            raise ConversionRefused(RefusalCode.TOO_DEEP, f"nesting deeper than {MAX_DEPTH}")
        stack.extend((child, level + 1) for child in element)
    return {"depth": depth, "elements": elements}


def scan_xml_secrets(root: ET.Element) -> None:
    """Refuse a secret-shaped attribute name with a value, a name/value pair naming a
    secret, or a secret-shaped attribute value or text, anywhere."""
    stack: List[Tuple[ET.Element, str]] = [(root, local_name(root.tag))]
    while stack:
        element, where = stack.pop()
        attrs = {local_name(k): v for k, v in element.attrib.items()}
        pair_name = attrs.get("name") or attrs.get("key") or ""
        pair_value = attrs.get("value") if attrs.get("value") is not None else (element.text or "")
        if pair_name and SECRET_KEY.search(pair_name) and str(pair_value).strip():
            raise ConversionRefused(RefusalCode.EMBEDDED_SECRET, f"{where}[name={pair_name!r}] names a secret and carries a value")
        for key, value in attrs.items():
            if SECRET_KEY.search(key) and value.strip():
                raise ConversionRefused(RefusalCode.EMBEDDED_SECRET, f"{where}@{key} is named like a secret and carries a value")
            for pattern in SECRET_VALUE:
                if pattern.search(value):
                    raise ConversionRefused(RefusalCode.EMBEDDED_SECRET, f"{where}@{key} carries a secret-shaped value")
        text = (element.text or "").strip()
        if text:
            for pattern in SECRET_VALUE:
                if pattern.search(text):
                    raise ConversionRefused(RefusalCode.EMBEDDED_SECRET, f"{where} text carries a secret-shaped value")
        for child in element:
            stack.append((child, f"{where}/{local_name(child.tag)}"))


def local_name(tag: str) -> str:
    return tag.split("}", 1)[1] if tag.startswith("{") else tag


def namespace_of(tag: str) -> str:
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else ""


def measure(document: Any) -> dict:
    depth = elements = 0
    stack = [(document, 1)]
    while stack:
        value, level = stack.pop()
        elements += 1
        if elements > MAX_ELEMENTS:
            raise ConversionRefused(RefusalCode.TOO_LARGE, f"more than {MAX_ELEMENTS} values")
        depth = max(depth, level)
        if depth > MAX_DEPTH:
            raise ConversionRefused(RefusalCode.TOO_DEEP, f"nesting deeper than {MAX_DEPTH}")
        if isinstance(value, Mapping):
            stack.extend((v, level + 1) for v in value.values())
        elif isinstance(value, (list, tuple)):
            stack.extend((v, level + 1) for v in value)
    return {"depth": depth, "elements": elements}


def scan_secrets(document: Any, path: str = "$") -> None:
    """Refuse a secret-shaped key with a value, or a secret-shaped value, anywhere."""
    stack = [(document, path, None)]
    while stack:
        value, where, key = stack.pop()
        if isinstance(value, str):
            if key is not None and SECRET_KEY.search(key) and value.strip():
                raise ConversionRefused(RefusalCode.EMBEDDED_SECRET, f"{where} is named like a secret and carries a value")
            for pattern in SECRET_VALUE:
                if pattern.search(value):
                    raise ConversionRefused(RefusalCode.EMBEDDED_SECRET, f"{where} carries a secret-shaped value")
        elif isinstance(value, Mapping):
            for k, v in value.items():
                stack.append((v, f"{where}.{k}", str(k)))
        elif isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                stack.append((v, f"{where}[{i}]", None))


def slug(text: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return out or "unnamed"
