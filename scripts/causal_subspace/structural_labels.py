"""
Part 2 — Structural Label Alignment
=====================================

Attach structural metadata to each token/word:
    - Sentence ID
    - Dependency tree depth
    - Dependency relation (nsubj, dobj, root, etc.)
    - Grammatical role (subject, object, root, modifier, other)

Token-to-Word Aggregation: For multi-token words, extract only the hidden
state of the **last** sub-token to represent the synthesized structural
context of the word.

We use a lightweight rule-based dependency parser so that this module works
without spaCy/stanza as hard dependencies.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structural label definitions
# ---------------------------------------------------------------------------

GRAMMATICAL_ROLES = ["subject", "object", "root", "modifier", "other"]
ROLE_TO_IDX = {r: i for i, r in enumerate(GRAMMATICAL_ROLES)}


@dataclass
class WordAnnotation:
    """Structural annotation for a single word."""

    word: str
    sentence_id: int
    position_in_sentence: int
    dep_depth: int
    dep_relation: str
    grammatical_role: str  # one of GRAMMATICAL_ROLES
    token_indices: List[int]  # indices into the token-level arrays
    last_token_index: int  # the representative token index


@dataclass
class StructuralAnnotations:
    """Full structural annotation set for a corpus run."""

    words: List[WordAnnotation] = field(default_factory=list)
    n_sentences: int = 0

    # Aggregated arrays (set by aggregate())
    hidden_states: Optional[Dict[int, np.ndarray]] = None  # layer → [N_words, d]
    labels_role: Optional[np.ndarray] = None  # [N_words] int
    labels_depth: Optional[np.ndarray] = None  # [N_words] int
    labels_sentence: Optional[np.ndarray] = None  # [N_words] int


# ---------------------------------------------------------------------------
# Dependency parsing (lightweight)
# ---------------------------------------------------------------------------

def _try_spacy_parse(sentences: List[str]):
    """Attempt spaCy-based parsing; return None if unavailable."""
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
    except Exception:
        return None

    parsed = []
    for sent in sentences:
        doc = nlp(sent)
        words = []
        for token in doc:
            depth = 0
            ancestor = token
            while ancestor.head != ancestor:
                depth += 1
                ancestor = ancestor.head
                if depth > 20:
                    break
            role = _dep_to_role(token.dep_)
            words.append((token.text, token.dep_, depth, role))
        parsed.append(words)
    return parsed


def _dep_to_role(dep: str) -> str:
    """Map dependency relation to coarse grammatical role."""
    if dep in ("nsubj", "nsubjpass", "csubj", "csubjpass", "expl"):
        return "subject"
    if dep in ("dobj", "iobj", "obj", "obl", "pobj"):
        return "object"
    if dep == "ROOT" or dep == "root":
        return "root"
    if dep in ("amod", "advmod", "nummod", "nmod", "det", "poss",
               "aux", "auxpass", "neg", "mark", "case", "cc", "punct"):
        return "modifier"
    return "other"


def _heuristic_parse(sentences: List[str]):
    """Rule-based fallback parser using word position heuristics.

    This is intentionally simple.  Real experiments should use spaCy.
    """
    parsed = []
    for sent in sentences:
        words_raw = sent.split()
        words = []
        for i, w in enumerate(words_raw):
            clean = re.sub(r"[^\w']", "", w)
            if not clean:
                continue
            # Heuristic role assignment
            if i == 0:
                role, dep, depth = "subject", "nsubj", 1
            elif i == 1 and clean[0].islower():
                role, dep, depth = "root", "ROOT", 0
            elif 2 <= i <= 3:
                role, dep, depth = "object", "dobj", 2
            else:
                role, dep, depth = "modifier", "amod", max(3, i)
            words.append((clean, dep, depth, role))
        parsed.append(words)
    return parsed


# ---------------------------------------------------------------------------
# Sentence segmentation
# ---------------------------------------------------------------------------

_SENT_RE = re.compile(r'(?<=[.!?])\s+')


def segment_sentences(text: str) -> List[str]:
    """Simple sentence splitter."""
    sentences = _SENT_RE.split(text.strip())
    return [s.strip() for s in sentences if s.strip()]


# ---------------------------------------------------------------------------
# Token-to-word alignment
# ---------------------------------------------------------------------------

def _align_tokens_to_words(
    token_strings: List[str],
    word_strings: List[str],
) -> List[List[int]]:
    """Align tokenizer sub-tokens to parsed words.

    Returns a list (one entry per word) of token index lists.
    Greedy left-to-right matching.
    """
    alignments: List[List[int]] = []
    tok_idx = 0

    for word in word_strings:
        word_clean = word.lower().replace(" ", "")
        matched_indices = []
        buffer = ""

        while tok_idx < len(token_strings):
            tok_text = token_strings[tok_idx].replace(" ", "").replace("Ġ", "").replace("▁", "").lower()
            buffer += tok_text
            matched_indices.append(tok_idx)
            tok_idx += 1

            if word_clean in buffer or buffer in word_clean:
                if len(buffer) >= len(word_clean):
                    break
            elif len(buffer) > len(word_clean) + 3:
                # Moved too far, stop
                break

        if not matched_indices:
            matched_indices = [max(0, tok_idx - 1)]

        alignments.append(matched_indices)

    return alignments


# ---------------------------------------------------------------------------
# Main labeling pipeline
# ---------------------------------------------------------------------------

def annotate_structural_labels(
    token_strings: List[str],
    sequence_ids: np.ndarray,
    hidden_states: Dict[int, np.ndarray],
    tokenizer=None,
) -> StructuralAnnotations:
    """Annotate tokens with structural labels and aggregate to word level.

    Parameters
    ----------
    token_strings : list[str]
        Decoded token strings (one per sub-token).
    sequence_ids : np.ndarray [N]
        Which sequence each token belongs to.
    hidden_states : dict[int, np.ndarray]
        Per-layer hidden states, each [N, d].
    tokenizer : optional
        HuggingFace tokenizer (used for better alignment).

    Returns
    -------
    StructuralAnnotations
        Word-level annotations with aggregated hidden states.
    """
    annotations = StructuralAnnotations()
    unique_seqs = np.unique(sequence_ids)

    logger.info("Annotating %d sequences with structural labels", len(unique_seqs))

    global_word_idx = 0
    all_word_anns: List[WordAnnotation] = []
    sentence_counter = 0

    for seq_id in unique_seqs:
        mask = sequence_ids == seq_id
        seq_token_indices = np.where(mask)[0]
        seq_tokens = [token_strings[i] for i in seq_token_indices]

        # Reconstruct text
        text = "".join(seq_tokens).replace("Ġ", " ").replace("▁", " ").strip()
        sentences = segment_sentences(text)

        if not sentences:
            continue

        # Parse sentences
        parsed = _try_spacy_parse(sentences)
        if parsed is None:
            parsed = _heuristic_parse(sentences)

        # Align tokens to words across all sentences
        all_words_flat = []
        word_meta = []  # (sentence_local_id, word_in_sentence_idx, dep, depth, role)
        for s_idx, sent_words in enumerate(parsed):
            for w_idx, (word, dep, depth, role) in enumerate(sent_words):
                all_words_flat.append(word)
                word_meta.append((sentence_counter + s_idx, w_idx, dep, depth, role))

        alignments = _align_tokens_to_words(seq_tokens, all_words_flat)

        for w_local, (word, meta) in enumerate(
            zip(all_words_flat, word_meta)
        ):
            sent_id, pos_in_sent, dep, depth, role = meta
            if w_local < len(alignments):
                tok_local_indices = alignments[w_local]
            else:
                tok_local_indices = [len(seq_tokens) - 1]

            # Map local seq indices to global indices
            tok_global_indices = [
                int(seq_token_indices[i])
                for i in tok_local_indices
                if i < len(seq_token_indices)
            ]
            if not tok_global_indices:
                continue

            ann = WordAnnotation(
                word=word,
                sentence_id=sent_id,
                position_in_sentence=pos_in_sent,
                dep_depth=depth,
                dep_relation=dep,
                grammatical_role=role,
                token_indices=tok_global_indices,
                last_token_index=tok_global_indices[-1],
            )
            all_word_anns.append(ann)

        sentence_counter += len(sentences)

    annotations.words = all_word_anns
    annotations.n_sentences = sentence_counter

    # Aggregate hidden states: take last sub-token per word
    _aggregate_to_words(annotations, hidden_states)

    logger.info(
        "Structural annotation complete: %d words, %d sentences, %d roles",
        len(annotations.words),
        annotations.n_sentences,
        len(GRAMMATICAL_ROLES),
    )
    return annotations


def _aggregate_to_words(
    annotations: StructuralAnnotations,
    hidden_states: Dict[int, np.ndarray],
) -> None:
    """Select the last sub-token hidden state per word and build label arrays."""
    n_words = len(annotations.words)
    if n_words == 0:
        return

    indices = np.array(
        [w.last_token_index for w in annotations.words], dtype=np.int64
    )

    # Per-layer word-level hidden states
    annotations.hidden_states = {}
    for layer_idx, layer_arr in hidden_states.items():
        annotations.hidden_states[layer_idx] = layer_arr[indices]

    # Label arrays
    annotations.labels_role = np.array(
        [ROLE_TO_IDX.get(w.grammatical_role, ROLE_TO_IDX["other"])
         for w in annotations.words],
        dtype=np.int32,
    )
    annotations.labels_depth = np.array(
        [w.dep_depth for w in annotations.words], dtype=np.int32
    )
    annotations.labels_sentence = np.array(
        [w.sentence_id for w in annotations.words], dtype=np.int32
    )
