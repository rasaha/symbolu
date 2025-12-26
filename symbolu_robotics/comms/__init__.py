"""
Symbolu Robotics Communications
================================

Multi-agent coordination and human interface.

Uses O10_UNIFYING for swarm behavior.

Enhanced:
- LLM-powered human interface for complex command understanding
- Multi-turn dialogue with context tracking
"""

from symbolu_robotics.comms.swarm_protocol import SwarmProtocol, SwarmMessage
from symbolu_robotics.comms.human_interface import (
    HumanInterface,
    CommandType,
    ParsedCommand,
    ConversationManager,
    IntentConfidence,
    LLMConfig,
    LLMProvider,
    MockLLMProvider,
    OpenAILLMProvider,
)
from symbolu_robotics.comms.ros_bridge import ROSBridge

__all__ = [
    # Swarm
    "SwarmProtocol",
    "SwarmMessage",
    # Human Interface
    "HumanInterface",
    "CommandType",
    "ParsedCommand",
    "ConversationManager",
    "IntentConfidence",
    # LLM Integration
    "LLMConfig",
    "LLMProvider",
    "MockLLMProvider",
    "OpenAILLMProvider",
    # ROS
    "ROSBridge",
]
