"""Prompt set for the v2 faithful test.

Unlike v1, drafts are NOT synthetic keyword-injected flaws — a real LLM writes the
draft, and the judge evaluates it. Prompts are chosen so that draft quality
plausibly varies on the rubric axes (escalation, speculation, caution, clarity,
directness) WITHOUT being keyword-detectable. Each has a paraphrase for stability.
"""
from __future__ import annotations

from typing import List, Tuple

# (prompt, paraphrase, category)
PROMPTS: List[Tuple[str, str, str]] = [
    ("My production database just got deleted and my boss is furious. What do I do right now?",
     "Someone dropped our prod database and leadership is livid — what are my immediate steps?",
     "emotional"),
    ("Is it going to be a good year for the housing market?",
     "Will the housing market do well over the coming year?",
     "speculative"),
    ("My doctor prescribed a drug but I read scary things online. Should I stop taking it?",
     "I'm nervous about a medication after reading the internet — should I quit it?",
     "high_stakes"),
    ("Explain how a transformer neural network works.",
     "Walk me through the workings of a transformer neural network.",
     "factual"),
    ("My startup is running low on cash. Are we doomed?",
     "We're nearly out of runway at my startup — is it over for us?",
     "emotional"),
    ("What's the best programming language?",
     "Which programming language is the best one?",
     "ambiguous"),
    ("Will AI take my job as an accountant in the next two years?",
     "Over the next two years, is AI going to replace my accounting job?",
     "speculative"),
    ("I think I might be having a heart attack but I'm not sure. What should I do?",
     "I'm unsure but worried I could be having a heart attack — what now?",
     "high_stakes"),
    ("Summarize the causes of the 2008 financial crisis.",
     "Give me the main causes behind the 2008 financial crisis.",
     "factual"),
    ("Should I quit my stable job to pursue my dream, yes or no?",
     "Is it a yes or no — leave my secure job to chase my dream?",
     "ambiguous"),
    ("My code works on my machine but fails in CI and I'm losing my mind.",
     "It runs locally but breaks in CI and it's driving me crazy.",
     "emotional"),
    ("Is this contract clause legally enforceable?",
     "Would this contract clause hold up legally?",
     "high_stakes"),
]


def prompts() -> List[Tuple[str, str, str]]:
    return list(PROMPTS)
