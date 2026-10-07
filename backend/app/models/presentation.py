"""Validated data structures for presentations, slides, and slide components."""

from enum import StrEnum
from typing import Annotated

from pydantic import (
    BaseModel,
    Field,
    JsonValue,
    RootModel,
    StringConstraints,
    model_validator,
)


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class SlideLayout(StrEnum):
    """Supported predefined slide layouts."""

    TITLE = "title"
    TITLE_BULLETS = "title_bullets"
    TWO_COLUMN = "two_column"
    COMPARISON = "comparison"
    THREE_CARD = "three_card"
    IMAGE_TEXT = "image_text"
    TIMELINE = "timeline"
    STATISTIC = "statistic"
    CONCLUSION = "conclusion"


class ComponentType(StrEnum):
    """Supported content types that a future renderer can display."""

    TITLE = "title"
    TEXT = "text"
    BULLET_LIST = "bullet_list"
    IMAGE = "image"
    STATISTIC = "statistic"
    CARD = "card"
    TABLE = "table"
    TIMELINE = "timeline"


class SlideComponent(BaseModel):
    """A stable, typed piece of slide content with JSON-compatible data."""

    id: NonEmptyString
    type: ComponentType
    content: JsonValue
    properties: dict[str, JsonValue] = Field(default_factory=dict)


class PresentationMetadata(RootModel[dict[str, JsonValue]]):
    """Flexible JSON metadata associated with a presentation."""


class Slide(BaseModel):
    """One ordered slide in a presentation."""

    id: NonEmptyString
    order: int = Field(gt=0)
    layout: SlideLayout
    purpose: NonEmptyString
    components: list[SlideComponent]


class Presentation(BaseModel):
    """The structured internal representation of a generated presentation."""

    id: NonEmptyString
    title: NonEmptyString
    metadata: PresentationMetadata
    slides: list[Slide] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_stable_ids_and_order(self) -> "Presentation":
        slide_ids = [slide.id for slide in self.slides]
        if len(slide_ids) != len(set(slide_ids)):
            raise ValueError("Slide IDs must be unique within a presentation.")

        orders = [slide.order for slide in self.slides]
        if len(orders) != len(set(orders)):
            raise ValueError("Slide order values must be unique.")

        component_ids = [
            component.id
            for slide in self.slides
            for component in slide.components
        ]
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("Component IDs must be unique within a presentation.")

        return self
