"""Result model for slide-level selective regeneration."""

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from app.models.presentation import Presentation


class SelectiveRegenerationStatus(StrEnum):
    """Outcome of a selective-regeneration request."""

    REGENERATED = "regenerated"
    CLARIFICATION_NEEDED = "clarification_needed"
    GLOBAL_CHANGE = "global_change"


class SelectiveRegenerationResult(BaseModel):
    """Updated presentation and scope information for later metrics."""

    status: SelectiveRegenerationStatus
    presentation: Presentation
    affected_slides: list[str] = Field(default_factory=list)
    regenerated_slides: list[str] = Field(default_factory=list)
    preserved_slides: list[str] = Field(default_factory=list)
    clarification_needed: bool = False
    message: str
    total_slide_count: int
    output_path: Path | None = None
