"""Unit tests for agent tools."""

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture

from data_orchestration_agent.clients import (
    ApolloMCPClient,
    DiscoveryClient,
    GraphQLClient,
    QueryGenClient,
)
from data_orchestration_agent.tools import (
    action_mode_tools,
    ask_mode_tools,
    mode_switch_tools,
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
    
    @pytest.mark.asyncio
    async def test_generate_sql_for_question_with_explicit_params(
        self,
        mock_discovery_client: DiscoveryClient,
        mock_query_gen_client: QueryGenClient,
        mock_graphql_client: GraphQLClient,
        session_state: SessionState,
        mocker: "MockerFixture"
    ) -> None:
        """Test generate_sql_for_question with explicit parameters.
        
        Args:
            mock_discovery_client: Mocked discovery client
            mock_query_gen_client: Mocked query generation client
            mock_graphql_client: Mocked GraphQL client
            session_state: Session state fixture
            mocker: Pytest mocker fixture
        """
        # Set up clients and state
        action_mode_tools.set_clients(
            mock_discovery_client,
            mock_query_gen_client,
            mock_graphql_client
        )
        action_mode_tools.set_session_state(session_state)
        
        # Prepare test data
        question = "Show me the latest backtest predictions for last week"
        candidate_tables = [
            {
                "project_id": "lennyisagoodboy",
                "dataset_id": "lfndata",
                "table_id": "backtest_regression_inferences",
                "schema": [
                    {"name": "run_id", "type": "STRING"},
                    {"name": "game_id", "type": "STRING"},
                    {"name": "week", "type": "INTEGER"},
                    {"name": "predictions", "type": "FLOAT"}
                ],
                "description": "Backtest regression inferences",
                "row_count": 449,
                "column_count": 4
            }
        ]
        mentioned_columns = ["week", "predictions", "game_id"]
        
        # Mock query generation response
        mock_query_gen_client.generate_queries_async.return_value = {
            "queries": [
                {
                    "query_name": "backtest_predictions_last_week",
                    "sql": "SELECT * FROM lennyisagoodboy.lfndata.backtest_regression_inferences WHERE week = 10 LIMIT 30",
                    "description": "Latest backtest predictions"
                }
            ]
        }
        mock_query_gen_client.format_query_summary.return_value = "Query generated successfully"
        
        # Call tool with explicit parameters
        result = await action_mode_tools.generate_sql_for_question(
            question=question,
            candidate_tables=candidate_tables,
            mentioned_columns=mentioned_columns,
            related_queries=None,
            tool_context=None
        )
        
        # Verify
        assert "Query generated successfully" in result
        mock_query_gen_client.generate_queries_async.assert_called_once()
        
        # Verify the enhanced question contains our data
        call_args = mock_query_gen_client.generate_queries_async.call_args
        enhanced_question = call_args.kwargs["insight"]
        assert question in enhanced_question
        assert "backtest_regression_inferences" in enhanced_question
        assert "week" in enhanced_question or "predictions" in enhanced_question
        assert "1" in enhanced_question  # Should show 1 table
    
    @pytest.mark.asyncio
    async def test_generate_sql_for_question_validates_inputs(
        self,
        mock_discovery_client: DiscoveryClient,
        mock_query_gen_client: QueryGenClient,
        mock_graphql_client: GraphQLClient,
        session_state: SessionState
    ) -> None:
        """Test that generate_sql_for_question validates required inputs.
        
        Args:
            mock_discovery_client: Mocked discovery client
            mock_query_gen_client: Mocked query generation client
            mock_graphql_client: Mocked GraphQL client
            session_state: Session state fixture
        """
        # Set up clients
        action_mode_tools.set_clients(
            mock_discovery_client,
            mock_query_gen_client,
            mock_graphql_client
        )
        action_mode_tools.set_session_state(session_state)
        
        # Test empty question
        result = await action_mode_tools.generate_sql_for_question(
            question="",
            candidate_tables=[{"table_id": "test"}],
            mentioned_columns=None
        )
        assert "error" in result.lower()
        assert "question" in result.lower()
        
        # Test no tables
        result = await action_mode_tools.generate_sql_for_question(
            question="Show me data",
            candidate_tables=[],
            mentioned_columns=None
        )
        assert "error" in result.lower()
        assert "table" in result.lower()
    
    @pytest.mark.asyncio
    async def test_generate_sql_for_question_intent_detection(
        self,
        mock_discovery_client: DiscoveryClient,
        mock_query_gen_client: QueryGenClient,
        mock_graphql_client: GraphQLClient,
        session_state: SessionState
    ) -> None:
        """Test intent detection in generate_sql_for_question.
        
        Args:
            mock_discovery_client: Mocked discovery client
            mock_query_gen_client: Mocked query generation client
            mock_graphql_client: Mocked GraphQL client
            session_state: Session state fixture
        """
        # Set up clients
        action_mode_tools.set_clients(
            mock_discovery_client,
            mock_query_gen_client,
            mock_graphql_client
        )
        action_mode_tools.set_session_state(session_state)
        
        # Mock response
        mock_query_gen_client.generate_queries_async.return_value = {
            "queries": [{
                "query_name": "test",
                "sql": "SELECT * FROM test",
                "description": "Test"
            }]
        }
        mock_query_gen_client.format_query_summary.return_value = "Success"
        
        # Test single table with comparison - should detect COMPARISON only
        table = {
            "project_id": "p", "dataset_id": "d", "table_id": "t",
            "schema": [], "row_count": 100, "column_count": 5
        }
        
        result = await action_mode_tools.generate_sql_for_question(
            question="Compare backtest with regression predictions",
            candidate_tables=[table],
            mentioned_columns=None
        )
        
        # Verify intent was detected correctly
        call_args = mock_query_gen_client.generate_queries_async.call_args
        enhanced_question = call_args.kwargs["insight"]
        assert "COMPARISON" in enhanced_question
        # Should NOT detect JOIN for single table
        assert "JOIN operation" not in enhanced_question or len([table]) > 1


class TestModeSwitchTools:
    """Tests for mode switching tools."""
    
    def test_switch_to_action_mode_preserves_discovery_state(
        self,
        mocker: "MockerFixture"
    ) -> None:
        """Test that switching to Action Mode preserves discovered datasets from Ask Mode.
        
        This test verifies the fix for the bug where discovered table information
        was lost when switching from Ask Mode to Action Mode.
        
        Args:
            mocker: Pytest mocker fixture
        """
        # Create mock ToolContext with session state
        mock_session = mocker.Mock()
        mock_session.state = {
            "current_mode": "ask",
            "some_other_key": "some_value"
        }
        
        mock_tool_context = mocker.Mock()
        mock_tool_context.session = mock_session
        mock_tool_context.actions = mocker.Mock()
        
        # Set up Ask Mode state with discovered datasets
        ask_state = {
            "last_search_results": {
                "results": [
                    {
                        "project_id": "lennyisagoodboy",
                        "dataset_id": "lfndata",
                        "table_id": "backtest_regression_inferences",
                        "row_count": 449,
                        "description": "Backtest regression inferences table"
                    }
                ],
                "total_count": 1,
                "query": "backtest regression inferences"
            },
            "last_search_query": "backtest regression inferences",
            "discovered_datasets": [
                {
                    "target_table": "customer_analytics",
                    "sources": [
                        {
                            "table_id": "project.dataset.customers",
                            "confidence": 0.95
                        }
                    ]
                }
            ]
        }
        
        # Mock the ask_mode_tools.get_session_state() to return our test state
        mocker.patch.object(
            ask_mode_tools,
            "get_session_state",
            return_value=ask_state
        )
        
        # Mock set_session_state methods
        mocker.patch.object(action_mode_tools, "set_session_state")
        mocker.patch.object(ask_mode_tools, "set_session_state")
        
        # Call switch_to_action_mode
        result = mode_switch_tools.switch_to_action_mode(mock_tool_context)
        
        # Verify the result message
        assert "Switching to Action Mode" in result
        
        # Verify mode was changed
        assert mock_session.state["current_mode"] == "action"
        
        # Verify that all three keys were preserved in the session state
        assert "user:last_search_results" in mock_session.state
        assert "user:last_search_query" in mock_session.state
        assert "user:planning_discovereddatasets" in mock_session.state
        
        # Verify the values match what was in Ask Mode state
        assert mock_session.state["user:last_search_results"] == ask_state["last_search_results"]
        assert mock_session.state["user:last_search_query"] == ask_state["last_search_query"]
        assert mock_session.state["user:planning_discovereddatasets"] == ask_state["discovered_datasets"]
        
        # Verify that both tools received the updated state
        action_mode_tools.set_session_state.assert_called_once_with(mock_session.state)
        ask_mode_tools.set_session_state.assert_called_once_with(mock_session.state)
        
        # Verify agent transfer was triggered
        assert mock_tool_context.actions.transfer_to_agent == "action_agent"

    def test_switch_to_action_mode_migrates_string_planning_state(
        self,
        mocker: "MockerFixture"
    ) -> None:
        """Test that string planning state is migrated and PRP content is preserved.
        
        Args:
            mocker: Pytest mocker fixture
        """
        prp_text = "# Data Product Requirement Prompt"

        mock_session = mocker.Mock()
        mock_session.state = {
            "current_mode": "planning",
            "planning": prp_text,
        }

        mock_tool_context = mocker.Mock()
        mock_tool_context.session = mock_session
        mock_tool_context.actions = mocker.Mock()

        mocker.patch.object(ask_mode_tools, "get_session_state", return_value={})
        mocker.patch.object(action_mode_tools, "set_session_state")
        mocker.patch.object(ask_mode_tools, "set_session_state")

        result = mode_switch_tools.switch_to_action_mode(mock_tool_context)

        assert "Switching to Action Mode" in result
        assert mock_session.state["current_mode"] == "action"
        assert isinstance(mock_session.state["planning"], dict)
        assert mock_session.state["planning"]["prp_content"] == prp_text
        assert mock_session.state["planning"]["prp_generated"] is True
        assert mock_session.state["prp_text"] == prp_text
        assert mock_tool_context.actions.transfer_to_agent == "action_agent"


class TestPlanModeTools:
    """Tests for Plan Mode tools."""

    def test_update_session_state_rejects_planning_overwrite(
        self,
        mocker: "MockerFixture"
    ) -> None:
        """Test that update_session_state prevents replacing planning root with non-dict.
        
        Args:
            mocker: Pytest mocker fixture
        """
        session_state = SessionState()
        mock_tool_context = mocker.Mock()
        mock_tool_context.session = mocker.Mock(state=session_state)

        result = planning_mode_tools.update_session_state(
            mock_tool_context,
            "planning",
            "# PRP",
            planning_mode_tools.SessionStateOperation.SET
        )

        assert "Attempted to replace planning state" in result
        assert isinstance(mock_tool_context.session.state["planning"], dict)

    def test_track_user_message(self, mocker: "MockerFixture") -> None:
        """Test track_user_message helper function.
        
        Args:
            mocker: Pytest mocker fixture
        """
        session_state = SessionState()
        mock_tool_context = mocker.Mock()
        mock_tool_context.session = mocker.Mock(state=session_state)

        result = planning_mode_tools.track_user_message(
            mock_tool_context, 
            message="I need a revenue report"
        )

        assert "✓ Appended to planning.qa_history" in result
        assert len(session_state["planning"]["qa_history"]) == 1
        assert session_state["planning"]["qa_history"][0]["role"] == "user"
        assert session_state["planning"]["qa_history"][0]["content"] == "I need a revenue report"

    def test_track_assistant_message(self, mocker: "MockerFixture") -> None:
        """Test track_assistant_message helper function.
        
        Args:
            mocker: Pytest mocker fixture
        """
        session_state = SessionState()
        mock_tool_context = mocker.Mock()
        mock_tool_context.session = mocker.Mock(state=session_state)

        result = planning_mode_tools.track_assistant_message(
            mock_tool_context,
            message="I found 3 tables"
        )

        assert "✓ Appended to planning.qa_history" in result
        assert len(session_state["planning"]["qa_history"]) == 1
        assert session_state["planning"]["qa_history"][0]["role"] == "assistant"
        assert session_state["planning"]["qa_history"][0]["content"] == "I found 3 tables"

    def test_set_datasets_confirmed(self, mocker: "MockerFixture") -> None:
        """Test set_datasets_confirmed helper function.
        
        Args:
            mocker: Pytest mocker fixture
        """
        session_state = SessionState()
        session_state["planning"] = {"datasets_confirmed": False}
        mock_tool_context = mocker.Mock()
        mock_tool_context.session = mocker.Mock(state=session_state)

        result = planning_mode_tools.set_datasets_confirmed(mock_tool_context, True)

        assert "✓ Updated planning.datasets_confirmed" in result
        assert session_state["planning"]["datasets_confirmed"] is True

    def test_set_intent_confirmed(self, mocker: "MockerFixture") -> None:
        """Test set_intent_confirmed helper function.
        
        Args:
            mocker: Pytest mocker fixture
        """
        session_state = SessionState()
        session_state["planning"] = {"intent_confirmed": False}
        mock_tool_context = mocker.Mock()
        mock_tool_context.session = mocker.Mock(state=session_state)

        result = planning_mode_tools.set_intent_confirmed(mock_tool_context, True)

        assert "✓ Updated planning.intent_confirmed" in result
        assert session_state["planning"]["intent_confirmed"] is True

    def test_store_discovered_datasets(self, mocker: "MockerFixture") -> None:
        """Test store_discovered_datasets helper function.
        
        Args:
            mocker: Pytest mocker fixture
        """
        session_state = SessionState()
        session_state["planning"] = {"discovered_datasets": []}
        mock_tool_context = mocker.Mock()
        mock_tool_context.session = mocker.Mock(state=session_state)

        dataset_ids = ["project.dataset.table1", "project.dataset.table2"]
        result = planning_mode_tools.store_discovered_datasets(
            mock_tool_context,
            dataset_ids
        )

        assert "✓ Updated planning.discovered_datasets" in result
        assert session_state["planning"]["discovered_datasets"] == dataset_ids

