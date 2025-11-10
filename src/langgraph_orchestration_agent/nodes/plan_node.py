"""Plan mode node for PRP creation."""

import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ..llm import create_llm
from ..state import AgentState

logger = logging.getLogger(__name__)


def plan_node(state: AgentState, config: Any, clients: dict[str, Any]) -> dict[str, Any]:
    """Process messages in Plan mode for PRP creation.

    Args:
        state: Current agent state
        config: Agent configuration
        clients: Dictionary of MCP clients

    Returns:
        Updated state dictionary
    """
    logger.info("Entering plan_node")

    # Initialize mode if needed
    if "current_mode" not in state:
        state["current_mode"] = "plan"

    # Get the last user message
    messages = state.get("messages", [])
    if not messages:
        logger.warning("No messages in state")
        return {"messages": messages, "current_mode": "plan"}

    last_message = messages[-1]
    if not isinstance(last_message, HumanMessage):
        logger.warning("Last message is not a HumanMessage")
        return state

    # Create system message for plan mode
    SystemMessage(content="""You are a Data Planning Specialist in Plan Mode.

Your role: Guide users through creating Data Product Requirement Prompts (PRPs) via conversational Q&A.

**Workflow:**

### Phase 1: Understand Intent & Discover Datasets
1. Search for relevant datasets using the user's intent
2. Present datasets with key columns from schemas
3. Ask: "Do these tables cover your needs?"

### Phase 2: Gather Requirements
4. Ask iterative questions to understand requirements
5. Continue until you have complete information

### Phase 3: Generate PRP
6. Confirm understanding with user
7. Generate the PRP document

**Guidelines:**
- Always prepend responses with: # Plan Mode
- Be thorough, conversational, and data-driven
- Plan Mode creates PRPs (requirements), NOT SQL queries""")

    # Create LLM
    create_llm(config)

    # For now, provide a simple response
    response_content = "# Plan Mode\n\nI'm in Plan mode and ready to help you create a Product Requirement Prompt. What data product would you like to plan?"

    # Create response message
    ai_message = AIMessage(content=response_content)

    # Update messages
    updated_messages = messages + [ai_message]

    return {
        "messages": updated_messages,
        "current_mode": "plan"
    }

