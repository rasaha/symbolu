"""Labeled draft generator for the internal policy-controller prototype.

The draft->policy->final loop needs DRAFTS WITH KNOWN FLAWS so we can score each
critic's ability to (a) diagnose the flaw and (b) drive a revision that fixes it.

Each flaw is a SEMANTIC/PRAGMATIC property (not a phonological one) — which is the
whole point: a good critic must read meaning. Flaws:

  speculative — hedging / unfounded guessing
  escalated   — emotional escalation / catastrophizing
  verbose     — padded with filler
  vague       — non-specific
  none        — clean (control)

A clean base answer is deterministically corrupted into each flaw. Ground-truth
flaw labels let us measure critic DIAGNOSTIC ACCURACY without any LLM.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

FLAWS = ["speculative", "escalated", "verbose", "vague", "none"]

# Lexicons used both to INJECT flaws and (by the evaluator) to SCORE residual flaw.
SPECULATIVE = ["maybe", "perhaps", "possibly", "might", "could", "conceivably",
               "presumably", "probably", "i guess", "it seems", "arguably"]
ESCALATED = ["disaster", "catastrophe", "panic", "terrible", "doomed", "furious",
             "unacceptable", "outrageous", "nightmare", "horrible", "crisis"]
FILLER = ["as a matter of fact", "it is worth noting that", "at the end of the day",
          "needless to say", "in order to", "for all intents and purposes",
          "when you really think about it"]
VAGUE = ["stuff", "things", "some", "various", "certain", "somehow", "kind of"]

BASE_ANSWERS = [
    "The deployment failed because of a malformed config value on line 12.",
    "A company that runs out of cash cannot pay suppliers and usually halts operations.",
    "Tell the team the target was missed, then give the two metrics that drove it.",
    "A battery stores energy chemically and releases it as current through a circuit.",
    "The test shows elevated markers; schedule a follow-up with the specialist next week.",
    "The journey home took three years and cost the traveler most of his crew.",
    "Restart the service, confirm the port is open, then re-run the migration.",
    "Revenue fell nine percent because the largest account churned in March.",
    "Back up the database before the upgrade and verify the checksum afterward.",
    "The bridge closed for repairs, so traffic is rerouted along the river road.",
    "Submit the form before Friday or the application will not be processed.",
    "The recipe needs two cups of flour, one egg, and a pinch of salt.",
    "Water boils at one hundred degrees Celsius at sea-level pressure.",
    "The meeting moved to Tuesday at noon in the third-floor conference room.",
    "Reduce the dose to ten milligrams and monitor blood pressure for a week.",
]


def _inject(base: str, flaw: str) -> str:
    if flaw == "none":
        return base
    if flaw == "speculative":
        return f"It might be that, {SPECULATIVE[1]}, {base.lower()} but I could be wrong."
    if flaw == "escalated":
        return f"This is an absolute {ESCALATED[0]} — {base} This is a total {ESCALATED[8]}."
    if flaw == "verbose":
        return f"{FILLER[1].capitalize()}, {base} {FILLER[3].capitalize()}, {FILLER[6]}."
    if flaw == "vague":
        return f"There are {VAGUE[3]} {VAGUE[1]} going on and {base.lower()} or {VAGUE[5]}."
    raise ValueError(flaw)


def make_drafts(seed: int = 0) -> List[Tuple[str, str, str]]:
    """Return (base, draft, flaw) triples covering every base × every flaw."""
    out = []
    for base in BASE_ANSWERS:
        for flaw in FLAWS:
            out.append((base, _inject(base, flaw), flaw))
    return out


def flaw_lexicons() -> Dict[str, List[str]]:
    return {"speculative": SPECULATIVE, "escalated": ESCALATED,
            "verbose": FILLER, "vague": VAGUE}
