"""Live Gemini integration checks for structured slide content generation."""

import sys

from pydantic import ValidationError

from app.llm.gemini_provider import GeminiProviderError
from app.models.plan import PresentationPlan
from app.models.presentation import ComponentType, Presentation
from app.models.requirements import PresentationRequirements
from app.services.slide_generator import SlideGenerator


def make_requirements(
    *,
    topic: str,
    audience: str,
    slide_count: int,
    tone: str,
    key_requirements: list[str],
) -> PresentationRequirements:
    return PresentationRequirements(
        topic=topic,
        purpose=None,
        audience=audience,
        slide_count=slide_count,
        tone=tone,
        language=None,
        key_requirements=key_requirements,
        constraints=[],
    )


def make_plan(title: str, layouts: list[str], purposes: list[str]) -> PresentationPlan:
    return PresentationPlan(
        title=title,
        slides=[
            {
                "id": f"slide-{index}",
                "order": index,
                "purpose": purpose,
                "layout": layout,
            }
            for index, (layout, purpose) in enumerate(zip(layouts, purposes, strict=True), start=1)
        ],
    )


def generate_or_fail(
    generator: SlideGenerator,
    label: str,
    requirements: PresentationRequirements,
    plan: PresentationPlan,
) -> Presentation:
    try:
        presentation = generator.generate(requirements, plan)
    except (GeminiProviderError, ValidationError, ValueError) as exc:
        raise RuntimeError(f"{label} slide generation failed: {exc}") from exc

    if not isinstance(presentation, Presentation):
        raise RuntimeError(f"{label} did not return a Presentation model.")
    return presentation


def has_content(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(has_content(item) for item in value.values())
    if isinstance(value, list):
        return any(has_content(item) for item in value)
    return value is not None


def verify_presentation(
    presentation: Presentation,
    plan: PresentationPlan,
    label: str,
) -> None:
    assert len(presentation.slides) == len(plan.slides), f"{label}: extra or missing slides."
    all_component_ids: set[str] = set()

    for actual, planned in zip(presentation.slides, plan.slides, strict=True):
        assert actual.id == planned.id, f"{label}: slide ID changed."
        assert actual.order == planned.order, f"{label}: slide order changed."
        assert actual.layout == planned.layout, f"{label}: slide layout changed."
        assert actual.purpose == planned.purpose, f"{label}: slide purpose changed."
        assert actual.components, f"{label}: {actual.id} has no components."

        for component in actual.components:
            assert isinstance(component.type, ComponentType), (
                f"{label}: unsupported component type on {actual.id}."
            )
            assert component.id not in all_component_ids, (
                f"{label}: duplicate component ID {component.id}."
            )
            all_component_ids.add(component.id)
            assert component.id.startswith(f"{actual.id}-"), (
                f"{label}: component ID {component.id} lacks the slide ID prefix."
            )
            assert has_content(component.content), f"{label}: empty component {component.id}."


def main() -> None:
    try:
        generator = SlideGenerator()
    except GeminiProviderError as exc:
        raise SystemExit(f"Could not initialize slide generator: {exc}") from exc

    cases = [
        (
            "AI in healthcare",
            make_requirements(
                topic="AI in healthcare",
                audience="college students",
                slide_count=7,
                tone="professional",
                key_requirements=["Include a conclusion"],
            ),
            make_plan(
                "AI in Healthcare",
                [
                    "title",
                    "title_bullets",
                    "statistic",
                    "comparison",
                    "three_card",
                    "timeline",
                    "conclusion",
                ],
                [
                    "Introduce AI in healthcare",
                    "Summarize major clinical applications",
                    "Describe an evidence-aware key metric",
                    "Compare traditional and AI-supported workflows",
                    "Present three areas of healthcare use",
                    "Show a responsible adoption sequence",
                    "Summarize the key takeaways",
                ],
            ),
        ),
        (
            "Renewable energy",
            make_requirements(
                topic="renewable energy",
                audience="general readers",
                slide_count=5,
                tone="clear and informative",
                key_requirements=[],
            ),
            make_plan(
                "Renewable Energy",
                ["title", "title_bullets", "comparison", "timeline", "conclusion"],
                [
                    "Introduce renewable energy",
                    "Explain major renewable energy sources",
                    "Compare common renewable energy sources",
                    "Outline a high-level energy transition sequence",
                    "Summarize the main points",
                ],
            ),
        ),
    ]

    failures: list[str] = []
    for label, requirements, plan in cases:
        try:
            presentation = generate_or_fail(generator, label, requirements, plan)
            verify_presentation(presentation, plan, label)
            print(f"{label} presentation:")
            print(presentation.model_dump_json(indent=2))
        except (RuntimeError, AssertionError) as exc:
            failures.append(str(exc))
            print(f"{exc}", file=sys.stderr)

    if failures:
        raise SystemExit(f"{len(failures)} live Gemini slide-generation check(s) failed.")
    print("Both live Gemini slide-generation checks passed.")


if __name__ == "__main__":
    main()
