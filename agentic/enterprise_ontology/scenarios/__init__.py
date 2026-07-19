"""Multi-vertical enterprise scenarios."""

from __future__ import annotations

from typing import List

from agentic.enterprise_ontology.projection import Scenario
from agentic.enterprise_ontology.scenarios import (
    campaign, discount, hiring, procurement,
)


def all_scenarios() -> List[Scenario]:
    return [discount.build(), campaign.build(), procurement.build(), hiring.build()]


__all__ = ["all_scenarios", "discount", "campaign", "procurement", "hiring"]
