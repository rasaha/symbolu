"""Ugence Governed Value — governed-value accounting kernel.

An independently packaged, stdlib-only leaf that turns an agent's realized
value, wrong-action risk, and cost of ownership into **net governed value per
authorized action (NGVA)** — the single figure that makes agents across domains
and geographies commensurable, measured at the control-plane chokepoint where
authorization already happens.

    ROI = (realized value - TCO) / TCO
    realized value = labor displaced + throughput/revenue gained + loss avoided
    net governed value = value x (1 - p_error x severity) - cost to serve
    NGVA = net governed value / authorized actions

Domain, geography and intended outcome act as *modifiers* on the spine's terms,
not as separate frameworks. The scorer fails closed: without a defensible basis
(baseline, priced error term, holdout where required, actions to normalize over)
it reports ``NOT_SCORABLE`` and suppresses the headline rather than emit a
flattering number.

See :mod:`governed_value.api` for the public surface.
"""

from __future__ import annotations

from .version import __version__

__all__ = ["__version__"]
