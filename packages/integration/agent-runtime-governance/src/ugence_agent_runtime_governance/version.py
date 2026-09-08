"""Distribution version.

0.1.0 is the first production ``GovernanceHook`` adapter for the Agent Runtime
(roadmap GAS-3). It is **Core implemented**, not pilot-validated and not
production-certified: Risk Authority ``production_mode`` still raises
``ProductionContainmentError``, and a HOLD still has no sink — an ESCALATE gained one
at GAS-7, while a HOLD carrying no required approval is released upstream and never by
an approval (HR-5).
"""

__version__ = "0.1.0"
