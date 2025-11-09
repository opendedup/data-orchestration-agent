"""CopilotKit AG-UI server using standard ag_ui_adk package.

This module provides AG-UI integration using the official CopilotKit SDK,
replacing the custom implementation with a standardized approach.
"""

import logging
from typing import Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint

from .agent import root_agent
from .config import Config

logger = logging.getLogger(__name__)


def create_copilotkit_app(config: Config) -> FastAPI:
    """Create and configure FastAPI application with CopilotKit AG-UI.

    Uses the official ag_ui_adk package to wrap the existing ADK agent
    with full AG-UI protocol support including streaming, state management,
    and frontend synchronization.

    Args:
        config: Application configuration

    Returns:
        Configured FastAPI application with AG-UI endpoints
    """
    logger.info("Initializing CopilotKit AG-UI server")

    # Create ADK middleware agent instance
    # This wraps our existing root_agent with AG-UI protocol support
    adk_agent = ADKAgent(
        adk_agent=root_agent,
        app_name="data_orchestration_agent",
        user_id="default_user",  # Can be overridden per request
        session_timeout_seconds=3600,
        use_in_memory_services=True,
    )

    logger.info("ADK agent wrapped with CopilotKit middleware")

    # Create FastAPI app
    app = FastAPI(
        title="Data Orchestration Agent - CopilotKit",
        description="AG-UI compatible server using official CopilotKit SDK",
        version="1.0.0",
    )

    # Configure CORS for frontend access
    if config.enable_cors:
        logger.info("CORS enabled for all origins (development mode)")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Allow all origins in development
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        logger.info("CORS disabled (production mode)")

    # Add health endpoint
    @app.get("/health")
    async def health_check() -> Dict[str, str]:
        """Health check endpoint for container orchestration.

        Returns:
            Dictionary with status and service information
        """
        return {
            "status": "healthy",
            "service": "data-orchestration-agent-copilotkit",
            "transport": "http",
        }

    # Add the ADK endpoint - this automatically adds all AG-UI protocol endpoints:
    # - WebSocket endpoint for bidirectional communication
    # - State synchronization
    # - Streaming responses
    # - Tool execution
    # All handled by CopilotKit!
    add_adk_fastapi_endpoint(app, adk_agent, path="/")

    logger.info(
        "CopilotKit AG-UI endpoints added - streaming, state sync, and protocol support enabled"
    )
    logger.info(f"Server will run on {config.agent_host}:{config.agent_port}")

    return app

