"""Session state management utilities."""

from typing import Any, Dict, Optional


class SessionState(dict):
    """Enhanced dictionary for session state management."""
    
    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize session state with default values."""
        super().__init__(*args, **kwargs)
        self.setdefault("current_mode", "ask")  # Always start in Ask/Discover mode
        self.setdefault("planning_session_id", None)
        self.setdefault("planning_complete", False)
        self.setdefault("prp_text", None)
        self.setdefault("discovered_datasets", None)
        self.setdefault("query_results", None)
        self.setdefault("graphql_output_path", None)
        self.setdefault("action_step", None)
        self.setdefault("pending_confirmation", None)


def initialize_session_state() -> SessionState:
    """Initialize a new session state.
    
    Returns:
        Empty session state with default values
    """
    return SessionState()


def get_session_state(session_id: str, store: Dict[str, SessionState]) -> SessionState:
    """Get or create session state for a given session ID.
    
    Args:
        session_id: Unique session identifier
        store: Dictionary storing session states
        
    Returns:
        Session state for the given ID
    """
    if session_id not in store:
        store[session_id] = initialize_session_state()
    return store[session_id]

