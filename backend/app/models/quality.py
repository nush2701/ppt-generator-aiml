"""Validated models for blinded human presentation-quality evaluation."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
EvaluationId = Annotated[str, StringConstraints(pattern=r"^eval-[a-f0-9]{20}$")]
Score = Annotated[StrictInt, Field(ge=1, le=5)]


class QualityDimension(StrEnum):
    RELEVANCE = "relevance"
    COMPLETENESS = "completeness"
    CONSISTENCY = "consistency"
    READABILITY = "readability"
    LAYOUT_SUITABILITY = "layout_suitability"
    REQUIREMENT_ADHERENCE = "requirement_adherence"


class RegenerationMethod(StrEnum):
    SELECTIVE = "selective"
    FULL = "full"


class BlindedLabel(StrEnum):
    VERSION_A = "Version A"
    VERSION_B = "Version B"


class QualityEvaluationCase(BaseModel):
    """Internal evaluation record for one method's version of a case."""

    model_config = ConfigDict(extra="forbid")

    evaluation_id: EvaluationId
    experiment_id: NonEmptyString
    case_id: NonEmptyString
    presentation_case_id: NonEmptyString
    modification_request: NonEmptyString
    method: RegenerationMethod
    original_presentation_id: NonEmptyString
    output_pptx_path: NonEmptyString
    affected_slide_ids: list[NonEmptyString]
    quality_status: Literal["pending", "rated"] = "pending"
    blinded_pptx_path: NonEmptyString
    original_pptx_path: NonEmptyString


class QualityEvaluationMapping(BaseModel):
    """Private mapping between a blinded label and the producing method."""

    model_config = ConfigDict(extra="forbid")

    evaluation_id: EvaluationId
    blinded_label: BlindedLabel
    actual_method: RegenerationMethod


class QualityRating(BaseModel):
    """One evaluator's human scores for one blinded presentation."""

    model_config = ConfigDict(extra="forbid")

    evaluation_id: EvaluationId
    blinded_label: BlindedLabel
    relevance: Score
    completeness: Score
    consistency: Score
    readability: Score
    layout_suitability: Score
    requirement_adherence: Score
    evaluator_id: NonEmptyString
    optional_comments: str | None = None

    def overall_score(self) -> float:
        return sum(
            getattr(self, dimension.value)
            for dimension in QualityDimension
        ) / len(QualityDimension)
