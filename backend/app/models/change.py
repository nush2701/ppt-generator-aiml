"""Validated result of analyzing a requested presentation change."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StrictBool, StringConstraints, model_validator


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ChangeType(StrEnum):
    """Scope or kind of the requested presentation modification."""

    CONTENT = "content"
    LAYOUT = "layout"
    COMPONENT = "component"
    MULTIPLE = "multiple"
    GLOBAL = "global"
    UNCLEAR = "unclear"


class ChangeAnalysis(BaseModel):
    """The existing slides and components a request would affect."""

    affected_slides: list[NonEmptyString] = Field(default_factory=list)
    affected_components: list[NonEmptyString] = Field(default_factory=list)
    change_type: ChangeType
    instruction: NonEmptyString
    requires_regeneration: StrictBool

    @model_validator(mode="after")
    def validate_scope(self) -> "ChangeAnalysis":
        if len(self.affected_slides) != len(set(self.affected_slides)):
            raise ValueError("Affected slide IDs must be unique.")
        if len(self.affected_components) != len(set(self.affected_components)):
            raise ValueError("Affected component IDs must be unique.")

        if self.change_type == ChangeType.UNCLEAR:
            if self.affected_slides or self.affected_components:
                raise ValueError("An unclear change must not guess affected slide or component IDs.")
            if self.requires_regeneration:
                raise ValueError("An unclear change must request clarification before regeneration.")
        elif not self.affected_slides:
            raise ValueError("A clear change must identify at least one affected slide.")

        if self.change_type == ChangeType.GLOBAL and not self.requires_regeneration:
            raise ValueError("A global change requires regeneration.")
        return self
