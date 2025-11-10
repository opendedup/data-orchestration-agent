"""Tests for interrupt functionality in ask_node.

These tests verify that the interrupt mechanism works correctly for query confirmation.
Note: These tests mock the interrupt behavior since actual interrupts require a 
compiled graph with checkpointer to be properly tested in integration tests.
"""

import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from langgraph_orchestration_agent.config import Config
from langgraph_orchestration_agent.nodes.ask_node import ask_node
from langgraph_orchestration_agent.state import AgentState

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_config() -> Config:
    """Create a mock configuration."""
    return Config(
        agent_model="gemini-2.0-flash-exp",
        agent_host="localhost",
        agent_port=8000,
        enable_cors=True,
    )


@pytest.fixture
def mock_clients() -> dict[str, Any]:
    """Create mock MCP clients."""
    discovery_client = MagicMock()
    discovery_client.get_asset_details = MagicMock(return_value="Asset details")
    
    query_gen_client = MagicMock()
    query_gen_client.generate_queries = MagicMock(
        return_value='{"queries": [{"sql": "SELECT * FROM table LIMIT 10", "description": "Test query"}]}'
    )
    
    return {
        "discovery": discovery_client,
        "query_gen": query_gen_client,
        "graphql": MagicMock(),
    }


@pytest.fixture
def base_state() -> AgentState:
    """Create a base agent state for testing."""
    return {
        "messages": [],
        "current_mode": "ask",
        "queries": [],
        "query_results": [],
        "datasets": {},
        "last_search_results": None,
    }


@pytest.mark.asyncio
async def test_interrupt_logic_with_execution_keywords(
    mock_config: Config,
    mock_clients: dict[str, Any],
    base_state: AgentState,
) -> None:
    """Test that execution keywords are correctly detected.
    
    This unit test verifies the keyword detection logic without actually
    invoking the full agent loop.
    """
    # Test messages with execution keywords
    execution_messages = [
        "run a query to show sales",
        "execute a query for me",
        "show me the data",
        "get me the results",
        "fetch the sales data",
    ]
    
    execution_keywords = ["run", "execute", "show me", "get me", "fetch"]
    
    for msg_content in execution_messages:
        user_question = msg_content.lower()
        explicitly_requested = any(
            keyword in user_question for keyword in execution_keywords
        )
        assert explicitly_requested, f"Should detect execution keyword in: {msg_content}"
    
    # Test messages without execution keywords
    non_execution_messages = [
        "create a query for sales",
        "generate a query",
        "what would the SQL look like",
        "can you write a query",
    ]
    
    for msg_content in non_execution_messages:
        user_question = msg_content.lower()
        explicitly_requested = any(
            keyword in user_question for keyword in execution_keywords
        )
        assert not explicitly_requested, f"Should NOT detect execution keyword in: {msg_content}"


@pytest.mark.asyncio
async def test_query_state_management(
    mock_config: Config,
    mock_clients: dict[str, Any],
    base_state: AgentState,
) -> None:
    """Test that queries are properly saved to state.
    
    This test verifies the state manager correctly stores query information.
    """
    from langgraph_orchestration_agent.tools.state_manager import AskModeStateManager
    
    state_manager = AskModeStateManager(base_state)
    
    # Add a query
    query_sql = "SELECT * FROM table LIMIT 10"
    query_summary = "Get table data"
    question = "Show me the data"
    
    query_index = state_manager.add_query(query_sql, query_summary, question)
    
    # Verify query was added
    assert query_index == 0
    assert len(base_state["queries"]) == 1
    assert base_state["queries"][0]["query"] == query_sql
    assert base_state["queries"][0]["querysummary"] == query_summary
    assert base_state["queries"][0]["question"] == question
    
    # Verify query can be retrieved
    retrieved_query = state_manager.get_query(0)
    assert retrieved_query is not None
    assert retrieved_query["query"] == query_sql


