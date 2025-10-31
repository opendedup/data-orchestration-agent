"""Main entry point for the Data Orchestration Agent."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from google.genai import Client, types
from pydantic import BaseModel

from .agents.bigquery_agent import create_bigquery_agent
from .agents.root_agent import create_orchestration_agent
from .clients import (
    ApolloMCPClient,
    DiscoveryClient,
    GraphQLClient,
    PlanningClient,
    QueryGenClient,
)
from .config import load_config
from .utils import SessionState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Global state
agent_instance = None
genai_client = None


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    
    session_id: str
    message: str


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    
    session_id: str
    response: str
    tool_calls: List[Dict[str, Any]] = []


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle.
    
    Args:
        app: FastAPI application instance
        
    Yields:
        None
    """
    global agent_instance, genai_client
    
    # Load configuration
    logger.info("Loading configuration...")
    config = load_config()
    
    # Initialize Google GenAI client
    logger.info("Initializing Google GenAI client...")
    genai_client = Client(api_key=os.getenv("GOOGLE_API_KEY"))
    
    # Initialize MCP clients
    logger.info("Initializing MCP clients...")
    discovery_client = DiscoveryClient(
        config.discovery_agent_url,
        timeout=config.http_timeout
    )
    query_gen_client = QueryGenClient(
        config.query_gen_agent_url,
        timeout=config.http_timeout
    )
    planning_client = PlanningClient(
        config.planning_agent_url,
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
    
    # Create BigQuery sub-agent
    logger.info("Creating BigQuery sub-agent...")
    bigquery_agent = create_bigquery_agent(config)
    
    # Create orchestration agent
    logger.info("Creating orchestration agent...")
    agent_instance = create_orchestration_agent(
        config=config,
        discovery_client=discovery_client,
        query_gen_client=query_gen_client,
        planning_client=planning_client,
        graphql_client=graphql_client,
        apollo_mcp_client=apollo_mcp_client,
        bigquery_agent=bigquery_agent,
    )
    
    logger.info("Orchestration agent ready!")
    
    yield
    
    # Cleanup
    logger.info("Shutting down...")
    await discovery_client.close()
    await query_gen_client.close()
    await planning_client.close()
    await graphql_client.close()
    await apollo_mcp_client.close()


# Create FastAPI app
app = FastAPI(
    title="Data Orchestration Agent",
    description="Root agent for data discovery, planning, and product creation",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint.
    
    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "service": "data-orchestration-agent",
        "transport": "http"
    }


@app.get("/")
async def root(request: Request) -> Dict[str, Any]:
    """Root endpoint with service information.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Service information
    """
    # Check for SSE request
    accept = request.headers.get("accept", "")
    if "text/event-stream" in accept:
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream"
        )
    
    return {
        "service": "data-orchestration-agent",
        "version": "0.1.0",
        "modes": ["ask", "planning", "action"],
        "endpoints": [
            "/health",
            "/chat",
            "/session/{session_id}",
            "/session/{session_id}/state"
        ]
    }


async def event_stream() -> AsyncGenerator[str, None]:
    """Server-Sent Events stream.
    
    Yields:
        SSE formatted messages
    """
    yield "event: message\n"
    yield "data: {\"type\": \"connected\", \"service\": \"data-orchestration-agent\"}\n\n"


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat endpoint for interacting with the agent.
    
    Args:
        request: Chat request with session ID and message
        
    Returns:
        Agent response
        
    Raises:
        HTTPException: If agent is not initialized or error occurs
    """
    if not agent_instance or not genai_client:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        # Get session state
        session_state = agent_instance.get_session_state(request.session_id)
        
        # Create chat with history
        chat = genai_client.chats.create(
            model=agent_instance.config.agent_model,
            config=types.GenerateContentConfig(
                system_instruction=agent_instance.instruction,
                tools=agent_instance.tools,
                temperature=0.7,
            )
        )
        
        # Send user message
        response = await chat.send_message_async(request.message)
        
        # Handle tool calls
        tool_calls = []
        while response.candidates[0].content.parts:
            part = response.candidates[0].content.parts[0]
            
            # Check if it's a function call
            if hasattr(part, 'function_call') and part.function_call:
                function_call = part.function_call
                function_name = function_call.name
                arguments = dict(function_call.args) if function_call.args else {}
                
                logger.info(f"Tool call: {function_name}({arguments})")
                tool_calls.append({
                    "name": function_name,
                    "arguments": arguments
                })
                
                # Execute tool
                result = await agent_instance.handle_function_call(
                    function_name,
                    arguments,
                    session_state
                )
                
                # Send function response back
                response = await chat.send_message_async(
                    types.Part.from_function_response(
                        name=function_name,
                        response={"result": result}
                    )
                )
            else:
                # Text response
                break
        
        # Extract final text response
        final_response = ""
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    final_response += part.text
        
        return ChatResponse(
            session_id=request.session_id,
            response=final_response,
            tool_calls=tool_calls
        )
        
    except Exception as e:
        logger.error(f"Error processing chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session/{session_id}")
async def get_session(session_id: str) -> Dict[str, Any]:
    """Get session information.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Session information
        
    Raises:
        HTTPException: If agent is not initialized
    """
    if not agent_instance:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    session_state = agent_instance.get_session_state(session_id)
    
    return {
        "session_id": session_id,
        "exists": session_id in agent_instance.sessions,
        "state_keys": list(session_state.keys())
    }


@app.get("/session/{session_id}/state")
async def get_session_state(session_id: str) -> SessionState:
    """Get session state.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Session state dictionary
        
    Raises:
        HTTPException: If agent is not initialized
    """
    if not agent_instance:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    return agent_instance.get_session_state(session_id)


@app.delete("/session/{session_id}")
async def delete_session(session_id: str) -> Dict[str, str]:
    """Delete a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Deletion status
        
    Raises:
        HTTPException: If agent is not initialized or session not found
    """
    if not agent_instance:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    if session_id not in agent_instance.sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    del agent_instance.sessions[session_id]
    
    return {"status": "deleted", "session_id": session_id}


def main() -> None:
    """Start the orchestration agent web server."""
    import uvicorn
    
    config = load_config()
    
    logger.info(f"Starting Data Orchestration Agent on {config.agent_host}:{config.agent_port}")
    
    uvicorn.run(
        app,
        host=config.agent_host,
        port=config.agent_port,
        log_level="info"
    )


if __name__ == "__main__":
    main()

