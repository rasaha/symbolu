#!/usr/bin/env python3
"""Varṇa Lens — reflection / naming tool (the product).

Architecture (the honest one): a DETERMINISTIC varṇa profile (same word → same chain, always) is the
seed; an LLM AUTHORS a reflection or naming palette on top of it, framed as a consistent symbolic mirror
— never as the word's decoded meaning. Backed by: H0 (determinism, proven) + H1 (the profile reliably
channels readers to a shared reading, RESULTS_H1_CONVERGENCE.md). It does NOT claim to decode meaning
(H3, falsified) and stays firewalled from any truth/scoring use.

Usage:
    python reflect.py scaffold "compassion"          # just the deterministic chain (JSON)
    python reflect.py reflect  "courage"             # authored reflection (needs ANTHROPIC_API_KEY,
    python reflect.py name "Lyra" "Veda" "Soma"      #   else prints scaffold + ready-to-paste prompt)
"""
import argparse, json, os, pathlib
import varna_lens as V

_LEX = None
def _lex():
    """Lexicon consonants dict (cached)."""
    global _LEX
    if _LEX is None:
        p = pathlib.Path(__file__).with_name("lexicon_authoritative.json")
        _LEX = json.loads(p.read_text(encoding="utf-8"))["consonants"]
    return _LEX


def _expanded(key):
    return (_lex().get(key) or {}).get("expanded_properties")


def _pole_text(p):
    """(sanskrit, english) from a pole that may be a {sanskrit,english} dict or a plain string."""
    if isinstance(p, dict):
        return p.get("sanskrit", ""), p.get("english", "")
    return "", (p or "")


def term_glossary(word):
    """Ordered {Sanskrit term: English} for every Sanskrit-named pole of the word's consonants — lets the
    chain carry Sanskrit texture while keeping the author grounded in the precise English meaning."""
    phon, _w, _src = V.auto_phonemes(word)
    gl = {}
    for typ, key, _surf in phon:
        if typ != "C":
            continue
        c = _lex().get(key)
        if not c:
            continue
        for pole in ("negative", "positive"):
            skt, eng = _pole_text(c.get(pole))
            if skt:
                gl.setdefault(skt, eng)
    return gl


def _glossary_block(word):
    gl = term_glossary(word)
    if not gl:
        return ""
    return ("\nGlossary (Sanskrit term = English grounding): "
            + "; ".join(f"{k} = {v}" for k, v in gl.items()))


def acoustic_imagery(word):
    """Per-consonant source imagery for the word's sounds (vṛtti · elemental · first acoustic root)."""
    phon, _w, _src = V.auto_phonemes(word)
    lines = []
    for typ, key, _surf in phon:
        if typ != "C":
            continue
        ep = _expanded(key)
        if not ep:
            continue
        vr = ep.get("vrtti", {})
        bits = [f"{vr.get('name','')} ({vr.get('english','')})"] if vr else []
        if ep.get("elemental"):
            bits.append(ep["elemental"])
        if ep.get("acoustic_roots"):
            bits.append(ep["acoustic_roots"][0])
        iast = (_lex().get(key) or {}).get("iast", key)
        lines.append(f"  {iast}: " + " · ".join(b for b in bits if b))
    return lines

HONESTY_RULES = """LANGUAGE RULES (hard — this is what keeps it honest):
- NEVER use: "means", "represents", "reveals", "signifies", "your word is", "this shows you are",
  "you will", "decodes", "the hidden meaning".
- ALWAYS frame as invitation / the reader's own projection: "invites reflection on", "you might sit
  with", "notice whether", "where in your life…", "if this were true for you today…", "evokes / tends
  toward" (for names).
- Keep the vivid Sanskrit images and the worldly→dissolution (⤳) motion; strip only the truth claim.
- A reflection ends in a question to the user, never a verdict."""

DUAL_LANGUAGE = ("DUAL-LANGUAGE: the chain names each propensity by its Sanskrit term (e.g. Āśā, Karuṇā) "
                 "— use those for evocative texture, and lean on the English glossary below for accurate "
                 "grounding. Name the Sanskrit term, let its English meaning steer the sense.")


def scaffold(word, by="hybrid"):
    # by: hybrid (consonants by sound + vowels by spelling) | sound (g2p/auto) | spelling (literal roman)
    kw = {"hybrid": {"hybrid": True}, "sound": {}, "spelling": {"roman": True}}.get(by, {"hybrid": True})
    d, src, _warn = V.analyze(word, model="op", **kw)          # model="op" = the vowel-attachment rule
    whole = d.get("whole_word_essence") or {}
    return {"word": word, "reading_mode": by, "source": src, "chain": d.get("essence_short"),
            "chain_detail": d.get("essence"), "whole_word_essence": whole.get("essence"),
            "glossary": term_glossary(word)}


