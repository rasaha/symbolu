"""Sentence-level classical-Vritti cognitive evaluator (provenance: sentence_semantic_rule_v1).

Replaces the previous PHONOLOGICAL derived_bridge for classical_vritti with a
MEANING-oriented evaluation of the DRAFT ANSWER. It inspects what the answer is
*doing* epistemically, not how its phonemes sound.

Representation (practical 3+2 design):
    primary in {pramana, viparyaya, vikalpa}   (mutually exclusive epistemic mode)
    nidra : bool   (low-information / evasive / non-answer / needs clarification)
    smrti : bool   (memory-/prior-context-reference; needs provenance)

Rule-based v1 (an LLM judge could later replace this -> provenance llm_judge_vritti).
Canonical NAMES from symbolu_core.presentation.signals.VrittiDistribution.
"""
from __future__ import annotations

from typing import Dict

PRIMARY_VRITTI = ["pramana", "viparyaya", "vikalpa"]
FLAGS = ["nidra", "smrti"]
PROVENANCE = "sentence_semantic_rule_v1"

# --- meaning-oriented marker lexicons (about the ANSWER's epistemic behaviour) ---
SPECULATION = ["might", "may ", "could ", "possibly", "perhaps", "probably", "likely",
               "i imagine", "hypothetical", "in theory", "speculat", "i guess",
               "i suspect", "my guess", "presumably", "conceivably", "it's possible",
               "if i had to guess", "i would assume", "potentially"]
OVERCERTAINTY = ["definitely", "certainly", "guaranteed", "without a doubt", "100%",
                 "absolutely", "undoubtedly", "for sure", "always", "never ", "no question"]
CONTRADICTION = ["actually, no", "that's wrong", "contradict", "but actually",
                 "i was wrong", "incorrect", "on the contrary", "scratch that"]
GROUNDED = ["because", "according to", "evidence", "specifically", "for example",
            "the data", "step 1", "first,", "research shows", "studies", "by definition",
            "is defined as", "the cause", "due to", "as shown", "the reason is"]
LOWINFO = ["it depends", "i cannot", "i can't", "as an ai", "i'm not sure", "i am not sure",
           "no information", "cannot answer", "unclear", "hard to say",
           "not enough information", "i don't know", "unable to", "it's complicated"]
MEMORY = ["as you mentioned", "earlier you said", "as we discussed", "you told me",
          "previously", "last time", "you said", "your earlier", "recall that",
          "as noted before", "you asked earlier", "from our prior", "remember when"]


def _count(text: str, markers) -> int:
    return sum(text.count(m) for m in markers)


def evaluate_cognitive(text: str) -> Dict:
    """draft answer text -> {primary, nidra, smrti, scores, provenance}."""
    t = (text or "").lower()
    n_words = max(len(t.split()), 1)
    spec = _count(t, SPECULATION)
    cert = _count(t, OVERCERTAINTY)
    contra = _count(t, CONTRADICTION)
    grounded = _count(t, GROUNDED)
    lowinfo = _count(t, LOWINFO)
    mem = _count(t, MEMORY)

    nidra = lowinfo > 0 or n_words < 8                 # evasive / non-answer / too thin
    smrti = mem > 0                                    # relies on remembered context

    if spec > 0 and spec >= grounded and spec > contra:
        primary = "vikalpa"                            # speculation/extrapolation dominates
    elif contra > 0 or (cert > 0 and grounded == 0):
        primary = "viparyaya"                          # contradiction / unsupported overclaim
    else:
        primary = "pramana"                            # grounded / default valid cognition

    return {"primary": primary, "nidra": bool(nidra), "smrti": bool(smrti),
            "scores": {"pramana": grounded, "viparyaya": cert + contra, "vikalpa": spec,
                       "lowinfo": lowinfo, "memory": mem},
            "provenance": PROVENANCE}


# crafted probe answers (one per category) — prove every state is reachable
PROBE_ANSWERS = {
    "pramana": "The deployment failed because the config value on line 12 is malformed; "
               "specifically, fix that value and redeploy.",
    "viparyaya": "This is definitely a heart attack, absolutely, 100% guaranteed, "
                 "and you should never worry about anything else at all.",
    "vikalpa": "It might possibly be a good year; perhaps prices could rise or fall, and "
               "I would assume momentum continues, but this is purely speculative extrapolation.",
    "nidra": "It depends. I'm not sure.",
    "smrti": "As you mentioned earlier, your budget was tight, so recall that we "
             "previously discussed cutting recurring costs first before anything else.",
}


if __name__ == "__main__":
    for label, ans in PROBE_ANSWERS.items():
        e = evaluate_cognitive(ans)
        print(f"{label:10} -> primary={e['primary']:9} nidra={e['nidra']} smrti={e['smrti']}")
