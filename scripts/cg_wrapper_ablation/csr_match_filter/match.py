"""match.py — C×R×S MATCH-filter scoring, decisions, trace, prompt frame, and the wrapper.

MATCH(term, domain) = C × R × S  (multiplicative veto). S is the non-phonemic firewall and, together
with C, holds veto power over MATCH magnitude. The wrapper constrains the answer-space; the base LLM
(injected, optional) only verbalizes within the CSR-selected frame. No logits, no governance.

NOT A BHAVA LATENT VECTOR. C and R consume the deterministic PHONEMIC 12D profile
(`compute_12d_profile`, derived from the term's letters — see profile.py); S consumes non-phonemic
semantic definitions/embeddings (semantic.py). No hidden-state "Bhava" latent vector and no model
hidden state are used anywhere in Phase 1–3 scoring. The 12D layer names (Identity, Cognition, …) are
a varna-flavoured phonemic ontology, not a learned Bhava read. Hidden-state / learned-Bhava work is
Phase 4 only (design + Stage-A plumbing) and is NOT runtime-active here.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

import numpy as np

from . import registry as REG
from .profile import compute_12d_profile, dominant_layers
from .resonance import C_GATE_HI, C_GATE_LO, realization_flat, realization_grouped, s_gate_suppression
from .semantic import SemanticCoherenceAdapter, compute_semantic_coherence


class CSRMatchDecision(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    WEAK = "weak"
    REJECT_ONTOLOGICAL = "reject_ontological"
    REJECT_SEMANTIC = "reject_semantic"

    @property
    def is_reject(self) -> bool:
        return self in (CSRMatchDecision.REJECT_ONTOLOGICAL, CSRMatchDecision.REJECT_SEMANTIC)

    @property
    def is_frame(self) -> bool:
        return self in (CSRMatchDecision.PRIMARY, CSRMatchDecision.SECONDARY)


@dataclass(frozen=True)
class CSRThresholds:
    reject_C: float = 0.20
    reject_S: float = 0.20
    primary_match: float = 0.20      # calibrated to the C×R×S product scale (real_embed_fn, F1-optimal)
    secondary_match: float = 0.05    # separates true-secondary (~0.086) from unlabeled 'other' (~0.038)
    rewrite_if_answer_alignment_below: float = 0.40


DEFAULT_THRESHOLDS = CSRThresholds()

# S-gating of the blocked-lane penalty (shared by C and R) lives in resonance.py: C_GATE_LO/HI +
# s_gate_suppression(). Only a STRONG semantic match relaxes the phoneme-derived penalty.


@dataclass
class CSRMatchScore:
    term: str
    domain: str
    C: float
    R: float
    S: float
    match: float
    decision: str                       # CSRMatchDecision value
    r_groups: Optional[dict] = None      # group-aware R trace (per resonance group + penalty)


@dataclass
class CSRMatchTrace:
    query: str
    terms: List[str]
    domains: List[str]
    scores: List[CSRMatchScore]
    primary_domains: List[str] = field(default_factory=list)
    secondary_domains: List[str] = field(default_factory=list)
    rejected_domains: List[str] = field(default_factory=list)

    def to_json(self, **kw) -> str:
        return json.dumps({
            "query": self.query, "terms": self.terms, "domains": self.domains,
            "scores": [asdict(s) for s in self.scores],
            "primary_domains": self.primary_domains,
            "secondary_domains": self.secondary_domains,
            "rejected_domains": self.rejected_domains,
        }, **kw)

    @staticmethod
    def from_json(text: str) -> "CSRMatchTrace":
        d = json.loads(text)
        d["scores"] = [CSRMatchScore(**s) for s in d["scores"]]
        return CSRMatchTrace(**d)


# --- scoring --------------------------------------------------------------------------------------

def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    den = (np.linalg.norm(a) * np.linalg.norm(b))
    return float(a @ b / den) if den else 0.0


def compute_constraint(term_vec: np.ndarray, domain: str, s: Optional[float] = None) -> float:
    """C — ontological allowance: required layers lit, blocked layers dark, mass on-target.

    S-gated blocked penalty: the blocked-lane penalty is computed from the *phoneme* profile, which can
    falsely light a correct domain's blocked lane (e.g. 'fire'→Reasoning, which `heat` blocks). When the
    non-phonemic firewall S strongly supports the match, that penalty is suppressed (lerp toward no
    penalty as s→1), so C does not ontologically veto a semantically-correct domain. When S is low
    (semantically unsupported), the full penalty stands and C still vetoes impossible domains.
    """
    rule = REG.ontology_rule(domain)   # hand-tagged override if present, else derived from template
    idx = REG.LAYER_INDEX

    def mean_over(names):
        return float(np.mean([term_vec[idx[n]] for n in names])) if names else 0.0

    required_score = mean_over(rule.required_high)
    blocked_score = mean_over(rule.blocked_high)
    blocked_penalty = 1.0 - blocked_score
    if s is not None:                                  # S-gate: only STRONG semantic support relaxes it
        blocked_penalty = blocked_penalty + (1.0 - blocked_penalty) * s_gate_suppression(s)
    on_names = set(rule.required_high) | set(rule.allowed_high)
    on_target = mean_over(list(on_names)) if on_names else 0.0
    off_names = [n for n in REG.LAYERS_12 if n not in on_names and n not in rule.blocked_high]
    off_target = mean_over(off_names) if off_names else 0.0
    denom = on_target + off_target
    consistency = (on_target / denom) if denom else 0.5
    C = required_score * blocked_penalty * (0.5 + 0.5 * consistency)
    return float(np.clip(C, 0.0, 1.0))


def compute_realization(term_vec: np.ndarray, domain: str, grouped: bool = True, s=None):
    """R — realization strength. Group-aware by default (returns (R, trace)); flat cosine optional.

    Group-aware R compares per-resonance-group emphasis (weighted per domain) and penalises blocked
    lanes, so domains that differ in which family of structure is active are separable — unlike flat
    12D cosine, which is near-collinear for all positive templates. `s` S-gates the blocked-lane
    penalty (a strong semantic match relaxes it), parallel to C.
    """
    if grouped:
        return realization_grouped(term_vec, domain, s=s)
    return realization_flat(term_vec, domain), None


def decide(match: float, C: float, S: float,
           thr: CSRThresholds = DEFAULT_THRESHOLDS) -> CSRMatchDecision:
    """Veto-ordered decision: C firewall, then S firewall, then MATCH bands."""
    if C < thr.reject_C:
        return CSRMatchDecision.REJECT_ONTOLOGICAL
    if S < thr.reject_S:
        return CSRMatchDecision.REJECT_SEMANTIC
    if match >= thr.primary_match:
        return CSRMatchDecision.PRIMARY
    if match >= thr.secondary_match:
        return CSRMatchDecision.SECONDARY
    return CSRMatchDecision.WEAK


def score_match(term: str, domain: str,
                adapter: Optional[SemanticCoherenceAdapter] = None,
                thr: CSRThresholds = DEFAULT_THRESHOLDS,
                term_vec: Optional[np.ndarray] = None) -> CSRMatchScore:
    vec = compute_12d_profile(term) if term_vec is None else term_vec
    S = compute_semantic_coherence(term, domain, adapter)
    C = compute_constraint(vec, domain, s=S)           # S-gated blocked penalty (allowance)
    R, r_trace = compute_realization(vec, domain, s=S)  # S-gated blocked penalty (realization)
    match = C * R * S
    dec = decide(match, C, S, thr)
    return CSRMatchScore(term, domain, round(C, 4), round(R, 4), round(S, 4),
                         round(match, 4), dec.value, r_groups=r_trace)


def build_trace(query: str, terms: List[str], domains: List[str],
                adapter: Optional[SemanticCoherenceAdapter] = None,
                thr: CSRThresholds = DEFAULT_THRESHOLDS) -> CSRMatchTrace:
    scores: List[CSRMatchScore] = []
    for term in terms:
        vec = compute_12d_profile(term)
        for domain in domains:
            scores.append(score_match(term, domain, adapter, thr, term_vec=vec))

    # aggregate a domain to its best (max-MATCH, non-reject) decision across terms
    best: Dict[str, CSRMatchScore] = {}
    for s in scores:
        cur = best.get(s.domain)
        if cur is None or s.match > cur.match:
            best[s.domain] = s
    primary = sorted(d for d, s in best.items() if s.decision == CSRMatchDecision.PRIMARY.value)
    secondary = sorted(d for d, s in best.items() if s.decision == CSRMatchDecision.SECONDARY.value)
    rejected = sorted(d for d, s in best.items()
                      if s.decision in (CSRMatchDecision.REJECT_ONTOLOGICAL.value,
                                        CSRMatchDecision.REJECT_SEMANTIC.value))
    return CSRMatchTrace(query, list(terms), list(domains), scores, primary, secondary, rejected)


def build_prompt_frame(trace: CSRMatchTrace) -> str:
    """System-context frame: tells the LLM which domains are permitted (hook 2)."""
    def fmt(xs):
        return ", ".join(xs) if xs else "(none)"
    return (
        "You are answering the user's question.\n"
        "CSR analysis has already selected the permitted semantic frame.\n\n"
        f"Primary domains:\n  {fmt(trace.primary_domains)}\n"
        f"Secondary domains:\n  {fmt(trace.secondary_domains)}\n"
        f"Rejected domains:\n  {fmt(trace.rejected_domains)}\n\n"
        "Instructions:\n"
        "1. Use primary domains as the main explanation frame.\n"
        "2. Mention secondary domains only if useful.\n"
        "3. Do not introduce rejected domains unless the user explicitly asks.\n"
        "4. Keep the answer faithful to external semantic meaning.\n"
        "5. Do not claim that phonemes alone prove meaning.\n\n"
        f"User question:\n  {trace.query}\n"
    )


def csr_alignment(answer: str, trace: CSRMatchTrace) -> float:
    """Hook 4 post-check (non-phonemic): reward primary-domain keyword presence, penalise rejected."""
    from .semantic import _tokens
    toks = _tokens(answer)
    if not toks:
        return 0.0

    def kw(domains):
        s = set()
        for d in domains:
            t = REG.DOMAIN_TEMPLATES.get(d)
            if t:
                s |= set(t.keywords)
        return s

    prim, rej = kw(trace.primary_domains), kw(trace.rejected_domains)
    prim_hits = len(toks & prim)
    rej_hits = len(toks & rej)
    if not prim:
        return 0.5  # nothing to align to
    score = prim_hits / max(1, len(prim)) - 0.5 * (rej_hits / max(1, len(rej or {1})))
    return float(np.clip(score * 3.0, 0.0, 1.0))  # scaled; keyword hits are sparse


# --- wrapper (Mode A — API; LLM optional) ---------------------------------------------------------

class CSRMatchFilterWrapper:
    """API-mode wrapper: scores the frame, prompts an (optional) LLM, reranks, post-checks/rewrites.

    `llm` is any object/callable producing text; if None, generation hooks are skipped and the
    wrapper returns the trace + prompt frame only (useful for the demo and tests).
    """

    def __init__(self,
                 llm: Optional[object] = None,
                 adapter: Optional[SemanticCoherenceAdapter] = None,
                 domains: Optional[List[str]] = None,
                 thresholds: CSRThresholds = DEFAULT_THRESHOLDS,
                 term_extractor: Optional[Callable[[str], List[str]]] = None):
        self.llm = llm
        self.adapter = adapter or SemanticCoherenceAdapter()
        self.domains = list(domains) if domains else list(REG.DOMAIN_REGISTRY)
        self.thr = thresholds
        self.term_extractor = term_extractor or _default_term_extractor

    def analyze(self, query: str, terms: Optional[List[str]] = None) -> CSRMatchTrace:
        terms = terms or self.term_extractor(query)
        return build_trace(query, terms, self.domains, self.adapter, self.thr)

    def filtered_domains(self, trace: CSRMatchTrace) -> List[str]:
        """Hook 1 retrieval filter: keep only primary/secondary (drop weak + rejected)."""
        keep = {s.domain for s in trace.scores
                if s.decision in (CSRMatchDecision.PRIMARY.value, CSRMatchDecision.SECONDARY.value)}
        return sorted(keep)

    def answer(self, query: str, terms: Optional[List[str]] = None,
               n_candidates: int = 3) -> Dict:
        trace = self.analyze(query, terms)
        prompt = build_prompt_frame(trace)
        result = {"query": query, "csr_trace": trace, "prompt_frame": prompt,
                  "filtered_domains": self.filtered_domains(trace), "answer": None,
                  "post_check": None}
        if self.llm is None:
            return result
        # Hook 3 — candidate generation + rerank
        drafts = _generate(self.llm, prompt, n_candidates)
        best = max(drafts, key=lambda d: 0.60 * _relevance(d, query)
                   + 0.25 * csr_alignment(d, trace) + 0.15 * 1.0) if drafts else ""
        # Hook 4 — post-generation correction
        align = csr_alignment(best, trace)
        if align < self.thr.rewrite_if_answer_alignment_below and hasattr(self.llm, "rewrite"):
            instr = (f"Rewrite using {', '.join(trace.primary_domains) or 'the primary frame'} as the "
                     f"primary frame; mention {', '.join(trace.secondary_domains) or 'secondary'} only "
                     f"if useful; do not introduce {', '.join(trace.rejected_domains) or 'rejected'} "
                     f"domains.")
            best = self.llm.rewrite(best, instruction=instr)
            align = csr_alignment(best, trace)
        result["answer"] = best
        result["post_check"] = {"alignment": round(align, 4),
                                "rewritten": align != csr_alignment(drafts[0], trace) if drafts else False}
        return result


# filler / question / generic words that are never the dominant theme of a query
_THEME_STOP = {
    "is", "are", "was", "were", "the", "a", "an", "of", "to", "or", "and", "more", "most", "than",
    "what", "which", "who", "whom", "whose", "why", "how", "does", "do", "did", "can", "could",
    "would", "should", "explain", "whether", "about", "between", "kind", "type", "sort", "really",
    "actually", "just", "like", "figure", "thing", "something", "someone",
}


def dominant_terms(query: str, k: int = 2) -> List[str]:
    """Pick the dominant word(s)/theme of the user input — not every token.

    Keeps the term axis small (latency) and focused (relevance). Multi-word known glosses
    (e.g. 'authority figure') are the strongest theme signal; otherwise rank content words by a
    light salience (length + position, minus filler/question words).
    """
    import re
    q = query.lower()
    glosses = sorted((t for t in REG.TERM_GLOSSES if t in q), key=lambda t: -len(t))
    claimed = set()
    chosen: List[str] = []
    for g in glosses:                       # prefer multi-word themes, longest first
        if not any(w in claimed for w in g.split()):
            chosen.append(g)
            claimed.update(g.split())
    toks = re.findall(r"[A-Za-z]+", query)
    cands = []
    for i, w in enumerate(toks):
        lw = w.lower()
        if lw in _THEME_STOP or len(lw) <= 3 or lw in claimed:
            continue
        salience = len(lw) + (1.5 if w[0].isupper() and i > 0 else 0) - 0.1 * i
        cands.append((salience, i, lw))
    for _, _, w in sorted(cands, key=lambda x: (-x[0], x[1])):
        if w not in chosen:
            chosen.append(w)
    return chosen[:k] if chosen else (toks[:1] or [query])


def _default_term_extractor(query: str) -> List[str]:
    """Default wrapper extractor — the dominant theme of the query."""
    return dominant_terms(query)


def _generate(llm, prompt: str, n: int) -> List[str]:
    if hasattr(llm, "generate_candidates"):
        return list(llm.generate_candidates(prompt, n=n))
    if callable(llm):
        return [llm(prompt)]
    if hasattr(llm, "generate"):
        return [llm.generate(prompt)]
    return []


def _relevance(draft: str, query: str) -> float:
    from .semantic import _tokens
    a, b = _tokens(draft), _tokens(query)
    return (len(a & b) / len(b)) if b else 0.0
