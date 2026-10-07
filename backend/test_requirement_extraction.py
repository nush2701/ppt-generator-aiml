"""Integration checks for requirement extraction using live Gemini calls."""

import sys

from pydantic import ValidationError

from app.models.requirements import PresentationRequirements
from app.services.requirement_extractor import RequirementExtractor
from app.llm.gemini_provider import GeminiProviderError


def extract_or_fail(extractor: RequirementExtractor, label: str, prompt: str) -> PresentationRequirements:
    try:
        result = extractor.extract(prompt)
    except (GeminiProviderError, ValidationError, ValueError) as exc:
        raise RuntimeError(f"{label} requirement extraction failed: {exc}") from exc

    if not isinstance(result, PresentationRequirements):
        raise RuntimeError(f"{label} extraction did not return PresentationRequirements.")
    return result


def main() -> None:
    try:
        extractor = RequirementExtractor()
    except GeminiProviderError as exc:
        raise SystemExit(f"Could not initialize requirement extraction: {exc}") from exc

    failures: list[str] = []

    try:
        realistic = extract_or_fail(
            extractor,
            "Realistic request",
            "Create a 7-slide presentation about AI in healthcare for college students. "
            "Keep it professional and include a conclusion.",
        )
        print("Realistic request:")
        print(realistic.model_dump_json(indent=2))
        assert realistic.slide_count == 7, "The explicit slide count was not preserved."
        assert realistic.audience is not None and "college" in realistic.audience.lower(), (
            "The explicit audience was not preserved."
        )
        assert realistic.tone is not None and "professional" in realistic.tone.lower(), (
            "The explicit tone was not preserved."
        )
        assert any("conclusion" in item.lower() for item in realistic.key_requirements), (
            "The requested conclusion was not preserved."
        )
    except (RuntimeError, AssertionError) as exc:
        failures.append(str(exc))
        print(f"{exc}", file=sys.stderr)

    try:
        underspecified = extract_or_fail(
            extractor,
            "Underspecified request",
            "Make a presentation about renewable energy.",
        )
        print("Underspecified request:")
        print(underspecified.model_dump_json(indent=2))
        assert underspecified.audience is None, (
            "An audience was invented for an underspecified request."
        )
        assert underspecified.slide_count is None, (
            "A slide count was invented for an underspecified request."
        )
    except (RuntimeError, AssertionError) as exc:
        failures.append(str(exc))
        print(f"{exc}", file=sys.stderr)

    if failures:
        raise SystemExit(f"{len(failures)} live Gemini requirement-extraction check(s) failed.")
    print("Both live Gemini requirement-extraction checks passed.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"Requirement extraction assertion failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
