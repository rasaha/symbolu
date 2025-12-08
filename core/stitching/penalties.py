"""
Stitching Penalties - Redundancy and Domain Jump
================================================

PATENT NOTICE: Symbol-U formula to be added later.
"""


class PenaltyCalculator:
    """Calculates penalties for candidate scoring."""
    
    def __init__(self):
        pass
    
    def redundancy_penalty(self, candidates: list) -> list:
        """Calculate redundancy penalties between candidates."""
        raise NotImplementedError("Symbol-U formula to be added later.")
    
    def domain_jump_penalty(self, candidate: object, context: dict) -> float:
        """Calculate domain jump penalty."""
        raise NotImplementedError("Symbol-U formula to be added later.")
