"""Generate concise slide content for an existing validated presentation plan."""

import json
from uuid import uuid4

from app.llm.gemini_provider import GeminiProvider
from app.llm.provider import LLMProvider
from app.models.plan import PresentationPlan
from app.models.presentation import ComponentType, Presentation
from app.models.requirements import PresentationRequirements


class SlideGenerator:
    """Use the configured LLM provider to populate a plan with slide components."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider or GeminiProvider()

    def generate(
        self,
        requirements: PresentationRequirements,
        plan: PresentationPlan,
        presentation_id: str | None = None,
    ) -> Presentation:
        """Generate a validated presentation while preserving the supplied plan."""
        requirements = PresentationRequirements.model_validate(requirements)
        plan = PresentationPlan.model_validate(plan)
        presentation_id = presentation_id or f"presentation-{uuid4().hex}"
        metadata = {
            "topic": requirements.topic,
            "purpose": requirements.purpose,
            "audience": requirements.audience,
            "slide_count": len(plan.slides),
            "tone": requirements.tone,
            "language": requirements.language,
            "key_requirements": requirements.key_requirements,
            "constraints": requirements.constraints,
        }

        generation_prompt = self._build_prompt(
            requirements=requirements,
            plan=plan,
            presentation_id=presentation_id,
            metadata=metadata,
        )
        presentation = self._provider.generate_structured(
            prompt=generation_prompt,
            response_model=Presentation,
        )
        presentation = Presentation.model_validate(presentation)
        self._validate_against_plan(
            presentation=presentation,
            plan=plan,
            presentation_id=presentation_id,
            metadata=metadata,
        )
        return presentation

    def _build_prompt(
        self,
        requirements: PresentationRequirements,
        plan: PresentationPlan,
        presentation_id: str,
        metadata: dict[str, object],
    ) -> str:
        requirements_json = requirements.model_dump_json(indent=2, exclude_none=False)
        plan_json = plan.model_dump_json(indent=2)
        metadata_json = json.dumps(metadata, indent=2, ensure_ascii=False)
        component_types = ", ".join(f'"{kind.value}"' for kind in ComponentType)

        return f"""ROLE
You are a concise presentation content writer. Create clear, audience-appropriate content for the supplied slide plan.

TASK
Generate actual slide content for the existing plan. Do not create a new presentation plan.

PRESENTATION REQUIREMENTS
```json
{requirements_json}
```

PRESENTATION PLAN — SOURCE OF TRUTH FOR SLIDE STRUCTURE
```json
{plan_json}
```

CONTENT-GENERATION RULES
- Follow the plan exactly. Do not add or remove slides.
- Preserve every planned slide ID, order, layout, and purpose exactly.
- Use presentation ID `{presentation_id}` and presentation title `{plan.title}` exactly.
- Use this exact metadata object:
```json
{metadata_json}
```
- Generate content appropriate for the stated audience, tone, and language. When one is null, do not assume a specific audience, tone, or language.
- Keep content concise and presentation-friendly. Avoid essay-length paragraphs, excessive bullets, long card text, and repetition. Use about 3–6 bullets when a bullet list is appropriate.
- Do not create unsupported sections or invent factual claims, precise statistics, sources, or citations. Use cautious wording for general factual statements.
- Do not generate speaker notes, image assets, or design instructions. Component properties may contain only concise semantic data needed to interpret the component, not visual styling directions.
- Component IDs must be predictable, unique, and start with their slide ID followed by a hyphen, for example `slide-1-title`, `slide-1-bullets`, or `slide-2-card-1`.
- Use only these component types: {component_types}.
- Every component must have non-empty content.

LAYOUT / COMPONENT RULES
- `title`: a title component and optionally a short text subtitle.
- `title_bullets`: a title component and a concise bullet_list component.
- `two_column`: a title component and two text or card components, one for each column.
- `comparison`: a title component and comparison content using a table or suitable cards/text.
- `three_card`: a title component and three concise card components.
- `image_text`: a title, an image component describing the intended image subject as a placeholder, and a related text component. Do not create or link an image.
- `timeline`: a title component and a timeline component with concise ordered steps. Do not invent dates.
- `statistic`: a title and a statistic component. Do not invent numeric values; use only figures supplied in the requirements or plan context, or express a supported metric qualitatively.
- `conclusion`: a title and concise concluding text or a short bullet_list.
- If a planned layout needs a different valid combination to represent its purpose, keep the content semantically appropriate while using only allowed component types.

STRUCTURED OUTPUT REQUIREMENT
Return one JSON object matching the provided Presentation schema, with `id`, `title`, `metadata`, and `slides`. Do not include markdown or text outside the JSON object."""

    @staticmethod
    def _has_nonempty_content(value: object) -> bool:
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, dict):
            return any(SlideGenerator._has_nonempty_content(item) for item in value.values())
        if isinstance(value, list):
            return any(SlideGenerator._has_nonempty_content(item) for item in value)
        return value is not None

    @classmethod
    def _validate_against_plan(
        cls,
        presentation: Presentation,
        plan: PresentationPlan,
        presentation_id: str,
        metadata: dict[str, object],
    ) -> None:
        if presentation.id != presentation_id:
            raise ValueError("Generated presentation ID does not match the requested ID.")
        if presentation.title != plan.title:
            raise ValueError("Generated presentation title does not match the plan.")
        if presentation.metadata.root != metadata:
            raise ValueError("Generated presentation metadata does not match the requirements.")
        if len(presentation.slides) != len(plan.slides):
            raise ValueError("Generated slide count does not match the presentation plan.")

        component_ids: set[str] = set()
        for generated_slide, planned_slide in zip(presentation.slides, plan.slides, strict=True):
            if (
                generated_slide.id != planned_slide.id
                or generated_slide.order != planned_slide.order
                or generated_slide.layout != planned_slide.layout
                or generated_slide.purpose != planned_slide.purpose
            ):
                raise ValueError(
                    f"Generated structure for {planned_slide.id} does not match the presentation plan."
                )
            if not generated_slide.components:
                raise ValueError(f"Generated slide {planned_slide.id} has no components.")

            for component in generated_slide.components:
                if not isinstance(component.type, ComponentType):
                    raise ValueError(f"Component {component.id} has an unsupported type.")
                if component.id in component_ids:
                    raise ValueError(f"Duplicate component ID: {component.id}.")
                component_ids.add(component.id)
                if not component.id.startswith(f"{planned_slide.id}-"):
                    raise ValueError(
                        f"Component ID {component.id} must start with {planned_slide.id}-."
                    )
                if not cls._has_nonempty_content(component.content):
                    raise ValueError(f"Component {component.id} has empty content.")
