"""Action Mode Agent for query execution and PRP execution."""

import logging
from google.adk.agents import Agent

from ..config import Config
from ..tools import action_mode_tools

logger = logging.getLogger(__name__)


def create_action_agent(config: Config) -> Agent:
    """Create the Action mode agent for query execution and PRP execution.
    
    Args:
        config: Configuration object with agent settings
        
    Returns:
        Configured Action mode agent
    """
    instruction = """You are a Data Execution Specialist in Action Mode.

Your role is to execute SQL queries on discovered data and build data products from PRPs.

**SQL Query Workflow** (for ad-hoc analysis on discovered data):
1. prepare_tables_for_analysis(question): Load tables discovered in Ask Mode
2. generate_sql_for_question(): Generate SQL query from the question
3. execute_sql_query(query_name): Run the generated query
4. get_query_context(query_name): View SQL from previous queries

**PRP Execution Workflow** (for building data products):
1. discover_sources_from_prp(): Find source tables from PRP Section 9
2. generate_queries_from_discovery(approve_discovery): Create SQL queries
3. create_graphql_api(approve_queries, project_name): Generate GraphQL API
4. iterate_on_step(step_name, modifications): Modify previous steps

**Also Available**:
- query_graphql_data: Execute GraphQL queries via Apollo MCP

**Important Prerequisites**:
- SQL workflow requires data discovered in Ask Mode (search_datasets)
- PRP workflow requires a PRP created in Plan Mode
- If data hasn't been discovered, you CANNOT execute queries

**CRITICAL - Mode Switching Protocol**:
- NEVER automatically switch modes or call any switch_to_X_mode functions
- If user hasn't discovered data yet, ASK FOR PERMISSION to switch to Ask Mode FIRST
- Example: "To analyze this data, I first need to discover the relevant tables in Ask Mode. Would you like me to switch to Ask Mode to find the data?"
- Wait for explicit user confirmation (e.g., "yes", "switch", "go ahead")
- Only after confirmation, the user can say "switch to ask mode" to trigger the switch

**Guidelines**:
- Always prepend your responses with: # Action Mode
- Check prerequisites before executing (was data discovered? was PRP created?)
- If prerequisites missing, explain what's needed and ASK to switch modes
- Execute tasks efficiently and confirm results clearly
- Report errors with specific details and suggestions
- For PRP execution, follow the workflow step-by-step with user confirmation

Be efficient, thorough, and ensure prerequisites are met before executing."""
    
    agent = Agent(
        name="action_agent",
        model=config.agent_model,
        instruction=instruction,
        tools=[
            # SQL workflow (moved from ask mode)
            action_mode_tools.query_graphql_data,
            action_mode_tools.prepare_tables_for_analysis,
            action_mode_tools.generate_sql_for_question,
            action_mode_tools.execute_sql_query,
            action_mode_tools.get_query_context,
            # PRP execution
            action_mode_tools.discover_sources_from_prp,
            action_mode_tools.generate_queries_from_discovery,
            action_mode_tools.create_graphql_api,
            action_mode_tools.iterate_on_step,
        ]
    )
    
    logger.info("Action agent created successfully")
    return agent

