"""Action mode node for query execution and PRP execution."""

import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ..llm import create_llm
from ..state import AgentState

logger = logging.getLogger(__name__)


def action_node(state: AgentState, config: Any, clients: dict[str, Any]) -> dict[str, Any]:
    """Process messages in Action mode for execution.

    Args:
        state: Current agent state
        config: Agent configuration
        clients: Dictionary of MCP clients

    Returns:
        Updated state dictionary
    """
    logger.info("Entering action_node")

    # Initialize mode if needed
    if "current_mode" not in state:
        state["current_mode"] = "action"

    # Get the last user message
    messages = state.get("messages", [])
    if not messages:
        logger.warning("No messages in state")
        return {"messages": messages, "current_mode": "action"}

    last_message = messages[-1]
    if not isinstance(last_message, HumanMessage):
        logger.warning("Last message is not a HumanMessage")
        return state

    # Create system message for action mode
    SystemMessage(content="""You are a Data Execution Specialist in Action Mode.

Your role is to execute SQL queries on discovered data and build data products from PRPs.

**FIRST THING ON ENTRY: Check for PRP Context**
When you first enter Action Mode:
1. Check session state for existing PRP
2. Present options to the user
3. WAIT for user to tell you what they want to do

**Available Workflows:**

**PRP Execution Workflow** (when user has a PRP):
1. discover_sources_from_prp(): Find source tables
2. generate_queries_from_discovery(): Create SQL queries
3. create_graphql_api(): Generate GraphQL API

**SQL Query Workflow** (for ad-hoc questions):
1. WAIT for user to ask a specific question
2. prepare_tables_for_analysis(): Load tables
3. generate_sql_for_question(): Generate SQL query
4. execute_sql_query(): Run the query

**Guidelines**:
- Always prepend responses with: # Action Mode
- NEVER interpret or analyze query results - present data AS-IS
- Check prerequisites before executing
- Report errors with specific details""")

    # Create LLM
    create_llm(config)

    # Check for PRP in state
    has_prp = state.get("planning_prp_generated", False)
    prp_content = state.get("planning_prp_content")

    if has_prp and prp_content:
        response_content = "# Action Mode\n\nI've detected a PRP from Plan Mode. What would you like to do?\n\n1. Generate SQL queries from the PRP\n2. Create a GraphQL API from the PRP\n3. Execute a custom query\n4. Switch to another mode"
    else:
        response_content = "# Action Mode\n\nI'm in Action mode. What would you like to do?\n\n1. Execute SQL queries on discovered data\n2. Build a data product from a PRP\n3. Query GraphQL APIs\n4. Switch to another mode"

    # Create response message
    ai_message = AIMessage(content=response_content)

    # Update messages
    updated_messages = messages + [ai_message]

    return {
        "messages": updated_messages,
        "current_mode": "action"
    }

