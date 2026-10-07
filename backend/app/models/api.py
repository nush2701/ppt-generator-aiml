"""Request and response models for the generation API."""

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


PromptText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000),
]


class GeneratePresentationRequest(BaseModel):
    """A single natural-language request for a new presentation."""

    prompt: PromptText


class GeneratePresentationResponse(BaseModel):
    """Summary and local file information for a generated presentation."""

    success: bool = True
    run_id: str
    presentation_id: str
    title: str
    slide_count: int
    file_name: str
    file_path: str


class ModifyPresentationRequest(BaseModel):
    """Modification request for a previously generated presentation."""

    presentation_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]
    prompt: PromptText


class ModifyPresentationResponse(BaseModel):
    """Summary of a selective-regeneration result."""

    success: bool = True
    run_id: str
    status: str
    title: str
    presentation_id: str
    slide_count: int
    affected_slides: list[str]
    regenerated_slides: list[str]
    preserved_slides: list[str]
    clarification_needed: bool
    message: str
    file_name: str | None = None
    file_path: str | None = None


class FullModifyPresentationResponse(BaseModel):
    """Summary of a baseline full-regeneration request."""

    success: bool
    run_id: str
    status: str
    title: str
    presentation_id: str
    version: int | None = None
    slide_count: int
    regenerated_slides: list[str]
    message: str
    file_name: str | None = None
    file_path: str | None = None
