"""Tests for ask mode tools."""

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest

from langgraph_orchestration_agent.tools.ask_tools import create_ask_tools
from langgraph_orchestration_agent.tools.state_manager import AskModeStateManager

if TYPE_CHECKING:
    pass


@pytest.fixture
def mock_state() -> dict[str, Any]:
    """Create a mock state dictionary for testing.

    Returns:
        Mock state dictionary
    """
    return {
        "messages": [],
        "current_mode": "ask",
        "queries": [],
        "query_results": [],
        "datasets": {},
        "last_search_results": None,
    }


@pytest.fixture
def mock_discovery_client() -> AsyncMock:
    """Create a mock discovery client.

    Returns:
        Mock discovery client
    """
    client = AsyncMock()
    client.query_data_assets = AsyncMock()
    client.get_asset_details = AsyncMock()
    return client


@pytest.fixture
def mock_query_gen_client() -> AsyncMock:
    """Create a mock query generation client.

    Returns:
        Mock query generation client
    """
    client = AsyncMock()
    client.generate_queries = AsyncMock()
    return client


@pytest.fixture
def state_manager(mock_state: dict[str, Any]) -> AskModeStateManager:
    """Create a state manager instance.

    Args:
        mock_state: Mock state dictionary

    Returns:
        AskModeStateManager instance
    """
    return AskModeStateManager(mock_state)


@pytest.fixture
def ask_tools(
    mock_discovery_client: AsyncMock,
    mock_query_gen_client: AsyncMock,
    state_manager: AskModeStateManager,
) -> list:
    """Create ask mode tools with mocked dependencies.

    Args:
        mock_discovery_client: Mock discovery client
        mock_query_gen_client: Mock query generation client
        state_manager: State manager instance

    Returns:
        List of ask mode tools
    """
    return create_ask_tools(mock_discovery_client, mock_query_gen_client, state_manager)


@pytest.mark.asyncio
async def test_search_datasets_success(
    ask_tools: list, mock_discovery_client: AsyncMock, state_manager: AskModeStateManager
) -> None:
    """Test successful dataset search.

    Args:
        ask_tools: List of ask mode tools
        mock_discovery_client: Mock discovery client
        state_manager: State manager instance
    """
    # Setup mock response
    search_response = json.dumps({
        "total_count": 2,
        "results": [
            {
                "project_id": "test-project",
                "dataset_id": "test_dataset",
                "table_id": "test_table",
                "description": "Test table",
                "row_count": 1000,
            }
        ],
    })
    mock_discovery_client.query_data_assets.return_value = search_response

    # Get search_datasets tool
    search_tool = next(t for t in ask_tools if t.name == "search_datasets")

    # Execute tool
    result = await search_tool.ainvoke({"query": "test data", "max_results": 5})

    # Verify
    assert "Found 2 dataset(s)" in result
    assert "test-project.test_dataset.test_table" in result
    assert state_manager.get_last_search_results() is not None


@pytest.mark.asyncio
async def test_search_datasets_no_results(
    ask_tools: list, mock_discovery_client: AsyncMock
) -> None:
    """Test dataset search with no results.

    Args:
        ask_tools: List of ask mode tools
        mock_discovery_client: Mock discovery client
    """
    mock_discovery_client.query_data_assets.return_value = "No results found"

    search_tool = next(t for t in ask_tools if t.name == "search_datasets")
    result = await search_tool.ainvoke({"query": "nonexistent data"})

    assert "No datasets found" in result


@pytest.mark.asyncio
async def test_get_dataset_details_success(
    ask_tools: list, mock_discovery_client: AsyncMock, state_manager: AskModeStateManager
) -> None:
    """Test successful dataset details retrieval.

    Args:
        ask_tools: List of ask mode tools
        mock_discovery_client: Mock discovery client
        state_manager: State manager instance
    """
    mock_discovery_client.get_asset_details.return_value = "# Table Details\n\nSchema info here"

    details_tool = next(t for t in ask_tools if t.name == "get_dataset_details")
    result = await details_tool.ainvoke({"table_id": "project.dataset.table"})

    assert "# Table Details" in result
    assert state_manager.get_dataset("project.dataset.table") is not None


@pytest.mark.asyncio
async def test_get_dataset_details_invalid_format(ask_tools: list) -> None:
    """Test dataset details with invalid table ID format.

    Args:
        ask_tools: List of ask mode tools
    """
    details_tool = next(t for t in ask_tools if t.name == "get_dataset_details")
    result = await details_tool.ainvoke({"table_id": "invalid_format"})

    assert "Invalid table ID format" in result


@pytest.mark.asyncio
async def test_generate_query_success(
    ask_tools: list, mock_query_gen_client: AsyncMock, state_manager: AskModeStateManager
) -> None:
    """Test successful query generation.

    Args:
        ask_tools: List of ask mode tools
        mock_query_gen_client: Mock query generation client
        state_manager: State manager instance
    """
    query_response = json.dumps({
        "queries": [
            {
                "sql": "SELECT * FROM project.dataset.table LIMIT 10",
                "description": "Get all records from table",
            }
        ]
    })
    mock_query_gen_client.generate_queries.return_value = query_response

    gen_tool = next(t for t in ask_tools if t.name == "generate_query")
    result = await gen_tool.ainvoke({
        "question": "Show me all records",
        "tables": "project.dataset.table",
        "max_rows_returned": 10,
    })

    assert "Query #0 Generated" in result
    assert "SELECT * FROM" in result
    assert len(state_manager.list_queries()) == 1


