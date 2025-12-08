"""
Audit Trail
============

Compliance audit logging.
EMPTY SCAFFOLD - No implementation yet.
"""

from typing import Dict, Any, List


class AuditTrail:
    """Audit Trail - SCAFFOLD ONLY."""
    
    def __init__(self):
        self.entries: List[Dict[str, Any]] = []
    
    def record(self, action: str, data: Dict[str, Any]) -> None:
        """Record audit entry."""
        raise NotImplementedError("Audit trail implementation pending.")
