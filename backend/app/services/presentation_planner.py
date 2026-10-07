"""Create a structured slide plan from validated presentation requirements."""

from app.llm.gemini_provider import GeminiProvider
from app.llm.provider import LLMProvider
from app.models.plan import PresentationPlan
from app.models.presentation import SlideLayout
from app.models.requirements import PresentationRequirements


class PresentationPlanner:
    """Use the configured LLM provider to plan slide purposes and layouts."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider or GeminiProvider()

    def plan(self, requirements: PresentationRequirements) -> PresentationPlan:
        """Return a validated plan without generating slide content."""
        requirements = PresentationRequirements.model_validate(requirements)
        requirements_json = requirements.model_dump_json(indent=2, exclude_none=False)
        allowed_layouts = ", ".join(f'"{layout.value}"' for layout in SlideLayout)

        planning_prompt = f"""ROLE
You are a presentation planner. Create a coherent, audience-aware sequence of slide purposes and layouts.

TASK
Plan the presentation from the validated requirements below. Decide the slide count when it is unspecified, then assign each slide a distinct purpose and one allowed layout.

PRESENTATION REQUIREMENTS
```json
{requirements_json}
```

PLANNING RULES
- Follow the extracted requirements and preserve their constraints.
- If slide_count is a number, return exactly that many slides.
- If slide_count is null, choose a reasonable 5–8 slides based on topic complexity; avoid unnecessarily large plans.
- Give every slide a distinct, concise purpose and arrange the slides in a logical sequence.
- Choose layouts based on the kind of information: use comparison for comparing alternatives, timeline for chronological processes, and statistic for numerical or key-metric topics when appropriate.
- Use "title" for the opening slide.
- Use "conclusion" for the final slide when the request calls for a conclusion or a closing summary is appropriate.
- Do not generate detailed slide text, paragraphs, bullet content, or factual claims.
- Do not add unsupported requirements or invent factual claims.
- Use stable slide IDs in the form "slide-1", "slide-2", and so on, matching sequential order values beginning at 1.
- Use only these allowed layouts: {allowed_layouts}.

STRUCTURED OUTPUT REQUIREMENT
Return one JSON object matching the provided PresentationPlan schema. Include a title and a non-empty slides array. Do not include markdown or text outside the JSON object."""

        result = self._provider.generate_structured(
            prompt=planning_prompt,
            response_model=PresentationPlan,
        )
        return PresentationPlan.model_validate(result)
