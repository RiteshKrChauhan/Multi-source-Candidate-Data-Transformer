from __future__ import annotations

from typing import Any

from models import CandidateProfile, ProvenanceRecord, SourceType


class ConfidenceScorer:
    SOURCE_RELIABILITY = {
        SourceType.RESUME: 0.95,
        SourceType.LINKEDIN: 0.92,
        SourceType.ATS: 0.85,
        SourceType.CSV: 0.75,
        SourceType.GITHUB: 0.70,
    }
    METHOD_RELIABILITY = {
        "structured_json": 0.98,
        "structured_column": 0.95,
        "mapped_field": 0.90,
        "regex": 0.82,
        "header_heuristic": 0.78,
        "section_heuristic": 0.76,
        "stable_hash": 1.0,
        "calculated": 0.95,
    }
    FIELD_WEIGHTS = {
        "full_name": 1.2, "emails": 1.4, "phones": 1.2, "links": 1.0,
        "location": 0.7, "headline": 0.6, "years_experience": 0.8,
        "skills": 1.0, "experience": 1.1, "education": 0.9,
    }
    SCORE_FIELDS = tuple(FIELD_WEIGHTS)

    def score(self, profile: CandidateProfile) -> CandidateProfile:
        scores: dict[str, float] = {}
        for field in self.SCORE_FIELDS:
            value = getattr(profile, field)
            records = profile.provenance.get(field, [])
            scores[field] = self._field_score(value, records)
        profile.confidence = scores
        populated = [
            (scores[field], weight) for field, weight in self.FIELD_WEIGHTS.items()
            if self._present(getattr(profile, field))
        ]
        profile.overall_confidence = round(
            sum(score * weight for score, weight in populated) / sum(weight for _, weight in populated), 3
        ) if populated else 0.0
        primary = next(
            (record for records in profile.provenance.values() for record in records), None
        )
        if primary is not None:
            profile.provenance["confidence"] = [ProvenanceRecord(
                source=primary.source, source_id=primary.source_id,
                extraction_method="calculated", value=scores,
            )]
            profile.provenance["overall_confidence"] = [ProvenanceRecord(
                source=primary.source, source_id=primary.source_id,
                extraction_method="calculated", value=profile.overall_confidence,
            )]
        return profile

    def _field_score(self, value: Any, records: list[Any]) -> float:
        if not self._present(value) or not records:
            return 0.0
        source_scores = [self.SOURCE_RELIABILITY.get(record.source, 0.6) for record in records]
        method_scores = [self.METHOD_RELIABILITY.get(record.extraction_method, 0.70) for record in records]
        base = max(source_scores) * 0.7 + max(method_scores) * 0.3
        corroboration = min(0.08, 0.03 * (len({record.source for record in records}) - 1))
        completeness = 0.02 if isinstance(value, list) and len(value) > 1 else 0.0
        return round(min(1.0, base + corroboration + completeness), 3)

    @staticmethod
    def _present(value: Any) -> bool:
        if value is None or value == "" or value == [] or value == {}:
            return False
        if hasattr(value, "model_dump"):
            return any(v not in (None, "", [], {}) for v in value.model_dump().values())
        return True
