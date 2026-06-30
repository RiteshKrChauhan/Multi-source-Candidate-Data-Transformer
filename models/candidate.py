from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.source import ProvenanceRecord


class Location(BaseModel):
    model_config = ConfigDict(extra="forbid")
    city: str | None = None
    region: str | None = None
    country: str | None = None


class Links(BaseModel):
    model_config = ConfigDict(extra="forbid")
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None


class Experience(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company: str
    title: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class Education(BaseModel):
    model_config = ConfigDict(extra="forbid")
    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class CandidateProfile(BaseModel):
    """Canonical profile used by all post-mapping business logic."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = ""
    full_name: str | None = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    location: Location | None = None
    links: Links = Field(default_factory=Links)
    headline: str | None = None
    years_experience: float | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    provenance: dict[str, list[ProvenanceRecord]] = Field(default_factory=dict)
    confidence: dict[str, float] = Field(default_factory=dict)
    overall_confidence: float = 0.0

    @field_validator("years_experience")
    @classmethod
    def non_negative_experience(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("years_experience cannot be negative")
        return value

    def field_value(self, name: str) -> Any:
        return getattr(self, name)

