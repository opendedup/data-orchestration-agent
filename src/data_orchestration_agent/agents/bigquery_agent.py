"""BigQuery analysis sub-agent using ADK's BigQueryToolset."""

import logging
from typing import Optional

import google.auth
from google.adk.agents import Agent
from google.adk.tools.bigquery import BigQueryToolset, BigQueryCredentialsConfig
from google.adk.tools.bigquery.config import BigQueryToolConfig, WriteMode

from ..config import Config

logger = logging.getLogger(__name__)


def create_bigquery_agent(config: Config) -> Agent:
    """Create a BigQuery execution sub-agent with ADK's BigQueryToolset.
    
    This agent executes SQL queries using ADK's built-in BigQuery tools.
    In the refactored workflow:
    - Query generation is handled by the query-generation-agent
    - This agent focuses solely on executing SQL and returning results
    
    Args:
        config: Configuration object with BigQuery settings
        
    Returns:
        Initialized BigQuery agent with BigQueryToolset
    """
    # Get default credentials
    credentials, project = google.auth.default()
    
    # Use project from config if available, otherwise from credentials
    project_id = config.gcp_project_id or project
    
    if not project_id:
        raise ValueError(
            "GCP_PROJECT_ID must be set in environment or available from credentials"
        )
    
    # Configure BigQueryToolset with credentials and settings
    credentials_config = BigQueryCredentialsConfig(credentials=credentials)
    
    tool_config = BigQueryToolConfig(
        write_mode=WriteMode.BLOCKED,  # Read-only for safety
        application_name="data_orchestration_bigquery_agent",
        compute_project_id=project_id,
    )
    
    bigquery_toolset = BigQueryToolset(
        credentials_config=credentials_config,
        bigquery_tool_config=tool_config
    )
    
    # Simplified instruction - agent just executes SQL provided to it
    instruction = """You are a BigQuery Execution Agent.

Your role is to execute SQL queries provided to you and return results clearly formatted.

**Your Capabilities**:
- Execute SQL queries using execute_sql
- Format results in a clear, readable way
- Report errors descriptively with specific details

**Guidelines**:
- You will receive SQL queries that are already generated
- Execute the query using the execute_sql tool
- Present results in a structured, easy-to-read format
- If there are errors, explain what went wrong clearly
- Include row counts and data summaries when relevant

**Error Handling**:
- For permission errors: Report clearly and do not retry
- For query errors: Report the specific error message
- Always be specific about what failed and why

Be helpful, clear, and thorough in presenting query results."""
    
    # Create the agent with BigQueryToolset
    agent = Agent(
        name="bigquery_agent",
        model=config.agent_model,
        instruction=instruction,
        tools=[bigquery_toolset],
    )
    
    logger.info("BigQuery sub-agent created successfully with BigQueryToolset")
    
    return agent

