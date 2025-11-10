"""Adapters to convert ADK tools to LangChain tools for LangGraph usage."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class MockToolContext:
    """Mock ToolContext for adapting ADK tools to LangChain.

    This provides a minimal implementation of ADK's ToolContext interface
    so existing tools can be called from LangGraph nodes.
    """

    def __init__(self, state: dict[str, Any]):
        """Initialize mock context with state.

        Args:
            state: LangGraph state dictionary
        """
        self.state = state
        self.session = MockSession(state)
        self.actions = MockActions()


class MockSession:
    """Mock session object that wraps LangGraph state."""

    def __init__(self, state: dict[str, Any]):
        """Initialize mock session.

        Args:
            state: LangGraph state dictionary
        """
        self.state = state


class MockActions:
    """Mock actions object for agent transfers."""

    def __init__(self):
        """Initialize mock actions."""
        self.transfer_to_agent = None

