"""Small interface shared by language model providers."""

from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass
class LLMCallUsage:
    """Usage details for one actual provider API call."""

    model_name: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    usage_available: bool = False


class LLMProvider(Protocol):
    """Contract for a provider that returns validated structured output."""

    @property
    def usage_records(self) -> list[LLMCallUsage]:
        """Actual API call usage records collected so far."""
        ...

    def generate_structured(
        self,
        prompt: str,
        response_model: type[ModelT],
    ) -> ModelT:
        """Generate and validate a response matching a Pydantic model."""
        ...

    def generate_smoke_test(self) -> dict[str, str]:
        """Return a greeting and short role description."""
        ...
