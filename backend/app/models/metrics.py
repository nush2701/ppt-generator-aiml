"""Validated metrics recorded for one generation or modification run."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class OperationType(StrEnum):
    """Operation measured by a metrics record."""

    GENERATION = "generation"
    SELECTIVE_REGENERATION = "selective_regeneration"
    FULL_REGENERATION = "full_regeneration"


class RunMetrics(BaseModel):
    """Serializable measurements for one API operation."""

    run_id: NonEmptyString
    timestamp: NonEmptyString
    operation: OperationType
    presentation_id: NonEmptyString
    modification_request: str | None = None
    status: NonEmptyString
    model_name: NonEmptyString
    latency_ms: float = Field(ge=0)
    llm_calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    token_usage_available: bool
    usage_unavailable_calls: int = Field(ge=0)
    regenerated_slide_count: int = Field(ge=0)
    total_slide_count: int = Field(ge=0)
    validation_errors: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    affected_slide_ids: list[NonEmptyString] = Field(default_factory=list)

    @field_validator("affected_slide_ids")
    @classmethod
    def validate_unique_affected_ids(cls, ids: list[str]) -> list[str]:
        if len(ids) != len(set(ids)):
            raise ValueError("affected_slide_ids must not contain duplicates.")
        return ids
