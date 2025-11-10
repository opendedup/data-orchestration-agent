"""AG-UI adapter for LangGraph orchestration agent.

This module provides a bridge between LangGraph's StateGraph and CopilotKit's AG-UI protocol,
enabling the LangGraph implementation to work with CopilotKit frontend clients.
"""

import logging
from copy import deepcopy
from typing import Any

from google.genai.types import GenerateContentConfig, Part
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph

logger = logging.getLogger(__name__)


class LangGraphAGUIAdapter:
    """Adapter that makes a LangGraph StateGraph compatible with AG-UI protocol.
    
    This adapter wraps a LangGraph compiled graph and provides the interface
    expected by ag_ui_adk.ADKAgent, allowing LangGraph agents to be used
    with CopilotKit's AG-UI integration.
    """

    def __init__(
        self,
        graph_app: StateGraph,
        app_name: str = "langgraph_orchestration_agent",
        model: str = "gemini-2.5-flash",
        agent_id: str | None = None,
        description: str = "",
        thread_id: str | None = None,
        tools: list[Any] | None = None,
        instruction: str | None = None,
        **extra: Any,
    ):
        """Initialize the adapter.

        Args:
            graph_app: Compiled LangGraph StateGraph.
            app_name: Name of the agent application.
            model: Model name for compatibility with ADK interface.
            agent_id: Optional identifier for the agent instance.
            description: Optional human-readable description.
            thread_id: Optional thread identifier used by AG-UI sessions.
            tools: Optional tool metadata list expected by CopilotKit.
            instruction: Optional system prompt or instruction text.
            extra: Additional metadata forwarded by ADKAgent.
        """
        self.graph_app = graph_app
        self.app_name = app_name
        self.model = model
        self.agent_id = agent_id
        self.description = description
        self.thread_id = thread_id
        self.tools: list[Any] = list(tools) if tools is not None else []
        self.instruction = instruction
        self.extra: dict[str, Any] = dict(extra)
        logger.info("LangGraph AG-UI adapter initialized for %s", app_name)

    def model_copy(
        self,
        *,
        update: dict[str, Any] | None = None,
        deep: bool = False,
    ) -> "LangGraphAGUIAdapter":
        """Provide a Pydantic-compatible copy operation used by ADKAgent."""
        base_tools = deepcopy(self.tools) if deep else list(self.tools)
        extra_copy = deepcopy(self.extra) if deep else dict(self.extra)
        data: dict[str, Any] = {
            "graph_app": self.graph_app,
            "app_name": self.app_name,
            "model": self.model,
            "agent_id": deepcopy(self.agent_id) if deep else self.agent_id,
            "description": deepcopy(self.description) if deep else self.description,
            "thread_id": deepcopy(self.thread_id) if deep else self.thread_id,
            "tools": base_tools,
            "instruction": deepcopy(self.instruction) if deep else self.instruction,
        }
        data.update(extra_copy)
        if update:
            data.update(update)
        return LangGraphAGUIAdapter(**data)

    def model_dump(self) -> dict[str, Any]:
        """Return a dictionary representation similar to Pydantic's model_dump."""
        return {
            "graph_app": self.graph_app,
            "app_name": self.app_name,
            "model": self.model,
            "agent_id": self.agent_id,
            "description": self.description,
            "thread_id": self.thread_id,
            "tools": list(self.tools),
            "instruction": self.instruction,
            **self.extra,
        }

    def create_initial_state(self) -> dict[str, Any]:
        """Return a fresh initial LangGraph state for new sessions."""

        return deepcopy(self._extract_state_from_config(None))

    async def generate_content(
        self,
        contents: list[Part] | str,
        config: GenerateContentConfig | None = None,
    ) -> Any:
        """Generate content using the LangGraph agent.
        
        This method adapts the ADK-style generate_content interface to work with
        LangGraph's invoke pattern.
        
        Args:
            contents: Input content (message or parts)
            config: Generation config (optional, used for state context)
            
        Returns:
            Generated response from the agent
        """
        # Extract user message
        if isinstance(contents, str):
            user_input = contents
        elif isinstance(contents, list) and contents:
            # Extract text from parts
            user_input = " ".join(
                part.text if hasattr(part, "text") else str(part)
                for part in contents
            )
        else:
            user_input = ""

        logger.info(f"Processing message: {user_input[:100]}")

        # Get or initialize state from config
        state = self._extract_state_from_config(config)

        # Add user message to state
        user_message = HumanMessage(content=user_input)
        state["messages"] = state.get("messages", []) + [user_message]

        # Run the graph
        try:
            result = await self.graph_app.ainvoke(state)
            
            # Extract the last AI message
            messages = result.get("messages", [])
            ai_messages = [m for m in messages if isinstance(m, AIMessage)]
            
            if ai_messages:
                response_text = ai_messages[-1].content
            else:
                response_text = "No response generated"

            logger.info(f"Generated response: {response_text[:100]}")

            # Return a mock response object compatible with ADK
            return MockGenerateContentResponse(
                text=response_text,
                state=result,
            )

        except Exception as e:
            logger.error(f"Error generating content: {e}", exc_info=True)
            raise

    def _extract_state_from_config(self, config: GenerateContentConfig | None) -> dict[str, Any]:
        """Extract LangGraph state from ADK config.
        
        Args:
            config: ADK generation config that may contain state
            
        Returns:
            LangGraph state dictionary
        """
        if config and hasattr(config, "state"):
            return config.state
        
        # Return initial state
        return {
            "messages": [],
            "current_mode": "ask",
            "datasets": {},
            "queries": [],
            "query_results": [],
            "planning_qa_history": [],
            "planning_discovered_datasets": {},
            "planning_datasets_confirmed": False,
            "planning_intent_confirmed": False,
            "planning_prp_generated": False,
            "last_search_results": None,
        }


class MockGenerateContentResponse:
    """Mock response object compatible with ADK's GenerateContentResponse.
    
    This allows the LangGraph adapter to return responses in a format that
    ag_ui_adk can process.
    """

    def __init__(self, text: str, state: dict[str, Any]):
        """Initialize mock response.
        
        Args:
            text: Response text
            state: Updated agent state
        """
        self.text = text
        self.state = state
        self._candidates = [MockCandidate(text)]

    @property
    def candidates(self) -> list["MockCandidate"]:
        """Get response candidates."""
        return self._candidates


class MockCandidate:
    """Mock candidate object compatible with ADK."""

    def __init__(self, text: str):
        """Initialize mock candidate.
        
        Args:
            text: Candidate text
        """
        self._content = MockContent(text)

    @property
    def content(self) -> "MockContent":
        """Get candidate content."""
        return self._content


class MockContent:
    """Mock content object compatible with ADK."""

    def __init__(self, text: str):
        """Initialize mock content.
        
        Args:
            text: Content text
        """
        self._parts = [MockPart(text)]

    @property
    def parts(self) -> list["MockPart"]:
        """Get content parts."""
        return self._parts


class MockPart:
    """Mock part object compatible with ADK."""

    def __init__(self, text: str):
        """Initialize mock part.
        
        Args:
            text: Part text
        """
        self.text = text

