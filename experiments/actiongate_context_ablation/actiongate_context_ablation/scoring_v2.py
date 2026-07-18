"""V2 benchmark — deterministic primary scorers.

Every V2 task carries a scorer built here. Scorers are:
  * deterministic (no LLM judge in the primary metric);
  * method-agnostic (they see only the model's raw text — never which arm produced it,
    never the ground-truth method, never a V1 output);
  * field-aware (structured tasks report per-field hits, not a single brittle
    contains-all), returning a score in [0, 1] plus a ``fields`` breakdown.

A scorer is a callable ``out_text -> ScoreResult``. The harness reads ``.score``;
diagnostics/reporting can read ``.fields``. All text comparison goes through the
frozen general normalization layer (``normalize_v2``); no item-specific patches.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

from . import normalize_v2 as NZ

SCORER_VERSION = "v2.0.0"


@dataclass
class ScoreResult:
    score: float
    fields: dict = field(default_factory=dict)   # field_name -> 1.0/0.0

    def __float__(self):
        return float(self.score)


# ---- primitive comparisons (all symmetric + normalized) -------------------- #
def _text_equiv(expected, out) -> float:
    e = NZ.normalize_text(expected)
    o = NZ.normalize_text(out)
    if not e:
        return 1.0
    # equivalence OR expected phrase contained in the answer (models add prose)
    return 1.0 if (e == o or (" " + e + " ") in (" " + o + " ")) else 0.0


def _bool_equiv(expected_bool, out) -> float:
    return 1.0 if NZ.canonical_bool(out) is bool(expected_bool) else 0.0


def _number_equiv(expected, out) -> float:
    en = NZ.canonical_number(expected)
    return 1.0 if en is not None and NZ.canonical_number(out) == en else 0.0


def _date_equiv(expected, out) -> float:
    ed = NZ.canonical_date(expected)
    return 1.0 if ed is not None and NZ.canonical_date(out) == ed else 0.0


def _strip_fences(out: str) -> str:
    s = (out or "").strip()
    s = re.sub(r"^```[a-zA-Z]*\n?|```$", "", s).strip()
    return s


def extract_field(name, out) -> str:
    """Isolate a single field's value from a structured answer, so that per-field
    comparison is not confused by OTHER fields' values (e.g. two booleans). Tries JSON,
    then a ``"name": value`` / ``name = value`` pattern. Returns '' when the field is
    absent (which fairly scores 0 for a task that asked for that field)."""
    s = _strip_fences(out)
    # 1) real JSON object
    try:
        obj = json.loads(s)
        if isinstance(obj, dict) and name in obj:
            return str(obj[name])
    except (ValueError, TypeError):
        pass
    # 2) loose "name": value  /  name = value  (value = quoted string, word, or number)
    m = re.search(rf'["\']?{re.escape(str(name))}["\']?\s*[:=]\s*'
                  r'("([^"]*)"|\'([^\']*)\'|[^,}\n]+)', s, re.IGNORECASE)
    if m:
        return (m.group(2) or m.group(3) or m.group(1) or "").strip().strip('",\'')
    return ""


def _field_cmp(kind, expected, out) -> float:
    if kind == "bool":
        return _bool_equiv(expected, out)
    if kind == "number":
        return _number_equiv(expected, out)
    if kind == "date":
        return _date_equiv(expected, out)
    if kind == "identifier":
        return 1.0 if NZ.canonical_identifier(expected) and \
            NZ.canonical_identifier(expected) in NZ.canonical_identifier(out) else 0.0
    return _text_equiv(expected, out)   # default: normalized text


# ---- public scorer factories ---------------------------------------------- #
def text_scorer(expected):
    """Single normalized-text answer (1.0 if the expected phrase is present)."""
    def _s(out):
        v = _text_equiv(expected, out)
        return ScoreResult(v, {"answer": v})
    return _s


def bool_scorer(expected_bool):
    def _s(out):
        v = _bool_equiv(expected_bool, out)
        return ScoreResult(v, {"answer": v})
    return _s


def number_scorer(expected):
    def _s(out):
        v = _number_equiv(expected, out)
        return ScoreResult(v, {"answer": v})
    return _s


def concept_scorer(expected_concepts):
    """Recall of a frozen set of canonical concepts expressed in the answer."""
    want = set(expected_concepts)

    def _s(out):
        got = NZ.map_concepts(out)
        hits = {c: (1.0 if c in got else 0.0) for c in sorted(want)}
        v = (sum(hits.values()) / len(want)) if want else 1.0
        return ScoreResult(v, hits)
    return _s


def fields_scorer(spec):
    """Structured answer scored field-by-field.

    ``spec`` is a list of (field_name, kind, expected) where kind ∈
    {text, bool, number, date, identifier}. Score = mean of per-field matches,
    so partial credit is field-level rather than all-or-nothing.
    """
    spec = list(spec)

    def _s(out):
        hits = {}
        for name, kind, expected in spec:
            isolated = extract_field(name, out)
            # text fields may also be answered inline (not as a keyed field); fall back to
            # the whole output for text/identifier only — never for bool/number/date, whose
            # value must be isolated to avoid cross-field contamination.
            target = isolated if isolated or kind in ("bool", "number", "date") else out
            hits[name] = _field_cmp(kind, expected, target)
        v = (sum(hits.values()) / len(spec)) if spec else 1.0
        return ScoreResult(v, hits)
    return _s


def contains_all_scorer(keys):
    """Normalized contains-all over a set of required strings (for summarization:
    preserve-these-facts). Field-level per key."""
    ks = [k for k in keys if str(k).strip()]

    def _s(out):
        hits = {str(k): _text_equiv(k, out) for k in ks}
        v = (sum(hits.values()) / len(ks)) if ks else 1.0
        return ScoreResult(v, hits)
    return _s


def format_and_value_scorer(expected, *, lowercase=True, max_tokens=4):
    """Instruction-following with an OBSERVABLE format requirement: the answer must
    (a) contain the expected value AND (b) obey the format (short, lowercased).
    Both are checkable from the output alone."""
    def _s(out):
        raw = (out or "").strip()
        value_ok = _text_equiv(expected, raw)
        fmt_ok = 1.0
        if lowercase and raw != raw.lower():
            fmt_ok = 0.0
        if len(raw.split()) > max_tokens:
            fmt_ok = 0.0
        v = 0.5 * value_ok + 0.5 * fmt_ok
        return ScoreResult(v, {"value": value_ok, "format": fmt_ok})
    return _s


def scorer_rules() -> dict:
    return {"scorer_version": SCORER_VERSION,
            "primitives": ["text", "bool", "number", "date", "identifier",
                           "concept", "fields", "contains_all", "format_and_value"]}


def scorer_hash() -> str:
    import json
    blob = json.dumps(scorer_rules(), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()
