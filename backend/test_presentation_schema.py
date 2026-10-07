"""Manual smoke test for the presentation Pydantic schema."""

from pydantic import ValidationError

from app.models.presentation import (
    ComponentType,
    Presentation,
    SlideLayout,
)


def main() -> None:
    sample = Presentation(
        id="pres_ai_healthcare",
        title="AI in Healthcare",
        metadata={"audience": "B.Tech students", "tone": "academic", "slide_count": 2},
        slides=[
            {
                "id": "slide_01",
                "order": 1,
                "layout": SlideLayout.TITLE,
                "purpose": "Introduce the topic",
                "components": [
                    {
                        "id": "slide_01_title",
                        "type": ComponentType.TITLE,
                        "content": {"text": "AI in Healthcare"},
                    },
                    {
                        "id": "slide_01_subtitle",
                        "type": ComponentType.TEXT,
                        "content": {"text": "Applications, benefits, and challenges"},
                    },
                ],
            },
            {
                "id": "slide_02",
                "order": 2,
                "layout": SlideLayout.TITLE_BULLETS,
                "purpose": "Introduce key applications",
                "components": [
                    {
                        "id": "slide_02_bullets",
                        "type": ComponentType.BULLET_LIST,
                        "content": {"items": ["Medical imaging", "Clinical decision support"]},
                    }
                ],
            },
        ],
    )

    serialized = sample.model_dump_json(indent=2)
    restored = Presentation.model_validate_json(serialized)
    assert restored == sample

    invalid_data = sample.model_dump()
    invalid_data["slides"][0]["order"] = 0
    try:
        Presentation.model_validate(invalid_data)
    except ValidationError:
        pass
    else:
        raise AssertionError("Invalid slide order was accepted.")

    print(serialized)
    print("Schema round-trip and invalid-data rejection: passed")


if __name__ == "__main__":
    main()
