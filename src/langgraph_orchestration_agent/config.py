"""Configuration management for the LangGraph Orchestration Agent."""

import os

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Configuration settings for the LangGraph Orchestration Agent.

    All settings are loaded from environment variables with sensible defaults
    for non-sensitive values.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Agent Configuration
    agent_model: str = Field(
        default="gemini-2.5-flash",
        description="Google AI model to use for the agent"
    )
    agent_host: str = Field(
        default="0.0.0.0",
        description="Host address for the agent web server"
    )
    agent_port: int = Field(
        default=8085,
        description="Port number for the agent web server"
    )
    enable_cors: bool = Field(
        default=True,
        description="Enable CORS for cross-origin requests (set to true for development)"
    )

    # MCP Service URLs
    discovery_agent_url: str = Field(
        default="http://localhost:8080",
        description="URL for the data discovery agent MCP service"
    )
    query_gen_agent_url: str = Field(
        default="http://localhost:8081",
        description="URL for the query generation agent MCP service"
    )
    graphql_agent_url: str = Field(
        default="http://localhost:8083",
        description="URL for the GraphQL agent MCP service"
    )
    apollo_mcp_url: str = Field(
        default="http://localhost:8084",
        description="URL for the Apollo MCP server"
    )

    # GCP Configuration
    gcp_project_id: str | None = Field(
        default=None,
        description="Google Cloud Project ID"
    )
    google_application_credentials: str | None = Field(
        default=None,
        description="Path to Google Cloud service account key"
    )
    google_api_key: str | None = Field(
        default=None,
        description="Google AI API key for Gemini models"
    )

    # Timeouts and Limits
    http_timeout: float = Field(
        default=300.0,
        description="HTTP request timeout in seconds"
    )
    max_planning_turns: int = Field(
        default=10,
        description="Maximum number of planning conversation turns"
    )
    max_queries_per_target: int = Field(
        default=3,
        description="Maximum number of queries to generate per target table"
    )
    max_query_iterations: int = Field(
        default=10,
        description="Maximum iterations for query generation refinement"
    )

    # BigQuery Configuration
    bigquery_max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts for BigQuery SQL execution"
    )
    bigquery_timeout: int = Field(
        default=300,
        description="Timeout in seconds for BigQuery query execution"
    )


def load_config() -> Config:
    """Load configuration from environment variables.

    Returns:
        Config: Configuration object with all settings loaded

    Raises:
        ValueError: If required configuration is missing
    """
    # Load environment variables from .env file
    load_dotenv()

    # Check for required environment variables
    gcp_project_id = os.getenv("GCP_PROJECT_ID")
    if not gcp_project_id:
        raise ValueError("GCP_PROJECT_ID environment variable is required")

    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is required for Gemini models")

    # Create config object
    config = Config()

    if config.google_application_credentials:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = config.google_application_credentials

    return config

