"""Read-only adapter over the historical phase_lc task/tokenizer/corpus code.

Imports experiments/phase_lc/tasks.py (which is Phase-free: json/re/random/torch only) so the
S-arm uses the IDENTICAL corpus, tokenizer, and task generators as the historical A/B/C study —
no task logic is duplicated. Nothing here writes to the historical tree.
"""
from __future__ import annotations

import os
import pathlib
import sys

_LAB = pathlib.Path(__file__).resolve().parents[2]
_REPO = _LAB.parent
_PHASE_LC = _REPO / "experiments" / "phase_lc"
if str(_PHASE_LC) not in sys.path:
    sys.path.insert(0, str(_PHASE_LC))

import tasks as T  # noqa: E402  (Phase-free historical task module)

CORPUS = [str(_REPO / "bounded_shadow_pilot" / "data" / "natural_pilot_v1" / "corpus.json"),
          str(_REPO / "evidence_assurance" / "data" / "v1" / "corpus.json")]
WINDOW = 64

# re-export the exact historical primitives
load_corpus_words = T.load_corpus_words
Vocab = T.Vocab
corpus_stream = T.corpus_stream
make_eval_set = T.make_eval_set
train_batch = T.train_batch
lm_batch = T.lm_batch
ABC_MIX = T.ABC_MIX


def build_corpus():
    words = load_corpus_words(CORPUS)
    vocab = Vocab(words)
    stream = corpus_stream(words, vocab)
    return words, vocab, stream


def corpus_hashes():
    import hashlib
    out = {}
    for p in CORPUS:
        if os.path.exists(p):
            out[p] = hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
        else:
            out[p] = None
    return out
