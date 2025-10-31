"""Mode detection logic for the orchestration agent."""

from enum import Enum
from typing import Any, Dict


class AgentMode(Enum):
    """Operational modes for the orchestration agent."""
    
    ASK = "ask"
    PLANNING = "planning"
    ACTION = "action"


def detect_mode(user_message: str, session_state: Dict[str, Any]) -> AgentMode:
    """Detect which mode the user wants based on message and state.
    
    Note: With the new architecture, mode switching is primarily manual via
    switch_to_X_mode tools. This function is kept for analytics/logging.
    
    Args:
        user_message: User's input message
        session_state: Current session state dictionary
        
    Returns:
        Detected agent mode (defaults to ASK if not explicitly set)
    """
    # Check for explicit mode in session state (set by mode switching tools)
    current_mode = session_state.get("current_mode", "ask")
    
    # Map string mode to enum
    mode_map = {
        "ask": AgentMode.ASK,
        "plan": AgentMode.PLANNING,
        "planning": AgentMode.PLANNING,
        "action": AgentMode.ACTION,
    }
    
    return mode_map.get(current_mode.lower(), AgentMode.ASK)

