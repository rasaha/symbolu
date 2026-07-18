"""Corpus schema for the naturalistic study.

A ``CorpusItem`` wraps an ablatable ``Context`` with the metadata the study needs:
partition (public vs authored), anti-leakage split, domain, action type, document
structure family, and a full provenance record. The ``Context`` itself is
unchanged, so the frozen ablation engine consumes it as-is.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

from ..units import Context

# ---- partitions (origin) ----
PUBLIC = "PUBLIC_NATURALISTIC_CORPUS"
AUTHORED = "AUTHORED_REALISTIC_CORPUS"

# ---- anti-leakage splits ----
DEV = "DEV"
VALIDATION = "VALIDATION"
HELDOUT = "HELDOUT_TEST"
SPLITS = (DEV, VALIDATION, HELDOUT)

# ---- document-structure families ----
PROSE = "prose"
PROSE_TABLES = "prose_tables"
STRUCTURED = "structured"
STRUCTURE_FAMILIES = (PROSE, PROSE_TABLES, STRUCTURED)


@dataclass(frozen=True)
class Provenance:
    source: str                 # URL or repo path or "authored_realistic"
    title: str
    license: str                # e.g. "repo-internal", "Apache-2.0", "original-authored"
    adapted: bool
    adaptations: str            # exact adaptations made
    action_type: str
    tool_domain: str
    expected_envelope: str      # short description of expected envelope mapping
    retrieved: str = ""         # retrieval date where applicable


@dataclass(frozen=True)
class CorpusItem:
    item_id: str
    partition: str              # PUBLIC | AUTHORED
    split: str                  # DEV | VALIDATION | HELDOUT_TEST
    domain: str
    action_type: str
    structure_family: str
    context: Context
    provenance: Provenance
    template_family: str        # for anti-leakage duplicate checks

    def content_hash(self) -> str:
        """Stable hash of the context content (for the result manifest)."""
        payload = {
            "base": self.context.base,
            "units": [(u.id, u.source_type, u.text, u.contrib, u.expected,
                       u.redundancy_set, list(u.references)) for u in self.context.units],
            "linked_pairs": [list(p) for p in self.context.linked_pairs],
        }
        blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return "sha256:" + hashlib.sha256(blob).hexdigest()

    def manifest_row(self) -> dict:
        return {
            "item_id": self.item_id, "partition": self.partition, "split": self.split,
            "domain": self.domain, "action_type": self.action_type,
            "structure_family": self.structure_family,
            "template_family": self.template_family,
            "n_units": len(self.context.units),
            "n_tokens": self.context.total_tokens,
            "content_hash": self.content_hash(),
            "provenance": asdict(self.provenance),
        }
