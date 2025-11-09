"""Main entry point for CopilotKit AG-UI server.

Command-line interface for starting the Data Orchestration Agent using
the official CopilotKit SDK for AG-UI protocol support.
"""

import argparse
import logging
import sys

import uvicorn

from .copilotkit_server import create_copilotkit_app
from .config import load_config

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the application.

    Args:
        verbose: Enable verbose (DEBUG) logging
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main() -> None:
    """Main entry point for AG-UI server."""
    parser = argparse.ArgumentParser(
        description="Data Orchestration Agent - AG-UI Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start server with defaults
  python -m data_orchestration_agent.main

  # Start on custom port
  python -m data_orchestration_agent.main --port 8080

  # Start with verbose logging
  python -m data_orchestration_agent.main --verbose

  # Enable auto-reload for development
  python -m data_orchestration_agent.main --reload
        """,
    )

    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host address to bind to (default: from config or 0.0.0.0)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port number to listen on (default: from config or 8085)",
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose)

    logger.info("Starting Data Orchestration Agent with CopilotKit AG-UI")

    try:
        # Load configuration
        config = load_config()
        logger.info("Configuration loaded successfully")

        # Use CLI arguments or fall back to config
        host = args.host if args.host is not None else config.agent_host
        port = args.port if args.port is not None else config.agent_port

        logger.info(f"Server configuration: host={host}, port={port}")
        logger.info(f"Model: {config.agent_model}")

        # Create FastAPI app with CopilotKit
        app = create_copilotkit_app(config)

        # Log MCP service connections
        logger.info(f"Discovery Agent: {config.discovery_agent_url}")
        logger.info(f"Query Gen Agent: {config.query_gen_agent_url}")
        logger.info(f"GraphQL Agent: {config.graphql_agent_url}")
        logger.info(f"Apollo MCP: {config.apollo_mcp_url}")

        # Run server
        logger.info(f"Starting server on http://{host}:{port}")
        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=args.reload,
            log_level="debug" if args.verbose else "info",
        )

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

