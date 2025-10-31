"""Ask Mode tools for data exploration and discovery (read-only)."""

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Global client instances (will be injected by main.py)
_discovery_client = None
_apollo_mcp_client = None
_session_state = {}


def set_clients(
    discovery_client: Any,
    apollo_mcp_client: Any
) -> None:
    """Set the global client instances.
    
    Args:
        discovery_client: Data discovery client instance
        apollo_mcp_client: Apollo MCP client instance
    """
    global _discovery_client, _apollo_mcp_client
    _discovery_client = discovery_client
    _apollo_mcp_client = apollo_mcp_client


def set_session_state(state: Dict[str, Any]) -> None:
    """Set the session state reference.
    
    Args:
        state: Session state dictionary
    """
    global _session_state
    _session_state = state


async def search_datasets(query: str, project_id: Optional[str] = None) -> str:
    """Search for BigQuery datasets using natural language query.
    
    Stores results in session state for use by prepare_tables_for_analysis.
    
    Args:
        query: Natural language search query
        project_id: Optional GCP project ID to filter results
        
    Returns:
        Human-readable summary of search results
    """
    try:
        logger.info(f"Searching datasets with query: {query}")
        
        filters = {}
        if project_id:
            filters["project_id"] = project_id
        
        # Request JSON format to get structured data with schemas
        filters["output_format"] = "json"
        
        # Get JSON-formatted results from discovery agent
        result = await _discovery_client.query_data_assets(query, filters)
        
        if not result or result == "No results found":
            search_results = {
                "results": [], 
                "total_count": 0, 
                "query": query,
                "message": "No datasets found matching your query."
            }
        else:
            try:
                search_results = json.loads(result)
                search_results["query"] = query  # Store original query
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse discovery client response: {e}")
                return f"Error: Invalid response format from discovery service: {str(e)}"
        
        # Store in session state for prepare_tables_for_analysis
        _session_state["last_search_results"] = search_results
        _session_state["last_search_query"] = query
        
        # Return human-readable summary
        total = search_results.get("total_count", 0)
        results = search_results.get("results", [])
        
        if total == 0:
            return "No datasets found matching your query."
        
        summary = f"Found {total} dataset(s):\n\n"
        for i, r in enumerate(results[:5], 1):  # Show top 5
            table_id = f"{r['project_id']}.{r['dataset_id']}.{r['table_id']}"
            desc = r.get('description', 'No description')
            row_count = r.get('row_count', 'Unknown')
            summary += f"{i}. **{table_id}**\n"
            summary += f"   - Description: {desc}\n"
            summary += f"   - Rows: {row_count}\n\n"
        
        if total > 5:
            summary += f"... and {total - 5} more\n\n"
        
        summary += "✓ Results saved. You can now analyze this data using the three-step workflow: prepare_tables_for_analysis → generate_sql_for_question → execute_sql_query"
        
        return summary
        
    except Exception as e:
        logger.error(f"Error searching datasets: {e}")
        return f"Error searching datasets: {str(e)}"


async def get_dataset_details(table_id: str) -> str:
    """Get detailed metadata for a specific BigQuery table.
    
    Args:
        table_id: Full table ID in format project.dataset.table
        
    Returns:
        Markdown-formatted table details
    """
    try:
        logger.info(f"Getting details for table: {table_id}")
        
        # Parse table ID
        parts = table_id.split(".")
        if len(parts) != 3:
            return "Invalid table ID format. Expected: project.dataset.table"
        
        project_id, dataset_id, table_name = parts
        
        # Returns markdown-formatted details directly from discovery agent
        result = await _discovery_client.get_asset_details(
            project_id, dataset_id, table_name
        )
        
        if not result or result == "Asset not found":
            return f"Table not found: {table_id}"
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting dataset details: {e}")
        return f"Error getting dataset details: {str(e)}"


async def list_graphql_operations() -> str:
    """List available GraphQL operations from Apollo MCP.
    
    Returns:
        Markdown-formatted list of operations
    """
    try:
        logger.info("Listing GraphQL operations")
        
        tools = await _apollo_mcp_client.list_tools()
        
        if not tools:
            return "No GraphQL operations available."
        
        # Format as markdown
        result = f"# Available GraphQL Operations ({len(tools)})\n\n"
        for tool in tools:
            result += f"## {tool.get('name')}\n"
            result += f"**Description**: {tool.get('description', 'No description')}\n\n"
            
            # Show input schema
            schema = tool.get('inputSchema', {})
            if schema:
                result += "**Parameters**:\n"
                for prop_name, prop_def in schema.get('properties', {}).items():
                    result += f"- `{prop_name}` ({prop_def.get('type')}): "
                    result += f"{prop_def.get('description', 'No description')}\n"
            result += "\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Error listing GraphQL operations: {e}")
        return f"Error listing GraphQL operations: {str(e)}"


async def get_current_time() -> str:
    """Get the current date and time.
    
    Returns:
        Current timestamp in ISO 8601 format with timezone
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return f"Current time: {now.isoformat()}"

