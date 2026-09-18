"""Ollama on the host GPU (ARCHITECTURE.md §8.1).

Prompts are files under `ai/prompts/`, never strings in Python (CLAUDE.md
Law 7). Every call reports which file it used and the SHA-256 of that file's
exact contents, so an `ai_actions` row can cite them and a past output can
always be traced to the prompt that produced it.

A timeout or an unreachable host raises `ExternalServiceDown`; the caller
decides what that means — labeling marks the post `unlabeled` and retries,
similarity skips and logs.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
import yaml

from backend.config.settings_env import get_env_settings, repo_root
from backend.errors import ExternalServiceDown

log = logging.getLogger(__name__)

PROMPT_DIR = repo_root() / "ai" / "prompts"
_VARIABLE = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")
_FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


@dataclass(frozen=True)
class PromptFile:
    name: str
    path: Path
    text: str
    sha256: str
    #: The prompt file's YAML header block, read for documentation and for the
    #: `format` schema below.
    header: dict
    #: A JSON Schema, written in the prompt file's header as `format:`. When a
    #: file declares one it is handed to Ollama, which then constrains the
    #: model to emit JSON of that shape. The shape is still stated in prose in
    #: the file, because the file is the contract (CLAUDE.md Law 7); this only
    #: stops a small model from wrapping it in commentary or mismatched braces.
    output_format: dict | None


@lru_cache(maxsize=32)
def load_prompt(name: str) -> PromptFile:
    path = PROMPT_DIR / name
    if not path.exists():
        raise ExternalServiceDown(
            f"The prompt file {name} is missing, so this AI step cannot run.",
            code="prompt_file_missing",
        )
    text = path.read_text(encoding="utf-8")
    header: dict = {}
    match = _FRONT_MATTER.match(text)
    if match:
        try:
            header = yaml.safe_load(match.group(0).strip("-\n")) or {}
        except yaml.YAMLError:
            header = {}
    return PromptFile(
        name=name,
        path=path,
        text=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        header=header,
        output_format=header.get("format"),
    )


def render(prompt: PromptFile, variables: dict[str, Any]) -> str:
    """Substitute `{{name}}`; the YAML header block is documentation for people
    and is not sent to the model."""
    body = _FRONT_MATTER.sub("", prompt.text)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables:
            raise ExternalServiceDown(
                f"The prompt file {prompt.name} expects a value for {key}.",
                code="prompt_variable_missing",
            )
        return str(variables[key])

    return _VARIABLE.sub(replace, body).strip()


class OllamaClient:
    """The only code that speaks to Ollama."""

    def __init__(self, base_url: str | None = None, timeout: int | None = None):
        env = get_env_settings()
        self.base_url = (base_url or env.OLLAMA_BASE_URL).rstrip("/")
        self.timeout = timeout or env.OLLAMA_TIMEOUT_SECONDS
        self.model = env.OLLAMA_MODEL
        self.embed_model = env.EMBED_MODEL

    @property
    def model_label(self) -> str:
        """The string recorded on every `ai_actions` row, so model swaps are data."""
        return f"ollama:{self.model}"

    @property
    def embed_model_label(self) -> str:
        return f"ollama:{self.embed_model}"

    async def generate(self, prompt_file: str, variables: dict[str, Any]) -> tuple[str, PromptFile]:
        # No blocking calls inside async def (Law 11) — load_prompt is
        # lru_cached, so this only ever blocks once per prompt file per
        # process, but the rule makes no exception for that (audit demo-01
        # run 5, LOW).
        prompt = await asyncio.to_thread(load_prompt, prompt_file)
        body = render(prompt, variables)
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": body,
            "stream": False,
            # Temperature 0: the same input should file a post the same way
            # twice. A labeler that wanders is a labeler nobody can audit.
            "options": {"temperature": 0},
        }
        if prompt.output_format:
            payload["format"] = prompt.output_format
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("ollama_unreachable", extra={"prompt_file": prompt_file})
            raise ExternalServiceDown(
                "The labelling service is not answering right now. "
                "The platform will try again by itself.",
                code="ollama_unavailable",
            ) from exc
        return data.get("response", ""), prompt

    async def embed(self, text: str) -> list[float]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.embed_model, "prompt": text},
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ExternalServiceDown(
                "The similarity service is not answering right now.",
                code="ollama_unavailable",
            ) from exc
        embedding = data.get("embedding")
        if not embedding:
            raise ExternalServiceDown(
                "The similarity service returned nothing usable.", code="ollama_bad_output"
            )
        return [float(x) for x in embedding]


def parse_json_output(raw: str) -> dict[str, Any]:
    """Output is parsed strictly; malformed output is a failure, not a guess.

    Models sometimes wrap JSON in a code fence or add a sentence around it, so
    the first balanced object is extracted before parsing. Anything else raises.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"\A```[a-z]*\n", "", text)
        text = re.sub(r"\n?```\s*\Z", "", text)
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object in the model's answer")
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : index + 1])
    raise ValueError("the JSON object in the model's answer is not closed")


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """DEMOCRACY.md §9.3 — cosine similarity between two embeddings."""
    if not a or not b or len(a) != len(b):
        raise ValueError("embeddings must be the same non-zero length")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return max(-1.0, min(1.0, dot / (norm_a * norm_b)))


_client: OllamaClient | None = None


def get_ollama() -> OllamaClient:
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client


def override_ollama(client) -> None:
    """Used by the test suite, which never reaches the real model."""
    global _client
    _client = client
