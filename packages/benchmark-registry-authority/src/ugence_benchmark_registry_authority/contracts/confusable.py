"""The confusable-coordinate comparison contract — rejection only, honestly empty.

D-06 as ratified defines the typed
:attr:`~.reasons.BenchmarkRegistryRefusalReason.CONFUSABLE_COORDINATE` refusal
and **the comparison contract**: what is compared, against what, and what the
refusal means. It explicitly **does not** claim a complete Unicode-confusable
implementation, and this module says so in machine-readable form rather than
only in prose.

Normalization is prohibited outright
------------------------------------
This supersedes revision 1's proposed casefold/NFKC collision check.
:data:`BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT` records the posture as
:attr:`~.enums.BenchmarkConfusableNormalizationPosture.EXPLICITLY_PROHIBITED`:
the canonical locator and the stored bytes are **never** casefolded, NFKC-
normalized or otherwise rewritten — only compared and refused.

The reason is the same one BR-1's reject-don't-normalize Unicode posture exists
for. Normalizing would map two *structurally different* locators onto one, so a
digest over one would attest a value nobody wrote, and a registry that rewrote a
publisher's coordinate would be registering something the publisher did not
submit.

The algorithm slot is empty, and that is the honest state
----------------------------------------------------------
A complete confusable-detection algorithm needs a named, versioned, deterministic
rule set — a specific Unicode confusables table at a specific Unicode version,
with a specified skeleton function and specified handling of mixed scripts. None
of that is ratified, so :data:`BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT`'s
``algorithm_identifier`` and ``unicode_version`` are :data:`None`.

**A partial implementation presented as complete would not be honest.** A
half-built confusable check that misses a case is worse than a declared absence,
because a consumer would believe the class of attack was handled. The contract
exists — the refusal is typed, the comparison basis is named, the posture is
fixed — and the algorithm is explicitly outstanding.

What is compared, at this version
---------------------------------
The comparison basis is the **exact nine-element identity tuple** of the BR-1
locator (:attr:`ugence_benchmark_registry.BenchmarkCoordinate.exact_identity`),
compared code-point-for-code-point against the locators the registry already
holds. At this version that detects only *exact* collisions, which
:attr:`~.reasons.BenchmarkRegistryRefusalReason.COORDINATE_SLOT_CONFLICT`
already covers — which is precisely why the confusable *algorithm* is recorded as
outstanding rather than claimed.

Nothing in this module executes a comparison. BR-2A holds no registry and no set
of occupied locators to compare against; the comparison itself belongs to BR-2B's
admission path. This is the contract that path must implement.
"""

from __future__ import annotations

from types import MappingProxyType

from .enums import BenchmarkConfusableNormalizationPosture
from .reasons import BenchmarkRegistryRefusalReason

__all__ = [
    "BENCHMARK_CONFUSABLE_COMPARED_ELEMENTS",
    "BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT",
]

#: The nine scalar elements of the BR-1 exact identity tuple, in order — the
#: whole locator and nothing but the locator. Publisher is deliberately absent:
#: it is not in the locator, and comparing it would make coordinate squatting
#: *easier* by partitioning the namespace per publisher, which D-06 prohibits.
BENCHMARK_CONFUSABLE_COMPARED_ELEMENTS: tuple = (
    "benchmark_id",
    "benchmark_family",
    "benchmark_version",
    "scope.kind",
    "scope.tenant_id",
    "geography.declaration",
    "geography.value",
    "domain.declaration",
    "domain.value",
)

#: The ratified comparison contract, machine-readable so a later milestone
#: implements *this* and a reviewer can check it did.
BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT: MappingProxyType = MappingProxyType(
    {
        "compared_elements": BENCHMARK_CONFUSABLE_COMPARED_ELEMENTS,
        "compared_against": (
            "the exact locators the registry already holds; the submitted "
            "locator is never compared against a normalized form of itself or "
            "of any stored locator"
        ),
        "comparison_basis_at_this_version": (
            "exact Unicode code-point equality over the nine-element identity "
            "tuple"
        ),
        "normalization_posture": (
            BenchmarkConfusableNormalizationPosture.EXPLICITLY_PROHIBITED.value
        ),
        "rewrite_permitted": False,
        "outcome": "rejection only — the submitted locator is refused; neither "
        "it nor any stored locator is ever rewritten, merged or aliased",
        "refusal_reason": (
            BenchmarkRegistryRefusalReason.CONFUSABLE_COORDINATE.value
        ),
        "algorithm_identifier": None,
        "unicode_version": None,
        "completeness_claim": (
            "NONE. No complete Unicode-confusable algorithm is claimed at this "
            "version. The deterministic algorithm and its version are not yet "
            "specified or tested, so the slot is explicitly empty rather than "
            "partially filled — a partial implementation presented as complete "
            "would leave a consumer believing this class of attack is handled."
        ),
        "implemented_by": (
            "no code in BR-2A. BR-2A holds no registry and no set of occupied "
            "locators; the comparison belongs to BR-2B's admission path, which "
            "must implement this contract."
        ),
    }
)
