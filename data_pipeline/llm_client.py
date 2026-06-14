"""LLM client abstraction with JSON-mode prompting and rate-limit retries."""

from __future__ import annotations

import os
from dataclasses import dataclass

from data_pipeline.common import call_with_backoff, get_logger


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    temperature: float = 0.0
    max_attempts: int = 6


def load_llm_config() -> LLMConfig:
    provider = os.getenv("DITTO_LLM_PROVIDER")
    if not provider:
        provider = "openai" if os.getenv("OPENAI_API_KEY") else "google"

    provider = provider.strip().lower()
    if provider == "openai":
        model = os.getenv("DITTO_LLM_MODEL", "gpt-4o-mini")
    elif provider in {"google", "gemini"}:
        model = os.getenv("DITTO_LLM_MODEL", "gemini-2.5-flash")
    else:
        model = os.getenv("DITTO_LLM_MODEL", "")

    temperature = float(os.getenv("DITTO_LLM_TEMPERATURE", "0"))
    max_attempts = int(os.getenv("DITTO_LLM_MAX_ATTEMPTS", "6"))
    return LLMConfig(
        provider=provider,
        model=model,
        temperature=temperature,
        max_attempts=max_attempts,
    )


class LLMClient:
    """Minimal provider adapter for JSON-returning enrichment calls."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or load_llm_config()
        self.logger = get_logger(__name__)

    def generate_json_text(self, *, system_prompt: str, user_text: str) -> str:
        provider = self.config.provider
        if provider == "openai":
            return call_with_backoff(
                lambda: self._generate_openai(system_prompt=system_prompt, user_text=user_text),
                logger=self.logger,
                max_attempts=self.config.max_attempts,
            )
        if provider in {"google", "gemini"}:
            return call_with_backoff(
                lambda: self._generate_gemini(system_prompt=system_prompt, user_text=user_text),
                logger=self.logger,
                max_attempts=self.config.max_attempts,
            )
        raise RuntimeError(
            "Unsupported DITTO_LLM_PROVIDER. Use 'openai' or 'google'. "
            f"Received: {provider!r}"
        )

    def _generate_openai(self, *, system_prompt: str, user_text: str) -> str:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required when DITTO_LLM_PROVIDER=openai.")

        from openai import OpenAI

        client = OpenAI()
        response = client.chat.completions.create(
            model=self.config.model,
            temperature=self.config.temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("OpenAI returned an empty response.")
        return content

    def _generate_gemini(self, *, system_prompt: str, user_text: str) -> str:
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY or GEMINI_API_KEY is required when DITTO_LLM_PROVIDER=google."
            )

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=self.config.model,
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=self.config.temperature,
                response_mime_type="application/json",
            ),
        )
        if not response.text:
            raise RuntimeError("Gemini returned an empty response.")
        return response.text

