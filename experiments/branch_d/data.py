"""Branch D data loading + feature construction (reachable public data).

Builds, from word -> ARPABET (CMUdict), articulatory features (PanPhon) and a
semantic observable Y (Warriner VAD):

  PHON_feat  : per-word mean of per-phoneme PanPhon articulatory features
               + length summaries (n_phonemes, n_syllables)   [the phonology baseline]
  E_max_feat : per-word ARPABET phoneme-identity COUNT vector  [maximal gloss-free E]

By the data-processing inequality, any deterministic phoneme-level essence table
E = g(phoneme) aggregated linearly is a linear function of the phoneme counts, so
the incremental predictive value of E_max over PHON upper-bounds that of any such E
(within the linear/additive model class).

Raw datasets are read from local files (fetched separately, NOT committed; license:
CMUdict BSD-2, PanPhon MIT, Warriner et al. 2013 academic norms). No gloss enters
E_max or PHON. Tests use tiny inline fixtures, not the real data.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import numpy as np

# frozen ARPABET (39) -> single representative IPA segment for PanPhon lookup.
# Affricates/diphthongs use a documented single-segment proxy (nucleus / sibilant).
ARPABET_IPA = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "a", "AY": "a",
    "EH": "ɛ", "ER": "ə", "EY": "e", "IH": "ɪ", "IY": "i", "OW": "o",
    "OY": "ɔ", "UH": "ʊ", "UW": "u",
    "B": "b", "CH": "ʃ", "D": "d", "DH": "ð", "F": "f", "G": "ɡ", "HH": "h",
    "JH": "ʒ", "K": "k", "L": "l", "M": "m", "N": "n", "NG": "ŋ", "P": "p",
    "R": "ɹ", "S": "s", "SH": "ʃ", "T": "t", "TH": "θ", "V": "v", "W": "w",
    "Y": "j", "Z": "z", "ZH": "ʒ",
}
ARPABET = sorted(ARPABET_IPA)               # fixed 39-phoneme column order
VOWELS = {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY",
          "OW", "OY", "UH", "UW"}
_STRESS = re.compile(r"\d+$")


def parse_cmudict(path) -> dict[str, list[str]]:
    """word -> ARPABET phoneme list (stress stripped); first pronunciation only."""
    out: dict[str, list[str]] = {}
    for line in Path(path).read_text(encoding="latin-1").splitlines():
        line = line.strip()
        if not line or line.startswith(";;;"):
            continue
        parts = line.split()
        word = parts[0].lower()
        if word.endswith(")"):              # variant entry like "word(2)"
            continue
        phones = [_STRESS.sub("", p) for p in parts[1:]]
        phones = [p for p in phones if p in ARPABET_IPA]
        if phones:
            out.setdefault(word, phones)
    return out


def panphon_features(path) -> tuple[list[str], dict[str, np.ndarray]]:
    """ipa segment -> articulatory feature vector (PanPhon ipa_all.csv)."""
    rows = list(csv.reader(Path(path).read_text(encoding="utf-8").splitlines()))
    header = rows[0]
    feat_names = header[1:]
    table: dict[str, np.ndarray] = {}
    for r in rows[1:]:
        if not r:
            continue
        table[r[0]] = np.array([float(x) if x not in ("", "+", "-") else
                                {"+": 1.0, "-": -1.0, "": 0.0}.get(x, 0.0)
                                for x in r[1:]], dtype=float)
    return feat_names, table


def phoneme_feature_matrix(panphon_table) -> tuple[np.ndarray, list[str]]:
    """ARPABET phoneme -> articulatory vector via the frozen IPA map.
    Returns (39 x F) matrix in ARPABET order and the list of uncovered phonemes."""
    any_vec = next(iter(panphon_table.values()))
    F = len(any_vec)
    M = np.zeros((len(ARPABET), F))
    missing = []
    for i, ph in enumerate(ARPABET):
        ipa = ARPABET_IPA[ph]
        if ipa in panphon_table:
            M[i] = panphon_table[ipa]
        else:
            missing.append(f"{ph}->{ipa}")
    return M, missing


def parse_warriner(path) -> dict[str, tuple[float, float, float]]:
    """word -> (valence, arousal, dominance) means (V/A/D .Mean.Sum)."""
    rows = list(csv.reader(Path(path).read_text(encoding="utf-8").splitlines()))
    hdr = rows[0]
    iw = hdr.index("Word")
    iv, ia, idom = hdr.index("V.Mean.Sum"), hdr.index("A.Mean.Sum"), hdr.index("D.Mean.Sum")
    out = {}
    for r in rows[1:]:
        if not r:
            continue
        try:
            out[r[iw].lower()] = (float(r[iv]), float(r[ia]), float(r[idom]))
        except (ValueError, IndexError):
            continue
    return out


def build_dataset(cmudict_path, panphon_path, warriner_path):
    """Join the three sources; return feature matrices + Y + diagnostics.

    Returns dict with E_max (n×39 counts), PHON (n×(F+2) mean articulatory + length),
    Y (n×3 VAD), words, coverage diagnostics.
    """
    pron = parse_cmudict(cmudict_path)
    _, pp = panphon_features(panphon_path)
    phon_mat, missing = phoneme_feature_matrix(pp)
    vad = parse_warriner(warriner_path)
    idx = {ph: i for i, ph in enumerate(ARPABET)}

    words, E, PH, Y = [], [], [], []
    for w, (v, a, dom) in vad.items():
        if w not in pron:
            continue
        phones = pron[w]
        counts = np.zeros(len(ARPABET))
        for p in phones:
            counts[idx[p]] += 1.0
        nsyl = sum(1 for p in phones if p in VOWELS)
        mean_artic = phon_mat[[idx[p] for p in phones]].mean(axis=0)
        words.append(w)
        E.append(counts)
        PH.append(np.concatenate([mean_artic, [len(phones), nsyl]]))
        Y.append([v, a, dom])
    return {
        "words": words,
        "E_max": np.array(E),
        "PHON": np.array(PH),
        "Y": np.array(Y),
        "n": len(words),
        "n_warriner": len(vad), "n_cmudict": len(pron),
        "missing_phonemes": missing,
    }
