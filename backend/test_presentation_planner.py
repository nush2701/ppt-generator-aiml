"""Live Gemini integration checks for presentation planning."""

import sys

from pydantic import ValidationError

from app.llm.gemini_provider import GeminiProviderError
from app.models.plan import PresentationPlan
from app.models.presentation import SlideLayout
from app.models.requirements import PresentationRequirements
from app.services.presentation_planner import PresentationPlanner


def create_requirements(
    *,
    topic: str,
    audience: str | None,
    slide_count: int | None,
    tone: str | None,
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


def create_plan_or_fail(
    planner: PresentationPlanner,
    label: str,
    requirements: PresentationRequirements,
) -> PresentationPlan:
    try:
        plan = planner.plan(requirements)
    except (GeminiProviderError, ValidationError, ValueError) as exc:
        raise RuntimeError(f"{label} planning request failed: {exc}") from exc

    if not isinstance(plan, PresentationPlan):
        raise RuntimeError(f"{label} did not return a PresentationPlan.")
    return plan


def validate_plan(plan: PresentationPlan, label: str) -> None:
    ids = [slide.id for slide in plan.slides]
    orders = [slide.order for slide in plan.slides]

    assert len(ids) == len(set(ids)), f"{label}: slide IDs are not unique."
    assert orders == list(range(1, len(plan.slides) + 1)), (
        f"{label}: slide orders are not sequential."
    )
    assert all(slide.layout in SlideLayout for slide in plan.slides), (
        f"{label}: plan contains an unsupported layout."
    )


def main() -> None:
    try:
        planner = PresentationPlanner()
    except GeminiProviderError as exc:
        raise SystemExit(f"Could not initialize presentation planner: {exc}") from exc

    failures: list[str] = []

    try:
        specified_count = create_requirements(
            topic="AI in healthcare",
            audience="college students",
            slide_count=7,
            tone="professional",
            key_requirements=["Include a conclusion"],
        )
        first_plan = create_plan_or_fail(planner, "Specified-count case", specified_count)
        print("Specified-count plan:")
        print(first_plan.model_dump_json(indent=2))
        assert len(first_plan.slides) == 7, "Specified-count case must return exactly 7 slides."
        validate_plan(first_plan, "Specified-count case")
        assert first_plan.slides[0].layout == SlideLayout.TITLE, (
            "The first slide must use the title layout."
        )
        assert first_plan.slides[-1].layout == SlideLayout.CONCLUSION, (
            "The final slide must use the conclusion layout."
        )
    except (RuntimeError, AssertionError) as exc:
        failures.append(str(exc))
        print(f"{exc}", file=sys.stderr)

    try:
        unspecified_count = create_requirements(
            topic="renewable energy",
            audience=None,
            slide_count=None,
            tone=None,
            key_requirements=[],
        )
        second_plan = create_plan_or_fail(planner, "Unspecified-count case", unspecified_count)
        print("Unspecified-count plan:")
        print(second_plan.model_dump_json(indent=2))
        assert 5 <= len(second_plan.slides) <= 8, (
            "Unspecified-count case must return between 5 and 8 slides."
        )
        validate_plan(second_plan, "Unspecified-count case")
    except (RuntimeError, AssertionError) as exc:
        failures.append(str(exc))
        print(f"{exc}", file=sys.stderr)

    if failures:
        raise SystemExit(f"{len(failures)} live Gemini presentation-planning check(s) failed.")
    print("Both live Gemini presentation-planning checks passed.")


if __name__ == "__main__":
    main()
