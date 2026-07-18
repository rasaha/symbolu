"""Symbol-U vector backends — pluggable ways to compute `U` for a word/sentence.

All backends share one interface:

    backend.name -> str
    backend.dim  -> int
    backend.encode(text: str) -> list[float]      # word or sentence

and the SAME pipeline shape:

    sentence -> word segmentation -> phoneme/varna decomposition
             -> word-level vector -> sentence-level vector (mean pool)

Backends
--------
- ``vritti_mapper`` : the ORIGINAL approximation. char -> SoundClass -> Vritti
  energy state (via symbolu_core.formulas.vritti_mapper). Phonological/surface.
  Implemented in symbolu_engine.SymbolUEngine; wrapped here for a uniform API.

- ``pse_meaning``   : the PSE phoneme->MEANING layer. Uses the canonical
  varna_lens engine (`varna_lens.varna_lens.analyze`, model="op") to decompose a
  word into varṇas, then looks up each consonant's SEMANTIC ``domain_tags`` from
  `lexicon_authoritative.json` (107 distinct meaning tags such as hope /
  creation / manifestation, shared across phonemes) plus each vowel's
  liberating/binding state. This is the "stronger hypothesis": meaning, not just
  sound class.

- ``pse_resonance`` : the PSE polarity/valence "resonance" signal — the
  liberating(+) vs binding(−) poles that varna_lens's CV-attachment rule assigns
  to each varṇa, summarized as a compact valence vector. Distinct from meaning
  *identity*: it captures the emergent spiritual/worldly lean.

- ``combined``      : concat(vritti_mapper, pse_meaning, pse_resonance).

Torch-free. varna_lens is pure Python. If varna_lens is unavailable the PSE
backends raise a clear error at construction (the vritti_mapper backend always
works).
"""
from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np

from .symbolu_engine import SymbolUEngine, _tokenize


# --------------------------------------------------------------------------- #
# Backend 0: vritti_mapper (original) — uniform wrapper over SymbolUEngine
# --------------------------------------------------------------------------- #
class VrittiMapperBackend:
    name = "vritti_mapper"

    def __init__(self):
        self._eng = SymbolUEngine()
        self.dim = self._eng.dim

    def encode(self, text: str) -> List[float]:
        return self._eng.encode(text)


# --------------------------------------------------------------------------- #
# PSE shared machinery (varna_lens + lexicon)
# --------------------------------------------------------------------------- #
def _load_varna_lens():
    from varna_lens import varna_lens as V  # pure python, torch-free
    return V


def _build_vocabs(V):
    """Fixed, sorted vocabularies so every PSE vector has a stable dimension."""
    cons = V.LEX["consonants"]
    vows = V.LEX["vowels"]
    tags = set()
    for d in cons.values():
        ep = d.get("expanded_properties", {}) or {}
        for t in ep.get("domain_tags", []) or []:
            tags.add(t)
    tag_vocab = sorted(tags)
    # Vowel semantic states (liberating + binding) as meaning tokens.
    vstates = set()
    for d in vows.values():
        for f in ("liberating_state", "binding_state"):
            if d.get(f):
                vstates.add(f"V::{d[f]}")
    vstate_vocab = sorted(vstates)
    return tag_vocab, vstate_vocab


class _PSEBase:
    """Holds the shared varna_lens decomposition + caches."""

    def __init__(self):
        self.V = _load_varna_lens()
        self.tag_vocab, self.vstate_vocab = _build_vocabs(self.V)
        self.tag_index = {t: i for i, t in enumerate(self.tag_vocab)}
        self.vstate_index = {t: i for i, t in enumerate(self.vstate_vocab)}
        self._cache: Dict[str, list] = {}

    def varnas(self, word: str):
        """[(type, key, polarity)] from the canonical varna_lens engine."""
        if word in self._cache:
            return self._cache[word]
        try:
            res, _src, _warn = self.V.analyze(word, model="op")
            seq = [(it["type"], it["key"], it.get("polarity")) for it in res["sequence"]]
            valence = res.get("emergent_valence", {}) or {}
            whole = res.get("whole_word_essence", {}) or {}
        except Exception:
            seq, valence, whole = [], {}, {}
        out = (seq, valence, whole)
        self._cache[word] = out
        return out


