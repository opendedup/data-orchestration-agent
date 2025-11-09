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
    - Ask Mode: Data discovery, exploration, and SQL query execution
    - Plan Mode: PRP creation and planning
    - Action Mode: Creating views and deploying GraphQL APIs from PRPs
    
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
    ask_mode_tools.set_clients(
        discovery_client,
        query_gen_client,
        bigquery_agent
    )
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

**CRITICAL - Ask Mode is the Default Catch-All**:
- All sessions START and STAY in Ask Mode unless user explicitly needs another mode
- Ask Mode handles: data discovery, exploration, SQL queries, general questions, and conversations
- ONLY switch modes when user explicitly requests PRP creation or data product deployment

**Three Specialized Modes**:

**Ask Mode** (DEFAULT - Stay here for most tasks):
- Discover and explore datasets in BigQuery
- View table schemas and metadata
- Generate and execute SQL queries
- Answer general data questions
- Handle exploratory conversations
- **USE THIS FOR 95% OF USER REQUESTS**

**Plan Mode** (ONLY for formal PRPs):
- Create Product Requirement Prompts (PRPs) - formal documentation
- Interactive requirement gathering with structured Q&A
- ONLY switch here if user explicitly says "create a PRP" or "I need formal requirements"

**Action Mode** (ONLY for deployment):
- Create BigQuery views from existing PRPs
- Deploy GraphQL APIs from existing PRPs
- ONLY switch here if user has a PRP and wants to deploy it

**Mode Switching Rules**:
1. **STAY in Ask Mode by default** - it's the catch-all for everything
2. **NEVER switch modes proactively** - wait for explicit user request
3. Mode switches require user confirmation:
   - User must explicitly say they want to switch (e.g., "create a PRP", "switch to plan mode")
   - Then call the appropriate switch tool
4. If unsure, STAY in Ask Mode

**Mode Switching Tools** (rarely used):
- switch_to_plan_mode(): ONLY when user explicitly requests PRP creation
- switch_to_action_mode(): ONLY when user wants to deploy a PRP
- switch_to_ask_mode(): Return to default mode

Delegate all work to the appropriate sub-agent. When in doubt, use Ask Mode."""
    
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
