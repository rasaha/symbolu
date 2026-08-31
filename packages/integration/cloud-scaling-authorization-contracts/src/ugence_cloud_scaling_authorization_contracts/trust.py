"""The single unverified trust state Phase 5A can represent.

Phase 5A holds two signed-looking artifacts — a producer attestation and a policy/target
binding — and establishes the trustworthiness of **neither**. The enum below therefore has
exactly one member. There is no ``TRUST_VERIFIED``, no ``AUTHENTIC``, no ``TRUSTED`` and no
``VALID`` to reach, so no caller, subclass, forged mapping or doctored instance dictionary
can put a Phase 5A artifact into a verified state: the state does not exist to be set.

That is the whole design. A boolean ``verified: bool = False`` would be weaker — a fixed
False still *represents* the concept of verification and invites a later commit to flip
it. An absent state cannot be flipped.

The state is exposed as a read-only ``property`` on each artifact rather than as a
dataclass field, which closes the usual frozen-dataclass bypass: ``object.__setattr__``
raises against a data descriptor, and a doctored ``__dict__`` loses to it as well.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

__all__ = ["EvidenceTrustState", "PHASE_5A_TRUST_STATE"]


class EvidenceTrustState(str, Enum):
    """The closed trust vocabulary available to Phase 5A. Exactly one member.

    ``PRESENT_BUT_NOT_TRUST_VERIFIED`` means: the artifact is structurally well-formed and
    its content binds to the subject Phase 5A reconciled — and nothing more. It does not
    mean the signature verifies, the key is entitled, the issuer is authoritative, the
    policy is in force, or the artifact is fresh. Every one of those is Phase 5B's, and
    Phase 5B is not implemented here.
    """

    PRESENT_BUT_NOT_TRUST_VERIFIED = "PRESENT_BUT_NOT_TRUST_VERIFIED"


#: The only state a Phase 5A artifact ever reports.
PHASE_5A_TRUST_STATE: Final[EvidenceTrustState] = (
    EvidenceTrustState.PRESENT_BUT_NOT_TRUST_VERIFIED
)
