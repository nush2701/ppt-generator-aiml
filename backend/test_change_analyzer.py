"""Live Gemini checks for smallest-scope presentation change analysis."""

from app.models.change import ChangeType
from app.llm.gemini_provider import GeminiProviderError
from app.models.presentation import (
    ComponentType,
    Presentation,
    PresentationMetadata,
    Slide,
    SlideComponent,
    SlideLayout,
)
from app.services.change_analyzer import ChangeAnalyzer


def component(identifier: str, kind: ComponentType, content) -> SlideComponent:
    return SlideComponent(id=identifier, type=kind, content=content)


def fixture_presentation() -> Presentation:
    return Presentation(
        id="change-analysis-fixture",
        title="Renewable Energy",
        metadata=PresentationMetadata(root={}),
        slides=[
            Slide(
                id="slide-1", order=1, layout=SlideLayout.TITLE,
                purpose="Introduce renewable energy",
                components=[component("slide-1-title", ComponentType.TITLE, "Renewable Energy")],
            ),
            Slide(
                id="slide-2", order=2, layout=SlideLayout.TITLE_BULLETS,
                purpose="Describe major renewable sources",
                components=[
                    component("slide-2-title", ComponentType.TITLE, "Renewable Sources"),
                    component("slide-2-bullets", ComponentType.BULLET_LIST, {"items": ["Solar", "Wind", "Hydro"]}),
                ],
            ),
            Slide(
                id="slide-3", order=3, layout=SlideLayout.COMPARISON,
                purpose="Compare energy sources",
                components=[
                    component("slide-3-title", ComponentType.TITLE, "Source Comparison"),
                    component("slide-3-table", ComponentType.TABLE, {
                        "headers": ["Source", "Driver"],
                        "rows": [["Solar", "Sunlight"], ["Wind", "Air currents"]],
                    }),
                ],
            ),
            Slide(
                id="slide-4", order=4, layout=SlideLayout.STATISTIC,
                purpose="Present a key energy statistic",
                components=[
                    component("slide-4-title", ComponentType.TITLE, "Energy at a Glance"),
                    component("slide-4-statistic", ComponentType.STATISTIC, {
                        "value": "42%", "label": "Example share of generation",
                    }),
                ],
            ),
        ],
    )


def main() -> None:
    analyzer = ChangeAnalyzer()
    presentation = fixture_presentation()
    cases = [
        (
            "CASE 1 — target comparison table",
            "Change slide 3 to compare solar and wind instead.",
        ),
        (
            "CASE 2 — target title component",
            "Change the title of slide 2 to 'Major Renewable Energy Sources'.",
        ),
        ("CASE 3 — concise slide", "Make slide 4 more concise."),
        ("CASE 4 — global scope", "Make the whole presentation more professional."),
        ("CASE 5 — ambiguous request", "Change it."),
    ]

    results = []
    for label, request in cases:
        print(label)
        try:
            result = analyzer.analyze(presentation, request)
        except GeminiProviderError as exc:
            # A real SDK connection can be closed between requests; retry only transient transport failures.
            error = str(exc)
            transient_network_error = any(
                marker in error for marker in ("WinError 10054", "WinError 10061", "ConnectError", "ReadError")
            )
            if not transient_network_error:
                raise
            print(f"Transient Gemini connection failure; retrying this real case with a fresh client: {error}")
            analyzer = ChangeAnalyzer()
            result = analyzer.analyze(presentation, request)
        print(result.model_dump_json(indent=2))
        results.append(result)

    first, second, third, fourth, fifth = results
    assert first.affected_slides == ["slide-3"]
    assert "slide-3-table" in first.affected_components
    assert first.requires_regeneration is True

    assert second.affected_slides == ["slide-2"]
    assert "slide-2-title" in second.affected_components
    assert not {"slide-3", "slide-4"}.intersection(second.affected_slides)
    assert second.requires_regeneration is True

    assert third.affected_slides == ["slide-4"]
    assert not {"slide-1", "slide-2", "slide-3"}.intersection(third.affected_slides)
    assert third.requires_regeneration is True

    all_slide_ids = {slide.id for slide in presentation.slides}
    assert fourth.change_type == ChangeType.GLOBAL
    assert set(fourth.affected_slides) == all_slide_ids
    assert len(fourth.affected_slides) > 1
    assert fourth.requires_regeneration is True

    assert fifth.change_type == ChangeType.UNCLEAR
    assert fifth.affected_slides == []
    assert fifth.affected_components == []
    assert fifth.requires_regeneration is False

    print("All five live Gemini change-analysis cases passed.")


if __name__ == "__main__":
    main()
