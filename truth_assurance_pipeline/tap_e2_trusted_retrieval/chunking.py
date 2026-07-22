"""
Deterministic chunking + token/concept derivation.

Chunking splits a document body into sentence-level evidence-unit texts (the smallest
independently citable fragment used here). Concept derivation maps tokens to a small,
hand-built concept lexicon; this is the deterministic stand-in for "semantic"
representation used by the dense-retrieval baseline.

HONESTY: the concept lexicon is a lexical-synonym stand-in, NOT neural embeddings.
"Dense semantic retrieval" in this study means concept-expanded token vectors, so any
semantic gain is a mechanism demonstration on synthetic text, not evidence about real
embedding models.
"""

from __future__ import annotations

import re
from typing import List, Tuple

_STOP = frozenset((
    "the", "a", "an", "to", "of", "and", "or", "for", "in", "on", "at", "by",
    "is", "are", "be", "was", "were", "with", "as", "that", "this", "these",
    "those", "it", "its", "from", "must", "may", "we", "our", "you", "your",
    "any", "all", "no", "not", "which", "who", "what", "when", "where", "how",
    "do", "does", "can", "will", "shall", "should", "per", "each", "into",
))

# token -> concept id. Synonyms collapse to a shared concept so the semantic
# baseline can match vocabulary the lexical baseline misses.
CONCEPT_MAP = {
    # data retention
    "retain": "c_retention", "retention": "c_retention", "keep": "c_retention",
    "kept": "c_retention", "store": "c_retention", "storage": "c_retention",
    "preserve": "c_retention",
    # deletion
    "delete": "c_deletion", "deletion": "c_deletion", "erase": "c_deletion",
    "purge": "c_deletion", "remove": "c_deletion", "destroy": "c_deletion",
    # personal data
    "customer": "c_personal_data", "personal": "c_personal_data",
    "pii": "c_personal_data", "user": "c_personal_data", "records": "c_personal_data",
    "data": "c_personal_data",
    # duration / time
    "duration": "c_duration", "period": "c_duration", "months": "c_duration",
    "days": "c_duration", "years": "c_duration", "long": "c_duration",
    "timeframe": "c_duration",
    # access control
    "access": "c_access", "permission": "c_access", "authorization": "c_access",
    "grant": "c_access", "role": "c_access", "privilege": "c_access",
    # authentication
    "password": "c_auth", "authenticate": "c_auth", "authentication": "c_auth",
    "mfa": "c_auth", "login": "c_auth", "credential": "c_auth", "credentials": "c_auth",
    # encryption
    "encrypt": "c_encryption", "encryption": "c_encryption", "cipher": "c_encryption",
    "tls": "c_encryption", "aes": "c_encryption",
    # incident
    "incident": "c_incident", "breach": "c_incident", "outage": "c_incident",
    "postmortem": "c_incident",
    # rate limit / api
    "rate": "c_rate_limit", "throttle": "c_rate_limit", "limit": "c_rate_limit",
    "quota": "c_rate_limit", "requests": "c_rate_limit",
    "api": "c_api", "endpoint": "c_api", "webhook": "c_api",
    # termination / contract
    "terminate": "c_termination", "termination": "c_termination",
    "cancel": "c_termination", "notice": "c_termination",
    "liability": "c_liability", "indemnity": "c_liability", "damages": "c_liability",
    # backup
    "backup": "c_backup", "restore": "c_backup", "recovery": "c_backup",
    "snapshot": "c_backup",
    # vendor / third party
    "vendor": "c_vendor", "supplier": "c_vendor", "contractor": "c_vendor",
    "subprocessor": "c_vendor", "third-party": "c_vendor",
    # deployment
    "deploy": "c_deploy", "release": "c_deploy", "rollout": "c_deploy",
    # logging / audit
    "log": "c_audit", "logs": "c_audit", "audit": "c_audit", "logging": "c_audit",
    # timeout
    "timeout": "c_timeout", "deadline": "c_timeout",
    # regulation
    "gdpr": "c_regulation", "regulation": "c_regulation", "compliance": "c_regulation",
    "regulatory": "c_regulation", "law": "c_regulation",
}


def tokenize(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9][a-z0-9-]*", text.lower())
            if t not in _STOP and len(t) > 1]


def concepts_of(tokens: List[str]) -> List[str]:
    out: List[str] = []
    for t in tokens:
        c = CONCEPT_MAP.get(t)
        if c is None and t.endswith("s") and len(t) > 3:      # light depluralization
            c = CONCEPT_MAP.get(t[:-1])
        if c is None and t.endswith("es") and len(t) > 4:
            c = CONCEPT_MAP.get(t[:-2])
        if c:
            out.append(c)
    return out


def split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.;])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]
