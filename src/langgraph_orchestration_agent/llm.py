"""LLM initialization for LangGraph agent using Gemini."""

import logging
import os

from langchain_google_genai import ChatGoogleGenerativeAI

from .config import Config

logger = logging.getLogger(__name__)


def create_llm(config: Config | None = None, model_name: str | None = None) -> ChatGoogleGenerativeAI:
    """Create a ChatGoogleGenerativeAI instance for use in LangGraph nodes.

    Args:
        config: Optional configuration object. If not provided, will use environment variables.
        model_name: Optional model name override. If not provided, uses config or default.

    Returns:
        Configured ChatGoogleGenerativeAI instance

    Raises:
        ValueError: If GOOGLE_API_KEY is not set
    """
    # Get API key from config or environment
    api_key = None
    if config:
        api_key = config.google_api_key
    if not api_key:
        api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is required")

    # Get model name
    if not model_name:
        if config:
            model_name = config.agent_model
        else:
            model_name = os.getenv("AGENT_MODEL", "gemini-2.5-flash")

    logger.info(f"Creating LLM with model: {model_name}")

    # Create and return the LLM
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.1,
        convert_system_message_to_human=True,
    )

    return llm

