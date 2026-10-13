"""Tests for LLMPort, GeminiAdapter, FixtureLLMAdapter, and error handling (Rule 7, ADR-0005)."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from app.adapters.llm_port import (
    FixtureLLMAdapter,
    GeminiAdapter,
    LLMError,
)


class DummySchema(BaseModel):
    name: str = Field(...)
    score: int = Field(...)


def test_fixture_adapter_valid() -> None:
    """Test FixtureLLMAdapter returning registered fixture."""
    adapter = FixtureLLMAdapter()
    adapter.register_fixture(
        key_or_prompt="test prompt",
        schema_name="DummySchema",
        data={"name": "Test Item", "score": 95},
    )

    result = adapter.generate("test prompt", DummySchema)
    assert result.name == "Test Item"
    assert result.score == 95


def test_fixture_adapter_invalid_schema() -> None:
    """Test FixtureLLMAdapter rejects cached data that violates schema."""
    adapter = FixtureLLMAdapter()
    adapter.register_fixture(
        key_or_prompt="bad prompt",
        schema_name="DummySchema",
        data={"name": "Missing score"},  # Missing required field 'score'
    )

    with pytest.raises(LLMError, match="invalid"):
        adapter.generate("bad prompt", DummySchema)


def test_fixture_adapter_missing_key() -> None:
    """Test FixtureLLMAdapter raises error when no matching fixture exists."""
    adapter = FixtureLLMAdapter()
    with pytest.raises(LLMError, match="No fixture found"):
        adapter.generate("unknown prompt for missing schema", DummySchema)


def test_gemini_adapter_retry_on_malformed_json() -> None:
    """Test that GeminiAdapter rejects malformed LLM output and retries once (Rule 7)."""
    with patch("app.adapters.llm_port.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = "dummy-key"
        mock_settings.GEMINI_MODEL = "gemini-2.5-flash"

        adapter = GeminiAdapter(api_key="test-key")

        # Mock client to return invalid JSON first, then valid JSON on retry
        mock_client = MagicMock()
        mock_resp_fail = MagicMock()
        mock_resp_fail.text = "NOT JSON AT ALL"

        mock_resp_success = MagicMock()
        mock_resp_success.text = '{"name": "Valid Item", "score": 88}'

        mock_client.models.generate_content.side_effect = [mock_resp_fail, mock_resp_success]
        adapter._client = mock_client

        # Should retry and succeed
        result = adapter.generate("prompt", DummySchema)
        assert result.name == "Valid Item"
        assert result.score == 88
        assert mock_client.models.generate_content.call_count == 2


def test_gemini_adapter_fails_after_retry() -> None:
    """Test that GeminiAdapter raises LLMError if output remains malformed after retry."""
    adapter = GeminiAdapter(api_key="test-key")

    mock_client = MagicMock()
    mock_resp_fail = MagicMock()
    mock_resp_fail.text = "INVALID_OUTPUT"

    mock_client.models.generate_content.side_effect = [mock_resp_fail, mock_resp_fail]
    adapter._client = mock_client

    with pytest.raises(LLMError, match="failed validation after 2 attempts"):
        adapter.generate("prompt", DummySchema)
