"""LangGraph graph definition for orchestration agent."""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph

from .config import Config
from .nodes import action_node, ask_node, plan_node, router_node
from .state import AgentState

logger = logging.getLogger(__name__)


def create_graph(config: Config, clients: dict[str, Any]) -> StateGraph:
    """Create the LangGraph state graph for orchestration.

    Args:
        config: Agent configuration
        clients: Dictionary of MCP clients (discovery, query_gen, graphql, apollo)

    Returns:
        Compiled StateGraph ready for execution
    """
    logger.info("Creating LangGraph orchestration graph")

    # Create the graph
    workflow = StateGraph(AgentState)

    # Define node functions with config and clients bound
    async def ask_with_context(state: AgentState) -> dict[str, Any]:
        return await ask_node(state, config, clients)

    def plan_with_context(state: AgentState) -> dict[str, Any]:
        return plan_node(state, config, clients)

    def action_with_context(state: AgentState) -> dict[str, Any]:
        return action_node(state, config, clients)

    # Add nodes
    workflow.add_node("router", router_node)
    workflow.add_node("ask", ask_with_context)
    workflow.add_node("plan", plan_with_context)
    workflow.add_node("action", action_with_context)

    # Set entry point
    workflow.set_entry_point("router")

    # Add conditional edges from router to mode nodes
    workflow.add_conditional_edges(
        "router",
        lambda state: router_node(state)["next"],
        {
            "ask": "ask",
            "plan": "plan",
            "action": "action",
        }
    )

    # Each mode node ends (no loop back to router)
    workflow.add_edge("ask", END)
    workflow.add_edge("plan", END)
    workflow.add_edge("action", END)

    # Compile the graph
    app = workflow.compile()

    logger.info("LangGraph orchestration graph compiled successfully")
    return app


@dataclass(slots=True)
class GraphStreamEvent:
    """Streaming update emitted while LangGraph executes.

    Attributes:
        event_type: Identifier describing the LangGraph lifecycle event.
        payload: Raw payload dictionary returned by LangGraph.
        state: Latest known state after applying the event.
    """

    event_type: str
    payload: dict[str, Any]
    state: dict[str, Any]


async def run_graph(
    app: StateGraph, user_input: str, state: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Run the graph with a user input.

    Args:
        app: Compiled StateGraph
        user_input: User's message
        state: Optional existing state to continue conversation

    Returns:
        Updated state after graph execution
    """
    if state is None:
        state = {
            "messages": [],
            "current_mode": "ask",
            "datasets": {},
            "queries": [],
            "query_results": [],
            "planning_qa_history": [],
            "planning_discovered_datasets": {},
            "planning_datasets_confirmed": False,
            "planning_intent_confirmed": False,
            "planning_prp_generated": False,
            "last_search_results": None,
        }

    # Add user message to state
    user_message = HumanMessage(content=user_input)
    state["messages"] = state.get("messages", []) + [user_message]

    # Run the graph
    result = await app.ainvoke(state)

    return result


async def stream_graph(
    app: StateGraph,
    user_input: str,
    state: dict[str, Any] | None = None,
    *,
    thread_id: str | None = None,
) -> AsyncIterator[GraphStreamEvent]:
    """Stream LangGraph execution while yielding incremental state updates.

    Args:
        app: Compiled LangGraph application.
        user_input: User-provided text to append to messages.
        state: Optional existing agent state.
        thread_id: Optional identifier used for LangGraph persistence.

    Yields:
        GraphStreamEvent instances describing each lifecycle update.
    """
    if state is None:
        state = {
            "messages": [],
            "current_mode": "ask",
            "datasets": {},
            "queries": [],
            "query_results": [],
            "planning_qa_history": [],
            "planning_discovered_datasets": {},
            "planning_datasets_confirmed": False,
            "planning_intent_confirmed": False,
            "planning_prp_generated": False,
            "last_search_results": None,
        }

    user_message = HumanMessage(content=user_input)
    state["messages"] = state.get("messages", []) + [user_message]

    latest_state: dict[str, Any] = state
    config: dict[str, Any] | None = (
        {"configurable": {"thread_id": thread_id}} if thread_id else None
    )

    # Use astream to get node outputs with updated state
    async for event in app.astream(state, config=config, stream_mode="updates"):
        # event is a dict with node_name as key and node output as value
        # e.g., {"router": {"next": "ask", ...}} or {"ask": {"messages": [...]}}
        for node_name, node_output in event.items():
            logger.debug(f"Node '{node_name}' output: {node_output.keys() if isinstance(node_output, dict) else type(node_output)}")
            
            # Yield node start event
            yield GraphStreamEvent(
                event_type="on_node_start",
                payload={"node": node_name},
                state=latest_state,
            )
            
            # Update latest_state with node output
            if isinstance(node_output, dict):
                # Merge node output into latest_state
                for key, value in node_output.items():
                    if key == "messages" and isinstance(value, list):
                        # For messages, take the full list from node output
                        latest_state[key] = value
                    elif value is not None:
                        latest_state[key] = value
            
            # Yield node end event with updated state
            yield GraphStreamEvent(
                event_type="on_node_end",
                payload={"node": node_name, "output": node_output},
                state=latest_state,
            )

    yield GraphStreamEvent(
        event_type="final_state",
        payload={"result": latest_state},
        state=latest_state,
    )
