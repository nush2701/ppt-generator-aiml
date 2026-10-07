"""Pydantic model for requirements extracted from a presentation request."""

from pydantic import BaseModel, Field, field_validator, model_validator


class PresentationRequirements(BaseModel):
    """User-specified presentation requirements, before any slide planning."""

    topic: str = Field(description="The presentation topic stated or clearly implied by the request.")
    purpose: str | None = Field(description="The requested purpose, if the user states one; otherwise null.")
    audience: str | None = Field(description="The intended audience, if specified; otherwise null.")
    slide_count: int | None = Field(description="The requested number of slides; otherwise null.")
    tone: str | None = Field(description="The requested tone, if specified; otherwise null.")
    language: str | None = Field(description="The requested language, if specified; otherwise null.")
    key_requirements: list[str] = Field(
        description="Explicit requested sections, inclusions, or emphasis; empty when none are stated."
    )
    constraints: list[str] = Field(
        description="Explicit restrictions or boundaries; empty when none are stated."
    )

    @field_validator("topic", "purpose", "audience", "tone", "language")
    @classmethod
    def strip_nonempty_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Text values must not be empty.")
        return cleaned

    @field_validator("key_requirements", "constraints")
    @classmethod
    def strip_list_items(cls, values: list[str]) -> list[str]:
        cleaned_values = [value.strip() for value in values]
        if any(not value for value in cleaned_values):
            raise ValueError("List entries must not be empty.")
        return cleaned_values

    @model_validator(mode="after")
    def validate_slide_count(self) -> "PresentationRequirements":
        if self.slide_count is not None and self.slide_count < 1:
            raise ValueError("slide_count must be a positive integer when provided.")
        return self
