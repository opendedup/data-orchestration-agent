"""FastAPI server with CopilotKit AG-UI integration for LangGraph agent."""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage

from data_orchestration_agent.clients import (
    DiscoveryClient,
    GraphQLClient,
    QueryGenClient,
)

from .config import Config
from .graph import create_graph, run_graph

logger = logging.getLogger(__name__)


def create_app(config: Config) -> FastAPI:
    """Create and configure FastAPI application with LangGraph agent.

    Args:
        config: Application configuration

    Returns:
        Configured FastAPI application
    """
    logger.info("Initializing LangGraph orchestration server")

    # Initialize MCP clients
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

    clients = {
        "discovery": discovery_client,
        "query_gen": query_gen_client,
        "graphql": graphql_client,
    }

    # Create LangGraph app
    graph_app = create_graph(config, clients)

    # Store session states (in production, use Redis or database)
    session_states: dict[str, dict[str, Any]] = {}

    # Create FastAPI app
    app = FastAPI(
        title="LangGraph Orchestration Agent",
        description="LangGraph-based orchestration agent with AG-UI support",
        version="0.1.0",
    )

    # Configure CORS
    if config.enable_cors:
        logger.info("CORS enabled for all origins (development mode)")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": "langgraph-orchestration-agent",
            "transport": "http",
        }

    @app.post("/chat")
    async def chat(request: Request) -> dict[str, Any]:
        """Chat endpoint for processing messages.

        Expected request body:
        {
            "message": "user message",
            "session_id": "optional session id"
        }
        """
        body = await request.json()
        user_message = body.get("message", "")
        session_id = body.get("session_id", "default")

        logger.info(f"Received message for session {session_id}: {user_message[:100]}")

        # Get or create session state
        state = session_states.get(session_id)

        # Run graph
        result = run_graph(graph_app, user_message, state)

        # Update session state
        session_states[session_id] = result

        # Get the last AI message
        messages = result.get("messages", [])
        ai_messages = [m for m in messages if isinstance(m, AIMessage)]
        last_response = ai_messages[-1].content if ai_messages else "No response"

        return {
            "response": last_response,
            "session_id": session_id,
            "current_mode": result.get("current_mode", "ask"),
        }

    @app.post("/chat/stream")
    async def chat_stream(request: Request) -> StreamingResponse:
        """Streaming chat endpoint for real-time responses."""
        body = await request.json()
        user_message = body.get("message", "")
        session_id = body.get("session_id", "default")

        async def generate() -> AsyncIterator[str]:
            """Generate streaming response."""
            # Get or create session state
            state = session_states.get(session_id)

            # Run graph
            result = run_graph(graph_app, user_message, state)

            # Update session state
            session_states[session_id] = result

            # Get the last AI message
            messages = result.get("messages", [])
            ai_messages = [m for m in messages if isinstance(m, AIMessage)]
            last_response = ai_messages[-1].content if ai_messages else "No response"

            # Stream response in chunks
            words = last_response.split()
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            yield f"data: {json.dumps({'done': True})}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.delete("/session/{session_id}")
    async def clear_session(session_id: str) -> dict[str, str]:
        """Clear a session's state."""
        if session_id in session_states:
            del session_states[session_id]
            return {"status": "cleared", "session_id": session_id}
        return {"status": "not_found", "session_id": session_id}

    @app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint."""
        return {
            "service": "langgraph-orchestration-agent",
            "version": "0.1.0",
            "status": "running",
        }

    logger.info(f"Server configured on {config.agent_host}:{config.agent_port}")

    return app

