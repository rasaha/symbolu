"""V2 benchmark — frozen, general answer-normalization layer.

This module exists to score *semantically equivalent* free-text answers fairly,
without item-specific patches and without ever looking at model outputs or completed
V1 results. Every rule here is GENERAL (applies to any answer) and SYMMETRIC (applied
identically to the expected answer and to every method's model output).

Provided:
  * ``normalize_text``      — Unicode NFKC, casefold, punctuation/whitespace/underscore-
                              hyphen-space unification, article removal.
  * ``canonical_bool``      — yes/no/true/false/present/absent → bool | None.
  * ``canonical_number``    — first integer (thousands separators stripped) → int | None.
  * ``canonical_date``      — ISO-8601 date (YYYY-MM-DD) if present → str | None.
  * ``canonical_identifier``— normalized token form of an identifier.
  * ``map_concepts``        — map surface phrasing to a FROZEN set of canonical concepts
                              via a preregistered alias dictionary (derived from the
                              corpus source text, NOT from any model output).
  * ``rules_hash``          — sha256 over the frozen rule set + version.

The alias dictionary is preregistered from the corpus's own recognized/paraphrased
phrasings (``corpus/core.py``). It is finite and closed; adding an alias changes
``rules_hash`` (and therefore the V2 fingerprint), which the integrity tests enforce.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata

NORM_RULES_VERSION = "v2.0.0"

# Articles removed as leading/standalone tokens (English, general).
_ARTICLES = ("a", "an", "the")

# Boolean surface forms (general, not item-specific).
_TRUE_WORDS = ("true", "yes", "y", "present", "provided", "attached", "recorded",
               "approved", "exists", "existing", "included", "1")
_FALSE_WORDS = ("false", "no", "n", "absent", "missing", "not provided", "none",
                "not present", "not approved", "does not exist", "0")

# FROZEN, preregistered concept alias dictionary. Keys are NORMALIZED surface phrases
# (as they appear in the corpus recognized/paraphrased text); values are canonical
# concept ids. Derived from corpus/core.py phrasings only — never from model output.
_CONCEPT_ALIASES = {
    # signed build artifact / provenance-stamped image
    "signed artifact": "signed_artifact",
    "signed build artifact": "signed_artifact",
    "signed build artifact from ci": "signed_artifact",
    "provenance stamped image": "signed_artifact",
    "provenance stamped": "signed_artifact",
    "provenance stamp": "signed_artifact",
    # simulation / dress rehearsal / trial run
    "simulation": "simulation",
    "deployment simulation": "simulation",
    "dress rehearsal": "simulation",
    "full dress rehearsal": "simulation",
    "trial run": "simulation",
    "partial trial run": "simulation",
    "dry run": "simulation",
    # verified restorable backup / point-in-time copy
    "verified restorable backup": "verified_restorable_backup",
    "restorable backup": "verified_restorable_backup",
    "verified backup": "verified_restorable_backup",
    "point in time copy": "verified_restorable_backup",
    "backup": "verified_restorable_backup",
    # dual-control approval
    "dual control": "dual_control",
    "dual control approval": "dual_control",
    "two leads": "dual_control",
    "two named leads": "dual_control",
    "two approvers": "dual_control",
    # single approver
    "single approver": "single",
    "single approval": "single",
    "one approver": "single",
    # workload-identity attestation
    "workload identity attestation": "attestation",
    "workload identity": "attestation",
    "machine credential": "attestation",
    "verified machine credential": "attestation",
    # reversibility
    "reversible with cost": "reversible_with_cost",
    "reversible at some cost": "reversible_with_cost",
}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def normalize_text(s) -> str:
    """General, symmetric text normalization used by every text scorer."""
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = _strip_accents(s).casefold()
    # underscore / hyphen / slash all read as a space (space-equivalence)
    s = re.sub(r"[_\-/]+", " ", s)
    # drop remaining punctuation (keep alphanumerics and spaces)
    s = re.sub(r"[^0-9a-z ]+", " ", s)
    toks = [t for t in s.split() if t]
    # remove articles (general)
    toks = [t for t in toks if t not in _ARTICLES]
    return " ".join(toks)


def canonical_bool(s):
    """Return True/False/None from a free-text yes/no-style answer."""
    n = normalize_text(s)
    if not n:
        return None
    # phrase-level negatives first (they contain positive words)
    for w in ("not provided", "not present", "not approved", "does not exist",
              "no ", "none", "absent", "missing"):
        if n.startswith(w.strip()) or (" " + w.strip() + " ") in (" " + n + " "):
            return False
    toks = set(n.split())
    if toks & set(_FALSE_WORDS):
        return False
    if toks & set(_TRUE_WORDS):
        return True
    return None


def canonical_number(s):
    """First integer in the text with thousands separators removed, else None."""
    if s is None:
        return None
    m = re.search(r"-?\d[\d,]*", str(s))
    if not m:
        return None
    try:
        return int(m.group(0).replace(",", ""))
    except ValueError:
        return None


def canonical_date(s):
    """First ISO-8601 date (YYYY-MM-DD) in the text, else None."""
    if s is None:
        return None
    m = re.search(r"\d{4}-\d{2}-\d{2}", str(s))
    return m.group(0) if m else None


def canonical_identifier(s) -> str:
    """Identifier canonical form: normalized, spaces removed."""
    return normalize_text(s).replace(" ", "")


def map_concepts(s) -> set:
    """Map a free-text answer to the set of frozen canonical concepts it expresses."""
    n = " " + normalize_text(s) + " "
    found = set()
    for phrase, concept in _CONCEPT_ALIASES.items():
        if (" " + phrase + " ") in n:
            found.add(concept)
    return found


def frozen_rules() -> dict:
    """The exact frozen rule set (for hashing / audit)."""
    return {
        "version": NORM_RULES_VERSION,
        "articles": list(_ARTICLES),
        "true_words": list(_TRUE_WORDS),
        "false_words": list(_FALSE_WORDS),
        "concept_aliases": dict(sorted(_CONCEPT_ALIASES.items())),
    }


def rules_hash() -> str:
    blob = json.dumps(frozen_rules(), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()
