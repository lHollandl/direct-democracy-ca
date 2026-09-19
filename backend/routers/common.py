"""Shapes shared by more than one router: pagination and plain responses."""

from __future__ import annotations

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field

DEFAULT_LIMIT = 25
MAX_LIMIT = 100

CursorParam = Annotated[int | None, Query(description="Id to continue after")]
LimitParam = Annotated[int, Query(ge=1, le=MAX_LIMIT, description="Page size")]


class Page(BaseModel):
    """Every list endpoint paginates the same way (ARCHITECTURE.md §6)."""

    items: list
    next_cursor: int | None = None


class Message(BaseModel):
    message: str


class Created(BaseModel):
    id: int
    message: str = Field(default="Saved.")
