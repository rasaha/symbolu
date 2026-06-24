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
import argparse, json, os
import varna_lens as V

HONESTY_RULES = """LANGUAGE RULES (hard — this is what keeps it honest):
- NEVER use: "means", "represents", "reveals", "signifies", "your word is", "this shows you are",
  "you will", "decodes", "the hidden meaning".
- ALWAYS frame as invitation / the reader's own projection: "invites reflection on", "you might sit
  with", "notice whether", "where in your life…", "if this were true for you today…", "evokes / tends
  toward" (for names).
- Keep the vivid Sanskrit images and the worldly→dissolution (⤳) motion; strip only the truth claim.
- A reflection ends in a question to the user, never a verdict."""


def scaffold(word):
    d, src, _warn = V.analyze(word, model="op")          # model="op" = the vowel-attachment rule
    whole = d.get("whole_word_essence") or {}
    return {"word": word, "source": src, "chain": d.get("essence_short"),
            "chain_detail": d.get("essence"), "whole_word_essence": whole.get("essence")}


def reflect_prompt(s):
    note = f"\nWhole-word note: {s['whole_word_essence']}" if s["whole_word_essence"] else ""
    return f"""You are the authoring voice of "Varṇa Lens", a contemplative reflection tool.
{HONESTY_RULES}

THE MIRROR FOR "{s['word']}"  (read by sound: {s['source']})
A consistent symbolic reflection — NOT a claim about this word.
Its sounds carry this fixed propensity chain (each − worldly pole shown easing ⤳ toward its spiritual
counter; + = an active/anchored pole):
  {s['chain']}{note}

Write the reflection:
1. One opening line naming the chain's images (as images, not claims).
2. Three reflection questions, drawn respectively from: the leading propensity, an active (+) pole, and a
   dissolving (⤳) arc — each phrased as an invitation per the rules.
3. A one-line journaling prompt on the movement across the chain.
Close with: "There are no right answers — the meaning is the one you bring."
"""


def name_prompt(scaffolds):
    blocks = "\n".join(f'  "{s["word"]}" → {s["chain"]}' for s in scaffolds)
    return f"""You are the authoring voice of "Varṇa Lens" naming mode.
{HONESTY_RULES}

For each candidate name you are given its deterministic varṇa propensity chain. Produce:
1. Per name: a SYMBOLIC MOOD PALETTE — 3–5 theme tags (e.g. "drive / activation", "release / letting-go",
   "warmth", "edge", "expansion"), framed as "evokes / tends toward", never "means".
2. A short A/B/C CONTRAST: how the candidates differ in mood (e.g. soft/expansive vs sharp/driving).
3. One or two FIT QUESTIONS to help the chooser decide against their own stated intent.
This is a mood board — decoration and conversation-fuel for a subjective choice, not a meaning claim.

Profiles:
{blocks}
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
    sub.add_parser("scaffold").add_argument("word")
    sub.add_parser("reflect").add_argument("word")
    pn = sub.add_parser("name"); pn.add_argument("names", nargs="+")
    a = ap.parse_args(argv)

    if a.mode == "scaffold":
        print(json.dumps(scaffold(a.word), ensure_ascii=False, indent=2)); return 0
    if a.mode == "reflect":
        s = scaffold(a.word); prompt = reflect_prompt(s); scaf = s
    else:
        scafs = [scaffold(n) for n in a.names]; prompt = name_prompt(scafs); scaf = scafs

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
