"""Pytest configuration and fixtures."""

from typing import TYPE_CHECKING, Any, Dict

import pytest

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture

from data_orchestration_agent.clients import (
    ApolloMCPClient,
    DiscoveryClient,
    GraphQLClient,
    QueryGenClient,
)
from data_orchestration_agent.config import Config
from data_orchestration_agent.utils import SessionState


@pytest.fixture
def mock_config() -> Config:
    """Create a mock configuration for testing.
    
    Returns:
        Mock configuration object
    """
    config = Config(
        agent_model="gemini-2.0-flash-001",
        agent_host="127.0.0.1",
        agent_port=8085,
        discovery_agent_url="http://localhost:8080",
        query_gen_agent_url="http://localhost:8081",
        planning_agent_url="http://localhost:8082",
        graphql_agent_url="http://localhost:8083",
        apollo_mcp_url="http://localhost:8084",
        gcp_project_id="test-project",
        http_timeout=30.0,
        max_planning_turns=10,
        max_queries_per_target=3,
        max_query_iterations=10,
    )
    return config


@pytest.fixture
def mock_discovery_client(mocker: "MockerFixture") -> DiscoveryClient:
    """Create a mock discovery client.
    
    Args:
        mocker: Pytest mocker fixture
        
    Returns:
        Mocked discovery client
    """
    client = mocker.Mock(spec=DiscoveryClient)
    client.query_data_assets = mocker.AsyncMock(return_value=[])
    client.get_asset_details = mocker.AsyncMock(return_value={})
    client.discover_from_prp = mocker.AsyncMock(return_value={})
    return client


@pytest.fixture
def mock_query_gen_client(mocker: "MockerFixture") -> QueryGenClient:
    """Create a mock query generation client.
    
    Args:
        mocker: Pytest mocker fixture
        
    Returns:
        Mocked query generation client
    """
    client = mocker.Mock(spec=QueryGenClient)
    client.generate_queries = mocker.AsyncMock(return_value={})
    return client


@pytest.fixture
def mock_graphql_client(mocker: "MockerFixture") -> GraphQLClient:
    """Create a mock GraphQL client.
    
    Args:
        mocker: Pytest mocker fixture
        
    Returns:
        Mocked GraphQL client
    """
    client = mocker.Mock(spec=GraphQLClient)
    client.generate_graphql_api = mocker.AsyncMock(return_value={})
    return client


@pytest.fixture
def mock_apollo_mcp_client(mocker: "MockerFixture") -> ApolloMCPClient:
    """Create a mock Apollo MCP client.
    
    Args:
        mocker: Pytest mocker fixture
        
    Returns:
        Mocked Apollo MCP client
    """
    client = mocker.Mock(spec=ApolloMCPClient)
    client.list_tools = mocker.AsyncMock(return_value=[])
    client.call_tool = mocker.AsyncMock(return_value={})
    return client


@pytest.fixture
def mock_bigquery_agent(mocker: "MockerFixture") -> Any:
    """Create a mock BigQuery agent.
    
    Args:
        mocker: Pytest mocker fixture
        
    Returns:
        Mocked BigQuery agent
    """
    agent = mocker.Mock()
    
    # Mock Agent attributes that are accessed
    agent.model = "gemini-2.0-flash-001"
    agent.instruction = "You are a BigQuery Analysis Agent"
    agent.tools = []
    
    return agent


@pytest.fixture
def session_state() -> SessionState:
    """Create a fresh session state for testing.
    
    Returns:
        Empty session state
    """
    return SessionState()


@pytest.fixture
def sample_prp_text() -> str:
    """Create a sample PRP text for testing.
    
    Returns:
        Sample PRP markdown
    """
    return """# Data Product Requirement Prompt

## 9. Target Schema

### Table: `customer_analytics`

```json
{
  "fields": [
    {"name": "customer_id", "type": "STRING"},
    {"name": "total_orders", "type": "INTEGER"},
    {"name": "total_revenue", "type": "FLOAT"}
  ]
}
```

## 10. Additional Notes

This is a test PRP.
"""

