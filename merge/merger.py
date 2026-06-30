from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Any, TypeVar

from models import CandidateProfile, Education, Experience, Links, Location, ProvenanceRecord, SourceType


T = TypeVar("T")


class CandidateMerger:
    SOURCE_PRIORITY = {
        SourceType.RESUME: 0,
        SourceType.LINKEDIN: 1,
        SourceType.ATS: 2,
        SourceType.CSV: 3,
        SourceType.GITHUB: 4,
    }
    ID_NAMESPACE = uuid.UUID("71518fe1-e18d-49ae-a2bc-77b83ae43217")

    def merge(self, group: list[CandidateProfile]) -> CandidateProfile:
        if not group:
            raise ValueError("Cannot merge an empty candidate group")
        ordered = sorted(group, key=self._profile_priority)
        provenance = self._merge_provenance(ordered)
        full_name = self._best_name(ordered)
        links = self._merge_links(ordered)
        merged = CandidateProfile(
            candidate_id=self._candidate_id(ordered),
            full_name=full_name,
            emails=self._union(ordered, lambda profile: profile.emails),
            phones=self._union(ordered, lambda profile: profile.phones),
            location=self._merge_location(ordered),
            links=links,
            headline=self._first(ordered, lambda profile: profile.headline),
            years_experience=self._first(ordered, lambda profile: profile.years_experience),
            skills=self._union(ordered, lambda profile: profile.skills),
            experience=self._merge_complex(ordered, "experience"),
            education=self._merge_complex(ordered, "education"),
            provenance=provenance,
        )
        primary = self._primary_provenance(ordered)
        merged.provenance["candidate_id"] = [ProvenanceRecord(
            source=primary.source,
            source_id=primary.source_id,
            extraction_method="stable_hash",
            original_field=None,
            value=merged.candidate_id,
        )]
        return merged

    def _profile_priority(self, profile: CandidateProfile) -> tuple[int, str]:
        sources = [record.source for records in profile.provenance.values() for record in records]
        rank = min((self.SOURCE_PRIORITY[source] for source in sources), default=99)
        return rank, profile.candidate_id

    def _best_name(self, profiles: list[CandidateProfile]) -> str | None:
        candidates = [(profile.full_name, self._profile_priority(profile)) for profile in profiles if profile.full_name]
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: (-len(item[0]), item[1], item[0].casefold()))[0][0]

    @staticmethod
    def _first(profiles: list[CandidateProfile], getter: Callable[[CandidateProfile], T | None]) -> T | None:
        return next((value for profile in profiles if (value := getter(profile)) is not None), None)

    @staticmethod
    def _union(profiles: list[CandidateProfile], getter: Callable[[CandidateProfile], list[str]]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for profile in profiles:
            for value in getter(profile):
                if value.casefold() not in seen:
                    seen.add(value.casefold())
                    result.append(value)
        return result

    def _merge_location(self, profiles: list[CandidateProfile]) -> Location | None:
        values: dict[str, str] = {}
        for field in ("city", "region", "country"):
            value = self._first(profiles, lambda profile, f=field: getattr(profile.location, f) if profile.location else None)
            if value:
                values[field] = value
        return Location(**values) if values else None

    def _merge_links(self, profiles: list[CandidateProfile]) -> Links:
        values: dict[str, str] = {}
        for field in ("linkedin", "github", "portfolio"):
            value = self._first(profiles, lambda profile, f=field: getattr(profile.links, f))
            if value:
                values[field] = value
        return Links(**values)

    def _merge_complex(self, profiles: list[CandidateProfile], field: str) -> list[Any]:
        result: list[Any] = []
        index: dict[tuple[str, str, str], int] = {}
        for profile in profiles:
            for item in getattr(profile, field):
                if isinstance(item, Experience):
                    key = (item.company.casefold(), (item.title or "").casefold(), item.start_date or "")
                else:
                    key = (item.institution.casefold(), (item.degree or "").casefold(), "")
                if key not in index:
                    index[key] = len(result)
                    result.append(item)
                else:
                    current = result[index[key]]
                    values = current.model_dump()
                    for name, value in item.model_dump().items():
                        if not values.get(name) or (isinstance(value, str) and len(value) > len(str(values[name]))):
                            values[name] = value
                    result[index[key]] = type(current)(**values)
        return result

    @staticmethod
    def _merge_provenance(profiles: list[CandidateProfile]) -> dict[str, list[ProvenanceRecord]]:
        result: dict[str, list[ProvenanceRecord]] = {}
        seen: set[str] = set()
        for profile in profiles:
            for field, records in profile.provenance.items():
                for record in records:
                    signature = json.dumps(record.model_dump(mode="json"), sort_keys=True, default=str)
                    if signature not in seen:
                        seen.add(signature)
                        result.setdefault(field, []).append(record)
        return result

    @staticmethod
    def _candidate_id(profiles: list[CandidateProfile]) -> str:
        identifiers: list[str] = []
        for profile in profiles:
            identifiers.extend(f"email:{value}" for value in profile.emails)
            identifiers.extend(f"phone:{value}" for value in profile.phones)
            identifiers.extend(f"link:{value}" for value in profile.links.model_dump().values() if value)
        if not identifiers:
            identifiers = [f"name:{profile.full_name.casefold()}" for profile in profiles if profile.full_name]
        if not identifiers:
            identifiers = [profile.candidate_id for profile in profiles]
        stable_key = "|".join(sorted(set(identifiers)))
        return f"cand_{uuid.uuid5(CandidateMerger.ID_NAMESPACE, stable_key).hex}"

    @staticmethod
    def _primary_provenance(profiles: list[CandidateProfile]) -> ProvenanceRecord:
        for profile in profiles:
            for records in profile.provenance.values():
                if records:
                    return records[0]
        raise ValueError("Mapped profiles must contain at least one provenance record")
