"""Data Orchestration Agent - Root agent for data discovery, planning, and product creation."""

__version__ = "0.1.0"

# Import root_agent for ADK compatibility
try:
    from .agent import root_agent
    __all__ = ["root_agent"]
except ImportError:
    # If agent.py imports fail, continue without ADK support
    __all__ = []

