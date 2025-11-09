"""Action Mode tools for executing PRPs and building data products."""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)

# Global client instances (will be injected by main.py)
_discovery_client = None
_query_gen_client = None
_graphql_client = None
_apollo_mcp_client = None
_bigquery_agent = None


def set_clients(
    discovery_client: Any,
    query_gen_client: Any,
    graphql_client: Any,
    apollo_mcp_client: Optional[Any] = None
) -> None:
    """Set the global client instances.
    
    Args:
        discovery_client: Data discovery client instance
        query_gen_client: Query generation client instance
        graphql_client: GraphQL client instance
        apollo_mcp_client: Apollo MCP client instance (optional)
    """
    global _discovery_client, _query_gen_client, _graphql_client, _apollo_mcp_client
    _discovery_client = discovery_client
    _query_gen_client = query_gen_client
    _graphql_client = graphql_client
    _apollo_mcp_client = apollo_mcp_client


def set_bigquery_agent(bigquery_agent: Any) -> None:
    """Set the BigQuery agent instance.
    
    Args:
        bigquery_agent: BigQuery agent instance
    """
    global _bigquery_agent
    _bigquery_agent = bigquery_agent


def _extract_target_schemas(prp_text: str) -> List[Dict[str, Any]]:
    """Extract target table schemas from PRP Section 9.
    
    Args:
        prp_text: Full PRP markdown text
        
    Returns:
        List of target schema definitions
    """
    # Find Section 9 in PRP
    section_9_match = re.search(
        r'## 9\. Target Schema.*?(?=## 10\.|$)',
        prp_text,
        re.DOTALL | re.IGNORECASE
    )
    
    if not section_9_match:
        logger.warning("Could not find Section 9 in PRP")
        return []
    
    section_9_text = section_9_match.group(0)
    
    # Extract table definitions (simplified parsing)
    # In a real implementation, this would be more sophisticated
    target_schemas = []
    
    # Look for table markdown blocks
    table_matches = re.finditer(
        r'### Table: `(.+?)`.*?```(?:json|yaml)?\n(.*?)\n```',
        section_9_text,
        re.DOTALL
    )
    
    for match in table_matches:
        table_name = match.group(1)
        schema_text = match.group(2)
        
        try:
            schema_data = json.loads(schema_text)
            target_schemas.append({
                "table_name": table_name,
                "schema": schema_data
            })
        except json.JSONDecodeError:
            logger.warning(f"Could not parse schema for table: {table_name}")
    
    return target_schemas


async def query_graphql_data(
    operation_name: str,
    variables: Optional[Dict[str, Any]] = None
) -> str:
    """Execute GraphQL query via Apollo MCP server (ACTION MODE).
    
    Args:
        operation_name: Name of the GraphQL operation/tool
        variables: Optional query variables as dictionary
        
    Returns:
        Formatted query results
    """
    try:
        logger.info(f"[ACTION MODE] Executing GraphQL operation: {operation_name}")
        
        if variables is None:
            variables = {}
        
        result = await _apollo_mcp_client.call_tool(operation_name, variables)
        
        # Format results
        return f"# Query Results: {operation_name}\n\n```json\n{json.dumps(result, indent=2)}\n```"
        
    except Exception as e:
        logger.error(f"Error executing GraphQL query: {e}")
        return f"Error executing GraphQL query: {str(e)}"


# ============================================================================
# PRP Execution Workflow
# ============================================================================


