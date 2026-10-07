"""Live Gemini checks for the baseline full-presentation regeneration method."""

from pathlib import Path
from uuid import uuid4

from pptx import Presentation as PowerPoint

from app.models.full_regeneration import FullRegenerationStatus
from app.models.presentation import (
    ComponentType,
    Presentation,
    PresentationMetadata,
    Slide,
    SlideComponent,
    SlideLayout,
)
from app.models.requirements import PresentationRequirements
from app.services.full_regenerator import FullRegenerator


def make_presentation() -> Presentation:
    """Build a deterministic, identifiable five-slide source presentation."""
    titles = [
        "Introduction",
        "Solar Energy",
        "Renewable Energy Comparison",
        "Energy Transition",
        "Conclusion",
    ]
    layouts = [
        SlideLayout.TITLE,
        SlideLayout.TITLE_BULLETS,
        SlideLayout.COMPARISON,
        SlideLayout.TITLE_BULLETS,
        SlideLayout.CONCLUSION,
    ]
    slides = []
    for index, (title, layout) in enumerate(zip(titles, layouts, strict=True), start=1):
        components = [
            SlideComponent(
                id=f"slide-{index}-title",
                type=ComponentType.TITLE,
                content=title,
            )
        ]
        if index == 3:
            components.append(
                SlideComponent(
                    id="slide-3-table",
                    type=ComponentType.TABLE,
                    content={
                        "headers": ["Source", "Driver"],
                        "rows": ["Solar", "Sunlight", "Wind", "Air currents"],
                    },
                )
            )
        elif index > 1:
            components.append(
                SlideComponent(
                    id=f"slide-{index}-body",
                    type=ComponentType.TEXT,
                    content=f"Current content for {title.lower()}.",
                )
            )
        slides.append(
            Slide(
                id=f"slide-{index}",
                order=index,
                layout=layout,
                purpose=f"Explain {title.lower()}.",
                components=components,
            )
        )

    return Presentation(
        id=f"presentation-full-test-{uuid4().hex}",
        title="Renewable Energy",
        metadata=PresentationMetadata(
            root={
                "topic": "renewable energy",
                "purpose": None,
                "audience": "college students",
                "slide_count": 5,
                "tone": "professional",
                "language": "English",
                "key_requirements": [],
                "constraints": [],
            }
        ),
        slides=slides,
    )


REQUIREMENTS = PresentationRequirements(
    topic="renewable energy",
    purpose=None,
    audience="college students",
    slide_count=5,
    tone="professional",
    language="English",
    key_requirements=[],
    constraints=[],
)


def serialized(presentation: Presentation) -> str:
    return presentation.model_dump_json()


def verify_deck(path: Path) -> None:
    assert path.is_file(), f"PowerPoint was not created: {path}"
    assert path.stat().st_size > 0, "PowerPoint file is empty"
    opened = PowerPoint(path)
    assert len(opened.slides) == 5, f"Expected five slides; got {len(opened.slides)}"


def main() -> None:
    service = FullRegenerator()
    source = make_presentation()
    original_id = source.id
    original_json = serialized(source)
    initial_slide_ids = [f"slide-{number}" for number in range(1, 6)]

    unclear = service.fully_regenerate(source, REQUIREMENTS, "Change it.")
    assert unclear.status == FullRegenerationStatus.CLARIFICATION_NEEDED, unclear.message
    assert unclear.regenerated_slides == []
    assert unclear.output_path is None
    assert serialized(unclear.presentation) == original_json
    assert serialized(source) == original_json

    local_output = Path(__file__).parent / "generated" / f"full_regeneration_{uuid4().hex}.pptx"
    local = service.fully_regenerate(
        source,
        REQUIREMENTS,
        "Change slide 3 to compare solar and wind energy instead.",
        output_path=local_output,
    )
    assert local.status == FullRegenerationStatus.REGENERATED, local.message
    assert local.presentation is not source, "Expected a newly generated Presentation object."
    assert local.presentation.id == original_id
    assert local.regenerated_slides == initial_slide_ids, local.regenerated_slides
    assert len(local.presentation.slides) == 5
    verify_deck(local_output)
    assert serialized(source) == original_json, "Full regeneration mutated the original object."

    global_output = Path(__file__).parent / "generated" / f"full_regeneration_{uuid4().hex}.pptx"
    global_result = service.fully_regenerate(
        source,
        REQUIREMENTS,
        "Make the entire presentation more professional.",
        output_path=global_output,
    )
    assert global_result.status == FullRegenerationStatus.REGENERATED, global_result.message
    assert global_result.presentation.id == original_id
    assert global_result.regenerated_slides == initial_slide_ids
    verify_deck(global_output)
    assert serialized(source) == original_json

    print(f"Ambiguous request: {unclear.status.value}; no deck created.")
    print(f"Localized request status: {local.status.value}")
    print(f"Localized request regenerated slides: {local.regenerated_slides}")
    print(f"Localized request PPTX: {local_output}")
    print(f"Global request status: {global_result.status.value}")
    print(f"Global request regenerated slides: {global_result.regenerated_slides}")
    print(f"Global request PPTX: {global_output}")
    print("Live Gemini full-regeneration checks passed.")


if __name__ == "__main__":
    main()
