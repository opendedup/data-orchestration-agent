"""Plan Mode tools for PRP creation and session state management."""

import json
import logging
from typing import Any, Dict, Optional

from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)


def update_session_state(
    tool_context: ToolContext,
    state_path: str,
    value: Any,
    operation: str = "set"
) -> str:
    """Update session state for tracking planning progress.
    
    Use this tool to track conversation history, discovered datasets, and confirmation flags
    during the planning process.
    
    Args:
        tool_context: ADK tool context with session access
        state_path: Dot-notation path to state key (e.g., "planning.qa_history", "planning.datasets_confirmed")
        value: Value to set or append (can be string, dict, list, bool)
        operation: Operation to perform - "set" (replace), "append" (add to list), "merge" (merge dict)
        
    Returns:
        Confirmation message
        
    Examples:
        # Initialize planning state
        update_session_state(ctx, "planning", {"qa_history": [], "discovered_datasets": []}, "set")
        
        # Add to Q&A history
        update_session_state(ctx, "planning.qa_history", {"role": "user", "content": "..."}, "append")
        
        # Set confirmation flag
        update_session_state(ctx, "planning.datasets_confirmed", True, "set")
    """
    try:
        # Get session state
        session_state = tool_context.session.state
        
        # Parse the state path
        path_parts = state_path.split(".")
        
        # Navigate to the parent of the target key
        current = session_state
        for part in path_parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # Get the final key
        final_key = path_parts[-1]
        
        # Perform the operation
        if operation == "set":
            current[final_key] = value
            logger.info(f"Set session state: {state_path} = {value}")
            return f"✓ Updated {state_path}"
            
        elif operation == "append":
            if final_key not in current:
                current[final_key] = []
            if not isinstance(current[final_key], list):
                return f"Error: {state_path} is not a list (cannot append)"
            current[final_key].append(value)
            logger.info(f"Appended to session state: {state_path}")
            return f"✓ Appended to {state_path}"
            
        elif operation == "merge":
            if final_key not in current:
                current[final_key] = {}
            if not isinstance(current[final_key], dict):
                return f"Error: {state_path} is not a dict (cannot merge)"
            if not isinstance(value, dict):
                return f"Error: Value must be a dict for merge operation"
            current[final_key].update(value)
            logger.info(f"Merged into session state: {state_path}")
            return f"✓ Merged into {state_path}"
            
        else:
            return f"Error: Unknown operation '{operation}'. Use 'set', 'append', or 'merge'"
            
    except Exception as e:
        error_msg = f"Error updating session state: {str(e)}"
        logger.error(error_msg)
        return error_msg


def get_session_state(
    tool_context: ToolContext,
    state_path: Optional[str] = None
) -> str:
    """Retrieve session state for reading planning progress.
    
    Args:
        tool_context: ADK tool context with session access
        state_path: Optional dot-notation path to specific state key. If None, returns all state.
        
    Returns:
        JSON string of the requested state
        
    Examples:
        # Get all planning state
        get_session_state(ctx, "planning")
        
        # Get Q&A history
        get_session_state(ctx, "planning.qa_history")
    """
    try:
        session_state = tool_context.session.state
        
        if state_path is None:
            # Return entire state
            return json.dumps(session_state, indent=2)
        
        # Navigate to the requested path
        path_parts = state_path.split(".")
        current = session_state
        
        for part in path_parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return f"State path not found: {state_path}"
        
        return json.dumps(current, indent=2)
        
    except Exception as e:
        error_msg = f"Error reading session state: {str(e)}"
        logger.error(error_msg)
        return error_msg

