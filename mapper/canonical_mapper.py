from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from typing import Any

from models.candidate import CandidateProfile, Education, Experience, Links, Location
from models.source import ProvenanceRecord, SourceRecord
from normalizer import DataNormalizer


class CanonicalMapper:
    """Maps parser-neutral fields into the canonical model."""

    ALIASES: dict[str, tuple[str, ...]] = {
        "full_name": ("full_name", "name", "candidate_name", "displayName"),
        "emails": ("emails", "email", "email_address", "contact.email"),
        "phones": ("phones", "phone", "phone_number", "mobile", "contact.phone"),
        "headline": ("headline", "title", "current_title", "summary"),
        "years_experience": ("years_experience", "experience_years", "total_experience"),
        "skills": ("skills", "technical_skills", "skill_set"),
        "experience": ("experience", "work_experience", "employment"),
        "education": ("education", "academic_history"),
        "location": ("location", "address"),
        "linkedin": ("linkedin", "linkedin_url", "links.linkedin"),
        "github": ("github", "github_url", "links.github"),
        "portfolio": ("portfolio", "website", "personal_url", "links.portfolio"),
    }

    def __init__(self, normalizer: DataNormalizer | None = None) -> None:
        self.normalizer = normalizer or DataNormalizer()

    def map(self, record: SourceRecord) -> CandidateProfile:
        profile = CandidateProfile(candidate_id=self._temporary_id(record))
        provenance: dict[str, list[ProvenanceRecord]] = {}

        name, name_key = self._lookup(record.fields, self.ALIASES["full_name"])
        profile.full_name = self.normalizer.name(name)
        self._track(provenance, "full_name", record, name_key, name)

        emails, email_key = self._lookup(record.fields, self.ALIASES["emails"])
        profile.emails = self.normalizer.unique_normalized(self._as_list(emails), self.normalizer.email)
        self._track(provenance, "emails", record, email_key, emails, bool(profile.emails))

        phones, phone_key = self._lookup(record.fields, self.ALIASES["phones"])
        profile.phones = self.normalizer.unique_normalized(self._as_list(phones), self.normalizer.phone)
        self._track(provenance, "phones", record, phone_key, phones, bool(profile.phones))

        headline, headline_key = self._lookup(record.fields, self.ALIASES["headline"])
        profile.headline = self.normalizer.name(headline)
        self._track(provenance, "headline", record, headline_key, headline)

        years, years_key = self._lookup(record.fields, self.ALIASES["years_experience"])
        profile.years_experience = self._number(years)
        self._track(provenance, "years_experience", record, years_key, years, profile.years_experience is not None)

        skills, skills_key = self._lookup(record.fields, self.ALIASES["skills"])
        profile.skills = self.normalizer.unique_normalized(self._split_list(skills), self.normalizer.skill)
        self._track(provenance, "skills", record, skills_key, skills, bool(profile.skills))

        location, location_key = self._lookup(record.fields, self.ALIASES["location"])
        profile.location = self._location(location, record.fields)
        if location_key:
            self._track(provenance, "location", record, location_key, location, profile.location is not None)
        elif profile.location is not None:
            # Some flat exports provide city/state/country without a location container.
            for component in ("city", "region", "state", "country", "country_code"):
                actual = next((key for key in record.fields if key.casefold() == component), None)
                if actual and record.fields[actual] not in (None, ""):
                    self._track(provenance, "location", record, actual, record.fields[actual])

        links = {}
        link_sources: list[tuple[str, Any]] = []
        for link_type in ("linkedin", "github", "portfolio"):
            value, key = self._lookup(record.fields, self.ALIASES[link_type])
            normalized = self.normalizer.url(value)
            if normalized:
                links[link_type] = normalized
                link_sources.append((key or link_type, value))
        profile.links = Links(**links)
        for key, value in link_sources:
            self._track(provenance, "links", record, key, value)

        raw_experience, experience_key = self._lookup(record.fields, self.ALIASES["experience"])
        profile.experience = self._experience(raw_experience)
        self._track(provenance, "experience", record, experience_key, raw_experience, bool(profile.experience))

        raw_education, education_key = self._lookup(record.fields, self.ALIASES["education"])
        profile.education = self._education(raw_education)
        self._track(provenance, "education", record, education_key, raw_education, bool(profile.education))

        provenance["candidate_id"] = [ProvenanceRecord(
            source=record.source,
            source_id=record.source_id,
            extraction_method="stable_hash",
            original_field=None,
            value=profile.candidate_id,
        )]
        profile.provenance = provenance
        return profile

    @staticmethod
    def _temporary_id(record: SourceRecord) -> str:
        digest = hashlib.sha256(f"{record.source}:{record.source_id}".encode()).hexdigest()[:16]
        return f"src_{digest}"

    @staticmethod
    def _lookup(fields: dict[str, Any], aliases: tuple[str, ...]) -> tuple[Any, str | None]:
        folded = {key.casefold(): key for key in fields}
        for alias in aliases:
            current: Any = fields
            found = True
            for part in alias.split("."):
                if not isinstance(current, dict):
                    found = False
                    break
                actual = next((key for key in current if key.casefold() == part.casefold()), None)
                if actual is None:
                    found = False
                    break
                current = current[actual]
            if found and current not in (None, "", [], {}):
                return current, alias
            direct = folded.get(alias.casefold())
            if direct and fields[direct] not in (None, "", [], {}):
                return fields[direct], direct
        return None, None

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        if value is None:
            return []
        return value if isinstance(value, list) else [value]

    @classmethod
    def _split_list(cls, value: Any) -> list[Any]:
        result: list[Any] = []
        for item in cls._as_list(value):
            if isinstance(item, str):
                result.extend(part.strip() for part in re.split(r"[,;|]", item) if part.strip())
            elif isinstance(item, dict):
                result.append(item.get("name") or item.get("skill"))
            else:
                result.append(item)
        return [item for item in result if item is not None]

    def _location(self, raw: Any, fields: dict[str, Any]) -> Location | None:
        if isinstance(raw, dict):
            city = self.normalizer.name(raw.get("city"))
            region = self.normalizer.name(raw.get("region") or raw.get("state"))
            country = self.normalizer.country(raw.get("country") or raw.get("country_code"))
        elif isinstance(raw, str):
            parts = [part.strip() for part in raw.split(",")]
            city = parts[0] if len(parts) >= 2 else None
            region = parts[-2] if len(parts) >= 3 else None
            country = self.normalizer.country(parts[-1])
        else:
            city = self.normalizer.name(fields.get("city"))
            region = self.normalizer.name(fields.get("region") or fields.get("state"))
            country = self.normalizer.country(fields.get("country") or fields.get("country_code"))
        return Location(city=city, region=region, country=country) if any((city, region, country)) else None

    def _experience(self, raw: Any) -> list[Experience]:
        if not isinstance(raw, list):
            return []
        result: list[Experience] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            company = self.normalizer.name(item.get("company") or item.get("organization") or item.get("employer"))
            if not company:
                continue
            result.append(Experience(
                company=company,
                title=self.normalizer.name(item.get("title") or item.get("position")),
                start_date=self.normalizer.date(item.get("start_date") or item.get("start")),
                end_date=self.normalizer.date(item.get("end_date") or item.get("end")),
                description=self.normalizer.name(item.get("description")),
            ))
        return result

    def _education(self, raw: Any) -> list[Education]:
        if not isinstance(raw, list):
            return []
        result: list[Education] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            institution = self.normalizer.name(item.get("institution") or item.get("school") or item.get("university"))
            if not institution:
                continue
            result.append(Education(
                institution=institution,
                degree=self.normalizer.name(item.get("degree")),
                field_of_study=self.normalizer.name(item.get("field_of_study") or item.get("field")),
                start_date=self.normalizer.date(item.get("start_date") or item.get("start")),
                end_date=self.normalizer.date(item.get("end_date") or item.get("end")),
            ))
        return result

    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None:
            return None
        match = re.search(r"\d+(?:\.\d+)?", str(value))
        if not match:
            return None
        parsed = float(match.group())
        return parsed if 0 <= parsed <= 80 else None

    @staticmethod
    def _track(
        target: dict[str, list[ProvenanceRecord]], canonical: str, record: SourceRecord,
        original: str | None, value: Any, valid: bool = True,
    ) -> None:
        if original is None or not valid:
            return
        method = record.extraction_methods.get(original, "mapped_field")
        target.setdefault(canonical, []).append(ProvenanceRecord(
            source=record.source,
            source_id=record.source_id,
            extraction_method=method,
            original_field=original,
            value=value,
        ))
