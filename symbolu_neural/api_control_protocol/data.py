"""Prompt set for the API control-protocol pilot.

Prompts are chosen so that *tone/affect control actually matters* — situations
where the same content could be delivered calmly, energetically, or heavily. Each
has a paraphrase (for the stability-under-paraphrase metric).
"""
from __future__ import annotations

from typing import List, Tuple

# (prompt, paraphrase)
PROMPTS: List[Tuple[str, str]] = [
    ("My deployment failed again and I'm losing my patience. What do I do?",
     "The deploy broke one more time and I'm getting really frustrated. Help."),
    ("Explain what happens to a company when it runs out of cash.",
     "Describe what occurs to a business once its money is gone."),
    ("I have to tell my team we missed the quarterly target. How should I frame it?",
     "How do I break it to my team that we fell short of the quarter's goal?"),
    ("Give me a quick rundown of how a battery stores energy.",
     "Briefly walk me through the way a battery holds energy."),
    ("The test results came back and they are not good. Walk me through next steps.",
     "The results are in and they're bad. Talk me through what comes next."),
    ("Summarize the plot of a story about a long, difficult journey home.",
     "Recap the storyline of a tale about a hard, lengthy trip back home."),
]


def prompts() -> List[Tuple[str, str]]:
    return list(PROMPTS)
