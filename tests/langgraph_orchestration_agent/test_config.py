"""Tests for LangGraph agent configuration."""

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture

from langgraph_orchestration_agent.config import Config, load_config


def test_config_defaults() -> None:
    """Test that Config has expected default values."""
    config = Config(gcp_project_id="test-project", google_api_key="test-key")

    assert config.agent_model == "gemini-2.5-flash"
    assert config.agent_host == "0.0.0.0"
    assert config.agent_port == 8085
    assert config.enable_cors is True
    assert config.http_timeout == 300.0


def test_config_from_env(mocker: "MockerFixture") -> None:
    """Test that Config loads from environment variables."""
    mocker.patch.dict(os.environ, {
        "GCP_PROJECT_ID": "env-project",
        "GOOGLE_API_KEY": "env-key",
        "AGENT_MODEL": "gemini-1.5-pro",
        "AGENT_PORT": "9000",
    })

    config = Config()

    assert config.gcp_project_id == "env-project"
    assert config.google_api_key == "env-key"
    assert config.agent_model == "gemini-1.5-pro"
    assert config.agent_port == 9000


def test_load_config_missing_project_id(mocker: "MockerFixture") -> None:
    """Test that load_config raises error when GCP_PROJECT_ID is missing."""
    mocker.patch.dict(os.environ, {}, clear=True)
    mocker.patch("langgraph_orchestration_agent.config.load_dotenv")

    with pytest.raises(ValueError, match="GCP_PROJECT_ID"):
        load_config()


def test_load_config_missing_api_key(mocker: "MockerFixture") -> None:
    """Test that load_config raises error when GOOGLE_API_KEY is missing."""
    mocker.patch.dict(os.environ, {"GCP_PROJECT_ID": "test-project"}, clear=True)
    mocker.patch("langgraph_orchestration_agent.config.load_dotenv")

    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        load_config()


def test_load_config_success(mocker: "MockerFixture") -> None:
    """Test successful configuration loading."""
    mocker.patch.dict(os.environ, {
        "GCP_PROJECT_ID": "test-project",
        "GOOGLE_API_KEY": "test-key",
    }, clear=True)
    mocker.patch("langgraph_orchestration_agent.config.load_dotenv")

    config = load_config()

    assert config.gcp_project_id == "test-project"
    assert config.google_api_key == "test-key"

