"""Utility tools for ask mode."""

import logging
from datetime import datetime, timezone

from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)


async def get_current_time(tool_context: ToolContext) -> str:
    """Get the current date and time.
    
    Args:
        tool_context: The ADK ToolContext (required for consistent tool signatures)

    Returns:
        Current timestamp in ISO 8601 format with timezone
    """
    logger.warning(f"⏰ TOOL CALLED: get_current_time")
    now = datetime.now(timezone.utc)
    return f"Current time: {now.isoformat()}"