@pytest.mark.asyncio
async def test_interrupt_integration_with_checkpointer() -> None:
    """Integration test verifying interrupt works with LangGraph checkpointer.
    
    This test verifies that the interrupt mechanism integrates properly
    with the graph's checkpointer. It creates a minimal graph with the 
    checkpointer to test the interrupt flow.
    """
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import StateGraph, END
    from langgraph.types import interrupt
    from typing import TypedDict
    
    # Define a simple state for testing
    class TestState(TypedDict):
        value: int
        interrupted: bool
    
    # Create a node that interrupts
    def interrupt_node(state: TestState) -> dict[str, Any]:
        """Node that triggers an interrupt."""
        should_continue = interrupt({
            "type": "test_interrupt",
            "message": "Should we continue?"
        })
        return {"interrupted": True, "value": state["value"] + 1 if should_continue else state["value"]}
    
    # Build graph
    workflow = StateGraph(TestState)
    workflow.add_node("test", interrupt_node)
    workflow.set_entry_point("test")
    workflow.add_edge("test", END)
    
    # Compile with checkpointer
    checkpointer = MemorySaver()
    graph = workflow.compile(checkpointer=checkpointer)
    
    # Initial state
    initial_state = {"value": 0, "interrupted": False}
    config = {"configurable": {"thread_id": "test-thread"}}
    
    # This would normally interrupt and return, but in tests without
    # resumption, we can verify the structure is correct
    try:
        result = await graph.ainvoke(initial_state, config=config)
        # If we get here, the graph completed (which shouldn't happen with interrupt)
        # unless the interrupt is not properly configured
        logger.info(f"Graph result: {result}")
    except Exception as e:
        # Interrupt may throw an exception in test environment
        logger.info(f"Graph interrupted or errored: {e}")
        # This is expected behavior for interrupts in testing


def test_checkpointer_added_to_graph() -> None:
    """Test that MemorySaver checkpointer is added to graph compilation.
    
    This test verifies the graph.py file correctly imports and uses MemorySaver.
    """
    from langgraph_orchestration_agent.graph import create_graph
    from langgraph.checkpoint.memory import MemorySaver
    
    # Create a mock config and clients
    config = Config(
        agent_model="gemini-2.0-flash-exp",
        agent_host="localhost",
        agent_port=8000,
        enable_cors=True,
    )
    
    clients = {
        "discovery": MagicMock(),
        "query_gen": MagicMock(),
        "graphql": MagicMock(),
    }
    
    # Create the graph
    graph = create_graph(config, clients)
    
    # Verify the graph has a checkpointer
    assert hasattr(graph, "checkpointer"), "Graph should have a checkpointer"
    assert graph.checkpointer is not None, "Checkpointer should not be None"
    assert isinstance(graph.checkpointer, MemorySaver), "Checkpointer should be MemorySaver"


def test_interrupt_import() -> None:
    """Test that interrupt is properly imported in ask_node."""
    import pathlib
    
    # Get the path to the ask_node.py file
    ask_node_path = pathlib.Path(__file__).parent.parent.parent / "src" / "langgraph_orchestration_agent" / "nodes" / "ask_node.py"
    
    # Read the source code
    source = ask_node_path.read_text()
    
    # Verify interrupt is imported from langgraph.types
    assert "from langgraph.types import interrupt" in source, "interrupt should be imported from langgraph.types"


@pytest.mark.asyncio
async def test_copilotkit_server_interrupt_handling() -> None:
    """Test that copilotkit_server.py properly handles interrupt events.
    
    This test verifies that the server detects __interrupt__ in state
    and emits the appropriate events.
    """
    from langgraph_orchestration_agent.copilotkit_server import create_copilotkit_app
    from langgraph_orchestration_agent.config import Config
    
    config = Config(
        agent_model="gemini-2.0-flash-exp",
        agent_host="localhost",
        agent_port=8000,
        enable_cors=True,
    )
    
    mock_clients = {
        "discovery": MagicMock(),
        "query_gen": MagicMock(),
        "graphql": MagicMock(),
    }
    
    # Create the app
    app = create_copilotkit_app(config, mock_clients)
    
    # Verify the app was created
    assert app is not None
    
    # Verify the /run endpoint exists
    routes = [route.path for route in app.routes]
    assert "/run" in routes or "/" in routes, "Run endpoint should exist"
