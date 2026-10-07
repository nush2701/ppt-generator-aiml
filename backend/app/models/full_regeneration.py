"""Result model for baseline full-presentation regeneration."""

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from app.models.presentation import Presentation


class FullRegenerationStatus(StrEnum):
    """Outcome of the full-regeneration baseline."""

    REGENERATED = "regenerated"
    CLARIFICATION_NEEDED = "clarification_needed"
    FAILED = "failed"


class FullRegenerationResult(BaseModel):
    """Result and artifacts from a baseline regeneration attempt."""

    status: FullRegenerationStatus
    presentation: Presentation
    regenerated_slides: list[str] = Field(default_factory=list)
    message: str
    output_path: Path | None = None
    version: int | None = None
    validation_errors: int = 0
