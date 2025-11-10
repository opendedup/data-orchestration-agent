"""Router node to determine which mode to use based on conversation context."""

import logging

from langchain_core.messages import HumanMessage

from ..state import AgentState

logger = logging.getLogger(__name__)


def router_node(state: AgentState) -> dict[str, str]:
    """Route to the appropriate mode based on state and conversation.

    Args:
        state: Current agent state

    Returns:
        Dictionary with the next node to route to
    """
    logger.info("Entering router_node")

    # Check if we have an explicit mode set
    current_mode = state.get("current_mode", "ask")

    # Check if the user explicitly requested a mode switch
    messages = state.get("messages", [])
    if messages:
        last_message = messages[-1]
        if isinstance(last_message, HumanMessage):
            content = last_message.content.lower()

            # Check for explicit mode switch requests
            if any(phrase in content for phrase in ["switch to plan", "create a prp", "plan mode"]):
                logger.info("User requested Plan mode")
                return {"next": "plan"}
            elif any(phrase in content for phrase in ["switch to action", "action mode", "execute", "run query"]):
                logger.info("User requested Action mode")
                return {"next": "action"}
            elif any(phrase in content for phrase in ["switch to ask", "ask mode", "discover", "search"]):
                logger.info("User requested Ask mode")
                return {"next": "ask"}

    # Default: stay in current mode or go to ask mode
    logger.info(f"Staying in current mode: {current_mode}")
    return {"next": current_mode}

