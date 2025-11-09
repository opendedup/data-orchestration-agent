"""ADK-compatible agent definition for development and testing.

This module provides the root_agent variable expected by ADK web server (`adk web`).
For production deployment, use the FastAPI server in main.py instead.
"""

import logging
import os

# Configure logging to respect the LOG_LEVEL environment variable
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
# Get the root logger configured by the ADK framework and set its level.
# This is more robust than using basicConfig(force=True) which can be overwritten.
logging.getLogger().setLevel(log_level)

from .agents.bigquery_agent import create_bigquery_agent
from .agents.root_agent import create_orchestration_agent
from .clients import (
    ApolloMCPClient,
    DiscoveryClient,
    GraphQLClient,
    QueryGenClient,
)
from .config import load_config

logger = logging.getLogger(__name__)

# Load configuration
config = load_config()

# Initialize clients for ADK mode
discovery_client = DiscoveryClient(
    config.discovery_agent_url,
    timeout=config.http_timeout
)
query_gen_client = QueryGenClient(
    config.query_gen_agent_url,
    timeout=config.http_timeout
)
graphql_client = GraphQLClient(
    config.graphql_agent_url,
    timeout=config.http_timeout
)
apollo_mcp_client = ApolloMCPClient(
    config.apollo_mcp_url,
    timeout=config.http_timeout
)

# Create BigQuery sub-agent
bigquery_agent = create_bigquery_agent(config)

# Create root orchestration agent with sub-agents
root_agent = create_orchestration_agent(
    config=config,
    discovery_client=discovery_client,
    query_gen_client=query_gen_client,
    graphql_client=graphql_client,
    apollo_mcp_client=apollo_mcp_client,
    bigquery_agent=bigquery_agent,
)

logger.info("ADK root_agent initialized successfully with sub-agents")
