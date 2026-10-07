# Project Specification

## Project Title

Cost-Efficient AI-Based PowerPoint Generation Using Prompt Engineering and Context-Aware Selective Regeneration

---

## 1. Project Overview

This project is an AI-powered web application that accepts a user's natural-language request and generates an actual PowerPoint (`.pptx`) presentation.

The system uses prompt engineering and structured LLM outputs to:

1. Extract presentation requirements.
2. Plan the presentation.
3. Generate structured slide content.
4. Select appropriate predefined layouts.
5. Convert the structured representation into a real `.pptx` file.
6. Accept modification requests after generation.
7. Identify the affected slide.
8. Regenerate only the affected slide instead of the entire presentation.
9. Export the updated presentation.

The central research contribution is:

> Use prompt engineering, structured generation, and context-aware selective regeneration to reduce unnecessary LLM calls, token usage, latency, and estimated cost while maintaining presentation quality.

---

# 2. Problem Statement

Creating presentations manually requires significant time for organizing information, writing slide content, selecting layouts, and maintaining consistency.

AI-based presentation generation can automate this process, but when a user requests a modification, regenerating the entire presentation can result in unnecessary LLM calls, token consumption, latency, and resource usage.

This project proposes a structured AI presentation-generation system that uses context-aware selective regeneration. Instead of regenerating the complete presentation after every modification, the system analyzes the modification request, identifies the affected slide, and regenerates only the necessary portion while preserving the rest of the presentation.

The project will experimentally compare full presentation regeneration with selective regeneration in terms of efficiency and presentation quality.

---

# 3. Objectives

1. Convert natural-language presentation requests into structured requirements.
2. Use prompt engineering to improve presentation planning and content generation.
3. Generate structured and validated slide representations.
4. Generate actual `.pptx` presentations using deterministic rendering.
5. Implement predefined reusable PowerPoint layouts.
6. Detect which slide is affected by a user modification.
7. Regenerate only the affected slide in the MVP.
8. Measure LLM calls, tokens, latency, estimated cost, and regenerated slides.
9. Compare full regeneration against selective regeneration.
10. Evaluate whether selective regeneration maintains comparable presentation quality.

---

# 4. MVP Scope

The MVP must support:

- Natural-language user prompt
- Requirement extraction
- Presentation planning
- Structured slide generation
- Predefined layout selection
- Pydantic schema validation
- `.pptx` generation using `python-pptx`
- Presentation download
- User modification request
- Modification/change analysis
- Affected-slide identification
- Slide-level selective regeneration
- Updated `.pptx` generation
- Basic generation metrics

---

# 5. Out of Scope

The MVP will NOT include:

- Website/Webflow generation
- Arbitrary PowerPoint design generation
- User authentication
- Payment systems
- Cloud database
- Vector database/RAG
- Fine-tuning
- Custom-trained LLM
- Automatic web research
- Image generation
- Video/audio generation
- Real-time collaboration
- Mobile application
- Editing arbitrary uploaded PowerPoint files
- Complex animations
- Advanced transitions

These may be considered future work.

---

# 6. Core Architecture

