"""Runtime data types: Request, Candidate, Signal, GateConfig."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

from .states import Evidence
from .version import POLICY_VERSION


@dataclass
class Signal:
    """One observed operational fact about a candidate, with its evidence.
    value == None means UNKNOWN (never silently treated as a pass)."""
    value: Any
    evidence: Evidence
    reason_hint: Optional[str] = None   # e.g. 'DNS_FAILURE' to disambiguate a False reachable


@dataclass
class Request:
    """The task's execution requirements (governance + technical + operational)."""
    request_id: str
    context_tokens: int = 1000
    features_required: Set[str] = field(default_factory=set)   # {'structured_output','tool_use'}
    approved_providers: Optional[Set[str]] = None              # None => no enterprise allowlist
    region_allowed: Optional[Set[str]] = None                  # None => any region
    residency_required: Optional[str] = None                   # e.g. 'eu' / 'us'
    latency_limit_ms: Optional[float] = None
    cost_cap_usd: Optional[float] = None
    est_output_tokens: int = 200


@dataclass
class Candidate:
    """A provider/model with declared metadata and observed signals."""
    provider: str            # serving provider (e.g. 'anthropic', 'google', 'alibaba_modelstudio')
    model_id: str            # exact provider model ID
    family: str              # 'claude' | 'gemma' | 'gemini' | 'qwen' | ...
    developer: str = ""      # model developer (may differ from serving provider)
    region: str = "global"
    context_limit: int = 8000
    structured_output: bool = False
    tool_use: bool = False
    price_in_per_mtok: float = 0.0
    price_out_per_mtok: float = 0.0
    signals: Dict[str, Signal] = field(default_factory=dict)


@dataclass
class GateConfig:
    allow_conditional: bool = True
    require_billing: bool = False           # True => unknown billing is INELIGIBLE, not INDETERMINATE
    reliability_floor: float = 0.90
    default_latency_limit_ms: float = 60000.0
    #: Hard, non-compensatory minimum capability prior, in [0, 1]. ``None`` (the
    #: default) leaves the ``quality_within_floor`` condition unevaluated entirely, so
    #: a configuration that does not set it produces byte-identical decisions to one
    #: from before the floor existed.
    #:
    #: When set, a candidate whose ``quality`` signal is below the floor — or missing,
    #: stale, or not a real number in [0, 1] — is INELIGIBLE, and no ranking score can
    #: restore it, because ranking only ever sees the eligible set. The floor is a
    #: *narrowing* control: it can disqualify an otherwise-eligible candidate and can
    #: never qualify one that any other condition disqualified.
    quality_floor: Optional[float] = None
    # CRITICAL-OP conditions whose UNKNOWN is INDETERMINATE rather than fail-closed:
    indeterminate_on_unknown: Set[str] = field(
        default_factory=lambda: {"billing_active", "credential_expiry_valid"})
    #: Stamped onto every decision this configuration produces. It must be the version
    #: this code actually implements: writing an older version from newer code is the one
    #: thing a policy version exists to make impossible. Reading an older version is a
    #: separate, supported capability — see ``EligibilityDecision.from_dict``.
    policy_version: str = POLICY_VERSION

    def __post_init__(self) -> None:
        if self.policy_version != POLICY_VERSION:
            raise ValueError(
                f"this implementation stamps {POLICY_VERSION!r} and may not write "
                f"{self.policy_version!r}. Stored records of an earlier version stay "
                f"readable through EligibilityDecision.from_dict; they are not "
                f"reproducible by this code, which is why it may not claim to be it.")
        floor = self.quality_floor
        if floor is None:
            return
        # bool is an int subclass; True would otherwise pass as the float 1.0 and
        # configure a floor nobody wrote.
        if isinstance(floor, bool) or not isinstance(floor, (int, float)):
            raise TypeError("quality_floor must be a real number in [0, 1] or None")
        if floor != floor or not (0.0 <= floor <= 1.0):   # NaN fails both comparisons
            raise ValueError(f"quality_floor must be within [0, 1]; got {floor!r}")
