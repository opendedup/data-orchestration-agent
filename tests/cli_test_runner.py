"""Command-line test runner for orchestration agent scenarios."""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

# Google GenAI imports removed - using ADK's native agent execution

if TYPE_CHECKING:
    from data_orchestration_agent.agents.root_agent import Agent

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


class AgentTester:
    """Interactive command-line tester for the orchestration agent."""

    def __init__(
        self,
        agent: "Agent",
        session_id: str = "test-session"
    ) -> None:
        """Initialize the agent tester.
        
        Args:
            agent: The orchestration agent instance
            session_id: Session identifier for the test
        """
        self.agent = agent
        self.session_id = session_id
        self.history: List[Dict[str, Any]] = []

    async def send_message(self, message: str, verbose: bool = True) -> str:
        """Send a message to the agent and get response using real API calls.
        
        Args:
            message: User message to send
            verbose: Whether to print detailed output
            
        Returns:
            Agent's text response
        """
        if verbose:
            logger.info(f"\n{'='*80}")
            logger.info(f"USER: {message}")
            logger.info(f"{'='*80}\n")
        
        # Use ADK's native agent execution for real API calls
        try:
            # Execute the agent with the user message (returns async generator for streaming)
            response_stream = self.agent.run_async(message)
            
            # Collect the streamed response
            final_response = ""
            tool_calls: List[Dict[str, Any]] = []
            
            async for chunk in response_stream:
                # Extract text from each chunk
                if hasattr(chunk, 'text') and chunk.text:
                    final_response += chunk.text
                elif hasattr(chunk, 'content') and chunk.content:
                    final_response += chunk.content
                elif isinstance(chunk, str):
                    final_response += chunk
                    
                # Track tool calls if available in chunk
                if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                    for tool_call in chunk.tool_calls:
                        tool_name = tool_call.name if hasattr(tool_call, 'name') else str(tool_call)
                        tool_args = tool_call.args if hasattr(tool_call, 'args') else {}
                        
                        # Only add if not already tracked
                        if not any(tc['name'] == tool_name for tc in tool_calls):
                            tool_calls.append({
                                "name": tool_name,
                                "arguments": tool_args
                            })
                            
                            if verbose:
                                logger.info(f"🔧 TOOL CALL: {tool_name}")
                                logger.info(f"   Arguments: {json.dumps(tool_args, indent=2, default=str)}\n")
            
            if verbose:
                logger.info(f"AGENT: {final_response}\n")
            
            # Store in history
            self.history.append({
                "user": message,
                "agent": final_response,
                "tool_calls": tool_calls
            })
            
            return final_response
            
        except Exception as e:
            error_msg = f"Error executing agent: {e}"
            logger.error(error_msg, exc_info=True)
            
            # Store error in history
            self.history.append({
                "user": message,
                "agent": f"[ERROR] {error_msg}",
                "tool_calls": []
            })
            
            return f"[ERROR] {error_msg}"

    def print_summary(self) -> None:
        """Print a summary of the test conversation."""
        logger.info(f"\n{'='*80}")
        logger.info("TEST SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"Total interactions: {len(self.history)}")
        logger.info(f"Total tool calls: {sum(len(h['tool_calls']) for h in self.history)}")
        
        tool_counts: Dict[str, int] = {}
        for interaction in self.history:
            for tool_call in interaction['tool_calls']:
                tool_name = tool_call['name']
                tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
        
        if tool_counts:
            logger.info("\nTool usage:")
            for tool_name, count in sorted(tool_counts.items()):
                logger.info(f"  - {tool_name}: {count}x")
        
        logger.info(f"{'='*80}\n")

    def export_history(self, output_file: str) -> None:
        """Export conversation history to JSON file.
        
        Args:
            output_file: Path to output file
        """
        with open(output_file, 'w') as f:
            json.dump(self.history, f, indent=2)
        logger.info(f"History exported to {output_file}")


async def run_scenario(scenario_file: str, verbose: bool = True) -> bool:
    """Run a test scenario from a JSON file.
    
    Args:
        scenario_file: Path to scenario JSON file
        verbose: Whether to print detailed output
        
    Returns:
        True if all assertions passed, False otherwise
    """
    # Load scenario
    with open(scenario_file, 'r') as f:
        scenario = json.load(f)
    
    logger.info(f"\n{'#'*80}")
    logger.info(f"SCENARIO: {scenario.get('name', 'Unnamed')}")
    logger.info(f"Description: {scenario.get('description', 'No description')}")
    logger.info(f"{'#'*80}\n")
    
    # Initialize clients and agent
    config = load_config()
    
    discovery_client = DiscoveryClient(
        config.discovery_agent_url,
        timeout=config.http_timeout
    )
    query_gen_client = QueryGenClient(
        config.query_gen_agent_url,
        timeout=config.http_timeout
    )
    graphql_client = GraphQLClient(
        config.graphql_agent_url,
        timeout=config.http_timeout
    )
    apollo_mcp_client = ApolloMCPClient(
        config.apollo_mcp_url,
        timeout=config.http_timeout
    )
    bigquery_agent = create_bigquery_agent(config)
    
    agent = create_orchestration_agent(
        config=config,
        discovery_client=discovery_client,
        query_gen_client=query_gen_client,
        graphql_client=graphql_client,
        apollo_mcp_client=apollo_mcp_client,
        bigquery_agent=bigquery_agent,
    )
    
    # Create tester
    session_id = scenario.get('session_id', 'test-session')
    tester = AgentTester(agent, session_id=session_id)
    
    all_assertions_passed = True
    
    # Run steps
    for i, step in enumerate(scenario.get('steps', []), 1):
        logger.info(f"\n{'#'*80}")
        logger.info(f"STEP {i}: {step.get('description', 'No description')}")
        logger.info(f"{'#'*80}")
        
        response = await tester.send_message(step['message'], verbose=verbose)
        
        # Check assertions if present
        if 'assertions' in step:
            for assertion in step['assertions']:
                if assertion['type'] == 'contains':
                    expected = assertion['value']
                    if expected.lower() not in response.lower():
                        logger.warning(
                            f"⚠️  Assertion failed: Expected response to contain '{expected}'"
                        )
                        all_assertions_passed = False
                    else:
                        logger.info(f"✅ Assertion passed: Response contains '{expected}'")
                elif assertion['type'] == 'tool_called':
                    tool_name = assertion['value']
                    # Check if tool was called in the last interaction
                    last_interaction = tester.history[-1]
                    tool_names = [tc['name'] for tc in last_interaction['tool_calls']]
                    if tool_name not in tool_names:
                        logger.warning(
                            f"⚠️  Assertion failed: Expected tool '{tool_name}' to be called"
                        )
                        all_assertions_passed = False
                    else:
                        logger.info(f"✅ Assertion passed: Tool '{tool_name}' was called")
        
        # Wait between steps if specified
        if 'wait' in step:
            await asyncio.sleep(step['wait'])
    
    # Print summary
    tester.print_summary()
    
    # Export history if specified
    if 'export_history' in scenario:
        tester.export_history(scenario['export_history'])
    
    # Cleanup
    await discovery_client.close()
    await query_gen_client.close()
    await graphql_client.close()
    await apollo_mcp_client.close()
    
    return all_assertions_passed


async def interactive_mode() -> None:
    """Run in interactive CLI mode."""
    logger.info("Starting interactive mode...")
    
    # Initialize
    config = load_config()
    
    discovery_client = DiscoveryClient(
        config.discovery_agent_url,
        timeout=config.http_timeout
    )
    query_gen_client = QueryGenClient(
        config.query_gen_agent_url,
        timeout=config.http_timeout
    )
    graphql_client = GraphQLClient(
        config.graphql_agent_url,
        timeout=config.http_timeout
    )
    apollo_mcp_client = ApolloMCPClient(
        config.apollo_mcp_url,
        timeout=config.http_timeout
    )
    bigquery_agent = create_bigquery_agent(config)
    
    agent = create_orchestration_agent(
        config=config,
        discovery_client=discovery_client,
        query_gen_client=query_gen_client,
        graphql_client=graphql_client,
        apollo_mcp_client=apollo_mcp_client,
        bigquery_agent=bigquery_agent,
    )
    
    tester = AgentTester(agent)
    
    logger.info("\n✨ Interactive Agent Testing Mode")
    logger.info("Commands:")
    logger.info("  - Type your message to chat with the agent")
    logger.info("  - 'exit' or 'quit': End the session")
    logger.info("  - 'summary': See conversation summary")
    logger.info("  - 'export <filename>': Export history to JSON")
    logger.info("  - 'clear': Clear conversation history\n")
    
    while True:
        try:
            user_input = input("\n💬 You: ").strip()
            
            if user_input.lower() in ['exit', 'quit']:
                logger.info("Exiting interactive mode...")
                break
            elif user_input.lower() == 'summary':
                tester.print_summary()
                continue
            elif user_input.lower().startswith('export '):
                filename = user_input.split(' ', 1)[1]
                tester.export_history(filename)
                continue
            elif user_input.lower() == 'clear':
                tester.history.clear()
                logger.info("✅ Conversation history cleared")
                continue
            elif not user_input:
                continue
            
            await tester.send_message(user_input)
            
        except KeyboardInterrupt:
            logger.info("\n\nInterrupted by user. Exiting...")
            break
        except EOFError:
            logger.info("\n\nEOF received. Exiting...")
            break
        except Exception as e:
            logger.error(f"❌ Error: {e}", exc_info=True)
    
    tester.print_summary()
    
    # Cleanup
    await discovery_client.close()
    await query_gen_client.close()
    await graphql_client.close()
    await apollo_mcp_client.close()


def main() -> None:
    """Main entry point for CLI test runner."""
    parser = argparse.ArgumentParser(
        description="Command-line test runner for data orchestration agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run in interactive mode
  python cli_test_runner.py --interactive
  
  # Run a scenario
  python cli_test_runner.py --scenario scenarios/nfl_backtest_scenario.json
  
  # Run quietly (less verbose)
  python cli_test_runner.py --scenario scenarios/nfl_backtest_scenario.json --quiet
        """
    )
    parser.add_argument(
        '--scenario',
        '-s',
        type=str,
        help='Path to scenario JSON file'
    )
    parser.add_argument(
        '--interactive',
        '-i',
        action='store_true',
        help='Run in interactive mode'
    )
    parser.add_argument(
        '--quiet',
        '-q',
        action='store_true',
        help='Reduce output verbosity'
    )
    
    args = parser.parse_args()
    
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    try:
        if args.interactive:
            asyncio.run(interactive_mode())
        elif args.scenario:
            success = asyncio.run(run_scenario(args.scenario, verbose=not args.quiet))
            sys.exit(0 if success else 1)
        else:
            parser.print_help()
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

