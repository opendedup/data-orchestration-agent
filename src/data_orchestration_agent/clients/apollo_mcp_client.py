"""HTTP client for the Apollo MCP server."""

import logging
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)


class ApolloMCPClient:
    """Client for interacting with the Apollo MCP server via HTTP."""

    def __init__(self, base_url: str, timeout: float = 300.0):
        """Initialize the Apollo MCP client.
        
        Args:
            base_url: Base URL for the Apollo MCP server (e.g., http://localhost:8084)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available GraphQL operations as MCP tools.
        
        Returns:
            List of tool definitions with schemas
        """
        url = f"{self.base_url}/mcp/tools"
        
        logger.info("Listing Apollo MCP tools")
        
        response = await self.client.get(url)
        response.raise_for_status()
        
        result = response.json()
        logger.debug(f"Available tools: {result}")
        
        return result.get("tools", [])

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a GraphQL query via Apollo MCP tool.
        
        Args:
            name: Tool/operation name
            arguments: GraphQL query variables
            
        Returns:
            Query execution results
            
        Raises:
            httpx.HTTPError: If the HTTP request fails
        """
        url = f"{self.base_url}/mcp/call-tool"
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            },
            "id": 1
        }
        
        logger.info(f"Calling Apollo MCP tool: {name}")
        logger.debug(f"Request payload: {payload}")
        
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        logger.debug(f"Response: {result}")
        
        return result.get("result", {})