async def discover_sources_from_prp(tool_context: ToolContext) -> str:
    """Discover source tables from PRP Section 9 requirements.
    
    Returns:
        Summary of discovered sources with confirmation prompt
    """
    try:
        session_state = tool_context.session.state
        prp_text = session_state.get("prp_text")
        if not prp_text:
            return "No PRP found in session. Please generate a PRP first using Planning Mode."
        
        logger.info("Discovering sources from PRP")
        
        # Extract target schemas from PRP
        target_schemas = _extract_target_schemas(prp_text)
        
        if not target_schemas:
            return "Could not extract target schemas from PRP. Please check Section 9 format."
        
        # Discover sources for each target table
        all_discoveries = []
        
        for target in target_schemas:
            result = await _discovery_client.discover_from_prp(
                prp_markdown=prp_text,
                target_schema=target
            )
            all_discoveries.append({
                "target_table": target["table_name"],
                "sources": result.get("sources", []),
                "mappings": result.get("mappings", [])
            })
        
        # Store in state
        logger.debug("Storing discovered_datasets, action_step, and pending_confirmation in session state")
        session_state["discovered_datasets"] = all_discoveries
        session_state["action_step"] = "discovery"
        session_state["pending_confirmation"] = "discovery"
        
        # Format response
        response = "# Discovery Results 🔍\n\n"
        response += f"Found sources for {len(all_discoveries)} target table(s):\n\n"
        
        for discovery in all_discoveries:
            response += f"## Target: `{discovery['target_table']}`\n"
            response += f"- **Source tables found**: {len(discovery['sources'])}\n"
            
            for source in discovery['sources'][:5]:  # Show first 5
                response += f"  - `{source.get('table_id', 'N/A')}` "
                response += f"(confidence: {source.get('confidence', 0):.0%})\n"
            
            if len(discovery['sources']) > 5:
                response += f"  - ... and {len(discovery['sources']) - 5} more\n"
            response += "\n"
        
        response += "\n**Next Step**: Would you like to proceed with query generation, "
        response += "iterate on the discovery, or cancel?\n"
        
        return response
        
    except Exception as e:
        logger.error(f"Error discovering sources: {e}")
        return f"Error discovering sources: {str(e)}"


async def generate_queries_from_discovery(tool_context: ToolContext, approve_discovery: bool = True) -> str:
    """Generate SQL queries from discovered datasets.
    
    Args:
        tool_context: The ADK ToolContext with access to session state.
        approve_discovery: Whether user approves the discovery results
        
    Returns:
        Summary of generated queries with confirmation prompt
    """
    try:
        if not approve_discovery:
            return "Discovery not approved. Please use `iterate_on_step` to modify the discovery."
        
        session_state = tool_context.session.state
        discovered_datasets = session_state.get("discovered_datasets")
        if not discovered_datasets:
            return "No discovered datasets found. Please run discovery first."
        
        prp_text = session_state.get("prp_text", "")
        
        logger.info("Generating queries from discovery")
        
        # Generate queries for each target table
        all_query_results = []
        
        for discovery in discovered_datasets:
            target_table = discovery["target_table"]
            sources = discovery["sources"]
            
            # Create insight from PRP
            insight = f"Generate queries for target table {target_table} using discovered sources"
            
            # Prepare datasets for query generation
            datasets = [
                {
                    "table_id": source.get("table_id"),
                    "schema": source.get("schema", {}),
                    "description": source.get("description", "")
                }
                for source in sources
            ]
            
            result = await _query_gen_client.generate_queries(
                insight=insight,
                datasets=datasets,
                max_queries=session_state.get("max_queries_per_target", 3),
                max_iterations=session_state.get("max_query_iterations", 10)
            )
            
            all_query_results.append({
                "target_table": target_table,
                "queries": result.get("queries", []),
                "validation": result.get("validation", {})
            })
        
        # Store in state
        logger.debug("Storing query_results, action_step, and pending_confirmation in session state")
        session_state["query_results"] = all_query_results
        session_state["action_step"] = "queries"
        session_state["pending_confirmation"] = "queries"
        
        # Format response
        response = "# Query Generation Results 🔧\n\n"
        response += f"Generated queries for {len(all_query_results)} target table(s):\n\n"
        
        for result in all_query_results:
            response += f"## Target: `{result['target_table']}`\n"
            response += f"- **Queries generated**: {len(result['queries'])}\n"
            
            validation = result.get("validation", {})
            if validation:
                response += f"- **Validation status**: {validation.get('status', 'unknown')}\n"
            
            # Show first query
            if result['queries']:
                first_query = result['queries'][0]
                response += "\n**Sample Query**:\n"
                response += f"```sql\n{first_query.get('sql', 'N/A')[:300]}...\n```\n"
            response += "\n"
        
        response += "\n**Next Step**: Would you like to proceed with GraphQL API generation, "
        response += "iterate on the queries, or cancel?\n"
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating queries: {e}")
        return f"Error generating queries: {str(e)}"


