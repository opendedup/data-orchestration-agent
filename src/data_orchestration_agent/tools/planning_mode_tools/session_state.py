"""Session state management tools for Plan Mode."""

import json
import logging
from enum import Enum
from typing import Any, Optional

from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)


def to_prefixed_key(state_path: str) -> str:
    """Converts a dot-notation path to a prefixed session state key.
    
    Follows the convention: `planning.some_value` -> `user:planning_somevalue`
    """
    if not state_path.startswith("planning"):
        return state_path
    
    # Remove "planning." or "planning_" prefix if it exists
    if state_path.startswith("planning."):
        key_suffix = state_path[len("planning."):]
    elif state_path.startswith("planning_"):
        key_suffix = state_path[len("planning_"):]
    else: # just "planning"
        key_suffix = state_path[len("planning"):]

    # Remove all underscores and dots from the rest of the key
    sanitized_suffix = key_suffix.replace("_", "").replace(".", "")
    
    return f"user:planning_{sanitized_suffix}"


def _get_session_state_summary(session_state: dict[str, Any]) -> str:
    """Generates a summary of the session state for logging."""
    if not isinstance(session_state, dict):
        return f"Session state is not a dict, it is of type {type(session_state)}"

    summary: dict[str, Any] = {
        "planning_keys": [],
        "planning_sizes": {},
        "other_keys": [],
    }

    for key, value in session_state.items():
        if key.startswith("user:planning_"):
            simple_key = key.replace("user:", "")
            summary["planning_keys"].append(simple_key)
            size: Any
            if hasattr(value, "__len__"):
                size = len(value)
            else:
                size = f"type:{type(value).__name__}"
            summary["planning_sizes"][simple_key] = size
        else:
            summary["other_keys"].append(key)

    return json.dumps(summary, default=str)


class SessionStateOperation(str, Enum):
    """Valid operations for session state updates."""
    
    SET = "set"
    APPEND = "append"
    MERGE = "merge"


