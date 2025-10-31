"""HTTP client for the Data Planning Agent MCP service."""

import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


class PlanningClient:
    """Client for interacting with the Data Planning Agent via HTTP."""

    def __init__(self, base_url: str, timeout: float = 300.0):
        """Initialize the planning client.
        
        Args:
            base_url: Base URL for the planning agent (e.g., http://localhost:8082)
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
        
        logger.info(f"Calling planning tool: {tool_name}")
        logger.debug(f"Request payload: {payload}")
        
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        logger.debug(f"Response: {result}")
        
        return result

    async def start_planning_session(self, initial_intent: str) -> Dict[str, Any]:
        """Start a new planning session.
        
        Args:
            initial_intent: Initial user intent or description of the data product
            
        Returns:
            Session information including session_id and first questions
        """
        arguments = {"initial_intent": initial_intent}
        result = await self._call_tool("start_planning_session", arguments)
        return result.get("result", {})

    async def continue_conversation(
        self,
        session_id: str,
        user_response: str
    ) -> Dict[str, Any]:
        """Continue a planning conversation with user responses.
        
        Args:
            session_id: Planning session ID
            user_response: User's response to planning questions
            
        Returns:
            Next questions or completion status
        """
        arguments = {
            "session_id": session_id,
            "user_response": user_response
        }
        result = await self._call_tool("continue_conversation", arguments)
        return result.get("result", {})

    async def generate_data_prp(self, session_id: str) -> Dict[str, Any]:
        """Generate the final Data Product Requirement Prompt.
        
        Args:
            session_id: Planning session ID
            
        Returns:
            Generated PRP markdown text and metadata
        """
        arguments = {"session_id": session_id}
        result = await self._call_tool("generate_data_prp", arguments)
        return result.get("result", {})

