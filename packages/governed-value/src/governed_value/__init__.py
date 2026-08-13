"""Ugence Governed Value — experimental reported-value calculation kernel.

An independently packaged, stdlib-only leaf that computes a **reported
(post-deployment) governed-value** figure from **caller-reported, unverified**
inputs. It is the downstream financial-calculation stage only — one of three
engines in the larger Ugence Value Intelligence capability (Agent Value
Readiness, Value Forecasting, Governed Value Verification); the readiness and
forecast engines, evidence/attribution/authority binding, FX and portfolio
comparison are separate, later, reviewed phases and are **not** in this package.

    total benefit   = reported benefit + reported avoided loss
    ReportedNGV     = total benefit − actual losses − cost to serve
    RiskAdjustedNGV = ReportedNGV − residual expected loss   (Σ probability × magnitude)
    ReportedROI     = ReportedNGV / Total Investment

Expected loss is additive absolute money and may exceed total benefit; reported
benefit is never re-discounted; Total Investment is distinct from cost-to-serve.
Every result is classified on four orthogonal axes and this kernel never rises
above ``POST_DEPLOYMENT_VALUE / REPORTED / UNVERIFIED``: naming an input
"realized" does not make it observed, attributed or verified.

See :mod:`governed_value.api` for the public surface.
"""

from __future__ import annotations

from .version import __version__

__all__ = ["__version__"]