async def create_graphql_api(
    tool_context: ToolContext,
    approve_queries: bool = True,
    project_name: Optional[str] = None
) -> str:
    """Generate GraphQL API from validated queries.
    
    Args:
        tool_context: The ADK ToolContext with access to session state.
        approve_queries: Whether user approves the generated queries
        project_name: Name for the GraphQL project
        
    Returns:
        Success message with file paths
    """
    try:
        if not approve_queries:
            return "Queries not approved. Please use `iterate_on_step` to modify the queries."
        
        session_state = tool_context.session.state
        query_results = session_state.get("query_results")
        if not query_results:
            return "No query results found. Please generate queries first."
        
        if not project_name:
            project_name = "data_product_api"
        
        logger.info(f"Creating GraphQL API: {project_name}")
        
        # Flatten all queries
        all_queries = []
        for result in query_results:
            for query in result.get("queries", []):
                all_queries.append({
                    "target_table": result["target_table"],
                    "sql": query.get("sql"),
                    "description": query.get("description"),
                    "parameters": query.get("parameters", [])
                })
        
        result = await _graphql_client.generate_graphql_api(
            queries=all_queries,
            project_name=project_name,
            validation_level="moderate"
        )
        
        # Store in state
        output_path = result.get("output_path", "")
        logger.debug(f"Storing graphql_output_path: {output_path} in session state")
        session_state["graphql_output_path"] = output_path
        session_state["action_step"] = "complete"
        session_state["pending_confirmation"] = None
        
        # Format response
        response = "# GraphQL API Generated! 🚀\n\n"
        response += f"**Project Name**: {project_name}\n"
        response += f"**Output Path**: `{output_path}`\n\n"
        
        # Show generated files
        files = result.get("files", [])
        if files:
            response += "## Generated Files\n\n"
            for file in files:
                response += f"- `{file}`\n"
        
        response += "\n**Status**: Data product workflow complete! ✨\n"
        response += "\nYou can now deploy and use your GraphQL API.\n"
        
        return response
        
    except Exception as e:
        logger.error(f"Error creating GraphQL API: {e}")
        return f"Error creating GraphQL API: {str(e)}"


async def iterate_on_step(tool_context: ToolContext, step_name: str, modifications: str) -> str:
    """Allow user to request modifications to a previous step.
    
    Args:
        tool_context: The ADK ToolContext with access to session state.
        step_name: Step to iterate on (discovery, queries, or graphql)
        modifications: User's requested changes
        
    Returns:
        Status message about re-execution
    """
    try:
        logger.info(f"Iterating on step: {step_name}")
        
        valid_steps = ["discovery", "queries", "graphql"]
        if step_name not in valid_steps:
            return f"Invalid step name. Must be one of: {', '.join(valid_steps)}"
        
        # Store modification request
        session_state = tool_context.session.state
        modification_key = f"{step_name}_modifications"
        logger.debug(f"Storing modification request in session_state['{modification_key}']")
        session_state[modification_key] = modifications
        
        response = f"# Iterating on {step_name.title()} Step 🔄\n\n"
        response += f"**Modifications requested**: {modifications}\n\n"
        
        # Re-execute the appropriate step
        if step_name == "discovery":
            # Clear downstream results
            logger.debug("Clearing query_results and graphql_output_path from session state")
            session_state.pop("query_results", None)
            session_state.pop("graphql_output_path", None)
            return response + "\nPlease call `discover_sources_from_prp` again to re-run discovery."
        
        elif step_name == "queries":
            # Clear downstream results
            logger.debug("Clearing graphql_output_path from session state")
            session_state.pop("graphql_output_path", None)
            return response + "\nPlease call `generate_queries_from_discovery` again to re-generate queries."
        
        elif step_name == "graphql":
            return response + "\nPlease call `create_graphql_api` again to re-generate the GraphQL API."
        
    except Exception as e:
        logger.error(f"Error iterating on step: {e}")
        return f"Error iterating on step: {str(e)}"
