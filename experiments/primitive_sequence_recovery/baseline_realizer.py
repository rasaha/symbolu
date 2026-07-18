"""Phase-1 baseline offline realizer: English lexical-overlap (Jaccard).

INFRASTRUCTURE ONLY. This module exercises the realizer architecture end-to-end against
the frozen artifacts using nothing but deterministic string tokenization and set overlap.

It performs NONE of the following: embeddings, vectors, neural models, learning, fitting,
downloads, network, LLM/API calls. It does NOT run the experiment, compute corpus-wide MRR
or scramble nulls, touch the runner/manifest, enable READY/run, or write any result. Stage A
is never imported.

Pipeline (Part 1):
    ordered primitive (atom) sequence
        -> English realization content (realization_en_gloss.json)
        -> deterministic tokenization
        -> lexical-overlap (Jaccard) similarity
        -> candidate ranking
"""
from __future__ import annotations

import json
import pathlib
import re
from abc import ABC, abstractmethod

_HERE = pathlib.Path(__file__).resolve().parent
_FROZEN = _HERE / "frozen"

# Deterministic tokenizer: lowercase, split on non-alphanumeric runs, drop 1-char tokens.
# No stemming, no stoplist, no embeddings — fully mechanical and reproducible.
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> frozenset:
    return frozenset(t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 1)


def tokenize_ordered(text: str) -> tuple:
    """Same rules as tokenize() but preserves occurrence order and duplicates (a tuple).
    Used by the order-sensitive realizer; tokenize() (set) is used by the bag baseline."""
    return tuple(t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 1)


class Realizer(ABC):
    """Stable realizer interface (Part 2).

    Every future realizer (WordNet, static embeddings, concept-graph resolver, ...) must
    implement exactly these three methods. Callers rely on nothing beyond this contract:

        encode_sequence(atom_ids)      -> an opaque "query" encoding
        encode_candidate(meaning_ref)  -> an opaque "candidate" encoding in the same space
        similarity(query, candidate)   -> a deterministic float, higher = more similar
    """

    @abstractmethod
    def encode_sequence(self, atom_ids):
        ...

    @abstractmethod
    def encode_candidate(self, meaning_ref):
        ...

    @abstractmethod
    def similarity(self, encoded_query, encoded_candidate) -> float:
        ...


class LexicalOverlapRealizer(Realizer):
    """English lexical-overlap baseline. Encodings are token *sets*; similarity is Jaccard.

    Jaccard (|A∩B| / |A∪B|) was chosen over Dice / raw-overlap because it is symmetric,
    bounded in [0, 1], parameter-free (no weighting choices to tune -> nothing to "fit"),
    and the textbook set-overlap baseline. The ranking within a fixed candidate set is
    monotonic in the shared-token count, so the specific normalization only affects ties.

    LIMITATION (by design): token sets are ORDER-INSENSITIVE, so this baseline cannot test
    the ordered-sequence claim. That is acceptable for a pipeline-validation floor and is
    deferred to a later, order-sensitive realizer phase.
    """

    realizer_type = "lexical_overlap_jaccard_en"
    deterministic = True
    offline = True

    def __init__(self, atom_content: dict):
        # atom_id -> English gloss string (from realization_en_gloss.json). Copied so the
        # realizer is self-contained and immutable to external mutation.
        self._atom_content = dict(atom_content)

    @classmethod
    def from_frozen(cls, frozen_dir=_FROZEN):
        rec = json.loads(
            (pathlib.Path(frozen_dir) / "realization_en_gloss.json").read_text(encoding="utf-8"))
        return cls(rec["atom_content"])

    def encode_sequence(self, atom_ids) -> frozenset:
        toks: set = set()
        for a in atom_ids:
            toks |= tokenize(self._atom_content[a])
        return frozenset(toks)

    def encode_candidate(self, meaning_ref) -> frozenset:
        return tokenize(meaning_ref)

    def similarity(self, encoded_query, encoded_candidate) -> float:
        union = len(encoded_query | encoded_candidate)
        if not union:
            return 0.0
        return len(encoded_query & encoded_candidate) / union


