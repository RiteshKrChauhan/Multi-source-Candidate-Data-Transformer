from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CANONICAL_FIELDS = {
    "candidate_id", "full_name", "emails", "phones", "location", "links",
    "headline", "years_experience", "skills", "experience", "education",
    "provenance", "confidence", "overall_confidence",
}


class MissingValuePolicy(StrEnum):
    NULL = "null"
    OMIT = "omit"
    ERROR = "error"


class ProjectionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: list[str] = Field(default_factory=lambda: [
        "candidate_id", "full_name", "emails", "phones", "location", "links",
        "headline", "years_experience", "skills", "experience", "education",
        "overall_confidence",
    ])
    rename: dict[str, str] = Field(default_factory=dict)
    include_confidence: bool = True
    include_provenance: bool = True
    apply_normalization: bool = True
    missing_value_policy: MissingValuePolicy = MissingValuePolicy.NULL

    @field_validator("fields")
    @classmethod
    def valid_fields(cls, fields: list[str]) -> list[str]:
        invalid = sorted(set(fields) - CANONICAL_FIELDS)
        if invalid:
            raise ValueError(f"Unknown projection fields: {', '.join(invalid)}")
        if len(fields) != len(set(fields)):
            raise ValueError("Projection fields must be unique")
        return fields

    @field_validator("rename")
    @classmethod
    def valid_renames(cls, rename: dict[str, str]) -> dict[str, str]:
        invalid = sorted(set(rename) - CANONICAL_FIELDS)
        if invalid:
            raise ValueError(f"Cannot rename unknown fields: {', '.join(invalid)}")
        if any(not name.strip() for name in rename.values()):
            raise ValueError("Renamed fields cannot be blank")
        if len(rename.values()) != len(set(rename.values())):
            raise ValueError("Renamed output fields must be unique")
        return rename

    @model_validator(mode="after")
    def no_output_name_collisions(self) -> "ProjectionConfig":
        enabled = list(self.fields)
        if self.include_confidence and "confidence" not in enabled:
            enabled.append("confidence")
        if self.include_provenance and "provenance" not in enabled:
            enabled.append("provenance")
        output_names = [self.rename.get(field, field) for field in enabled]
        if len(output_names) != len(set(output_names)):
            raise ValueError("Projection renames produce duplicate output field names")
        return self

    @classmethod
    def from_file(cls, path: str | Path | None) -> "ProjectionConfig":
        if path is None:
            return cls()
        with Path(path).open(encoding="utf-8") as handle:
            return cls.model_validate(json.load(handle))
