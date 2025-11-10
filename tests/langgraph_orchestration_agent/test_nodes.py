"""Tests for LangGraph node functions."""

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import HumanMessage

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture

from langgraph_orchestration_agent.config import Config
from langgraph_orchestration_agent.nodes import action_node, ask_node, plan_node, router_node
from langgraph_orchestration_agent.state import AgentState


@pytest.fixture
def mock_config() -> Config:
    """Create a mock configuration."""
    return Config(
        gcp_project_id="test-project",
        google_api_key="test-key",
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


@pytest.fixture
def base_state() -> AgentState:
    """Create a base state for testing."""
    return {
        "messages": [HumanMessage(content="Test message")],
        "current_mode": "ask",
        "datasets": {},
        "generated_queries": [],
        "planning_qa_history": [],
        "planning_discovered_datasets": {},
        "planning_datasets_confirmed": False,
        "planning_intent_confirmed": False,
        "planning_prp_generated": False,
    }


@pytest.mark.asyncio
async def test_ask_node_returns_response(
    mocker: "MockerFixture",
    mock_config: Config,
    mock_clients: dict[str, Any],
    base_state: AgentState
) -> None:
    """Test that ask_node returns a response."""
    mock_llm = mocker.patch("langgraph_orchestration_agent.llm.create_llm")
    mock_llm.return_value.bind_tools.return_value.invoke.return_value = mocker.MagicMock(
        content="Test response",
        tool_calls=None
    )

    result = await ask_node(base_state, mock_config, mock_clients)

    assert "messages" in result
    assert "current_mode" in result
    assert result["current_mode"] == "ask"


def test_plan_node_returns_response(
    mocker: "MockerFixture",
    mock_config: Config,
    mock_clients: dict[str, Any],
    base_state: AgentState
) -> None:
    """Test that plan_node returns a response."""
    mocker.patch("langgraph_orchestration_agent.llm.create_llm")

    result = plan_node(base_state, mock_config, mock_clients)

    assert "messages" in result
    assert "current_mode" in result
    assert result["current_mode"] == "plan"


def test_action_node_returns_response(
    mocker: "MockerFixture",
    mock_config: Config,
    mock_clients: dict[str, Any],
    base_state: AgentState
) -> None:
    """Test that action_node returns a response."""
    mocker.patch("langgraph_orchestration_agent.llm.create_llm")

    result = action_node(base_state, mock_config, mock_clients)

    assert "messages" in result
    assert "current_mode" in result
    assert result["current_mode"] == "action"


def test_router_node_defaults_to_ask(base_state: AgentState) -> None:
    """Test that router defaults to ask mode."""
    result = router_node(base_state)

    assert result["next"] == "ask"


def test_router_node_switches_to_plan(base_state: AgentState) -> None:
    """Test that router switches to plan mode on request."""
    base_state["messages"] = [HumanMessage(content="switch to plan mode")]

    result = router_node(base_state)

    assert result["next"] == "plan"


def test_router_node_switches_to_action(base_state: AgentState) -> None:
    """Test that router switches to action mode on request."""
    base_state["messages"] = [HumanMessage(content="switch to action mode")]

    result = router_node(base_state)

    assert result["next"] == "action"


def test_router_node_stays_in_current_mode(base_state: AgentState) -> None:
    """Test that router stays in current mode by default."""
    base_state["current_mode"] = "plan"
    base_state["messages"] = [HumanMessage(content="Tell me more")]

    result = router_node(base_state)

    assert result["next"] == "plan"

