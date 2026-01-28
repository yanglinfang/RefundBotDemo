"""
Tests for application configuration.
"""

import json

import pytest

from src.config import Settings, LLMEndpoint


class TestLLMEndpoint:
    """Tests for LLMEndpoint model."""

    def test_llm_endpoint_defaults(self):
        """Test LLMEndpoint default values."""
        endpoint = LLMEndpoint(
            name="test",
            url="http://localhost:8000",
            model="gpt-3.5"
        )
        assert endpoint.api_key == ""
        assert endpoint.priority == 10
        assert endpoint.is_local is False
        assert endpoint.cost_per_1k_tokens is None
        assert endpoint.request_timeout_seconds is None

    def test_llm_endpoint_with_all_fields(self):
        """Test LLMEndpoint with all fields specified."""
        endpoint = LLMEndpoint(
            name="cloud",
            url="https://api.openai.com/v1",
            api_key="sk-test",
            model="gpt-4",
            priority=1,
            is_local=False,
            cost_per_1k_tokens=0.03,
            request_timeout_seconds=30.0
        )
        assert endpoint.name == "cloud"
        assert endpoint.api_key == "sk-test"
        assert endpoint.cost_per_1k_tokens == 0.03
        assert endpoint.request_timeout_seconds == 30.0


class TestSettingsGetLLMEndpoints:
    """Tests for Settings.get_llm_endpoints method."""

    def test_get_llm_endpoints_from_json(self):
        """Test parsing endpoints from JSON configuration."""
        endpoints_json = json.dumps([
            {
                "name": "local",
                "url": "http://localhost:11434/v1",
                "model": "llama2",
                "is_local": True,
                "priority": 1
            },
            {
                "name": "cloud",
                "url": "https://api.openai.com/v1",
                "api_key": "sk-test",
                "model": "gpt-4",
                "is_local": False,
                "priority": 2
            }
        ])

        settings = Settings(llm_endpoints_json=endpoints_json)
        endpoints = settings.get_llm_endpoints()

        assert len(endpoints) == 2
        assert endpoints[0].name == "local"
        assert endpoints[0].is_local is True
        assert endpoints[1].name == "cloud"
        assert endpoints[1].api_key == "sk-test"

    def test_get_llm_endpoints_invalid_json_falls_back(self):
        """Test that invalid JSON falls back to default endpoint."""
        settings = Settings(
            llm_endpoints_json="not valid json",
            llm_api_url="http://localhost:11434/v1",
            llm_model="llama2"
        )
        endpoints = settings.get_llm_endpoints()

        assert len(endpoints) == 1
        assert endpoints[0].name == "default"
        assert endpoints[0].url == "http://localhost:11434/v1"
        assert endpoints[0].model == "llama2"

    def test_get_llm_endpoints_empty_json_uses_default(self):
        """Test that empty JSON uses default endpoint."""
        settings = Settings(
            llm_endpoints_json="",
            llm_api_url="http://localhost:11434/v1",
            llm_model="test-model"
        )
        endpoints = settings.get_llm_endpoints()

        assert len(endpoints) == 1
        assert endpoints[0].name == "default"

    def test_get_llm_endpoints_whitespace_json_uses_default(self):
        """Test that whitespace-only JSON uses default endpoint."""
        settings = Settings(
            llm_endpoints_json="   ",
            llm_api_url="http://localhost:8000/v1",
            llm_model="test"
        )
        endpoints = settings.get_llm_endpoints()

        assert len(endpoints) == 1
        assert endpoints[0].name == "default"

    def test_get_llm_endpoints_detects_local_from_url(self):
        """Test that localhost URLs are detected as local."""
        settings = Settings(
            llm_endpoints_json="",
            llm_api_url="http://localhost:11434/v1",
            llm_model="llama"
        )
        endpoints = settings.get_llm_endpoints()

        assert endpoints[0].is_local is True

    def test_get_llm_endpoints_detects_ollama_as_local(self):
        """Test that ollama URLs are detected as local."""
        settings = Settings(
            llm_endpoints_json="",
            llm_api_url="http://ollama.local:11434/v1",
            llm_model="llama"
        )
        endpoints = settings.get_llm_endpoints()

        assert endpoints[0].is_local is True

    def test_get_llm_endpoints_remote_url_not_local(self):
        """Test that remote URLs are not detected as local."""
        settings = Settings(
            llm_endpoints_json="",
            llm_api_url="https://api.openai.com/v1",
            llm_model="gpt-4"
        )
        endpoints = settings.get_llm_endpoints()

        assert endpoints[0].is_local is False

    def test_get_llm_endpoints_uses_dummy_key_when_empty(self):
        """Test that empty API key is replaced with dummy-key."""
        settings = Settings(
            llm_endpoints_json="",
            llm_api_url="http://localhost:11434/v1",
            llm_api_key="",
            llm_model="llama"
        )
        endpoints = settings.get_llm_endpoints()

        assert endpoints[0].api_key == "dummy-key"

    def test_get_llm_endpoints_preserves_api_key(self):
        """Test that provided API key is preserved."""
        settings = Settings(
            llm_endpoints_json="",
            llm_api_url="https://api.openai.com/v1",
            llm_api_key="sk-real-key",
            llm_model="gpt-4"
        )
        endpoints = settings.get_llm_endpoints()

        assert endpoints[0].api_key == "sk-real-key"
