"""LangGraph graph definition for orchestration agent."""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
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

    # Compile the graph with checkpointer for interrupt support
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)

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
    app: StateGraph,
    user_input: str,
    state: dict[str, Any] | None = None,
    *,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """Run the graph with a user input.

    Args:
        app: Compiled StateGraph
        user_input: User's message
        state: Optional existing state to continue conversation
        thread_id: Optional thread ID for checkpointer persistence

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

    # Build config with thread_id if checkpointer is present
    config: dict[str, Any] | None = None
    if hasattr(app, "checkpointer") and app.checkpointer is not None:
        # Checkpointer requires a thread_id
        thread_id = thread_id or "default-thread"
        config = {"configurable": {"thread_id": thread_id}}

    # Run the graph
    result = await app.ainvoke(state, config=config)

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

    config: dict[str, Any] | None = (
        {"configurable": {"thread_id": thread_id}} if thread_id else None
    )

    # Use astream with stream_mode="values" to get full state including interrupts
    async for latest_state in app.astream(state, config=config, stream_mode="values"):
        logger.debug(f"State update: {latest_state.keys() if isinstance(latest_state, dict) else type(latest_state)}")
        
        # Check for interrupt in state
        if "__interrupt__" in latest_state:
            logger.info(f"[INTERRUPT] Detected interrupt in state: {latest_state['__interrupt__']}")
            yield GraphStreamEvent(
                event_type="interrupt",
                payload={"interrupt": latest_state["__interrupt__"]},
                state=latest_state,
            )
            # Don't yield final_state on interrupt - the graph is paused
            return
        
        # Yield state update event
        yield GraphStreamEvent(
            event_type="state_update",
            payload={"state": latest_state},
            state=latest_state,
        )

    # Only yield final_state if we completed without interrupt
    yield GraphStreamEvent(
        event_type="final_state",
        payload={"result": latest_state},
        state=latest_state,
    )
