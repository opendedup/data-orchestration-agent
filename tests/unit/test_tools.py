"""Unit tests for agent tools."""

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture

from data_orchestration_agent.clients import (
    ApolloMCPClient,
    DiscoveryClient,
    GraphQLClient,
    PlanningClient,
    QueryGenClient,
)
from data_orchestration_agent.tools import (
    action_mode_tools,
    ask_mode_tools,
    planning_mode_tools,
)
from data_orchestration_agent.utils import SessionState


class TestAskModeTools:
    """Tests for Ask Mode tools."""
    
    @pytest.mark.asyncio
    async def test_search_datasets(
        self,
        mock_discovery_client: DiscoveryClient,
        mock_apollo_mcp_client: ApolloMCPClient
    ) -> None:
        """Test searching datasets.
        
        Args:
            mock_discovery_client: Mocked discovery client
            mock_apollo_mcp_client: Mocked Apollo MCP client
        """
        # Set up clients
        ask_mode_tools.set_clients(mock_discovery_client, mock_apollo_mcp_client)
        
        # Mock response
        mock_discovery_client.query_data_assets.return_value = [
            {
                "display_name": "Test Table",
                "name": "test.dataset.table",
                "asset_type": "table",
                "description": "Test description"
            }
        ]
        
        # Call tool
        result = await ask_mode_tools.search_datasets("test query")
        
        # Verify
        assert "Test Table" in result
        assert "test.dataset.table" in result
        mock_discovery_client.query_data_assets.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_dataset_details(
        self,
        mock_discovery_client: DiscoveryClient,
        mock_apollo_mcp_client: ApolloMCPClient
    ) -> None:
        """Test getting dataset details.
        
        Args:
            mock_discovery_client: Mocked discovery client
            mock_apollo_mcp_client: Mocked Apollo MCP client
        """
        # Set up clients
        ask_mode_tools.set_clients(mock_discovery_client, mock_apollo_mcp_client)
        
        # Mock response
        mock_discovery_client.get_asset_details.return_value = {
            "description": "Test table",
            "schema": {
                "fields": [
                    {"name": "id", "type": "STRING", "description": "ID field"}
                ]
            }
        }
        
        # Call tool
        result = await ask_mode_tools.get_dataset_details("project.dataset.table")
        
        # Verify
        assert "Test table" in result
        assert "id" in result
        assert "STRING" in result
        mock_discovery_client.get_asset_details.assert_called_once_with(
            "project", "dataset", "table"
        )
    
    @pytest.mark.asyncio
    async def test_get_current_time(self) -> None:
        """Test getting current time."""
        from datetime import datetime, timezone
        
        # Call tool
        result = await ask_mode_tools.get_current_time()
        
        # Verify
        assert "Current time:" in result
        assert "T" in result  # ISO 8601 format includes T separator
        assert "+" in result or "Z" in result  # Should have timezone info
        
        # Verify it's a recent timestamp (within last minute)
        now = datetime.now(timezone.utc)
        assert str(now.year) in result
    
    @pytest.mark.asyncio
    async def test_analyze_with_bigquery(
        self,
        mock_discovery_client: DiscoveryClient,
        mock_apollo_mcp_client: ApolloMCPClient,
        mock_bigquery_agent: Any,
        mocker: "MockerFixture"
    ) -> None:
        """Test analyzing with BigQuery.
        
        Args:
            mock_discovery_client: Mocked discovery client
            mock_apollo_mcp_client: Mocked Apollo MCP client
            mock_bigquery_agent: Mocked BigQuery agent
            mocker: Pytest mocker fixture
        """
        # Set up clients and agent
        ask_mode_tools.set_clients(mock_discovery_client, mock_apollo_mcp_client)
        ask_mode_tools.set_bigquery_agent(mock_bigquery_agent)
        
        # Mock GenAI client and chat API
        mock_client = mocker.Mock()
        mock_chat = mocker.Mock()
        
        # Mock the response structure
        mock_part = mocker.Mock()
        mock_part.text = "Query results: 42 rows returned"
        mock_part.function_call = None
        
        mock_content = mocker.Mock()
        mock_content.parts = [mock_part]
        
        mock_candidate = mocker.Mock()
        mock_candidate.content = mock_content
        
        mock_response = mocker.Mock()
        mock_response.candidates = [mock_candidate]
        
        # Mock both sync and async methods (code will use async if available, otherwise sync)
        # In Vertex AI mode, send_message_async may not exist, so we'll use send_message
        mock_chat.send_message = mocker.Mock(return_value=mock_response)
        # Don't add send_message_async to simulate Vertex AI behavior
        mock_client.chats.create = mocker.Mock(return_value=mock_chat)
        
        # Patch the Client import
        mocker.patch("data_orchestration_agent.tools.ask_mode_tools.Client", return_value=mock_client)
        # Mock os.getenv to return Vertex AI mode (no API key needed)
        def mock_getenv(key: str, default: str = "") -> str:
            if key == "GOOGLE_GENAI_USE_VERTEXAI":
                return "TRUE"
            return default
        mocker.patch("os.getenv", side_effect=mock_getenv)
        
        # Mock asyncio.to_thread to call the function directly (for testing)
        async def mock_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)
        mocker.patch("asyncio.to_thread", side_effect=mock_to_thread)
        
        # Call tool
        question = "How many orders were placed last week?"
        candidate_tables = ["project.dataset.orders", "project.dataset.customers"]
        result = await ask_mode_tools.analyze_with_bigquery(question, candidate_tables)
        
        # Verify
        assert "Query results: 42 rows returned" in result
        mock_chat.send_message.assert_called_once()
        
        # Check that the call included the question and tables
        call_args = mock_chat.send_message.call_args[0][0]
        assert question in call_args
        assert "project.dataset.orders" in call_args
        assert "project.dataset.customers" in call_args
    
    @pytest.mark.asyncio
    async def test_analyze_with_bigquery_no_agent(
        self,
        mock_discovery_client: DiscoveryClient,
        mock_apollo_mcp_client: ApolloMCPClient
    ) -> None:
        """Test analyzing with BigQuery when agent not initialized.
        
        Args:
            mock_discovery_client: Mocked discovery client
            mock_apollo_mcp_client: Mocked Apollo MCP client
        """
        # Set up clients without BigQuery agent
        ask_mode_tools.set_clients(mock_discovery_client, mock_apollo_mcp_client)
        ask_mode_tools.set_bigquery_agent(None)
        
        # Call tool
        result = await ask_mode_tools.analyze_with_bigquery(
            "test question",
            ["project.dataset.table"]
        )
        
        # Verify error message
        assert "Error: BigQuery agent not initialized" in result
    
    @pytest.mark.asyncio
    async def test_analyze_with_bigquery_no_tables(
        self,
        mock_discovery_client: DiscoveryClient,
        mock_apollo_mcp_client: ApolloMCPClient,
        mock_bigquery_agent: Any
    ) -> None:
        """Test analyzing with BigQuery when no tables provided.
        
        Args:
            mock_discovery_client: Mocked discovery client
            mock_apollo_mcp_client: Mocked Apollo MCP client
            mock_bigquery_agent: Mocked BigQuery agent
        """
        # Set up clients and agent
        ask_mode_tools.set_clients(mock_discovery_client, mock_apollo_mcp_client)
        ask_mode_tools.set_bigquery_agent(mock_bigquery_agent)
        
        # Call tool with empty tables list
        result = await ask_mode_tools.analyze_with_bigquery("test question", [])
        
        # Verify error message
        assert "Error: No candidate tables provided" in result


