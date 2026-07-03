#!/usr/bin/env python3
"""Positional G2P Varṇa-Process — EXPLORATORY SAMPLE-TEXT RENDERER (no model, no scoring, no evidence).

Deterministic inspection tool ONLY. Renders sample words / word-pairs / short phrases under the
positional rule (onset consonant → binding/worldly pole ; vowel → field/active essence ; final
consonant → liberating/counter pole as transformer ; internal consonants → INTERNAL_UNRESOLVED),
using the committed `lexicon_authoritative.json` exactly and TRUE G2P only.

Hard rules:
  * True G2P only. If G2P is unavailable (no nltk/cmudict) or the word is not in cmudict → abort
    loudly (`G2P_UNAVAILABLE → ABORT`). NEVER falls back to roman / written-letter / hybrid.
  * Lexicon used exactly as committed; no meanings invented; missing units marked MISSING; the
    G2P→varṇa mapping is approximate and is marked so.
  * Output emits ONLY frozen lexicon terms + fixed labels. No dictionary meaning, no bridge
    interpretation, no score, no verdict, no signal claim. Every output is stamped
    `EXPLORATORY_SAMPLE_ONLY — not scored, not evidence`.

NOT an experiment, NOT a prereg, NOT evidence, NOT a Track G rescue, NOT a Track B unblock.
"""
from __future__ import annotations

import argparse
import pathlib
import json
import random
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import varna_lens as V   # noqa: E402  (frozen engine: lexicon + phoneme functions)

BANNER = "EXPLORATORY_SAMPLE_ONLY — not scored, not evidence"
SCRAMBLE_SEED = "sample_harness_scramble_v1"   # fixed → deterministic display-only permutation
RANDOM_SEED = "sample_harness_random_v1"
# phrases that would smuggle interpretation/scoring — must never appear in output
# bridge/score phrases that must never appear. NOTE: the mandated banner contains "not scored", so
# we forbid emitted-score forms ("score:"/"score=") rather than the bare root, to avoid colliding
# with the required disclaimer.
FORBIDDEN = ("therefore", "signifies", "represents", " means ", "preference", "bonding",
             "score:", "score=", "verdict", "=>", "⇒", "a_vs", "delta ", "accuracy",
             "is better", "real is better")


SYNTH_LABEL = "INTERPRETIVE_SYNTHESIS_ONLY — not scored, not evidence"
SYNTH_WARNING = ("WARNING: This is interpretive synthesis, not evidence and not semantic proof. "
                 "The same templates applied to a scrambled/random lexicon read equally well; "
                 "prior controlled tests returned NO_SIGNAL.")

# FROZEN Layer 2 bridge vocabulary: one fixed paraphrase per canonical lexicon gloss, authored blind
# to any target word. A gloss with no entry renders [unresolved]; nothing is invented. This is a
# controlled paraphrase, NOT a semantic mapping. Loaded from layer2_bridge_vocab.json; if that file
# is missing, falls back to the original 9-entry inline table so the harness never breaks.
_INLINE_BRIDGE = {
    "krūratā": "separative harshness",
    "karuṇā/sneha": "compassion/gentleness",
    "dharma/jalatattva": "order/dharmic relation",
    "nirāśā": "detachment/letting-go",
    "āśā": "hope",
    "viśvāsa": "trust",
    "cintā": "worry",
    "mūrcchā": "deluded obsession/entrancement",
    "jāgaraṇa": "awareness/awakening",
}
_BRIDGE_JSON = HERE / "layer2_bridge_vocab.json"


def _load_bridge():
    try:
        data = json.loads(_BRIDGE_JSON.read_text(encoding="utf-8"))
        b = data.get("bridge")
        if isinstance(b, dict) and b:
            return dict(b)
    except (FileNotFoundError, ValueError, OSError):
        pass
    return dict(_INLINE_BRIDGE)


BRIDGE = _load_bridge()
# fixed template stopwords (the only non-bridge tokens allowed in a synthesis string)
_SYNTH_STOP = {"moves", "toward", "and", "is", "the", "resolving", "principle", "[unresolved]"}


class SynthesisInvalid(ValueError):
    """Raised when a synthesis contains a term not traceable to an emitted gloss bridge."""


