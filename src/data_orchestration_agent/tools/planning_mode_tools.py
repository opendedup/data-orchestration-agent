"""Planning Mode tools for gathering requirements and creating PRPs."""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Global client instance (will be injected by main.py)
_planning_client = None
_session_state = {}


def set_client(planning_client: Any) -> None:
    """Set the global planning client instance.
    
    Args:
        planning_client: Data planning client instance
    """
    global _planning_client
    _planning_client = planning_client


def set_session_state(state: Dict[str, Any]) -> None:
    """Set the session state reference.
    
    Args:
        state: Session state dictionary
    """
    global _session_state
    _session_state = state


async def start_planning(initial_intent: str) -> str:
    """Start a planning session to gather requirements for a data product.
    
    Args:
        initial_intent: Initial description of the data product or goal
        
    Returns:
        First set of planning questions
    """
    try:
        logger.info(f"Starting planning session with intent: {initial_intent}")
        
        result = await _planning_client.start_planning_session(initial_intent)
        
        # Store session ID in state
        session_id = result.get("session_id")
        _session_state["planning_session_id"] = session_id
        _session_state["planning_complete"] = False
        _session_state["current_mode"] = "planning"
        
        # Format questions
        questions = result.get("questions", [])
        response = "# Planning Session Started\n\n"
        response += f"**Session ID**: {session_id}\n\n"
        response += "Please answer the following questions:\n\n"
        
        for i, question in enumerate(questions, 1):
            response += f"{i}. {question}\n"
        
        return response
        
    except Exception as e:
        logger.error(f"Error starting planning session: {e}")
        return f"Error starting planning session: {str(e)}"


async def answer_planning_questions(user_response: str) -> str:
    """Continue planning conversation with user responses.
    
    Args:
        user_response: User's answers to planning questions
        
    Returns:
        Next questions or completion message
    """
    try:
        session_id = _session_state.get("planning_session_id")
        if not session_id:
            return "No active planning session. Please start a planning session first."
        
        logger.info(f"Continuing planning session: {session_id}")
        
        result = await _planning_client.continue_conversation(session_id, user_response)
        
        # Check if planning is complete
        is_complete = result.get("is_complete", False)
        _session_state["planning_complete"] = is_complete
        
        if is_complete:
            response = "# Planning Complete! 🎉\n\n"
            response += "All requirements have been gathered. "
            response += "You can now generate the Data Product Requirement Prompt (PRP) "
            response += "using the `generate_prp` tool.\n"
            return response
        
        # More questions
        questions = result.get("questions", [])
        response = "# Next Questions\n\n"
        
        for i, question in enumerate(questions, 1):
            response += f"{i}. {question}\n"
        
        return response
        
    except Exception as e:
        logger.error(f"Error continuing planning conversation: {e}")
        return f"Error continuing planning conversation: {str(e)}"


async def generate_prp() -> str:
    """Generate the final Data Product Requirement Prompt (PRP).
    
    Returns:
        Success message with PRP summary
    """
    try:
        session_id = _session_state.get("planning_session_id")
        if not session_id:
            return "No active planning session. Please start a planning session first."
        
        if not _session_state.get("planning_complete"):
            return "Planning is not complete yet. Please answer all questions first."
        
        logger.info(f"Generating PRP for session: {session_id}")
        
        result = await _planning_client.generate_data_prp(session_id)
        
        # Store PRP in state
        prp_text = result.get("prp_text", "")
        _session_state["prp_text"] = prp_text
        _session_state["current_mode"] = "action"
        
        # Format response
        response = "# Data Product Requirement Prompt Generated! 📋\n\n"
        response += "The PRP has been created and stored in the session.\n\n"
        
        # Show summary
        summary = result.get("summary", {})
        if summary:
            response += "## Summary\n\n"
            response += f"- **Product Name**: {summary.get('product_name', 'N/A')}\n"
            response += f"- **Objective**: {summary.get('objective', 'N/A')}\n"
            response += f"- **Target Tables**: {len(summary.get('target_tables', []))}\n"
            response += "\n"
        
        response += "You can now proceed to Action Mode to execute the PRP and build the data product.\n"
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating PRP: {e}")
        return f"Error generating PRP: {str(e)}"

