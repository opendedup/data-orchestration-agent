"""Root orchestration agent with sub-agent delegation."""

import logging
from typing import Any

from google.adk.agents import Agent

from ..config import Config
from ..tools import action_mode_tools, ask_mode_tools, mode_switch_tools
from .action_agent import create_action_agent
from .ask_agent import create_ask_agent
from .plan_agent import create_plan_agent

logger = logging.getLogger(__name__)


def create_orchestration_agent(
    config: Config,
    discovery_client: Any,
    query_gen_client: Any,
    graphql_client: Any,
    apollo_mcp_client: Any,
    bigquery_agent: Any = None,
) -> Agent:
    """Create the root orchestration agent with specialized sub-agents.
    
    The root agent coordinates between three specialized modes:
    - Ask Mode: Data discovery and exploration (read-only)
    - Plan Mode: PRP creation and planning (local implementation)
    - Action Mode: Query execution and PRP execution
    
    Args:
        config: Configuration object
        discovery_client: Data discovery client
        query_gen_client: Query generation client
        graphql_client: GraphQL client
        apollo_mcp_client: Apollo MCP client
        bigquery_agent: BigQuery sub-agent for data analysis
        
    Returns:
        Configured root orchestration agent with sub-agents
    """
    # Inject clients into tool modules
    ask_mode_tools.set_clients(discovery_client, apollo_mcp_client)
    action_mode_tools.set_clients(
        discovery_client, 
        query_gen_client, 
        graphql_client,
        apollo_mcp_client
    )
    
    if bigquery_agent:
        action_mode_tools.set_bigquery_agent(bigquery_agent)
    
    logger.info("Injected clients into tool modules")
    
    # Create specialized sub-agents
    ask_agent = create_ask_agent(config)
    plan_agent = create_plan_agent(config)
    action_agent = create_action_agent(config)
    
    logger.info("Created specialized sub-agents (ask, plan, action)")
    
    # Create root agent instruction
    instruction = """You are the Data Orchestration Root Agent.

You coordinate between three specialized modes:

**Ask Mode** (STARTING MODE - Default):
- Discover and explore datasets in BigQuery
- View table schemas and metadata
- Browse available GraphQL operations
- Read-only exploration

**Plan Mode**:
- Create Product Requirement Prompts (PRPs)
- Interactive requirement gathering
- Design data products

**Action Mode**:
- Execute SQL queries on discovered data
- Execute PRPs to build data products
- Run GraphQL queries

**CRITICAL - Mode Switching Protocol**:
All sessions start in Ask Mode. Mode switches require explicit user confirmation:

1. Sub-agents will ASK for permission to switch modes
2. You must wait for explicit user confirmation (e.g., "yes", "switch", "go ahead", "switch to action mode")
3. ONLY call mode switch tools AFTER user explicitly confirms
4. NEVER automatically switch modes without user permission

**Mode Switching Tools** (only call AFTER user confirms):
- switch_to_ask_mode(): Switch to data discovery
- switch_to_plan_mode(): Switch to PRP creation
- switch_to_action_mode(): Switch to execution

**Important**:
- If a user asks something out of scope for the current mode, the sub-agent will ask for permission to switch
- Do NOT call mode switch tools until user explicitly confirms
- Remind users that all sessions start in Ask Mode
- Each mode prepends responses with "# {Mode Name}"

Delegate all work to the appropriate sub-agent based on current mode."""
    
    # Create root agent with sub-agents
    # ADK requires sub-agents to be passed in the constructor for proper agent tree registration
    root = Agent(
        name="root_orchestration_agent",
        model=config.agent_model,
        instruction=instruction,
        tools=[
            mode_switch_tools.switch_to_ask_mode,
            mode_switch_tools.switch_to_plan_mode,
            mode_switch_tools.switch_to_action_mode,
        ],
        sub_agents=[ask_agent, plan_agent, action_agent]
    )
    
    logger.info("Root orchestration agent created with sub-agents")
    return root