```text
User
 |
 v
Next.js Frontend
 |
 v
FastAPI Backend
 |
 +-----------------------------+
 |                             |
 v                             v
Generation Pipeline       Modification Pipeline
 |                             |
 v                             v
Requirement Analyst       Change Analyzer
 |                             |
 v                             v
Presentation Planner      Affected Slide
 |                             |
 v                             v
Slide Content Generator   Selective Regenerator
 |                             |
 +-------------+---------------+
               |
               v
        Pydantic Validation
               |
               v
        Layout Rendering
               |
               v
          python-pptx
               |
               v
            .pptx
               |
               v
          Metrics Logger

7. Agent Architecture
The project will use an agentic/pipeline architecture without unnecessary autonomous-agent complexity.
AI-powered components
Requirement Analyst
Input:
- User prompt
Output:
- Structured presentation requirements
Presentation Planner
Input:
- Structured requirements
Output:
- Presentation outline
- Slide purposes
- Recommended layouts
Content Generator
Input:
- Slide specification
- Relevant presentation context
Output:
- Structured slide content
Change Analyzer
Input:
- Existing presentation structure
- User modification request
Output:
- Affected slide
- Change type
- Regeneration scope
Selective Regenerator
Input:
- Affected slide
- Relevant context
- Modification request
Output:
- Updated slide
Deterministic components
These should NOT unnecessarily be implemented as agents:
- Pydantic validation
- Layout rendering
- PowerPoint rendering
- File management
- Merging/replacement
- Metrics collection
8. LLM Provider Architecture
The system should be provider-agnostic.
Initial provider:
- Gemini API
Potential alternatives:
- Groq
- OpenRouter
The application should have an abstraction similar to:
LLMProvider
    |
    +-- GeminiProvider
    +-- GroqProvider
    +-- OpenRouterProvider

Only Gemini needs to be implemented initially.
API keys must always be stored in environment variables.
Never hardcode API keys.
9. Prompt Engineering Pipeline
The system will use multiple prompt stages.
Stage 1 — Requirement Extraction
Natural-language prompt
        |
        v
Requirement Extraction Prompt
        |
        v
Structured Requirements

Extract:
- Topic
- Audience
- Number of slides
- Tone
- Visual style
- Required sections
- Constraints
Stage 2 — Presentation Planning
Requirements
      |
      v
Planning Prompt
      |
      v
Slide Plan

Each slide should contain:
- Slide ID
- Purpose
- Recommended layout
- Key information
Stage 3 — Slide Generation
Slide specification
+
Relevant context
+
Layout schema
        |
        v
Slide Generation Prompt
        |
        v
Structured Slide

Stage 4 — Change Analysis
Existing presentation
+
User modification
        |
        v
Change Analysis Prompt
        |
        v
Affected slide/component
+
Change type
+
Regeneration scope

Stage 5 — Selective Regeneration
Only provide necessary context:
Modification request
+
Affected slide
+
Relevant presentation context
+
Schema

Do NOT send the entire presentation unnecessarily.
10. Prompt Engineering Techniques
Techniques to investigate and use where appropriate:
- Role/instruction prompting
- Structured JSON output
- JSON schema validation
- Few-shot examples
- Prompt decomposition
- Context minimization
- Deterministic templates
- Component-specific prompts
- Validation/refinement prompts
Do not use techniques merely for complexity. Each technique should have a clear purpose.
11. PPT Layout System
The initial system will use controlled predefined layouts.
Layouts:
1. title
2. title_bullets
3. two_column
4. comparison
5. three_cards
6. image_text
7. timeline
8. statistics
9. conclusion
The LLM selects the layout.
The deterministic renderer controls the actual PowerPoint design.
The LLM must NOT generate arbitrary PowerPoint coordinates.
12. Structured Presentation Representation
The presentation must have stable IDs and structured components.
Example:
{
  "presentation": {
    "id": "pres_001",
    "title": "AI in Healthcare",
    "theme": {
      "name": "professional",
      "font_family": "Aptos"
    },
    "metadata": {
      "audience": "B.Tech students",
      "tone": "academic",
      "slide_count": 10
    },
    "slides": [
      {
        "id": "slide_01",
        "order": 1,
        "layout": "title",
        "purpose": "Introduce the topic",
        "components": {
          "title": {
            "id": "slide_01_title",
            "text": "AI in Healthcare"
          },
          "subtitle": {
            "id": "slide_01_subtitle",
            "text": "Applications, Benefits and Challenges"
          }
        }
      }
    ]
  }
}

Requirements:
- Stable presentation ID
- Stable slide IDs
- Stable component IDs
- Explicit layout
- Explicit slide order
- Structured components
- Pydantic validation
- Easy JSON serialization
- Easy diffing/versioning
- Easy deterministic rendering
13. Selective Regeneration
For MVP, selective regeneration operates at the slide level.
Example:
User:
"Change slide 4 to focus on medical imaging."

        |
        v

Change Analyzer

        |
        v

Affected slide = slide_04

        |
        v

Retrieve slide_04
+ necessary global context

        |
        v

Selective Regenerator

        |
        v

Validate updated slide

        |
        v

Replace slide_04

        |
        v

Export updated PPT

The system should NOT regenerate all slides.
14. Baseline vs Proposed System
The project must support an experimental comparison.
Baseline
Full regeneration:
Original presentation
       |
Modification
       |
Regenerate entire presentation
       |
New presentation

Proposed
Selective regeneration:
Original presentation
       |
Modification
       |
Change analysis
       |
Affected slide
       |
Regenerate affected slide only
       |
Updated presentation

15. Evaluation Metrics
Track at minimum:
Efficiency
- Number of LLM/API calls
- Input tokens
- Output tokens
- Total tokens
- Latency
- Estimated API cost
- Number of regenerated slides
Reliability
- Validation errors
- Failed generations
- Change-detection errors
Quality
Evaluate:
- Relevance
- Completeness
- Consistency
- Factual correctness where reasonably assessable
- Layout suitability
- Readability
- Requirement adherence
16. Quality Evaluation
Use a fixed evaluation rubric rather than an unsupported "AI quality percentage."
Human evaluators can rate each presentation on a 1–5 Likert scale for:
1. Relevance
2. Completeness
3. Consistency
4. Readability
5. Layout suitability
6. Requirement adherence
Compare quality between:
- Full regeneration
- Selective regeneration
The research objective is to determine whether selective regeneration provides efficiency improvements while maintaining comparable quality.
17. Technology Stack
Frontend
- Next.js
- React
- TypeScript
- Tailwind CSS
Backend
- Python
- FastAPI
- Pydantic
AI
- Gemini API
- Provider abstraction
PPT
- python-pptx
Storage
- Local filesystem initially
Metrics
- Python logging
- Timing measurements
- LLM usage metadata
- JSON/CSV experiment logs
18. Development Principles
- Build incrementally.
- Do not build the entire application at once.
- Keep code modular and readable.
- Prefer simple solutions.
- Avoid unnecessary infrastructure.
- Never hardcode API keys.
- Use .env.
- Validate all LLM-generated structured output.
- Add error handling.
- Add logging where useful.
- Do not hide errors with fake fallback data.
- Test each stage independently.
- Do not implement future features before the MVP works.
19. Development Order
1. Repository setup
2. Backend setup
3. Frontend setup
4. Gemini API test
5. Pydantic schemas
6. Requirement extraction
7. Presentation planning
8. Slide generation
9. Schema validation
10. PPT rendering
11. First working MVP
12. Frontend integration
13. Modification/change analysis
14. Selective regeneration
15. Metrics tracking
16. Baseline implementation
17. Evaluation pipeline
18. Prompt/layout improvements
20. Current Implementation Status
At project initialization:
- Specification: COMPLETE
- Architecture: COMPLETE
- MVP definition: COMPLETE
- Schema design: COMPLETE
- Prompt pipeline: COMPLETE
- Evaluation methodology: COMPLETE
Implementation: NOT STARTED
The next task is repository initialization.