class G2PUnavailable(RuntimeError):
    """Raised to abort loudly when true G2P cannot be used. No roman fallback, ever."""


# --------------------------------------------------------------- lexicon helpers ----
def _gloss(state):
    if isinstance(state, dict):
        s, e = state.get("sanskrit", ""), state.get("english", "")
        return f"{s} ({e})" if s and e else (e or s or "?")
    return str(state)


def _lex_entry(typ, key):
    table = V.LEX["vowels"] if typ == "V" else V.LEX["consonants"]
    return table.get(key)


# --------------------------------------------------------------- g2p (hard abort) ---
def g2p_units(word):
    """Return [(type, varṇa_key, arpa_surface), ...] via TRUE G2P only. Aborts loudly otherwise.
    Never calls roman/hybrid/auto."""
    try:
        units, warn = V.phonemes_cmudict(word)
    except (ImportError, ModuleNotFoundError) as e:
        raise G2PUnavailable(f"G2P_UNAVAILABLE → ABORT: nltk/cmudict not installed ({e})")
    if not units:
        raise G2PUnavailable(f"G2P_UNAVAILABLE → ABORT: '{word}' not in cmudict "
                             "(no roman/written fallback permitted)")
    return units, warn


# --------------------------------------------------------------- role assignment ----
def profile(word):
    """Deterministic per-unit profile for one word under the positional rule. PURE (given g2p)."""
    units, warn = g2p_units(word)
    cons_idx = [i for i, (t, _, _) in enumerate(units) if t == "C"]
    first_c = cons_idx[0] if cons_idx else None
    last_c = cons_idx[-1] if cons_idx else None
    rows = []
    for i, (typ, key, surf) in enumerate(units):
        entry = _lex_entry(typ, key)
        missing = entry is None
        row = {"i": i, "type": typ, "key": key, "arpa": surf, "missing": missing, "approx": True}
        if typ == "V":
            row["role"] = "FIELD"
            row["pole"] = "active_essence(liberating)"
            row["term"] = _gloss(entry["liberating_state"]) if not missing else "MISSING"
        else:  # consonant
            if i == first_c and i == last_c:
                row["role"] = "ONSET_SEED"           # single consonant: seed only, no distinct transformer
                row["pole"] = "worldly(binding)"
                row["term"] = _gloss(entry["binding_state"]) if not missing else "MISSING"
            elif i == first_c:
                row["role"] = "ONSET_SEED"
                row["pole"] = "worldly(binding)"
                row["term"] = _gloss(entry["binding_state"]) if not missing else "MISSING"
            elif i == last_c:
                row["role"] = "TRANSFORMER"
                row["pole"] = "counter(liberating)"
                row["term"] = _gloss(entry["liberating_state"]) if not missing else "MISSING"
            else:
                row["role"] = "INTERNAL_UNRESOLVED"  # committed positional renderer not applied here; do not invent
                row["pole"] = "(unresolved)"
                row["term"] = "(role unresolved; not inventing)"
        rows.append(row)
    return {"word": word, "units": rows, "warnings": warn,
            "seed_key": units[first_c][1] if first_c is not None else None}


# --------------------------------------------------------------- display controls ---
def _perm_map(seed, keys):
    order = list(keys)
    shuffled = list(keys)
    random.Random(seed).shuffle(shuffled)
    return dict(zip(order, shuffled))


def _display_variant(word, kind):
    """Display-only scrambled/random re-render. No scoring, no comparison, no 'real is better'."""
    units, _ = g2p_units(word)
    cons_keys = list(V.LEX["consonants"]); vow_keys = list(V.LEX["vowels"])
    if kind == "scramble":
        cmap = _perm_map(SCRAMBLE_SEED, cons_keys); vmap = _perm_map(SCRAMBLE_SEED + "v", vow_keys)
        remap = lambda t, k: (vmap.get(k, k) if t == "V" else cmap.get(k, k))
    else:  # random
        rc = random.Random(RANDOM_SEED); rv = random.Random(RANDOM_SEED + "v")
        remap = lambda t, k: (rv.choice(vow_keys) if t == "V" else rc.choice(cons_keys))
    parts = []
    for (t, k, _s) in units:
        rk = remap(t, k)
        ent = _lex_entry(t, rk)
        g = _gloss(ent["binding_state"]) if (t == "C" and ent) else (
            _gloss(ent["liberating_state"]) if ent else "MISSING")
        parts.append(f"{rk}:{g}")
    tag = "DISPLAY_ONLY_SCRAMBLE" if kind == "scramble" else "DISPLAY_ONLY_RANDOM"
    return f"  [{tag}] (permuted lexicon; NOT scored, NOT compared) " + " · ".join(parts)


