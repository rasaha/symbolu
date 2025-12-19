"""
P31 Output Envelope Phase Schema
==================================

Schema definitions for the P31 Output Envelope phase within the
Delivery Adaptation Band (P27-P31).

Phase Authority: LOW
Band: Delivery Adaptation (P27-P31)

This phase wraps final output in appropriate envelope format:
- Output structure formatting (plain/markdown/JSON)
- Metadata attachment
- Delivery channel adaptation
- Final safety gating

Inputs:
    - P30 verified text
    - Pipeline metadata
    - Delivery channel specification

Outputs:
    - Enveloped output text
    - Attached metadata
    - Format specification

Version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

# =============================================================================
# VERSION
# =============================================================================

VERSION = "1.0.0"


# =============================================================================
# ENUMS
# =============================================================================


class P31Authority(Enum):
    """Authority level for P31 phase decisions."""
    HIGH = "high"       # Envelope decision is binding
    MEDIUM = "medium"   # Envelope can be adjusted
    LOW = "low"         # Envelope is advisory (default)


class EnvelopeFormat(Enum):
    """Output envelope format."""
    PLAIN = "plain"         # Plain text
    MARKDOWN = "markdown"   # Markdown formatted
    JSON = "json"           # JSON structured
    HTML = "html"           # HTML formatted
    SSML = "ssml"           # Speech synthesis markup


class DeliveryChannel(Enum):
    """Delivery channel type."""
    CHAT = "chat"           # Chat interface
    API = "api"             # API response
    VOICE = "voice"         # Voice/TTS output
    EMAIL = "email"         # Email delivery
    REPORT = "report"       # Report generation


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass(frozen=True)
class P31Metadata:
    """
    Metadata attached to output envelope.
    """
    # Pipeline trace
    pipeline_version: str = "3.1"
    phases_executed: List[str] = field(default_factory=list)

    # Persona/DHA context
    persona_id: Optional[str] = None
    delivery_profile: Optional[str] = None

    # Verification status
    verification_passed: bool = True

    # Timing
    render_timestamp: Optional[float] = None

    # Custom metadata
    custom: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pipeline_version": self.pipeline_version,
            "phases_executed": self.phases_executed,
            "persona_id": self.persona_id,
            "delivery_profile": self.delivery_profile,
            "verification_passed": self.verification_passed,
            "render_timestamp": self.render_timestamp,
            "custom": self.custom,
        }


@dataclass(frozen=True)
class P31Output:
    """
    Output from P31 Output Envelope phase.
    """
    # Enveloped text
    envelope_text: str

    # Format specification
    envelope_format: EnvelopeFormat = EnvelopeFormat.PLAIN

    # Delivery channel
    delivery_channel: DeliveryChannel = DeliveryChannel.CHAT

    # Authority level
    authority: P31Authority = P31Authority.LOW

    # Attached metadata
    metadata: Optional[P31Metadata] = None

    # Processing trace
    processing_trace: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "phase": "P31",
            "version": VERSION,
            "envelope_text": self.envelope_text,
            "envelope_format": self.envelope_format.value,
            "delivery_channel": self.delivery_channel.value,
            "authority": self.authority.value,
            "metadata": self.metadata.to_dict() if self.metadata else None,
            "processing_trace": self.processing_trace,
        }

    def to_api_response(self) -> Dict[str, Any]:
        """Convert to API response format."""
        response = {
            "text": self.envelope_text,
            "format": self.envelope_format.value,
        }
        if self.metadata:
            response["meta"] = self.metadata.to_dict()
        return response


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "VERSION",
    "P31Authority",
    "EnvelopeFormat",
    "DeliveryChannel",
    "P31Metadata",
    "P31Output",
]
