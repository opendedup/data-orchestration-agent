"""Configuration management for the Data Orchestration Agent."""

import os
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Configuration settings for the Data Orchestration Agent.
    
    All settings are loaded from environment variables with sensible defaults
    for non-sensitive values.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra environment variables (like those from ADK)
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

    # MCP Service URLs
    discovery_agent_url: str = Field(
        default="http://localhost:8080",
        description="URL for the data discovery agent MCP service"
    )
    query_gen_agent_url: str = Field(
        default="http://localhost:8081",
        description="URL for the query generation agent MCP service"
    )
    planning_agent_url: str = Field(
        default="http://localhost:8082",
        description="URL for the data planning agent MCP service"
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
    gcp_project_id: Optional[str] = Field(
        default=None,
        description="Google Cloud Project ID"
    )
    google_application_credentials: Optional[str] = Field(
        default=None,
        description="Path to Google Cloud service account key"
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
    
    # Create config object
    config = Config()
    
    # Validate required settings
    if config.gcp_project_id is None:
        raise ValueError("GCP_PROJECT_ID environment variable is required")
    
    if config.google_application_credentials:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = config.google_application_credentials
    
    return config

