#!/usr/bin/env python3
"""B1.4b′ — covariate / baseline adapter (versioned). Wires the McRae length/frequency covariate
(`G_LENGTH_FREQUENCY`) from McRae `CONCS_brm.txt` (KF/BNC/syllables), and provides a strict loader
for an operator-supplied sentiment/affect lexicon (`H_SENTIMENT_LEXICON`).

STRICT: this adapter NEVER fabricates sentiment. If no approved sentiment source is supplied (or a
concept is not covered by it), that concept simply carries no `sentiment` covariate, which keeps
`H_SENTIMENT_LEXICON` visibly pending in the scorer. Raw McRae data / lexicons are read from
private/operator paths and are NEVER committed. Stage A′ + prep are imported READ-ONLY.
"""
from __future__ import annotations

import csv
import math
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stage_a_prime_coverage as A            # READ-ONLY
import b1_4b_prime_prepare_mcrae_y as PREP    # _base tag-strip + source resolver (no run)

# accepted (word, value) column names for common license-clear affect lexicons
SENTIMENT_WORD_COLS = ("Word", "word", "term", "Term")
SENTIMENT_VALUE_COLS = ("V.Mean.Sum", "valence", "Valence", "value", "sentiment")   # Warriner / NRC-VAD / generic


def load_mcrae_covariates(source_dir: pathlib.Path) -> dict:
    """concept(lower) -> {kf, bnc, syll}. Reads McRae CONCS_brm.txt (private; never committed)."""
    concs = PREP._resolve(pathlib.Path(source_dir), "CONCS_brm.txt")
    out = {}
    for r in csv.DictReader(open(concs, newline=""), delimiter="\t"):
        c = (r.get("Concept") or "").strip().lower()
        if not c:
            continue
        def _f(col):
            try:
                return float(r.get(col) or "nan")
            except ValueError:
                return float("nan")
        out[c] = {"kf": _f("KF"), "bnc": _f("BNC"), "syll": _f("Length_Syllables")}
    return out


def load_sentiment_lexicon(path, value_col: str | None = None) -> dict | None:
    """word(lower) -> float sentiment/affect value. Returns None if `path` is None/missing.
    NEVER fabricates; only reads a supplied, license-clear lexicon (Warriner VAD / NRC-VAD / generic)."""
    if not path:
        return None
    p = pathlib.Path(path)
    if not p.exists():
        return None
    delim = "\t" if p.suffix.lower() in (".tsv", ".txt") else ","
    with open(p, newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter=delim))
    if not rows:
        return {}
    cols = rows[0].keys()
    wcol = next((c for c in SENTIMENT_WORD_COLS if c in cols), None)
    vcol = value_col or next((c for c in SENTIMENT_VALUE_COLS if c in cols), None)
    if wcol is None or vcol is None:
        raise ValueError(f"sentiment lexicon missing word/value column (have {list(cols)})")
    out = {}
    for r in rows:
        w = (r.get(wcol) or "").strip().lower()
        try:
            out[w] = float(r.get(vcol))
        except (TypeError, ValueError):
            continue
    return out


def build_records(concepts, source_dir, sentiment_path=None, value_col=None):
    """Build scorer records (phonemes + covariates) for `concepts`, aligned row-for-row.
    - frequency (G): log1p(KF), with BNC fallback; syllable length attached.
    - sentiment (H): attached ONLY where the supplied lexicon covers the concept; else absent
      (keeps H pending). No fabrication.
    Returns (records, coverage)."""
    mc = load_mcrae_covariates(source_dir)
    sent = load_sentiment_lexicon(sentiment_path, value_col)
    recs, n_freq, n_sent = [], 0, 0
    for c in concepts:
        base = PREP._base(c)
        ph = A.normalize(base, "A_PRIME_EN")["phonemes"]
        covars = {}
        m = mc.get(c.lower()) or mc.get(base)
        if m:
            f = m["kf"] if math.isfinite(m["kf"]) else m["bnc"]
            if f is not None and math.isfinite(f):
                covars["freq"] = math.log1p(max(0.0, f)); n_freq += 1
            if math.isfinite(m.get("syll", float("nan"))):
                covars["length_syll"] = m["syll"]
        if sent is not None:
            v = sent.get(base, sent.get(c.lower()))
            if v is not None:
                covars["sentiment"] = float(v); n_sent += 1
        recs.append({"phonemes": ph, "covars": covars})
    coverage = {
        "n_concepts": len(concepts),
        "n_with_frequency": n_freq,
        "n_with_sentiment": n_sent,
        "sentiment_source_supplied": sent is not None,
        "sentiment_full_coverage": (sent is not None and n_sent == len(concepts)),
        "frequency_full_coverage": (n_freq == len(concepts)),
    }
    return recs, coverage


if __name__ == "__main__":
    print("B1.4b′ covariate adapter: wires McRae KF/BNC frequency (G); strict sentiment loader (H).")
    print("No fabrication; no real run; raw data / lexicons never committed.")
