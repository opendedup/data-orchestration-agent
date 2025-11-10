"""Tests for LangGraph orchestration graph."""

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import HumanMessage

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture

from langgraph_orchestration_agent.config import Config
from langgraph_orchestration_agent.graph import create_graph, run_graph


@pytest.fixture
def mock_config() -> Config:
    """Create a mock configuration."""
    return Config(
        gcp_project_id="test-project",
        google_api_key="test-key",
        agent_model="gemini-2.5-flash",
    )


@pytest.fixture
def mock_clients() -> dict[str, Any]:
    """Create mock MCP clients."""
    return {
        "discovery": MagicMock(),
        "query_gen": MagicMock(),
        "graphql": MagicMock(),
        "apollo": MagicMock(),
    }


def test_create_graph(mock_config: Config, mock_clients: dict[str, Any]) -> None:
    """Test that create_graph returns a compiled graph."""
    graph = create_graph(mock_config, mock_clients)

    assert graph is not None
    # The graph should be compiled and ready to use
    assert hasattr(graph, "invoke")


@pytest.mark.asyncio
async def test_run_graph_initializes_state(
    mocker: "MockerFixture",
    mock_config: Config,
    mock_clients: dict[str, Any]
) -> None:
    """Test that run_graph initializes state correctly."""
    # Mock the LLM to avoid actual API calls
    mock_llm = mocker.patch("langgraph_orchestration_agent.llm.create_llm")
    mock_llm.return_value.bind_tools.return_value.invoke.return_value = mocker.MagicMock(
        content="Test response",
        tool_calls=None
    )

    graph = create_graph(mock_config, mock_clients)

    result = await run_graph(graph, "Hello")

    assert "messages" in result
    assert "current_mode" in result
    assert result["current_mode"] == "ask"
    assert len(result["messages"]) >= 1


@pytest.mark.asyncio
async def test_run_graph_adds_user_message(
    mocker: "MockerFixture",
    mock_config: Config,
    mock_clients: dict[str, Any]
) -> None:
    """Test that run_graph adds the user message to state."""
    mock_llm = mocker.patch("langgraph_orchestration_agent.llm.create_llm")
    mock_llm.return_value.bind_tools.return_value.invoke.return_value = mocker.MagicMock(
        content="Test response",
        tool_calls=None
    )

    graph = create_graph(mock_config, mock_clients)

    result = await run_graph(graph, "Test message")

    messages = result["messages"]
    human_messages = [m for m in messages if isinstance(m, HumanMessage)]

    assert len(human_messages) >= 1
    assert human_messages[0].content == "Test message"


@pytest.mark.asyncio
async def test_run_graph_maintains_conversation(
    mocker: "MockerFixture",
    mock_config: Config,
    mock_clients: dict[str, Any]
) -> None:
    """Test that run_graph maintains conversation history."""
    mock_llm = mocker.patch("langgraph_orchestration_agent.llm.create_llm")
    mock_llm.return_value.bind_tools.return_value.invoke.return_value = mocker.MagicMock(
        content="Test response",
        tool_calls=None
    )

    graph = create_graph(mock_config, mock_clients)

    # First turn
    state1 = await run_graph(graph, "First message")

    # Second turn with existing state
    state2 = await run_graph(graph, "Second message", state1)

    messages = state2["messages"]
    human_messages = [m for m in messages if isinstance(m, HumanMessage)]

    # Should have both messages
    assert len(human_messages) >= 2
    assert any("First message" in m.content for m in human_messages)
    assert any("Second message" in m.content for m in human_messages)

