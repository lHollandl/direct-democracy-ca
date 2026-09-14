# ARCHITECTURE.md — AnimationDirector Technical Blueprint

> This document is the single source of truth for the tech stack, external
> dependencies, folder layout, API surface, pipeline state definitions,
> and hardware context. It evolves as the project grows.
> Principles and laws live in CLAUDE.md.
>
> Claude Code must update this document whenever a new endpoint, dependency,
> folder, pipeline state, or stack component is added or changed.

---

## The Stack

| Layer | Technology | Location |
|---|---|---|
| Frontend | React + TypeScript + Tailwind | /frontend |
| Backend API | Python FastAPI + WebSockets | /backend |
| Script AI | Ollama llama4 (local) | port 11434 |
| Vision AI | Ollama qwen2.5vl:7b (local) | port 11434 |
| Image Gen | ComfyUI + FLUX.1-dev + Sketch Pad LoRA | port 8188 |
| Session State | JSON files | /outputs/sessions |
| LoRA files | .safetensors | /loras |
| Config | Environment variables via .env | /.env |

---

## External Dependencies

This is the authoritative list of external dependencies and their status.
TODO.md holds only the installation-status checkboxes and points here for details.

| Dependency | Version / Notes | Port | Status |
|---|---|---|---|
| ComfyUI | Existing install | 8188 | Installed |
| Ollama | Latest stable | 11434 | Unknown — verify |
| llama4 model | `ollama pull llama4` | — | Unknown |
| qwen2.5vl:7b model | `ollama pull qwen2.5vl:7b` | — | Unknown |
| FLUX.1-dev model | Place in ComfyUI models folder | — | Unknown |
| Sketch Pad LoRA | Download from Civitai, place in /loras/ | — | Unknown |
| Node.js | Required for frontend build | — | Unknown |
| Python | 3.11+ required | — | Unknown |
| pip packages | fastapi, uvicorn, httpx, websockets, python-dotenv | — | Unknown |

---

## Hardware Context

| Component | Spec |
|---|---|
| GPU | NVIDIA RTX 5090 (32 GB VRAM) |
| CPU | AMD Threadripper 7970X |
| RAM | 96 GB |
| OS | Linux |

All services run locally — no cloud dependencies.
ComfyUI is pre-installed; its path is set via `$COMFYUI_PATH` in .env.

### Performance Target
- Storyboard frame generation: 2–4 seconds at 1024×576, 20 steps.
- FLUX and LLM inference run sequentially, never simultaneously.
  The GPU is a shared resource managed by the orchestrator.

---

## Pipeline State Definitions

These are the five canonical pipeline states. This is the single source of
truth for state names — CLAUDE.md references these by name only, and
UI_DESIGN.md describes how the frontend behaves in each state.

| State | Description |
|---|---|
| IDLE | No active generation. Session is open and waiting for the director to trigger generation. |
| GENERATING | Image generation is in progress. The GPU is active. No human action is accepted. |
| PAUSED | A frame has been generated and is waiting for the director's decision. This is the only state where Accept, Reject, and Edit are available. |
| ADVANCING | The director has accepted a frame. The pipeline is committing the decision and transitioning. Brief — returns to IDLE or begins next GENERATING. |
| ERROR | Something went wrong. The pipeline is halted. The director decides the next action. No automatic retry. |

### State Transitions

```
IDLE → GENERATING    (director triggers generation)
GENERATING → PAUSED  (frame ready for review)
GENERATING → ERROR   (generation failed)
PAUSED → ADVANCING   (director accepts)
PAUSED → GENERATING  (director rejects or edits — regenerates)
PAUSED → ERROR       (unexpected failure during review)
ADVANCING → IDLE     (commit complete)
ERROR → IDLE         (director clears error and resets)
ERROR → GENERATING   (director retries)
```

---

## Folder Structure

