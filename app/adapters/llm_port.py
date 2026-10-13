"""LLM Port interface, GeminiAdapter, and FixtureLLMAdapter (ADR-0002, ADR-0005)."""

from __future__ import annotations

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Raised when an LLM generation fails or cannot be validated."""


class LLMPort(ABC):
    """Port interface for LLM structured output generation."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        schema: type[T],
        system_instruction: str | None = None,
    ) -> T:
        """Generate a response validated against a Pydantic schema."""


class GeminiAdapter(LLMPort):
    """Adapter for Google Gemini using the official google-genai SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self._client: Any = None

        if self.api_key:
            try:
                from google import genai

                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning("Failed to initialize google-genai Client: %s", e)
                self._client = None

    def generate(
        self,
        prompt: str,
        schema: type[T],
        system_instruction: str | None = None,
    ) -> T:
        """Generate structured output validated by Pydantic with single retry on failure (Rule 7)."""
        if not self._client:
            raise LLMError("Gemini API key is missing or client is uninitialized.")

        from google.genai import types

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            system_instruction=system_instruction,
            temperature=0.1,
        )

        attempts = 0
        last_error: Exception | None = None
        current_prompt = prompt

        while attempts < 2:  # Try once, retry once on validation failure (Rule 7)
            attempts += 1
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=current_prompt,
                    config=config,
                )
                raw_text = response.text or "{}"
                # Pydantic validation
                return schema.model_validate_json(raw_text)
            except (ValidationError, json.JSONDecodeError) as val_err:
                last_error = val_err
                logger.warning(
                    "LLM output validation failed on attempt %d: %s. Retrying...",
                    attempts,
                    val_err,
                )
                current_prompt = (
                    f"{prompt}\n\nIMPORTANT: Your previous output failed schema validation: {val_err}. "
                    f"Please correct the JSON output strictly according to the required schema."
                )
            except Exception as api_err:
                logger.error("Gemini API call failed: %s", api_err)
                raise LLMError(f"Gemini API failure: {api_err}") from api_err

        raise LLMError(f"LLM output failed validation after 2 attempts: {last_error}")


class FixtureLLMAdapter(LLMPort):
    """Replays deterministic fixtures from a local JSON cache for offline demos and tests."""

    def __init__(self, cache_path: str | Path | None = None) -> None:
        self.cache_path = Path(cache_path or settings.LLM_FIXTURES_PATH)
        self._fixtures: dict[str, Any] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load fixture cache from file if it exists."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, encoding="utf-8") as f:
                    self._fixtures = json.load(f)
            except Exception as e:
                logger.warning("Could not read LLM fixtures cache: %s", e)
                self._fixtures = {}
        else:
            self._fixtures = {}

    def _hash_key(self, prompt: str, schema_name: str) -> str:
        """Create a reproducible lookup hash key."""
        content = f"{schema_name}::{prompt.strip()}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def register_fixture(self, key_or_prompt: str, schema_name: str, data: dict[str, Any]) -> None:
        """Register a fixture in-memory."""
        key = self._hash_key(key_or_prompt, schema_name)
        self._fixtures[key] = data
        self._fixtures[schema_name] = data  # Schema-level fallback

    def generate(
        self,
        prompt: str,
        schema: type[T],
        system_instruction: str | None = None,
    ) -> T:
        """Replay cached fixture or raise LLMError."""
        key = self._hash_key(prompt, schema.__name__)

        # Lookup by exact hash, then schema name, then first available
        data = self._fixtures.get(key) or self._fixtures.get(schema.__name__)

        if data is None:
            raise LLMError(f"No fixture found for key '{key}' or schema '{schema.__name__}'.")

        try:
            return schema.model_validate(data)
        except ValidationError as e:
            raise LLMError(f"Cached fixture for '{schema.__name__}' is invalid: {e}") from e


def get_llm_adapter() -> LLMPort:
    """Factory creating configured LLM adapter according to LLM_MODE and settings."""
    if settings.LLM_MODE == "live" and settings.GEMINI_API_KEY:
        try:
            return GeminiAdapter(api_key=settings.GEMINI_API_KEY)
        except Exception as e:
            logger.warning("Failed to create GeminiAdapter, falling back to FixtureLLMAdapter: %s", e)

    return FixtureLLMAdapter()