def reflect_prompt(s, rich=False):
    note = f"\nWhole-word note: {s['whole_word_essence']}" if s["whole_word_essence"] else ""
    imagery = ""
    if rich:
        lines = acoustic_imagery(s["word"])
        if lines:
            imagery = ("\nOptional source imagery for each sound (traditional acoustic-root associations — "
                       "use sparingly, as evocative texture, never as claims):\n" + "\n".join(lines))
    glossary = _glossary_block(s["word"])
    return f"""You are the authoring voice of "Varṇa Lens", a contemplative reflection tool.
{HONESTY_RULES}
{DUAL_LANGUAGE}

THE MIRROR FOR "{s['word']}"  (read by sound: {s['source']})
A consistent symbolic reflection — NOT a claim about this word.
Its sounds carry this fixed propensity chain (each − worldly pole shown easing ⤳ toward its spiritual
counter; + = an active/anchored pole):
  {s['chain']}{note}{glossary}{imagery}

Write the reflection:
1. One opening line naming the chain's images (as images, not claims).
2. Three reflection questions, drawn respectively from: the leading propensity, an active (+) pole, and a
   dissolving (⤳) arc — each phrased as an invitation per the rules.
3. A one-line journaling prompt on the movement across the chain.
Close with: "There are no right answers — the meaning is the one you bring."
"""


def name_prompt(scaffolds):
    blocks = "\n".join(f'  "{s["word"]}" → {s["chain"]}' for s in scaffolds)
    merged = {}
    for s in scaffolds:
        merged.update(s.get("glossary") or term_glossary(s["word"]))
    glossary = ("\nGlossary (Sanskrit term = English grounding): "
                + "; ".join(f"{k} = {v}" for k, v in merged.items())) if merged else ""
    return f"""You are the authoring voice of "Varṇa Lens" naming mode.
{HONESTY_RULES}
{DUAL_LANGUAGE}

For each candidate name you are given its deterministic varṇa propensity chain. Produce:
1. Per name: a SYMBOLIC MOOD PALETTE — 3–5 theme tags (e.g. "drive / activation", "release / letting-go",
   "warmth", "edge", "expansion"), framed as "evokes / tends toward", never "means".
2. A short A/B/C CONTRAST: how the candidates differ in mood (e.g. soft/expansive vs sharp/driving).
3. One or two FIT QUESTIONS to help the chooser decide against their own stated intent.
This is a mood board — decoration and conversation-fuel for a subjective choice, not a meaning claim.

Profiles:
{blocks}{glossary}
"""


def call_llm(prompt):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    import ssl, urllib.request
    body = json.dumps({"model": "claude-opus-4-8", "max_tokens": 1000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    ctx = ssl.create_default_context()
    ca = "/root/.ccr/ca-bundle.crt"
    if os.path.exists(ca):
        ctx.load_verify_locations(ca)
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
                                 headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                          "content-type": "application/json"})
    with urllib.request.urlopen(req, context=ctx, timeout=120) as r:
        return json.loads(r.read())["content"][0]["text"]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Varṇa Lens reflection / naming tool (authoring on a deterministic scaffold).")
    sub = ap.add_subparsers(dest="mode", required=True)
    BY = dict(choices=["hybrid", "sound", "spelling"], default="hybrid",
              help="reading mode: hybrid=consonants by sound + vowels by spelling (default); "
                   "sound=pronunciation (g2p); spelling=literal letters")
    ps = sub.add_parser("scaffold"); ps.add_argument("word"); ps.add_argument("--by", **BY)
    pr = sub.add_parser("reflect"); pr.add_argument("word"); pr.add_argument("--by", **BY)
    pr.add_argument("--rich", action="store_true", help="include source acoustic imagery (expanded_properties)")
    pn = sub.add_parser("name"); pn.add_argument("names", nargs="+"); pn.add_argument("--by", **BY)
    a = ap.parse_args(argv)

    if a.mode == "scaffold":
        s = scaffold(a.word, by=a.by); s["acoustic_imagery"] = acoustic_imagery(a.word)
        print(json.dumps(s, ensure_ascii=False, indent=2)); return 0
    if a.mode == "reflect":
        s = scaffold(a.word, by=a.by); prompt = reflect_prompt(s, rich=a.rich); scaf = s
    else:
        scafs = [scaffold(n, by=a.by) for n in a.names]; prompt = name_prompt(scafs); scaf = scafs

    out = call_llm(prompt)
    if out:
        print(out)
    else:
        print("# No ANTHROPIC_API_KEY set — printing the deterministic scaffold + ready-to-author prompt.")
        print("# Wire a key (or paste the prompt into any LLM) to get the authored output.\n")
        print("SCAFFOLD:\n" + json.dumps(scaf, ensure_ascii=False, indent=2))
        print("\n----- AUTHORING PROMPT -----\n")
        print(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
