from __future__ import annotations

from copy import deepcopy
from typing import Any

from config import MissingValuePolicy, ProjectionConfig
from models import CandidateProfile
from normalizer import DataNormalizer


class ProjectionError(ValueError):
    pass


class Projector:
    """Applies output-only selection and representation policies."""

    def __init__(self, normalizer: DataNormalizer | None = None) -> None:
        self.normalizer = normalizer or DataNormalizer()

    def project(self, profile: CandidateProfile, config: ProjectionConfig) -> dict[str, Any]:
        canonical = profile.model_dump(mode="json")
        if config.apply_normalization:
            canonical = self._normalize(deepcopy(canonical))

        fields = list(config.fields)
        if config.include_confidence and "confidence" not in fields:
            fields.append("confidence")
        if config.include_provenance and "provenance" not in fields:
            fields.append("provenance")
        if not config.include_confidence:
            fields = [field for field in fields if field != "confidence"]
        if not config.include_provenance:
            fields = [field for field in fields if field != "provenance"]

        result: dict[str, Any] = {}
        for field in fields:
            value = canonical.get(field)
            output_name = config.rename.get(field, field)
            if self._missing(value):
                if config.missing_value_policy == MissingValuePolicy.OMIT:
                    continue
                if config.missing_value_policy == MissingValuePolicy.ERROR:
                    raise ProjectionError(f"Candidate {profile.candidate_id} is missing required output field '{field}'")
                value = None
            result[output_name] = value
        return result

    def _normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        data["emails"] = self.normalizer.unique_normalized(data.get("emails", []), self.normalizer.email)
        data["phones"] = self.normalizer.unique_normalized(data.get("phones", []), self.normalizer.phone)
        data["skills"] = self.normalizer.unique_normalized(data.get("skills", []), self.normalizer.skill)
        if isinstance(data.get("location"), dict):
            data["location"]["country"] = self.normalizer.country(data["location"].get("country"))
        for collection in ("experience", "education"):
            for item in data.get(collection, []):
                item["start_date"] = self.normalizer.date(item.get("start_date"))
                item["end_date"] = self.normalizer.date(item.get("end_date"))
        return data

    @staticmethod
    def _missing(value: Any) -> bool:
        if value in (None, "", [], {}):
            return True
        if isinstance(value, dict):
            return not any(item not in (None, "", [], {}) for item in value.values())
        return False

