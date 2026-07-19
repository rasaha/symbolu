#!/usr/bin/env python3
"""
Shared machinery for conventional baseline extractors.

Design (controlled comparison): every baseline shares the SAME frozen
relationship-resolution module (`InHouseExtractor.resolve` / the conflict +
answer construction in `InHouseExtractor.extract`). Baselines differ ONLY in the
retrieval front-end that selects which evidence spans enter the packet. This
isolates *retrieval capability* — the variable this phase studies — while holding
relationship reasoning constant.

Consequences, by construction:
  * `resolved_answer`, `conflicts_resolved` (→ Precedence Recall) and coverage are
    produced by the shared resolver → identical across retrieval baselines.
    Precedence is therefore NOT a retrieval variable here; it is a property of the
    shared reasoning module. (This is itself an honest finding.)
  * `evidence` spans differ by retriever → Critical / Defeater / Definition Recall,
    packet-only Sufficiency, faithfulness, and Unsafe Handover all vary.

Nothing in the frozen handover package or the SEEB benchmark is modified; this
package only imports them.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from agentic.hybrid_handover.inhouse import InHouseExtractor
from agentic.hybrid_handover.schema import Corpus, Coverage, EvidencePacket, EvidenceSpan

_SENTENCE_SPLIT = re.compile(r"(?<=[.;])\s+")
_WORD = re.compile(r"[a-z0-9]+")

# One shared reasoning module for every baseline (frozen; imported, not modified).
_SHARED_RESOLVER = InHouseExtractor()

# Retrieval budget. Small by necessity — SEEB v1 corpora are short (2–6 sentences),
# which limits retrieval selectivity (see BASELINE_COMPARISON "Limitations").
TOP_K = 4


def iter_sentences(corpus: Corpus):
    """Yield (doc, sentence_text, start_offset) for every non-empty sentence,
    with exact offsets so extracted spans ground verbatim."""
    for doc in corpus.documents:
        for chunk in _SENTENCE_SPLIT.split(doc.text):
            s = chunk.strip()
            if not s:
                continue
            start = doc.text.find(s)
            if start < 0:
                continue
            yield doc, s, start


def tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def char_ngrams(text: str, n: int = 3) -> Counter:
    t = re.sub(r"\s+", " ", text.lower()).strip()
    if len(t) < n:
        return Counter([t]) if t else Counter()
    return Counter(t[i : i + n] for i in range(len(t) - n + 1))


def cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _span_from(doc, sentence: str, start: int) -> EvidenceSpan:
    return EvidenceSpan(
        quote=sentence,
        doc_id=doc.doc_id,
        citation=doc.citation,
        char_span=(start, start + len(sentence)),
        confidence=0.90,
    )


class BaseRetrieverExtractor:
    """Retriever + shared frozen reasoning. Subclasses implement `rank`."""

    name = "base"
    mode = "n/a"

    def resolve(self, question: str, corpus: Corpus):
        return _SHARED_RESOLVER.resolve(question, corpus)

    def rank(self, question: str, corpus: Corpus) -> list[tuple[float, object, str, int]]:
        """Return [(score, doc, sentence, start), ...]; higher score = more relevant."""
        raise NotImplementedError

    def retrieve(self, question: str, corpus: Corpus) -> list[EvidenceSpan]:
        scored = self.rank(question, corpus)
        # deterministic order: score desc, then doc order, then offset
        order = {d.doc_id: i for i, d in enumerate(corpus.documents)}
        scored.sort(key=lambda t: (-t[0], order.get(t[1].doc_id, 0), t[3]))
        top = scored[:TOP_K]
        # restore document/reading order for the packet
        top.sort(key=lambda t: (order.get(t[1].doc_id, 0), t[3]))
        return [_span_from(doc, sent, start) for _, doc, sent, start in top]

    def extract(self, question: str, corpus: Corpus) -> EvidencePacket:
        base = _SHARED_RESOLVER.extract(question, corpus)  # answer, conflicts, coverage
        spans = self.retrieve(question, corpus)
        coverage = Coverage(
            docs_scanned=len(corpus.documents),
            tokens_ingested=corpus.total_tokens(),
            spans_returned=len(spans),
        )
        return base.model_copy(update={"evidence": spans, "coverage": coverage})
