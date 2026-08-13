"""Ugence Governed Value — experimental realized-value calculation kernel.

An independently packaged, stdlib-only leaf that computes a **realized
(post-deployment) governed-value** figure from **caller-reported, unverified**
inputs. It is the downstream financial-calculation stage only — one of three
engines in the larger Ugence Value Intelligence capability (Agent Value
Readiness, Value Forecasting, Governed Value Verification); the readiness and
forecast engines, evidence/attribution/authority binding, FX and portfolio
comparison are separate, later, reviewed phases and are **not** in this package.

    total benefit   = attributable realized benefit + attributed avoided loss
    RealizedNGV     = total benefit − actual losses − cost to serve
    RiskAdjustedNGV = RealizedNGV − residual expected loss   (Σ probability × magnitude)
    RealizedROI     = RealizedNGV / Total Investment

Expected loss is additive absolute money and may exceed total benefit; realized
benefit is never realization-discounted; Total Investment is distinct from
cost-to-serve. Every result is classified on four orthogonal axes and this kernel
never rises above ``POST_DEPLOYMENT_VALUE / REPORTED / UNVERIFIED``: naming an
input "realized" does not make it observed, attributed or verified.

See :mod:`governed_value.api` for the public surface.
"""

from __future__ import annotations

from .version import __version__

__all__ = ["__version__"]
