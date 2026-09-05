"""The ratified version ladder, and how a milestone-conditional ban reads it.

D-19 makes the capability-token bans milestone-conditional: each token carries
the subphase that may **first** ship it. Two test modules apply that rule to two
different surfaces — the tree-wide class/function scan and the exported-symbol
scan — so the ladder and the predicate live here rather than in either of them.

**A rung is not a subphase.** D-01, amended 2026-08-20, ratifies **five**
separately auditable subphases and D-33 leaves that unamended. The ladder below
carries six rungs because one of them, ``BR-2C-0``, is a **version rung**: it
names the version at which BR-2C's *contract surface* landed while no BR-2C
*capability* did. It mints no closure audit and no separate ratification, and
``0.3.0`` remains BR-2C — the audited verifier, which no rung below it ships.

Nothing in this module relaxes anything. It decides *when* a ban lifts; the ban
sets themselves, and the assertions that they are no weaker than BR-2A froze,
stay next to the surfaces they guard. Inserting ``BR-2C-0`` shifts the index of
every rung above it, which unlocks nothing:
:func:`banned_capability_tokens` compares by ladder **index**, so a token whose
unlock phase is ``"BR-2C"`` stays banned at every rung below ``BR-2C``.
"""

from __future__ import annotations

#: The ratified version ladder, in order (ADR §35.1, D-01 as amended, D-33, and
#: the owner's BR-2C candidate ruling). Five of the seven rungs are D-01's five
#: subphases. ``BR-2C-0`` is D-33's contract-only **version rung**, sitting
#: between BR-2B and BR-2C; ``BR-2C-RC`` is the candidate **version rung**,
#: sitting between BR-2C-0 and BR-2C.
SUBPHASE_LADDER = ("BR-2A", "BR-2B", "BR-2C-0", "BR-2C-RC", "BR-2C", "BR-2D", "BR-2E")

#: Version → rung. Read from the live ``api.__version__`` by the callers, so
#: the effective ban set follows the distribution rather than a constant someone
#: could edit to widen it.
#:
#: ``0.2.1`` is D-33's rung. The BR-2C contract slice moved this distribution's
#: curated surface — ``api.__all__`` 93 → 106 — at an unchanged ``0.2.0``, which
#: left two different surfaces wearing one version and D-18's "counts move
#: deliberately at each version bump" untrue of the distribution. ``0.3.0`` was
#: not available: §35.1 defines it as the *audited verifier*, and taking it would
#: unlock twelve BR-2C capability tokens the slice does not ship.
#:
#: ``0.2.2`` is D-34's surface move — the anchor-resolution outcome replacing
#: ``Optional[BenchmarkTrustAnchorRecord]`` at the seam — and ``0.2.3`` is
#: D-35's, narrowing which refusals a verified result may carry. **D-36 rules
#: that all three map to the same rung**, so this map is ratified rather than
#: inferred: the rung names what a version ships, not how many times it shipped,
#: and all three are BR-2C's contract surface with no BR-2C capability, so all
#: three must ban the same twelve tokens. A rung per version would add ladder
#: indices whose ban sets are identical to ``BR-2C-0``'s, and so rule nothing.
#:
#: ``0.3.0rc1`` is the **BR-2C candidate rung**, ``BR-2C-RC``, ratified by the
#: owner as a candidate version only. It sits between ``BR-2C-0`` and ``BR-2C``
#: because it ships what neither neighbour does: BR-2C's capability — the
#: candidate verifier — without BR-2C's closure, which D-32(4) and D-38(i)
#: reserve for ``0.3.0`` after an independent external cryptographic review
#: that has not occurred. The ratified release transition (D-40, as applied to
#: this rung) lifts exactly the twelve capability tokens D-33 records as
#: BR-2C's, and nothing else: every other prohibition, permanent or later,
#: stands. It is a version rung, not a subphase, and it mints no closure audit.
VERSION_SUBPHASE = {
    "0.1.0": "BR-2A",
    "0.2.0": "BR-2B",
    "0.2.1": "BR-2C-0",
    "0.2.2": "BR-2C-0",
    "0.2.3": "BR-2C-0",
    "0.3.0rc1": "BR-2C-RC",
    "0.3.0": "BR-2C",
    "0.4.0": "BR-2D",
    "0.5.0": "BR-2E",
}


def banned_capability_tokens(
    subphase: str, unlock_map: dict, ladder: tuple = SUBPHASE_LADDER
) -> frozenset:
    """The tokens from ``unlock_map`` still banned at ``subphase``.

    A token stays banned unless its unlock phase has been **reached**. An unlock
    of :data:`None` means *permanently banned* and never lifts — D-07's ban on a
    convenience resolver or selection API, D-10's exclusion of supersession, and
    the permanent ``{stub, fake, dummy, noop, null_}`` entries of
    ``EXPORTED_IMPLEMENTATION_UNLOCK`` are prohibitions, not deferrals, and
    folding them into "not yet" would convert a permanent ruling into a
    schedule. Note what that last one is and is not: §17 is *Registry and
    resolution semantics* and bans no placeholder; the placeholder prohibition
    is a **name** ban carried by that unlock map alone, in the same self-attested
    one-file two-literal pattern D-37 and D-38 rule.

    Comparison is by ladder **index**, never by string ordering, so a renamed or
    misspelled subphase raises rather than sorting itself quietly into scope.

    ``ladder`` defaults to the real :data:`SUBPHASE_LADDER` and is a parameter
    only so D-36's check can measure a *hypothetical* ladder with **this**
    predicate rather than a copy of it. An independent audit showed the copy it
    replaced could drift — ``>`` to ``>=`` — with the suite still green, because
    both sides of that comparison came from the same copy.
    """

    reached = ladder.index(subphase)
    return frozenset(
        token
        for token, unlock in unlock_map.items()
        if unlock is None or ladder.index(unlock) > reached
    )
