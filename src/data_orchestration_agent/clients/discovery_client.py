"""HTTP client for the Data Discovery Agent MCP service."""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class DiscoveryClient:
    """Client for interacting with the Data Discovery Agent via HTTP."""

    def __init__(self, base_url: str, timeout: float = 300.0):
        """Initialize the discovery client.
        
        Args:
            base_url: Base URL for the discovery agent (e.g., http://localhost:8080)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool via HTTP.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool response as dictionary
            
        Raises:
            httpx.HTTPError: If the HTTP request fails
        """
        url = f"{self.base_url}/mcp/call-tool"
        payload = {
            "name": tool_name,
            "arguments": arguments
        }
        
        logger.info(f"Calling discovery tool: {tool_name}")
        logger.debug(f"Request payload: {payload}")
        
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        logger.debug(f"Response type: {type(result)}")
        logger.debug(f"Response content: {result}")
        
        return result

    async def query_data_assets(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> str:
        """Query data assets using natural language.
        
        Args:
            query: Natural language search query
            filters: Optional filters (project_id, dataset_id, etc.)
            
        Returns:
            Markdown formatted search results
        """
        arguments = {"query": query, "output_format": "markdown"}
        if filters:
            arguments.update(filters)
        
        result = await self._call_tool("query_data_assets", arguments)
        
        # Extract text from MCP TextContent response
        if isinstance(result.get("result"), list) and len(result["result"]) > 0:
            return result["result"][0].get("text", "No results found")
        
        return "No results found"

    async def get_asset_details(
        self,
        project_id: str,
        dataset_id: str,
        table_id: str
    ) -> str:
        """Get detailed metadata for a specific BigQuery table.
        
        Args:
            project_id: GCP project ID
            dataset_id: BigQuery dataset ID
            table_id: BigQuery table ID
            
        Returns:
            Markdown formatted asset details
        """
        arguments = {
            "project_id": project_id,
            "dataset_id": dataset_id,
            "table_id": table_id
        }
        
        result = await self._call_tool("get_asset_details", arguments)
        
        # Extract text from MCP TextContent response
        if isinstance(result.get("result"), list) and len(result["result"]) > 0:
            return result["result"][0].get("text", "Asset not found")
        
        return "Asset not found"

    async def discover_from_prp(
        self,
        prp_markdown: str,
        target_schema: Optional[Dict[str, Any]] = None
    ) -> str:
        """Discover source tables from a PRP Section 9 requirements.
        
        Args:
            prp_markdown: Full PRP markdown text
            target_schema: Optional target schema definition
            
        Returns:
            JSON formatted discovery results
        """
        arguments = {"prp_markdown": prp_markdown}
        if target_schema:
            arguments["target_schema"] = target_schema
        
        result = await self._call_tool("discover_from_prp", arguments)
        
        # Extract text from MCP TextContent response
        if isinstance(result.get("result"), list) and len(result["result"]) > 0:
            return result["result"][0].get("text", "{}")
        
        return "{}"

