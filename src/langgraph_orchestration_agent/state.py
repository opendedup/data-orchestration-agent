"""State definitions for the LangGraph orchestration agent."""

from typing import Any, Literal, TypedDict

from langchain_core.messages import BaseMessage


class AgentState(TypedDict, total=False):
    """State for the orchestration agent graph.

    This state is passed between nodes and maintains the conversation context,
    mode information, and accumulated data.
    """

    # Conversation messages
    messages: list[BaseMessage]

    # Current mode
    current_mode: Literal["ask", "plan", "action"]

    # Ask mode state
    last_search_results: dict[str, Any] | None
    datasets: dict[str, dict[str, Any]]
    queries: list[dict[str, Any]]
    query_results: list[dict[str, Any]]

    # Plan mode state
    planning_qa_history: list[dict[str, str]]
    planning_discovered_datasets: dict[str, str]
    planning_datasets_confirmed: bool
    planning_intent_confirmed: bool
    planning_prp_content: str | None
    planning_prp_generated: bool

    # Action mode state
    prp_text: str | None
    action_discovered_sources: dict[str, Any] | None
    action_generated_queries: dict[str, Any] | None
    action_graphql_api: dict[str, Any] | None

    # Next action (for routing)
    next: str | None

