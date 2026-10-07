"""Minimal Gemini provider used to verify structured API responses."""

import os

from google import genai
from pydantic import BaseModel, ValidationError

from app.llm.provider import LLMCallUsage, ModelT


class GeminiProviderError(RuntimeError):
    """Raised when Gemini cannot return a valid structured response."""


class SmokeTestResponse(BaseModel):
    greeting: str
    description: str


class GeminiProvider:
    """Call Gemini once and parse its response into the expected JSON shape."""

    def __init__(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise GeminiProviderError(
                "GEMINI_API_KEY is missing. Set it in the environment before running the smoke test."
            )

        self.model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
        self.usage_records: list[LLMCallUsage] = []
        self._api_key = api_key
        try:
            self.client = genai.Client(api_key=api_key)
        except Exception as exc:
            raise GeminiProviderError(
                f"Could not initialize the Gemini client: {self._safe_error(exc)}"
            ) from exc

    def generate_structured(self, prompt: str, response_model: type[ModelT]) -> ModelT:
        """Generate JSON matching a Pydantic model and validate the response."""
        usage_record = LLMCallUsage(model_name=self.model)
        self.usage_records.append(usage_record)
        try:
            response = self.client.interactions.create(
                model=self.model,
                input=prompt,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": response_model.model_json_schema(),
                },
            )
        except Exception as exc:
            raise GeminiProviderError(
                f"Gemini API request failed: {self._safe_error(exc)}"
            ) from exc

        self._capture_usage(getattr(response, "usage", None), usage_record)

        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            raise GeminiProviderError("Gemini returned an empty or missing structured response.")

        try:
            return response_model.model_validate_json(output_text)
        except ValidationError as exc:
            raise GeminiProviderError(
                "Gemini response did not match the expected JSON schema: "
                f"{self._safe_error(exc)}"
            ) from exc

    @staticmethod
    def _capture_usage(usage: object, record: LLMCallUsage) -> None:
        """Copy actual Interactions SDK usage fields when present."""
        if usage is None:
            return

        def read_field(snake_case: str, camel_case: str) -> int | None:
            if isinstance(usage, dict):
                value = usage.get(snake_case, usage.get(camel_case))
            else:
                value = getattr(usage, snake_case, None)
            return value if isinstance(value, int) and value >= 0 else None

        record.input_tokens = read_field("total_input_tokens", "totalInputTokens")
        record.output_tokens = read_field("total_output_tokens", "totalOutputTokens")
        record.total_tokens = read_field("total_tokens", "totalTokens")
        record.usage_available = all(
            value is not None
            for value in (record.input_tokens, record.output_tokens, record.total_tokens)
        )

    def generate_smoke_test(self) -> dict[str, str]:
        """Preserve the original small provider smoke-test operation."""
        result = self.generate_structured(
            prompt=(
                "Return a JSON object containing a greeting and a short "
                "description of your role. Keep both values brief."
            ),
            response_model=SmokeTestResponse,
        )
        return result.model_dump()

    def _safe_error(self, error: Exception) -> str:
        """Include useful SDK details while ensuring the configured key is never leaked."""
        detail = str(error) or error.__class__.__name__
        return detail.replace(self._api_key, "[REDACTED]")
