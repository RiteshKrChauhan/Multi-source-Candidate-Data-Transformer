from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceType(StrEnum):
    RESUME = "resume"
    LINKEDIN = "linkedin"
    ATS = "ats"
    CSV = "csv"
    GITHUB = "github"


class ProvenanceRecord(BaseModel):
    """Explains where a value came from and how it was extracted."""

    model_config = ConfigDict(extra="forbid")

    source: SourceType
    source_id: str
    extraction_method: str
    original_field: str | None = None
    value: Any = None


class SourceRecord(BaseModel):
    """Parser-neutral record. Parsers never depend on canonical models."""

    model_config = ConfigDict(extra="forbid")

    source: SourceType
    source_id: str
    fields: dict[str, Any] = Field(default_factory=dict)
    extraction_methods: dict[str, str] = Field(default_factory=dict)

