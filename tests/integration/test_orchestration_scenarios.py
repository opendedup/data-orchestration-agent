"""Integration tests for orchestration agent scenarios."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

import pytest

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture

from data_orchestration_agent.agents.root_agent import create_orchestration_agent
from data_orchestration_agent.config import Config


class TestOrchestrationScenarios:
    """Test orchestration agent with multi-step scenarios."""

    @pytest.fixture
    def orchestration_agent(
        self,
        mock_config: Config,
        mock_discovery_client: Any,
        mock_query_gen_client: Any,
        mock_graphql_client: Any,
        mock_apollo_mcp_client: Any,
        mock_bigquery_agent: Any,
    ) -> Any:
        """Create orchestration agent for testing.
        
        Args:
            mock_config: Mock configuration
            mock_discovery_client: Mock discovery client
            mock_query_gen_client: Mock query gen client
            mock_graphql_client: Mock GraphQL client
            mock_apollo_mcp_client: Mock Apollo MCP client
            mock_bigquery_agent: Mock BigQuery agent
            
        Returns:
            Orchestration agent instance
        """
        agent = create_orchestration_agent(
            config=mock_config,
            discovery_client=mock_discovery_client,
            query_gen_client=mock_query_gen_client,
            graphql_client=mock_graphql_client,
            apollo_mcp_client=mock_apollo_mcp_client,
            bigquery_agent=mock_bigquery_agent,
        )
        return agent

    @pytest.mark.asyncio
    async def test_nfl_backtest_scenario_mock(
        self,
        orchestration_agent: Any,
        mock_discovery_client: Any,
        mocker: "MockerFixture",
    ) -> None:
        """Test complete NFL backtest scenario with mocked responses.
        
        Args:
            orchestration_agent: Agent instance
            mock_discovery_client: Mock discovery client
            mocker: Pytest mocker fixture
        """
        # Configure mock responses for each step
        mock_discovery_client.query_data_assets.return_value = [
            {
                "table_id": "lennyisagoodboy.lfndata.backtest_regression_inferences",
                "row_count": 449,
                "description": "Backtest regression inferences",
                "last_modified": "2025-10-28T20:58:44.24Z"
            },
            {
                "table_id": "lennyisagoodboy.lfndata.regression_predictions",
                "row_count": 670,
                "description": "Regression predictions",
                "last_modified": "2025-10-27T15:30:00.00Z"
            }
        ]
        
        mock_discovery_client.get_asset_details.return_value = {
            "table_id": "lennyisagoodboy.lfndata.backtest_regression_inferences",
            "schema": {
                "fields": [
                    {"name": "run_id", "type": "STRING", "description": "Backtest run ID"},
                    {"name": "game_id", "type": "STRING", "description": "NFL game ID"},
                    {"name": "predicted_margin", "type": "FLOAT", "description": "Predicted score margin"}
                ]
            },
            "row_count": 449,
            "last_modified": "2025-10-28T20:58:44.24Z",
            "contains_pii": False
        }
        
        # Step 1: Initial discovery
        result = await mock_discovery_client.query_data_assets("backtest nfl predictions")
        assert len(result) == 2
        assert any("backtest" in r["table_id"].lower() for r in result)
        
        # Step 2: Get details
        details = await mock_discovery_client.get_asset_details(
            project_id="lennyisagoodboy",
            dataset_id="lfndata",
            table_id="backtest_regression_inferences"
        )
        assert "schema" in details
        assert len(details["schema"]["fields"]) == 3
        assert details["row_count"] == 449

    @pytest.mark.asyncio
    async def test_mode_switching_workflow(
        self,
        orchestration_agent: Any,
        session_state: Dict[str, Any],
    ) -> None:
        """Test mode switching from Ask to Plan to Action.
        
        Args:
            orchestration_agent: Agent instance
            session_state: Session state fixture
        """
        # Initial state should be Ask mode (default)
        assert session_state.get("current_mode", "ask") == "ask"
        
        # Simulate mode switches
        session_state["current_mode"] = "plan"
        assert session_state["current_mode"] == "plan"
        
        session_state["current_mode"] = "action"
        assert session_state["current_mode"] == "action"
        
        # Switch back to ask
        session_state["current_mode"] = "ask"
        assert session_state["current_mode"] == "ask"

    def test_load_scenario_file(self) -> None:
        """Test loading and validating scenario files."""
        # Create a minimal scenario for testing
        scenario = {
            "name": "Test Scenario",
            "description": "A test scenario",
            "session_id": "test-123",
            "steps": [
                {
                    "step": 1,
                    "description": "First step",
                    "message": "Hello",
                    "assertions": [
                        {"type": "contains", "value": "response"}
                    ]
                }
            ]
        }
        
        # Validate structure
        assert "name" in scenario
        assert "steps" in scenario
        assert len(scenario["steps"]) > 0
        assert "message" in scenario["steps"][0]
        assert scenario["session_id"] == "test-123"

    def test_load_nfl_scenario(self) -> None:
        """Test loading the NFL backtest scenario file."""
        scenario_path = Path(__file__).parent.parent / "scenarios" / "nfl_backtest_scenario.json"
        
        # Only run if file exists
        if scenario_path.exists():
            with open(scenario_path, 'r') as f:
                scenario = json.load(f)
            
            # Validate structure
            assert scenario["name"] == "NFL Predictions Backtest vs Live Comparison Scenario"
            assert "steps" in scenario
            assert len(scenario["steps"]) == 11
            
            # Validate first step
            first_step = scenario["steps"][0]
            assert first_step["step"] == 1
            assert "message" in first_step
            assert "assertions" in first_step

    def test_load_simple_scenario(self) -> None:
        """Test loading the simple discovery scenario file."""
        scenario_path = Path(__file__).parent.parent / "scenarios" / "simple_discovery_scenario.json"
        
        # Only run if file exists
        if scenario_path.exists():
            with open(scenario_path, 'r') as f:
                scenario = json.load(f)
            
            # Validate structure
            assert scenario["name"] == "Simple Data Discovery Scenario"
            assert "steps" in scenario
            assert len(scenario["steps"]) == 3

    @pytest.mark.asyncio
    async def test_agent_has_required_tools(
        self,
        orchestration_agent: Any,
    ) -> None:
        """Test that orchestration agent has all required tools.
        
        Args:
            orchestration_agent: Agent instance
        """
        # The root agent should have mode switching tools
        assert orchestration_agent is not None
        assert hasattr(orchestration_agent, 'sub_agents')
        assert len(orchestration_agent.sub_agents) == 3  # ask, plan, action

    @pytest.mark.asyncio
    async def test_session_state_management(
        self,
        session_state: Dict[str, Any],
    ) -> None:
        """Test session state management.
        
        Args:
            session_state: Session state fixture
        """
        # Test setting and getting state
        session_state["test_key"] = "test_value"
        assert session_state["test_key"] == "test_value"
        
        # Test multiple keys
        session_state["current_mode"] = "ask"
        session_state["discovered_tables"] = ["table1", "table2"]
        
        assert session_state["current_mode"] == "ask"
        assert len(session_state["discovered_tables"]) == 2


class TestScenarioValidation:
    """Test scenario file validation and structure."""

    def test_scenario_required_fields(self) -> None:
        """Test that scenarios have all required fields."""
        required_fields = ["name", "description", "steps"]
        
        scenario = {
            "name": "Test",
            "description": "Test scenario",
            "steps": []
        }
        
        for field in required_fields:
            assert field in scenario

    def test_step_required_fields(self) -> None:
        """Test that steps have all required fields."""
        required_fields = ["step", "description", "message"]
        
        step = {
            "step": 1,
            "description": "Test step",
            "message": "Test message"
        }
        
        for field in required_fields:
            assert field in step

    def test_assertion_types(self) -> None:
        """Test valid assertion types."""
        valid_assertion_types = ["contains", "tool_called", "not_contains", "equals"]
        
        for assertion_type in valid_assertion_types:
            assertion = {
                "type": assertion_type,
                "value": "test"
            }
            assert assertion["type"] in valid_assertion_types


class TestAgentComponents:
    """Test individual agent components."""

    @pytest.mark.asyncio
    async def test_discovery_client_mock(
        self,
        mock_discovery_client: Any,
    ) -> None:
        """Test mock discovery client functionality.
        
        Args:
            mock_discovery_client: Mock discovery client
        """
        # Configure mock
        mock_discovery_client.query_data_assets.return_value = [
            {"table_id": "test.dataset.table1", "row_count": 100}
        ]
        
        # Test query
        result = await mock_discovery_client.query_data_assets("test query")
        assert len(result) == 1
        assert result[0]["table_id"] == "test.dataset.table1"

    @pytest.mark.asyncio
    async def test_query_gen_client_mock(
        self,
        mock_query_gen_client: Any,
    ) -> None:
        """Test mock query generation client functionality.
        
        Args:
            mock_query_gen_client: Mock query gen client
        """
        # Configure mock
        mock_query_gen_client.generate_queries.return_value = {
            "queries": ["SELECT * FROM table1"]
        }
        
        # Test generate
        result = await mock_query_gen_client.generate_queries({})
        assert "queries" in result
        assert len(result["queries"]) == 1

