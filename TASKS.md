# Development Tasks

## Status Legend

- [ ] Not started
- [~] In progress
- [x] Complete

---

# Phase 1 — Project Initialization

- [ ] Create repository
- [x] Create root README.md
- [x] Create PROJECT_SPEC.md
- [x] Create ARCHITECTURE.md
- [x] Create TASKS.md
- [x] Create .gitignore
- [x] Create frontend directory
- [x] Create backend directory
- [x] Create docs directory
- [x] Create experiments directory
- [x] Create generated directory

---

# Phase 2 — Backend Foundation

- [ ] Create Python virtual environment
- [x] Create requirements.txt
- [x] Create FastAPI application
- [x] Create health-check endpoint
- [ ] Create backend configuration system
- [x] Create .env.example
- [ ] Configure environment variables
- [ ] Add basic logging
- [ ] Add backend error handling
- [x] Verify FastAPI starts successfully

---

# Phase 3 — Frontend Foundation

- [x] Create Next.js application
- [x] Configure TypeScript
- [x] Configure Tailwind CSS
- [x] Create basic application layout
- [x] Create landing/generation page
- [ ] Verify frontend starts successfully

---

# Phase 4 — LLM Provider Layer

- [x] Define LLMProvider interface
- [x] Implement GeminiProvider
- [x] Configure Gemini API key through environment variable
- [x] Create minimal Gemini request
- [ ] Test Gemini response
- [ ] Test structured JSON output
- [ ] Add timeout handling
- [ ] Add API error handling
- [ ] Record token usage where available

---

# Phase 5 — Presentation Schema

- [x] Create Pydantic Presentation model
- [x] Create Slide model
- [x] Create component models
- [ ] Create theme model
- [x] Create metadata model
- [x] Define supported layouts
- [x] Validate example presentation JSON
- [x] Test invalid JSON rejection

---

# Phase 6 — Requirement Extraction

- [ ] Create requirement extraction prompt
- [ ] Define Requirement model
- [ ] Implement requirement extraction service
- [ ] Validate LLM output
- [ ] Test multiple user prompts
- [ ] Handle missing requirements
- [ ] Define sensible defaults

---

# Phase 7 — Presentation Planning

- [ ] Create presentation planning prompt
- [ ] Define SlidePlan model
- [ ] Implement planning service
- [ ] Select layouts based on slide purpose
- [ ] Validate slide plan
- [ ] Test different presentation topics

---

# Phase 8 — Slide Generation

- [ ] Create slide generation prompt
- [ ] Implement content generation service
- [ ] Generate structured slide JSON
- [ ] Validate generated slide
- [ ] Handle malformed LLM responses
- [ ] Test every supported layout

---

# Phase 9 — PPT Rendering

- [x] Set up python-pptx
- [x] Create theme system
- [x] Implement title renderer
- [x] Implement title_bullets renderer
- [x] Implement two_column renderer
- [x] Implement comparison renderer
- [x] Implement three_cards renderer
- [x] Implement image_text renderer
- [x] Implement timeline renderer
- [x] Implement statistics renderer
- [x] Implement conclusion renderer
- [x] Implement presentation renderer
- [x] Export .pptx
- [x] Verify generated files open correctly

---

# Phase 10 — First MVP

- [ ] Connect frontend to backend
- [ ] Add prompt input
- [ ] Add generation button
- [ ] Show generation status
- [x] Generate presentation
- [ ] Provide PPT download
- [x] Handle generation errors
- [x] Test complete Prompt → PPT flow

## MVP Milestone

> Prompt → actual .pptx works.

---

# Phase 11 — Modification System

- [ ] Add modification input
- [ ] Define ChangeRequest model
- [x] Create change-analysis prompt
- [x] Implement Change Analyzer
- [x] Identify affected slide
- [x] Identify change type
- [x] Determine regeneration scope
- [x] Test modification requests

---

# Phase 12 — Selective Regeneration

- [x] Create selective regeneration prompt
- [x] Retrieve affected slide
- [x] Retrieve necessary global context
- [x] Regenerate affected slide
- [x] Validate regenerated slide
- [x] Replace affected slide
- [x] Export updated PPT
- [x] Verify unaffected slides remain unchanged

## Selective Regeneration Milestone

> Modify one slide → only that slide is regenerated.

---

# Phase 13 — Baseline Regeneration

- [x] Implement full regeneration
- [x] Ensure baseline uses the same presentation request
- [x] Ensure baseline and proposed systems are comparable
- [ ] Record baseline metrics

---

# Phase 14 — Metrics

- [x] Track API/LLM calls
- [x] Track input tokens
- [x] Track output tokens
- [x] Track total tokens
- [x] Track latency
- [x] Track estimated cost
- [x] Track regenerated slides
- [x] Track validation errors
- [ ] Store experiment results

---

# Phase 15 — Evaluation

- [ ] Define presentation test set
- [ ] Define modification test set
- [ ] Run baseline experiments
- [ ] Run selective regeneration experiments
- [ ] Compare token usage
- [ ] Compare API calls
- [ ] Compare latency
- [ ] Compare estimated cost
- [ ] Compare regeneration ratio
- [ ] Evaluate presentation quality
- [ ] Conduct human evaluation
- [ ] Generate graphs/tables
- [ ] Analyze results

---

# Phase 16 — Prompt Engineering Experiments

Only start this phase after the complete MVP works.

- [ ] Establish baseline prompts
- [ ] Test prompt decomposition
- [ ] Test structured prompting
- [ ] Test few-shot examples where useful
- [ ] Test context minimization
- [ ] Test validation/refinement
- [ ] Compare results
- [ ] Document useful techniques

---

# Phase 17 — Final Improvements

- [ ] Improve error messages
- [ ] Improve UI
- [ ] Improve layouts
- [ ] Improve prompt reliability
- [ ] Improve documentation
- [ ] Add unit tests
- [ ] Add integration tests
- [ ] Clean unused code
- [ ] Finalize experiment results
- [ ] Prepare project demonstration
- [ ] Prepare viva explanation
- [ ] Prepare final report

---

# Current Milestone

## Phase 1 — Documentation

- [x] PROJECT_SPEC.md
- [x] ARCHITECTURE.md
- [x] TASKS.md

## Next

Complete Gemini API smoke test, then continue with Phase 5 — Presentation Schema.