class TestPlanningModeTools:
    """Tests for Planning Mode tools."""
    
    @pytest.mark.asyncio
    async def test_start_planning(
        self,
        mock_planning_client: PlanningClient,
        session_state: SessionState
    ) -> None:
        """Test starting planning session.
        
        Args:
            mock_planning_client: Mocked planning client
            session_state: Session state fixture
        """
        # Set up client and state
        planning_mode_tools.set_client(mock_planning_client)
        planning_mode_tools.set_session_state(session_state)
        
        # Mock response
        mock_planning_client.start_planning_session.return_value = {
            "session_id": "test-session-123",
            "questions": ["What is your goal?", "Who are the users?"]
        }
        
        # Call tool
        result = await planning_mode_tools.start_planning("Build a customer dashboard")
        
        # Verify
        assert "test-session-123" in result
        assert "What is your goal?" in result
        assert session_state["planning_session_id"] == "test-session-123"
        assert session_state["planning_complete"] is False
        mock_planning_client.start_planning_session.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_answer_planning_questions(
        self,
        mock_planning_client: PlanningClient,
        session_state: SessionState
    ) -> None:
        """Test answering planning questions.
        
        Args:
            mock_planning_client: Mocked planning client
            session_state: Session state fixture
        """
        # Set up client and state
        planning_mode_tools.set_client(mock_planning_client)
        planning_mode_tools.set_session_state(session_state)
        session_state["planning_session_id"] = "test-session-123"
        
        # Mock response - not complete yet
        mock_planning_client.continue_conversation.return_value = {
            "is_complete": False,
            "questions": ["Next question?"]
        }
        
        # Call tool
        result = await planning_mode_tools.answer_planning_questions("My answers here")
        
        # Verify
        assert "Next question?" in result
        assert session_state["planning_complete"] is False
        mock_planning_client.continue_conversation.assert_called_once()


