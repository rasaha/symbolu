"""The ratified subphase ladder, and how a milestone-conditional ban reads it.

D-19 makes the capability-token bans milestone-conditional: each token carries
the subphase that may **first** ship it. Two test modules apply that rule to two
different surfaces — the tree-wide class/function scan and the exported-symbol
scan — so the ladder and the predicate live here rather than in either of them.

Nothing in this module relaxes anything. It decides *when* a ban lifts; the ban
sets themselves, and the assertions that they are no weaker than BR-2A froze,
stay next to the surfaces they guard.
"""

from __future__ import annotations

#: The ratified subphase ladder, in order (ADR §35.1, D-01 as amended).
SUBPHASE_LADDER = ("BR-2A", "BR-2B", "BR-2C", "BR-2D", "BR-2E")

#: Version → subphase. Read from the live ``api.__version__`` by the callers, so
#: the effective ban set follows the distribution rather than a constant someone
#: could edit to widen it.
VERSION_SUBPHASE = {
    "0.1.0": "BR-2A",
    "0.2.0": "BR-2B",
    "0.3.0": "BR-2C",
    "0.4.0": "BR-2D",
    "0.5.0": "BR-2E",
}


def banned_capability_tokens(subphase: str, unlock_map: dict) -> frozenset:
    """The tokens from ``unlock_map`` still banned at ``subphase``.

    A token stays banned unless its unlock phase has been **reached**. An unlock
    of :data:`None` means *permanently banned* and never lifts — D-07's ban on a
    convenience resolver or selection API, D-10's exclusion of supersession, and
    §17's ban on executable placeholders are prohibitions, not deferrals, and
    folding them into "not yet" would convert a permanent ruling into a
    schedule.

    Comparison is by ladder **index**, never by string ordering, so a renamed or
    misspelled subphase raises rather than sorting itself quietly into scope.
    """

    reached = SUBPHASE_LADDER.index(subphase)
    return frozenset(
        token
        for token, unlock in unlock_map.items()
        if unlock is None or SUBPHASE_LADDER.index(unlock) > reached
    )
