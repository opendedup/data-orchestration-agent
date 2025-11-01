"""Simple CLI test runner that supports both mock and HTTP-based real API testing."""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

import httpx

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_orchestration_agent.agents.bigquery_agent import create_bigquery_agent
from data_orchestration_agent.agents.root_agent import create_orchestration_agent
from data_orchestration_agent.clients import (
    ApolloMCPClient,
    DiscoveryClient,
    GraphQLClient,
    QueryGenClient,
)
from data_orchestration_agent.config import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MockAgentTester:
    """Mock-based tester for fast testing without API calls."""

    def __init__(self, session_id: str = "test-session") -> None:
        """Initialize mock tester."""
        self.session_id = session_id
        self.history: List[Dict[str, Any]] = []

    async def send_message(self, message: str, verbose: bool = True) -> str:
        """Send message with mock response."""
        if verbose:
            logger.info(f"\n{'='*80}")
            logger.info(f"USER: {message}")
            logger.info(f"{'='*80}\n")
        
        tool_calls: List[Dict[str, Any]] = []
        
        # Mock logic (simplified for this version)
        if "backtest" in message.lower() or "data" in message.lower() or "inference" in message.lower():
            tool_calls.append({"name": "search_datasets", "arguments": {"query": message}})
            if verbose:
                logger.info(f"🔧 TOOL CALL: search_datasets\n")
            final_response = "Found datasets for backtesting NFL predictions."
        else:
            final_response = f"Received: {message}"
        
        if verbose:
            logger.info(f"AGENT: {final_response}\n")
        
        self.history.append({"user": message, "agent": final_response, "tool_calls": tool_calls})
        return final_response


class HTTPAgentTester:
    """HTTP-based tester for real API calls through the server."""

    def __init__(self, base_url: str = "http://localhost:8085", session_id: str = "test-session") -> None:
        """Initialize HTTP tester."""
        self.base_url = base_url
        self.session_id = session_id
        self.client = httpx.AsyncClient(timeout=300.0)
        self.history: List[Dict[str, Any]] = []

    async def send_message(self, message: str, verbose: bool = True) -> str:
        """Send message via HTTP to real server."""
        if verbose:
            logger.info(f"\n{'='*80}")
            logger.info(f"USER: {message}")
            logger.info(f"{'='*80}\n")
        
        try:
            response = await self.client.post(
                f"{self.base_url}/chat",
                json={"session_id": self.session_id, "message": message}
            )
            response.raise_for_status()
            
            data = response.json()
            agent_response = data.get("response", "")
            tool_calls = data.get("tool_calls", [])
            
            if verbose and tool_calls:
                for tool_call in tool_calls:
                    logger.info(f"🔧 TOOL CALL: {tool_call['name']}\n")
            
            if verbose:
                logger.info(f"AGENT: {agent_response}\n")
            
            self.history.append({"user": message, "agent": agent_response, "tool_calls": tool_calls})
            return agent_response
            
        except Exception as e:
            error_msg = f"HTTP Error: {e}"
            logger.error(error_msg)
            return f"[ERROR] {error_msg}"

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()


async def run_scenario(scenario_file: str, use_real_api: bool = False, verbose: bool = True) -> bool:
    """Run a test scenario."""
    with open(scenario_file, 'r') as f:
        scenario = json.load(f)
    
    logger.info(f"\n{'#'*80}")
    logger.info(f"SCENARIO: {scenario.get('name', 'Unnamed')}")
    logger.info(f"Mode: {'REAL API (HTTP)' if use_real_api else 'MOCK'}")
    logger.info(f"{'#'*80}\n")
    
    # Create appropriate tester
    if use_real_api:
        tester = HTTPAgentTester()
        # Check server
        try:
            health = await tester.client.get(f"{tester.base_url}/health")
            health.raise_for_status()
            logger.info("✅ Server is running\n")
        except:
            logger.error("❌ Server not running. Start with: poetry run python -m data_orchestration_agent.main")
            return False
    else:
        tester = MockAgentTester()
    
    # Run steps
    for i, step in enumerate(scenario.get('steps', []), 1):
        logger.info(f"\n{'#'*80}")
        logger.info(f"STEP {i}: {step.get('description', 'No description')}")
        logger.info(f"{'#'*80}")
        
        response = await tester.send_message(step['message'], verbose=verbose)
        
        # Simple assertion checking
        if 'assertions' in step:
            for assertion in step['assertions']:
                if assertion['type'] == 'contains':
                    if assertion['value'].lower() in response.lower():
                        logger.info(f"✅ Assertion passed: contains '{assertion['value']}'")
                    else:
                        logger.warning(f"⚠️  Assertion failed: missing '{assertion['value']}'")
        
        if 'wait' in step:
            await asyncio.sleep(step['wait'])
    
    # Summary
    logger.info(f"\n{'='*80}")
    logger.info(f"Total interactions: {len(tester.history)}")
    logger.info(f"{'='*80}\n")
    
    if use_real_api:
        await tester.close()
    
    return True


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="CLI test runner for orchestration agent")
    parser.add_argument('--scenario', '-s', type=str, required=True, help='Scenario JSON file')
    parser.add_argument('--real-api', '-r', action='store_true', help='Use real API (requires server running)')
    parser.add_argument('--quiet', '-q', action='store_true', help='Reduce verbosity')
    
    args = parser.parse_args()
    
    success = asyncio.run(run_scenario(args.scenario, args.real_api, not args.quiet))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

