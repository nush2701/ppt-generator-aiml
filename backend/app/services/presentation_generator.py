"""Orchestrate extraction, planning, slide generation, and PPT rendering."""

from dataclasses import dataclass
from pathlib import Path

from app.llm.gemini_provider import GeminiProvider
from app.llm.provider import LLMProvider
from app.models.presentation import Presentation
from app.rendering import render_presentation
from app.services.presentation_planner import PresentationPlanner
from app.services.presentation_store import PresentationStore
from app.services.requirement_extractor import RequirementExtractor
from app.services.slide_generator import SlideGenerator


@dataclass(frozen=True)
class GeneratedPresentation:
    """Validated presentation data and the file produced from it."""

    presentation: Presentation
    output_path: Path


class PresentationGenerator:
    """Run the existing generation services in their required order."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider

    def generate_presentation(
        self,
        prompt: str,
        output_path: str | Path | None = None,
        presentation_id: str | None = None,
    ) -> GeneratedPresentation:
        """Generate a validated presentation and save its PowerPoint file."""
        cleaned_prompt = prompt.strip()
        if not cleaned_prompt:
            raise ValueError("The presentation request must not be empty.")
        if len(cleaned_prompt) > 20_000:
            raise ValueError("The presentation request must not exceed 20,000 characters.")

        provider = self._provider or GeminiProvider()
        requirements = RequirementExtractor(provider).extract(cleaned_prompt)
        plan = PresentationPlanner(provider).plan(requirements)
        presentation = SlideGenerator(provider).generate(
            requirements,
            plan,
            presentation_id=presentation_id,
        )

        if output_path is None:
            generated_dir = Path(__file__).resolve().parents[2] / "generated"
            output_path = generated_dir / f"presentation_{presentation.id}_v1.pptx"

        saved_path = render_presentation(presentation, output_path)
        PresentationStore().save(presentation, version=1)
        return GeneratedPresentation(presentation=presentation, output_path=saved_path)


def generate_presentation(
    prompt: str,
    output_path: str | Path | None = None,
    presentation_id: str | None = None,
) -> GeneratedPresentation:
    """Convenience entry point for the complete presentation pipeline."""
    return PresentationGenerator().generate_presentation(prompt, output_path, presentation_id)