def _lcs_len(a, b) -> int:
    """Length of the longest common subsequence of two token tuples. Deterministic DP,
    parameter-free. O(len(a)*len(b))."""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0] * (len(b) + 1)
        for j, y in enumerate(b, 1):
            cur[j] = prev[j - 1] + 1 if x == y else (prev[j] if prev[j] >= cur[j - 1] else cur[j - 1])
        prev = cur
    return prev[len(b)]


class OrderSensitiveLexicalRealizer(Realizer):
    """Phase-2 order-sensitive baseline. Encodings are ORDERED token tuples; similarity is a
    normalized longest-common-subsequence (LCS) ratio: LCS / max(len_query, len_candidate).

    LCS was chosen over positional-weighting / bigram overlap because it is parameter-free
    (nothing to weight or tune -> nothing to "fit"), deterministic, needs no assets, and is
    genuinely order-sensitive: it counts tokens shared *in order*, so reordering the primitive
    sequence changes the score against any multi-token target — exactly what the bag/Jaccard
    baseline cannot see. It still ranks single-token candidates (LCS in {0,1} = presence), so
    it works on the real artifacts even though order cannot matter for a 1-token meaning.

    Like Phase 1 this is a PLUMBING VALIDATOR only: surface-form, English-only, no semantics,
    no statistics, not a cross-realization test.
    """

    realizer_type = "order_sensitive_lcs_en"
    deterministic = True
    offline = True

    def __init__(self, atom_content: dict):
        self._atom_content = dict(atom_content)

    @classmethod
    def from_frozen(cls, frozen_dir=_FROZEN):
        rec = json.loads(
            (pathlib.Path(frozen_dir) / "realization_en_gloss.json").read_text(encoding="utf-8"))
        return cls(rec["atom_content"])

    def encode_sequence(self, atom_ids) -> tuple:
        toks: list = []
        for a in atom_ids:                       # atom order preserved
            toks.extend(tokenize_ordered(self._atom_content[a]))
        return tuple(toks)

    def encode_candidate(self, meaning_ref) -> tuple:
        return tokenize_ordered(meaning_ref)

    def similarity(self, encoded_query, encoded_candidate) -> float:
        denom = max(len(encoded_query), len(encoded_candidate))
        if denom == 0:
            return 0.0
        return _lcs_len(encoded_query, encoded_candidate) / denom


def rank(realizer: Realizer, atom_ids, candidate_refs: dict):
    """Rank candidates for one ordered atom sequence. INFRASTRUCTURE, not the experiment.

    candidate_refs: {candidate_id: meaning_ref}. Returns [(candidate_id, similarity), ...]
    sorted by descending similarity, ties broken by candidate_id ascending (a fixed,
    documented, fully deterministic tie-break so identical input -> identical ranking).
    Computes no corpus metric, no null, writes nothing.
    """
    q = realizer.encode_sequence(atom_ids)
    scored = [(cid, realizer.similarity(q, realizer.encode_candidate(ref)))
              for cid, ref in candidate_refs.items()]
    scored.sort(key=lambda t: (-t[1], t[0]))
    return scored


# --- artifact helpers (load-only; no scoring of the pre-registered protocol) ---------
def load_word_atoms(frozen_dir=_FROZEN) -> dict:
    """word_id -> ordered [atom_id] via assignment.tau (active + excluded alike)."""
    fd = pathlib.Path(frozen_dir)
    tau = json.loads((fd / "assignment.json").read_text(encoding="utf-8"))["tau"]
    words = json.loads((fd / "word_list.json").read_text(encoding="utf-8"))["words"]
    return {w["word_id"]: [tau[v] for v in w["varna_sequence"]] for w in words}


def load_en_meaning_refs(frozen_dir=_FROZEN) -> dict:
    """word_id -> en_gloss meaning reference string."""
    fd = pathlib.Path(frozen_dir)
    meanings = json.loads((fd / "meaning_reference.json").read_text(encoding="utf-8"))["meanings"]
    return {m["word_id"]: m["realization_specific_reference"]["en_gloss"] for m in meanings}