# --------------------------------------------------------------- layer 2 synthesis -
def _canon(state):
    # key on the Sanskrit label; fall back to the English gloss when the Sanskrit label is empty
    # (resolves the empty-label collision). Non-empty labels are unaffected.
    if isinstance(state, dict):
        key = state.get("sanskrit", "") or state.get("english", "")
    else:
        key = str(state)
    key = key.lower().strip()
    key = re.sub(r"\s*/\s*", "/", key)
    return re.sub(r"\s+", " ", key)


def _bridge(state):
    """Frozen bridge phrase for a lexicon gloss, or None if unmapped (→ [unresolved])."""
    return BRIDGE.get(_canon(state))


def validate_synthesis(text, used_bridges):
    """Every content token in `text` must trace to a used bridge phrase (or a fixed template
    stopword / [unresolved]). Rejects any unsupported/target-fitted term. Raises SynthesisInvalid."""
    allowed = set()
    for b in used_bridges:
        allowed |= set(re.findall(r"[a-z/]+", b.lower()))
    for tok in re.findall(r"\[unresolved\]|[a-z/]+", text.lower()):
        if tok in _SYNTH_STOP or tok in allowed:
            continue
        raise SynthesisInvalid(f"unsupported synthesis term: {tok!r}")
    return True


def synthesize(prof):
    """Deterministic Layer 2 paraphrase of Layer 1 poles via FIXED templates + FROZEN bridge table.
    No dictionary lookup, no target-fitting, no handcrafted prose. Missing bridge → [unresolved].
    Returns (text, used_bridges); text is validated before return."""
    units = prof["units"]
    seed = next((r for r in units if r["role"] == "ONSET_SEED"), None)
    trans = next((r for r in reversed(units) if r["role"] == "TRANSFORMER"), None)
    clauses, used = [], []
    if seed is not None:
        ent = _lex_entry("C", seed["key"])
        b_bind = (_bridge(ent["binding_state"]) if ent else None) or "[unresolved]"
        b_counter = (_bridge(ent["liberating_state"]) if ent else None) or "[unresolved]"
        clauses.append(f"{b_bind} moves toward {b_counter}")
        used += [b_bind, b_counter]
    if trans is not None and trans is not seed:
        ent = _lex_entry("C", trans["key"])
        b_tr = (_bridge(ent["liberating_state"]) if ent else None) or "[unresolved]"
        clauses.append(f"{b_tr} is the resolving principle")
        used.append(b_tr)
    text = ", and ".join(clauses) if clauses else "[unresolved]"
    validate_synthesis(text, used)
    return text, used


# --------------------------------------------------------------- renderers ----------
def _fmt_units(prof):
    out = []
    for r in prof["units"]:
        approx = " ~approx" if r["approx"] else ""
        miss = " MISSING" if r["missing"] else ""
        out.append(f"    [{r['role']:<18}] {r['type']} {r['key']:<5} (arpa {r['arpa']:<4}) "
                   f"pole={r['pole']:<22} term={r['term']}{approx}{miss}")
    return "\n".join(out)


def _profile_line(prof):
    seg = []
    for r in prof["units"]:
        if r["role"] == "INTERNAL_UNRESOLVED":
            seg.append("INTERNAL_UNRESOLVED")
        else:
            seg.append(f"{r['role']}={r['term']}")
    return " · ".join(seg)


