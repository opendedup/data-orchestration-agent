"""HTTP client for testing the orchestration agent via ADK API server."""

import asyncio
import json
import logging
from typing import Any, Dict, List

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrchestrationAgentHTTPTester:
    """Test the orchestration agent through ADK API server (real API calls)."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        app_name: str = "data_orchestration_agent",
        user_id: str = "test-user",
        session_id: str = "test-session"
    ) -> None:
        """Initialize HTTP tester.
        
        Args:
            base_url: Base URL of the ADK API server (default: http://localhost:8000)
            app_name: Name of the agent application
            user_id: User ID for session management
            session_id: Session ID for the conversation
        """
        self.base_url = base_url
        self.app_name = app_name
        self.user_id = user_id
        self.session_id = session_id
        self.client = httpx.AsyncClient(timeout=300.0)
        self.history: List[Dict[str, Any]] = []
        self.session_created = False

    async def ensure_session(self) -> None:
        """Ensure the session is created before sending messages."""
        if self.session_created:
            return
        
        try:
            # Create session using ADK API
            session_url = f"{self.base_url}/apps/{self.app_name}/users/{self.user_id}/sessions/{self.session_id}"
            response = await self.client.post(
                session_url,
                json={}
            )
            response.raise_for_status()
            self.session_created = True
            logger.info(f"✅ Session created: {self.session_id}")
        except Exception as e:
            logger.warning(f"Session creation failed (may already exist): {e}")
            # Session might already exist, which is fine
            self.session_created = True

    async def send_message(self, message: str, verbose: bool = True, streaming: bool = False) -> str:
        """Send a message to the agent via ADK API.
        
        Args:
            message: User message
            verbose: Whether to print output
            streaming: Whether to use streaming endpoint (/run_sse)
            
        Returns:
            Agent response text
        """
        # Ensure session is created before sending messages
        await self.ensure_session()
        
        if verbose:
            logger.info(f"\n{'='*80}")
            logger.info(f"USER: {message}")
            logger.info(f"{'='*80}\n")
        
        try:
            # ADK API request format
            request_body = {
                "app_name": self.app_name,
                "user_id": self.user_id,
                "session_id": self.session_id,
                "new_message": {
                    "role": "user",
                    "parts": [{"text": message}]
                },
                "streaming": streaming
            }
            
            endpoint = "/run_sse" if streaming else "/run"
            response = await self.client.post(
                f"{self.base_url}{endpoint}",
                json=request_body
            )
            response.raise_for_status()
            
            # Parse ADK response format (returns array of events directly)
            events = response.json()
            if not isinstance(events, list):
                events = [events]
            
            # Extract agent responses and tool calls from events
            agent_responses: List[str] = []
            tool_calls: List[Dict[str, Any]] = []
            
            for event in events:
                # Extract content from model responses
                if event.get("content", {}).get("role") == "model":
                    parts = event.get("content", {}).get("parts", [])
                    for part in parts:
                        if "text" in part:
                            agent_responses.append(part["text"])
                
                # Extract tool calls from function_call parts
                content = event.get("content", {})
                if content:
                    for part in content.get("parts", []):
                        if "functionCall" in part:
                            fc = part["functionCall"]
                            tool_calls.append({
                                "name": fc.get("name", "unknown"),
                                "arguments": fc.get("args", {})
                            })
            
            agent_response = " ".join(agent_responses).strip()
            
            if verbose and tool_calls:
                for tool_call in tool_calls:
                    logger.info(f"🔧 TOOL CALL: {tool_call['name']}")
                    logger.info(f"   Arguments: {json.dumps(tool_call.get('arguments', {}), indent=2)}\n")
            
            if verbose:
                logger.info(f"AGENT: {agent_response}\n")
            
            self.history.append({
                "user": message,
                "agent": agent_response,
                "tool_calls": tool_calls
            })
            
            return agent_response
            
        except Exception as e:
            error_msg = f"HTTP Error: {e}"
            logger.error(error_msg, exc_info=True)
            return f"[ERROR] {error_msg}"

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    def print_summary(self) -> None:
        """Print conversation summary."""
        logger.info(f"\n{'='*80}")
        logger.info("TEST SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"Total interactions: {len(self.history)}")
        
        total_tools = sum(len(h['tool_calls']) for h in self.history)
        logger.info(f"Total tool calls: {total_tools}")
        
        if total_tools > 0:
            tool_counts: Dict[str, int] = {}
            for interaction in self.history:
                for tool_call in interaction['tool_calls']:
                    tool_name = tool_call['name']
                    tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
            
            logger.info("\nTool usage:")
            for tool_name, count in sorted(tool_counts.items()):
                logger.info(f"  - {tool_name}: {count}x")
        
        logger.info(f"{'='*80}\n")


async def test_nfl_scenario() -> None:
    """Test the NFL backtest scenario via ADK API server."""
    tester = OrchestrationAgentHTTPTester()
    
    try:
        # Check if server is running by listing available agents
        list_apps = await tester.client.get(f"{tester.base_url}/list-apps")
        list_apps.raise_for_status()
        available_apps = list_apps.json()
        logger.info(f"✅ ADK API Server is running")
        logger.info(f"   Available agents: {available_apps}\n")
        
        # Run the scenario
        await tester.send_message("what data do I have to backtest my nfl predictions?")
        await tester.send_message("what about live inferences")
        await tester.send_message("ok it looks like I am interested in backtest_regression_inferences and regression_predictions tell me more about these tables")
        await tester.send_message("great lets create a plan")
        await tester.send_message("yes switch to plan mode")
        
        tester.print_summary()
        
    except httpx.ConnectError:
        logger.error("❌ Could not connect to ADK API server. Make sure it's running:")
        logger.error("   cd /home/user/git/data-orchestration-agent")
        logger.error("   adk api_server")
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(test_nfl_scenario())

