"""
The Trusted Retrieval pipeline and the A-F baseline configuration.

Explicit, typed stages (Section: Retrieval pipeline):
  1. intent normalization    5. candidate deduplication   8. gap detection
  2. query generation        6. provenance attachment     9. RetrievalRecord generation
  3. candidate retrieval     7. ranking
  4. candidate expansion

The layer selects candidate evidence ONLY. It makes no factual, policy, relationship,
authorization, claim, or response judgment, and never answers the user. TAP-E1 is used
through its public interface (an IntentRecord in) and is never modified.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple

from truth_assurance_pipeline.tap_e1_intent.schema import IntentRecord, TaskType
from truth_assurance_pipeline.tap_e2_trusted_retrieval import provenance as prov_mod
from truth_assurance_pipeline.tap_e2_trusted_retrieval.chunking import (
    concepts_of, tokenize,
)
from truth_assurance_pipeline.tap_e2_trusted_retrieval.evidence_unit import (
    EvidenceUnit, RetrievalMethod,
)
from truth_assurance_pipeline.tap_e2_trusted_retrieval.index import RetrievalIndex
from truth_assurance_pipeline.tap_e2_trusted_retrieval.ranking import (
    RankingWeights, authority_signal, combine, freshness_signal, specificity_signal,
)
from truth_assurance_pipeline.tap_e2_trusted_retrieval.schema import (
    SCHEMA_VERSION, GapType, RankedCandidate, RankingSignals, RetrievalConfidence,
    RetrievalGap, RetrievalQuery, RetrievalRecord,
)

_AUTHORITY_TERMS = ("policy", "regulation", "regulatory", "compliance", "contract",
                    "law", "gdpr", "official", "standard", "sop", "required")
_SCORE_FLOOR = 0.12          # minimum combined score to be returned at all
_SPECIFIC_CIDF = 2.0         # a concept this discriminative counts as specific grounding
_SPECIFIC_IDF = 2.5          # a term this discriminative counts as specific grounding


@dataclass(frozen=True)
class RetrievalConfig:
    name: str
    use_lexical: bool
    use_semantic: bool
    expansion: bool
    dedup: bool
    provenance_filter: bool
    gap_detection: bool
    weights: RankingWeights
    k: int
    description: str


BASELINES: Tuple[RetrievalConfig, ...] = (
    RetrievalConfig("A", True, False, False, False, False, False,
                    RankingWeights.lexical_only(), 5, "keyword (lexical) retrieval"),
    RetrievalConfig("B", False, True, False, False, False, False,
                    RankingWeights.semantic_only(), 5, "dense semantic retrieval (concept stand-in)"),
    RetrievalConfig("C", True, True, False, False, False, False,
                    RankingWeights.hybrid(), 5, "hybrid retrieval"),
    RetrievalConfig("D", True, True, False, False, True, False,
                    RankingWeights.hybrid(), 5, "hybrid + provenance filtering"),
    RetrievalConfig("E", True, True, False, False, True, True,
                    RankingWeights.hybrid(), 5, "hybrid + provenance + gap detection"),
    RetrievalConfig("F", True, True, True, True, True, True,
                    RankingWeights.full(), 5, "full TAP-E2 pipeline"),
)


def config(name: str) -> RetrievalConfig:
    for c in BASELINES:
        if c.name == name:
            return c
    raise KeyError(name)


class TrustedRetrievalLayer:
    def __init__(self, cfg: RetrievalConfig, index: RetrievalIndex):
        self.cfg = cfg
        self.index = index

    # -- 1. intent normalization + 2. query generation -----------------------
    def _build_query(self, intent: IntentRecord) -> RetrievalQuery:
        obj = intent.primary_objective
        terms = list(tokenize(obj))
        ents = []
        for e in intent.entities:
            terms.extend(tokenize(e.text))
            ents.append(e.text)
        concepts = concepts_of(terms)
        year = None
        for t in intent.temporal_constraints:
            m = re.search(r"\b(19|20)\d{2}\b", t.text)
            if m:
                year = int(m.group(0))
        if year is None:
            m = re.search(r"\b(19|20)\d{2}\b", obj)
            year = int(m.group(0)) if m else None
        low = obj.lower()
        required_authority = (
            intent.task_type in (TaskType.FACTUAL_ANSWER, TaskType.ANALYSIS)
            and (any(w in low for w in _AUTHORITY_TERMS) or "c_regulation" in concepts
                 or "c_retention" in concepts or "c_access" in concepts))
        return RetrievalQuery(tuple(dict.fromkeys(terms)), tuple(dict.fromkeys(concepts)),
                              tuple(ents), year, bool(required_authority))

    # -- 3. candidate retrieval ----------------------------------------------
    def _candidates(self, q: RetrievalQuery) -> Dict[str, Tuple[float, float]]:
        lex = self.index.lexical_candidates(q.terms) if self.cfg.use_lexical else {}
        sem = self.index.semantic_candidates(q.concepts) if self.cfg.use_semantic else {}
        cand: Dict[str, Tuple[float, float]] = {}
        for uid in set(lex) | set(sem):
            cand[uid] = (lex.get(uid, 0.0), sem.get(uid, 0.0))
        return cand

    # -- 4. candidate expansion (F) ------------------------------------------
    def _expand(self, cand: Dict[str, Tuple[float, float]], q: RetrievalQuery
                ) -> Dict[str, Tuple[float, float]]:
        if not self.cfg.expansion or not cand:
            return cand
        top = sorted(cand, key=lambda u: (sum(cand[u]), u), reverse=True)[:3]
        top_entities = set()
        for uid in top:
            top_entities |= set(self.index.by_id(uid).entities)
        for u in self.index.units:
            if u.unit_id in cand:
                continue
            if top_entities & set(u.entities):
                # pull in same-entity evidence at a modest lexical/semantic echo
                lex = self.index.lexical_score(q.terms, u.unit_id)
                cand[u.unit_id] = (lex * 0.5, 0.0)
        return cand

    # -- 5. deduplication (F) -------------------------------------------------
    def _dedup(self, ranked: List[RankedCandidate]) -> List[RankedCandidate]:
        if not self.cfg.dedup:
            return ranked
        kept: List[RankedCandidate] = []
        seen_claims: set = set()
        seen_tokens: List[set] = []
        for c in ranked:
            u = c.unit
            key = (u.claim_key, u.claim_value)
            if u.claim_key and key in seen_claims:
                continue
            toks = set(self.index.tokens_of(u.unit_id))
            dup = any(toks and len(toks & t) / max(1, len(toks | t)) >= 0.8
                      for t in seen_tokens)
            if dup:
                continue
            if u.claim_key:
                seen_claims.add(key)
            seen_tokens.append(toks)
            kept.append(c)
        return kept

    # -- 6 + 7. provenance attachment + ranking ------------------------------
    def _rank(self, cand: Dict[str, Tuple[float, float]], q: RetrievalQuery
              ) -> List[RankedCandidate]:
        method = (RetrievalMethod.HYBRID if self.cfg.use_lexical and self.cfg.use_semantic
                  else RetrievalMethod.LEXICAL if self.cfg.use_lexical
                  else RetrievalMethod.SEMANTIC)
        path = ["intent_normalization", "query_generation", "candidate_retrieval"]
        if self.cfg.expansion:
            path.append("candidate_expansion")
        path.append("provenance_attachment")
        ranked: List[RankedCandidate] = []
        # redundancy tracking for the penalty signal
        seen_tokens: List[set] = []
        # order candidates by a provisional score so redundancy penalty is stable;
        # unit_id tiebreak makes this fully deterministic regardless of dict/set order
        prelim = sorted(cand, key=lambda u: (sum(cand[u]), u), reverse=True)
        for uid in prelim:
            u = self.index.by_id(uid)
            lex, sem = cand[uid]
            provenance = prov_mod.attach(
                u, method, round(lex + sem, 6),
                tuple(path + (["candidate_expansion"] if u.doc_id and lex and sem == 0
                              and self.cfg.expansion else [])))
            if self.cfg.provenance_filter and not provenance.is_complete():
                continue  # drop evidence without complete provenance
            toks = set(self.index.tokens_of(uid))
            redundancy = 0.0
            for t in seen_tokens:
                if toks and len(toks & t) / max(1, len(toks | t)) >= 0.6:
                    redundancy = 1.0
                    break
            seen_tokens.append(toks)
            signals = RankingSignals(
                lexical=round(lex, 6), semantic=round(sem, 6),
                authority=authority_signal(u), freshness=freshness_signal(u),
                provenance_completeness=1.0 if provenance.is_complete() else 0.0,
                specificity=specificity_signal(u, len(toks)),
                redundancy_penalty=redundancy)
            ranked.append(RankedCandidate(u, provenance, signals,
                                          combine(self.cfg.weights, signals)))
        ranked.sort(key=lambda c: (c.score, c.unit.unit_id), reverse=True)
        ranked = self._dedup(ranked)
        # score floor: drop weakly-matching filler so a narrow query returns few,
        # high-precision units rather than always k tangential ones.
        ranked = [c for c in ranked
                  if (c.signals.lexical + c.signals.semantic) >= _SCORE_FLOOR]
        return ranked

    # -- 8. gap detection -----------------------------------------------------
    def _gaps(self, q: RetrievalQuery, topk: List[RankedCandidate]
              ) -> Tuple[RetrievalGap, ...]:
        if not self.cfg.gap_detection:
            return ()
        gaps: List[RetrievalGap] = []
        top_ids = {c.unit.unit_id for c in topk}

        # MISSING_ENTITY: a query entity absent from the entire corpus
        for ent in q.entities:
            et = set(tokenize(ent))
            if et and not any(et & set(u.entities and tokenize(" ".join(u.entities)) or [])
                              and et & set(tokenize(u.text)) for u in self.index.units):
                if not any(et & set(tokenize(u.text)) for u in self.index.units):
                    gaps.append(RetrievalGap(GapType.MISSING_ENTITY,
                                             f"no evidence mentions entity '{ent}'",
                                             {"entity": ent}))

        # NO_AUTHORITATIVE_SOURCE: no STRONGLY-matching authoritative unit was
        # retrieved (an off-topic authoritative unit must not mask the gap).
        if q.required_authority and not any(
                c.unit.is_authoritative and (c.signals.lexical + c.signals.semantic) >= 0.30
                for c in topk):
            gaps.append(RetrievalGap(GapType.NO_AUTHORITATIVE_SOURCE,
                                     "no strongly-matching authoritative source retrieved"))

        # CONFLICTING_SOURCES: two RETRIEVED (top-k) units share a claim_key but assert
        # different current values — surfaced explicitly, never hidden.
        by_key: Dict[str, set] = {}
        for c in topk:
            u = c.unit
            if u.claim_key and u.claim_value and not u.is_deprecated:
                by_key.setdefault(u.claim_key, set()).add(u.claim_value)
        for key, vals in by_key.items():
            if len(vals) > 1:
                gaps.append(RetrievalGap(GapType.CONFLICTING_SOURCES,
                                         f"conflicting values for '{key}': {sorted(vals)}",
                                         {"claim_key": key, "values": sorted(vals)}))

        # OUTDATED_SOURCES: a deprecated/superseded unit retrieved while a fresher one exists
        for c in topk:
            if c.unit.is_deprecated:
                gaps.append(RetrievalGap(GapType.OUTDATED_SOURCES,
                                         f"retrieved evidence '{c.unit.unit_id}' is outdated",
                                         {"unit_id": c.unit.unit_id,
                                          "superseded_by": c.unit.superseded_by}))

        # INSUFFICIENT_EVIDENCE: no retrieved unit is grounded by a DISCRIMINATIVE
        # signal (a specific concept or a distinctive term). Matching only broad
        # concepts / very common terms does not count as sufficient evidence — this
        # is what surfaces a genuine gap even when a coarse concept spuriously matches.
        if not self._has_specific_grounding(q, topk):
            gaps.append(RetrievalGap(GapType.INSUFFICIENT_EVIDENCE,
                                     "no discriminative evidence retrieved for the query",
                                     {"n_candidates": len(topk)}))

        # UNRESOLVED_TEMPORAL_SCOPE
        if q.temporal_scope is not None and not any(
                c.unit.effective_year is not None
                and c.unit.effective_year <= q.temporal_scope for c in topk):
            gaps.append(RetrievalGap(GapType.UNRESOLVED_TEMPORAL_SCOPE,
                                     f"no evidence covers the temporal scope {q.temporal_scope}",
                                     {"year": q.temporal_scope}))
        return tuple(gaps)

    def _has_specific_grounding(self, q: RetrievalQuery, topk: List[RankedCandidate]
                                ) -> bool:
        qc = set(q.concepts)
        qt = set(q.terms)
        for c in topk:
            utoks = set(self.index.tokens_of(c.unit.unit_id))
            uconcepts = set(concepts_of(list(utoks)))
            if any(concept in uconcepts and self.index._cidf(concept) >= _SPECIFIC_CIDF
                   for concept in qc):
                return True
            if any(t in utoks and self.index._idf(t) >= _SPECIFIC_IDF for t in qt):
                return True
        return False

    # -- 9. RetrievalRecord generation ---------------------------------------
    def retrieve(self, intent: IntentRecord) -> RetrievalRecord:
        t0 = time.perf_counter()
        q = self._build_query(intent)
        cand = self._candidates(q)
        cand = self._expand(cand, q)
        ranked = self._rank(cand, q)
        topk = ranked[:self.cfg.k]
        gaps = self._gaps(q, topk)
        confidence = self._confidence(q, topk)
        latency = (time.perf_counter() - t0) * 1000.0
        return RetrievalRecord(
            schema_version=SCHEMA_VERSION,
            retrieval_id=f"ret::{intent.request_id}::{self.cfg.name}",
            intent_ref=intent.request_id, intent_objective=intent.primary_objective,
            query=q, candidates=tuple(topk), confidence=confidence, gaps=gaps,
            latency_ms=latency)

    def _confidence(self, q: RetrievalQuery, topk: List[RankedCandidate]
                    ) -> RetrievalConfidence:
        if not topk:
            return RetrievalConfidence(0, 0, 0, 0, 0, 0)
        n = len(topk)
        ent_hits = 0
        for ent in q.entities:
            et = set(tokenize(ent))
            if any(et & set(tokenize(c.unit.text)) for c in topk):
                ent_hits += 1
        entity_match = (ent_hits / len(q.entities)) if q.entities else \
            (1.0 if any(c.unit.entities for c in topk) else 0.5)
        semantic_relevance = sum(c.signals.semantic for c in topk) / n
        if q.temporal_scope is None:
            temporal_relevance = 1.0
        else:
            temporal_relevance = (sum(1 for c in topk if c.unit.effective_year
                                      and c.unit.effective_year <= q.temporal_scope) / n)
        source_completeness = sum(1 for c in topk if c.unit.is_authoritative) / n
        provenance_quality = sum(1 for c in topk if c.provenance.is_complete()) / n
        retrieval_coverage = min(1.0, n / self.cfg.k)
        return RetrievalConfidence(round(entity_match, 4), round(semantic_relevance, 4),
                                   round(temporal_relevance, 4), round(source_completeness, 4),
                                   round(provenance_quality, 4), round(retrieval_coverage, 4))