@pytest.mark.asyncio
async def test_generate_query_no_tables(ask_tools: list) -> None:
    """Test query generation with no tables provided.

    Args:
        ask_tools: List of ask mode tools
    """
    gen_tool = next(t for t in ask_tools if t.name == "generate_query")
    result = await gen_tool.ainvoke({
        "question": "Show me data",
        "tables": "",
    })

    assert "No tables provided" in result


@pytest.mark.asyncio
async def test_view_query_list_all(
    ask_tools: list, state_manager: AskModeStateManager
) -> None:
    """Test viewing all queries.

    Args:
        ask_tools: List of ask mode tools
        state_manager: State manager instance
    """
    # Add some queries
    state_manager.add_query("SELECT 1", "Test query 1", "Question 1")
    state_manager.add_query("SELECT 2", "Test query 2", "Question 2")

    view_tool = next(t for t in ask_tools if t.name == "view_query")
    result = await view_tool.ainvoke({"query_index": -1})

    assert "Query History (2 queries)" in result
    assert "Test query 1" in result
    assert "Test query 2" in result


@pytest.mark.asyncio
async def test_view_query_specific(
    ask_tools: list, state_manager: AskModeStateManager
) -> None:
    """Test viewing a specific query.

    Args:
        ask_tools: List of ask mode tools
        state_manager: State manager instance
    """
    state_manager.add_query("SELECT 1", "Test query", "Question")

    view_tool = next(t for t in ask_tools if t.name == "view_query")
    result = await view_tool.ainvoke({"query_index": 0})

    assert "Query #0" in result
    assert "SELECT 1" in result
    assert "Test query" in result


@pytest.mark.asyncio
async def test_view_query_no_queries(ask_tools: list) -> None:
    """Test viewing queries when none exist.

    Args:
        ask_tools: List of ask mode tools
    """
    view_tool = next(t for t in ask_tools if t.name == "view_query")
    result = await view_tool.ainvoke({"query_index": -1})

    assert "No queries have been generated" in result


@pytest.mark.asyncio
async def test_get_current_time(ask_tools: list) -> None:
    """Test getting current time.

    Args:
        ask_tools: List of ask mode tools
    """
    time_tool = next(t for t in ask_tools if t.name == "get_current_time")
    result = await time_tool.ainvoke({})

    assert "Current time:" in result
    # Should contain ISO format timestamp
    assert "T" in result
    assert "Z" in result or "+" in result


@pytest.mark.asyncio
async def test_run_query_no_queries(ask_tools: list) -> None:
    """Test running a query when no queries exist.

    Args:
        ask_tools: List of ask mode tools
    """
    run_tool = next(t for t in ask_tools if t.name == "run_query")
    result = await run_tool.ainvoke({"query_index": 0})

    assert "No queries found" in result


@pytest.mark.asyncio
async def test_generate_query_with_previous_indices(
    ask_tools: list, mock_query_gen_client: AsyncMock, state_manager: AskModeStateManager
) -> None:
    """Test query generation with previous query indices.

    Args:
        ask_tools: List of ask mode tools
        mock_query_gen_client: Mock query generation client
        state_manager: State manager instance
    """
    # Add some previous queries
    state_manager.add_query("SELECT * FROM table1", "Query 1", "Question 1")
    state_manager.add_query("SELECT * FROM table2", "Query 2", "Question 2")

    query_response = json.dumps({
        "queries": [
            {
                "sql": "SELECT * FROM project.dataset.table3 LIMIT 10",
                "description": "Similar to previous queries",
            }
        ]
    })
    mock_query_gen_client.generate_queries.return_value = query_response

    gen_tool = next(t for t in ask_tools if t.name == "generate_query")
    result = await gen_tool.ainvoke({
        "question": "Show me data like before",
        "tables": "project.dataset.table3",
        "previous_query_indices": "0,1",
    })

    assert "Query #2 Generated" in result
    # Verify the insight sent to query_gen_client includes examples
    call_args = mock_query_gen_client.generate_queries.call_args
    insight = call_args.kwargs["insight"]
    assert "Previous Query Examples" in insight


def test_state_manager_add_query(state_manager: AskModeStateManager) -> None:
    """Test adding a query to state manager.

    Args:
        state_manager: State manager instance
    """
    index = state_manager.add_query("SELECT 1", "Test query", "Question")
    assert index == 0
    assert len(state_manager.list_queries()) == 1
    assert state_manager.get_query(0)["query"] == "SELECT 1"


def test_state_manager_add_dataset(state_manager: AskModeStateManager) -> None:
    """Test adding a dataset to state manager.

    Args:
        state_manager: State manager instance
    """
    state_manager.add_dataset("project.dataset.table", "Details here")
    dataset = state_manager.get_dataset("project.dataset.table")
    assert dataset is not None
    assert dataset["details"] == "Details here"


def test_state_manager_set_search_results(state_manager: AskModeStateManager) -> None:
    """Test setting search results.

    Args:
        state_manager: State manager instance
    """
    results = {"total_count": 5, "results": []}
    state_manager.set_last_search_results(results)
    assert state_manager.get_last_search_results() == results