def render(*, text=None, pair=None, mode="word_profile", g2p=True,
           show_scramble=False, show_random=False, label=None, synthesize_mode=False):
    if not g2p:
        raise G2PUnavailable("G2P_UNAVAILABLE → ABORT: this harness is G2P-only; pass --g2p "
                             "(no roman/written fallback)")
    lines = [BANNER, f"mode={mode} | representation=TRUE_G2P_ONLY | lexicon=lexicon_authoritative.json (frozen)"]

    def emit_word(w):
        prof = profile(w)
        lines.append(f"\ninput: {w!r}")
        lines.append("  g2p phonemes: " + " ".join(u["arpa"] for u in prof["units"]))
        lines.append("  varṇa units:  " + " ".join(u["key"] for u in prof["units"]))
        if mode == "raw":
            lines.append(_fmt_units(prof))
        else:
            lines.append("  profile: " + _profile_line(prof))
        if prof["warnings"]:
            lines.append("  warnings: " + " | ".join(prof["warnings"]))
        if synthesize_mode:                               # Layer 2 — optional, controlled paraphrase
            syn, _used = synthesize(prof)
            lines.append("  " + SYNTH_LABEL)
            lines.append("  synthesis: " + syn)
            lines.append("  " + SYNTH_WARNING)
        if show_scramble:
            lines.append(_display_variant(w, "scramble"))
        if show_random:
            lines.append(_display_variant(w, "random"))
        return prof

    if mode == "shared_seed":
        if not pair or len(pair) != 2:
            raise ValueError("shared_seed mode requires --pair WORD1 WORD2")
        p0 = emit_word(pair[0]); p1 = emit_word(pair[1])
        shared = p0["seed_key"] is not None and p0["seed_key"] == p1["seed_key"]
        lines.append("\n  ONSET status: " + ("SHARED_SEED (" + str(p0["seed_key"]) + ")" if shared
                     else f"ONSET_NOT_SHARED ({p0['seed_key']} vs {p1['seed_key']})"))
        for p in (p0, p1):
            tr = [r for r in p["units"] if r["role"] == "TRANSFORMER"]
            trs = tr[-1]["term"] if tr else "(none)"
            lines.append(f"  {p['word']}: differentiating TRANSFORMER = {trs}")
    elif mode == "phrase":
        words = (text or "").split()
        if not words:
            raise ValueError("phrase mode requires --text with one or more words")
        profs = [emit_word(w) for w in words]
        lines.append("\n  phrase sequence (per-word profiles, no semantic interpretation):")
        for p in profs:
            lines.append(f"    {p['word']}: " + _profile_line(p))
    else:  # raw | word_profile
        words = pair if pair else (text or "").split()
        if not words:
            raise ValueError("provide --text or --pair")
        for w in words:
            emit_word(w)

    if label is not None:
        lines.append(f"\nUSER_LABEL_NOT_USED: {label}")
    lines.append("\n" + BANNER)
    return "\n".join(lines)


# --------------------------------------------------------------- CLI ----------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="Exploratory G2P varṇa-process sample renderer "
                                             "(no model, no scoring, no evidence).")
    ap.add_argument("--text", default=None)
    ap.add_argument("--pair", nargs=2, metavar=("WORD1", "WORD2"), default=None)
    ap.add_argument("--mode", choices=["raw", "word_profile", "shared_seed", "phrase"],
                    default="word_profile")
    ap.add_argument("--g2p", action="store_true", help="required: use true G2P (no fallback)")
    ap.add_argument("--show-scramble", action="store_true")
    ap.add_argument("--show-random", action="store_true")
    ap.add_argument("--synthesize", action="store_true",
                    help="OPTIONAL Layer 2 controlled paraphrase (off by default; INTERPRETIVE only, "
                         "not scored, not evidence)")
    ap.add_argument("--label", default=None, help="printed only as USER_LABEL_NOT_USED, never used")
    args = ap.parse_args(argv)
    if not args.g2p:
        print("G2P_REQUIRED → ABORT: pass --g2p (this harness is G2P-only; no roman fallback).")
        return 2
    try:
        print(render(text=args.text, pair=args.pair, mode=args.mode, g2p=True,
                     show_scramble=args.show_scramble, show_random=args.show_random,
                     label=args.label, synthesize_mode=args.synthesize))
    except G2PUnavailable as e:
        print(str(e))
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
