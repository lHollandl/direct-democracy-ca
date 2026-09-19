# ai/

Prompt files and evaluation material only. No application code lives here: the
platform reaches Ollama through `backend/clients/ollama.py` (ARCHITECTURE.md
§2, §8.1).

`ai/prompts/*.md` — one file per AI function. CLAUDE.md Law 7: AI prompts are
files, never strings in Python. Each file has a header block stating its
inputs, its required output JSON shape, and its version. Every `ai_actions` row
cites the file and a SHA-256 of its exact contents, so the prompt that produced
any past output can be identified even after the file changes.

Variables are written `{{name}}` and are substituted by the client.
