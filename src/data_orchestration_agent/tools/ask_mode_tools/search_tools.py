"""Search and discovery tools for BigQuery datasets."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)

# Global client instance
_discovery_client = None


def set_clients(discovery_client: Any) -> None:
    """Set the global discovery client instance.
    
    Args:
        discovery_client: Data discovery client instance
    """
    global _discovery_client
    _discovery_client = discovery_client


def _get_datasets_from_state(tool_context: ToolContext) -> Dict[str, Dict[str, Any]]:
    """Get datasets dict from context state, initializing if needed.
    
    Args:
        tool_context: ADK tool context with session access
        
    Returns:
        Dictionary of dataset entries keyed by table_id
    """
    session_state = tool_context.session.state
    datasets = session_state.get("user:datasets")
    if datasets is None:
        logger.info("Initializing user:datasets in session state")
        datasets = {}
        session_state["user:datasets"] = datasets
    tool_context.state["user:datasets"] = datasets
    
    logger.info(f"Found {len(datasets)} datasets in session state")
    return datasets


async def search_datasets(
    tool_context: ToolContext,
    query: str,
    project_id: Optional[str] = None,
    max_results: int = 5,
) -> str:
    """Search for BigQuery datasets using natural language query.
    
    Stores results in session state for use by query generation tools.
    
    Args:
        tool_context: The ADK ToolContext with access to session state
        query: Natural language search query
        project_id: Optional GCP project ID to filter results
        max_results: Maximum number of results to display in summary (default: 5)
        
    Returns:
        Human-readable summary of search results
    """
    logger.warning(f"🔍 TOOL CALLED: search_datasets | query={query[:100]}... | project_id={project_id} | max_results={max_results}")
    try:
        logger.info(f"Searching datasets with query: {query} (max_results: {max_results})")
        
        # Build filters
        filters = {"output_format": "json"}
        if project_id:
            filters["project_id"] = project_id
        
        # Get JSON-formatted results from discovery agent
        result = await _discovery_client.query_data_assets(query, filters)
        
        if not result or result == "No results found":
            search_results = {
                "results": [], 
                "total_count": 0, 
                "query": query,
                "message": "No datasets found matching your query.",
            }
        else:
            try:
                search_results = json.loads(result)
                search_results["query"] = query
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse discovery client response: {e}")
                return f"Error: Invalid response format from discovery service: {str(e)}"
        
        # Store in session state for query generation tools
        session_state = tool_context.session.state
        session_state["user:last_search_results"] = search_results
        
        # Return human-readable summary
        total = search_results.get("total_count", 0)
        results = search_results.get("results", [])
        
        if total == 0:
            return "No datasets found matching your query."
        
        summary = f"Found {total} dataset(s):\n\n"
        for i, r in enumerate(results[:max_results], 1):
            table_id = f"{r['project_id']}.{r['dataset_id']}.{r['table_id']}"
            desc = r.get('description', 'No description')
            row_count = r.get('row_count', 'Unknown')
            summary += f"{i}. **{table_id}**\n"
            summary += f"   - Description: {desc}\n"
            summary += f"   - Rows: {row_count}\n\n"
        
        if total > max_results:
            summary += f"... and {total - max_results} more\n\n"
        
        return summary
        
    except Exception as e:
        logger.error(f"Error searching datasets: {e}")
        return f"Error searching datasets: {str(e)}"


async def get_dataset_details(tool_context: ToolContext, table_id: str) -> str:
    """Get detailed metadata for a specific BigQuery table.
    
    Stores results in session state for later reference.
    
    Args:
        tool_context: The ADK ToolContext (required for consistent tool signatures)
        table_id: Full table ID in format project.dataset.table
        
    Returns:
        Markdown-formatted table details
    """
    logger.warning(f"📊 TOOL CALLED: get_dataset_details | table_id={table_id}")
    try:
        logger.info(f"Getting details for table: {table_id}")
        
        # Get current datasets from context state
        datasets = _get_datasets_from_state(tool_context)
        
        # Parse table ID
        parts = table_id.split(".")
        if len(parts) != 3:
            return "Invalid table ID format. Expected: project.dataset.table"
        
        project_id, dataset_id, table_name = parts
        
        # Get markdown-formatted details from discovery agent
        result = await _discovery_client.get_asset_details(
            project_id, dataset_id, table_name
        )
        
        if not result or result == "Asset not found":
            return f"Table not found: {table_id}"
        
        # Create dataset entry
        dataset_entry = {
            "table_id": table_id,
            "details": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Store with table_id as key
        datasets[table_id] = dataset_entry
        
        # Store back to session and run state to ensure persistence and immediate availability
        session_state = tool_context.session.state
        session_state["user:datasets"] = datasets
        tool_context.state["user:datasets"] = datasets
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting dataset details: {e}")
        return f"Error getting dataset details: {str(e)}"

