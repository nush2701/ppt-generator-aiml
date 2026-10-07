"""Orchestrate change analysis, slide-only replacement, validation, and rendering."""

from pathlib import Path
from uuid import uuid4

from app.llm.gemini_provider import GeminiProvider
from app.llm.provider import LLMProvider
from app.models.change import ChangeType
from app.models.plan import PlannedSlide
from app.models.presentation import Presentation
from app.models.requirements import PresentationRequirements
from app.models.selective_regeneration import (
    SelectiveRegenerationResult,
    SelectiveRegenerationStatus,
)
from app.rendering import render_presentation
from app.services.change_analyzer import ChangeAnalyzer
from app.services.slide_regenerator import SlideRegenerator


class SelectiveRegenerator:
    """Regenerate affected slides while leaving every other slide intact."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        shared_provider = provider or GeminiProvider()
        self._change_analyzer = ChangeAnalyzer(shared_provider)
        self._slide_regenerator = SlideRegenerator(shared_provider)

    def selectively_regenerate(
        self,
        presentation: Presentation,
        requirements: PresentationRequirements,
        modification_request: str,
        output_path: str | Path | None = None,
    ) -> SelectiveRegenerationResult:
        """Analyze a request and, when local, regenerate its affected slides."""
        original = Presentation.model_validate(presentation)
        requirements = PresentationRequirements.model_validate(requirements)
        request = modification_request.strip()
        if not request:
            raise ValueError("The modification request must not be empty.")

        analysis = self._change_analyzer.analyze(original, request)
        slide_by_id = {slide.id: slide for slide in original.slides}
        ordered_ids = [slide.id for slide in sorted(original.slides, key=lambda item: item.order)]

        if analysis.change_type == ChangeType.UNCLEAR:
            return SelectiveRegenerationResult(
                status=SelectiveRegenerationStatus.CLARIFICATION_NEEDED,
                presentation=original.model_copy(deep=True),
                clarification_needed=True,
                message=analysis.instruction,
                total_slide_count=len(original.slides),
            )

        if analysis.change_type == ChangeType.GLOBAL:
            return SelectiveRegenerationResult(
                status=SelectiveRegenerationStatus.GLOBAL_CHANGE,
                presentation=original.model_copy(deep=True),
                affected_slides=ordered_ids,
                preserved_slides=ordered_ids,
                message="This request affects the full presentation and requires the baseline/full-regeneration path.",
                total_slide_count=len(original.slides),
            )

        affected = sorted(analysis.affected_slides, key=lambda slide_id: slide_by_id[slide_id].order)
        replacements = {}
        for slide_id in affected:
            current = slide_by_id[slide_id]
            plan = PlannedSlide(
                id=current.id,
                order=current.order,
                purpose=current.purpose,
                layout=current.layout,
            )
            replacements[slide_id] = self._slide_regenerator.regenerate(
                presentation=original,
                requirements=requirements,
                planned_slide=plan,
                current_slide=current,
                modification_request=request,
                instruction=analysis.instruction,
                change_type=analysis.change_type,
            )

        slides = [
            replacements.get(slide.id, slide.model_copy(deep=True))
            for slide in original.slides
        ]
        updated = Presentation.model_validate(
            {
                **original.model_dump(mode="python"),
                "slides": slides,
            }
        )
        preserved = [slide_id for slide_id in ordered_ids if slide_id not in replacements]
        for slide_id in preserved:
            updated_slide = next(item for item in updated.slides if item.id == slide_id)
            if updated_slide.model_dump(mode="json") != slide_by_id[slide_id].model_dump(mode="json"):
                raise ValueError(f"Unaffected slide {slide_id} changed during selective regeneration.")

        if output_path is None:
            generated_dir = Path(__file__).resolve().parents[2] / "generated"
            output_path = generated_dir / f"selective_regeneration_{uuid4().hex}.pptx"
        saved_path = render_presentation(updated, output_path)
        return SelectiveRegenerationResult(
            status=SelectiveRegenerationStatus.REGENERATED,
            presentation=updated,
            affected_slides=affected,
            regenerated_slides=affected,
            preserved_slides=preserved,
            message=f"Regenerated {len(affected)} affected slide(s).",
            total_slide_count=len(updated.slides),
            output_path=saved_path,
        )