# --------------------------------------------------------------------------- #
# Backend 1: pse_meaning — semantic domain-tag histogram
# --------------------------------------------------------------------------- #
class PSEMeaningBackend(_PSEBase):
    name = "pse_meaning"

    def __init__(self):
        super().__init__()
        self.dim = len(self.tag_vocab) + len(self.vstate_vocab)

    def _word_vec(self, word: str) -> np.ndarray:
        seq, _val, _whole = self.varnas(word)
        v = np.zeros(self.dim, dtype=np.float64)
        cons = self.V.LEX["consonants"]
        vows = self.V.LEX["vowels"]
        nt = len(self.tag_vocab)
        for typ, key, _pol in seq:
            if typ == "C":
                d = cons.get(key, {})
                ep = d.get("expanded_properties", {}) or {}
                for t in ep.get("domain_tags", []) or []:
                    if t in self.tag_index:
                        v[self.tag_index[t]] += 1.0
            elif typ == "V":
                d = vows.get(key, {})
                for f in ("liberating_state", "binding_state"):
                    tok = f"V::{d.get(f)}"
                    if tok in self.vstate_index:
                        v[nt + self.vstate_index[tok]] += 0.5
        s = v.sum()
        return v / s if s > 0 else v

    def encode(self, text: str) -> List[float]:
        toks = _tokenize(text)
        if not toks:
            return [0.0] * self.dim
        acc = np.zeros(self.dim, dtype=np.float64)
        for w in toks:
            acc += self._word_vec(w)
        return (acc / len(toks)).tolist()


# --------------------------------------------------------------------------- #
# Backend 2: pse_resonance — polarity / valence "resonance" vector
# --------------------------------------------------------------------------- #
class PSEResonanceBackend(_PSEBase):
    name = "pse_resonance"
    # [frac_liberating, frac_binding, net_valence, whole_word_sign,
    #  lean_liberating, lean_binding, lean_mixed]
    dim = 7

    def _word_vec(self, word: str) -> np.ndarray:
        seq, val, whole = self.varnas(word)
        cons_pol = [p for (t, k, p) in seq if t == "C" and p in ("created", "destroyed")]
        n = len(cons_pol)
        lib = sum(1 for p in cons_pol if p == "created")  # CV onset -> liberating(+)
        bind = sum(1 for p in cons_pol if p == "destroyed")  # bare coda -> binding(-)
        frac_lib = lib / n if n else 0.0
        frac_bind = bind / n if n else 0.0
        net = (lib - bind) / n if n else 0.0
        sign = {"+": 1.0, "−": -1.0, "-": -1.0}.get(str(whole.get("sign", "")), 0.0)
        lean = str(val.get("lean", ""))
        return np.array([
            frac_lib, frac_bind, net, sign,
            1.0 if lean == "liberating" else 0.0,
            1.0 if lean == "binding" else 0.0,
            1.0 if lean == "mixed" else 0.0,
        ], dtype=np.float64)

    def encode(self, text: str) -> List[float]:
        toks = _tokenize(text)
        if not toks:
            return [0.0] * self.dim
        acc = np.zeros(self.dim, dtype=np.float64)
        for w in toks:
            acc += self._word_vec(w)
        return (acc / len(toks)).tolist()


# --------------------------------------------------------------------------- #
# Backend 3: combined
# --------------------------------------------------------------------------- #
class CombinedBackend:
    name = "combined"

    def __init__(self):
        self.parts = [VrittiMapperBackend(), PSEMeaningBackend(), PSEResonanceBackend()]
        self.dim = sum(p.dim for p in self.parts)

    def encode(self, text: str) -> List[float]:
        out: List[float] = []
        for p in self.parts:
            out.extend(p.encode(text))
        return out


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
_REGISTRY = {
    "vritti_mapper": VrittiMapperBackend,
    "pse_meaning": PSEMeaningBackend,
    "pse_resonance": PSEResonanceBackend,
    "combined": CombinedBackend,
}

BACKENDS = list(_REGISTRY.keys())


def get_backend(name: str):
    if name not in _REGISTRY:
        raise ValueError(f"unknown U backend {name!r}; choose from {BACKENDS}")
    return _REGISTRY[name]()


def u_matrix(texts: Sequence[str], backend) -> np.ndarray:
    """Stack U vectors for a list of texts using a constructed backend object."""
    return np.stack([np.asarray(backend.encode(t), dtype=np.float64) for t in texts])


if __name__ == "__main__":
    words = ["happy", "glad", "joyful", "cheerful", "merry", "sad", "war", "peace"]
    for name in BACKENDS:
        b = get_backend(name)
        print(f"\n=== backend={name}  dim={b.dim} ===")
        for w in words:
            v = b.encode(w)
            nz = sum(1 for x in v if abs(x) > 1e-9)
            print(f"  {w:9} nnz={nz:3d}  ||u||={np.linalg.norm(v):.3f}")
