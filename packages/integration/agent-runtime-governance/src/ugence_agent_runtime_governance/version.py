"""Distribution version.

0.1.0 is the first production ``GovernanceHook`` adapter for the Agent Runtime
(roadmap GAS-3). It is **Core implemented**, not pilot-validated and not
production-certified: Risk Authority ``production_mode`` still raises
``ProductionContainmentError``, and HOLD, DEFER, ESCALATE and MANUAL_REVIEW still
have no sink.
"""

__version__ = "0.1.0"