class TestActionModeTools:
    """Tests for Action Mode tools."""
    
    @pytest.mark.asyncio
    async def test_discover_sources_from_prp(
        self,
        mock_discovery_client: DiscoveryClient,
        mock_query_gen_client: QueryGenClient,
        mock_graphql_client: GraphQLClient,
        session_state: SessionState,
        sample_prp_text: str
    ) -> None:
        """Test discovering sources from PRP.
        
        Args:
            mock_discovery_client: Mocked discovery client
            mock_query_gen_client: Mocked query generation client
            mock_graphql_client: Mocked GraphQL client
            session_state: Session state fixture
            sample_prp_text: Sample PRP text
        """
        # Set up clients and state
        action_mode_tools.set_clients(
            mock_discovery_client,
            mock_query_gen_client,
            mock_graphql_client
        )
        action_mode_tools.set_session_state(session_state)
        session_state["prp_text"] = sample_prp_text
        
        # Mock response
        mock_discovery_client.discover_from_prp.return_value = {
            "sources": [
                {
                    "table_id": "project.dataset.customers",
                    "confidence": 0.95,
                    "schema": {}
                }
            ],
            "mappings": []
        }
        
        # Call tool
        result = await action_mode_tools.discover_sources_from_prp()
        
        # Verify
        assert "Discovery Results" in result
        assert "customer_analytics" in result
        assert session_state["action_step"] == "discovery"
        assert "discovered_datasets" in session_state
    
    @pytest.mark.asyncio
    async def test_iterate_on_step(
        self,
        mock_discovery_client: DiscoveryClient,
        mock_query_gen_client: QueryGenClient,
        mock_graphql_client: GraphQLClient,
        session_state: SessionState
    ) -> None:
        """Test iterating on a step.
        
        Args:
            mock_discovery_client: Mocked discovery client
            mock_query_gen_client: Mocked query generation client
            mock_graphql_client: Mocked GraphQL client
            session_state: Session state fixture
        """
        # Set up clients and state
        action_mode_tools.set_clients(
            mock_discovery_client,
            mock_query_gen_client,
            mock_graphql_client
        )
        action_mode_tools.set_session_state(session_state)
        
        # Call tool
        result = await action_mode_tools.iterate_on_step(
            "discovery",
            "Please use more recent data sources"
        )
        
        # Verify
        assert "Iterating on Discovery" in result
        assert "discovery_modifications" in session_state
        assert session_state["discovery_modifications"] == "Please use more recent data sources"

