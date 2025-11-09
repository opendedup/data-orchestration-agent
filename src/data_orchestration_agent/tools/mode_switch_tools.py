"""Mode switching tools using ToolContext for agent transfers."""

import logging
from typing import Any, Dict, Optional

from google.adk.tools import ToolContext

from .planning_mode_tools.session_state import to_prefixed_key

logger = logging.getLogger(__name__)


def switch_to_ask_mode(tool_context: ToolContext) -> str:
    """Switch to Ask/Discover mode for exploring datasets.
    
    Call this ONLY after user explicitly confirms they want to switch to Ask Mode.
    
    Args:
        tool_context: ADK tool context for agent transfer
        
    Returns:
        Confirmation message
    """
    logger.warning(f"🔄 TOOL CALLED: switch_to_ask_mode")
    session_state = tool_context.session.state
    logger.debug("Setting current_mode to 'ask' in session state")
    session_state["current_mode"] = "ask"
    tool_context.actions.transfer_to_agent = "ask_agent"
    logger.info("Transferring to Ask/Discover mode (ask_agent)")
    return "Switching to Ask/Discover Mode. You can now search for datasets and explore their schemas."


def switch_to_plan_mode(tool_context: ToolContext) -> str:
    """Switch to Plan mode to create PRPs.
    
    Call this ONLY after user explicitly confirms they want to switch to Plan Mode.
    
    Args:
        tool_context: ADK tool context for agent transfer
        
    Returns:
        Confirmation message
    """
    logger.warning(f"🔄 TOOL CALLED: switch_to_plan_mode")
    session_state = tool_context.session.state
    logger.debug("Setting current_mode to 'planning' in session state")
    session_state["current_mode"] = "planning"
    tool_context.actions.transfer_to_agent = "plan_agent"
    logger.info("Transferring to Plan mode (plan_agent)")
    return "Switching to Plan Mode. Let's create a Product Requirement Prompt (PRP)."


def switch_to_action_mode(tool_context: ToolContext) -> str:
    """Switch to Action mode to execute queries or build data products.
    
    Call this ONLY after user explicitly confirms they want to switch to Action Mode.
    
    Args:
        tool_context: ADK tool context for agent transfer
        
    Returns:
        Confirmation message
    """
    logger.warning(f"🔄 TOOL CALLED: switch_to_action_mode")
    session_state = tool_context.session.state
    logger.debug("Setting current_mode to 'action' in session state")
    session_state["current_mode"] = "action"

    # Surface PRP content generated in Plan Mode for Action Mode tools
    prp_content_key = to_prefixed_key("planning.prp_content")
    prp_content = session_state.get(prp_content_key)

    if prp_content and isinstance(prp_content, str):
        logger.info(f"Found PRP content in '{prp_content_key}', making it available to Action Mode.")
        session_state["prp_text"] = prp_content
    else:
        logger.info("No PRP content found in session state to forward to Action Mode.")

    tool_context.actions.transfer_to_agent = "action_agent"
    logger.info("Transferring to Action mode (action_agent)")
    return "Switching to Action Mode. You can now execute queries or build data products from PRPs."

