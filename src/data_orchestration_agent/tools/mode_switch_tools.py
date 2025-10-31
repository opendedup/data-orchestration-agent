"""Mode switching tools for manual mode transitions."""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Global session state reference (will be injected)
_session_state: Dict[str, Any] = {}


def set_session_state(state: Dict[str, Any]) -> None:
    """Set the session state reference.
    
    Args:
        state: Session state dictionary
    """
    global _session_state
    _session_state = state


async def switch_to_ask_mode() -> str:
    """Switch to Ask/Discover mode for exploring datasets.
    
    Returns:
        Confirmation message
    """
    _session_state["current_mode"] = "ask"
    logger.info("Switched to Ask/Discover mode")
    return "Switched to Ask/Discover Mode. You can now search for datasets and explore their schemas."


async def switch_to_plan_mode() -> str:
    """Switch to Plan mode to create PRPs.
    
    Returns:
        Confirmation message
    """
    _session_state["current_mode"] = "plan"
    logger.info("Switched to Plan mode")
    return "Switched to Plan Mode. Let's create a Product Requirement Prompt (PRP)."


async def switch_to_action_mode() -> str:
    """Switch to Action mode to execute queries or build data products.
    
    Returns:
        Confirmation message
    """
    _session_state["current_mode"] = "action"
    logger.info("Switched to Action mode")
    return "Switched to Action Mode. You can now execute queries or build data products from PRPs."

