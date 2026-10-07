# System Architecture

## 1. Architecture Overview

The application converts a natural-language presentation request into a validated structured representation and then deterministically renders that representation into a PowerPoint file.

The system has two major workflows:

1. Initial presentation generation
2. Modification and selective regeneration

The architecture separates AI-based reasoning from deterministic PowerPoint rendering.

The LLM decides what the presentation should contain.

The deterministic rendering engine decides how that content is represented in PowerPoint.

---

# 2. High-Level System Architecture

```text
                         USER
                           |
                           v
                  +------------------+
                  |    Next.js UI    |
                  | React + TypeScript|
                  +--------+---------+
                           |
                           | HTTP / JSON
                           v
                  +------------------+
                  |     FastAPI      |
                  |     Backend      |
                  +--------+---------+
                           |
              +------------+------------+
              |                         |
              v                         v
      +---------------+         +-------------------+
      |  Generation   |         |  Modification     |
      |   Pipeline    |         |    Pipeline       |
      +-------+-------+         +---------+---------+
              |                           |
              v                           v
      +---------------+         +-------------------+
      | Requirement   |         | Change Analyzer   |
      | Analyst       |         +---------+---------+
      +-------+-------+                   |
              |                           v
              v                 +-------------------+
      +---------------+         | Selective         |
      | Presentation  |         | Regenerator       |
      | Planner       |         +---------+---------+
      +-------+-------+                   |
              |                           |
              v                           |
      +---------------+                   |
      | Content       |<------------------+
      | Generator     |
      +-------+-------+
              |
              v
      +---------------+
      | Pydantic      |
      | Validation    |
      +-------+-------+
              |
              v
      +---------------+
      | Layout Engine |
      +-------+-------+
              |
              v
      +---------------+
      | python-pptx   |
      +-------+-------+
              |
              v
          .pptx file
              |
              v
       Metrics Logger

3. Frontend Architecture
The frontend uses:
- Next.js
- React
- TypeScript
- Tailwind CSS
The frontend is responsible for:
- Accepting the user's presentation prompt
- Sending requests to the backend
- Showing generation status
- Displaying basic presentation information
- Accepting modification requests
- Providing the generated .pptx file for download
- Displaying errors to the user
The frontend should NOT contain:
- LLM API keys
- LLM prompt logic
- PowerPoint rendering logic
- Core presentation generation logic
These belong in the backend.
4. Backend Architecture
The backend uses:
- Python
- FastAPI
- Pydantic
The backend is responsible for:
- API endpoints
- Request validation
- LLM interaction
- Prompt execution
- Presentation schema validation
- Presentation generation
- Modification analysis
- Selective regeneration
- PPT rendering
- Metrics collection
- File management
5. LLM Provider Architecture
The application must keep the LLM layer provider-agnostic.
Conceptually:
                    LLMProvider
                         |
             +-----------+-----------+
             |           |           |
             v           v           v
          Gemini       Groq      OpenRouter

Only Gemini is required for the initial implementation.
The rest are possible future providers.
Application services should depend on the LLMProvider abstraction rather than directly depending on Gemini-specific code.
This allows the model/provider to be changed later without rewriting the entire application.
6. Generation Pipeline
The initial presentation generation flow is:
User Prompt
     |
     v
Requirement Extraction
     |
     v
Structured Requirements
     |
     v
Presentation Planning
     |
     v
Slide Plan
     |
     v
Slide Content Generation
     |
     v
Pydantic Validation
     |
     v
Presentation JSON
     |
     v
Layout Renderer
     |
     v
python-pptx
     |
     v
.pptx

Each stage should be independently testable.
7. Requirement Analyst
Input
Natural-language user prompt.
Example:
Create a 10-slide presentation about AI in healthcare
for B.Tech students.
Use a professional academic tone.

Output
Structured requirements such as:
topic
audience
slide_count
tone
visual_style
required_sections
constraints

The output must be validated using Pydantic.
8. Presentation Planner
The planner receives structured requirements.
It produces a slide plan.
Each slide should contain information such as:
slide_id
purpose
recommended_layout
key_information

Example:
slide_01
Purpose: Introduce AI in healthcare
Layout: title

slide_02
Purpose: Explain major applications
Layout: three_cards

slide_03
Purpose: Explain benefits
Layout: title_bullets

The planner should not directly create PowerPoint objects.
9. Content Generator
The content generator receives:
- Slide specification
- Relevant presentation context
- Layout schema
- User requirements where necessary
It generates structured slide content.
Example:
Slide
 |
 +-- id
 +-- order
 +-- layout
 +-- purpose
 +-- components

The generated output must be validated before it reaches the renderer.
10. Presentation Data Flow
The LLM must NOT directly manipulate PowerPoint objects.
The data flow must remain:
Natural Language
       |
       v
      LLM
       |
       v
Structured JSON
       |
       v
Pydantic Models
       |
       v
Validated Presentation
       |
       v
Layout Renderer
       |
       v
python-pptx
       |
       v
.pptx

This separation is important for:
- Reliability
- Validation
- Reproducibility
- Debugging
- Selective regeneration
- Testing
11. Presentation Data Model
The core object hierarchy is:
Presentation
 |
 +-- id
 +-- title
 +-- theme
 +-- metadata
 |
 +-- slides[]
       |
       +-- id
       +-- order
       +-- layout
       +-- purpose
       +-- components

Every slide must have a stable ID.
Every important component should also have a stable ID.
Example:
presentation
 |
 +-- slide_01
 |     +-- slide_01_title
 |     +-- slide_01_subtitle
 |
 +-- slide_02
       +-- slide_02_title
       +-- slide_02_bullets

Stable IDs are necessary for future versioning, diffing, and selective regeneration.
12. Layout Architecture
The application uses predefined layouts rather than arbitrary AI-generated PowerPoint designs.
Supported layouts:
title
title_bullets
two_column
comparison
three_cards
image_text
timeline
statistics
conclusion

The LLM chooses the layout.
The deterministic renderer implements the layout.
Example:
LLM Output:

layout = "three_cards"

        |
        v

Renderer:

render_three_cards()

        |
        v

python-pptx

        |
        v

PowerPoint slide

The LLM should NOT generate arbitrary PowerPoint coordinates.
13. Rendering Architecture
The renderer should contain separate functions/services for each layout.
Conceptually:
LayoutRenderer
 |
 +-- render_title()
 |
 +-- render_title_bullets()
 |
 +-- render_two_column()
 |
 +-- render_comparison()
 |
 +-- render_three_cards()
 |
 +-- render_image_text()
 |
 +-- render_timeline()
 |
 +-- render_statistics()
 |
 +-- render_conclusion()

The renderer receives validated structured data and converts it into PowerPoint objects.
14. Modification Pipeline
After a presentation has been generated, the user can submit a modification.
Example:
Change slide 4 to focus on medical imaging.

The flow is:
Existing Presentation JSON
          +
User Modification
          |
          v
     Change Analyzer
          |
          v
Affected Slide
          |
          v
Relevant Context Retrieval
          |
          v
Selective Regenerator
          |
          v
Pydantic Validation
          |
          v
Replace Affected Slide
          |
          v
PPT Renderer
          |
          v
Updated .pptx

15. Change Analyzer
The Change Analyzer determines:
- Which slide is affected
- What type of modification is requested
- What regeneration scope is required
Example output:
{
  "affected_slides": ["slide_04"],
  "change_type": "content_rewrite",
  "regeneration_scope": "slide"
}

For the MVP, the regeneration scope should be slide-level.
Component-level regeneration can be added later.
16. Selective Regeneration
The selective regeneration system should minimize unnecessary context.
For example:
Modification:
"Change slide 4 to focus on medical imaging."

Instead of sending:

Entire 10-slide presentation

send:

User modification
+
slide_04
+
relevant global requirements
+
layout schema

The regenerated slide is then validated and inserted back into the presentation structure.
17. Baseline Architecture
The project must also implement a baseline full-regeneration strategy.
Original Presentation
        |
        v
User Modification
        |
        v
Full Presentation Regeneration
        |
        v
New Presentation

The baseline exists primarily for research comparison.
18. Proposed Architecture
The proposed system uses selective regeneration.
Original Presentation
        |
        v
User Modification
        |
        v
Change Analyzer
        |
        v
Affected Slide
        |
        v
Selective Regeneration
        |
        v
Updated Slide
        |
        v
Updated Presentation

19. Research Comparison
The two systems must be evaluated under comparable conditions.
Baseline
Full presentation regeneration.
Proposed
Selective slide regeneration.
Compare:
LLM calls
Input tokens
Output tokens
Total tokens
Latency
Estimated cost
Slides regenerated
Validation errors
Presentation quality

20. Metrics Architecture
Metrics should be collected by deterministic application code.
A generation record should conceptually contain:
generation_id
strategy
timestamp
llm_provider
model
llm_calls
input_tokens
output_tokens
total_tokens
latency_ms
slides_regenerated
validation_errors
estimated_cost

The exact implementation can evolve during development.
Metrics should be stored in a simple local format initially.
Possible formats:
- JSON
- CSV
Do not introduce a database just for metrics during the MVP.
21. Error Handling
The system must handle:
- LLM API errors
- Invalid structured output
- Pydantic validation errors
- Missing required fields
- Unsupported layouts
- PPT rendering errors
- File creation errors
- Timeouts
- Rate-limit errors
Errors should be logged and surfaced appropriately.
The system must not silently replace failed LLM output with fake content.
22. File Architecture
Generated presentations should initially be stored locally.
Conceptually:
generated/
    presentations/
        <presentation_id>/
            presentation.json
            presentation.pptx

The exact storage implementation can be finalized during backend development.
23. Separation of Responsibilities
The architecture follows these principles:
LLM
Responsible for:
- Understanding user requirements
- Planning
- Generating content
- Selecting layouts
- Analyzing modifications
Pydantic
Responsible for:
- Schema validation
- Type validation
- Rejecting malformed structured output
Renderer
Responsible for:
- PowerPoint layout
- Positioning
- Typography
- Shapes
- Tables/cards
- Creating .pptx
Backend
Responsible for:
- Orchestration
- API endpoints
- File handling
- Metrics
- Error handling
Frontend
Responsible for:
- User interaction
- Prompt input
- Modification input
- Downloading generated files
- Displaying status/errors
24. Engineering Principles
1. Keep the architecture simple.
2. Keep the LLM provider replaceable.
3. Keep PowerPoint rendering deterministic.
4. Validate every LLM-generated structure.
5. Use stable IDs.
6. Minimize LLM context where possible.
7. Do not regenerate unaffected slides.
8. Do not introduce unnecessary infrastructure.
9. Keep each service independently testable.
10. Build and test incrementally.
11. Do not implement future features before the MVP works.
12. Prefer readable code over complex abstractions.