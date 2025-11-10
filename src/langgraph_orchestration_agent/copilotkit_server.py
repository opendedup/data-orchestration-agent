"""CopilotKit AG-UI server for LangGraph orchestration agent.

This module provides AG-UI integration for the LangGraph implementation,
making it compatible with CopilotKit frontend clients.
"""

import logging
from copy import deepcopy
from typing import Any, AsyncIterator
from uuid import uuid4

from ag_ui.core import (
    RunAgentInput,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    RunErrorEvent,
    StateSnapshotEvent,
)
from ag_ui.encoder import EventEncoder
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage

from .agui_adapter import LangGraphAGUIAdapter
from .config import Config
from .graph import create_graph, stream_graph

logger = logging.getLogger(__name__)


def create_copilotkit_app(config: Config, clients: dict[str, Any]) -> FastAPI:
    """Create and configure FastAPI application with CopilotKit AG-UI.

    Uses the ag_ui_adk package to wrap the LangGraph agent with full AG-UI
    protocol support including streaming, state management, and frontend
    synchronization.

    Args:
        config: Application configuration
        clients: Dictionary of MCP clients (discovery, query_gen, graphql)

    Returns:
        Configured FastAPI application with AG-UI endpoints
    """
    logger.info("Initializing CopilotKit AG-UI server for LangGraph")

    # Create the LangGraph state graph
    graph_app = create_graph(config, clients)
    logger.info("LangGraph orchestration graph compiled")

    # Create the AG-UI adapter that bridges LangGraph to ADK interface
    langgraph_adapter = LangGraphAGUIAdapter(
        graph_app=graph_app,
        app_name="langgraph_orchestration_agent",
        model=config.agent_model,
    )
    logger.info("LangGraph AG-UI adapter created")

    # Create FastAPI app
    app = FastAPI(
        title="LangGraph Orchestration Agent - CopilotKit",
        description="AG-UI compatible LangGraph server using CopilotKit SDK",
        version="2.0.0",
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
    async def health_check() -> dict[str, str]:
        """Health check endpoint for container orchestration.

        Returns:
            Dictionary with status and service information
        """
        return {
            "status": "healthy",
            "service": "langgraph-orchestration-agent-copilotkit",
            "transport": "http",
        }

    session_states: dict[str, dict[str, Any]] = {}

    def build_shared_state(state: dict[str, Any]) -> dict[str, Any]:
        """Extract frontend-facing state from the LangGraph session state."""

        return deepcopy(
            {
                "user:current_mode": state.get("current_mode", "ask"),
                "user:queries": state.get("queries", []),
                "user:datasets": state.get("datasets", {}),
                "user:query_results": state.get("query_results", []),
                "user:last_search_results": state.get("last_search_results"),
                "user:planning": {
                    "qa_history": state.get("planning_qa_history", []),
                    "discovered_datasets": state.get("planning_discovered_datasets", {}),
                    "datasets_confirmed": state.get("planning_datasets_confirmed", False),
                    "intent_confirmed": state.get("planning_intent_confirmed", False),
                    "prp_generated": state.get("planning_prp_generated", False),
                },
            }
        )

    def extract_user_input(messages: list[Any]) -> str:
        """Return the latest user message content from the conversation."""

        for message in reversed(messages):
            if message.role == "user":
                content = message.content
                if isinstance(content, list):
                    return " ".join(
                        item.text for item in content if getattr(item, "type", "") == "text"
                    )
                return content or ""
        return ""

    @app.post("/run")
    async def run_agent(input_data: RunAgentInput) -> StreamingResponse:
        """Execute a LangGraph run and stream AG-UI protocol events."""

        thread_id = input_data.thread_id
        run_id = input_data.run_id
        parent_run_id = input_data.parent_run_id
        user_input = extract_user_input(input_data.messages)
        encoder = EventEncoder()
        message_id = str(uuid4())

        # Extract selectedDatasets from context
        selected_datasets: list[str] = []
        for ctx in input_data.context:
            if ctx.key == "selectedDatasets" and isinstance(ctx.value, list):
                selected_datasets = ctx.value
                break

        async def event_stream() -> AsyncIterator[bytes]:
            previous_state = session_states.get(thread_id)
            if previous_state is None:
                previous_state = langgraph_adapter.create_initial_state()
            previous_state_snapshot = deepcopy(previous_state)
            
            # Inject selected datasets into state
            state_with_context = deepcopy(previous_state)
            if selected_datasets:
                state_with_context["selected_datasets"] = selected_datasets

            yield encoder.encode(
                RunStartedEvent(
                    threadId=thread_id,
                    runId=run_id,
                    parentRunId=parent_run_id,
                    input=input_data,
                )
            )

            yield encoder.encode(
                StateSnapshotEvent(
                    snapshot={
                        "session_id": thread_id,
                        "message_id": message_id,
                        **build_shared_state(previous_state),
                    },
                )
            )

            updated_state: dict[str, Any] | None = None

            try:
                async for graph_event in stream_graph(
                    graph_app,
                    user_input,
                    state_with_context,
                    thread_id=thread_id,
                ):
                    # Handle interrupt event
                    if graph_event.event_type == "interrupt":
                        interrupt_data = graph_event.payload.get("interrupt", [])
                        logger.info(f"[INTERRUPT] Detected in stream: {interrupt_data}")
                        
                        # Emit state snapshot with interrupt information
                        yield encoder.encode(StateSnapshotEvent(
                            snapshot={
                                "session_id": thread_id,
                                "message_id": message_id,
                                "interrupted": True,
                                "interrupt_payload": interrupt_data,
                                **build_shared_state(graph_event.state)
                            }
                        ))
                        
                        # Store interrupted state in session
                        session_states[thread_id] = graph_event.state
                        
                        # Emit run finished event
                        yield encoder.encode(RunFinishedEvent(
                            threadId=thread_id,
                            runId=run_id,
                            result=build_shared_state(graph_event.state)
                        ))
                        
                        logger.info("Graph execution interrupted - waiting for user response")
                        break
                    
                    # Handle state update events
                    if graph_event.event_type == "state_update":
                        snapshot = {
                            "session_id": thread_id,
                            "message_id": message_id,
                            "event_type": graph_event.event_type,
                            **build_shared_state(graph_event.state),
                        }
                        yield encoder.encode(StateSnapshotEvent(snapshot=snapshot))
                    
                    # Handle final state
                    if graph_event.event_type == "final_state":
                        updated_state = graph_event.state
                        session_states[thread_id] = updated_state

                        # Check if there are any messages and if the last one is from assistant
                        current_messages = updated_state.get("messages", [])
                        logger.info(f"Final state has {len(current_messages)} messages")
                        
                        if current_messages and len(current_messages) > 0:
                            last_message = current_messages[-1]
                            logger.info(f"Last message type: {type(last_message).__name__}")
                            
                            # Check if it's an AIMessage with content
                            if isinstance(last_message, AIMessage):
                                content = last_message.content
                                if isinstance(content, list):
                                    # Handle list content (join parts)
                                    text_content = " ".join(str(chunk).strip() for chunk in content)
                                else:
                                    # Handle string content
                                    text_content = str(content).strip() if content else ""
                                
                                logger.info(f"AI message content length: {len(text_content)}")
                                
                                # Only emit message if there's actual content
                                if text_content:
                                    logger.info("Emitting AI response to client")
                                    assistant_message_id = str(uuid4())
                                    yield encoder.encode(
                                        TextMessageStartEvent(
                                            messageId=assistant_message_id,
                                            role="assistant",
                                        )
                                    )
                                    yield encoder.encode(
                                        TextMessageContentEvent(
                                            messageId=assistant_message_id,
                                            delta=text_content,
                                        )
                                    )
                                    yield encoder.encode(TextMessageEndEvent(messageId=assistant_message_id))
                                else:
                                    logger.warning("Last AI message has no content")
                            else:
                                logger.debug(f"Last message is not AIMessage: {type(last_message)}")
                        else:
                            logger.warning("No messages in final state")

                        yield encoder.encode(
                            RunFinishedEvent(
                                threadId=thread_id,
                                runId=run_id,
                                result=build_shared_state(updated_state),
                            )
                        )
                        break
            except Exception as exc:  # pragma: no cover - runtime safety
                logger.exception("Error during LangGraph execution")
                yield encoder.encode(RunErrorEvent(message=str(exc)))

            finally:
                # Ensure session state is persisted even if there is no AI response.
                session_states.setdefault(thread_id, previous_state_snapshot)

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    app.post("/")(run_agent)

    logger.info("LangGraph AG-UI streaming endpoint registered")
    logger.info("Server will run on %s:%s", config.agent_host, config.agent_port)

    return app

