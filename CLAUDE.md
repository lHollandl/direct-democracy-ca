# CLAUDE.md — AnimationDirector Developer Constitution

> This document defines the permanent principles and laws of the project.
> It does not describe the current tech stack, folder layout, or UI conventions —
> those live in ARCHITECTURE.md and CONVENTIONS.md respectively.
> Claude Code reads this file at the start of every session.

---

## Mission

We are building a locally-run AI pipeline that helps a human director
write, visualize, and iterate on animation storyboards. The system
orchestrates a Script AI, a Vision AI, and an image generator —
but the human is always in control. No frame advances without approval.
No decision is made without the director seeing it first.
The system is a tool, not an author.

---

## Core Principles

### 1. The Director Is Always in Control
Every generated frame pauses for human review before the pipeline continues.
The AI proposes. The director decides. This is not optional behavior —
it is the foundation of the entire system.
Accept moves forward. Reject rolls back. Edit lets the director revise
and regenerate. The pipeline never advances without explicit approval.

### 2. Nothing Is Lost
The pipeline maintains a complete frame history stack at all times.
Rejecting a frame never deletes it — every generated frame is preserved
regardless of the director's decision. The director can always review,
compare, or restore any previous frame from the session. If the backend
crashes, the director resumes from the last persisted state.

### 3. The AI Is a Collaborator, Not a Director
The Script AI writes scene descriptions. The Vision AI analyzes frames.
Neither makes creative decisions. They provide material for the director
to work with. If the AI output is wrong, the director fixes it.
AI suggestions are always visible and editable before use.
Vision AI analysis is shown to the director, not silently fed forward.

### 4. Local First
The entire pipeline runs on local hardware. No frames, scripts, or
creative material leave the machine unless the director explicitly
exports them. No cloud API calls are made during pipeline execution.

### 5. Fast Iteration
The feedback loop must stay tight. Style choices, model configuration,
and generation parameters should all favor speed over perfection.
The GPU is a shared resource — LLM inference and image generation
run sequentially, never simultaneously.

### 6. Clean and Explicit Code
Prefer explicit, readable logic over clever shortcuts.
Pipeline stages must be independently testable.
Errors surface immediately and halt the pipeline.
No silent failures. No partial states. No magic.
Do not install dependencies that are not required.
Do not write files outside the project directory without explicit reason.

### 7. The UI Is Replaceable
The backend is the permanent core of this project. The frontend is a skin.
Any UI — React, Vue, Electron, mobile, CLI — must be able to plug in
without touching a single line of backend code. The API is the contract.

---

## Universal Laws

These apply to every line of code in the project, regardless of layer.

### Security
- NEVER commit .env or any file containing credentials, tokens, or local paths.
- ALWAYS use environment variables for ports, model names, and file paths.
- ALWAYS validate file paths before writing to disk.
- NEVER expose internal error details to the frontend — log server-side,
  return a clean generic message to the client.

### Code Quality
- ALWAYS use async/await in Python — never synchronous blocking calls.
- ALWAYS write descriptive variable names — code is read more than written.
- ALWAYS add a comment explaining WHY when doing something non-obvious.
- ALWAYS handle errors explicitly — never silently swallow exceptions.
- NEVER leave TODO comments in code — if it needs doing, it goes in TODO.md.

### Pipeline State Machine
- The pipeline has exactly three states per frame:
  GENERATING → PAUSED → ADVANCING.
- PAUSED is the only state where the human can act.
- A frame is not accepted until the director explicitly approves it.
- Rollback must always be available — never remove the previous frame
  from state before the current one is accepted.
- Session state is persisted after every single state change —
  if the backend crashes, nothing is lost.

### State Persistence
- Frame history is an append-only array — never mutate past entries.
- Every frame entry records: prompt used, frame path, vision analysis,
  director decision, and timestamp.
- Session state must be recoverable from disk after any crash.

### AI Model Boundaries
- Model names, ports, and paths are always environment variables — never hardcoded.
- Prompt templates are always plain text files — never embedded as strings in code.
- Every AI interaction must be visible to the director before it influences the pipeline.

### API Independence
- The backend exposes a clean REST API and WebSocket interface only.
- The backend has zero knowledge of the frontend — no HTML, no templates,
  no frontend logic of any kind.
- Every pipeline action must be triggerable via API call alone —
  the UI is a convenience layer, not a requirement.
- The WebSocket pushes updates to whoever is listening —
  it does not care what is on the other end.

---

## Before Every Feature — Ask These Questions

1. Does this give the director more control or less?
2. Can the director undo or reverse this action?
3. Does this work if Ollama is slow or temporarily offline?
4. Is the AI's role in this step visible to the director?
5. Does this respect the sequential GPU rule?
6. If the backend crashes mid-generation, does the director lose work?
7. Is this stored in session state so it survives a restart?
8. Can this feature be driven by API call alone, without the UI?

---

## The North Star

A solo director with a vision should be able to sit down, describe a scene
in plain language, watch a rough storyboard frame appear in seconds,
say yes or no, and have the AI adapt from that decision to make the next
frame better. Everything we build serves that loop.
The UI can always change. The pipeline is the product.

---

## Session Law

At the start of every Claude Code session:
1. Read CLAUDE.md fully.
2. Read TODO.md fully.
3. Read ARCHITECTURE.md and CONVENTIONS.md if the task touches structure or style.
4. Check the Current Status table in TODO.md before writing any code.
5. Do not install anything or create files until the session goal is confirmed.

At the end of every completed prompt:
1. Update TODO.md — mark completed items done.
2. Add any new technical debt to the Technical Debt section.
3. Add any new future tasks that came up.
4. Update the Current Status table.
5. Append one entry to HISTORY.md with what was built and why.

---

## Document Map

| Document | Purpose | Changes Often? |
|---|---|---|
| CLAUDE.md | Principles and laws — the constitution | Rarely |
| ARCHITECTURE.md | Tech stack, folder layout, API contract | When structure changes |
| CONVENTIONS.md | Coding style, framework rules, file routing | When conventions evolve |
| UI_DESIGN.md | Frontend capabilities, layout, interaction spec | Each UI phase |
| TODO.md | Task tracker, status, phase checklist | Every session |
| HISTORY.md | Append-only log of completed work | Every session |
