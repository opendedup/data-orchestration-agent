"""HTTP client for the Data GraphQL Agent MCP service."""

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class GraphQLClient:
    """Client for interacting with the Data GraphQL Agent via HTTP."""

    def __init__(self, base_url: str, timeout: float = 300.0):
        """Initialize the GraphQL client.
        
        Args:
            base_url: Base URL for the GraphQL agent (e.g., http://localhost:8083)
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
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": 1
        }
        
        logger.info(f"Calling GraphQL tool: {tool_name}")
        logger.debug(f"Request payload: {payload}")
        
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        logger.debug(f"Response: {result}")
        
        return result

    async def generate_graphql_api(
        self,
        queries: List[Dict[str, Any]],
        project_name: str,
        validation_level: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a GraphQL API from validated SQL queries.
        
        Args:
            queries: List of validated SQL queries with metadata
            project_name: Name for the GraphQL project
            validation_level: Validation level (strict, moderate, permissive)
            
        Returns:
            GraphQL API generation results including file paths
        """
        arguments = {
            "queries": queries,
            "project_name": project_name
        }
        
        if validation_level:
            arguments["validation_level"] = validation_level
        
        result = await self._call_tool("generate_graphql_api", arguments)
        return result.get("result", {})