```
AnimationDirector/
├── CLAUDE.md                  # Developer constitution
├── ARCHITECTURE.md            # This file — technical blueprint
├── CONVENTIONS.md             # Coding style and framework conventions
├── UI_DESIGN.md               # Frontend layout and interaction spec
├── TODO.md                    # Task tracker and status
├── HISTORY.md                 # Append-only session log
├── README.md                  # Project overview and quick start
├── .env                       # Local config — never committed
├── .env.example               # Template for .env
├── .gitignore
│
├── backend/
│   ├── main.py                # FastAPI app init and route registration
│   ├── config.py              # Load all env vars at startup
│   ├── orchestrator.py        # Pipeline flow: GENERATING → PAUSED → ADVANCING
│   ├── state_manager.py       # Session JSON load/save, frame history, rollback
│   ├── ollama_client.py       # All Ollama API calls (Script AI + Vision AI)
│   ├── comfyui_client.py      # All ComfyUI API calls (image generation)
│   └── routers/
│       └── session.py         # All REST API routes
│
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   └── src/
│       ├── App.tsx
│       ├── api.ts             # Typed API client — all fetch calls here
│       ├── ws.ts              # WebSocket manager — one connection point
│       ├── components/
│       │   ├── ScriptPanel.tsx
│       │   ├── FrameViewer.tsx
│       │   ├── ReviewControls.tsx
│       │   ├── FrameHistory.tsx
│       │   ├── VisionAnalysis.tsx
│       │   └── StatusBar.tsx
│       └── pages/
│           └── Session.tsx
│
├── prompts/
│   ├── script_system.txt      # Llama 4 system prompt for scene writing
│   ├── script_scene.txt       # Per-scene user prompt template
│   ├── vision_system.txt      # Qwen VL system prompt for frame analysis
│   └── continuity_check.txt   # Frame vs intended scene comparison
│
├── infra/
│   └── flux_storyboard_workflow.json   # ComfyUI workflow with FLUX + LoRA
│
├── outputs/
│   ├── frames/                # All generated frames (never deleted)
│   ├── accepted/              # Copies of accepted frames only
│   └── sessions/              # Session state JSON files
│
├── loras/
│   └── sketch_pad.safetensors
│
├── docs/
│   └── design/                # Design documents and reference material
│
└── ai/                        # Reserved for future AI-related scripts
```

---

## Folder Routing Rules

Each concern has exactly one home. Code that violates these boundaries
should be refactored immediately.

| Concern | Lives in | Never in |
|---|---|---|
| Ollama API calls | backend/ollama_client.py | Any other backend file |
| ComfyUI API calls | backend/comfyui_client.py | Any other backend file |
| Pipeline state logic | backend/state_manager.py | Orchestrator or routes |
| Pipeline flow logic | backend/orchestrator.py | State manager or routes |
| API route definitions | backend/routers/session.py | main.py or other files |
| Frontend HTTP calls | frontend/src/api.ts | Inside components |
| Frontend WebSocket | frontend/src/ws.ts | Inside components |
| Prompt templates | prompts/*.txt | Embedded in Python code |
| Generated output | outputs/ | Anywhere else on disk |
| Environment config | .env | Hardcoded in any file |

---

## API Contract

Every frontend must be able to drive the entire pipeline using only these endpoints.

### REST Endpoints

| Method | Path | Description |
|---|---|---|
| POST | /session/start | Create new session, return session_id |
| POST | /session/{id}/generate | Trigger next frame generation |
| POST | /session/{id}/accept | Accept current pending frame, advance pipeline |
| POST | /session/{id}/reject | Reject current pending frame, rollback to previous |
| POST | /session/{id}/edit | Update scene prompt and regenerate current frame |
| GET | /session/{id}/state | Return full current session state as JSON |
| GET | /session/{id}/frames | Return list of all frames in this session |

### WebSocket

| Path | Description |
|---|---|
| WS /ws/{session_id} | Real-time push of frames and status changes |

WebSocket event types and payloads are defined in UI_DESIGN.md,
which is the authoritative source for frontend communication contracts.

---

## State Persistence Format

- One JSON file per session: `session_YYYYMMDD_HHMMSS.json`
- Stored in `outputs/sessions/`
- Written after every state change (crash recovery guarantee)
- No database required for v1

### Session JSON Structure (reference)
```json
{
  "session_id": "session_20260328_141500",
  "created_at": "2026-03-28T14:15:00Z",
  "current_state": "PAUSED",
  "current_frame_index": 3,
  "frames": [
    {
      "index": 0,
      "prompt": "A lone figure stands at the edge of a cliff at dawn",
      "frame_path": "outputs/frames/session_20260328_141500_frame_000.png",
      "vision_analysis": "Scene shows a silhouette on a cliff edge, warm sky tones...",
      "decision": "accepted",
      "timestamp": "2026-03-28T14:15:12Z"
    }
  ]
}
```

---

## AI Model Configuration

All model identifiers are set via environment variables in `.env`.
Never hardcode a model name, port, or file path.

| Role | Model | Env Var | Default |
|---|---|---|---|
| Script AI | llama4 via Ollama | SCRIPT_MODEL | llama4 |
| Vision AI | qwen2.5vl:7b via Ollama | VISION_MODEL | qwen2.5vl:7b |
| Image Gen | FLUX.1-dev via ComfyUI | (workflow JSON) | — |
| LoRA | Sketch Pad | (workflow JSON) | sketch_pad.safetensors |
| Ollama port | — | OLLAMA_PORT | 11434 |
| ComfyUI port | — | COMFYUI_PORT | 8188 |
| Backend port | — | BACKEND_PORT | 8000 |
| Frontend port | — | FRONTEND_PORT | 3000 |