def update_session_state(
    tool_context: ToolContext,
    state_path: str,
    value: Any,
    operation: SessionStateOperation
) -> str:
    """Update session state for tracking planning progress.
    
    Use this tool to track conversation history, discovered datasets, and confirmation flags
    during the planning process.
    
    Args:
        tool_context: ADK tool context with session access
        state_path: Dot-notation path to state key (e.g., "planning_qahistory", "planning_datasetsconfirmed")
        value: Value to set or append (can be string, dict, list, bool)
        operation: Operation to perform (SET, APPEND, or MERGE)
        
    Returns:
        Confirmation message
        
    Examples:
        # Initialize planning state (now done automatically by _ensure_planning_session_initialized)
        
        # Add to Q&A history
        update_session_state(ctx, "planning_qahistory", {"role": "user", "content": "..."}, SessionStateOperation.APPEND)
        
        # Set confirmation flag
        update_session_state(ctx, "planning_datasetsconfirmed", True, SessionStateOperation.SET)
    """
    try:
        # Get session state
        session_state = tool_context.session.state
        
        # Comprehensive debug logging
        logger.info(
            f"update_session_state called: path='{state_path}', operation='{operation.value}'"
        )
        logger.info(f"Session state before update: {_get_session_state_summary(session_state)}")
        
        # HANDLE LONG CONTENT to prevent malformed function call errors
        # Store full content separately and keep summary in qa_history
        MAX_CONTENT_LENGTH = 800  # Safe limit for function call parameters
        
        if operation == SessionStateOperation.APPEND and isinstance(value, dict) and "content" in value:
            content = value["content"]
            if len(content) > MAX_CONTENT_LENGTH:
                # Initialize content store if needed
                if "temp:full_content_store" not in session_state:
                    session_state["temp:full_content_store"] = {}
                
                # Generate unique ID for this content
                content_id = f"msg_{len(session_state['temp:full_content_store'])}"
                
                # Store full content separately
                session_state["temp:full_content_store"][content_id] = content
                
                # Keep truncated version in qa_history for context
                value["content"] = content[:MAX_CONTENT_LENGTH] + f"... [Full content stored as {content_id}]"
                value["_content_ref"] = content_id
                value["_full_length"] = len(content)
                
                logger.info(
                    f"Stored long content ({len(content)} chars) separately as {content_id}. "
                    f"Truncated to {MAX_CONTENT_LENGTH} chars in qa_history."
                )
        
        # Convert to prefixed key
        prefixed_key = to_prefixed_key(state_path)
        
        # Perform the operation
        if operation == SessionStateOperation.SET:
            old_value_json = json.dumps(session_state.get(prefixed_key), default=str)
            new_value_json = json.dumps(value, default=str)
            logger.debug(f"SET: '{prefixed_key}'. Old value: {old_value_json}, New value: {new_value_json}")
            
            session_state[prefixed_key] = value
            logger.debug(f"Set session state: {prefixed_key}")
            logger.debug(f"Session state after update: {_get_session_state_summary(session_state)}")
            return f"✓ Updated {state_path}"
            
        elif operation == SessionStateOperation.APPEND:
            current_list = session_state.get(prefixed_key, [])
            if not isinstance(current_list, list):
                return f"Error: {state_path} ({prefixed_key}) is not a list (cannot append)"
            
            logger.debug(f"APPEND: '{prefixed_key}'. Appending value: {json.dumps(value, default=str)}")
            
            current_list.append(value)
            session_state[prefixed_key] = current_list
            logger.debug(f"Appended to session state: {prefixed_key}")
            logger.debug(f"Session state after update: {_get_session_state_summary(session_state)}")
            return f"✓ Appended to {state_path}"
            
        elif operation == SessionStateOperation.MERGE:
            current_dict = session_state.get(prefixed_key, {})
            if not isinstance(current_dict, dict):
                return f"Error: {state_path} ({prefixed_key}) is not a dict (cannot merge)"
            if not isinstance(value, dict):
                return f"Error: Value must be a dict for merge operation"

            logger.debug(f"MERGE: '{prefixed_key}'. Merging value: {json.dumps(value, default=str)}")

            current_dict.update(value)
            session_state[prefixed_key] = current_dict
            logger.debug(f"Merged into session state: {prefixed_key}")
            logger.debug(f"Session state after update: {_get_session_state_summary(session_state)}")
            return f"✓ Merged into {state_path}"
            
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
        get_session_state(ctx, "planning_qahistory")
    """
    try:
        logger.info(f"get_session_state called: path='{state_path or 'all'}'")
        session_state = tool_context.session.state
        
        if state_path is None:
            # Return entire state
            return json.dumps(session_state, indent=2, default=str)
        
        if state_path == "planning":
            # Special case: return all planning-related state
            planning_state = {
                key: session_state[key]
                for key in session_state
                if key.startswith("user:planning_")
            }
            return json.dumps(planning_state, indent=2, default=str)
        
        # Get specific value
        prefixed_key = to_prefixed_key(state_path)
        
        if prefixed_key in session_state:
            value = session_state[prefixed_key]
            return json.dumps(value, indent=2, default=str)
        else:
            return f"State path not found: {state_path} (key: {prefixed_key})"
        
    except Exception as e:
        error_msg = f"Error reading session state: {str(e)}"
        logger.error(error_msg)
        return error_msg


def track_user_message(tool_context: ToolContext, message: str) -> str:
    """Track a user message in planning qa_history.
    
    Stores the user message content in the planning session state for PRP generation.
    
    Args:
        tool_context: ADK tool context with session access
        message: The user message content to track
        
    Returns:
        Confirmation message
        
    Example:
        track_user_message(ctx, "I want to create a sales forecast view")
    """
    try:
        # Ensure planning session is initialized
        _ensure_planning_session_initialized(tool_context)
        
        logger.info(f"Tracking user message ({len(message)} chars)")
        
        return update_session_state(
            tool_context,
            "planning_qahistory",
            {"role": "user", "content": message},
            SessionStateOperation.APPEND
        )
            
    except Exception as e:
        error_msg = f"Error tracking user message: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg


def track_assistant_message(tool_context: ToolContext, message: str) -> str:
    """Track an assistant message in planning qa_history.
    
    Stores the assistant message content in the planning session state for PRP generation.
    
    Args:
        tool_context: ADK tool context with session access
        message: The assistant message content to track
        
    Returns:
        Confirmation message
        
    Example:
        track_assistant_message(ctx, "Here are the datasets I found...")
    """
    try:
        # Ensure planning session is initialized
        _ensure_planning_session_initialized(tool_context)
        
        logger.info(f"Tracking assistant message ({len(message)} chars)")
        
        return update_session_state(
            tool_context,
            "planning_qahistory",
            {"role": "assistant", "content": message},
            SessionStateOperation.APPEND
        )
            
    except Exception as e:
        error_msg = f"Error tracking assistant message: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg


def _ensure_planning_session_initialized(tool_context: ToolContext) -> None:
    """Internal helper to ensure planning session is initialized.
    
    Automatically initializes the planning session state if it doesn't exist.
    This is called by other functions to ensure the session structure is ready.
    
    Args:
        tool_context: ADK tool context with session access
    """
    session_state = tool_context.session.state
    #logger.info(f" DIAGNOSTIC: session_state object ID in _ensure_planning_session_initialized is {id(session_state)}")
    logger.info(f" DIAGNOSTIC: session_state keys in _ensure_planning_session_initialized: {list(session_state.keys())}")

    qa_history_key = to_prefixed_key("planning_qahistory")

    if qa_history_key not in session_state:
        logger.info("Planning session not initialized. Initializing keys...")
        session_state[qa_history_key] = []
        session_state[to_prefixed_key("planning_discovereddatasets")] = {}
        session_state[to_prefixed_key("planning_intentconfirmed")] = False
        session_state[to_prefixed_key("planning_datasetsconfirmed")] = False
        session_state[to_prefixed_key("planning_prpgenerated")] = False
        session_state[to_prefixed_key("planning_prpcontent")] = ""
        logger.info("Planning session initialized.")
    else:
        # Log current state for debugging
        datasets_key = to_prefixed_key("planning_discovereddatasets")
        current_datasets = session_state.get(datasets_key, {})
        dataset_count = len(current_datasets) if isinstance(current_datasets, dict) else 0
        logger.info(f"Planning session already exists with {dataset_count} discovered datasets")


def set_datasets_confirmed(tool_context: ToolContext, confirmed: bool) -> str:
    """Set the datasets_confirmed flag.
    
    Marks whether user has confirmed the discovered datasets are suitable.
    
    Args:
        tool_context: ADK tool context with session access
        confirmed: True if datasets are confirmed, False otherwise
        
    Returns:
        Confirmation message
        
    Example:
        set_datasets_confirmed(ctx, True)
    """
    # Ensure planning session is initialized
    _ensure_planning_session_initialized(tool_context)
    
    return update_session_state(
        tool_context,
        "planning_datasetsconfirmed",
        confirmed,
        SessionStateOperation.SET
    )


def set_intent_confirmed(tool_context: ToolContext, confirmed: bool) -> str:
    """Set the intent_confirmed flag.
    
    Marks whether user has confirmed the requirements understanding is correct.
    
    Args:
        tool_context: ADK tool context with session access
        confirmed: True if intent is confirmed, False otherwise
        
    Returns:
        Confirmation message
        
    Example:
        set_intent_confirmed(ctx, True)
    """
    # Ensure planning session is initialized
    _ensure_planning_session_initialized(tool_context)
    
    return update_session_state(
        tool_context,
        "planning_intentconfirmed",
        confirmed,
        SessionStateOperation.SET
    )





async def load_dataset_to_session(tool_context: ToolContext, table_ids: list[str]) -> str:
    """Load full dataset details into session state.
    
    Fetches complete metadata (schema, description, etc.) for each table and stores
    it in session state as a dictionary mapping table_id to markdown details.
    This provides the PRP generator with full schema information.
    
    Args:
        tool_context: ADK tool context with session access
        table_ids: List of BigQuery table IDs (e.g., ["project.dataset.table1", ...])
        
    Returns:
        Confirmation message with count of datasets loaded
        
    Example:
        load_dataset_to_session(ctx, ["project.dataset.customers", "project.dataset.orders"])
    """
    try:
        logger.info(f" DIAGNOSTIC: tool_context.session.state object ID at start of load_dataset_to_session is {id(tool_context.session.state)}")
        logger.info(f"load_dataset_to_session called with {len(table_ids)} table IDs: {table_ids}")
        
        # Ensure planning session is initialized
        _ensure_planning_session_initialized(tool_context)
        
        # Log current state before loading
        datasets_key = to_prefixed_key("planning_discovereddatasets")
        current_datasets = tool_context.session.state.get(datasets_key, {})
        logger.info(f"Current discovered_datasets before loading: {len(current_datasets)} datasets")
        
        # Import discovery client
        from ..ask_mode_tools import _discovery_client
        
        if _discovery_client is None:
            return "Error: Discovery client not initialized"
        
        # Dictionary to store table_id -> markdown details
        datasets_dict = {}
        successful_loads = 0
        failed_loads = []
        
        # Fetch details for each table
        for table_id in table_ids:
            try:
                # Parse table ID
                parts = table_id.split(".")
                if len(parts) != 3:
                    logger.warning(f"Invalid table ID format: {table_id}")
                    failed_loads.append(table_id)
                    continue
                
                project_id, dataset_id, table_name = parts
                
                # Get dataset details from discovery client
                logger.info(f"Fetching details for {table_id}")
                result = await _discovery_client.get_asset_details(
                    project_id, dataset_id, table_name
                )
                
                if result and result != "Asset not found":
                    datasets_dict[table_id] = result
                    successful_loads += 1
                    logger.info(f"Successfully loaded details for {table_id}")
                else:
                    logger.warning(f"Asset not found: {table_id}")
                    failed_loads.append(table_id)
                    
            except Exception as e:
                logger.error(f"Error fetching details for {table_id}: {e}")
                failed_loads.append(table_id)
        
        # Store in session state
        if datasets_dict:
            logger.info(f"Storing {len(datasets_dict)} datasets into planning_discovereddatasets")
            logger.info(f"Dataset table IDs being stored: {list(datasets_dict.keys())}")
            
            update_session_state(
                tool_context,
                "planning_discovereddatasets",
                datasets_dict,
                SessionStateOperation.SET
            )
            
            # Verify storage
            stored_datasets_key = to_prefixed_key("planning_discovereddatasets")
            stored_datasets = tool_context.session.state.get(stored_datasets_key, {})
            logger.info(f"✓ Verified: planning_discovereddatasets now contains {len(stored_datasets)} datasets")
            logger.info(f"Stored dataset keys: {list(stored_datasets.keys())}")
        else:
            logger.warning("No datasets to store - datasets_dict is empty")
        
        # Build confirmation message
        message_parts = [f"✓ Loaded {successful_loads}/{len(table_ids)} datasets"]
        if failed_loads:
            message_parts.append(f"Failed to load: {', '.join(failed_loads)}")
        
        return " | ".join(message_parts)
        
    except Exception as e:
        error_msg = f"Error loading datasets: {str(e)}"
        logger.error(error_msg)
        return error_msg

