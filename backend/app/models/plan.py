"""Pydantic models for a presentation's structure before slide content generation."""

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.models.presentation import SlideLayout


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PlannedSlide(BaseModel):
    """A single planned slide without its detailed content."""

    id: NonEmptyString
    order: int = Field(gt=0)
    purpose: NonEmptyString
    layout: SlideLayout


class PresentationPlan(BaseModel):
    """An ordered sequence of slide purposes and controlled layouts."""

    title: NonEmptyString
    slides: list[PlannedSlide] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_slide_ids_and_order(self) -> "PresentationPlan":
        ids = [slide.id for slide in self.slides]
        if len(ids) != len(set(ids)):
            raise ValueError("Planned slide IDs must be unique.")

        orders = [slide.order for slide in self.slides]
        expected_orders = list(range(1, len(self.slides) + 1))
        if orders != expected_orders:
            raise ValueError("Planned slides must be ordered sequentially starting at 1.")

        return self
