"""Mode switching tools using ToolContext for agent transfers."""

import logging
from typing import Dict, Iterable

from google.adk.tools import ToolContext

from . import action_mode_tools, ask_mode_tools

logger = logging.getLogger(__name__)


def _merge_state_keys(source: Dict[str, object], target: Dict[str, object], keys: Iterable[str]) -> None:
    """Merge selected keys from source into target.

    Args:
        source: Source dictionary containing values to merge.
        target: Target dictionary to update.
        keys: Iterable of keys to copy from source to target when present.
    """
    for key in keys:
        if key in source:
            target[key] = source[key]


def switch_to_ask_mode(tool_context: ToolContext) -> str:
    """Switch to Ask/Discover mode for exploring datasets.
    
    Call this ONLY after user explicitly confirms they want to switch to Ask Mode.
    
    Args:
        tool_context: ADK tool context for agent transfer
        
    Returns:
        Confirmation message
    """
    session_state = tool_context.session.state
    session_state["current_mode"] = "ask"
    action_mode_tools.set_session_state(session_state)
    ask_mode_tools.set_session_state(session_state)
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
    session_state = tool_context.session.state
    session_state["current_mode"] = "planning"
    action_mode_tools.set_session_state(session_state)
    ask_mode_tools.set_session_state(session_state)
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
    session_state = tool_context.session.state
    session_state["current_mode"] = "action"

    # Preserve dataset discovery context gathered in Ask Mode
    ask_state = ask_mode_tools.get_session_state()
    _merge_state_keys(
        ask_state,
        session_state,
        keys=("last_search_results", "last_search_query"),
    )

    # Surface PRP content generated in Plan Mode for Action Mode tools
    planning_state = session_state.get("planning", {})
    prp_content = planning_state.get("prp_content")
    if prp_content:
        session_state["prp_text"] = prp_content

    action_mode_tools.set_session_state(session_state)
    ask_mode_tools.set_session_state(session_state)
    tool_context.actions.transfer_to_agent = "action_agent"
    logger.info("Transferring to Action mode (action_agent)")
    return "Switching to Action Mode. You can now execute queries or build data products from PRPs."

