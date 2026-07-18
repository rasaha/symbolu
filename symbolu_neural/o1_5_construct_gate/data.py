"""Frozen offline corpus for the O1.5 construct-validity gate.

Hand-authored (this is a construct/dynamic-range diagnostic, NOT the O2A scientific
benchmark — O2A mandates external datasets per the protocol review). Kept small and
deterministic. No labels feed back into the reading; they are only for class-separation
metrics.
"""
from __future__ import annotations

# ---- 12-category corpus for DYNAMIC RANGE (audit 1) -----------------------------
CORPUS = {
    "joy": [
        "We are overjoyed, she said yes and we are getting married.",
        "I am thrilled, the baby arrived healthy and happy.",
        "What a wonderful, bright, delightful morning this is.",
        "I am so happy and grateful for this beautiful celebration.",
        "Pure joy filled the room as everyone laughed and danced.",
    ],
    "grief": [
        "My father passed away last night and I am shattered.",
        "I lost everything in the fire and I feel broken.",
        "Her death has crushed me and I cannot stop crying.",
        "We are mourning a terrible, devastating, sorrowful loss.",
        "The grief is unbearable and the emptiness will not leave.",
    ],
    "calm": [
        "Take your time, there is no rush at all today.",
        "Everything is settled and peaceful, simply rest now.",
        "We can proceed slowly and gently, nothing is urgent.",
        "Breathe quietly, the situation is stable and under control.",
        "It is a still, quiet, restful and tranquil afternoon.",
    ],
    "urgent": [
        "Call emergency services now, he is not breathing!",
        "Move fast, the building is on fire, get out immediately!",
        "We must act right now or we will lose everything!",
        "Hurry, there is no time, respond this instant!",
        "Critical alert, the system is failing, fix it now!",
    ],
    "technical": [
        "The function returns an integer pointer after allocation.",
        "A transformer uses self attention over token embeddings.",
        "The compiler optimizes the loop and frees the buffer.",
        "Configure the server with a thread pool and a queue.",
        "The gradient is computed by backpropagation through layers.",
    ],
    "legal": [
        "The party hereby agrees pursuant to section four of the contract.",
        "Liability shall be limited accordingly under the agreement.",
        "The plaintiff alleges breach of the aforementioned clause.",
        "This indemnity is governed by the laws of the jurisdiction.",
        "The defendant waives all claims pursuant to the statute.",
    ],
    "speculative": [
        "Prices might possibly rebound next quarter, but who can say.",
        "It could perhaps improve, though that is only a guess.",
        "Maybe the market will shift, I am really not certain.",
        "Possibly it rains tomorrow, it is hard to predict.",
        "Perhaps the trend continues, but this is mere speculation.",
    ],
    "grounded": [
        "The build passed all four hundred and twelve tests today.",
        "The measured temperature was exactly twenty one degrees.",
        "The report confirms the deadline is March the third.",
        "Records show the payment cleared on Tuesday at noon.",
        "The experiment reproduced the result in every single trial.",
    ],
    "confused": [
        "I am not sure, it is all a blur and hard to say.",
        "Wait, what, I do not understand any of this at all.",
        "It makes no sense to me, I am completely lost here.",
        "Everything is muddled and unclear and I cannot follow.",
        "I have no idea what is happening, it is all confusing.",
    ],
    "memory": [
        "As I recall from last year's report, the figures were higher.",
        "I remember you said the meeting was moved to Friday.",
        "Back then, we used to gather here every single summer.",
        "From what I recollect, the old policy was quite different.",
        "I still remember the day we first opened the shop.",
    ],
    "nonsense": [
        "xtrrk blomp vint quzzle frananic gort plimble dwesh.",
        "wug blicket dax fendle morp zud quib snarl vex.",
        "florp glim bnik trell wozzle gak prindle shemp.",
        "vlonk thrip mabble zorn quff blent grix nood.",
        "skree plonk vurd glimble nax tronk weeb flud.",
    ],
    "neutral": [
        "The store opens at nine and closes at six daily.",
        "There are seven days in a week and twelve months.",
        "The book is on the table next to the lamp.",
        "Water boils at one hundred degrees at sea level.",
        "The train departs from platform two every hour.",
    ],
}

# ---- 6 contrast pairs for INTERNAL CONSISTENCY (audit 2) -------------------------
# expect_feature/direction: the reading feature expected to differ, where defined.
CONTRASTS = {
    "joy_vs_grief":        {"pos": "joy",        "neg": "grief",       "feat": "valence_ratio", "dir": "pos>neg"},
    "calm_vs_urgent":      {"pos": "calm",       "neg": "urgent",      "feat": None,            "dir": None},
    "grounded_vs_specul":  {"pos": "grounded",   "neg": "speculative", "feat": "coherence",     "dir": "pos>neg"},
    "clear_vs_confused":   {"pos": "neutral",    "neg": "confused",    "feat": "coherence",     "dir": "pos>neg"},
    "memory_vs_nonmemory": {"pos": "memory",     "neg": "neutral",     "feat": None,            "dir": None},
    "certain_vs_uncertain":{"pos": "grounded",   "neg": "speculative", "feat": "coherence",     "dir": "pos>neg"},
}

# ---- PARAPHRASE sets (audit 3): same meaning, varied wording/sound/length --------
PARAPHRASES = [
    # grief (wording)
    ["I am devastated by the loss.", "This loss has broken me.",
     "I cannot stop grieving.", "Her death has crushed me."],
    # joy (sound-varied synonyms)
    ["I am happy.", "I am joyful.", "I am elated.", "I am delighted."],
    # urgent (length-varied, same meaning)
    ["Help now.", "Please help me right now.",
     "I urgently need help from someone immediately, please.",
     "Right now, without any delay at all, I need urgent help."],
    # grounded (wording)
    ["The result is verified.", "The finding is confirmed.",
     "This has been validated.", "We proved it conclusively."],
]

# ---- MINIMAL PAIRS (audit 4): one semantic feature changes, wording similar ------
# (textA, textB, feature, expected: 'A>B' means feature(A) > feature(B))
MINIMAL_PAIRS = [
    ("This is verified.",        "This is only a guess.",      "coherence",     "A>B"),
    ("I remember you said that.","I do not remember that.",    "valence_ratio", "either"),
    ("He was calm and steady.",  "He was panicking wildly.",   "valence_ratio", "A>B"),
    ("The plan succeeded.",      "The plan failed.",           "valence_ratio", "A>B"),
    ("It is certainly true.",    "It might possibly be true.", "coherence",     "A>B"),
    ("We are safe now.",         "We are in danger now.",      "valence_ratio", "A>B"),
]

# tiny builtin sentiment lexicon (VADER not installed; SBERT deferred to O2A)
POS_WORDS = set("joy joyful happy overjoyed thrilled wonderful bright delightful grateful "
                "beautiful celebration laughed danced calm peaceful rest stable safe success "
                "succeeded verified confirmed validated proved healthy".split())
NEG_WORDS = set("grief shattered lost broken death crushed crying mourning devastating sorrowful "
                "unbearable emptiness fire fail failed danger panicking confusing muddled unclear "
                "lost terrible breach liability defendant alleges".split())
